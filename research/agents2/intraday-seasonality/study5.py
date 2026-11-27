"""Fifth pass: where in the afternoon does the continuation live, does a VWAP or
MA gate help, and when do the winner's stop events actually occur?

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/study5.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import lib  # noqa: E402

OUT = Path(__file__).resolve().parent


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return np.nan, np.nan, len(x)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    return m * 1e4, (m / se if se > 0 else np.nan), len(x)


def main():
    ts, opens, closes = lib.load_panel()
    cal = lib.calendar(ts)
    first, last = cal["first"], cal["last"]
    dates = cal["dates"]
    on, _, _ = lib.regime_on(ts, closes)

    T = {t: lib.time_index(ts, first, last, *t) for t in
         ((13, 0), (14, 0), (14, 30), (15, 0), (15, 30), (15, 59))}
    q_open = opens[first, 0]
    t_open = opens[first, 1]
    q = {t: closes[i, 0] for t, i in T.items()}
    t = {t: closes[i, 1] for t, i in T.items()}

    df = pd.DataFrame({"date": dates, "year": cal["year"], "on": on,
                       "dow": cal["dow"], "opex": cal["opex"],
                       "pre_hol": cal["pre_hol"], "post_hol": cal["post_hol"]})

    # day-so-far signals at various decision times
    for tt in ((13, 0), (14, 0), (14, 30), (15, 0), (15, 30)):
        df[f"q_day_{tt[0]}{tt[1]:02d}"] = q[tt] / q_open - 1.0

    # forward blocks (TQQQ)
    df["b_1300_1400"] = t[(14, 0)] / t[(13, 0)] - 1.0
    df["b_1400_1430"] = t[(14, 30)] / t[(14, 0)] - 1.0
    df["b_1430_1500"] = t[(15, 0)] / t[(14, 30)] - 1.0
    df["b_1500_1530"] = t[(15, 30)] / t[(15, 0)] - 1.0
    df["b_1530_1559"] = t[(15, 59)] / t[(15, 30)] - 1.0
    df["b_1430_1559"] = t[(15, 59)] / t[(14, 30)] - 1.0
    df["b_1500_1559"] = t[(15, 59)] / t[(15, 0)] - 1.0
    df["b_1400_1559"] = t[(15, 59)] / t[(14, 0)] - 1.0

    df = df[df["date"] >= "2017-01-03"].reset_index(drop=True)
    on_full = on.copy()
    on = df["on"].to_numpy()
    is_m = (df["year"] < 2022).to_numpy()

    def show(col, mask, label):
        mm = mask & on
        a = df.loc[mm, col].to_numpy()
        m1, t1, n1 = tstat(a[is_m[mm]])
        m2, t2, n2 = tstat(a[~is_m[mm]])
        m3, t3, n3 = tstat(a)
        print(f"  {label:26s} IS {m1:8.2f} t={t1:6.2f} | OOS {m2:8.2f} t={t2:6.2f} | "
              f"all {m3:8.2f} t={t3:6.2f} n={n3:4d}")

    print("=== term structure: QQQ open->14:30 signal, forward TQQQ blocks ===")
    for thr in (0.0, -0.005, -0.010):
        m = (df["q_day_1430"] < thr).to_numpy()
        print(f" signal {thr*100:5.2f}%  (n={int((m&on).sum())})")
        for col in ("b_1430_1500", "b_1500_1530", "b_1530_1559",
                    "b_1430_1559", "b_1500_1559"):
            show(col, m, f"   {col}")

    print("\n=== term structure by 15:00 signal ===")
    for thr in (0.0, -0.005, -0.010):
        m = (df["q_day_1500"] < thr).to_numpy()
        print(f" signal {thr*100:5.2f}%  (n={int((m&on).sum())})")
        for col in ("b_1500_1530", "b_1530_1559", "b_1500_1559"):
            show(col, m, f"   {col}")

    print("\n=== is it the level or the slope?  signal vs prior-close, 15:00 ===")
    prev = np.r_[np.nan, q[(15, 59)][:-1]]
    full = pd.DataFrame({"date": dates,
                         "q_prev_day": q[(15, 0)] / prev - 1.0,
                         "b_1500_1559": t[(15, 59)] / t[(15, 0)] - 1.0,
                         "on": on_full})
    full = full[full["date"] >= "2017-01-03"].reset_index(drop=True)
    on2 = full["on"].to_numpy()
    is2 = (pd.to_datetime(full["date"]).dt.year < 2022).to_numpy()
    for thr in (0.0, -0.005, -0.010):
        mm = (full["q_prev_day"] < thr).to_numpy() & on2
        a = full.loc[mm, "b_1500_1559"].to_numpy()
        m1, t1, n = tstat(a[is2[mm]])
        m2, t2, _ = tstat(a[~is2[mm]])
        m3, t3, _ = tstat(a)
        print(f"  vs prev close <{thr*100:5.1f}%  IS {m1:8.2f} t={t1:6.2f} | OOS {m2:8.2f} t={t2:6.2f} | "
              f"all {m3:8.2f} t={t3:6.2f} n={n}")

    print("\n=== stop events by calendar (winner, all sessions) ===")
    w, diag = lib.build_base(ts, opens, closes)
    stops = diag["stops"]
    sdf = pd.DataFrame(stops, columns=["date", "time"])
    sdf["date"] = pd.to_datetime(sdf["date"])
    sdf["year"] = sdf["date"].dt.year
    sdf["dow"] = sdf["date"].dt.day_of_week
    dd = pd.DataFrame({"date": pd.to_datetime(list(dates)), "opex": cal["opex"],
                       "pre_hol": cal["pre_hol"], "post_hol": cal["post_hol"]})
    sdf = sdf.merge(dd, on="date", how="left")
    print(f"  total stops {len(sdf)}")
    print("  by dow:", sdf.groupby("dow").size().to_dict())
    print("  by year:", sdf.groupby("year").size().to_dict())
    print(f"  on opex week: {int(sdf['opex'].sum())} ({sdf['opex'].mean()*100:.1f}%)  "
          f"pre-hol: {int(sdf['pre_hol'].sum())}  post-hol: {int(sdf['post_hol'].sum())}")

    # P&L of the stop: TQQQ return from stop bar close to next session open
    # (positive = the stop avoided a loss)
    rows = []
    dpos = {d: i for i, d in enumerate(dates.date)}
    for d, tm in stops:
        dd_ = pd.Timestamp(d)
        k = dpos.get(dd_.date(), -1)
        if k < 0 or k + 1 >= len(dates):
            continue
        f0 = first[k]
        hh, mm = map(int, tm.split(":")[:2])
        # find the bar at that time on that day
        j = lib.time_index(ts, first[k:k+1], last[k:k+1], hh, mm)[0]
        r = opens[first[k + 1], 1] / closes[j, 1] - 1.0
        rows.append({"date": dd_, "dow": dd_.day_of_week, "saving": -r,
                     "opex": bool(cal["opex"][k]), "pre_hol": bool(cal["pre_hol"][k]),
                     "post_hol": bool(cal["post_hol"][k])})
    ev = pd.DataFrame(rows)
    print("\n  stop event saving (positive = stop helped), bp:")
    for grp, sub in (("all", ev), ("opex", ev[ev["opex"]]),
                     ("pre_hol", ev[ev["pre_hol"]]), ("post_hol", ev[ev["post_hol"]]),
                     ("mon", ev[ev["dow"] == 0]), ("fri", ev[ev["dow"] == 4])):
        if len(sub) < 2:
            continue
        print(f"    {grp:9s} n={len(sub):3d} mean {sub['saving'].mean()*1e4:8.2f}bp  "
              f"median {sub['saving'].median()*1e4:7.2f}bp  win {np.mean(sub['saving']>0)*100:4.1f}%")

    df.to_csv(OUT / "afternoon_table.csv", index=False)
    ev.to_csv(OUT / "stops.csv", index=False)
    print("\nwrote afternoon_table.csv, stops.csv")


if __name__ == "__main__":
    main()
