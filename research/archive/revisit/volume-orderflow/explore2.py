"""Revisit exploration part 2: two-state ladder, sizing, placebo, benchmarks,
and correlations vs the 165-day baseline.  Development period only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore import (DEV_END, DEV_START, BARS, SYMS, daily, daily_ret, evaluate,
                     load, sessions, shift_mean)  # noqa: E402


def main():
    ts, op, cl, vol = load()
    dates, first, last = sessions(ts)
    qc, tc, v, qo = daily(ts, cl, vol, first, last)
    nd = len(qc)
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    reg = np.zeros(nd, bool)
    reg[1:] = qc[:-1] > pd.Series(qc).rolling(165).mean().to_numpy()[:-1]
    ret = np.r_[np.nan, qc[1:] / qc[:-1] - 1]

    def alloc_w(alloc):                    # alloc: (nd,3) fractions
        w = np.zeros((len(ts), 3))
        w[:] = alloc[day_id]
        return w

    def run(alloc, slip=1.0):
        s, r = evaluate(ts, op, cl, alloc_w(alloc), slip)
        return s, r

    def corr_with(rets_a, rets_b):
        j = rets_a.index.intersection(rets_b.index)
        return float(np.corrcoef(rets_a.loc[j], rets_b.loc[j])[0, 1])

    # ---------- benchmarks
    w_tq = np.zeros((len(ts), 3)); w_tq[:, 1] = 1
    w_qq = np.zeros((len(ts), 3)); w_qq[:, 0] = 1
    base_alloc = np.zeros((nd, 3))
    base_alloc[:, 1] = reg
    base_alloc[:, 2] = 1 - reg
    bench = {}
    for name, w in (("TQQQ", w_tq), ("QQQ", w_qq)):
        s, r = evaluate(ts, op, cl, w)
        bench[name] = s
        print(f"{name:6s} B&H dev: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:.2f}")
    sb, rb = run(base_alloc)
    bench["baseline165"] = sb
    print(f"165d   base dev: CAGR {sb['cagr']*100:6.2f}%  DD {sb['max_drawdown']*100:5.2f}%  "
          f"Sharpe {sb['sharpe']:.2f}  fills {sb['fills']}")

    r_tq = daily_ret(evaluate(ts, op, cl, w_tq)[1], ts, first, last)
    r_base = daily_ret(rb, ts, first, last)

    # ---------- D: two-state volume ladder (TQQQ / BIL)
    m5, m60 = shift_mean(v, 5, minp=5), shift_mean(v, 60, minp=60)
    vex = np.where(m60 > 0, m5 / m60, np.nan)
    vex = np.r_[np.nan, vex[:-1]]          # signal from prior close
    print("\n== D: TQQQ while volume expansion below threshold, else BIL")
    best = None
    for q in (0.5, 0.6, 0.7, 0.8, 0.9):
        thr = np.nanquantile(vex, q)
        a = np.zeros((nd, 3))
        on = ~(vex > thr)
        on &= np.isfinite(vex)
        a[:, 1] = on; a[:, 2] = 1 - on
        s, r = run(a)
        c = corr_with(daily_ret(r, ts, first, last), r_base)
        print(f"  q{q:.1f} thr {thr:.2f}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:.2f} off {np.mean(~on)*100:4.0f}% corr_base {c:+.2f}")
        if best is None or s["cagr"] > best[0]:
            best = (s["cagr"], q, a, s, c)

    # ---------- E: participation-scaled sizing (no binary switch)
    print("\n== E: TQQQ weight = clip((thr - vex)/(thr - lo), 0, 1)")
    print(f"  (non-finite volume days: {int((~np.isfinite(vex)).sum())} of {nd})")
    for lo_q, hi_q in ((0.4, 0.9), (0.5, 0.9), (0.6, 0.95)):
        lo, hi = np.nanquantile(vex, lo_q), np.nanquantile(vex, hi_q)
        wgt = np.clip((hi - vex) / (hi - lo), 0.0, 1.0)
        wgt[~np.isfinite(wgt)] = 0.0
        a = np.zeros((nd, 3))
        a[:, 1] = wgt; a[:, 2] = 1 - wgt
        s, r = run(a)
        c = corr_with(daily_ret(r, ts, first, last), r_base)
        print(f"  q{lo_q}/{hi_q}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:.2f} avg w {np.nanmean(wgt)*100:.0f}% corr_base {c:+.2f}")

    # ---------- F: placebo - random state with matched off-frequency
    print("\n== F: placebo (random states, matched frequency, 20 draws)")
    rng = np.random.default_rng(7)
    q = best[1]
    thr = np.nanquantile(vex, q)
    off_frac = float(np.mean(vex > thr))
    cagrs, dds = [], []
    for _ in range(20):
        rnd = rng.random(nd) < off_frac
        rnd = np.r_[False, rnd[:-1]]
        a = np.zeros((nd, 3))
        a[:, 1] = ~rnd; a[:, 2] = rnd
        s, _ = run(a)
        cagrs.append(s["cagr"]); dds.append(s["max_drawdown"])
    print(f"  off {off_frac*100:.0f}%: placebo CAGR median {np.median(cagrs)*100:.2f}% "
          f"[p05 {np.quantile(cagrs,0.05)*100:.2f}, p95 {np.quantile(cagrs,0.95)*100:.2f}] "
          f"DD median {np.median(dds)*100:.1f}%")
    print(f"  real ladder q{q}: CAGR {best[0]*100:.2f}%")

    # ---------- summary of correlations
    print("\n== correlations vs the 165-day baseline (dev daily returns)")
    for name, alloc in (("A ladder 0.6/0.9", None),):
        pass
    return bench


if __name__ == "__main__":
    if os.environ.get("REVISIT_AUTHORIZED") != "1":
        raise SystemExit("PAUSED 2026-11-26: pre-pause exploratory script; "
                             "do not run without authorisation.")
    main()
