"""Revisit exploration: can participation alone decide the position?

Development period only: 2016-01-04 .. 2023-12-29.  The holdout (2024+) is never
loaded here: bt.panel is asked to stop at the dev end, and every run is sliced
to the dev start.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/volume-orderflow/explore.py
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

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")


def load():
    ts, op, cl = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    # volume for QQQ on the same minute grid
    q = bt.load_1m("QQQ")
    q = q[(q["ts"] >= ts[0]) & (q["ts"] < ts[-1] + pd.Timedelta(minutes=1))]
    vol = q.set_index("ts")["volume"].reindex(ts).fillna(0.0).to_numpy()
    return ts, op, cl, vol


def sessions(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def daily(ts, cl, vol, first, last):
    qc = cl[last, 0]
    tc = cl[last, 1]
    v = np.array([vol[f:l + 1].sum() for f, l in zip(first, last)])
    qo = op_first = cl[first, 0]
    return qc, tc, v, qo


def shift_mean(x, n, minp=None):
    s = pd.Series(x)
    return s.rolling(n, min_periods=minp or max(2, n // 2)).mean().shift(1).to_numpy()


def evaluate(ts, op, cl, w, slip=1.0):
    r = bt.run(ts, op, cl, w, DEV_START, band=0.02, slippage_bps=slip)
    return bt.stats(r, BARS), r


def daily_ret(r, ts, first, last):
    eq = pd.Series(r["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    return d.pct_change().dropna()


def main():
    ts, op, cl, vol = load()
    dates, first, last = sessions(ts)
    qc, tc, v, qo = daily(ts, cl, vol, first, last)
    reg = np.zeros(len(qc), bool)
    reg[1:] = qc[:-1] > pd.Series(qc).rolling(165).mean().to_numpy()[:-1]
    ret = np.r_[np.nan, qc[1:] / qc[:-1] - 1]
    print(f"sessions {len(qc)}  {dates[0]}..{dates[-1]}  baseline risk-on {reg.mean()*100:.1f}%")

    # ---------------- feature: volume expansion (no price MA anywhere)
    def ratio(a, b):
        m1 = shift_mean(v, a, minp=a)
        m2 = shift_mean(v, b, minp=b)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(m2 > 0, m1 / m2, np.nan)

    vex = ratio(5, 60)
    vex20 = ratio(20, 120)

    print("\n== forward TQQQ returns by volume-expansion state (dev, all days)")
    fwd = {}
    for h in (1, 5, 20):
        y = np.full(len(tc), np.nan)
        y[:-h] = tc[h:] / tc[:-h] - 1
        fwd[h] = y
    for name, x in (("vol5_60", vex), ("vol20_120", vex20)):
        for h in (1, 5, 20):
            m = np.isfinite(x) & np.isfinite(fwd[h])
            print(f"  {name:9s} h={h:2d} n={m.sum():4d} "
                  f"corr={np.corrcoef(x[m], fwd[h][m])[0,1]:+.3f} "
                  f"q20 {np.quantile(x[m],0.2):.2f} q80 {np.quantile(x[m],0.8):.2f}")
            bins = np.quantile(x[m], [0, .2, .4, .6, .8, 1.0])
            b = np.clip(np.searchsorted(bins[1:-1], x[m]), 0, 4)
            print("        " + " ".join(
                f"{(fwd[h][m][b==k].mean()*100):+5.2f}" for k in range(5)))

    print("\n== event: high-participation down day -> next sessions (dev)")
    rv1 = np.r_[np.nan, v[1:] / shift_mean(v, 20)[1:]]
    for k in (1.5, 2.0, 2.5):
        for h in (1, 5):
            y = np.full(len(tc), np.nan)
            y[:-h] = tc[h:] / tc[:-h] - 1
            ev = (rv1 > k) & (ret < 0)
            m = ev & np.isfinite(y)
            base = np.isfinite(y) & ~ev
            print(f"  rvol>{k} & down: n={m.sum():3d} mean {y[m].mean()*100:+6.2f}% "
                  f"| other n={base.sum()} mean {y[base].mean()*100:+6.2f}%  h={h}")

    # ---------------- candidate bases
    def w_from_state(state_allocation):
        """state_allocation: array of per-day dict-like column index (1=TQQQ,0=QQQ,2=BIL)."""
        w = np.zeros((len(ts), 3))
        alloc = np.zeros((len(qc), 3))
        alloc[np.arange(len(qc)), state_allocation] = 1.0
        w[:] = alloc[day_id]
        return w

    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))

    results = {}

    # A: three-state participation ladder, thresholds from dev quantiles
    for lo_q, hi_q in ((0.5, 0.8), (0.4, 0.8), (0.6, 0.9)):
        lo, hi = np.nanquantile(vex, lo_q), np.nanquantile(vex, hi_q)
        st = np.full(len(qc), 1)          # 1 = TQQQ
        st[vex > lo] = 0                  # 0 = QQQ
        st[vex > hi] = 2                  # 2 = BIL
        st[~np.isfinite(vex)] = 1
        st = np.r_[1, st[:-1]]            # signal known at prior close
        w = w_from_state(st)
        results[f"ladder {lo_q}/{hi_q}"] = (w, st)
        s, _ = evaluate(ts, op, cl, w)
        mix = np.bincount(st, minlength=3) / len(st)
        print(f"\nA ladder {lo_q}/{hi_q}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:.2f} fills {s['fills']}  mix TQQQ/QQQ/BIL "
              f"{mix[1]*100:.0f}/{mix[0]*100:.0f}/{mix[2]*100:.0f}")

    # B: TQQQ by default; high-participation down day -> BIL for n sessions
    for k in (1.5, 2.0, 2.5):
        for hold in (1, 3, 5):
            ev = (rv1 > k) & (ret < 0)
            st = np.ones(len(qc), int)
            off = 0
            for d in range(len(qc)):
                if off > 0:
                    st[d] = 2
                    off -= 1
                if ev[d]:
                    off = hold
            st = np.r_[1, st[:-1]]
            w = w_from_state(st)
            s, _ = evaluate(ts, op, cl, w)
            print(f"B rvol>{k} hold{hold}: CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:.2f} fills {s['fills']} off {np.mean(st==2)*100:.0f}%")

    # C: always TQQQ + participation-armed 4% stop (pure stop, no regime)
    rvol_cum = None
    # per-minute cumulative rvol
    n = len(ts)
    cv = np.zeros((len(qc), 390))
    for d, (f, l) in enumerate(zip(first, last)):
        seg = vol[f:l + 1]
        cv[d, :len(seg)] = np.cumsum(seg)
    base = pd.DataFrame(cv).rolling(20, min_periods=10).mean().shift(1).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        rvc = np.where(base > 0, cv / base, np.nan)
    tod = np.array([t.hour * 60 + t.minute - 570 for t in ts])

    def stop_weights(arm_hi, floor, stop=0.04, regime=None):
        w = np.zeros((n, 3))
        hold = np.ones(n, bool)
        if regime is not None:
            hold &= regime[day_id]
        for d in range(len(qc)):
            if regime is not None and not regime[d]:
                continue
            f, l = first[d], last[d]
            m = l - f + 1
            rv = rvc[d, :m]
            ok = np.isfinite(rv)
            armed = ((ok & (rv > arm_hi)) & ok & (rv > floor))
            if regime is not None:
                # round-2 arming needed the MA20 gate; here only volume
                pass
            hit = armed & (cl[f:l + 1, 1] < cl[f, 1] * (1 - stop))
            if hit.any():
                j = int(np.argmax(hit))
                hold[f + j:l + 1] = False
        w[:, 1] = hold.astype(float)
        w[:, 2] = 1 - w[:, 1]
        return w

    for arm_hi, floor in ((1.0, 0.0), (1.5, 1.0), (2.0, 1.0)):
        w = stop_weights(arm_hi, floor)
        s, _ = evaluate(ts, op, cl, w)
        # regime-on version for reference only (not the rebuild)
        wr = stop_weights(arm_hi, floor, regime=reg)
        sr, _ = evaluate(ts, op, cl, wr)
        print(f"C stop pure (no regime) hi>{arm_hi} fl>{floor}: CAGR {s['cagr']*100:6.2f}% "
              f"DD {s['max_drawdown']*100:5.2f}% | with old regime {sr['cagr']*100:6.2f}%/"
              f"{sr['max_drawdown']*100:5.2f}%")


if __name__ == "__main__":
    if os.environ.get("REVISIT_AUTHORIZED") != "1":
        raise SystemExit("PAUSED 2026-11-26: pre-pause exploratory script; "
                             "do not run without authorisation.")
    main()
