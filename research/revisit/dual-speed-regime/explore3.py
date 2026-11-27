"""Standalone 60m EMA: DD anatomy, ATR trailing stop, strength tiers (dev only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore import (DEV_START, DEV_END, BPY, day_index, bars_60m, ema, map_state,
                     weights_from_state, baseline_165, stats_dev)  # noqa: E402
from explore2 import hyst_state, map_weight  # noqa: E402


def episodes(ts, eq, top=4):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    i, n = 0, len(eq)
    while i < n:
        if dd[i] >= -1e-9:
            i += 1
            continue
        j = i
        while j < n and dd[j] < -1e-9:
            j += 1
        p = int(np.argmax(eq[: i + 1]))
        seg = dd[p:j]
        t = p + int(np.argmin(seg))
        out.append((float(-seg.min()), str(ts[p])[:10], str(ts[t])[:10]))
        i = j + 1
    out.sort(reverse=True)
    return out[:top]


def atr_state(bar_close, bar_up, k, atr_span=14):
    """EMA crossover with a trailing close-based ATR stop; re-enter on a fresh cross."""
    diff = np.abs(np.diff(bar_close, prepend=np.nan))
    atr = pd.Series(diff).rolling(atr_span).mean().to_numpy()
    on = False
    peak = np.nan
    prev_up = False
    out = np.zeros(len(bar_close), bool)
    for j in range(len(bar_close)):
        up = bool(bar_up[j])
        if not on:
            if up and not prev_up:
                on = True
                peak = bar_close[j]
        else:
            peak = max(peak, bar_close[j])
            if np.isfinite(atr[j]) and bar_close[j] < peak - k * atr[j]:
                on = False
        out[j] = on
        prev_up = up
    return out


def tier_weights(bar_close, fast_ema, slow_ema, strong=0.005, weak=0.0):
    """TQQQ when spread > strong, QQQ when weak < spread <= strong, BIL otherwise."""
    spread = fast_ema / slow_ema - 1.0
    wq = np.zeros(len(spread))
    wt = np.zeros(len(spread))
    for j, s in enumerate(spread):
        if not np.isfinite(s):
            continue
        if s > strong:
            wt[j] = 1.0
        elif s > weak:
            wq[j] = 1.0
    return wq, wt


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                                 warmup_days=500)
    dates, first, last, day_id = day_index(ts)
    ends, bar_close, day_of = bars_60m(closes[:, 0], first, last)
    w_base = baseline_165(ts, closes, first, last, day_id)
    sb, rb = stats_dev(w_base, ts, opens, closes)
    base_daily = pd.Series(rb["equity"], index=rb["ts"]).resample("1D").last().pct_change().dropna()

    def report(lab, w):
        s, r = stats_dev(w, ts, opens, closes)
        a = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()
        corr = float(pd.concat([a, base_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
        print(f"{lab:34s} CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.2f} "
              f"Sharpe {s['sharpe']:5.2f} fl {s['fills']:5d} corr {corr:.3f}", flush=True)
        return s, r

    print("== anatomy ==", flush=True)
    for fast, slow in ((10, 60), (15, 45), (10, 30), (20, 100)):
        ef, es = ema(bar_close, fast), ema(bar_close, slow)
        st = hyst_state(ef, es, 0.0)
        w = weights_from_state(map_state(len(ts), ends, day_of, st, first), 1)
        s, r = report(f"raw {fast}/{slow}", w)
        eq = pd.Series(r["equity"], index=r["ts"])
        print("   yearly: " + " ".join(
            f"{y}:{eq[eq.index.year == y].iloc[-1] / eq[eq.index.year == y].iloc[0] - 1:+.1%}"
            for y in range(2016, 2024)), flush=True)
        for e in episodes(r["ts"], r["equity"], 4):
            print(f"   DD {e[0]*100:5.2f}% {e[1]} -> {e[2]}", flush=True)

    print("\n== ATR trailing stop on raw cross, 10/60 and 15/45 ==", flush=True)
    for fast, slow in ((10, 60), (15, 45)):
        ef, es = ema(bar_close, fast), ema(bar_close, slow)
        up = ef > es
        for k in (2, 3, 4, 5, 6, 8):
            st = atr_state(bar_close, up, k)
            w = weights_from_state(map_state(len(ts), ends, day_of, st, first), 1)
            report(f"{fast}/{slow} ATRstop k{k}", w)

    print("\n== strength tiers (TQQQ > strong, QQQ > weak, else BIL) ==", flush=True)
    for fast, slow in ((10, 60), (15, 45)):
        ef, es = ema(bar_close, fast), ema(bar_close, slow)
        for strong in (0.002, 0.004, 0.007, 0.010):
            wq, wt = tier_weights(bar_close, ef, es, strong=strong, weak=0.0)
            w = np.zeros((len(ts), 3))
            w[:, 0] = map_weight(len(ts), ends, day_of, wq, first)
            w[:, 1] = map_weight(len(ts), ends, day_of, wt, first)
            w[:, 2] = 1.0 - w[:, 0] - w[:, 1]
            report(f"{fast}/{slow} tier strong{strong*100:.1f}%", w)


if __name__ == "__main__":
    main()
