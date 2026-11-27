"""Fourth-pass study: the last-hour continuation effect, measured on the exact
window the overlay trades (15:01 open -> 15:59 open), with IS/OOS, per-year,
per-decile, and an official-close robustness check.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/study4.py
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

    i1100 = lib.time_index(ts, first, last, 11, 0)
    i1200 = lib.time_index(ts, first, last, 12, 0)
    i1400 = lib.time_index(ts, first, last, 14, 0)
    i1500 = lib.time_index(ts, first, last, 15, 0)
    i1530 = lib.time_index(ts, first, last, 15, 30)
    i1559 = lib.time_index(ts, first, last, 15, 59)

    gaps = i1559 - i1530
    print("bar gap 15:30->15:59:", np.bincount(gaps).nonzero()[0][:10], "most common", np.bincount(gaps).argmax())

    q_open = opens[first, 0]
    t_open = opens[first, 1]
    q_1500 = opens[i1500, 0]
    t_1500 = opens[i1500, 1]
    q_c1530 = closes[i1530, 0]
    t_c1530 = closes[i1530, 1]
    q_c1559 = closes[i1559, 0]
    t_c1559 = closes[i1559, 1]

    # official daily close for robustness
    daily = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    daily.index = pd.to_datetime(daily["date"])
    q_off = daily["adjclose"].reindex(dates).to_numpy()
    td = pd.read_parquet(ROOT / "data" / "intraday-hf" / "TQQQ-1d-yahoo.parquet")
    td.index = pd.to_datetime(td["date"])
    t_off = td["adjclose"].reindex(dates).to_numpy()

    on, _, _ = lib.regime_on(ts, closes)

    df = pd.DataFrame({"date": dates, "year": cal["year"], "dow": cal["dow"],
                       "on": on})
    df["q_day"] = q_c1530 / q_open - 1.0
    df["q_day_prev"] = q_c1530 / np.r_[np.nan, q_c1559[:-1]] - 1.0
    df["t_day"] = t_c1530 / t_open - 1.0
    df["last60_1m"] = t_c1559 / t_1500 - 1.0
    df["last30_1m"] = t_c1559 / t_c1530 - 1.0
    df["last60_exact"] = opens[i1559, 1] / opens[i1500 + 1, 1] - 1.0
    df["last60_off"] = t_off / t_1500 - 1.0
    df["close_bar"] = t_c1559 / t_1500 - 1.0
    df["last_bar"] = t_off / t_c1559 - 1.0
    df["open_bar"] = opens[i1500 + 1, 1] / t_1500 - 1.0

    df = df[df["date"] >= "2017-01-03"].reset_index(drop=True)
    on = df["on"].to_numpy()
    is_m = (df["year"] < 2022).to_numpy()

    def show(col, mask, label):
        mm = mask & on
        a = df.loc[mm, col].to_numpy()
        m1, t1, n1 = tstat(a[is_m[mm]])
        m2, t2, n2 = tstat(a[~is_m[mm]])
        m3, t3, n3 = tstat(a)
        print(f"  {label:34s} IS {m1:8.2f} t={t1:6.2f} n={n1:4d} | OOS {m2:8.2f} t={t2:6.2f} n={n2:4d} "
              f"| all {m3:8.2f} t={t3:6.2f}")

    print("\n=== QQQ day (open->15:30) -> TQQQ last hour (15:01 open -> 15:59 open) ===")
    bins = [-1, -0.03, -0.02, -0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015, 0.02, 0.03, 1]
    labs = ["<-3", "-3..-2", "-2..-1.5", "-1.5..-1", "-1..-.5", "-.5..0",
            "0..+.5", "+.5..1", "1..1.5", "1.5..2", "2..3", ">3"]
    g = pd.cut(df["q_day"], bins, labels=labs)
    for L in labs:
        m = (g == L).to_numpy()
        show("last60_1m", m, f"qday {L}% -> last hour")
    show("last60_1m", np.ones(len(df), bool), "ALL -> last hour")
    show("last60_exact", np.ones(len(df), bool), "ALL -> last hour (exact carve)")
    show("last60_off", np.ones(len(df), bool), "ALL -> last hour (official close)")
    show("last_bar", np.ones(len(df), bool), "last minute 15:59->16:00 (official)")

    print("\n=== threshold sweep, TQQQ last hour ===")
    for thr in (0.0, -0.0025, -0.005, -0.0075, -0.01, -0.015, -0.02, -0.03):
        m = (df["q_day"] < thr).to_numpy()
        show("last60_1m", m, f"qday<{thr*100:.2f}%")
        show("last60_exact", m, f"   exact qday<{thr*100:.2f}%")
        show("last60_off", m, f"   official qday<{thr*100:.2f}%")

    print("\n=== per-year: sum of last-hour TQQQ returns on qday<0 days ===")
    m = (df["q_day"] < 0).to_numpy() & on
    for yr in range(2017, 2027):
        mm = m & (df["year"] == yr).to_numpy()
        a = df.loc[mm, "last60_1m"].to_numpy()
        print(f"  {yr}: n={len(a):3d} sum {a.sum()*100:8.2f}%  mean {a.mean()*1e4:8.2f}bp  "
              f"win {np.mean(a>0)*100:5.1f}%")

    print("\n=== per-year: same for qday<0 day totals (open->close) ===")
    for yr in range(2017, 2027):
        mm = m & (df["year"] == yr).to_numpy()
        a = df.loc[mm, "last60_1m"].to_numpy()
        print(f"  {yr}: gross avoided {a.sum()*100:8.2f}% on {len(a)} days")

    print("\n=== robustness: official close version, threshold sweep ===")
    for thr in (0.0, -0.005, -0.01, -0.02):
        mm = (df["q_day"] < thr).to_numpy() & on
        a = df.loc[mm, "last60_off"].to_numpy()
        m1, t1, n = tstat(a)
        m2, t2, _ = tstat(df.loc[mm & is_m, "last60_off"].to_numpy())
        m3, t3, _ = tstat(df.loc[mm & ~is_m, "last60_off"].to_numpy())
        print(f"  qday<{thr*100:5.2f}%  IS {m2:8.2f}  OOS {m3:8.2f}  all {m1:8.2f} t={t1:5.2f} n={n}")

    print("\n=== decomposition: is the effect in the 15:00 bar, the hour, or the close bar? ===")
    for thr in (0.0, -0.01):
        mm = (df["q_day"] < thr).to_numpy() & on
        for col in ("open_bar", "last60_exact", "last_bar"):
            m1, t1, n = tstat(df.loc[mm, col].to_numpy())
            print(f"  qday<{thr*100:5.1f}% {col:14s} {m1:8.2f}bp t={t1:5.2f}")

    df.to_csv(OUT / "last_hour_table.csv", index=False)
    print("\nwrote last_hour_table.csv")


if __name__ == "__main__":
    main()
