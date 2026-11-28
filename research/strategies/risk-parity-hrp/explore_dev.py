"""Dev-only exploration for the risk-parity rebuild (2016-01-04..2023-12-29).

No holdout data is loaded. Purpose: find an allocation rule whose daily returns
are genuinely different from the 165-day baseline (corr < 0.60).
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
BARS = 252 * 390


def build_targets(ts, opens, closes):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    dcl = closes[last]
    d = len(first)
    rets = np.diff(dcl, axis=0) / dcl[:-1]

    def lag(x):
        o = np.empty_like(x)
        o[0] = np.nan
        o[1:] = x[:-1]
        return o

    def roll_std(win):
        v = pd.DataFrame(rets).rolling(win).std().to_numpy() * np.sqrt(252)
        v = np.vstack([np.full((1, 3), np.nan), v])
        return lag(v)

    def roll_mean(win):
        v = pd.DataFrame(rets).rolling(win).mean().to_numpy() * 252
        v = np.vstack([np.full((1, 3), np.nan), v])
        return lag(v)

    return dict(dates=dates, first=first, last=last, dcl=dcl, d=d, rets=rets,
                lag=lag, vol=roll_std, mean=roll_mean)


def baseline_w(S):
    """165-day SMA baseline, for correlation only."""
    q = S["dcl"][:, 0]
    sma = pd.Series(q).rolling(165).mean().to_numpy()
    prev = S["lag"](sma)
    d = S["d"]
    tgt = np.zeros((d, 3))
    on = np.zeros(d, bool)
    on[1:] = q[:-1] > prev[1:]
    tgt[on, 1] = 1.0
    tgt[~on, 2] = 1.0
    return tgt, on


def expand(ts_dates, first, last, tgt):
    n = last[-1] + 1
    day = np.empty(n, dtype=int)
    day[first[0]:] = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    is_last = np.zeros(n, bool)
    is_last[last] = True
    idx = np.minimum(day + is_last.astype(int), len(first) - 1)
    w = np.empty((n, 3))
    w[:] = tgt[idx]
    return w


def daily_returns(ts, eq):
    s = pd.Series(eq, index=ts)
    e = s.groupby(s.index.date).last().to_numpy()
    return np.diff(e) / e[:-1]


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    print("bars", len(ts), ts[0], ts[-1])
    S = build_targets(ts, opens, closes)
    tgt_base, on = baseline_w(S)
    w_base = expand(S["dates"], S["first"], S["last"], tgt_base)
    r = bt.run(ts, opens, closes, w_base, DEV_START, band=0.0, slippage_bps=0.0)
    m = bt.stats(r, BARS)
    rb = daily_returns(r["ts"], r["equity"])
    print(f"baseline dev: CAGR {m['cagr']*100:.2f}% DD {m['max_drawdown']*100:.2f}% "
          f"vol {m['volatility']*100:.2f}% risk-on {on.mean()*100:.1f}%")

    def test(name, tgt):
        tgt = np.array(tgt, dtype=float)
        bad = ~np.isfinite(tgt).all(axis=1)
        tgt[bad] = (0.0, 0.0, 1.0)
        w = expand(S["dates"], S["first"], S["last"], tgt)
        res = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(res, BARS)
        rr = daily_returns(res["ts"], res["equity"])
        n = min(len(rr), len(rb))
        corr = np.corrcoef(rr[-n:], rb[-n:])[0, 1]
        print(f"{name:<38} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"vol {s['volatility']*100:5.2f}% Sh {s['sharpe']:4.2f} "
              f"corr {corr:5.2f} fills {s['fills']:4d}")
        return corr

    d = S["d"]
    v20 = S["vol"](20)
    v60 = S["vol"](60)

    print("\n--- static / always-invested pairs ---")
    for wt in (1.0, 0.75, 0.5, 0.25):
        t = np.zeros((d, 3)); t[:, 1] = wt; t[:, 0] = 1 - wt
        test(f"static TQQQ {wt:.2f}", t)

    print("\n--- inverse-vol within QQQ/TQQQ (ERC) ---")
    for win in (20, 60):
        v = S["vol"](win)
        t = np.zeros((d, 3))
        t[:, 1] = np.clip(v[:, 0] / (v[:, 0] + v[:, 1]), 0, 1)
        t[:, 0] = 1 - t[:, 1]
        test(f"ERC QQQ/TQQQ win={win}", t)

    print("\n--- vol target on TQQQ with QQQ remainder (no gate) ---")
    for win in (20, 60):
        v = S["vol"](win)
        for tv in (0.60, 0.45, 0.30, 0.20):
            t = np.zeros((d, 3))
            t[:, 1] = np.clip(tv / v[:, 1], 0, 1)
            t[:, 0] = 1 - t[:, 1]
            test(f"voltarget tv={tv:.2f} win={win}", t)

    print("\n--- vol target with hard cash switch ---")
    for win in (20, 60):
        v = S["vol"](win)
        for thr in (0.90, 1.10, 1.40):
            t = np.zeros((d, 3))
            t[:, 1] = np.clip(0.60 / v[:, 1], 0, 1)
            t[:, 0] = 1 - t[:, 1]
            off = v[:, 1] > thr
            t[off] = [0, 0, 1]
            test(f"tv60 + off if vol>{thr:.2f} win={win}", t)

    print("\n--- contrarian vol-ratio tilt ---")
    for win_s, win_l in ((5, 60), (10, 120)):
        vs, vl = S["vol"](win_s), S["vol"](win_l)
        ratio = vl[:, 1] / vs[:, 1]
        for tv in (0.45, 0.30):
            t = np.zeros((d, 3))
            base = np.clip(tv / vl[:, 1], 0, 1)
            tilt = np.clip(ratio, 0.5, 2.0)
            wt = np.clip(base * tilt, 0, 1)
            t[:, 1] = wt
            t[:, 0] = 1 - wt
            test(f"contrarian {win_s}/{win_l} tv={tv}", t)


if __name__ == "__main__":
    main()
