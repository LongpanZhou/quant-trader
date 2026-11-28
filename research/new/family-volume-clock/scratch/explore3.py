"""Third exploration: fixed intraday grid + daily clock-state diagnostics."""
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


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V, CUM, dayvol, med_day = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)

    # ---------- daily filter diagnostics ----------
    j100 = np.full(n, np.nan)
    j50 = np.full(n, np.nan)
    for k in range(n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        tgt = med_day[k]
        if not np.isfinite(tgt) or tgt <= 0:
            continue
        a = int(np.searchsorted(CUM[k, :m], 0.5 * tgt))
        b = int(np.searchsorted(CUM[k, :m], tgt))
        if 0 < a < m - 1:
            j50[k] = a
        if 0 < b < m - 1:
            j100[k] = b
    dn = np.full(n, np.nan)
    dn[1:] = c[last[1:], 1] / c[last[:-1], 1] - 1.0

    print("=== 'fast clock' (j100 < 240, i.e. 100% of median volume by 13:30) ===")
    fast = np.isfinite(j100) & (j100 < 240)
    print(f"fast days {fast.sum()} / {np.isfinite(j100).sum()} completed; "
          f"share of all {fast.mean()*100:.1f}%")
    print(f"P(next-day TQQQ < 0 | fast) = {np.nanmean(dn[1:][fast[:-1]] < 0):.3f}")
    print(f"P(next-day TQQQ < 0 | not fast) = {np.nanmean(dn[1:][~fast[:-1]] < 0):.3f}")
    for lab, mask in (("fast", fast), ("not fast", ~fast)):
        x = dn[1:][mask[:-1]]
        x = x[np.isfinite(x)]
        print(f"  {lab:9s} n={len(x):4d} mean {x.mean()*1e4:7.2f}bp "
              f"median {np.median(x)*1e4:7.2f}bp t={x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):5.2f}")
    # worst next days
    order = np.argsort(dn)[:15]
    print("worst next-day TQQQ returns and prior-day clock:")
    for k in order:
        print(f"  {dates[first[k]]} {dn[k]*100:7.2f}%  prior j100={j100[k-1] if k else np.nan:6.1f} "
              f"prior rvol={dayvol[k-1]/med_day[k-1] if k and np.isfinite(med_day[k-1]) else np.nan:5.2f}")
    # best next days
    order = np.argsort(dn)[-8:]
    print("best next-day TQQQ returns and prior-day clock:")
    for k in order:
        print(f"  {dates[first[k]]} {dn[k]*100:7.2f}%  prior j100={j100[k-1] if k else np.nan:6.1f} "
              f"prior rvol={dayvol[k-1]/med_day[k-1] if k and np.isfinite(med_day[k-1]) else np.nan:5.2f}")

    # yearly breakdown of fast-day avoidance
    print("\nfast-day count by year:", {y: int(np.sum(fast[np.array([d.year for d in dates[first]]) == y]))
                                          for y in range(2016, 2024)})

    # ---------- fixed intraday grid ----------
    print("\n=== fixed intraday grid ===")
    feats = {}
    for x in (0.4, 0.5, 0.6, 0.75, 1.0):
        arr = np.full(n, -1)
        for k in range(n):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            tgt = x * med_day[k] if np.isfinite(med_day[k]) else np.nan
            if np.isfinite(tgt) and tgt > 0:
                j = int(np.searchsorted(CUM[k, :m], tgt))
                if 0 < j < m - 1:
                    arr[k] = j
        feats[x] = arr

    sig = {}
    for x in feats:
        for k in range(n):
            j = int(feats[x][k])
            if j <= 0:
                continue
            fk = int(first[k]); m = min(int(last[k]) - fk + 1, 390)
            cl = c[fk:fk + m, 0]
            v = V[k, :m]
            vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
            rr = np.diff(np.log(cl[:j + 1]))
            vv = v[1:j + 1]
            sig[(x, k)] = dict(
                vwapdev=cl[j] / vw - 1.0,
                r_open=cl[j] / cl[0] - 1.0,
                vwret=float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0,
            )

    def make_w(x, sk, dead, hold, mode):
        w = np.zeros((len(ts), 3))
        for k in range(n):
            j = int(feats[x][k])
            if j <= 0 or (x, k) not in sig:
                continue
            val = sig[(x, k)][sk]
            allow = val > dead if mode == "long_when_pos" else not (val < -dead)
            if not allow:
                continue
            fk, lk = int(first[k]), int(last[k])
            en = min(fk + j + 1, lk)
            w[fk + j, 1] = 1.0
            if hold == "intraday":
                w[en:lk, 1] = 1.0
                w[lk - 1, 1] = 0.0
            elif hold == "overnight":
                w[en:lk + 1, 1] = 1.0
                w[lk, 1] = 0.0
            elif hold == "next_close":
                if k + 1 < n:
                    fn, ln = int(first[k + 1]), int(last[k + 1])
                    w[en:ln, 1] = 1.0
                    w[ln - 1, 1] = 0.0
        w[-1] = w[-2]
        return w

    def ev(w):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BPY)
        return s

    out = []
    for x in (0.5, 0.6, 0.75):
        for sk in ("vwapdev", "r_open", "vwret"):
            for dead in (0.0, 0.001, 0.002):
                for hold in ("intraday", "overnight", "next_close"):
                    for mode in ("long_when_pos", "avoid_neg"):
                        s = ev(make_w(x, sk, dead, hold, mode))
                        out.append((s["sharpe"], s["cagr"], x, sk, dead, hold, mode,
                                    s["max_drawdown"], s["fills"], s["turnover"],
                                    np.mean(make_w(x, sk, dead, hold, mode)[:, 1] > 0)))
    out.sort(reverse=True)
    print("top 30 by Sharpe:")
    for row in out[:30]:
        sh, cagr, x, sk, dead, hold, mode, dd, fills, to, expo = row
        print(f"x{x:.2f} {sk:7s} d{dead*1e4:4.0f}bp {hold:10s} {mode:13s} "
              f"CAGR {cagr*100:6.2f}% DD {dd*100:5.1f}% Sh {sh:4.2f} "
              f"fills {fills:5d} expo {expo*100:4.1f}%")

    # ---------- daily clock state as a long-only timing signal ----------
    print("\n=== daily clock-state timing (TQQQ next day if condition on prior close) ===")
    # precompute daily features
    vwapdev = np.full(n, np.nan); vwret = np.full(n, np.nan); rvol = dayvol / med_day
    for k in range(n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        cl = c[int(first[k]):int(first[k]) + m, 0]
        v = V[k, :m]
        vw = np.sum(v * cl) / max(v.sum(), 1)
        vwapdev[k] = cl[-1] / vw - 1.0
        rr = np.diff(np.log(cl)); vv = v[1:]
        vwret[k] = float(np.sum(rr * vv) / max(vv.sum(), 1))

    def daily_mask_w(long_mask):
        w = np.zeros((len(ts), 3))
        for k in range(n):
            fk, lk = int(first[k]), int(last[k])
            if long_mask[k]:
                w[fk:lk, 1] = 1.0
            else:
                w[fk:lk, 2] = 1.0
        w[-1] = w[-2]
        return w

    conds = {
        "not fast": ~fast,
        "fast": fast,
        "fast & vwap<0": fast & (vwapdev < 0),
        "fast & vwap>0": fast & (vwapdev > 0),
        "fast & vwret<0": fast & (vwret < 0),
        "fast & vwret>0": fast & (vwret > 0),
        "not fast & vwap>0": (~fast) & (vwapdev > 0),
        "not fast & vwap<0": (~fast) & (vwapdev < 0),
        "rvol in [0.7,1.5]": (rvol >= 0.7) & (rvol <= 1.5),
        "rvol<1.5": rvol < 1.5,
        "rvol<1.3": rvol < 1.3,
        "not fast, rvol<1.5": (~fast) & (rvol < 1.5),
        "j100>300 or nan": ~np.isfinite(j100) | (j100 > 300),
        "vwap>0": vwapdev > 0,
        "vwap>0 & not fast": (vwapdev > 0) & (~fast),
    }
    # shift: condition on prior session close (mask[k-1])
    for name, cm in conds.items():
        lm = np.zeros(n, bool)
        lm[1:] = cm[:-1]
        s = ev(daily_mask_w(lm))
        print(f"{name:26s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
              f"Sh {s['sharpe']:4.2f} fills {s['fills']:5d} TQQQ days {lm.mean()*100:4.1f}%")

    # invert: BIL on risk-off
    print("\nBIL on risk-off (long otherwise):")
    for name, cm in conds.items():
        lm = np.ones(n, bool)
        lm[1:] = ~cm[:-1]
        s = ev(daily_mask_w(lm))
        print(f"{name:26s} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
              f"Sh {s['sharpe']:4.2f} fills {s['fills']:5d} TQQQ days {lm.mean()*100:4.1f}%")


if __name__ == "__main__":
    main()
