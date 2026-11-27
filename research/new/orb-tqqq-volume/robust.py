"""Robustness: sub-period cut tests and placebo entry-time/day distributions.

Placebo uses the same event-level fill convention as strategy.py: entry at the
open after the signal bar, ATR stop checked on 1-minute lows (next-open exit),
otherwise exit at the last bar's open. 500 draws per placebo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

RNG = np.random.default_rng(20231127)


def event_arrays():
    ts, o, c, bars = S.load_dev()
    st = S.session_tables(ts, bars, 30)
    hi = bars["high"].to_numpy()
    lo = bars["low"].to_numpy()
    op = bars["open"].to_numpy()
    tod = np.asarray(ts.hour * 60 + ts.minute)
    return ts, o, c, bars, st, hi, lo, op, tod


def sim_trade(k, entry_i, st, hi, lo, op, stop_atr=0.55):
    """Return (ret, kind) for one intraday long with an ATR stop."""
    s, e = st["starts"][k], st["ends"][k]
    if entry_i < s or entry_i >= e - 2:
        return np.nan, "skip"
    entry = op[entry_i + 1]
    stop = entry - stop_atr * st["atr14"][k]
    seg = lo[entry_i + 1:e - 1]
    hit = np.flatnonzero(seg <= stop)
    if len(hit):
        exit_i = entry_i + 1 + int(hit[0]) + 1
        kind = "stop"
    else:
        exit_i = e - 1
        kind = "eod"
    if exit_i >= len(op):
        return np.nan, "skip"
    return float(op[exit_i] / entry - 1.0), kind


def cagr_from_trades(rets, years=7.984):
    rets = rets[np.isfinite(rets)]
    if len(rets) == 0:
        return np.nan
    return float(np.prod(1.0 + rets) ** (1.0 / years) - 1.0)


def main():
    ts, o, c, bars, st, hi, lo, op, tod = event_arrays()
    log = []
    S._build(ts, o, c, S.CFG, bars, log=log)
    tr = pd.DataFrame(log)
    core_cagr = cagr_from_trades(tr["ret"].to_numpy())
    print(f"core event-level CAGR (572 trades, no costs): {core_cagr*100:.2f}%")
    print(f"core trade mean {tr['ret'].mean()*100:.3f}%  win {np.mean(tr['ret']>0)*100:.1f}%")

    # ---- cut tests on the actual harness equity curve ----
    w = S.build_weights(ts, o, c)
    res = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=1.0)
    eq = pd.Series(res["equity"], index=res["ts"])
    print("\n=== sub-period cut tests (1bp, minute marks) ===")
    cuts = [("2016-01-04", "2019-12-31"), ("2020-01-01", "2021-12-31"),
            ("2022-01-01", "2023-12-29"), ("2016-01-04", "2023-12-29")]
    cut_out = {}
    for a, b in cuts:
        seg = eq[(eq.index >= pd.Timestamp(a, tz="America/New_York")) &
                 (eq.index <= pd.Timestamp(b + " 23:59", tz="America/New_York"))]
        if len(seg) < 2:
            continue
        yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
        cg = (seg.iloc[-1] / seg.iloc[0]) ** (1 / yrs) - 1
        peak = np.maximum.accumulate(seg.to_numpy())
        dd = float(-(seg.to_numpy() / peak - 1).min())
        r = seg.pct_change().dropna()
        sh = float(r.mean() / r.std(ddof=0) * np.sqrt(S.BARS_1M)) if r.std() > 0 else 0
        cut_out[f"{a}..{b}"] = dict(cagr=float(cg), max_drawdown=dd, sharpe=sh,
                                   years=float(yrs))
        print(f"  {a}..{b}: CAGR {cg*100:6.2f}%  DD {dd*100:5.2f}%  Sharpe {sh:4.2f}")

    # leave-one-year-out CAGR
    print("\n=== leave-one-year-out CAGR ===")
    yearly = {}
    for y in range(2016, 2024):
        seg = eq[eq.index.year == y]
        yearly[y] = float(seg.iloc[-1] / seg.iloc[0] - 1.0)
    total = float(eq.iloc[-1] / eq.iloc[0])
    for y in range(2016, 2024):
        without = total / (1 + yearly[y])
        cg = without ** (1 / 7.984) - 1
        print(f"  without {y}: {cg*100:6.2f}%  (year {yearly[y]*100:7.2f}%)")

    # ---- placebo 1: random days, same entry-time distribution ----
    entries = tr[["date", "entry_min"]].copy()
    day_of = {d: k for k, d in enumerate(st["date"])}
    valid = [k for k in range(len(st["starts"]))
             if np.isfinite(st["atr14"][k]) and np.isfinite(st["or_hi"][k])
             and st["date"][k] >= pd.Timestamp(S.DEV_START).date()]
    entry_mins = entries["entry_min"].to_numpy()
    n_trades = len(entries)
    print(f"\n=== placebo 1: {n_trades} random days, bootstrap entry-time mix, 500 draws ===")
    vals = []
    for _ in range(500):
        ks = RNG.choice(valid, size=n_trades, replace=False)
        rets = np.empty(n_trades)
        for j, k in enumerate(ks):
            s, e = st["starts"][k], st["ends"][k]
            m = int(RNG.choice(entry_mins))
            i = int(np.searchsorted(tod[s:e], m)) + s
            i = min(max(i, s + 30), e - 3)
            rets[j], _ = sim_trade(k, i, st, hi, lo, op)
        vals.append(cagr_from_trades(rets))
    vals = np.array(vals)
    p = float(np.mean(vals >= core_cagr))
    print(f"  placebo CAGR mean {vals.mean()*100:6.2f}%  p5 {np.percentile(vals,5)*100:6.2f}%  "
          f"p95 {np.percentile(vals,95)*100:6.2f}%  max {vals.max()*100:6.2f}%")
    print(f"  core {core_cagr*100:.2f}%  percentile {np.mean(vals < core_cagr)*100:.1f}%  "
          f"one-sided p {p:.3f}")

    # ---- placebo 2: same days, random entry time 10:00-15:00 ----
    print(f"\n=== placebo 2: same {n_trades} days, random uniform entry time 10:00-15:00 ===")
    vals2 = []
    for _ in range(500):
        rets = np.empty(n_trades)
        for j, d in enumerate(entries["date"]):
            k = day_of[d]
            s, e = st["starts"][k], st["ends"][k]
            i = int(RNG.integers(s + 30, e - 35))
            rets[j], _ = sim_trade(k, i, st, hi, lo, op)
        vals2.append(cagr_from_trades(rets))
    vals2 = np.array(vals2)
    p2 = float(np.mean(vals2 >= core_cagr))
    print(f"  placebo CAGR mean {vals2.mean()*100:6.2f}%  p5 {np.percentile(vals2,5)*100:6.2f}%  "
          f"p95 {np.percentile(vals2,95)*100:6.2f}%  max {vals2.max()*100:6.2f}%")
    print(f"  core {core_cagr*100:.2f}%  one-sided p {p2:.3f}")

    # ---- placebo 3: random days, entry 10:00, no stop, hold to close ----
    print(f"\n=== placebo 3: random days, 10:00 entry, hold to close (no stop) ===")
    vals3 = []
    for _ in range(500):
        ks = RNG.choice(valid, size=n_trades, replace=False)
        rets = np.empty(n_trades)
        for j, k in enumerate(ks):
            s, e = st["starts"][k], st["ends"][k]
            i = s + int(np.searchsorted(tod[s:e], 600))
            rets[j], _ = sim_trade(k, i, st, hi, lo, op, stop_atr=1e9)
        vals3.append(cagr_from_trades(rets))
    vals3 = np.array(vals3)
    print(f"  placebo CAGR mean {vals3.mean()*100:6.2f}%  "
          f"p5 {np.percentile(vals3,5)*100:6.2f}%  p95 {np.percentile(vals3,95)*100:6.2f}%")

    out = dict(core_event_cagr=core_cagr, cuts=cut_out,
               placebo_random_day=dict(mean=float(vals.mean()),
                                       p5=float(np.percentile(vals, 5)),
                                       p95=float(np.percentile(vals, 95)),
                                       p_one_sided=p),
               placebo_random_time=dict(mean=float(vals2.mean()),
                                        p5=float(np.percentile(vals2, 5)),
                                        p95=float(np.percentile(vals2, 95)),
                                        p_one_sided=p2),
               placebo_no_stop=dict(mean=float(vals3.mean()),
                                    p5=float(np.percentile(vals3, 5)),
                                    p95=float(np.percentile(vals3, 95))))
    (HERE / "_robust.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nwrote _robust.json")


if __name__ == "__main__":
    main()
