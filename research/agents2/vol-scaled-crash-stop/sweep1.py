"""Screen volatility-scaled stops and partial de-risking (10y, 1 bp).

Writes measures.npz (per-day stop-distance candidates) next to this file so the
final strategy does not have to recompute them.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/sweep1.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390


def load_cache():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(
        pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
    )
    return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def build_measures(ts, opens, highs, lows, closes):
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    t_high = np.maximum.reduceat(highs[:, 1], first)
    t_low = np.minimum.reduceat(lows[:, 1], first)
    t_close = closes[last, 1]

    prev_close = np.r_[np.nan, t_close[:-1]]
    tr = np.maximum.reduce(
        [t_high - t_low, np.abs(t_high - prev_close), np.abs(t_low - prev_close)]
    )
    atr14 = pd.Series(tr).rolling(14).mean().to_numpy() / t_close

    r1 = np.diff(np.log(t_close), prepend=np.nan)
    vol20 = pd.Series(r1).rolling(20).std(ddof=0).to_numpy()

    r1m = np.zeros(len(ts))
    r1m[1:] = np.diff(np.log(closes[:, 1]))
    r1m[first] = 0.0
    nb = np.diff(np.r_[first, len(ts)]).astype(float)
    sess_var = np.add.reduceat(r1m ** 2, first) / np.maximum(nb, 1)
    sigma1m_day = np.sqrt(sess_var * 390.0)

    atr5 = np.full(len(first), np.nan)
    for k, (f, l) in enumerate(zip(first, last)):
        n5 = (l - f + 1) // 5
        if n5 < 15:
            continue
        h = highs[f:f + n5 * 5, 1].reshape(n5, 5).max(axis=1)
        lo = lows[f:f + n5 * 5, 1].reshape(n5, 5).min(axis=1)
        c = closes[f:f + n5 * 5, 1].reshape(n5, 5)[:, -1]
        pc = np.r_[np.nan, c[:-1]]
        t5 = np.maximum.reduce([h - lo, np.abs(h - pc), np.abs(lo - pc)])
        atr5[k] = pd.Series(t5).rolling(14).mean().to_numpy()[-1] / c[-1]

    # all shifted one day: only prior-close information available for session k
    sh = lambda x: np.r_[np.nan, x[:-1]]
    out = dict(
        atr14=sh(atr14), vol20=sh(vol20), sigma1m=sh(sigma1m_day), atr5=sh(atr5),
        dates=dates, first=first, last=last, t_close=t_close,
    )
    np.savez_compressed(
        HERE / "measures.npz",
        atr14=out["atr14"], vol20=out["vol20"], sigma1m=out["sigma1m"],
        atr5=out["atr5"],
    )
    return out


def regime_arrays(ts, closes, first, last, sma_n=165, ma_fast=20, arm_buf=0.01):
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    k = np.arange(len(first))
    ok = k > 0
    risk_on = np.zeros(len(first), bool)
    risk_on[ok] = dc[:-1] > sma_prev[1:]  # dc[-1] vs sma computed through prior close
    armed = np.zeros(len(first), bool)
    armed[ok] = closes[first, 0][ok] < ma20_prev[ok] * (1 + arm_buf)
    return risk_on, armed, dc


def build_weights(ts, opens, closes, first, last, risk_on, armed, dist,
                  alloc1=(0.0, 0.0, 1.0), alloc2=None, stage2_mult=1.5,
                  intraday_only=False):
    """Generic stop engine.

    dist[k]     stop distance from session open for day k (fraction)
    alloc1      weights after first stop (default 100% BIL)
    alloc2      weights after second stop (None -> single stage)
    intraday_only: revert alloc1 to BIL at the last tradeable bar (out overnight)
    """
    n = len(ts)
    w = np.zeros((n, 3))
    alloc1 = np.asarray(alloc1, float)
    alloc2 = None if alloc2 is None else np.asarray(alloc2, float)
    nstops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k]:
            w[f:l + 1, 2] = 1.0
            continue
        base = opens[f, 1]
        d = dist[k]
        stage = 0
        for i in range(f, l + 1):
            if stage == 0:
                w[i, 1] = 1.0
                if armed[k] and d == d and closes[i, 1] < base * (1.0 - d):
                    stage = 1
                    nstops += 1
                    w[i, :] = alloc1
            elif stage == 1:
                w[i, :] = alloc1
                if alloc2 is not None and d == d and closes[i, 1] < base * (1.0 - stage2_mult * d):
                    stage = 2
                    w[i, :] = alloc2
            else:
                w[i, :] = alloc2
        if intraday_only and stage >= 1 and l - f >= 3:
            w[l - 1, :] = (0.0, 0.0, 1.0)  # fills at 15:59 open
    return w, nstops


def run_one(label, ts, opens, closes, w, window="10y", slip=1.0):
    start = START10 if window == "10y" else START5
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    return s


def fmt(s):
    return f"CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}  fills {s['fills']:5,d}"


def main():
    t0 = time.time()
    ts, opens, highs, lows, closes, vols = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    dates, first, last = m["dates"], m["first"], m["last"]
    risk_on, armed, dc = regime_arrays(ts, closes, first, last)
    print(f"setup {time.time()-t0:.1f}s  days={len(first)} risk_on={risk_on.mean()*100:.1f}% "
          f"armed_days={armed.mean()*100:.1f}%")

    n = len(ts)
    fixed4 = np.full(len(first), 0.04)
    variants = []

    variants.append(("winner 4% -> BIL", fixed4, (0, 0, 1), None, 1.5, False))
    for k in (0.7, 0.85, 1.0, 1.2):
        d = np.clip(k * m["atr14"], 0.025, 0.06)
        variants.append((f"ATR14 x{k:.2f} -> BIL", d, (0, 0, 1), None, 1.5, False))
    for k in (1.0, 1.2, 1.4, 1.6):
        d = np.clip(k * m["vol20"], 0.03, 0.06)
        variants.append((f"vol20 x{k:.2f} -> BIL", d, (0, 0, 1), None, 1.5, False))
    for k in (1.5, 1.8, 2.1):
        d = np.clip(k * m["sigma1m"], 0.03, 0.06)
        variants.append((f"1mvol x{k:.2f} -> BIL", d, (0, 0, 1), None, 1.5, False))
    for k in (7.0, 9.0, 11.0):
        d = np.clip(k * m["atr5"], 0.025, 0.06)
        variants.append((f"ATR5m x{k:.0f} -> BIL", d, (0, 0, 1), None, 1.5, False))

    variants.append(("4% -> 50 QQQ/BIL", fixed4, (0.5, 0.0, 0.5), None, 1.5, False))
    variants.append(("4% -> 50 QQQ intraday only", fixed4, (0.5, 0.0, 0.5), None, 1.5, True))
    variants.append(("4% -> 50 TQQQ/BIL", fixed4, (0.0, 0.5, 0.5), None, 1.5, False))
    variants.append(("4%: 50QQQ@4%, BIL@8%", fixed4, (0.5, 0.0, 0.5), (0, 0, 1), 2.0, False))

    print(f"\n{'variant':34s} {'stops':>5s}  10y metrics")
    rows = []
    for label, d, a1, a2, s2, io in variants:
        t1 = time.time()
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed, d,
                              alloc1=a1, alloc2=a2, stage2_mult=s2, intraday_only=io)
        s = run_one(label, ts, opens, closes, w, "10y", 1.0)
        rows.append((label, ns, s))
        print(f"{label:34s} {ns:5d}  {fmt(s)}   [{time.time()-t1:.0f}s]")

    print("\nmedian stop distance by variant (%), 2017 vs 2020 vs 2022 vs 2026")
    yrs = np.array([d.year for d in dates])
    for label, d, *_ in variants[:14]:
        med = []
        for y in (2017, 2020, 2022, 2026):
            med.append(np.nanmedian(d[yrs == y]) * 100)
        print(f"  {label:34s} " + "  ".join(f"{v:5.2f}" for v in med))


if __name__ == "__main__":
    main()
