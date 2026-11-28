"""Data / curve integrity checks for the two winners."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402

OUT = {}


def main():
    ts, o, h, l, c = W.load_panel()
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sd = dates[last]
    counts = last - first + 1
    uniq, freq = np.unique(counts, return_counts=True)
    OUT["sessions"] = int(len(first))
    OUT["bars"] = int(len(ts))
    OUT["bar_count_distribution"] = {int(k): int(v) for k, v in zip(uniq, freq)}
    OUT["first_ts"] = str(ts[0])
    OUT["last_ts"] = str(ts[-1])
    OUT["duplicate_ts"] = int(len(ts) - len(np.unique(ts.asi8)))
    OUT["monotonic_ts"] = bool(np.all(np.diff(ts.asi8) > 0))

    # bar-count anomalies vs 390 (regular) / 210 (half-day)
    half = {d for d in bt.HALF_DAYS}
    anomalies = []
    for k, (d, f, ll, n) in enumerate(zip(sd, first, last, counts)):
        d = pd.Timestamp(d).date()
        expected = 210 if d in half else 390
        if n != expected:
            anomalies.append({"date": str(d), "bars": int(n), "expected": expected,
                              "half_day_listed": d in half,
                              "first": str(ts[f].time()), "last": str(ts[ll].time())})
    OUT["bar_count_anomalies"] = anomalies
    OUT["bar_count_anomaly_count"] = len(anomalies)

    # OHLC sanity on the panel
    bad = {
        "high_lt_max_oc": int(np.sum(h < np.maximum(o, c) - 1e-9)),
        "low_gt_min_oc": int(np.sum(l > np.minimum(o, c) + 1e-9)),
        "high_lt_low": int(np.sum(h < l - 1e-9)),
        "nonpositive": int(np.sum((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0))),
        "nan": int(np.sum(~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(l) | ~np.isfinite(c))),
    }
    OUT["ohlc_bad"] = bad

    # raw 1m return extremes per symbol
    ext = {}
    for j, sym in enumerate(("QQQ", "TQQQ", "BIL")):
        r = np.diff(c[:, j]) / c[:-1, j]
        idx = np.argsort(r)
        top = []
        for i in list(idx[:12]):
            top.append({"ts": str(ts[i + 1]),
                        "ret": float(r[i]),
                        "prev_close": float(c[i, j]),
                        "close": float(c[i + 1, j]),
                        "next_ret": float(r[i + 1]) if i + 1 < len(r) else None,
                        "volume": None})
        ext[sym] = {
            "n_gt_10pct": int(np.sum(np.abs(r) > 0.10)),
            "n_gt_15pct": int(np.sum(np.abs(r) > 0.15)),
            "n_gt_20pct": int(np.sum(np.abs(r) > 0.20)),
            "worst": top,
        }
    OUT["minute_extremes"] = ext

    # panel daily close vs Yahoo adjusted daily close
    yd = {}
    for j, sym in enumerate(("QQQ", "TQQQ", "BIL")):
        df = pd.read_parquet(W.ROOT / "data" / "intraday-hf" / f"{sym}-1d-yahoo.parquet")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.set_index("date")
        p = pd.Series(c[last, j], index=[pd.Timestamp(d).date() for d in sd])
        common = p.index.intersection(df.index)
        rel = p.loc[common] / df.loc[common, "adjclose"].astype(float) - 1.0
        worst = rel.abs().sort_values(ascending=False).head(10)
        yd[sym] = {
            "n_days": int(len(common)),
            "max_abs_rel": float(rel.abs().max()),
            "mean_abs_rel": float(rel.abs().mean()),
            "worst": [{"date": str(d), "rel": float(rel.loc[d]),
                       "panel": float(p.loc[d]),
                       "yahoo": float(df.loc[d, "adjclose"])} for d in worst.index],
        }
    OUT["daily_vs_yahoo"] = yd

    # daily returns of panel vs yahoo
    dr = {}
    for j, sym in enumerate(("QQQ", "TQQQ", "BIL")):
        s = pd.Series(c[last, j], index=[pd.Timestamp(d) for d in sd])
        sr = s.pct_change()
        df = pd.read_parquet(W.ROOT / "data" / "intraday-hf" / f"{sym}-1d-yahoo.parquet")
        df["date"] = pd.to_datetime(df["date"])
        y = pd.Series(df["adjclose"].to_numpy(), index=df["date"])
        yr = y.pct_change()
        j2 = pd.concat([sr.rename("p"), yr.rename("y")], axis=1).dropna()
        diff = (j2["p"] - j2["y"]).abs()
        dr[sym] = {"max_abs_diff": float(diff.max()),
                   "p99_abs_diff": float(diff.quantile(0.99)),
                   "mean_abs_diff": float(diff.mean()),
                   "worst": [{"date": str(d.date()), "panel_ret": float(j2.loc[d, "p"]),
                              "yahoo_ret": float(j2.loc[d, "y"])}
                             for d in diff.sort_values(ascending=False).head(8).index]}
    OUT["daily_returns_vs_yahoo"] = dr

    # TQQQ stop triggers: how many, and are they isolated bad prints?
    mod, w, info, atr, f2, l2 = W.load_vol(ts, o, h, l, c)
    events = info["event_list"]
    trig = []
    for k, i, d in events:
        # reversal over the next 5 minutes and rest of session
        nxt5 = c[min(i + 5, len(c) - 1), 1] / c[i, 1] - 1.0
        eod = c[l2[k], 1] / c[i, 1] - 1.0
        trig.append({"date": str(pd.Timestamp(sd[k]).date()), "bar": int(i),
                     "ts": str(ts[i]), "d": float(d),
                     "trig_close_ret_from_open": float(c[i, 1] / o[f2[k], 1] - 1.0),
                     "next5_ret": float(nxt5), "eod_ret_from_trig": float(eod),
                     "volume": float(np.nan)})
    trig_sorted = sorted(trig, key=lambda x: x["trig_close_ret_from_open"])
    OUT["vol_events"] = {
        "n": len(trig),
        "worst_20": trig_sorted[:20],
        "n_next5_positive": int(sum(t["next5_ret"] > 0 for t in trig)),
        "mean_next5": float(np.mean([t["next5_ret"] for t in trig])),
        "mean_eod": float(np.mean([t["eod_ret_from_trig"] for t in trig])),
        "n_eod_positive": int(sum(t["eod_ret_from_trig"] > 0 for t in trig)),
    }

    # stop triggers in the ratio base: count days where the 4% stop fires
    qqq_close, tqqq_close = c[:, 0], c[:, 1]
    dc = qqq_close[last]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    trig_days = []
    for k, (f, ll) in enumerate(zip(first, last)):
        if k == 0 or not (ma20_prev[k] == ma20_prev[k]):
            continue
        if not (qqq_close[f] < ma20_prev[k] * 1.01):
            continue
        base = o[f, 1]
        idx = np.flatnonzero(tqqq_close[f:ll + 1] < base * 0.96)
        if len(idx):
            i = f + int(idx[0])
            trig_days.append({"date": str(pd.Timestamp(sd[k]).date()),
                              "ts": str(ts[i]),
                              "ret_from_open": float(tqqq_close[i] / base - 1.0),
                              "next5": float(c[min(i + 5, len(c) - 1), 1] / c[i, 1] - 1.0)})
    OUT["ratio_stop_days"] = {
        "n": len(trig_days),
        "worst_15": sorted(trig_days, key=lambda x: x["ret_from_open"])[:15],
    }

    (HERE / "winners_integrity.json").write_text(json.dumps(OUT, indent=1, default=float),
                                                 encoding="utf-8")
    print(json.dumps({k: OUT[k] for k in
                      ("sessions", "bars", "bar_count_anomaly_count", "ohlc_bad",
                       "duplicate_ts", "monotonic_ts")}, indent=1))
    print("anomalies", json.dumps(OUT["bar_count_anomalies"][:20], indent=1))
    print("daily vs yahoo", json.dumps({k: {"max": v["max_abs_rel"], "mean": v["mean_abs_rel"]}
                                        for k, v in yd.items()}, indent=1))
    print("minute extremes", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "worst"}
                                         for k, v in ext.items()}, indent=1))
    print("vol events", OUT["vol_events"]["n"], "mean next5",
          OUT["vol_events"]["mean_next5"], "ratio stop days", OUT["ratio_stop_days"]["n"])


if __name__ == "__main__":
    main()
