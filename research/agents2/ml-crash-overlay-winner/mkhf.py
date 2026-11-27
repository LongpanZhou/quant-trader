"""Build 15:50 daily features and test overnight-gap predictability."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from proto import walk_forward  # noqa: E402

START, END = "2017-01-03", "2026-10-23"


def daily_cut(ts, o, c, v, cutoff):
    """Per-session features using bars up to `cutoff` (e.g. 15:50)."""
    times = ts.time
    dates = np.array([t.date() for t in ts])
    rows = []
    firsts, lasts_cut, opens931 = [], [], []
    for d in np.unique(dates):
        idx = np.flatnonzero(dates == d)
        idx_cut = idx[times[idx] <= cutoff]
        if len(idx_cut) < 30:
            continue
        a, b = idx[0], idx_cut[-1]
        qo = o[a:b + 1, 0]; qc = c[a:b + 1, 0]; qv = v[a:b + 1, 0]
        lr = np.diff(np.log(qc))
        mu = lr.mean() if len(lr) else 0.0
        sd = lr.std(ddof=0) if len(lr) else 0.0
        sk = float(np.mean(((lr - mu) / sd) ** 3)) if sd > 0 else 0.0
        vwap = float(np.sum(qc * qv) / max(np.sum(qv), 1e-9))
        k30 = min(30, len(qc) - 1)
        rows.append({
            "date": d, "qc": qc[-1], "qo": qo[0], "qh": qc.max(), "ql": qc.min(),
            "tc": c[b, 1], "bc": c[b, 2],
            "qv": float(qv.sum()), "rv1": float(sd), "skew1": sk,
            "dvol": float(np.sqrt(np.mean(np.minimum(lr, 0.0) ** 2))) if len(lr) else 0.0,
            "vwap": vwap, "dd_high": float(qc[-1] / qc.max() - 1.0),
            "first30": float(qc[k30] / qo[0] - 1.0),
            "last30": float(qc[-1] / qc[max(0, len(qc) - 31)] - 1.0),
            "close_loc": float((qc[-1] - qc.min()) / max(qc.max() - qc.min(), 1e-9)),
            "range": float(qc.max() / qc.min() - 1.0),
        })
        firsts.append(a)
    df = pd.DataFrame(rows).set_index("date")
    return df


def build(ts, o, c, v):
    d = daily_cut(ts, o, c, v, pd.Timestamp("15:50").time())
    q = pd.Series(d["qc"].to_numpy(), index=pd.DatetimeIndex(d.index))
    qo = pd.Series(d["qo"].to_numpy(), index=q.index)
    f = pd.DataFrame(index=q.index)
    lr = np.log(q / q.shift(1))
    for k in (1, 2, 5, 10, 20, 60):
        f[f"r{k}"] = np.log(q / q.shift(k))
    f["rv1"] = d["rv1"]
    f["rv5"] = d["rv1"].rolling(5).mean()
    f["rv20"] = d["rv1"].rolling(20).mean()
    f["rv60"] = d["rv1"].rolling(60).mean()
    f["rv_ratio"] = f["rv5"] / f["rv60"]
    f["rv_pct"] = f["rv5"].rolling(252, min_periods=100).rank(pct=True)
    f["skew1"] = d["skew1"]
    f["skew20"] = d["skew1"].rolling(20).mean()
    f["dvol"] = d["dvol"]
    f["dvol20"] = d["dvol"].rolling(20).mean()
    f["vwap_dist"] = q / d["vwap"] - 1.0
    f["dd_high"] = d["dd_high"]
    f["first30"] = d["first30"]
    f["last30"] = d["last30"]
    f["close_loc"] = d["close_loc"]
    f["gap"] = qo / q.shift(1) - 1.0
    f["gap20"] = f["gap"].rolling(20).mean()
    f["intraday"] = q / qo - 1.0
    f["up20"] = (lr > 0).rolling(20).mean() - 0.5
    f["dd20"] = q / q.rolling(20).max() - 1.0
    f["dd252"] = q / q.rolling(252, min_periods=100).max() - 1.0
    f["sma20"] = q / q.rolling(20).mean() - 1.0
    f["sma165"] = q / q.rolling(165, min_periods=100).mean() - 1.0
    delta = q.diff(); up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    dn = (-delta).clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    f["rsi14"] = (100 - 100 / (1 + up / dn.clip(lower=1e-12))) / 100 - 0.5
    t = pd.Series(d["tc"].to_numpy(), index=q.index)
    b = pd.Series(d["bc"].to_numpy(), index=q.index)
    f["decay5"] = np.log(t / t.shift(5)) - 3.0 * np.log(q / q.shift(5))
    f["decay20"] = np.log(t / t.shift(20)) - 3.0 * np.log(q / q.shift(20))
    f["bil5"] = np.log(b / b.shift(5))
    f["dow"] = pd.Series(q.index, index=q.index).apply(lambda x: x.weekday()).astype(float) / 4 - 0.5
    f["range"] = d["range"]
    f["range20"] = f["range"].rolling(20).mean()
    f["vol_ratio"] = d["qv"] / d["qv"].rolling(20).mean()
    f["vol_z20"] = (d["qv"] - d["qv"].rolling(20).mean()) / d["qv"].rolling(20).std(ddof=0)
    return f, d


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    raw = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts).fillna(0.0).to_numpy()
    v = np.column_stack([raw, raw, raw])
    f, d = build(ts, o, c, v)
    print("features", f.shape)
    f.to_pickle(Path(__file__).parent / "features1550.pkl")

    # label: TQQQ return from 15:50 close of d to 09:31 open of d+1
    times = ts.time
    dates = np.array([t.date() for t in ts])
    day_idx = {}
    for d0 in np.unique(dates):
        idx = np.flatnonzero(dates == d0)
        day_idx[d0] = idx
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in d.index])
    tq = pd.Series(c[:, 1], index=ts)
    tqo = pd.Series(o[:, 1], index=ts)
    lab = []
    for k, dt in enumerate(d.index):
        if k + 1 >= len(d.index):
            lab.append(np.nan); continue
        nxt = d.index[k + 1]
        idx = day_idx[nxt]
        t931 = idx[times[idx] >= pd.Timestamp("09:31").time()][0]
        lab.append(np.log(tqo.iloc[t931] / d["tc"].iloc[k]))
    lab = np.array(lab)

    for thr in (-0.01, -0.015, -0.02):
        y = (lab < thr).astype(float); y[~np.isfinite(lab)] = np.nan
        x = f.to_numpy()
        p = walk_forward(dts, x, y, 1)
        print(f"\ngap label < {thr}: base {np.nanmean(y[dts>=pd.Timestamp('2017-01-03')]):.3f}")
        for yr in range(2017, 2027):
            m = np.isfinite(p) & np.isfinite(y) & (dts.year == yr)
            if m.sum() < 40:
                continue
            pp, yy = p[m], y[m]
            pos, neg = pp[yy == 1], pp[yy == 0]
            auc = ((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)) if len(pos) and len(neg) else np.nan
            print(f"  {yr}: n={m.sum()} base={yy.mean():.2f} AUC={auc:.3f}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
