"""Exploration 4: event-level minute-path test of ORB exits and volume confirm.

For each ORB signal, walk the actual 1-minute bars from the fill and apply
stop/target/failed-breakout exits with next-open fills. This is the same fill
convention as bt.simulate. Scratch; final numbers come from strategy.py.
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
CACHE = Path(__file__).resolve().parent / "_events4.pkl"


def build():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=100)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        d = bt.load_1m(sym)
        d = d[(d["ts"] >= lo) & (d["ts"] <= hi)]
        return d.set_index("ts").reindex(ts).ffill()

    q, t = prep("QQQ"), prep("TQQQ")
    to, th, tl, tc, tv = (t[c].to_numpy() for c in ("open", "high", "low", "close", "volume"))
    qc = q["close"].to_numpy()
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    tod = np.asarray(ts.hour * 60 + ts.minute)
    rows = []
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = int(np.searchsorted(tod[s:e], 600))
        if j < 10:
            continue
        orh, orl = th[s:s + j].max(), tl[s:s + j].min()
        orv = tv[s:s + j].sum()
        or_bar_vol = tv[s:s + j]
        brk = -1
        for i in range(s + j, e - 1):
            if tc[i] > orh:
                brk = i
                break
        row = dict(date=dates[s], t_open=to[s], t_high=th[s:e].max(), t_low=tl[s:e].min(),
                   t_close=tc[e - 1], t_vol=tv[s:e].sum(), or_hi=orh, or_lo=orl,
                   or_vol=orv, or_ret=tc[s + j - 1] / to[s] - 1.0,
                   brk_i=brk, brk_min=tod[brk] if brk >= 0 else np.nan,
                   brk_px=to[brk + 1] if brk >= 0 and brk + 1 < e else np.nan,
                   brk_vol=tv[brk] if brk >= 0 else np.nan,
                   brk_vol_ratio=(tv[brk] / np.mean(or_bar_vol)) if brk >= 0 else np.nan,
                   q_at_brk=qc[brk] if brk >= 0 else np.nan,
                   q_or_hi=q["high"].to_numpy()[s:s + j].max(),
                   )
        rows.append(row)
    df = pd.DataFrame(rows)
    df["prev_close"] = df["t_close"].shift(1)
    df["gap"] = df["t_open"] / df["prev_close"] - 1.0
    tr = np.maximum(df["t_high"] - df["t_low"],
                    np.maximum((df["t_high"] - df["prev_close"]).abs(),
                               (df["t_low"] - df["prev_close"]).abs()))
    df["atr14"] = tr.shift(1).rolling(14).mean()
    df["or_width"] = (df["or_hi"] - df["or_lo"]) / df["t_open"]
    df["or_atr"] = df["or_width"] * df["t_open"] / df["atr14"]
    df["rvol"] = df["or_vol"] / df["or_vol"].shift(1).rolling(20).mean()
    df["q_confirm"] = df["q_at_brk"] > df["q_or_hi"]
    df.to_pickle(CACHE)
    return df


_MIN = None


def min_arrays():
    global _MIN
    if _MIN is None:
        ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                     warmup_days=100)
        t = bt.load_1m("TQQQ").set_index("ts").reindex(ts).ffill()
        dates = ts.date
        starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        ends = np.r_[starts[1:], len(ts)]
        day_of = {d: k for k, d in enumerate(dates[starts])}
        _MIN = dict(
            to=t["open"].to_numpy(), th=t["high"].to_numpy(),
            tl=t["low"].to_numpy(), tc=t["close"].to_numpy(),
            starts=starts, ends=ends, day_of=day_of, n=len(ts),
        )
    return _MIN


def trade_returns(df, stop_frac=None, target_frac=None, fail_exit=False,
                  eod=True):
    """Walk minutes from the signal bar; return per-event return with next-open fills."""
    M = min_arrays()
    to, th, tl, tc = M["to"], M["th"], M["tl"], M["tc"]
    out = np.full(len(df), np.nan)
    exit_type = np.full(len(df), "", dtype=object)
    for n, (_, r) in enumerate(df.iterrows()):
        if not np.isfinite(r["brk_px"]):
            continue
        k = M["day_of"][r["date"]]
        s, e = M["starts"][k], M["ends"][k]
        i0 = int(r["brk_i"]) + 1
        entry = r["brk_px"]
        stop = entry * (1 - stop_frac) if stop_frac else -np.inf
        target = entry * (1 + target_frac) if target_frac else np.inf
        px, kind = np.nan, "eod"
        for i in range(i0, e - 1):
            if tl[i] <= stop:
                px, kind = to[i + 1], "stop"
                break
            if th[i] >= target:
                px, kind = to[i + 1], "target"
                break
            if fail_exit and tc[i] < r["or_hi"]:
                px, kind = to[i + 1], "fail"
                break
        if not np.isfinite(px):
            px = to[e - 1]
        out[n] = px / entry - 1.0
        exit_type[n] = kind
    return out, exit_type


def summarize(x, label, n_sessions=2012, years=7.984):
    x = pd.Series(x).replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 10:
        print(f"{label:58s} n={len(x):4d} (thin)")
        return
    gm = np.exp(np.mean(np.log1p(x))) - 1
    print(f"{label:58s} n={len(x):4d} mean={x.mean()*100:6.3f}% med={x.median()*100:6.3f}% "
          f"win={np.mean(x>0)*100:5.1f}% gm={gm*100:6.3f}% "
          f"cagr={((1+gm)**(len(x)/years)-1)*100:6.2f}%")


def main():
    df = pd.read_pickle(CACHE) if CACHE.exists() else build()
    df = df[df["date"] >= pd.Timestamp(DEV_START).date()].reset_index(drop=True)
    b = df[df["brk_px"].notna()].reset_index(drop=True)

    print("=== breakout-bar volume ratio (mean hold-to-close return) ===")
    for lo, hi in ((0, .8), (.8, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)):
        g = b[b["brk_vol_ratio"].between(lo, hi)]
        summarize(g["t_close"] / g["brk_px"] - 1, f"  ratio {lo}-{hi}")

    # baseline path exits
    print("\n=== exit structures, all ORB ===")
    for stop in (None, .01, .015, .02, .03):
        for target in (None, .02, .03, .05):
            x, k = trade_returns(b, stop, target)
            summarize(x, f"  stop={stop} target={target}")
    x, k = trade_returns(b, None, None, fail_exit=True)
    summarize(x, "  fail-exit (close<ORH -> next open)")

    print("\n=== filtered subsets, selected exits ===")
    filters = {
        "gap>0": b["gap"] > 0,
        "gap>0 & rvol .9-1.2": (b["gap"] > 0) & b["rvol"].between(.9, 1.2),
        "gap>0 & or/atr .3-.45": (b["gap"] > 0) & b["or_atr"].between(.3, .45),
        "gap>0 & brkvol>1.5": (b["gap"] > 0) & (b["brk_vol_ratio"] > 1.5),
        "gap>0 & brkvol>1.5 & rvol .9-1.3":
            (b["gap"] > 0) & (b["brk_vol_ratio"] > 1.5) & b["rvol"].between(.9, 1.3),
        "gap>0 & q_confirm": (b["gap"] > 0) & b["q_confirm"],
        "gap>0.2% & q_confirm & rvol .9-1.2":
            (b["gap"] > .002) & b["q_confirm"] & b["rvol"].between(.9, 1.2),
    }
    for name, mask in filters.items():
        g = b[mask.fillna(False)].reset_index(drop=True)
        for stop, target in ((None, None), (.015, None), (None, .03), (.02, .04)):
            x, k = trade_returns(g, stop, target)
            summarize(x, f"  {name} stop={stop} tgt={target}")
        print()


if __name__ == "__main__":
    main()
