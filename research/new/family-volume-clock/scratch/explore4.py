"""Fourth exploration: decompose the volume-clock event signal.

For each session, at the first minute cumulative QQQ volume reaches x times the
prior-20-session median full-day volume, measure:
  - r_open, vwap deviation, volume-weighted return, clock speed, 30m accel
and the forward returns:
  - decision -> session close (intraday remainder)
  - close -> next open (overnight)
  - decision -> next open
  - decision -> next close
Development window only.
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


def load_all():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)
    return ts, o, c, vol


def prep(ts, o, c, vol):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    OFF = 390
    V = np.zeros((n, OFF))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, OFF)
        V[k, :m] = vol[f:f + m]
    CUM = np.cumsum(V, axis=1)
    dayvol = V.sum(axis=1)
    med_day = np.full(n, np.nan)
    for k in range(n):
        if k >= 20:
            med_day[k] = np.median(dayvol[k - 20:k])
    return dates, np.asarray(first), np.asarray(last), V, CUM, dayvol, med_day


def qtable(df, col, ycol, q=5):
    d = df[[col, ycol]].dropna().copy()
    d["q"] = pd.qcut(d[col], q, labels=False, duplicates="drop")
    g = d.groupby("q")[ycol]
    out = pd.DataFrame({"n": g.count(), "mean_bp": g.mean() * 1e4,
                        "median_bp": g.median() * 1e4,
                        "t": g.apply(lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))})
    return out.round(2)


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V, CUM, dayvol, med_day = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)

    # time-to-level for each session
    def tol(x):
        arr = np.full(n, np.nan)
        for k in range(n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            tgt = x * med_day[k] if np.isfinite(med_day[k]) else np.nan
            if np.isfinite(tgt) and tgt > 0:
                j = int(np.searchsorted(CUM[k, :m], tgt))
                if 0 < j < m - 1:
                    arr[k] = j
        return arr

    for x in (0.50, 0.60, 0.75):
        J = tol(x)
        rows = []
        for k in range(20, n - 1):
            j = int(J[k]) if np.isfinite(J[k]) else -1
            if j <= 0:
                continue
            fk, lk = int(first[k]), int(last[k])
            m = min(lk - fk + 1, 390)
            cl = c[fk:fk + m, 0]
            v = V[k, :m]
            vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
            rr = np.diff(np.log(cl[:j + 1]))
            vv = v[1:j + 1]
            # same-time-of-day 20d median of last-30m volume
            w0 = max(0, j - 29)
            hist = [V[kk, w0:j + 1].sum() for kk in range(max(0, k - 20), k)]
            acc = (v[w0:j + 1].sum() / np.median(hist)) if len(hist) and np.median(hist) > 0 else np.nan
            # prior-20 median time to x
            jhist = J[max(0, k - 20):k]
            jmed = np.nanmedian(jhist) if np.isfinite(jhist).any() else np.nan
            fn, ln = int(first[k + 1]), int(last[k + 1])
            rows.append(dict(
                k=k, date=dates[fk], j=j,
                r_open=cl[j] / cl[0] - 1.0,
                vwapdev=cl[j] / vw - 1.0,
                vwret=float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0,
                accel=acc,
                speed=j - jmed if np.isfinite(jmed) else np.nan,
                rem_intraday=c[lk, 1] / c[fk + j, 1] - 1.0,
                overnight=o[fn, 1] / c[lk, 1] - 1.0,
                to_next_open=o[fn, 1] / c[fk + j, 1] - 1.0,
                to_next_close=c[ln, 1] / c[fk + j, 1] - 1.0,
            ))
        df = pd.DataFrame(rows)
        print(f"\n{'='*78}\nlevel {x:.2f}: {len(df)} events, "
              f"median decision {np.median(df.j):.0f} min after open")
        for col in ("r_open", "vwapdev", "vwret", "accel", "speed"):
            print(f"\n-- {col} quintiles --")
            for y in ("rem_intraday", "overnight", "to_next_open", "to_next_close"):
                print(qtable(df, col, y).to_string())
                print()

    # unconditional benchmarks: every session, measure from a fixed midday time
    print(f"\n{'='*78}\nUnconditional baselines (all sessions)")
    for jfix in (150, 180, 210, 240, 270, 300, 330):
        rem, on, tno, tnc = [], [], [], []
        for k in range(20, n - 1):
            fk, lk = int(first[k]), int(last[k])
            m = min(lk - fk + 1, 390)
            if jfix >= m - 1:
                continue
            fn, ln = int(first[k + 1]), int(last[k + 1])
            rem.append(c[lk, 1] / c[fk + jfix, 1] - 1.0)
            on.append(o[fn, 1] / c[lk, 1] - 1.0)
            tno.append(o[fn, 1] / c[fk + jfix, 1] - 1.0)
            tnc.append(c[ln, 1] / c[fk + jfix, 1] - 1.0)
        def st(v):
            v = np.array(v)
            return f"mean {v.mean()*1e4:7.2f}bp t={v.mean()/(v.std(ddof=1)/np.sqrt(len(v))):5.2f}"
        print(f"  j={jfix:3d} ({9+ (30+jfix)//60:02d}:{(30+jfix)%60:02d}) "
              f"rem {st(rem)} | overnight {st(on)} | to_open {st(tno)} | to_nextclose {st(tnc)}")


if __name__ == "__main__":
    main()
