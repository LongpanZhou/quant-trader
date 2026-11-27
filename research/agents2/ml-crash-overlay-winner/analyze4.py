"""Proper lagged analysis: features at d predict returns at d+1."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze2 import winner_daily  # noqa: E402

START, END = "2017-01-03", "2026-10-23"


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    tqo = pd.Series(o[first, 1], index=dts)
    tqc = pd.Series(c[last, 1], index=dts)
    qqo = pd.Series(o[first, 0], index=dts)
    qqc = pd.Series(c[last, 0], index=dts)
    bil = pd.Series(c[last, 2], index=dts)

    d = pd.DataFrame({"held": opened, "stopped": stopped}, index=dts)
    d["gap"] = tqo / tqc.shift(1) - 1.0
    d["intra"] = tqc / tqo - 1.0
    d["tot"] = tqc / tqc.shift(1) - 1.0
    d["ex_bil"] = d.tot - bil.pct_change()
    d["q_intra"] = qqc / qqo - 1.0
    d = d.join(f.add_prefix("f_").shift(1), how="left")  # lag: use data through d-1

    m = d.index >= pd.Timestamp("2017-01-03")
    base = d[m]
    held = d[m & d.held]
    print(f"all days {len(base)}, winner-held {len(held)}")

    for tgt in ("gap", "intra", "tot", "ex_bil"):
        print(f"\n=== target {tgt}: mean by feature decile (all days) ===")
        for col in ["rv_pct", "dvol20", "range20", "rv_ratio", "vwap_dist", "dd_high",
                    "last30", "rsi14", "sma20", "sma165", "decay20", "close_loc",
                    "first30", "vol_z20", "skew1"]:
            x = base["f_" + col].to_numpy()
            y = base[tgt].to_numpy()
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 500:
                continue
            qs = np.quantile(x[ok], np.linspace(0, 1, 11))
            qs[0] -= 1e-12
            idx = np.clip(np.searchsorted(qs, x[ok], side="right") - 1, 0, 9)
            means = [y[ok][idx == k].mean() * 100 for k in range(10)]
            hit = [(y[ok][idx == k] < -0.02).mean() * 100 for k in range(10)]
            print(f"  {col:11s} mean " + " ".join(f"{v:5.2f}" for v in means))
            print(f"  {'':11s} p<-2 " + " ".join(f"{v:5.1f}" for v in hit))

    print("\ncorr(feature d-1, next-day target):")
    for col in ["rv_pct", "dvol20", "range20", "rv_ratio", "vwap_dist", "dd_high",
                "last30", "rsi14", "sma20", "sma165", "decay20", "close_loc", "first30"]:
        x = base["f_" + col].to_numpy()
        out = []
        for tgt in ("gap", "intra", "tot", "ex_bil"):
            y = base[tgt].to_numpy()
            ok = np.isfinite(x) & np.isfinite(y)
            out.append(np.corrcoef(x[ok], y[ok])[0, 1])
        print(f"  {col:11s} " + " ".join(f"{v: .3f}" for v in out) + "   (gap intra tot ex_bil)")

    # conditional next-day stats on winner-held days only
    print("\n=== on winner-held days: next-day crash rate by prior feature quintile ===")
    for col in ["rv_pct", "dvol20", "range20", "vwap_dist", "dd_high", "last30", "rsi14",
                "sma20", "decay20"]:
        x = held["f_" + col].to_numpy()
        y = held["tot"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        qs = np.quantile(x[ok], np.linspace(0, 1, 6))
        qs[0] -= 1e-12
        idx = np.clip(np.searchsorted(qs, x[ok], side="right") - 1, 0, 4)
        means = [y[ok][idx == k].mean() * 100 for k in range(5)]
        crash = [(y[ok][idx == k] < -0.03).mean() * 100 for k in range(5)]
        print(f"  {col:11s} mean " + " ".join(f"{v:6.2f}" for v in means) +
              "   p<-3 " + " ".join(f"{v:5.1f}" for v in crash))


if __name__ == "__main__":
    main()
