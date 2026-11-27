"""Probe: overnight vs intraday, first/last 30 min, weekday, month effects.

Uses only local 1m QQQ/TQQQ data through the shared bt.panel loader.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt  # noqa: E402

pd.set_option("display.width", 200)


def build(start="2017-01-03", end="2026-10-23"):
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), start, end, "1min")
    df = pd.DataFrame(
        {
            "ts": ts,
            "date": ts.date,
            "minute": ts.hour * 60 + ts.minute,
            "qqq_o": op[:, 0], "qqq_c": cl[:, 0],
            "tqqq_o": op[:, 1], "tqqq_c": cl[:, 1],
            "bil_c": cl[:, 2],
        }
    )
    return df


def daily_table(df: pd.DataFrame, sym: str) -> pd.DataFrame:
    g = df.groupby("date")
    out = pd.DataFrame({
        "open": g[f"{sym}_o"].first(),
        "close": g[f"{sym}_c"].last(),
        "n": g.size(),
    })
    out.index = pd.to_datetime(out.index)
    out["overnight"] = out["open"] / out["close"].shift(1) - 1.0
    out["intraday"] = out["close"] / out["open"] - 1.0
    out["rw"] = out["close"] / out["close"].shift(1) - 1.0
    out["dow"] = out.index.dayofweek
    out["month"] = out.index.month
    out["dom"] = out.index.day
    # turn of month: last 2 and first 3 trading days of the month
    out["tom_rank_end"] = out.groupby(out.index.to_period("M")).cumcount(ascending=False)
    out["tom_rank_beg"] = out.groupby(out.index.to_period("M")).cumcount()
    out["tom"] = (out["tom_rank_end"] <= 1) | (out["tom_rank_beg"] <= 2)
    return out


def ann_stats(r: pd.Series, label: str) -> None:
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = -(eq / eq.cummax() - 1).min()
    sharpe = r.mean() / r.std() * np.sqrt(252)
    print(f"{label:34s} n={len(r):5d} CAGR {cagr*100:7.2f}%  DD {dd*100:6.2f}%  "
          f"vol {r.std()*np.sqrt(252)*100:6.2f}%  Sharpe {sharpe:5.2f}  "
          f"mean_bp {r.mean()*1e4:6.2f}")


def main() -> None:
    df = build()
    q = daily_table(df, "qqq")
    t = daily_table(df, "tqqq")
    # drop the first row (no prior close) and partial/odd days
    q = q[q["n"] >= 200]
    t = t[t["n"] >= 200]

    print("=" * 110)
    print("Block returns, 2017-01-03 .. 2026-10-23 (daily obs = one overnight or one intraday session)")
    print("=" * 110)
    for name, d in (("QQQ", q), ("TQQQ", t)):
        print(f"\n--- {name} ---")
        ann_stats(d["overnight"], f"{name} overnight (C->O)")
        ann_stats(d["intraday"], f"{name} intraday (O->C)")
        ann_stats(d["rw"], f"{name} close-to-close")
        pair = d[["overnight", "intraday"]].dropna()
        print(f"    corr(overnight, intraday) = {pair.corr().iloc[0,1]:.3f}")
        print(f"    share of total log return from overnight: "
              f"{np.log1p(d['overnight']).sum() / np.log1p(d['rw']).sum() * 100:.1f}%")

    print("\n" + "=" * 110)
    print("Same, split 10y vs last 5y")
    print("=" * 110)
    for lo, hi, tag in (("2017-01-03", "2026-10-23", "10y"),
                        ("2021-10-25", "2026-10-23", "5y")):
        for name, d in (("QQQ", q), ("TQQQ", t)):
            dd = d.loc[lo:hi]
            print(f"[{tag}] {name}", end="  ")
            for col in ("overnight", "intraday", "rw"):
                r = dd[col].dropna()
                yrs = (r.index[-1] - r.index[0]).days / 365.25
                eq = (1 + r).cumprod()
                print(f"{col}: CAGR {(eq.iloc[-1]**(1/yrs)-1)*100:6.2f}% "
                      f"DD {-(eq/eq.cummax()-1).min()*100:5.2f}%", end="   ")
            print()

    print("\n" + "=" * 110)
    print("Per-year TQQQ overnight vs intraday (CAGR from daily compounding, no costs)")
    print("=" * 110)
    rows = []
    for y, grp in t.groupby(t.index.year):
        def f(col):
            r = grp[col].dropna()
            if len(r) < 20:
                return np.nan
            return (1 + r).prod() - 1
        rows.append({"year": y, "overnight": f("overnight"), "intraday": f("intraday"),
                     "rw": f("rw")})
    yr = pd.DataFrame(rows).set_index("year")
    print((yr * 100).round(1).to_string())
    print("\nsign consistency overnight:", (yr["overnight"] > 0).sum(), "/", len(yr),
          " intraday:", (yr["intraday"] > 0).sum(), "/", len(yr))

    print("\n" + "=" * 110)
    print("Intraday sub-blocks (TQQQ): open->10:00, 10:00->15:30, 15:30->close")
    print("=" * 110)
    mins = df["minute"].to_numpy()
    dates = df["date"].to_numpy()
    tc = df["tqqq_c"].to_numpy()
    to = df["tqqq_o"].to_numpy()
    qc = df["qqq_c"].to_numpy()
    qo = df["qqq_o"].to_numpy()

    idx_1000 = np.where(mins == 10 * 60)[0]
    idx_1530 = np.where(mins == 15 * 60)[0]
    # map date -> index of first bar and last bar
    first = pd.Series(np.arange(len(df))).groupby(dates).first().to_numpy()
    last = pd.Series(np.arange(len(df))).groupby(dates).last().to_numpy()

    dts = pd.DatetimeIndex(sorted(set(dates)))
    # close of 09:59 bar = 10:00:00
    c_1000 = np.array([tc[i - 1] for i in idx_1000 if i > 0])
    dates_1000 = np.array([dates[i - 1] for i in idx_1000 if i > 0])
    c_1530 = np.array([tc[i - 1] for i in idx_1530 if i > 0])
    dates_1530 = np.array([dates[i - 1] for i in idx_1530 if i > 0])
    m1000 = pd.Series(c_1000, index=pd.to_datetime(dates_1000))
    m1530 = pd.Series(c_1530, index=pd.to_datetime(dates_1530))

    dd = pd.DataFrame(index=t.index)
    dd["open"] = t["open"]
    dd["close"] = t["close"]
    dd["p1000"] = m1000.reindex(dd.index)
    dd["p1530"] = m1530.reindex(dd.index)
    dd = dd.dropna()
    blk = pd.DataFrame({
        "first30": dd["p1000"] / dd["open"] - 1,
        "mid": dd["p1530"] / dd["p1000"] - 1,
        "last30": dd["close"] / dd["p1530"] - 1,
        "overnight": dd["open"] / t["close"].shift(1).reindex(dd.index) - 1,
    })
    for c in blk.columns:
        ann_stats(blk[c], f"TQQQ {c}")
    print(f"\ncorr(first30, overnight) = {blk[['first30','overnight']].corr().iloc[0,1]:.3f}")
    print(f"corr(last30, overnight)  = {blk[['last30','overnight']].corr().iloc[0,1]:.3f}")

    print("\n" + "=" * 110)
    print("Weekday conditioning (TQQQ, full period), mean bp and annualised")
    print("=" * 110)
    for dow, grp in t.groupby("dow"):
        print(f"dow={dow} n={len(grp):4d}  overnight mean {grp['overnight'].mean()*1e4:7.2f}bp "
              f"tot {(1+grp['overnight']).prod()-1:9.1%}   "
              f"intraday mean {grp['intraday'].mean()*1e4:7.2f}bp tot {(1+grp['intraday']).prod()-1:9.1%}")

    print("\n" + "=" * 110)
    print("Turn-of-month vs rest (TQQQ)")
    print("=" * 110)
    for flag, grp in t.groupby("tom"):
        print(f"tom={flag} n={len(grp):4d} overnight tot {(1+grp['overnight'].dropna()).prod()-1:9.1%}"
              f"  intraday tot {(1+grp['intraday'].dropna()).prod()-1:9.1%}"
              f"  c2c tot {(1+grp['rw'].dropna()).prod()-1:9.1%}")

    print("\n" + "=" * 110)
    print("Monthly seasonality (TQQQ c2c total per year-avg)")
    print("=" * 110)
    m = t.groupby("month")["rw"].agg(["mean", "count"])
    m["mean_bp"] = m["mean"] * 1e4
    print(m.round(4).to_string())


if __name__ == "__main__":
    main()
