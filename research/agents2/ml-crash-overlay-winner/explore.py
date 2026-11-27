"""Exploration: causal daily features from 1m bars + crash-label diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2026-10-23"


def daily_from_1m(ts, o, c, v):
    """Per-session aggregates / intraday features from 1-minute bars."""
    dates = np.array([t.date() for t in ts])
    bounds = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    bounds = np.r_[bounds, len(dates)]
    rows = []
    for j in range(len(bounds) - 1):
        a, b = bounds[j], bounds[j + 1]
        qo = o[a:b, 0]
        qc = c[a:b, 0]
        qv = v[a:b, 0]
        lr = np.diff(np.log(qc))
        hi = np.maximum.accumulate(qc)
        vwap = float(np.sum(qc * qv) / max(np.sum(qv), 1e-9))
        mu = lr.mean() if len(lr) else 0.0
        sd = lr.std(ddof=0) if len(lr) else 0.0
        sk = float(np.mean(((lr - mu) / sd) ** 3)) if sd > 0 else 0.0
        k30 = min(30, len(qc) - 1)
        rows.append({
            "date": dates[a],
            "qo": qo[0], "qc": qc[-1], "qh": qc.max(), "ql": qc.min(),
            "qv": float(qv.sum()),
            "rv1": float(sd),
            "skew1": sk,
            "dvol": float(np.sqrt(np.mean(np.minimum(lr, 0.0) ** 2))) if len(lr) else 0.0,
            "vwap": vwap,
            "dd_high": float(qc[-1] / qc.max() - 1.0),
            "first30": float(qc[k30] / qo[0] - 1.0) if len(qc) > 1 else 0.0,
            "last30": float(qc[-1] / qc[max(0, len(qc) - 31)] - 1.0) if len(qc) > 1 else 0.0,
            "close_loc": float((qc[-1] - qc.min()) / max(qc.max() - qc.min(), 1e-9)),
        })
    df = pd.DataFrame(rows).set_index("date")
    return df


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    # volume is not returned by panel; reload raw QQQ minute frame once
    print("panel", len(ts), "bars")
    raw = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts).fillna(0.0).to_numpy()
    vol = np.column_stack([raw, raw, raw])
    dd = daily_from_1m(ts, o, c, vol)

    # daily closes from minute bars, minute-derived daily series
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    dclose = c[last]
    dopen = o[first]
    q = pd.Series(dclose[:, 0], index=pd.Index(dd.index))
    t = pd.Series(dclose[:, 1], index=pd.Index(dd.index))
    b = pd.Series(dclose[:, 2], index=pd.Index(dd.index))
    qo = pd.Series(dopen[:, 0], index=pd.Index(dd.index))

    f = pd.DataFrame(index=q.index)
    lr = np.log(q / q.shift(1))
    for k in (1, 2, 5, 10, 20, 60):
        f[f"r{k}"] = np.log(q / q.shift(k))
    f["rv1"] = dd["rv1"]
    f["rv5"] = dd["rv1"].rolling(5).mean()
    f["rv20"] = dd["rv1"].rolling(20).mean()
    f["rv60"] = dd["rv1"].rolling(60).mean()
    f["rv_ratio"] = f["rv5"] / f["rv60"]
    f["rv_pct"] = f["rv5"].rolling(252, min_periods=100).rank(pct=True)
    f["skew1"] = dd["skew1"]
    f["skew20"] = dd["skew1"].rolling(20).mean()
    f["dvol"] = dd["dvol"]
    f["dvol20"] = dd["dvol"].rolling(20).mean()
    f["vwap_dist"] = q / dd["vwap"] - 1.0
    f["dd_high"] = dd["dd_high"]
    f["first30"] = dd["first30"]
    f["last30"] = dd["last30"]
    f["close_loc"] = dd["close_loc"]
    f["gap"] = qo / q.shift(1) - 1.0
    f["intraday"] = q / qo - 1.0
    f["gap20"] = f["gap"].rolling(20).mean()
    f["up20"] = (lr > 0).rolling(20).mean() - 0.5
    f["dd20"] = q / q.rolling(20).max() - 1.0
    f["dd252"] = q / q.rolling(252, min_periods=100).max() - 1.0
    f["sma20"] = q / q.rolling(20).mean() - 1.0
    f["sma165"] = q / q.rolling(165, min_periods=100).mean() - 1.0
    delta = q.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    f["decay5"] = np.log(t / t.shift(5)) - 3.0 * np.log(q / q.shift(5))
    f["decay20"] = np.log(t / t.shift(20)) - 3.0 * np.log(q / q.shift(20))
    f["bil5"] = np.log(b / b.shift(5))
    f["dow"] = pd.Series(q.index, index=q.index).apply(lambda x: x.weekday()).astype(float) / 4 - 0.5
    f["range"] = (dd["qh"] / dd["ql"] - 1.0)
    f["range20"] = f["range"].rolling(20).mean()
    f["vol_ratio"] = dd["qv"] / dd["qv"].rolling(20).mean()
    f["vol_z20"] = (dd["qv"] - dd["qv"].rolling(20).mean()) / dd["qv"].rolling(20).std(ddof=0)
    f["rv_x_trend"] = f["rv_ratio"] * f["sma20"]
    f["skew_x_dd"] = f["skew1"] * f["dd_high"]

    # labels (decided at close of day d, return measured next session onward)
    tq = t.to_numpy()
    bl = b.to_numpy()
    ret1 = np.r_[np.nan, np.log(tq[1:] / tq[:-1])]
    fut1 = np.r_[np.log(tq[1:] / tq[:-1]), np.nan]
    fut5 = np.full(len(tq), np.nan)
    fut5[:-5] = np.log(tq[5:] / tq[:-5])
    fut5b = np.full(len(bl), np.nan)
    fut5b[:-5] = np.log(bl[5:] / bl[:-5])
    y1 = (fut1 < -0.03).astype(float)
    y1[np.isnan(fut1)] = np.nan
    y2 = (fut1 < -0.045).astype(float)
    y2[np.isnan(fut1)] = np.nan
    y5 = (fut5 < fut5b).astype(float)
    y5[np.isnan(fut5)] = np.nan
    yneg = (fut1 < 0).astype(float)
    yneg[np.isnan(fut1)] = np.nan

    print("\nlabel base rates (2017+):")
    m = np.array(q.index >= pd.Timestamp("2017-01-03").date())
    for name, y in (("crash3", y1), ("crash4.5", y2), ("neg1", yneg), ("under5", y5)):
        print(f"  {name}: {np.nanmean(y[m]):.3f}  n={int(np.isfinite(y[m]).sum())}")

    print("\nunivariate crash3 rate by decile (2017+, each feature):")
    for col in ["rv_ratio", "rv_pct", "skew1", "skew20", "vwap_dist", "dd_high", "gap",
                "intraday", "last30", "close_loc", "dd20", "sma20", "sma165", "rsi14",
                "decay5", "decay20", "range", "range20", "dvol20", "rv1", "first30",
                "rv_x_trend", "skew_x_dd", "up20"]:
        x = f[col].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y1) & m
        if ok.sum() < 500:
            continue
        qs = np.quantile(x[ok], np.linspace(0, 1, 11))
        qs[0] -= 1e-12
        idx = np.clip(np.searchsorted(qs, x[ok], side="right") - 1, 0, 9)
        rates = [y1[ok][idx == k].mean() for k in range(10)]
        print(f"  {col:12s} " + " ".join(f"{v*100:4.1f}" for v in rates))

    print("\ncorrelation with next-day TQQQ return:")
    for col in ["rv_ratio", "rv_pct", "skew1", "skew20", "vwap_dist", "dd_high", "gap",
                "intraday", "last30", "close_loc", "dd20", "sma20", "sma165", "rsi14",
                "decay5", "range", "rv1", "dvol20"]:
        x = f[col].to_numpy()
        ok = np.isfinite(x) & np.isfinite(fut1) & m
        print(f"  {col:12s} corr={np.corrcoef(x[ok], fut1[ok])[0,1]: .3f}")

    print("\ncorrelation with next-5d TQQQ-minus-BIL:")
    ex5 = fut5 - fut5b
    for col in ["rv_ratio", "rv_pct", "skew1", "skew20", "vwap_dist", "dd_high", "gap",
                "intraday", "last30", "close_loc", "dd20", "sma20", "sma165", "rsi14",
                "decay5", "range", "rv1", "dvol20"]:
        x = f[col].to_numpy()
        ok = np.isfinite(x) & np.isfinite(ex5) & m
        print(f"  {col:12s} corr={np.corrcoef(x[ok], ex5[ok])[0,1]: .3f}")

    f.to_pickle(Path(__file__).parent / "features.pkl")
    print("\nsaved features", f.shape)


if __name__ == "__main__":
    main()
