"""Failed gap-up fade, repaired — `gap-fill-fade-v2`.

Development window only: 2016-01-04 .. 2023-12-29. The 2024-2026 holdout is
never loaded. See HYPOTHESIS.md for the pre-registered grid.

Core mechanism: short QQQ on a small gap-up in a weak, stressed tape; target
the prior close; stop above the entry; flat overnight. The repair drops the
10:00 confirmation (enter at 09:31), tightens the gap band to +0.20%..+0.60%
(+0.25%..+0.50% primary), and raises the short from a 10% vol target to a
fixed 2x QQQ notional via short TQQQ. The short is implemented as a synthetic
session-reset inverse asset held long in the long-only bt.py engine.

Run:
    python research/new/gap-fill-fade-v2/strategy.py
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
from minute_marks import to_minutes  # noqa: E402

DEV0 = "2016-01-04"
DEV1 = "2023-12-29"
BARS_1M = 252 * 390
BORROW = 0.005
WEAK_MA = 10
STRESS_MULT = 1.0
VOL_TARGET = 0.10

# col 3 = synthetic inverse QQQ (1x short), col 4 = inverse TQQQ (3x short).
GRID = {
    "orig": dict(gap_lo=0.0010, gap_hi=0.0075, confirm=True, entry_off=31,
                 size="vol", asset_col=3, stop_mode="or", stop_pct=None,
                 time_min=11 * 60 + 30),
    "orig_size1": dict(gap_lo=0.0010, gap_hi=0.0075, confirm=True, entry_off=31,
                       size=1.0, asset_col=3, stop_mode="or", stop_pct=None,
                       time_min=11 * 60 + 30),
    "all_nc_1x": dict(gap_lo=0.0010, gap_hi=0.0075, confirm=False, entry_off=1,
                      size=1.0, asset_col=3, stop_mode="fixed", stop_pct=0.015,
                      time_min=15 * 60 + 58),
    "b20_60_1x": dict(gap_lo=0.0020, gap_hi=0.0060, confirm=False, entry_off=1,
                      size=1.0, asset_col=3, stop_mode="fixed", stop_pct=0.015,
                      time_min=15 * 60 + 58),
    "b20_60_2x": dict(gap_lo=0.0020, gap_hi=0.0060, confirm=False, entry_off=1,
                      size=0.667, asset_col=4, stop_mode="fixed", stop_pct=0.015,
                      time_min=15 * 60 + 58),
    "b20_60_3x": dict(gap_lo=0.0020, gap_hi=0.0060, confirm=False, entry_off=1,
                      size=1.0, asset_col=4, stop_mode="fixed", stop_pct=0.015,
                      time_min=15 * 60 + 58),
    "b25_50_2x": dict(gap_lo=0.0025, gap_hi=0.0050, confirm=False, entry_off=1,
                      size=0.667, asset_col=4, stop_mode="fixed", stop_pct=0.015,
                      time_min=15 * 60 + 58),
    "b20_60_conf_2x": dict(gap_lo=0.0020, gap_hi=0.0060, confirm=True,
                           entry_off=31, size=0.667, asset_col=4,
                           stop_mode="or", stop_pct=None,
                           time_min=11 * 60 + 30),
}
PRIMARY = "b25_50_2x"


# ---------------------------------------------------------------------------
# sessions and synthetic inverse assets
# ---------------------------------------------------------------------------
def sessions(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def inverse_asset(opens, closes, first, last, entry_offset=1, borrow=BORROW):
    """Session-reset linear inverse of a price series.

    At the entry open the value is 1.0. For every later bar i in the session
        inv_open[i]  = 1 - (open[i]  / open[e] - 1)
        inv_close[i] = 1 - (close[i] / open[e] - 1)
    so the return from the entry open to any later open is the negative of the
    underlying's return. Borrow accrues linearly over the elapsed minutes.
    """
    n = len(opens)
    io = np.ones(n)
    ic = np.ones(n)
    borrow_daily = borrow / 252.0
    for f, l in zip(first, last):
        e = f + entry_offset
        if e >= l:
            continue
        base = opens[e, 0]
        if not np.isfinite(base) or base <= 0:
            continue
        for i in range(e, l + 1):
            decay = 1.0 - borrow_daily * ((i - e) / 390.0)
            io[i] = (1.0 - (opens[i, 0] / base - 1.0)) * decay
            ic[i] = (1.0 - (closes[i, 0] / base - 1.0)) * decay
    return io, ic


# ---------------------------------------------------------------------------
# signal and weights
# ---------------------------------------------------------------------------
def build_weights(params, ts, opens, closes, high, low, inv_opens):
    dates, first, last = sessions(ts)
    n = len(ts)
    dclose = closes[last, 0]
    prior = np.r_[np.nan, dclose[:-1]]
    gap = opens[first, 0] / prior - 1.0

    sma = pd.Series(dclose).rolling(WEAK_MA).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ret5 = pd.Series(dclose).pct_change(5).shift(1).to_numpy()
    vol20 = (pd.Series(dclose).pct_change().rolling(20).std(ddof=0).shift(1).to_numpy()
             * np.sqrt(252.0))
    vol_med = pd.Series(vol20).rolling(252, min_periods=60).median().to_numpy()

    weak = (prior < sma_prev) & (ret5 < 0)
    stress = vol20 > vol_med * STRESS_MULT
    band = (gap >= params["gap_lo"]) & (gap < params["gap_hi"])
    valid = (first + params["entry_off"]) <= last

    open0930 = opens[first, 0]
    close1000 = np.full(len(first), np.nan)
    r30 = np.full(len(first), np.nan)
    if params["confirm"]:
        idx = first[valid] + 30
        close1000[valid] = closes[idx, 0]
        r30[valid] = close1000[valid] / open0930[valid] - 1.0
    n_or = params["entry_off"] if params["entry_off"] == 1 else params["entry_off"] - 1
    or_high = np.array([high[f:f + n_or].max() if v else np.nan
                        for f, v in zip(first, valid)])

    signal = band & weak & stress
    signal &= np.isfinite(gap) & np.isfinite(vol20) & np.isfinite(vol_med)
    if params["confirm"]:
        signal &= (r30 < 0) & (close1000 < open0930) & (close1000 > prior)
    signal &= valid

    mod = (ts.hour * 60 + ts.minute).to_numpy()
    w = np.zeros((n, 5))
    w[:, 2] = 1.0  # BIL default
    events = []

    for k in np.flatnonzero(signal):
        f, l = first[k], last[k]
        e = f + params["entry_off"]
        if e >= l:
            continue
        entry = opens[e, 0]
        if not np.isfinite(entry) or entry <= 0:
            continue
        # For the 09:31 entry, skip if the gap has already filled at the open.
        if not params["confirm"] and entry <= prior[k]:
            continue

        if params["stop_mode"] == "or":
            stop_px = min(max(or_high[k], entry * 1.002), entry * 1.015)
        else:
            stop_px = entry * (1.0 + params["stop_pct"])

        exit_i = l - 1
        reason = "eod"
        for i in range(e, l + 1):
            if high[i] >= stop_px:
                exit_i, reason = i, "stop"
                break
            if low[i] <= prior[k]:
                exit_i, reason = i, "target"
                break
            if mod[i] >= params["time_min"]:
                exit_i, reason = i, "time"
                break

        if params["size"] == "vol":
            size = float(np.clip(VOL_TARGET / vol20[k], 0.10, 1.0))
        else:
            size = float(params["size"])
        col = params["asset_col"]
        w[e - 1:exit_i, col] = size
        w[e - 1:exit_i, 2] = 1.0 - size
        w[exit_i, col] = 0.0
        w[exit_i, 2] = 1.0

        exit_i_next = min(exit_i + 1, l)
        entry_asset = inv_opens[e, col - 3]
        exit_asset = inv_opens[exit_i_next, col - 3]
        events.append({
            "date": str(dates[f]),
            "gap": float(gap[k]),
            "r30": float(-(close1000[k] / open0930[k] - 1.0)) if params["confirm"] else 0.0,
            "vol20": float(vol20[k]),
            "size": size,
            "asset": "inv_tqqq_3x" if col == 4 else "inv_qqq_1x",
            "entry": float(entry_asset),
            "exit": float(exit_asset),
            "gross": float(exit_asset / entry_asset - 1.0),
            "hold_min": int(exit_i - e + 1),
            "reason": reason,
        })

    info = {
        "events": events,
        "n_events": len(events),
        "signal_days": int(signal.sum()),
        "avg_short_notional": float(w[:, 3].mean() + w[:, 4].mean()),
        "time_in_market": float(((w[:, 3] + w[:, 4]) > 0).mean()),
        "max_short_notional": float((w[:, 3] + w[:, 4]).max()),
        "avg_gross_short_x": float(3.0 * w[:, 4].mean() + w[:, 3].mean()),
        "max_gross_short_x": float(3.0 * w[:, 4].max() + w[:, 3].max()),
    }
    return w, info


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def stats(run, slip):
    s = bt.stats(run, BARS_1M)
    return {k: float(s[k]) for k in ("cagr", "total_return", "max_drawdown",
                                     "sharpe", "sortino", "volatility", "fills",
                                     "turnover", "exposure", "ending_equity")}


def daily_equity(run):
    s = pd.Series(run["equity"], index=pd.DatetimeIndex(run["ts"]))
    d = s.groupby(s.index.date).last()
    d.index = pd.to_datetime(d.index)
    return d


def event_stats(events, slip):
    if not events:
        return {"n": 0}
    gross = np.array([e["gross"] for e in events])
    sized = np.array([e["size"] for e in events])
    net = sized * (gross - 2.0 * slip / 10_000.0)
    n = len(net)
    t = net.mean() / net.std(ddof=1) * np.sqrt(n) if n > 1 and net.std(ddof=1) > 0 else 0.0
    rng = np.random.default_rng(11)
    boot = np.array([rng.choice(net, size=n, replace=True).mean()
                     for _ in range(10_000)])
    return {
        "n": int(n),
        "gross_per_unit_mean": float(gross.mean()),
        "gross_per_unit_median": float(np.median(gross)),
        "sized_net_mean": float(net.mean()),
        "win_rate": float((net > 0).mean()),
        "t_stat": float(t),
        "bootstrap_p": float((boot <= 0).mean()),
        "bootstrap_ci_low": float(np.quantile(boot, 0.025)),
        "bootstrap_ci_high": float(np.quantile(boot, 0.975)),
        "avg_hold_min": float(np.mean([e["hold_min"] for e in events])),
        "avg_size": float(sized.mean()),
        "exit_reasons": {r: int(sum(1 for e in events if e["reason"] == r))
                         for r in ("stop", "target", "time", "eod")},
    }


def yearly(equity, bench):
    equity = pd.Series(equity).dropna()
    bench = pd.Series(bench).dropna()
    out = {}
    for y in sorted(set(equity.index.year)):
        e = equity[equity.index.year == y]
        b = bench[bench.index.year == y]
        if len(e) < 2 or len(b) < 2:
            continue
        out[int(y)] = {"strategy": float(e.iloc[-1] / e.iloc[0] - 1.0),
                       "benchmark": float(b.iloc[-1] / b.iloc[0] - 1.0)}
    return out


def subperiods(run):
    d = daily_equity(run)
    out = {}
    for lo, hi in ((2016, 2019), (2020, 2021), (2022, 2023)):
        s = d[(d.index.year >= lo) & (d.index.year <= hi)]
        prev = d[d.index.year < lo]
        start = prev.iloc[-1] if len(prev) else s.iloc[0]
        years = (s.index[-1] - (prev.index[-1] if len(prev) else s.index[0])).days / 365.25
        out[f"{lo}-{hi}"] = {
            "total_return": float(s.iloc[-1] / start - 1.0),
            "cagr": float((s.iloc[-1] / start) ** (1.0 / years) - 1.0),
        }
    return out


def baseline_weights(tsd, cd):
    qqq = cd[:, 0]
    sma = pd.Series(qqq).rolling(165).mean().to_numpy()
    on = np.zeros(len(qqq), bool)
    ok = np.isfinite(sma)
    on[ok] = qqq[ok] > sma[ok]
    w = np.zeros((len(qqq), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    return w


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    dates, first, last = sessions(ts)
    q = bt.load_1m("QQQ").set_index("ts").reindex(ts).ffill()
    t = bt.load_1m("TQQQ").set_index("ts").reindex(ts).ffill()
    high = q["high"].to_numpy()
    low = q["low"].to_numpy()

    inv_q = inverse_asset(o, c, first, last)
    inv_t = inverse_asset(t["open"].to_numpy()[:, None],
                          t["close"].to_numpy()[:, None], first, last)
    inv_open_only = np.column_stack([inv_q[0], inv_t[0]])
    all_o = np.column_stack([o, inv_q[0], inv_t[0]])
    all_c = np.column_stack([c, inv_q[1], inv_t[1]])

    names, weights, infos = [], [], {}
    for name, params in GRID.items():
        w, info = build_weights(params, ts, o, c, high, low, inv_open_only)
        names.append(name)
        weights.append(w)
        infos[name] = info

    runs = {}
    for slip in (1.0, 5.0, 10.0):
        runs[slip] = bt.run_many(ts, all_o, all_c, weights, DEV0, band=0.02,
                                 slippage_bps=slip)

    # Daily benchmarks and the old 165-day base.
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1D")
    itq = bt.start_index(tsd, DEV0)
    bench = {
        "qqq": bt.benchmark(cd[itq:, 0], tsd[itq:], 252),
        "tqqq": bt.benchmark(cd[itq:, 1], tsd[itq:], 252),
    }
    wb = to_minutes(tsd, baseline_weights(tsd, cd), ts, "1D")
    rb = bt.run(ts, o, c, wb, DEV0, band=0.02, slippage_bps=1.0)
    bench["baseline_165d"] = stats(rb, 1.0)

    # BIL-only: the honest carry benchmark.
    wbil = np.zeros((len(ts), 3))
    wbil[:, 2] = 1.0
    rbil = bt.run(ts, o, c, wbil, DEV0, band=0.02, slippage_bps=1.0)
    bil_stats = stats(rbil, 1.0)

    qqq_daily = pd.Series(cd[itq:, 0],
                          index=pd.to_datetime(tsd[itq:]).tz_localize(None).normalize()).pct_change().dropna()
    tqqq_daily = pd.Series(cd[itq:, 1],
                           index=pd.to_datetime(tsd[itq:]).tz_localize(None).normalize()).pct_change().dropna()
    base_daily = daily_equity(rb).pct_change().dropna()

    out = {
        "agent": "gap-fill-fade-v2",
        "original": "research/revisit/gap-fill-fade",
        "status": "development-only",
        "window": [DEV0, DEV1],
        "primary": PRIMARY,
        "variants_tried": len(GRID),
        "universe": ["QQQ short (synthetic inverse)", "TQQQ short (3x inverse for 2x/3x variants)", "BIL cash"],
        "direction": "short QQQ on event days; BIL and flat overnight otherwise",
        "idea": ("Fade a small gap-up in a weak, stressed tape: short QQQ at "
                 "09:31, target the prior close, stop +1.5%, flat by the close."),
        "bil_only": bil_stats,
        "benchmarks": {k: ({m: float(v[m]) for m in v
                            if isinstance(v[m], (int, float, np.floating))}
                           if isinstance(v, dict) else v)
                       for k, v in bench.items()},
        "variants": {},
    }

    for j, name in enumerate(names):
        v = {"params": {k: (str(x) if isinstance(x, str) else x)
                        for k, x in GRID[name].items()},
             "signal_days": infos[name]["signal_days"],
             "n_events": infos[name]["n_events"],
             "exposure": {k: infos[name][k] for k in
                          ("avg_short_notional", "time_in_market",
                           "max_short_notional", "avg_gross_short_x",
                           "max_gross_short_x")},
             "events": infos[name]["events"],
             "event_study": {f"{int(s)}bp": event_stats(infos[name]["events"], s)
                             for s in (1.0, 5.0, 10.0)},
             "costs": {}}
        for slip in (1.0, 5.0, 10.0):
            v["costs"][f"{slip:g}bp"] = stats(runs[slip][j], slip)
        v["per_year"] = yearly(daily_equity(runs[1.0][j]),
                               pd.Series(cd[itq:, 1],
                                         index=pd.to_datetime(tsd[itq:]).tz_localize(None).normalize()))
        v["subperiods"] = subperiods(runs[1.0][j])
        dr = daily_equity(runs[1.0][j]).pct_change().dropna()
        v["corr_vs_qqq"] = float(dr.corr(qqq_daily))
        v["corr_vs_tqqq"] = float(dr.corr(tqqq_daily))
        v["corr_vs_165d"] = float(dr.corr(base_daily))
        out["variants"][name] = v

    out["note"] = ("Development window only 2016-01-04..2023-12-29. The "
                   "2024-2026 holdout and the 10y/5y windows were not loaded. "
                   "All fills are next-open 1-minute fills. The short is a "
                   "synthetic session-reset inverse asset; the 2x variants hold "
                   "0.667 of the inverse TQQQ asset (3x QQQ), which is 2.0x "
                   "gross short QQQ on event days. Borrow 0.5%/yr, prorated.")
    path = Path(__file__).resolve().parent / "result.json"
    path.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: {c: round(v["costs"][c]["cagr"] * 100, 2)
                          for c in ("1bp", "5bp", "10bp")}
                      for k, v in out["variants"].items()}, indent=2))
    print("BIL", round(bil_stats["cagr"] * 100, 2), "%")
    print("wrote", path)


if __name__ == "__main__":
    main()
