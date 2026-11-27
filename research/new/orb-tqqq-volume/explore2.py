"""Exploration 2: conditional structure of TQQQ intraday sessions (dev only).

Scratch. Builds a session table once and tests signal families at the daily
level (entry at a known open, exit at the last-bar open). Numbers here are
screening evidence, not the final strategy.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
CACHE = Path(__file__).resolve().parent / "_sessions2.pkl"


def build():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=80)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= lo) & (df["ts"] <= hi)]
        return df.set_index("ts").reindex(ts).ffill()

    q, t = prep("QQQ"), prep("TQQQ")
    to, th, tl, tc, tv = (t[c].to_numpy() for c in ("open", "high", "low", "close", "volume"))
    qo, qh, ql, qc = (q[c].to_numpy() for c in ("open", "high", "low", "close"))
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    tod = np.asarray(ts.hour * 60 + ts.minute)
    n = len(starts)

    rows = []
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = int(np.searchsorted(tod[s:e], 10 * 60))
        if j < 10:
            continue
        # OR bars 09:30-09:59, then the 10:00 bar opens the "rest" window
        orh, orl = th[s:s + j].max(), tl[s:s + j].min()
        orv = tv[s:s + j].sum()
        rest_o = to[s + j] if s + j < e else np.nan
        rest_c = tc[e - 1]
        # classic breakout after 10:00
        brk_i, rec_i = -1, -1
        broke = False
        sweep = np.inf
        c = tc
        for i in range(s + j, e - 1):
            if not broke and hi_ok(c[i], orh):
                brk_i = i
                broke = True
                break
        # failed breakdown: low beneath ORL then close back above ORL
        for i in range(s + j, e - 1):
            if tl[i] < orl * 0.9995:
                sweep = min(sweep, tl[i])
                if c[i] > orl * 1.0005:
                    rec_i = i
                    break
        def px(i):
            return to[i + 1] if 0 <= i < e - 1 else np.nan

        rows.append(dict(
            date=dates[s], t_open=to[s], t_close=tc[e - 1],
            t_high=th[s:e].max(), t_low=tl[s:e].min(), t_vol=tv[s:e].sum(),
            or_hi=orh, or_lo=orl, or_vol=orv,
            or_ret=tc[s + j - 1] / to[s] - 1.0,
            rest_ret=rest_c / rest_o - 1.0,
            full_oc=rest_c / to[s] - 1.0,
            brk_px=px(brk_i), brk_min=tod[brk_i] if brk_i >= 0 else np.nan,
            reclaim_px=px(rec_i), reclaim_min=tod[rec_i] if rec_i >= 0 else np.nan,
            sweep_low=sweep if np.isfinite(sweep) else np.nan,
            q_close=qc[e - 1], q_open=qo[s], q_high=qh[s:e].max(), q_low=ql[s:e].min(),
            next_open=to[e] if e < len(to) else np.nan,
        ))
    df = pd.DataFrame(rows)
    df["prev_close"] = df["t_close"].shift(1)
    df["gap"] = df["t_open"] / df["prev_close"] - 1.0
    df["oc"] = df["t_close"] / df["t_open"] - 1.0
    df["brk_ret"] = df["t_close"] / df["brk_px"] - 1.0
    df["rec_ret"] = df["t_close"] / df["reclaim_px"] - 1.0
    df["rec_ret_stop"] = np.where(
        df["sweep_low"].notna(),
        np.where(df["t_low"] <= df["sweep_low"], np.nan, df["rec_ret"]), np.nan)
    tr = np.maximum(df["t_high"] - df["t_low"],
                    np.maximum((df["t_high"] - df["prev_close"]).abs(),
                               (df["t_low"] - df["prev_close"]).abs()))
    df["atr14"] = tr.shift(1).rolling(14).mean()
    df["or_width"] = (df["or_hi"] - df["or_lo"]) / df["t_open"]
    df["or_atr"] = df["or_width"] * df["t_open"] / df["atr14"]
    df["rvol"] = df["or_vol"] / df["or_vol"].shift(1).rolling(20).mean()
    df["prev_ret"] = df["t_close"].pct_change().shift(1)
    df["ret5"] = df["t_close"].pct_change(5).shift(1)
    df["gap_atr"] = df["gap"] * df["t_open"] / df["atr14"]
    df["sweep_depth"] = (df["or_lo"] - df["sweep_low"]) / df["or_lo"]
    df.to_pickle(CACHE)
    return df


def hi_ok(c, h):
    return c > h


def st(df, col, label, min_n=20):
    x = df[col].replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < min_n:
        print(f"{label:52s} n={len(x):4d}  (thin)")
        return
    print(f"{label:52s} n={len(x):4d} mean={x.mean()*100:7.3f}% med={x.median()*100:7.3f}% "
          f"win={np.mean(x>0)*100:5.1f}% t={x.mean()/x.std()*np.sqrt(len(x)):5.2f} "
          f"cagr={np.prod(1+x)**(252/len(df))-1:7.3%}")


def bucket_report(df, col, retcol, bins, labels, title):
    print(f"\n--- {title} ---")
    df = df.copy()
    df["_b"] = pd.cut(df[col], bins=bins, labels=labels)
    for lab in labels:
        st(df[df["_b"] == lab], retcol, f"  {lab}")


def main():
    df = pd.read_pickle(CACHE) if CACHE.exists() else build()
    df = df[df["date"] >= pd.Timestamp(DEV_START).date()].reset_index(drop=True)
    print(f"sessions {len(df)}")

    print("\n=== first-30m -> rest-of-day predictive structure ===")
    for q in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        pass
    df["or_q"] = pd.qcut(df["or_ret"], 10, labels=False, duplicates="drop")
    for k in sorted(df["or_q"].dropna().unique()):
        g = df[df["or_q"] == k]
        st(g, "rest_ret", f"  OR ret decile {int(k)}  [{g['or_ret'].min()*100:6.2f},"
                          f"{g['or_ret'].max()*100:6.2f}]%")

    print("\ncorr(or_ret, rest_ret) =", df["or_ret"].corr(df["rest_ret"]))
    print("corr(or_ret, full_oc) =", df["or_ret"].corr(df["full_oc"]))
    print("unconditional rest_ret:", df["rest_ret"].mean() * 100, "%/day")

    bucket_report(df, "rvol", "rest_ret", [0, .8, .9, 1.0, 1.1, 1.3, 10],
                  ["<0.8", "0.8-0.9", "0.9-1.0", "1.0-1.1", "1.1-1.3", ">1.3"],
                  "rest_ret by opening volume ratio")
    bucket_report(df, "or_atr", "rest_ret", [0, .25, .3, .35, .4, .5, 5],
                  ["<.25", ".25-.30", ".30-.35", ".35-.40", ".40-.50", ">.50"],
                  "rest_ret by OR width / ATR")
    bucket_report(df, "gap", "rest_ret", [-1, -.005, 0, .003, .007, .012, 1],
                  ["<-0.5%", "-0.5-0", "0-0.3%", "0.3-0.7%", "0.7-1.2%", ">1.2%"],
                  "rest_ret by gap")

    print("\n=== first-30m up (drive) subsets ===")
    st(df[df["or_ret"] > 0], "rest_ret", "or_ret>0")
    st(df[df["or_ret"] > 0.003], "rest_ret", "or_ret>+0.3%")
    st(df[(df["or_ret"] > 0.003) & (df["rvol"] > 1.0)], "rest_ret", "or_ret>+0.3% & rvol>1")
    st(df[(df["or_ret"] > 0.003) & (df["gap"] > 0)], "rest_ret", "or_ret>+0.3% & gap>0")
    st(df[(df["or_ret"] > 0.003) & (df["gap"] > 0) & (df["rvol"] > 1.0)],
       "rest_ret", "or_ret>+0.3% & gap>0 & rvol>1")
    st(df[(df["or_ret"] > 0.005) & (df["gap"] > 0) & (df["rvol"] > 1.1) & (df["or_atr"] < .5)],
       "rest_ret", "or_ret>+0.5% & gap>0 & rvol>1.1 & or/atr<.5")

    print("\n=== classic breakout subsets ===")
    b = df[df["brk_px"].notna()]
    st(b, "brk_ret", "all")
    st(b[b["gap"] > 0], "brk_ret", "gap>0")
    st(b[(b["gap"] > 0) & (b["rvol"] > 1.05)], "brk_ret", "gap>0 & rvol>1.05")
    st(b[(b["gap"] > 0) & (b["rvol"].between(.85, 1.15))], "brk_ret", "gap>0 & rvol .85-1.15")
    st(b[(b["gap"] > 0.003) & (b["rvol"].between(.85, 1.2))], "brk_ret", "gap>0.3% & rvol .85-1.2")
    st(b[(b["or_atr"].between(.25, .42))], "brk_ret", "or/atr .25-.42")
    st(b[(b["gap"] > 0) & (b["or_atr"].between(.25, .45))], "brk_ret", "gap>0 & or/atr .25-.45")
    st(b[(b["gap"] > 0) & (b["rvol"] > 1.05) & (b["or_atr"].between(.25, .45))],
       "brk_ret", "gap>0 & rvol>1.05 & or/atr .25-.45")
    st(b[(b["brk_min"] < 690)], "brk_ret", "entry before 11:30")
    st(b[(b["brk_min"] < 660)], "brk_ret", "entry before 11:00")

    print("\n=== failed-breakdown reclaim subsets ===")
    r = df[df["reclaim_px"].notna()]
    st(r, "rec_ret", "all reclaims (no stop)")
    st(r[r["sweep_depth"] > 0.001], "rec_ret", "sweep depth >0.1%")
    st(r[r["sweep_depth"] > 0.002], "rec_ret", "sweep depth >0.2%")
    st(r[r["sweep_depth"] > 0.003], "rec_ret", "sweep depth >0.3%")
    st(r[(r["sweep_depth"] > 0.002) & (r["rvol"] > 1.1)], "rec_ret", "depth>0.2% & rvol>1.1")
    st(r[(r["sweep_depth"] > 0.002) & (r["gap"] < 0)], "rec_ret", "depth>0.2% & gap<0")
    st(r[(r["sweep_depth"] > 0.002) & (r["gap"] < 0) & (r["rvol"] > 1.1)],
       "rec_ret", "depth>0.2% & gap<0 & rvol>1.1")

    print("\n=== day-of-week / year sanity for ORB ===")
    b = b.copy()
    b["dow"] = pd.to_datetime(b["date"]).dt.dayofweek
    for d in range(5):
        st(b[b["dow"] == d], "brk_ret", f"  dow {d}")


if __name__ == "__main__":
    main()
