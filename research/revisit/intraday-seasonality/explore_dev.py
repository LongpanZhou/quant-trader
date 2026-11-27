"""Development-only exploration for the intraday-seasonality revisit.

Extracted idea: on sessions where QQQ is more than 1% below its session open at
15:00, TQQQ keeps falling into the 15:30 close (forced selling by daily-reset
leveraged funds).  The original only ever used this as a 30-minute overlay on a
165-day-MA book.

Here I test whether the idea can stand alone: which position should the signal
own, and does that book have low correlation with the 165-day baseline?

DEV ONLY: 2016-01-04 .. 2023-12-29.  The panel is loaded with end=2023-12-29 so
no holdout bar is ever touched.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/intraday-seasonality/explore_dev.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent


def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def time_index(ts, first, last, hh, mm):
    target = hh * 60 + mm
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    out = np.empty(len(first), dtype=np.int64)
    for k, (f, l) in enumerate(zip(first, last)):
        j = np.searchsorted(mins[f:l + 1], target)
        out[k] = min(f + j, l)
    return out


def sim(ts, o, c, w, start=DEV_START, end=DEV_END, slip=1.0):
    i = bt.start_index(ts, start)
    j = bt.start_index(ts, end)
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=0.02, slippage_bps=slip)


def metr(r, slip=1.0):
    s = bt.stats(r, BARS_PER_YEAR)
    return {k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "volatility", "fills", "turnover")}


def daily_ret(r):
    ts, eq = r["ts"], r["equity"]
    d = bt.session_dates(ts)
    _, last = day_bounds(d)
    s = pd.Series(eq[last], index=pd.to_datetime([x for x in d[last]]))
    return s.pct_change().dropna()


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=500)
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    n = len(ts)
    i930 = first
    i1500 = time_index(ts, first, last, 15, 0)
    i1530 = time_index(ts, first, last, 15, 30)
    q_open = o[first, 0]
    q_1500 = c[i1500, 0]
    q_1530 = c[i1530, 0]
    q_day = q_1500 / q_open - 1.0
    q_day1530 = q_1530 / q_open - 1.0
    t_open = o[first, 1]
    t_1500 = c[i1500, 1]
    t_1530 = c[i1530, 1]
    print(f"panel {len(first)} sessions {ts[0].date()}..{ts[-1].date()}")

    # ---- 165-day baseline, built only to measure correlation (not used as a strategy)
    dc = c[last, 0]
    sma = pd.Series(dc).rolling(165).mean().to_numpy()
    reg = np.zeros(len(dc), bool)
    reg[1:] = dc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    wb = np.zeros((n, 3))
    wb[:, 1] = reg[day_id].astype(float)
    wb[:, 2] = 1.0 - wb[:, 1]
    rb = sim(ts, o, c, wb)
    mb = metr(rb)
    drb = daily_ret(rb)
    print(f"BASE 165d dev: CAGR {mb['cagr']*100:6.2f}% DD {mb['max_drawdown']*100:5.2f}% "
          f"Sharpe {mb['sharpe']:.2f}")

    def carve(w, mask, shm, ehm):
        out = w.copy()
        si = time_index(ts, first, last, *shm)
        ei = time_index(ts, first, last, *ehm)
        for k in np.flatnonzero(mask):
            a, b = si[k], ei[k] - 2
            a, b = max(a, first[k]), min(b, last[k])
            if b < a:
                continue
            out[a:b + 1] = 0.0
            out[a:b + 1, 2] = 1.0
        return out

    def report(name, w):
        r = sim(ts, o, c, w)
        m = metr(r)
        dr = daily_ret(r)
        j = dr.index.intersection(drb.index)
        corr = float(np.corrcoef(dr.loc[j], drb.loc[j])[0, 1])
        expo = float(np.mean(w[:, 1]))
        print(f"{name:34s} CAGR {m['cagr']*100:6.2f}% DD {m['max_drawdown']*100:5.2f}% "
              f"Sh {m['sharpe']:4.2f} fills {m['fills']:6d} expo {expo*100:5.1f}% corr {corr:5.2f}")
        return {"name": name, "metrics": m, "corr": corr, "expo": expo}, r

    rows = []
    # ---------------------------------------------------------------- A: overlay without a gate
    w = np.zeros((n, 3)); w[:, 1] = 1.0; w[:, 2] = 0.0
    rows.append(report("A long TQQQ always", w)[0])
    for thr in (-0.005, -0.010, -0.015):
        wa = carve(w, q_day < thr, (15, 0), (15, 30))
        rows.append(report(f"A2 carve 15:00-15:30 q<{thr*100:.1f}%", wa)[0])

    # ---------------------------------------------------------------- B: skip the last 30 min
    for shm, ehm, lab in (((15, 30), (15, 59), "15:30-15:59"), ((15, 0), (15, 30), "15:00-15:30")):
        wb2 = carve(w, np.ones(len(first), bool), shm, ehm)
        rows.append(report(f"B skip {lab} every day", wb2)[0])

    # ---------------------------------------------------------------- C: flow-reversal long-only
    # buy at the 15:30 open on a weak day, hold to the next session's 15:00 close
    wc = np.zeros((n, 3))
    for k in np.flatnonzero(q_day < -0.01):
        if k + 1 >= len(first):
            continue
        a = i1530[k]
        b = i1500[k + 1] - 1          # fill out at 15:01 next day
        wc[a:b + 1, 1] = 1.0
    wc[:, 2] = 1.0 - wc[:, 1]
    rows.append(report("C buy flush, hold 1 day q<-1%", wc)[0])

    # variant: exit at next open
    wc2 = np.zeros((n, 3))
    for k in np.flatnonzero(q_day < -0.01):
        if k + 1 >= len(first):
            continue
        wc2[i1530[k]:first[k + 1], 1] = 1.0
    wc2[:, 2] = 1.0 - wc2[:, 1]
    rows.append(report("C2 buy flush, hold to next open", wc2)[0])

    # threshold sweep on C
    for thr in (-0.005, -0.0075, -0.0125, -0.015, -0.020):
        wtmp = np.zeros((n, 3))
        for k in np.flatnonzero(q_day < thr):
            if k + 1 >= len(first):
                continue
            wtmp[i1530[k]:i1500[k + 1], 1] = 1.0
        wtmp[:, 2] = 1.0 - wtmp[:, 1]
        rows.append(report(f"C3 buy flush q<{thr*100:.2f}%", wtmp)[0])

    # C4: only mild down days (-2% < q < -0.5%)
    wtmp = np.zeros((n, 3))
    for k in np.flatnonzero((q_day < -0.005) & (q_day > -0.02)):
        if k + 1 >= len(first):
            continue
        wtmp[i1530[k]:i1500[k + 1], 1] = 1.0
    wtmp[:, 2] = 1.0 - wtmp[:, 1]
    rows.append(report("C4 buy flush -2%<q<-0.5%", wtmp)[0])

    # C5: weak at 15:30 (not 15:00), hold 1 day
    wtmp = np.zeros((n, 3))
    for k in np.flatnonzero(q_day1530 < -0.01):
        if k + 1 >= len(first):
            continue
        wtmp[i1530[k]:i1500[k + 1], 1] = 1.0
    wtmp[:, 2] = 1.0 - wtmp[:, 1]
    rows.append(report("C5 weak at 15:30, hold 1d", wtmp)[0])

    # ---------------------------------------------------------------- sub-periods for the best few
    print("\nsub-periods (1bp)")
    for name, w in (("C q<-1%", wc), ("C2 q<-1% overnight", wc2)):
        for lab, a, b in (("2016-19", "2016-01-04", "2020-01-01"),
                          ("2020-21", "2020-01-01", "2022-01-01"),
                          ("2022-23", "2022-01-01", DEV_END)):
            r = sim(ts, o, c, w, a, b)
            m = metr(r)
            print(f"  {name:22s} {lab} CAGR {m['cagr']*100:7.2f}% DD {m['max_drawdown']*100:6.2f}% "
                  f"Sharpe {m['sharpe']:5.2f} fills {m['fills']}")

    pd.DataFrame([{"name": r["name"], **{f"m_{k}": v for k, v in r["metrics"].items()},
                   "corr": r["corr"], "expo": r["expo"]} for r in rows]).to_csv(OUT / "explore_dev.csv", index=False)
    print("\nwrote explore_dev.csv")


if __name__ == "__main__":
    main()
