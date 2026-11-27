"""Second-pass descriptive study: 30-minute profile, predictive structure, and
per-year stability of the candidate calendar effects, all conditional on the
165-day QQQ regime being risk-on.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/study2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore import load_panel, day_bounds, bar_index, holiday_flags, opex_flags  # noqa: E402

OUT = Path(__file__).resolve().parent
START, END = "2017-01-03", "2026-10-23"
SMA_N = 165


def tstat(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return np.nan, np.nan, len(x)
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(len(x))
    return m * 1e4, (m / se if se > 0 else np.nan), len(x)


def build():
    ts, opens, closes = load_panel()
    dates_all = np.array([t.date() for t in ts])
    first, last = day_bounds(dates_all)
    dates = dates_all[first]

    # half-hour grid 09:30..15:30 plus close
    grid = [(9, 30)] + [(10 + (30 * k) // 60, (30 * k) % 60) for k in range(0, 0)]
    times = []
    for k in range(13):
        m = 9 * 60 + 30 + 30 * k
        times.append((m // 60, m % 60))
    times.append((15, 59))
    idx = [bar_index(ts, first, last, hh, mm) for hh, mm in times]

    tab = pd.DataFrame({"date": pd.to_datetime(list(dates))})
    tab["dow"] = tab["date"].dt.dayofweek
    tab["year"] = tab["date"].dt.year
    for sym, s in (("q", 0), ("t", 1)):
        for j, (hh, mm) in enumerate(times):
            col = f"{sym}_{hh:02d}{mm:02d}"
            tab[col] = closes[idx[j], s]
        tab[f"{sym}_open"] = opens[idx[0], s]
        tab[f"{sym}_prev_close"] = tab[f"{sym}_1559"].shift(1)
        for j in range(len(times) - 1):
            a = f"{sym}_{times[j][0]:02d}{times[j][1]:02d}"
            b = f"{sym}_{times[j+1][0]:02d}{times[j+1][1]:02d}"
            tab[f"{sym}_b{j}"] = tab[b] / tab[a] - 1.0
        tab[f"{sym}_gap"] = tab[f"{sym}_open"] / tab[f"{sym}_prev_close"] - 1.0

    dc = tab["q_1559"]
    sma = dc.rolling(SMA_N).mean()
    tab["regime"] = (dc.shift(1) > sma.shift(1)).astype(float)
    pre, post = holiday_flags(dates)
    op, prew, postw = opex_flags(dates)
    tab["pre_hol"] = pre
    tab["post_hol"] = post
    tab["opex"] = op
    tab["pre_opex"] = prew
    tab["post_opex"] = postw
    return tab


def main():
    tab = build()
    tab = tab[tab["date"] >= START].reset_index(drop=True)
    on = tab["regime"] == 1
    print(f"days {len(tab)}, risk-on {on.sum()} ({on.mean()*100:.1f}%)")

    print("\n=== TQQQ half-hour profile, risk-on days, bp/day ===")
    print("bucket        IS17-21      OOS22-26      full")
    for j in range(12):
        a = tab.loc[on, f"t_b{j}"]
        is_ = a[tab.loc[on, "date"] < "2022-01-01"]
        oos = a[tab.loc[on, "date"] >= "2022-01-01"]
        m1, t1, n1 = tstat(is_)
        m2, t2, n2 = tstat(oos)
        m3, t3, n3 = tstat(a)
        lab = f"{9 + (30 + 30*j)//60:02d}:{(30+30*j)%60:02d}-{9 + (30+30*(j+1))//60:02d}:{(30+30*(j+1))%60:02d}"
        print(f"{lab}  {m1:7.2f} t={t1:5.2f}  {m2:7.2f} t={t2:5.2f}  {m3:7.2f} t={t3:5.2f}")

    print("\n=== predictive regressions (risk-on days) ===")
    for name, xcol, ycol in (
        ("f30 -> last60", "q_b1", "t_b11"),
        ("f30 -> last30", "q_b1", "t_b12"),
        ("f60 -> last60", "q_b1", "t_b11"),
        ("narrow range first hour -> last hour", "q_b1", "t_b11"),
    ):
        if xcol == "q_b1" and name.startswith("f60"):
            x = tab.loc[on, "q_1030"] / tab.loc[on, "q_open"] - 1
        else:
            x = tab.loc[on, xcol]
        y = tab.loc[on, ycol]
        for pname, m in (("IS", tab.loc[on, "date"] < "2022-01-01"),
                         ("OOS", tab.loc[on, "date"] >= "2022-01-01"),
                         ("full", pd.Series(True, index=tab.loc[on].index))):
            xx = x[m.values].to_numpy(); yy = y[m.values].to_numpy()
            ok = np.isfinite(xx) & np.isfinite(yy)
            xx, yy = xx[ok], yy[ok]
            beta = np.polyfit(xx, yy, 1)[0]
            corr = np.corrcoef(xx, yy)[0, 1]
            # t of slope
            resid = yy - np.polyval(np.polyfit(xx, yy, 1), xx)
            se = np.sqrt(np.sum(resid**2) / (len(xx) - 2) / np.sum((xx - xx.mean())**2))
            print(f"  {name:38s} {pname:4s} beta {beta:7.2f} corr {corr:6.3f} t {beta/se:5.2f} n={len(xx)}")

    print("\n=== quintile table: TQQQ last60 by QQQ f30 quintile, risk-on ===")
    for pname, m in (("IS", tab["date"] < "2022-01-01"), ("OOS", tab["date"] >= "2022-01-01")):
        sub = tab[on & m].copy()
        sub["q5"] = pd.qcut(sub["q_b1"], 5, labels=False, duplicates="drop")
        print(f"  {pname}:")
        for k in range(5):
            s = sub[sub["q5"] == k]
            m1, t1, n = tstat(s["t_b11"])
            m2, t2, _ = tstat(s["t_b12"])
            print(f"    Q{k+1} f30 [{s['q_b1'].min()*100:6.2f}%,{s['q_b1'].max()*100:6.2f}%] "
                  f"last60 {m1:7.2f}bp t={t1:5.2f}  last30 {m2:7.2f}bp  n={n}")

    print("\n=== candidate calendar effects, risk-on days, last hour (t_b11) ===")
    masks = {
        "opex": tab["opex"].to_numpy(),
        "pre_opex": tab["pre_opex"].to_numpy(),
        "post_opex": tab["post_opex"].to_numpy(),
        "not opex-window": ~(tab["opex"] | tab["pre_opex"] | tab["post_opex"]).to_numpy(),
        "pre_hol": tab["pre_hol"].to_numpy(),
        "post_hol": tab["post_hol"].to_numpy(),
        "Mon": (tab["dow"] == 0).to_numpy(),
        "Tue": (tab["dow"] == 1).to_numpy(),
        "Wed": (tab["dow"] == 2).to_numpy(),
        "Thu": (tab["dow"] == 3).to_numpy(),
        "Fri": (tab["dow"] == 4).to_numpy(),
    }
    for name, m in masks.items():
        mm = m & on.to_numpy()
        for col, lab in (("t_b11", "last60"), ("t_b5", "12:00-14:00"), ("t_b4", "11:00-12:00")):
            a = tab.loc[mm, col]
            is_ = tab.loc[mm & (tab["date"] < "2022-01-01").to_numpy(), col]
            oos = tab.loc[mm & (tab["date"] >= "2022-01-01").to_numpy(), col]
            m1, t1, n1 = tstat(is_); m2, t2, n2 = tstat(oos)
            print(f"  {name:16s} {lab:12s} IS {m1:7.2f} t={t1:5.2f} n={n1:4d}   OOS {m2:7.2f} t={t2:5.2f} n={n2:4d}")

    print("\n=== per-year last-hour means, risk-on, by group ===")
    for name, m in (("opex", tab["opex"].to_numpy()), ("Wed", (tab["dow"] == 2).to_numpy()),
                    ("rest", ~(tab["opex"] | (tab["dow"] == 2)).to_numpy())):
        print(f"  {name}:")
        for yr in range(2017, 2027):
            mm = m & on.to_numpy() & (tab["year"] == yr).to_numpy()
            m1, t1, n = tstat(tab.loc[mm, "t_b11"])
            print(f"    {yr} {m1:8.2f}bp t={t1:5.2f} n={n:3d}")

    print("\n=== per-year lunch (12-14) means, risk-on ===")
    for name, m in (("opex", tab["opex"].to_numpy()), ("rest", ~tab["opex"].to_numpy())):
        print(f"  {name}:")
        for yr in range(2017, 2027):
            mm = m & on.to_numpy() & (tab["year"] == yr).to_numpy()
            m1, t1, n = tstat(tab.loc[mm, "t_b5"])
            print(f"    {yr} {m1:8.2f}bp t={t1:5.2f} n={n:3d}")

    print("\n=== OpEx-week last-hour daily detail (risk-on) ===")
    sub = tab[on & tab["opex"]]
    print(sub[["date", "dow", "t_b11"]].assign(bp=lambda d: d["t_b11"] * 1e4)
          .to_string(index=False, float_format=lambda v: f"{v:7.2f}"))


if __name__ == "__main__":
    main()
