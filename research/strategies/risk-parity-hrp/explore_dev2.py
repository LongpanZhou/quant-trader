"""Dev-only exploration 2: can a risk-allocation rule get corr < 0.60 vs the base?

The baseline censors TQQQ's worst days (it is in BIL 26% of sessions). Every
always-invested equity mix lands at 0.71-0.83. To decorrelate, the risk budget
must be long on a different subset of days, so test reversal-tilted risk
budgets (add risk after declines, cut after rallies) and asymmetric vol.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
from explore_dev import build_targets, baseline_w, expand, daily_returns  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    S = build_targets(ts, opens, closes)
    tgt_base, on = baseline_w(S)
    wb = expand(S["dates"], S["first"], S["last"], tgt_base)
    rb = bt.run(ts, opens, closes, wb, DEV_START, band=0.0, slippage_bps=0.0)
    rbase = daily_returns(rb["ts"], rb["equity"])
    d = S["d"]
    q = S["dcl"][:, 0]
    rets = S["rets"]
    v20 = S["vol"](20)
    v60 = S["vol"](60)

    def ret(win):
        x = pd.Series(q).pct_change(win).to_numpy()
        return S["lag"](x)

    def test(name, tgt, slip=1.0):
        tgt = np.array(tgt, float)
        tgt[~np.isfinite(tgt).all(axis=1)] = (0.0, 0.0, 1.0)
        w = expand(S["dates"], S["first"], S["last"], tgt)
        res = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(res, BARS)
        rr = daily_returns(res["ts"], res["equity"])
        n = min(len(rr), len(rbase))
        corr = np.corrcoef(rr[-n:], rbase[-n:])[0, 1]
        print(f"{name:<42} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"vol {s['volatility']*100:5.2f}% Sh {s['sharpe']:4.2f} "
              f"corr {corr:5.2f} fills {s['fills']:4d}")
        return corr

    def erc_sleeve(v, tv, tilt=None):
        """inverse-vol QQQ/TQQQ sleeve, scaled to a vol target, optional tilt."""
        t = np.zeros((d, 3))
        wT = np.clip(v[:, 0] / (v[:, 0] + v[:, 1]), 0, 1)
        # sleeve vol under near-perfect correlation = wT*sT + (1-wT)*sQ
        s = wT * v[:, 1] + (1 - wT) * v[:, 0]
        e = np.clip(tv / s, 0, 1)
        if tilt is not None:
            e = np.clip(e * tilt, 0, 1)
        t[:, 1] = e * wT
        t[:, 0] = e * (1 - wT)
        t[:, 2] = 1 - e
        return t

    print("--- pure ERC to a 45% vol target (reference) ---")
    test("ERC45 win20", erc_sleeve(v20, 0.45))
    test("ERC45 win60", erc_sleeve(v60, 0.45))

    print("\n--- reversal tilt on the risk budget: g=1-k*r5 ---")
    for win in (5, 10, 20):
        r = ret(win)
        for k in (2.0, 4.0, 6.0):
            g = np.clip(1.0 - k * r, 0.25, 1.75)
            test(f"ERC45 tilt r{win} k={k:.0f}", erc_sleeve(v20, 0.45, g))

    print("\n--- dip-buy risk budget: g=1+k*max(0,-r5) ---")
    for win in (5, 10):
        r = ret(win)
        for k in (5.0, 10.0):
            g = np.clip(1.0 + k * np.maximum(0.0, -r), 0.5, 2.5)
            test(f"ERC45 dip r{win} k={k:.0f}", erc_sleeve(v20, 0.45, g))

    print("\n--- asymmetric vol: downside vol vs upside vol ---")
    dn = pd.DataFrame(np.minimum(rets, 0.0)).rolling(20).std().to_numpy() * np.sqrt(252)
    dn = S["lag"](np.vstack([np.full((1, 3), np.nan), dn]))
    up = pd.DataFrame(np.maximum(rets, 0.0)).rolling(20).std().to_numpy() * np.sqrt(252)
    up = S["lag"](np.vstack([np.full((1, 3), np.nan), up]))
    for tv in (0.45, 0.35):
        t = np.zeros((d, 3))
        wT = np.clip(v20[:, 0] / (v20[:, 0] + v20[:, 1]), 0, 1)
        s = wT * v20[:, 1] + (1 - wT) * v20[:, 0]
        e = np.clip(tv / s, 0, 1)
        t[:, 1] = e * wT
        t[:, 0] = e * (1 - wT)
        t[:, 2] = 1 - e
        test(f"ERC{tv:.2f} asym vol", t)

    print("\n--- risk budget follows realised Sharpe (60d mean/vol) ---")
    mu = S["mean"](60)
    sh = mu / v60
    for tv in (0.45,):
        for k in (2.0, 4.0):
            g = np.clip(1.0 + k * sh[:, 0], 0.5, 2.0)
            test(f"ERC45 sharpe-tilt k={k:.0f}", erc_sleeve(v20, tv, g))

    print("\n--- half risk-parity core + half dip sleeve ---")
    r5 = ret(5)
    core = erc_sleeve(v20, 0.45)
    dip = erc_sleeve(v20, 0.45, np.clip(1.0 + 8.0 * np.maximum(0.0, -r5), 0.5, 2.5))
    for a in (0.5, 0.7):
        test(f"mix core/dip a={a}", a * core + (1 - a) * dip)


if __name__ == "__main__":
    main()
