"""Revisit exploration part 3: the decisive tests.

1. Placebo at the chosen ladder frequency (is the timing skill real?).
2. Overnight vs intraday decomposition of the TQQQ drawdown: can any
   intraday-executed rule avoid it?
3. A de-risk-to-QQQ variant driven only by heavy-volume declines.
4. Correlations of every candidate against the 165-day baseline.

Development period only.
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
from explore import (BARS, DEV_START, daily, daily_ret, evaluate, load,
                     sessions, shift_mean)  # noqa: E402


def main():
    ts, op, cl, vol = load()
    dates, first, last = sessions(ts)
    qc, tc, v, qo = daily(ts, cl, vol, first, last)
    nd = len(qc)
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    reg = np.zeros(nd, bool)
    reg[1:] = qc[:-1] > pd.Series(qc).rolling(165).mean().to_numpy()[:-1]
    ret = np.r_[np.nan, qc[1:] / qc[:-1] - 1]

    def alloc_w(a):
        w = np.zeros((len(ts), 3)); w[:] = a[day_id]; return w

    def run(a, slip=1.0):
        s, r = evaluate(ts, op, cl, alloc_w(a), slip)
        return s, r

    base = np.zeros((nd, 3)); base[:, 1] = reg; base[:, 2] = 1 - reg
    sb, rb = run(base)
    r_base = daily_ret(rb, ts, first, last)

    # ---------- the 61 non-finite volume days
    m5, m60 = shift_mean(v, 5, minp=5), shift_mean(v, 60, minp=60)
    vex = np.where(m60 > 0, m5 / m60, np.nan)
    bad = np.flatnonzero(~np.isfinite(vex))
    print(f"non-finite vex on {len(bad)} days; volume there: "
          f"median {np.median(v[bad]):,.0f}, zero-count {int((v[bad]==0).sum())}")
    print("  first 6:", [str(dates[i]) for i in bad[:6]])

    # ---------- signals
    sig = np.r_[np.nan, vex[:-1]]              # lagged one session
    s_filled = pd.Series(sig).ffill().to_numpy()

    def ladder(threshold):
        a = np.zeros((nd, 3))
        on = np.isfinite(s_filled) & ~(s_filled > threshold)
        a[:, 1] = on; a[:, 2] = 1 - on
        return a

    print("\n== 1. placebo at the selected frequencies (40 draws each)")
    rng = np.random.default_rng(11)
    for q in (0.7, 0.8):
        thr = np.nanquantile(sig, q)
        off = float(np.mean(s_filled > thr))
        s_real, _ = run(ladder(thr))
        cagrs, dds, shp = [], [], []
        for _ in range(40):
            rnd = np.r_[False, (rng.random(nd - 1) < off)]
            a = np.zeros((nd, 3)); a[:, 1] = ~rnd; a[:, 2] = rnd
            s, _ = run(a)
            cagrs.append(s["cagr"]); dds.append(s["max_drawdown"]); shp.append(s["sharpe"])
        p = float(np.mean(np.array(cagrs) >= s_real["cagr"]))
        print(f"  q{q} off {off*100:.0f}%: real {s_real['cagr']*100:6.2f}%/{s_real['max_drawdown']*100:5.2f}% "
              f"Sharpe {s_real['sharpe']:.2f} | placebo CAGR {np.median(cagrs)*100:6.2f}% "
              f"[{np.quantile(cagrs,0.05)*100:6.2f},{np.quantile(cagrs,0.95)*100:6.2f}] "
              f"DD {np.median(dds)*100:5.1f}%  p(placebo>=real)={p:.2f}")

    # ---------- 2. overnight vs intraday decomposition of the drawdown
    print("\n== 2. where the TQQQ drawdown actually happens (dev)")
    on_r = tc / np.r_[np.nan, tc[:-1]] - 1          # close-to-close not used
    # close[d-1] -> open[d]  and  open[d] -> close[d]
    ov = np.full(nd, np.nan); ov[1:] = op[first][1:] / tc[:-1] - 1
    intr = tc / op[first] - 1
    eqd = np.r_[np.nan, tc[1:] / tc[:-1] - 1]
    peak = np.maximum.accumulate(np.nan_to_num(tc, nan=1))
    dd = tc / peak - 1
    j = int(np.nanargmin(dd))
    p = int(np.nanargmax(tc[:j + 1]))
    seg_ov = np.nanprod(1 + ov[p + 1:j + 1]) - 1
    seg_in = np.nanprod(1 + intr[p + 1:j + 1]) - 1
    print(f"  max DD {dd[j]*100:.2f}%  {dates[p]} -> {dates[j]}")
    print(f"  sum of overnight returns over that span : {seg_ov*100:+8.2f}%")
    print(f"  sum of open-to-close returns over it    : {seg_in*100:+8.2f}%")
    print(f"  total (compounded)                      : {tc[j]/tc[p]*100-100:+8.2f}%")
    tq_intraday_only = np.nanprod(1 + intr[p + 1:j + 1]) - 1
    print(f"  hypothetically flat overnight in that span: {tq_intraday_only*100:+.2f}%")

    # ---------- 3. de-risk to QQQ after heavy-volume declines
    rv1 = np.r_[np.nan, v[1:] / shift_mean(v, 20)[1:]]
    print("\n== 3. heavy-volume decline -> QQQ for n sessions (else TQQQ)")
    for k in (1.5, 2.0):
        for hold in (1, 3, 5):
            ev = (rv1 > k) & (ret < 0)
            a = np.zeros((nd, 3))
            a[:, 1] = 1.0
            off = 0
            for d in range(nd):
                if off > 0:
                    a[d, 1] = 0.0; a[d, 0] = 1.0; off -= 1
                if ev[d]:
                    off = hold
            a = np.vstack([a[0:1], a[:-1]])
            s, r = run(a)
            c = float(np.corrcoef(daily_ret(r, ts, first, last), r_base)[0, 1])
            print(f"  rvol>{k} hold{hold}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:.2f} corr_base {c:+.2f}")

    # ---------- 4. correlation table for all candidates
    print("\n== 4. dev correlations vs the 165-day baseline")
    rows = {}
    # ladder
    for q in (0.7, 0.8):
        thr = np.nanquantile(sig, q)
        rows[f"ladder q{q}"] = ladder(thr)
    # sizing
    lo, hi = np.nanquantile(sig, 0.4), np.nanquantile(sig, 0.9)
    wgt = np.clip((hi - sig) / (hi - lo), 0, 1); wgt[~np.isfinite(wgt)] = 0
    a = np.zeros((nd, 3)); a[:, 1] = wgt; a[:, 2] = 1 - wgt
    rows["sizing q0.4/0.9"] = a
    # always long with participation-armed stop
    for hi_arm, floor in ((1.0, 0.0), (1.5, 1.0)):
        n = len(ts)
        cv = np.zeros((nd, 390))
        for d, (f, l) in enumerate(zip(first, last)):
            cv[d, :l - f + 1] = np.cumsum(vol[f:l + 1])
        bs = pd.DataFrame(cv).rolling(20, min_periods=10).mean().shift(1).to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            rvc = np.where(bs > 0, cv / bs, np.nan)
        w = np.zeros((n, 3)); hold = np.ones(n, bool)
        for d in range(nd):
            f, l = first[d], last[d]
            rv = rvc[d, :l - f + 1]
            ok = np.isfinite(rv)
            armed = ok & (rv > hi_arm) & (rv > floor)
            hit = armed & (cl[f:l + 1, 1] < cl[f, 1] * 0.96)
            if hit.any():
                j = int(np.argmax(hit)); hold[f + j:l + 1] = False
        w[:, 1] = hold; w[:, 2] = 1 - hold
        s = bt.stats(bt.run(ts, op, cl, w, DEV_START, band=0.02, slippage_bps=1.0), BARS)
        rr = bt.run(ts, op, cl, w, DEV_START, band=0.02, slippage_bps=1.0)
        c = float(np.corrcoef(daily_ret(rr, ts, first, last), r_base)[0, 1])
        print(f"  stop-only hi>{hi_arm} fl>{floor}: CAGR {s['cagr']*100:6.2f}% "
              f"DD {s['max_drawdown']*100:5.2f}% Sharpe {s['sharpe']:.2f} corr_base {c:+.2f}")
        rows[f"stop hi>{hi_arm}"] = None

    for name, a in rows.items():
        if a is None:
            continue
        s, r = run(a)
        c = float(np.corrcoef(daily_ret(r, ts, first, last), r_base)[0, 1])
        print(f"  {name:18s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:.2f} corr_base {c:+.2f}  (baseline {sb['cagr']*100:5.2f}%/"
              f"{sb['max_drawdown']*100:5.2f}%)")


if __name__ == "__main__":
    if os.environ.get("REVISIT_AUTHORIZED") != "1":
        raise SystemExit("PAUSED 2026-11-26: pre-pause exploratory script; "
                             "do not run without authorisation.")
    main()
