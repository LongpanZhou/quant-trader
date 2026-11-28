"""Second exploration pass: daily volume-clock states and coarse strategy grid."""
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


def build_sessions(ts, o, c, vol):
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
    # fraction of volume done by noon (offset 150), prior median optional
    def frac_by(j):
        f = np.where(dayvol > 0, CUM[:, min(j, OFF - 1)] / np.maximum(dayvol, 1), np.nan)
        return f
    return dates, first, last, V, CUM, dayvol, med_day, frac_by


def daily_features(ts, o, c, vol, first, last, V, CUM, dayvol, med_day):
    n = len(first)
    rows = []
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        if m < 30:
            continue
        cl = c[f:f + m, 0]
        op = o[f, 0]
        v = V[k, :m]
        vw = np.sum(v * cl) / max(v.sum(), 1)
        rr = np.diff(np.log(cl))
        vv = v[1:]
        vwret = float(np.sum(rr * vv) / max(vv.sum(), 1))
        cum = CUM[k, :m]
        tgt = med_day[k] if np.isfinite(med_day[k]) else np.nan
        j50 = j100 = np.nan
        if np.isfinite(tgt) and tgt > 0:
            i50 = int(np.searchsorted(cum, 0.5 * tgt))
            i100 = int(np.searchsorted(cum, tgt))
            if 0 < i50 < m:
                j50 = i50
            if 0 < i100 < m:
                j100 = i100
        # fraction of the day's volume in the first 150 min (through 11:59)
        f150 = float(cum[min(149, m - 1)] / max(v.sum(), 1))
        rows.append(dict(
            k=k, date=dates[k] if False else None, f=f, l=l, m=m,
            dayvol=dayvol[k], med_day=med_day[k],
            rvol=dayvol[k] / med_day[k] if np.isfinite(med_day[k]) and med_day[k] > 0 else np.nan,
            r_open=cl[-1] / op - 1.0,
            close=cl[-1], open=op, vwap=vw,
            vwap_dev=cl[-1] / vw - 1.0,
            vwret=vwret,
            f150=f150,
            j50=j50, j100=j100,
            # next-day segments (TQQQ)
            t_close=c[l, 1],
            t_next_open=o[int(first[k + 1]), 1] if k + 1 < n else np.nan,
            t_next_close=c[int(last[k + 1]), 1] if k + 1 < n else np.nan,
        ))
    return pd.DataFrame(rows)


def bucket_table(df, col, ycol, q=5):
    d = df[[col, ycol]].dropna()
    d["q"] = pd.qcut(d[col], q, labels=False, duplicates="drop")
    out = d.groupby("q")[ycol].agg(["count", "mean"])
    out["mean_bp"] = out["mean"] * 1e4
    t = d.groupby("q")[ycol].apply(lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))
    out["t"] = t
    return out


def main():
    ts, o, c, vol = load_all()
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

    rows = []
    for k in range(20, n - 1):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        if m < 30:
            continue
        cl = c[f:f + m, 0]
        op = o[f, 0]
        v = V[k, :m]
        vw = np.sum(v * cl) / max(v.sum(), 1)
        rr = np.diff(np.log(cl))
        vv = v[1:]
        vwret = float(np.sum(rr * vv) / max(vv.sum(), 1))
        cum = CUM[k, :m]
        tgt = med_day[k]
        i50 = i100 = -1
        if np.isfinite(tgt) and tgt > 0:
            i50 = int(np.searchsorted(cum, 0.5 * tgt))
            i100 = int(np.searchsorted(cum, tgt))
        fn, ln = int(first[k + 1]), int(last[k + 1])
        rows.append(dict(
            k=k, rvol=dayvol[k] / tgt if np.isfinite(tgt) and tgt > 0 else np.nan,
            vwap_dev=cl[-1] / vw - 1.0, vwret=vwret,
            r_open=cl[-1] / op - 1.0,
            f150=float(cum[min(149, m - 1)] / max(v.sum(), 1)),
            j50=i50 if 0 < i50 < m else np.nan,
            j100=i100 if 0 < i100 < m else np.nan,
            dn_open=o[fn, 1] / c[l, 1] - 1.0,
            dn_close=c[ln, 1] / c[l, 1] - 1.0,
            dn_oc=c[ln, 1] / o[fn, 1] - 1.0,
        ))
    df = pd.DataFrame(rows)
    print("daily feature rows", len(df))
    for col in ("rvol", "vwap_dev", "vwret", "r_open", "f150"):
        print(f"\n--- {col} -> next-day TQQQ close-to-close (bp) ---")
        print(bucket_table(df, col, "dn_open").round(3) if False else "")
        print(bucket_table(df, col, "dn_close").round(2))
    print("\n--- sign vwap_dev x sign vwret -> next-day TQQQ ---")
    for a in (-1, 1):
        for b in (-1, 1):
            m = (np.sign(df["vwap_dev"]) == a) & (np.sign(df["vwret"]) == b)
            x = df.loc[m, "dn_close"]
            print(f"vwapdev{a:+d} vwret{b:+d}: n={len(x):4d} mean {x.mean()*1e4:7.2f}bp "
                  f"t={x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):5.2f}")

    # --- coarse strategy grid ---
    print("\n=== coarse strategy grid ===")
    f = np.asarray(first); l = np.asarray(last)
    o = np.asarray(o); c = np.asarray(c)
    # precompute per-session decision offsets for each level
    feats = {}
    for x in (0.4, 0.5, 0.6, 0.75, 1.0):
        arr = []
        for k in range(n):
            m = min(int(l[k]) - int(f[k]) + 1, 390)
            tgt = x * med_day[k] if np.isfinite(med_day[k]) else np.nan
            j = -1
            if np.isfinite(tgt) and tgt > 0:
                j = int(np.searchsorted(CUM[k, :m], tgt))
                if j >= m - 1:
                    j = -1
            arr.append(j)
        feats[x] = np.array(arr)

    # per-session signals at each j
    def signals(k, j):
        m = min(int(l[k]) - int(f[k]) + 1, 390)
        cl = c[int(f[k]):int(f[k]) + m, 0]
        v = V[k, :m]
        vw = np.sum(v[:j + 1] * cl[:j + 1]) / max(v[:j + 1].sum(), 1)
        px = cl[j]
        rr = np.diff(np.log(cl[:j + 1]))
        vv = v[1:j + 1]
        return dict(vwapdev=px / vw - 1.0, r_open=px / cl[0] - 1.0,
                    vwret=float(np.sum(rr * vv) / max(vv.sum(), 1)) if len(vv) else 0.0)

    cache = {}
    for x in feats:
        for k in range(n):
            j = feats[x][k]
            if j > 0:
                cache[(x, int(k))] = signals(k, j)

    def make_w(x, sig, dead, hold, mode="long_when_pos", size=1.0):
        w = np.zeros((len(ts), 3))
        for k in range(n):
            j = feats[x][k]
            if j <= 0:
                continue
            s = cache.get((x, k))
            if s is None:
                continue
            val = s[sig]
            allow = val > dead if mode == "long_when_pos" else not (val < -dead)
            if not allow:
                continue
            fk, lk = int(f[k]), int(l[k])
            en = min(j + 1, lk)
            w[j, 1] = size
            if hold == "intraday":
                w[en:lk, 1] = size           # through bar lk-1, exit at lk open
                w[lk - 1, 1] = 0.0
            elif hold == "overnight":
                w[en:lk + 1, 1] = size       # through close
                w[lk, 1] = 0.0               # exit next open
            elif hold == "next_close":
                if k + 1 < n:
                    fn, ln = int(f[k + 1]), int(l[k + 1])
                    w[en:ln, 1] = size
                    w[ln - 1, 1] = 0.0
        w[-1] = w[-2]
        return w

    def ev(w, slip=1.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        return s

    # baseline
    wb = np.zeros((len(ts), 3)); wb[:, 1] = 1.0
    sb = ev(wb)
    print(f"baseline TQQQ: CAGR {sb['cagr']*100:6.2f}% DD {sb['max_drawdown']*100:6.2f}% "
          f"Sharpe {sb['sharpe']:.2f} fills {sb['fills']}")

    out = []
    for x in (0.5, 0.6, 0.75):
        for sig in ("vwapdev", "r_open", "vwret"):
            for dead in (0.0, 0.001, 0.002):
                for hold in ("intraday", "overnight", "next_close"):
                    for mode in ("long_when_pos", "avoid_neg"):
                        w = make_w(x, sig, dead, hold, mode)
                        s = ev(w)
                        out.append((s["sharpe"], s["cagr"], x, sig, dead, hold, mode,
                                    s["max_drawdown"], s["fills"], s["turnover"],
                                    np.mean(w[:, 1] > 0)))
    out.sort(reverse=True)
    print("\ntop 25 by Sharpe:")
    for row in out[:25]:
        sh, cagr, x, sig, dead, hold, mode, dd, fills, to, expo = row
        print(f"x{x:.2f} {sig:7s} d{dead*1e4:4.0f}bp {hold:10s} {mode:13s} "
              f"CAGR {cagr*100:6.2f}% DD {dd*100:5.1f}% Sh {sh:4.2f} "
              f"fills {fills:5d} expo {expo*100:4.1f}%")

    # daily-state filter grid: long TQQQ on day d+1 unless state says risk-off
    print("\n=== daily state filter: long TQQQ by default, BIL when condition ===")
    dfx = df.reset_index(drop=True)
    # map session k -> row
    row_of = {int(r.k): i for i, r in dfx.iterrows()}

    def daily_w(cond):
        w = np.zeros((len(ts), 3))
        w[:, 1] = 1.0
        for k in range(n):
            fk, lk = int(f[k]), int(l[k])
            if k == 0:
                continue
            # decide at prior close: cond is evaluated on session k-1
            i = row_of.get(k - 1)
            riskoff = bool(cond(dfx.iloc[i])) if i is not None else False
            if riskoff:
                w[fk:lk, 1] = 0.0
                w[fk:lk, 2] = 1.0
        w[-1] = w[-2]
        return w

    conds = {
        "rvol>1.5": lambda r: r.rvol > 1.5,
        "rvol>2.0": lambda r: r.rvol > 2.0,
        "rvol<0.7": lambda r: r.rvol < 0.7,
        "vwapdev<0": lambda r: r.vwap_dev < 0,
        "vwapdev<-0.3%": lambda r: r.vwap_dev < -0.003,
        "vwret<0": lambda r: r.vwret < 0,
        "vwret<-5bp": lambda r: r.vwret < -0.0005,
        "rvol>1.5 & vwapdev<0": lambda r: r.rvol > 1.5 and r.vwap_dev < 0,
        "rvol>1.5 & vwret<0": lambda r: r.rvol > 1.5 and r.vwret < 0,
        "f150>0.7": lambda r: r.f150 > 0.7,
        "f150>0.7 & vwapdev<0": lambda r: r.f150 > 0.7 and r.vwap_dev < 0,
        "f150<0.45": lambda r: r.f150 < 0.45,
        "j100 fast": lambda r: np.isfinite(r.j100) and r.j100 < 240,
        "j100 fast & vwapdev<0": lambda r: np.isfinite(r.j100) and r.j100 < 240 and r.vwap_dev < 0,
    }
    dout = []
    for name, cond in conds.items():
        w = daily_w(cond)
        s = ev(w)
        dout.append((s["sharpe"], s["cagr"], name, s["max_drawdown"], s["fills"],
                     np.mean(w[:, 1] > 0)))
    dout.sort(reverse=True)
    for sh, cagr, name, dd, fills, expo in dout:
        print(f"{name:30s} CAGR {cagr*100:6.2f}% DD {dd*100:5.1f}% Sh {sh:4.2f} "
              f"fills {fills:5d} TQQQ expo {expo*100:4.1f}%")


if __name__ == "__main__":
    main()
