"""Conditional overnight / intraday return analysis for ORB gating."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"


def prep(sym, ts):
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    x = bt.load_1m(sym)
    return x[(x["ts"] >= lo) & (x["ts"] <= hi)].set_index("ts").reindex(ts).ffill()


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    q = prep("QQQ", ts)
    t = prep("TQQQ", ts)
    g = pd.DataFrame({
        "date": ts.date,
        "qh": q["high"].to_numpy(), "ql": q["low"].to_numpy(),
        "th": t["high"].to_numpy(), "tl": t["low"].to_numpy(),
        "to": t["open"].to_numpy(), "tc": t["close"].to_numpy(),
        "qo": q["open"].to_numpy(), "qc": q["close"].to_numpy(),
    })
    agg = g.groupby("date").agg(
        qh=("qh", "max"), ql=("ql", "min"), qc=("qc", "last"), qo=("qo", "first"),
        th=("th", "max"), tl=("tl", "min"), tc=("tc", "last"), to=("to", "first"))
    orq = g.groupby("date").head(30).groupby("date").agg(or_h=("qh", "max"), or_l=("ql", "min"))
    ort = g.groupby("date").head(30).groupby("date").agg(t_or_h=("th", "max"), t_or_l=("tl", "min"))
    d = agg.join(orq).join(ort)
    d["ret_oc"] = d["tc"] / d["to"] - 1
    d["ret_co"] = d["to"] / d["tc"].shift(1) - 1
    d["close_pos"] = (d["tc"] - d["tl"]) / (d["th"] - d["tl"])
    d["aboveOR"] = d["tc"] > d["t_or_h"]
    d["sma165"] = d["qc"].rolling(165).mean()
    d["regime"] = (d["qc"] > d["sma165"]).shift(1).fillna(False)
    d["on_next"] = d["ret_co"].shift(-1)
    d["oc_next"] = d["ret_oc"].shift(-1)

    for tag, start in (("10y", START10), ("5y", START5)):
        x = d[d.index >= pd.Timestamp(start).date()].copy()
        x["on_next"] = x["ret_co"].shift(-1)
        x["oc_next"] = x["ret_oc"].shift(-1)
        print(f"\n=== {tag}  ({len(x)} days) ===")
        conds = {
            "all": pd.Series(True, index=x.index),
            "aboveOR": x["aboveOR"],
            "aboveOR&regime": x["aboveOR"] & x["regime"],
            "upday": x["tc"] > x["to"],
            "closePos>.7": x["close_pos"] > 0.7,
            "closePos>.7&reg": (x["close_pos"] > 0.7) & x["regime"],
            "aboveOR&closePos>.5": x["aboveOR"] & (x["close_pos"] > 0.5),
            "aboveOR&up&reg": x["aboveOR"] & (x["tc"] > x["to"]) & x["regime"],
        }
        for name, mask in conds.items():
            m = mask.fillna(False)
            r = x.loc[m, "on_next"].dropna()
            r2 = x.loc[m, "oc_next"].dropna()
            if len(r) == 0:
                continue
            ann = ((1 + r).prod() ** (252 / len(x)) - 1) * 100
            ann2 = ((1 + r2).prod() ** (252 / len(x)) - 1) * 100
            print(f"  {name:24s} n={len(r):4d}  overnight mean {r.mean()*100:+.4f}% ann {ann:6.2f}%"
                  f"   next-intraday mean {r2.mean()*100:+.4f}% ann {ann2:6.2f}%")

    # day-of-week / year breakdown of aboveOR overnight
    x = d[d.index >= pd.Timestamp(START10).date()].copy()
    x["year"] = [i.year for i in x.index]
    print("\naboveOR overnight mean by year")
    print((x[x["aboveOR"]].groupby("year")["on_next"].agg(["count", "mean"]) * [1, 100]).round(3))


if __name__ == "__main__":
    main()
