"""Exploratory feature inspection for the volume-clock family.

Development window only (2016-01-04 .. 2023-12-29).  No holdout data.
This script is not the final strategy; it prints conditional forward returns
for candidate volume-clock states so the pre-registered centre can be chosen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")


def load_all():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = df["volume"].to_numpy(dtype=float)
    vol = np.nan_to_num(vol, nan=0.0)
    return ts, o, c, vol


def session_matrices(ts, o, c, vol):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    OFF = 390
    V = np.zeros((n, OFF))
    CL = np.full((n, OFF), np.nan)
    OP = np.full((n, OFF), np.nan)
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, OFF)
        V[k, :m] = vol[f:f + m]
        CL[k, :m] = c[f:f + m, 0]
        OP[k, :m] = o[f:f + m, 0]
    # per-bar typical price = close approximation for VWAP
    CUM = np.cumsum(V, axis=1)
    return dates, first, last, V, CL, OP, CUM


def med_prior(X, k, win=20):
    a = max(0, k - win)
    if k == 0:
        return np.nan
    return float(np.nanmedian(X[a:k]))


def conditional(label, x, y, n_min=30):
    """x: signal (bool or float), y: forward return. Prints mean bp, t."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(y) == 0:
        print(f"  {label:44s} n=0")
        return
    if x.dtype == bool or set(np.unique(x)).issubset({0.0, 1.0}):
        a, b = y[x > 0], y[x <= 0]
        if len(a) >= n_min and len(b) >= n_min:
            t = (a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            print(f"  {label:44s} hi n={len(a):4d} {a.mean()*1e4:7.2f}bp  "
                  f"lo n={len(b):4d} {b.mean()*1e4:7.2f}bp  diff t={t:5.2f}")
        else:
            print(f"  {label:44s} n_hi={len(a)} n_lo={len(b)} (thin)")
    else:
        q = pd.qcut(pd.Series(x), 5, labels=False, duplicates="drop")
        rows = []
        for g in sorted(pd.Series(q).dropna().unique()):
            yy = y[q == g]
            rows.append(f"q{int(g)} n={len(yy):4d} {yy.mean()*1e4:7.2f}bp")
        print(f"  {label:44s} " + " | ".join(rows))


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V, CL, OP, CUM = session_matrices(ts, o, c, vol)
    n = len(first)
    dayvol = V.sum(axis=1)
    print(f"sessions {n}, bars {len(ts)}, {dates[0]} .. {dates[-1]}")
    print(f"median daily volume {np.median(dayvol):,.0f}; zero-vol bars {np.mean(vol == 0)*100:.2f}%")

    # TQQQ returns aligned to the same session offsets
    T = np.full((n, 390), np.nan)
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        T[k, :m] = c[f:f + m, 1]

    # median full-day volume over prior 20 sessions, and median time-to-level
    med_day = np.full(n, np.nan)
    for k in range(n):
        med_day[k] = med_prior(dayvol, k)

    levels = [0.40, 0.50, 0.60, 0.75, 1.00, 1.25]
    print("\n=== A. volume-clock level: cumulative volume >= x * prior-20 median day ===")
    for x in levels:
        rows = []
        for k in range(20, n):
            if not np.isfinite(med_day[k]) or med_day[k] <= 0:
                continue
            tgt = x * med_day[k]
            j = int(np.searchsorted(CUM[k], tgt))
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 2 or j < 1:
                continue
            f = int(first[k])
            rows.append((k, j, m))
        print(f"\nlevel {x:.2f}: {len(rows)} decisions")
        # features at decision
        rec = []
        for k, j, m in rows:
            f = int(first[k])
            px = CL[k, j]
            vw = np.sum(V[k, :j + 1] * CL[k, :j + 1]) / max(np.sum(V[k, :j + 1]), 1)
            r_open = px / OP[k, 0] - 1.0
            vwapdev = px / vw - 1.0
            rr = np.diff(np.log(CL[k, :j + 1]))
            vv = V[k, 1:j + 1]
            vwret = float(np.sum(rr * vv) / max(vv.sum(), 1))
            # forward returns
            fwd_q = CL[k, m - 1] / px - 1.0
            fwd_t = T[k, m - 1] / T[k, j] - 1.0
            # next session open/close
            if k + 1 < n:
                fn = int(first[k + 1])
                fwd_t_no = o[fn, 1] / T[k, j] - 1.0
                ln = int(last[k + 1])
                fwd_t_nc = c[ln, 1] / T[k, j] - 1.0
                night_q = o[fn, 0] / CL[k, m - 1] - 1.0
            else:
                fwd_t_no = fwd_t_nc = night_q = np.nan
            rec.append((k, j, r_open, vwapdev, vwret, fwd_q, fwd_t,
                        fwd_t_no, fwd_t_nc, night_q, m))
        A = np.array(rec, float)
        # sign of each feature
        for name, col in (("r_open", 2), ("vwap_dev", 3), ("vw_ret", 4)):
            conditional(f"{name} sign -> QQQ to close", (A[:, col] > 0).astype(float),
                        A[:, 5])
            conditional(f"{name} sign -> TQQQ to close", (A[:, col] > 0).astype(float),
                        A[:, 6])
            conditional(f"{name} sign -> TQQQ next close", (A[:, col] > 0).astype(float),
                        A[:, 8])
        # speed of the clock: decision offset relative to prior-20 median offset
        spd = np.full(len(A), np.nan)
        for i, (k, j, *_rest) in enumerate(rec):
            js = []
            for kk in range(max(0, int(k) - 20), int(k)):
                mm = min(int(last[kk]) - int(first[kk]) + 1, 390)
                tgt = x * med_day[kk]
                if np.isfinite(tgt):
                    jj = int(np.searchsorted(CUM[kk], tgt))
                    if 0 < jj < mm:
                        js.append(jj)
            if len(js) >= 10:
                spd[i] = j - np.median(js)
        conditional("fast clock (j < prior-20 median) -> TQQQ to close",
                    (spd < 0).astype(float), A[:, 6])
        conditional("fast clock -> TQQQ next close", (spd < 0).astype(float), A[:, 8])
        # joint: fast clock and positive vwap dev
        conditional("fast & vwap_dev>0 -> TQQQ to close",
                    ((spd < 0) & (A[:, 3] > 0)).astype(float), A[:, 6])
        conditional("fast & vwap_dev>0 -> TQQQ next close",
                    ((spd < 0) & (A[:, 3] > 0)).astype(float), A[:, 8])
        conditional("slow & vwap_dev<0 -> TQQQ to close",
                    ((spd >= 0) & (A[:, 3] < 0)).astype(float), A[:, 6])

    # B. fixed-time 30-min volume acceleration
    print("\n\n=== B. 30-min volume acceleration vs same-window prior-20 median ===")
    OFF = [60, 120, 180, 240, 300, 330]
    for j in OFF:
        rec = []
        for k in range(20, n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j >= m - 2:
                continue
            win = V[k, j - 29:j + 1].sum()
            hist = [V[kk, j - 29:j + 1].sum() for kk in range(k - 20, k)]
            med = np.median(hist)
            if med <= 0:
                continue
            acc = win / med
            # same-window volume-synchronized return
            rr = np.diff(np.log(CL[k, j - 29:j + 1]))
            vv = V[k, j - 29 + 1:j + 1]
            vwret30 = float(np.sum(rr * vv) / max(vv.sum(), 1))
            vw = np.sum(V[k, :j + 1] * CL[k, :j + 1]) / max(np.sum(V[k, :j + 1]), 1)
            vwapdev = CL[k, j] / vw - 1.0
            fwd_t = T[k, m - 1] / T[k, j] - 1.0
            if k + 1 < n:
                fwd_t_nc = c[int(last[k + 1]), 1] / T[k, j] - 1.0
            else:
                fwd_t_nc = np.nan
            rec.append((acc, vwret30, vwapdev, fwd_t, fwd_t_nc))
        A = np.array(rec, float)
        conditional(f"{j//60+9:02d}:00 accel quintile -> TQQQ to close",
                    A[:, 0], A[:, 3])
        conditional(f"{j//60+9:02d}:00 accel>1.3 -> TQQQ to close",
                    (A[:, 0] > 1.3).astype(float), A[:, 3])
        conditional(f"{j//60+9:02d}:00 accel>1.3 & vwret30>0 -> TQQQ to close",
                    ((A[:, 0] > 1.3) & (A[:, 1] > 0)).astype(float), A[:, 3])
        conditional(f"{j//60+9:02d}:00 accel>1.3 & vwapdev>0 -> TQQQ to close",
                    ((A[:, 0] > 1.3) & (A[:, 2] > 0)).astype(float), A[:, 3])
        conditional(f"{j//60+9:02d}:00 accel>1.3 & vwapdev>0 -> TQQQ next close",
                    ((A[:, 0] > 1.3) & (A[:, 2] > 0)).astype(float), A[:, 4])


if __name__ == "__main__":
    main()
