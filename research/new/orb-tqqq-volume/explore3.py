"""Exploration 3: how much intraday expectancy can ORB + confirmation buy?

Scratch. Rebuilds a richer session table (prior-day levels, QQQ opening range,
QQQ volume) and scans single/dual confirmation filters. The purpose is to
establish whether a long-only, flat-overnight TQQQ ORB can plausibly reach the
36.72% dev bar, before the pre-registered grid is written.
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
CACHE = Path(__file__).resolve().parent / "_sessions3.pkl"


def build():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=100)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= lo) & (df["ts"] <= hi)]
        return df.set_index("ts").reindex(ts).ffill()

    q, t = prep("QQQ"), prep("TQQQ")
    to, th, tl, tc, tv = (t[c].to_numpy() for c in ("open", "high", "low", "close", "volume"))
    qo, qh, ql, qc, qv = (q[c].to_numpy() for c in ("open", "high", "low", "close", "volume"))
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    tod = np.asarray(ts.hour * 60 + ts.minute)
    rows = []
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = int(np.searchsorted(tod[s:e], 10 * 60))
        if j < 10:
            continue
        c = tc
        # classic breakout after 10:00, entry next open
        brk = -1
        for i in range(s + j, e - 1):
            if c[i] > th[s:s + j].max():
                brk = i
                break
        # QQQ breakout at the same bar (confirmation)
        qbrk = -1
        for i in range(s + j, e - 1):
            if qc[i] > qh[s:s + j].max():
                qbrk = i
                break
        # failed breakdown of the OR low
        rec = -1
        sweep = np.inf
        for i in range(s + j, e - 1):
            if tl[i] < tl[s:s + j].min() * 0.9995:
                sweep = min(sweep, tl[i])
                if c[i] > tl[s:s + j].min() * 1.0005:
                    rec = i
                    break
        # sweep of the prior session low, reclaim (needs prior low; fill later)
        rows.append(dict(
            date=dates[s], t_open=to[s], t_high=th[s:e].max(), t_low=tl[s:e].min(),
            t_close=tc[e - 1], t_vol=tv[s:e].sum(),
            or_hi=th[s:s + j].max(), or_lo=tl[s:s + j].min(),
            or_vol=tv[s:s + j].sum(),
            or_ret=tc[s + j - 1] / to[s] - 1.0,
            rest_o=to[s + j] if s + j < e else np.nan,
            brk_px=to[brk + 1] if brk >= 0 else np.nan,
            brk_min=tod[brk] if brk >= 0 else np.nan,
            brk_first=(brk >= 0 and brk <= s + j + 30),
            qbrk_min=tod[qbrk] if qbrk >= 0 else np.nan,
            rec_px=to[rec + 1] if rec >= 0 else np.nan,
            rec_min=tod[rec] if rec >= 0 else np.nan,
            sweep_low=sweep if np.isfinite(sweep) else np.nan,
            q_or_hi=qh[s:s + j].max(), q_or_lo=ql[s:s + j].min(),
            q_or_vol=qv[s:s + j].sum(),
            q_open=qo[s], q_close=qc[e - 1], q_high=qh[s:e].max(), q_low=ql[s:e].min(),
        ))
    df = pd.DataFrame(rows)
    df["rest_c"] = df["t_close"]
    df["rest_ret"] = df["rest_c"] / df["rest_o"] - 1.0
    df["oc"] = df["t_close"] / df["t_open"] - 1.0
    df["brk_ret"] = df["t_close"] / df["brk_px"] - 1.0
    df["rec_ret"] = df["t_close"] / df["rec_px"] - 1.0
    df["prev_close"] = df["t_close"].shift(1)
    df["prev_high"] = df["t_high"].shift(1)
    df["prev_low"] = df["t_low"].shift(1)
    df["gap"] = df["t_open"] / df["prev_close"] - 1.0
    tr = np.maximum(df["t_high"] - df["t_low"],
                    np.maximum((df["t_high"] - df["prev_close"]).abs(),
                               (df["t_low"] - df["prev_close"]).abs()))
    df["atr14"] = tr.shift(1).rolling(14).mean()
    df["or_width"] = (df["or_hi"] - df["or_lo"]) / df["t_open"]
    df["or_atr"] = df["or_width"] * df["t_open"] / df["atr14"]
    df["rvol"] = df["or_vol"] / df["or_vol"].shift(1).rolling(20).mean()
    df["q_rvol"] = df["q_or_vol"] / df["q_or_vol"].shift(1).rolling(20).mean()
    df["prev_ret"] = df["t_close"].pct_change().shift(1)
    df["ret5"] = df["t_close"].pct_change(5).shift(1)
    df["ret20"] = df["t_close"].pct_change(20).shift(1)
    df["q_ret5"] = df["q_close"].pct_change(5).shift(1)
    df["q_ret20"] = df["q_close"].pct_change(20).shift(1)
    df["gap_atr"] = df["gap"] * df["t_open"] / df["atr14"]
    df["sweep_depth"] = (df["or_lo"] - df["sweep_low"]) / df["or_lo"]
    df["prior_low_sweep"] = df["t_low"] < df["prev_low"]
    df["prior_low_reclaim"] = df["t_close"] > df["prev_low"]
    df["qqq_confirm"] = df["qbrk_min"] <= df["brk_min"] + 5
    df.to_pickle(CACHE)
    return df


def show(df, col, label, min_n=15):
    x = df[col].replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < min_n:
        return
    yrs = 7.984
    gm = np.exp(np.mean(np.log1p(x))) - 1
    print(f"{label:56s} n={len(x):4d} ({len(x)/yrs:5.1f}/y) mean={x.mean()*100:6.3f}% "
          f"med={x.median()*100:6.3f}% win={np.mean(x>0)*100:5.1f}% "
          f"t={x.mean()/x.std()*np.sqrt(len(x)):5.2f} gm={gm*100:6.3f}% "
          f"cagr={((1+gm)**(len(x)/yrs)-1)*100:6.2f}%")


def main():
    df = pd.read_pickle(CACHE) if CACHE.exists() else build()
    df = df[df["date"] >= pd.Timestamp(DEV_START).date()].reset_index(drop=True)
    print(f"sessions {len(df)}  trades/yr denominator 7.984")

    print("\n=== baseline ===")
    show(df, "rest_ret", "long at 10:00 every day")
    show(df, "brk_ret", "classic ORB all")
    show(df, "rec_ret", "OR-low sweep+reclaim all")

    print("\n=== ceiling scan: long at 10:00, hold to close ===")
    tests = [
        ("or_ret>0", df["or_ret"] > 0),
        ("or_ret>0.3%", df["or_ret"] > 0.003),
        ("or_ret>0.5%", df["or_ret"] > 0.005),
        ("or_ret>0.8%", df["or_ret"] > 0.008),
        ("or_ret in [0,0.8%]", df["or_ret"].between(0, 0.008)),
        ("gap>0", df["gap"] > 0),
        ("gap 0.2-0.8%", df["gap"].between(0.002, 0.008)),
        ("gap>0 & or_up", (df["gap"] > 0) & (df["or_ret"] > 0)),
        ("gap>0 & or>0.3%", (df["gap"] > 0) & (df["or_ret"] > 0.003)),
        ("gap>0 & or>0.3% & rvol .9-1.2",
         (df["gap"] > 0) & (df["or_ret"] > 0.003) & df["rvol"].between(.9, 1.2)),
        ("gap>0 & or>0.3% & or/atr .3-.45",
         (df["gap"] > 0) & (df["or_ret"] > 0.003) & df["or_atr"].between(.3, .45)),
        ("gap>0 & or>0.3% & qqq_confirm",
         (df["gap"] > 0) & (df["or_ret"] > 0.003) & df["qqq_confirm"]),
        ("gap 0.2-0.8 & or>0.3 & rvol .9-1.2",
         df["gap"].between(.002, .008) & (df["or_ret"] > 0.003) & df["rvol"].between(.9, 1.2)),
        ("gap>0 & or>0.3% & ret5>0", (df["gap"] > 0) & (df["or_ret"] > 0.003) & (df["ret5"] > 0)),
        ("gap>0 & or>0.3% & ret20>0", (df["gap"] > 0) & (df["or_ret"] > 0.003) & (df["ret20"] > 0)),
        ("gap<0", df["gap"] < 0),
        ("gap<-1%", df["gap"] < -0.01),
        ("gap<-1.5%", df["gap"] < -0.015),
        ("gap<-1% & or_up", (df["gap"] < -0.01) & (df["or_ret"] > 0)),
        ("gap<-1.5% & or_up", (df["gap"] < -0.015) & (df["or_ret"] > 0)),
        ("prev day <-2%", df["prev_ret"] < -0.02),
        ("prev day <-2% & gap<0 & or_up",
         (df["prev_ret"] < -0.02) & (df["gap"] < 0) & (df["or_ret"] > 0)),
        ("open<prev_low & close>prev_low", (df["t_open"] < df["prev_low"]) &
         (df["t_close"] > df["prev_low"])),
        ("sweep prev_low & reclaim by close", (df["t_low"] < df["prev_low"]) &
         (df["t_close"] > df["prev_low"])),
    ]
    for label, mask in tests:
        show(df[mask.fillna(False)], "rest_ret", label)

    print("\n=== ORB variants ===")
    b = df[df["brk_px"].notna()]
    tests = [
        ("all", b["brk_px"].notna()),
        ("gap>0", b["gap"] > 0),
        ("gap>0 & rvol .9-1.2", (b["gap"] > 0) & b["rvol"].between(.9, 1.2)),
        ("gap>0 & rvol .8-1.3", (b["gap"] > 0) & b["rvol"].between(.8, 1.3)),
        ("gap>0 & or/atr .3-.45", (b["gap"] > 0) & b["or_atr"].between(.3, .45)),
        ("gap>0 & or/atr .25-.5", (b["gap"] > 0) & b["or_atr"].between(.25, .5)),
        ("gap>0 & rvol .9-1.2 & or/atr .3-.45",
         (b["gap"] > 0) & b["rvol"].between(.9, 1.2) & b["or_atr"].between(.3, .45)),
        ("gap 0.2-0.8% & rvol .9-1.2 & or/atr .3-.45",
         b["gap"].between(.002, .008) & b["rvol"].between(.9, 1.2) & b["or_atr"].between(.3, .45)),
        ("gap>0 & qqq_confirm", (b["gap"] > 0) & b["qqq_confirm"]),
        ("gap>0 & qqq_confirm & rvol .9-1.2",
         (b["gap"] > 0) & b["qqq_confirm"] & b["rvol"].between(.9, 1.2)),
        ("first 30 bars (early breakout)", b["brk_first"]),
        ("early & gap>0", b["brk_first"] & (b["gap"] > 0)),
        ("early & gap>0 & rvol .9-1.2",
         b["brk_first"] & (b["gap"] > 0) & b["rvol"].between(.9, 1.2)),
    ]
    for label, mask in tests:
        show(b[mask.fillna(False)], "brk_ret", label)

    print("\n=== sweep+reclaim variants ===")
    r = df[df["rec_px"].notna()]
    tests = [
        ("all", r["rec_px"].notna()),
        ("depth>0.2%", r["sweep_depth"] > 0.002),
        ("depth>0.2% & gap<0 & rvol .9-1.2",
         (r["sweep_depth"] > 0.002) & (r["gap"] < 0) & r["rvol"].between(.9, 1.2)),
        ("depth>0.2% & gap<0 & rvol>1.2",
         (r["sweep_depth"] > 0.002) & (r["gap"] < 0) & (r["rvol"] > 1.2)),
        ("gap<-1% & reclaim", (r["gap"] < -0.01)),
    ]
    for label, mask in tests:
        show(r[mask.fillna(False)], "rec_ret", label)

    print("\n=== what would 36.7% need? ===")
    for n in (100, 150, 200, 250):
        ne = np.log(1.367) / n
        print(f"  {n:3d} trades/yr need log {ne*100:.3f}%/trade "
              f"~ arithmetic {(ne + 0.5*(0.025**2))*100:.3f}% at 2.5% daily vol")


if __name__ == "__main__":
    main()
