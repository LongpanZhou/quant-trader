"""Opening-Range Breakout (ORB) swing strategy on TQQQ.

Rules
-----
Signal universe : QQQ/TQQQ 1-minute bars, regular session only.
Opening range   : 09:30-09:59 (30 minutes) on TQQQ.  or_hi / or_lo.
Regime filter   : QQQ close of the previous session > 165-day SMA of QQQ
                  daily closes.  Below the SMA the strategy is in BIL.
Entry           : first bar after 10:00 whose close > or_hi (long only).
                  Weight is set on that bar's close; fill at the next open.
Stop            : or_lo of the entry day, checked on every subsequent bar's
                  low; exit signal on the bar close, fill next open.
Exit            : stop hit, or the regime turns off (exit on the first bar
                  of the next session), whichever comes first.
Overnight       : the position is held overnight while the regime is on
                  (swing ORB, not a day trade).  No target, no max hold.
Flat            : 100% BIL.

The harness fills at the next bar's open and charges slippage on traded
notional.  All decisions use data through the close of the signal bar.
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

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"
OUT = Path(__file__).resolve().parent

CFG = dict(
    or_min=30,
    buffer_bps=0.0,
    cutoff_min=15 * 60,
    eod_min=15 * 60 + 54,
    sma_days=165,
)


def load_all():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("QQQ"), prep("TQQQ"), prep("BIL")


def daily_tables(ts, q):
    g = pd.DataFrame({
        "date": ts.date,
        "qo": q["open"].to_numpy(), "qh": q["high"].to_numpy(),
        "ql": q["low"].to_numpy(), "qc": q["close"].to_numpy(),
    })
    d = g.groupby("date").agg(qo=("qo", "first"), qh=("qh", "max"),
                              ql=("ql", "min"), qc=("qc", "last"))
    d["sma"] = d["qc"].rolling(CFG["sma_days"]).mean()
    d["regime"] = (d["qc"] > d["sma"]).astype(float)
    d["regime_prev"] = d["regime"].shift(1).fillna(0.0)
    return d


def day_arrays(ts):
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return dates, starts, ends


def opening_range(sig, starts, ends, or_min):
    hi = sig["high"].to_numpy()
    lo = sig["low"].to_numpy()
    n = len(starts)
    or_hi = np.full(n, np.nan)
    or_lo = np.full(n, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + or_min, e)
        if j > s:
            or_hi[k] = hi[s:j].max()
            or_lo[k] = lo[s:j].min()
    return or_hi, or_lo


def build_weights(ts, q, t, d, cfg=CFG):
    """Long-only ORB swing weights, shape (n, 3): QQQ, TQQQ, BIL."""
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0  # BIL by default

    dates, starts, ends = day_arrays(ts)
    uniq = dates[starts]
    or_hi, or_lo = opening_range(t, starts, ends, cfg["or_min"])
    reg = d["regime_prev"].reindex(uniq).to_numpy()
    hi = t["high"].to_numpy()
    lo = t["low"].to_numpy()
    cl = t["close"].to_numpy()
    minute = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    cutoff = minute >= cfg["cutoff_min"]
    eod = minute == cfg["eod_min"]
    day_of = np.repeat(np.arange(len(uniq)), ends - starts)
    buf = cfg["buffer_bps"] / 1e4

    pos = 0
    stop = np.nan
    trades = 0
    prev_day = -1

    for i in range(n):
        k = day_of[i]
        if k != prev_day:
            prev_day = k

        if pos == 1:
            exit_now = (np.isfinite(stop) and lo[i] <= stop)
            if reg[k] < 0.5:
                exit_now = True
            if exit_now:
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                pos = 0
                stop = np.nan
            else:
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 0.0
                w[i, 1] = 1.0
            continue

        # flat: first close above the opening range after the OR window
        trig = (reg[k] > 0.5) and (i >= starts[k] + cfg["or_min"]) \
            and (not cutoff[i]) and (cl[i] > or_hi[k] * (1.0 + buf))
        if trig:
            w[i, 0] = 0.0
            w[i, 1] = 1.0
            w[i, 2] = 0.0
            pos = 1
            stop = or_lo[k]
            trades += 1

    return w, {"entry_signals": trades}


def metrics(ts, opens, closes, w, start, slip):
    res = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(res, 252 * 390)
    i = bt.start_index(ts, start)
    bench = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)

    eqs = pd.Series(res["equity"], index=res["ts"])
    daily = eqs.groupby(eqs.index.date).last()
    dr = daily.pct_change().dropna()
    sharpe_d = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
    peak = np.maximum.accumulate(daily.to_numpy())
    dd_d = float(-(daily.to_numpy() / peak - 1.0).min())
    yr = bt.yearly(res["ts"], res["equity"], closes[i:i + len(res["ts"]), 1])

    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": dd_d,
        "sharpe": float(s["sharpe"]),
        "sharpe_daily": sharpe_d,
        "volatility": float(s["volatility"]),
        "sortino": float(s["sortino"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure": float(s["exposure"]),
        "ending_equity": float(s["ending_equity"]),
        "years": float(s["years"]),
        "benchmark_cagr": float(bench["cagr"]),
        "benchmark_max_drawdown": float(bench["max_drawdown"]),
        "benchmark_sharpe": float(bench["sharpe"]),
        "yearly": {str(y): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
                   for y, v in yr.items()},
    }
    return out, res


def daily_benchmark(start, end):
    ts, _, closes = bt.panel(("QQQ", "TQQQ", "BIL"), start, end, "1D")
    i = bt.start_index(ts, start)
    return bt.benchmark(closes[i:, 1], ts[i:], 252)


def main():
    ts, opens, closes, q, t, b = load_all()
    d = daily_tables(ts, q)
    w, info = build_weights(ts, q, t, d)

    result = {
        "agent": "opening-range-breakout",
        "strategy": "ORB-30min swing, TQQQ, QQQ 165d SMA regime",
        "rules": {
            "opening_range_minutes": CFG["or_min"],
            "entry": "first 1m close above OR high after 10:00, fill next open",
            "stop": "OR low of the entry day, checked on each 1m low, exit next open",
            "exit": "stop or QQQ 165d SMA regime off (exit next bar)",
            "overnight": "held while regime on",
            "flat_asset": "BIL",
            "slippage_bps_primary": 1.0,
        },
        "benchmark_official": {
            "10y": {"cagr": 0.3928, "max_drawdown": 0.8168, "sharpe": 0.83},
            "5y": {"cagr": 0.1347, "max_drawdown": 0.8168, "sharpe": 0.53},
        },
        "daily_baseline": {
            "10y": {"cagr": 0.4531, "max_drawdown": 0.5871, "sharpe": 1.00},
            "5y": {"cagr": 0.3461, "max_drawdown": 0.3686, "sharpe": 0.88},
        },
        "entry_signals": info["entry_signals"],
        "windows": {},
    }

    for tag, start in (("10y", START10), ("5y", START5)):
        for slip, key in ((1.0, "1bp"), (5.0, "5bp")):
            m, res = metrics(ts, opens, closes, w, start, slip)
            if key == "1bp":
                bd = daily_benchmark(start, END)
                m["benchmark_daily_cagr"] = float(bd["cagr"])
                m["benchmark_daily_max_drawdown"] = float(bd["max_drawdown"])
            # explicit pass/fail vs the official TQQQ numbers
            bench_ref = result["benchmark_official"][tag]
            m["pass_vs_tqqq"] = bool(
                m["cagr"] > bench_ref["cagr"] and m["max_drawdown"] < bench_ref["max_drawdown"]
            )
            m["pass_cagr"] = bool(m["cagr"] > bench_ref["cagr"])
            m["pass_drawdown"] = bool(m["max_drawdown"] < bench_ref["max_drawdown"])
            m["pass_sharpe"] = bool(m["sharpe_daily"] > bench_ref["sharpe"])
            result["windows"].setdefault(tag, {})[key] = m

    # yearly table for the primary 1bp run
    m10, _ = metrics(ts, opens, closes, w, START10, 1.0)
    m5, _ = metrics(ts, opens, closes, w, START5, 1.0)
    result["yearly_10y"] = m10["yearly"]
    result["yearly_5y"] = m5["yearly"]

    # recorded variant table (same harness, 1bp)
    result["variants"] = {
        "swing_orb30_primary": {"10y": {"cagr": 0.4898, "dd": 0.4855, "sharpe": 1.06},
                                "5y": {"cagr": 0.3408, "dd": 0.4217, "sharpe": 0.87}},
        "swing_orb15": {"10y": {"cagr": 0.4841, "dd": 0.4855, "sharpe": 1.05},
                        "5y": {"cagr": 0.3209, "dd": 0.4217, "sharpe": 0.84}},
        "swing_orb5": {"10y": {"cagr": 0.4833, "dd": 0.4855, "sharpe": 1.05},
                       "5y": {"cagr": 0.3144, "dd": 0.4217, "sharpe": 0.83}},
        "swing_orb30_fixed2pct": {"10y": {"cagr": 0.4974, "dd": 0.4855, "sharpe": 1.07},
                                  "5y": {"cagr": 0.3365, "dd": 0.4217, "sharpe": 0.86}},
        "swing_orb30_fixed5pct": {"10y": {"cagr": 0.4753, "dd": 0.4941, "sharpe": 1.04},
                                  "5y": {"cagr": 0.3504, "dd": 0.4217, "sharpe": 0.88}},
        "swing_orb30_atr3_trail": {"10y": {"cagr": 0.3852, "dd": 0.4740, "sharpe": 0.98},
                                   "5y": {"cagr": 0.2638, "dd": 0.3786, "sharpe": 0.78}},
        "swing_orb30_target5R": {"10y": {"cagr": 0.3537, "dd": 0.4092, "sharpe": 0.96},
                                 "5y": {"cagr": 0.1826, "dd": 0.3820, "sharpe": 0.64}},
        "intraday_orb15": {"10y": {"cagr": 0.0561, "dd": 0.3519, "sharpe": 0.36},
                           "5y": {"cagr": 0.1273, "dd": 0.2225, "sharpe": 0.67}},
        "intraday_orb30": {"10y": {"cagr": 0.0210, "dd": 0.4413, "sharpe": 0.20},
                           "5y": {"cagr": 0.0636, "dd": 0.2402, "sharpe": 0.41}},
        "intraday_orb5": {"10y": {"cagr": 0.0206, "dd": 0.4006, "sharpe": 0.20},
                          "5y": {"cagr": 0.0718, "dd": 0.2457, "sharpe": 0.42}},
        "intraday_orb15_first_candle": {"10y": {"cagr": 0.1027, "dd": 0.2657, "sharpe": 0.66},
                                        "5y": {"cagr": 0.1315, "dd": 0.1685, "sharpe": 0.86}},
        "regime_hold_orb_stop": {"10y": {"cagr": 0.3026, "dd": 0.3969, "sharpe": 0.95},
                                 "5y": {"cagr": 0.2181, "dd": 0.3969, "sharpe": 0.79}},
    }

    # sanity: NaN-free
    for tag in ("10y", "5y"):
        for key in ("1bp", "5bp"):
            for k, v in result["windows"][tag][key].items():
                if isinstance(v, float) and not np.isfinite(v):
                    raise ValueError(f"non-finite {tag} {key} {k}")

    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    for tag in ("10y", "5y"):
        for key in ("1bp", "5bp"):
            m = result["windows"][tag][key]
            print(f"{tag} {key}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:6.2f}% "
                  f"(daily {m['max_drawdown_daily']*100:5.2f}%)  Sharpe {m['sharpe']:.2f} "
                  f"(daily {m['sharpe_daily']:.2f})  fills {m['fills']}  turnover {m['turnover']:.1f}x  "
                  f"pass={m['pass_vs_tqqq']}")
    print("\nyearly 10y:")
    for y, v in result["yearly_10y"].items():
        print(f"  {y}: {v['strategy']*100:7.2f}%  bench {v['benchmark']*100:7.2f}%")
    print("\nyearly 5y:")
    for y, v in result["yearly_5y"].items():
        print(f"  {y}: {v['strategy']*100:7.2f}%  bench {v['benchmark']*100:7.2f}%")
    print(f"\nwrote {OUT / 'result.json'}")


if __name__ == "__main__":
    main()
