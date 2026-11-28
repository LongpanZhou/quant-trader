"""Fifth exploration: clock speed x sign interaction, state machines, attribution."""
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
BPY = 252 * 390


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
    V = np.zeros((n, 390))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        V[k, :m] = vol[f:f + m]
    CUM = np.cumsum(V, axis=1)
    dayvol = V.sum(axis=1)
    med_day = np.full(n, np.nan)
    for k in range(n):
        if k >= 20:
            med_day[k] = np.median(dayvol[k - 20:k])
    return dates, np.asarray(first), np.asarray(last), V, CUM, dayvol, med_day


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V, CUM, dayvol, med_day = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)

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

    J75 = tol(0.75)
    J100 = tol(1.00)

    rows = []
    for k in range(20, n - 1):
        j = int(J75[k]) if np.isfinite(J75[k]) else -1
        if j <= 0:
            continue
        fk, lk = int(first[k]), int(last[k])
        m = min(lk - fk + 1, 390)
        cl = c[fk:fk + m, 0]
        v = V[k, :m]
        vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
        rr = np.diff(np.log(cl[:j + 1]))
        vv = v[1:j + 1]
        jhist = J75[max(0, k - 20):k]
        jmed = np.nanmedian(jhist) if np.isfinite(jhist).any() else np.nan
        fn = int(first[k + 1])
        rows.append(dict(
            k=k, date=dates[fk], j=j,
            speed=j - jmed if np.isfinite(jmed) else np.nan,
            fast=(j < jmed) if np.isfinite(jmed) else False,
            r_open=cl[j] / cl[0] - 1.0,
            vwapdev=cl[j] / vw - 1.0,
            vwret=float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0,
            to_next_open=o[fn, 1] / c[fk + j, 1] - 1.0,
            overnight=o[fn, 1] / c[lk, 1] - 1.0,
        ))
    df = pd.DataFrame(rows)
    print(f"x0.75 events {len(df)}; fast {df.fast.sum()}, slow {(~df.fast).sum()}")

    print("\n=== clock speed x sign(vwret) -> TQQQ decision-to-next-open (bp) ===")
    for fast in (True, False):
        for pos in (True, False):
            x = df.loc[(df.fast == fast) & ((df.vwret > 0) == pos), "to_next_open"]
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
            print(f"  {'fast' if fast else 'slow'} & vwret{'+' if pos else '-'}: "
                  f"n={len(x):4d} mean {x.mean()*1e4:7.2f}bp median {x.median()*1e4:7.2f}bp t={t:5.2f}")
    print("\n=== clock speed x sign(r_open) -> TQQQ decision-to-next-open (bp) ===")
    for fast in (True, False):
        for pos in (True, False):
            x = df.loc[(df.fast == fast) & ((df.r_open > 0) == pos), "to_next_open"]
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
            print(f"  {'fast' if fast else 'slow'} & r_open{'+' if pos else '-'}: "
                  f"n={len(x):4d} mean {x.mean()*1e4:7.2f}bp median {x.median()*1e4:7.2f}bp t={t:5.2f}")

    # ---------------- simulations ----------------
    print("\n=== simulations (1bp, 2% band) ===")

    def eval_w(w, label):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BPY)
        print(f"  {label:46s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
              f"Sh {s['sharpe']:4.2f} fills {s['fills']:5d} turnover {s['turnover']:7.0f} "
              f"TQQQbars {np.mean(w[:,1]>0)*100:4.1f}%")
        return s

    def overnight_from_mask(enter, label, col=1):
        """Enter at decision bar close, hold through the close, exit next open."""
        w = np.zeros((len(ts), 3))
        for k in range(n):
            if not enter[k] or k + 1 >= n:
                continue
            j = int(J75[k]) if np.isfinite(J75[k]) else -1
            if j <= 0:
                continue
            fk, lk = int(first[k]), int(last[k])
            w[fk + j, col] = 1.0
            w[fk + j + 1:lk + 1, col] = 1.0
            w[lk, col] = 0.0
        w[-1] = w[-2]
        return eval_w(w, label)

    # map dataframe rows to session k
    D = df.set_index("k")
    def m(cond):
        out = np.zeros(n, bool)
        for k in D.index:
            out[int(k)] = bool(cond(D.loc[k]))
        return out

    # baseline: overnight only
    w = np.zeros((len(ts), 3))
    for k in range(n - 1):
        fk, lk = int(first[k]), int(last[k])
        w[fk:lk - 1, 2] = 1.0
        w[lk - 1, 2] = 0.0
        w[lk - 1, 1] = 1.0
        w[lk, 1] = 0.0
        w[lk, 2] = 1.0
    w[-1] = w[-2]
    eval_w(w, "overnight-only TQQQ (every close->open)")

    # TQQQ buy hold
    wb = np.zeros((len(ts), 3)); wb[:, 1] = 1.0
    eval_w(wb, "TQQQ buy & hold")

    overnight_from_mask(m(lambda r: True), "x0.75 all events, overnight")
    overnight_from_mask(m(lambda r: r.vwret > 0), "x0.75 vwret>0, overnight")
    overnight_from_mask(m(lambda r: r.vwret > -0.001), "x0.75 vwret>-10bp, overnight")
    overnight_from_mask(m(lambda r: r.vwret > -0.002), "x0.75 vwret>-20bp, overnight")
    overnight_from_mask(m(lambda r: r.vwret > -0.003), "x0.75 vwret>-30bp, overnight")
    overnight_from_mask(m(lambda r: r.r_open > -0.001), "x0.75 r_open>-10bp, overnight")
    overnight_from_mask(m(lambda r: r.r_open > -0.002), "x0.75 r_open>-20bp, overnight")
    overnight_from_mask(m(lambda r: r.r_open > -0.003), "x0.75 r_open>-30bp, overnight")
    overnight_from_mask(m(lambda r: (~r.fast) & (r.vwret > 0)), "x0.75 slow & vwret>0, overnight")
    overnight_from_mask(m(lambda r: (~r.fast) & (r.vwret > -0.001)), "x0.75 slow & vwret>-10bp, overnight")
    overnight_from_mask(m(lambda r: (~r.fast) & (r.r_open > 0)), "x0.75 slow & r_open>0, overnight")
    overnight_from_mask(m(lambda r: (~r.fast) & (r.r_open > -0.002)), "x0.75 slow & r_open>-20bp, overnight")
    overnight_from_mask(m(lambda r: (r.fast) & (r.vwret > 0)), "x0.75 fast & vwret>0, overnight")
    overnight_from_mask(m(lambda r: (r.fast) & (r.vwret < 0)), "x0.75 fast & vwret<0, overnight")

    # default overnight long, BIL after condition
    print("\n--- default overnight TQQQ, skip after condition ---")
    def skip_mask(cond, label):
        skip = m(cond)
        enter = ~skip
        overnight_from_mask(enter, label)
        return skip
    skip_mask(lambda r: r.fast, "skip after fast clock")
    skip_mask(lambda r: r.fast & (r.vwret < 0), "skip after fast & vwret<0")
    skip_mask(lambda r: r.fast & (r.vwret > 0), "skip after fast & vwret>0")
    skip_mask(lambda r: r.vwret < -0.002, "skip after vwret<-20bp")
    skip_mask(lambda r: (r.fast) & (r.vwret < -0.001), "skip after fast & vwret<-10bp")

    # daily fast-clock skip, all-day TQQQ (from prior exploration) for reference
    print("\n--- daily fast-clock skip, all-day TQQQ ---")
    w = np.zeros((len(ts), 3))
    for k in range(n):
        fk, lk = int(first[k]), int(last[k])
        prev_fast = bool(J100[k - 1] < 240) if k > 0 and np.isfinite(J100[k - 1]) else False
        if prev_fast:
            w[fk:lk, 2] = 1.0
        else:
            w[fk:lk, 1] = 1.0
    w[-1] = w[-2]
    eval_w(w, "all-day, BIL after fast clock (prior day)")


if __name__ == "__main__":
    main()
