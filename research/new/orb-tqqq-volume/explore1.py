"""Exploration 1: dev-window (2016-2023) structure of TQQQ intraday ORB.

Scratch only. Loads the 1-minute panel for the development window, builds
per-session aggregates, and prints conditional statistics. No strategy
results are claimed from this file; the final numbers come from strategy.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
CACHE = Path(__file__).resolve().parent / "_sessions.npz"


def build_sessions():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=80)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= lo) & (df["ts"] <= hi)]
        return df.set_index("ts").reindex(ts).ffill()

    q = prep("QQQ")
    t = prep("TQQQ")

    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    n = len(starts)
    tod = np.asarray(ts.hour * 60 + ts.minute)

    cols = {}
    cols["date"] = dates[starts]
    cols["t_open"] = t["open"].to_numpy()[starts]
    cols["t_close"] = t["close"].to_numpy()[ends - 1]
    cols["t_high"] = np.array([t["high"].to_numpy()[s:e].max() for s, e in zip(starts, ends)])
    cols["t_low"] = np.array([t["low"].to_numpy()[s:e].min() for s, e in zip(starts, ends)])
    cols["t_vol"] = np.array([t["volume"].to_numpy()[s:e].sum() for s, e in zip(starts, ends)])
    cols["q_close"] = q["close"].to_numpy()[ends - 1]
    cols["q_high"] = np.array([q["high"].to_numpy()[s:e].max() for s, e in zip(starts, ends)])
    cols["q_low"] = np.array([q["low"].to_numpy()[s:e].min() for s, e in zip(starts, ends)])

    # opening range: bars stamped before 10:00
    orh = np.full(n, np.nan)
    orl = np.full(n, np.nan)
    orv = np.full(n, np.nan)
    orhi_q = np.full(n, np.nan)
    orlo_q = np.full(n, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = int(np.searchsorted(tod[s:e], 10 * 60))
        if j < 5:
            continue
        orh[k] = t["high"].to_numpy()[s:s + j].max()
        orl[k] = t["low"].to_numpy()[s:s + j].min()
        orv[k] = t["volume"].to_numpy()[s:s + j].sum()
        orhi_q[k] = q["high"].to_numpy()[s:s + j].max()
        orlo_q[k] = q["low"].to_numpy()[s:s + j].min()
    cols["or_hi"] = orh
    cols["or_lo"] = orl
    cols["or_vol"] = orv
    cols["q_or_hi"] = orhi_q
    cols["q_or_lo"] = orlo_q

    # ORB entry: first close > ORH after 10:00, fill at next bar open
    ent_i = np.full(n, -1, dtype=int)
    ent_px = np.full(n, np.nan)
    ent_min = np.full(n, np.nan)
    exit_px = np.full(n, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        if not np.isfinite(orh[k]):
            continue
        c = t["close"].to_numpy()
        j0 = int(np.searchsorted(tod[s:e], 10 * 60))
        for i in range(s + j0, e):
            if c[i] > orh[k] and i + 1 < e:
                ent_i[k] = i
                ent_px[k] = t["open"].to_numpy()[i + 1]
                ent_min[k] = tod[i]
                exit_px[k] = t["open"].to_numpy()[e - 1]
                break
    cols["entry_i"] = ent_i
    cols["entry_px"] = ent_px
    cols["exit_px"] = exit_px
    cols["entry_min"] = ent_min

    df = pd.DataFrame(cols)
    df["prev_close"] = df["t_close"].shift(1)
    df["gap"] = df["t_open"] / df["prev_close"] - 1.0
    df["oc"] = df["t_close"] / df["t_open"] - 1.0
    df["orb_ret"] = df["exit_px"] / df["entry_px"] - 1.0
    df["or_width"] = (df["or_hi"] - df["or_lo"]) / df["t_open"]
    # prior 14-day ATR (TQQQ), causal
    tr = np.maximum(df["t_high"] - df["t_low"],
                    np.maximum((df["t_high"] - df["prev_close"]).abs(),
                               (df["t_low"] - df["prev_close"]).abs()))
    df["atr14"] = tr.shift(1).rolling(14).mean()
    df["or_atr"] = df["or_width"] * df["t_open"] / df["atr14"]
    df["rvol"] = df["or_vol"] / df["or_vol"].shift(1).rolling(20).mean()
    df["day_atr"] = (df["t_high"] - df["t_low"]) / df["atr14"]
    df.to_pickle(CACHE)
    return df


def qstats(df, label):
    x = df["orb_ret"].dropna()
    print(f"{label:40s} n={len(x):4d} mean={x.mean()*100:7.3f}% "
          f"med={x.median()*100:7.3f}% win={np.mean(x>0)*100:5.1f}% "
          f"std={x.std()*100:5.2f}% t={x.mean()/x.std()*np.sqrt(len(x)):5.2f}")


def main():
    if CACHE.exists():
        df = pd.read_pickle(CACHE)
    else:
        df = build_sessions()
    df = df[df["date"] >= pd.Timestamp(DEV_START).date()].copy()
    print(f"sessions {len(df)}  {df['date'].iloc[0]} .. {df['date'].iloc[-1]}")
    print(f"TQQQ close-to-close CAGR "
          f"{(df['t_close'].iloc[-1]/df['prev_close'].dropna().iloc[0])**(252/len(df))-1:.4f}")

    # benchmark exactly as the harness marks it
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=80)
    i = bt.start_index(ts, DEV_START)
    b = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)
    bb = bt.benchmark(closes[i:, 1], ts[i:], 252)
    print("harness 1m benchmark:", {k: round(v, 4) if isinstance(v, float) else v
                                   for k, v in b.items()})
    print("harness 1D benchmark:", {k: round(v, 4) if isinstance(v, float) else v
                                   for k, v in bb.items()})

    # intraday-only benchmark: open->close every day, no costs
    oc = df["oc"].dropna()
    print(f"\nTQQQ open->close every day: n={len(oc)} mean={oc.mean()*100:.4f}% "
          f"cagr={(np.prod(1+oc))**(252/len(oc))-1:.4f} vol={oc.std()*np.sqrt(252)*100:.1f}%")
    print(f"TQQQ close->open every day: mean={((1+df['t_open']/df['prev_close']-1).dropna()).mean()*100:.4f}%")

    print("\n=== classic ORB (first close > ORH after 10:00, exit last-bar open) ===")
    qstats(df, "all breakouts")
    qstats(df[df["gap"] > 0], "gap up")
    qstats(df[df["gap"] <= 0], "gap down/flat")

    df["rvol_q"] = pd.qcut(df["rvol"], 5, labels=False, duplicates="drop")
    print("\nrvol quintile (opening 30m volume / prior 20d mean):")
    for k in range(5):
        qstats(df[df["rvol_q"] == k], f"  rvol q{k} "
              f"[{df.loc[df.rvol_q==k,'rvol'].min():.2f}-{df.loc[df.rvol_q==k,'rvol'].max():.2f}]")

    df["oa_q"] = pd.qcut(df["or_atr"], 5, labels=False, duplicates="drop")
    print("\nOR width / ATR14 quintile:")
    for k in range(5):
        qstats(df[df["oa_q"] == k], f"  or/atr q{k} "
              f"[{df.loc[df.oa_q==k,'or_atr'].min():.2f}-{df.loc[df.oa_q==k,'or_atr'].max():.2f}]")

    print("\n=== rvol x or/atr cells (mean orb_ret, n) ===")
    for a in range(5):
        row = []
        for bq in range(5):
            x = df[(df["rvol_q"] == a) & (df["oa_q"] == bq)]["orb_ret"].dropna()
            row.append(f"{x.mean()*100:6.2f}%({len(x):3d})" if len(x) else "     -     ")
        print(f"  rvol q{a}: " + " ".join(row))

    # entry timing
    print("\nentry time deciles:")
    df["em"] = pd.cut(df["entry_min"], bins=[600, 630, 660, 690, 720, 780, 840, 900, 960],
                      labels=False)
    for k in range(8):
        qstats(df[df["em"] == k], f"  entry {600+30*k}-{630+30*k} min")

    # yearly
    print("\nORB by year:")
    for y, g in df.groupby(df["date"].apply(lambda d: d.year)):
        qstats(g, f"  {y}")


if __name__ == "__main__":
    main()
