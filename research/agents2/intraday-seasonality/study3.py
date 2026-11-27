"""Third-pass study: does the late-day tape predict the last 30 minutes and the
overnight?  Conditional means for close-weakness, lunch, and calendar groups.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/study3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
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
    F = cal["dates"]

    i1030 = lib.time_index(ts, first, last, 10, 30)
    i1200 = lib.time_index(ts, first, last, 12, 0)
    i1400 = lib.time_index(ts, first, last, 14, 0)
    i1500 = lib.time_index(ts, first, last, 15, 0)
    i1530 = lib.time_index(ts, first, last, 15, 30)
    i1559 = lib.time_index(ts, first, last, 15, 59)

    t_open = opens[first, 1]
    t_c = closes[:, 1]
    q_c = closes[:, 0]
    t_c1559 = t_c[i1559]
    t_c1530 = t_c[i1530]
    t_c1500 = t_c[i1500]
    t_c1200 = t_c[i1200]
    t_c1400 = t_c[i1400]
    t_c1030 = t_c[i1030]
    q_open = opens[first, 0]
    q_c1559 = q_c[i1559]

    on, _, _ = lib.regime_on(ts, closes)
    on_prev = np.r_[False, on[:-1]]  # regime applied to the session is prior close vs sma

    df = pd.DataFrame({"date": F, "dow": cal["dow"], "year": cal["year"],
                       "opex": cal["opex"], "pre_opex": cal["pre_opex"],
                       "post_opex": cal["post_opex"],
                       "pre_hol": cal["pre_hol"], "post_hol": cal["post_hol"],
                       "on": on})
    df["t_open"] = t_open
    df["t_day30"] = t_c1530 / t_open - 1.0            # open -> 15:30
    df["t_day00"] = t_c1500 / t_open - 1.0            # open -> 15:00
    df["t_last30"] = t_c1559 / t_c1530 - 1.0          # 15:30 -> close
    df["t_1500_30"] = t_c1530 / t_c1500 - 1.0         # 15:00 -> 15:30
    df["t_lunch"] = t_c1400 / t_c1200 - 1.0
    df["t_morning"] = t_c1200 / t_open - 1.0
    df["t_1030_1100"] = t_c1200 / t_c1030 - 1.0       # placeholder, fixed below
    df["t_on_next"] = np.r_[t_open[1:] / t_c1559[:-1] - 1.0, np.nan]
    df["t_1530_nextopen"] = np.r_[t_open[1:] / t_c1530[:-1] - 1.0, np.nan]
    df["t_1500_nextopen"] = np.r_[t_open[1:] / t_c1500[:-1] - 1.0, np.nan]
    df["t_nextday"] = np.r_[t_c1559[1:] / t_open[1:] - 1.0, np.nan]
    df["q_day30"] = q_c1559 / q_open - 1.0

    df = df[df["date"] >= "2017-01-03"].reset_index(drop=True)
    on = df["on"].to_numpy()
    is_m = (df["date"] < "2022-01-01").to_numpy()
    oos_m = ~is_m

    def show(col, mask, label):
        mm = mask & on
        a = df.loc[mm, col].to_numpy()
        m1, t1, n1 = tstat(a[is_m[mm]])
        m2, t2, n2 = tstat(a[oos_m[mm]])
        m3, t3, n3 = tstat(a)
        print(f"  {label:30s} IS {m1:7.2f} t={t1:5.2f} n={n1:4d} | OOS {m2:7.2f} t={t2:5.2f} n={n2:4d} "
              f"| all {m3:7.2f} t={t3:5.2f}")

    print("=== A. late-day weakness -> last 30 min and overnight (risk-on) ===")
    bins = [-1, -0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 1]
    labs = ["<-4%", "-4..-3", "-3..-2", "-2..-1", "-1..0", "0..1", "1..2", "2..3", ">3%"]
    g = pd.cut(df["t_day30"], bins, labels=labs)
    for L in labs:
        m = (g == L).to_numpy()
        show("t_last30", m, f"day@1530 {L} -> last30")
        show("t_on_next", m, f"day@1530 {L} -> overnight")
        show("t_1530_nextopen", m, f"day@1530 {L} -> 1530..nextopen")

    print("\n=== B. QQQ day move (open->close) buckets -> TQQQ overnight ===")
    bins2 = [-1, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 1]
    labs2 = ["<-3%", "-3..-2", "-2..-1", "-1..0", "0..1", "1..2", "2..3", ">3%"]
    g2 = pd.cut(df["q_day30"], bins2, labels=labs2)
    for L in labs2:
        m = (g2 == L).to_numpy()
        show("t_last30", m, f"QQQ day {L} -> last30")
        show("t_on_next", m, f"QQQ day {L} -> overnight")

    print("\n=== C. Tuesday/Wednesday overnight, Monday/Tuesday session etc (risk-on) ===")
    for d, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
        m = (df["dow"] == d).to_numpy()
        show("t_on_next", m, f"{name} -> next open")
        show("t_nextday", m, f"{name} session")
        show("t_last30", m, f"{name} last30")
        show("t_1500_30", m, f"{name} 15:00-15:30")

    print("\n=== D. calendar groups: last30 / overnight / session ===")
    for flag in ("opex", "pre_opex", "post_opex", "pre_hol", "post_hol"):
        m = df[flag].to_numpy()
        print(f"  -- {flag} --")
        show("t_last30", m, "last30")
        show("t_1500_30", m, "15:00-15:30")
        show("t_on_next", m, "overnight")
        show("t_nextday", m, "session")

    print("\n=== E. pre-holiday overnight detail (risk-on) ===")
    m = df["pre_hol"].to_numpy() & on
    print(df.loc[m, ["date", "dow", "t_on_next"]].assign(bp=df.loc[m, "t_on_next"] * 1e4)
          .to_string(index=False, float_format=lambda v: f"{v:8.2f}"))

    print("\n=== F. last-30-min carve: gross P&L per year vs cost ===")
    for flag, mask in (("all", np.ones(len(df), bool)),
                       ("opex", df["opex"].to_numpy()),
                       ("wed", (df["dow"] == 2).to_numpy()),
                       ("weak", (df["t_day30"] < -0.02).to_numpy())):
        mm = mask & on
        a = df.loc[mm, "t_last30"].to_numpy()
        m1, t1, n = tstat(a)
        print(f"  {flag:6s} n={n:4d} mean {m1:7.2f}bp t={t1:5.2f}  gross/yr {m1*n/10.2:7.2f}pp "
              f"cost@1bp {2.0*n/10.2:5.2f}pp  cost@5bp {10.0*n/10.2:5.2f}pp")

    df.to_csv(OUT / "daily_table.csv", index=False)
    print("\nwrote daily_table.csv", df.shape)


if __name__ == "__main__":
    main()
