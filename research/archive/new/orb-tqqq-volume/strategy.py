"""TQQQ opening-range breakout with volume and ATR confirmation (intraday only).

Rules
-----
Universe   : adjusted 1-minute TQQQ, flat asset cash (BIL optional).
Opening range: 09:30-09:59 ET (first 30 minutes of the regular session).
Session filters (all known by 10:00):
  gap      : today's TQQQ open > prior session's close.
  volume   : opening-range volume / mean of the prior 20 sessions'
             opening-range volume is in [vol_lo, vol_hi].  The band is a
             participation filter: a dead tape is not trusted, and a 2x+
             news spike is treated as exhaustion rather than confirmation.
  ATR      : (or_hi - or_lo) <= max_or_atr * ATR14.  A range that is already
             a large fraction of the daily ATR has spent its move.
Entry      : first 1-minute close after 10:00 above or_hi (plus a small
             buffer), at most 60 minutes before the session close.  The
             weight is set on that bar's close and filled at the next open.
Stop       : entry fill - stop_atr * ATR14, checked on every subsequent
             1-minute low.  The exit signal is set on the breach bar and
             filled at the next open (conservative: gaps through the stop).
Target     : optional fixed percentage; same next-open fill convention.
Exit       : stop, target, or the second-to-last bar of the session.  The
             last-bar-open exit keeps the book flat overnight (cash/BIL).
Position   : 100% TQQQ while in a trade, otherwise cash (100% BIL when
             flat="BIL").  One trade per session, no re-entry.  Long only,
             weights sum to <= 1.

All indicators use data through the signal bar: ATR is shifted one session,
the volume baseline is shifted one session and needs all 20 prior sessions,
and the opening range ends at 09:59.  No full-sample statistics are used.
A session needs at least min(10, or_min) one-minute opening-range bars.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
OUT = Path(__file__).resolve().parent

CFG = dict(
    or_min=30,
    gap_min=0.0,          # strictly greater than this
    vol_lo=0.7,
    vol_hi=1.6,
    max_or_atr=0.6,
    stop_atr=0.55,
    target=None,          # e.g. 0.03 for a fixed 3% target
    buffer_bps=0.0,
    entry_cutoff_min=60,  # no entries in the last 60 minutes
    flat="cash",          # "cash" or "BIL"
)

# Pre-registered 8-cell grid (written into HYPOTHESIS.md before this run).
GRID = [
    ("core_or30_vol_atr_stop55", {}),
    ("no_volume_filter", dict(vol_lo=None, vol_hi=None)),
    ("no_or_atr_filter", dict(max_or_atr=None)),
    ("stop_0.35atr", dict(stop_atr=0.35)),
    ("stop_0.75atr", dict(stop_atr=0.75)),
    ("or15", dict(or_min=15)),
    ("or45", dict(or_min=45)),
    ("core_plus_3pct_target", dict(target=0.03)),
]


def load_dev():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("TQQQ")


def session_tables(ts, t, or_min=30):
    """Per-session opening range, ATR, volume baseline and gap (all causal)."""
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    tod = np.asarray(ts.hour * 60 + ts.minute)
    hi, lo, cl, vol, op = (t[c].to_numpy() for c in ("high", "low", "close", "volume", "open"))
    n = len(starts)
    out = dict(date=dates[starts], starts=starts, ends=ends,
               or_hi=np.full(n, np.nan), or_lo=np.full(n, np.nan),
               or_vol=np.full(n, np.nan), atr14=np.full(n, np.nan),
               gap=np.full(n, np.nan), rvol=np.full(n, np.nan),
               day_open=op[starts], day_close=cl[ends - 1],
               day_high=np.array([hi[s:e].max() for s, e in zip(starts, ends)]),
               day_low=np.array([lo[s:e].min() for s, e in zip(starts, ends)]))
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = int(np.searchsorted(tod[s:e], 9 * 60 + 30 + or_min))
        if j < min(10, or_min):
            continue
        out["or_hi"][k] = hi[s:s + j].max()
        out["or_lo"][k] = lo[s:s + j].min()
        out["or_vol"][k] = vol[s:s + j].sum()
    d = pd.DataFrame({"or_vol": out["or_vol"], "high": out["day_high"],
                      "low": out["day_low"], "close": out["day_close"]})
    prev_close = d["close"].shift(1)
    tr = np.maximum(d["high"] - d["low"],
                    np.maximum((d["high"] - prev_close).abs(),
                               (d["low"] - prev_close).abs()))
    out["atr14"] = tr.shift(1).rolling(14).mean().to_numpy()
    out["gap"] = (out["day_open"] / prev_close.to_numpy() - 1.0)
    out["rvol"] = (d["or_vol"] / d["or_vol"].shift(1).rolling(20).mean()).to_numpy()
    return out


def _build(ts, o, c, cfg=CFG, bars=None, log=None):
    if bars is None:
        bars = load_dev()[3]
    c = dict(CFG)
    c.update(cfg)
    hi = bars["high"].to_numpy()
    lo = bars["low"].to_numpy()
    cl = bars["close"].to_numpy()
    op = bars["open"].to_numpy()
    tod = np.asarray(ts.hour * 60 + ts.minute)
    st = session_tables(ts, bars, c["or_min"])
    n = len(ts)
    w = np.zeros((n, 3))
    flat_col = 2 if c["flat"] == "BIL" else None
    if flat_col is not None:
        w[:, flat_col] = 1.0  # BIL by default
    info = dict(entries=0, stops=0, targets=0, eod=0, filtered_gap=0,
                filtered_vol=0, filtered_atr=0, no_breakout=0, hold_bars=[])
    buf = c["buffer_bps"] / 1e4
    n_sessions = len(st["starts"])
    for k in range(n_sessions):
        s, e = st["starts"][k], st["ends"][k]
        if not np.isfinite(st["or_hi"][k]) or not np.isfinite(st["atr14"][k]):
            continue
        if c["gap_min"] is not None and not (st["gap"][k] > c["gap_min"]):
            info["filtered_gap"] += 1
            continue
        if c["vol_lo"] is not None:
            rv = st["rvol"][k]
            if not np.isfinite(rv) or not (c["vol_lo"] <= rv <= c["vol_hi"]):
                info["filtered_vol"] += 1
                continue
        if c["max_or_atr"] is not None:
            if (st["or_hi"][k] - st["or_lo"][k]) > c["max_or_atr"] * st["atr14"][k]:
                info["filtered_atr"] += 1
                continue
        j0 = int(np.searchsorted(tod[s:e], 9 * 60 + 30 + c["or_min"]))
        last_tod = tod[e - 1]
        cutoff = last_tod - c["entry_cutoff_min"]
        entry_i = -1
        for i in range(s + j0, e - 2):
            if tod[i] > cutoff:
                break
            if cl[i] > st["or_hi"][k] * (1.0 + buf):
                entry_i = i
                break
        if entry_i < 0:
            info["no_breakout"] += 1
            continue
        entry_px = op[entry_i + 1]
        stop = entry_px - c["stop_atr"] * st["atr14"][k] if c["stop_atr"] else -np.inf
        target = entry_px * (1.0 + c["target"]) if c["target"] else np.inf
        info["entries"] += 1
        # Signal at the entry bar's close, filled at the next open.
        w[entry_i, 1] = 1.0
        if flat_col is not None:
            w[entry_i, 2] = 0.0
        exited = False
        exit_i = e - 1
        exit_kind = "eod"
        hold = 0
        for j in range(entry_i + 1, e - 2):
            hold += 1
            if lo[j] <= stop:
                w[j, 1] = 0.0
                if flat_col is not None:
                    w[j, 2] = 1.0
                info["stops"] += 1
                exited = True
                exit_i, exit_kind = j + 1, "stop"
                break
            if hi[j] >= target:
                w[j, 1] = 0.0
                if flat_col is not None:
                    w[j, 2] = 1.0
                info["targets"] += 1
                exited = True
                exit_i, exit_kind = j + 1, "target"
                break
            w[j, 1] = 1.0
            if flat_col is not None:
                w[j, 2] = 0.0
        if not exited:
            w[e - 2, 1] = 0.0
            if flat_col is not None:
                w[e - 2, 2] = 1.0
            info["eod"] += 1
            exit_i, exit_kind = e - 1, "eod"
        info["hold_bars"].append(hold)
        if log is not None:
            log.append(dict(date=st["date"][k], entry_min=int(tod[entry_i]),
                            entry_i=int(entry_i), entry_px=float(entry_px),
                            exit_i=int(exit_i), exit_px=float(op[exit_i]),
                            ret=float(op[exit_i] / entry_px - 1.0),
                            kind=exit_kind, stop=float(stop),
                            atr=float(st["atr14"][k]), rvol=float(st["rvol"][k]),
                            gap=float(st["gap"][k]),
                            or_width=float(st["or_hi"][k] - st["or_lo"][k])))
    return w, info


def load_full(ts):
    """Full-panel TQQQ OHLCV aligned to `ts` (holdout adapter).

    The frozen dev loader stops at 2023-12-29.  This adapter reads the same
    1-minute TQQQ archive through the panel's actual end and aligns it to the
    requested bars; it changes no signal or parameter.
    """
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("TQQQ")
    return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()


def build_weights(ts, o, c, bars=None):
    """Required public API. Returns (n, 3) weights: QQQ, TQQQ, BIL.

    `bars` is an optional TQQQ OHLCV frame aligned to `ts`.  When omitted, the
    frozen dev loader is used (2016-2023 only).  A full-panel holdout must pass
    load_full(ts).
    """
    return _build(ts, o, c, CFG, bars)[0]


def build_holdout_weights(ts, o, c):
    """Full-panel holdout entry point: same frozen logic, full TQQQ bars."""
    return build_weights(ts, o, c, bars=load_full(ts))


def metrics(ts, opens, closes, w, slip):
    res = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=slip)
    s = bt.stats(res, BARS_1M)
    i = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(closes[i:, 1], ts[i:], BARS_1M)
    eq = pd.Series(res["equity"], index=res["ts"])
    daily = eq.groupby(eq.index.date).last()
    dr = daily.pct_change().dropna()
    peak_d = np.maximum.accumulate(daily.to_numpy())
    dd_d = float(-(daily.to_numpy() / peak_d - 1.0).min())
    sharpe_d = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
    bench_daily = pd.Series(closes[i:, 1], index=ts[i:])
    bench_daily = bench_daily.groupby(bench_daily.index.date).last().pct_change().dropna()
    corr = float(dr.corr(bench_daily.reindex(dr.index)))
    yr = bt.yearly(res["ts"], res["equity"], closes[i:i + len(res["ts"]), 1])
    wslice = w[i:i + len(res["ts"])]
    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": dd_d,
        "sharpe": float(s["sharpe"]),
        "sharpe_daily": sharpe_d,
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "total_return": float(s["total_return"]),
        "ending_equity": float(s["ending_equity"]),
        "years": float(s["years"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure_total": float(s["exposure"]),
        "tqqq_exposure": float(np.mean(wslice[:, 1] > 0)),
        "bil_exposure": float(np.mean(wslice[:, 2] > 0)),
        "corr_to_tqqq_daily": corr,
        "yearly": {str(y): {"strategy": float(v["strategy"]),
                            "benchmark": float(v["benchmark"])}
                   for y, v in yr.items()},
        "benchmark": {"cagr": float(bench["cagr"]),
                      "max_drawdown": float(bench["max_drawdown"]),
                      "sharpe": float(bench["sharpe"]),
                      "volatility": float(bench["volatility"])},
    }
    return out, res


def main():
    ts, opens, closes, bars = load_dev()
    core_w, info = _build(ts, opens, closes, CFG, bars)
    i0 = bt.start_index(ts, DEV_START)
    def bench(col):
        b = bt.benchmark(closes[i0:, col], ts[i0:], BARS_1M)
        return {"cagr": float(b["cagr"]), "max_drawdown": float(b["max_drawdown"]),
                "sharpe": float(b["sharpe"]), "volatility": float(b["volatility"])}
    result = {
        "agent": "orb-tqqq-volume",
        "status": "negative_result",
        "strategy": "TQQQ 30-min ORB, gap/volume/ATR confirmation, ATR stop, EOD flat",
        "window": {"start": DEV_START, "end": DEV_END},
        "config": {k: v for k, v in CFG.items()},
        "rules": {
            "opening_range": "09:30-09:59 ET",
            "entry": "first 1m close > OR high after 10:00, next-open fill",
            "session_filters": "gap>0, opening volume ratio in [0.7,1.6], OR width <= 0.6*ATR14",
            "stop": "entry - 0.55*ATR14, 1m low breach, next-open fill",
            "exit": "stop or second-to-last bar of session (last-open fill)",
            "overnight": "flat; cash (BIL-flat variant reported in the report)",
            "flat_asset": CFG["flat"],
            "slippage_bps": [1.0, 5.0, 10.0],
            "band": 0.02,
        },
        "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82,
                "source": "task brief; harness-computed dev benchmark also below"},
        "benchmarks": {"tqqq": bench(1), "qqq": bench(0), "bil": bench(2)},
        "diagnostics": {
            "entries": info["entries"], "stops": info["stops"],
            "targets": info["targets"], "eod": info["eod"],
            "filtered_gap": info["filtered_gap"], "filtered_volume": info["filtered_vol"],
            "filtered_atr": info["filtered_atr"], "no_breakout": info["no_breakout"],
            "entries_logged": int(len(info["hold_bars"])),
            "avg_hold_bars": float(np.mean(info["hold_bars"])) if info["hold_bars"] else 0.0,
        },
        "windows": {"dev": {}},
        "grid": {},
    }
    for slip, key in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        m, _ = metrics(ts, opens, closes, core_w, slip)
        result["windows"]["dev"][key] = m
    m1 = result["windows"]["dev"]["1bp"]
    result["pass"] = {
        "cagr_above_bar": bool(m1["cagr"] > 0.3672),
        "drawdown_below_bar": bool(m1["max_drawdown"] < 0.8229),
        "sharpe_above_bar": bool(m1["sharpe"] > 0.82),
        "calmar": float(m1["cagr"] / m1["max_drawdown"]),
        "benchmark_calmar": float(m1["benchmark"]["cagr"] / m1["benchmark"]["max_drawdown"]),
        "note": "Risk-adjusted improvement only unless CAGR also clears the bar.",
    }
    for name, over in GRID:
        w, inf = _build(ts, opens, closes, dict(CFG, **over), bars)
        m, _ = metrics(ts, opens, closes, w, 1.0)
        result["grid"][name] = {
            "overrides": over, "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe"], "tqqq_exposure": m["tqqq_exposure"],
            "fills": m["fills"], "corr_to_tqqq_daily": m["corr_to_tqqq_daily"],
            "entries": inf["entries"],
        }
    # Sanity: finite numbers.
    for key in ("1bp", "5bp", "10bp"):
        for k, v in result["windows"]["dev"][key].items():
            if isinstance(v, float) and not np.isfinite(v):
                raise ValueError(f"non-finite dev {key} {k}")
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    for key in ("1bp", "5bp", "10bp"):
        m = result["windows"]["dev"][key]
        print(f"dev {key}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:6.2f}%  "
              f"Sharpe {m['sharpe']:.2f}  fills {m['fills']}  turnover {m['turnover']:.0f}x  "
              f"TQQQ exp {m['tqqq_exposure']*100:.1f}%  corr {m['corr_to_tqqq_daily']:.2f}")
    b = result["windows"]["dev"]["1bp"]["benchmark"]
    print(f"benchmark: CAGR {b['cagr']*100:.2f}%  DD {b['max_drawdown']*100:.2f}%  "
          f"Sharpe {b['sharpe']:.2f}")
    print("\ngrid (1bp):")
    for name, g in result["grid"].items():
        print(f"  {name:28s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:6.2f}%  "
              f"Sharpe {g['sharpe']:.2f}  trades {g['entries']}  exp {g['tqqq_exposure']*100:4.1f}%")
    print("\nyearly (1bp):")
    for y, v in result["windows"]["dev"]["1bp"]["yearly"].items():
        print(f"  {y}: {v['strategy']*100:7.2f}%  bench {v['benchmark']*100:7.2f}%")
    print(f"\nwrote {OUT / 'result.json'}")


if __name__ == "__main__":
    main()
