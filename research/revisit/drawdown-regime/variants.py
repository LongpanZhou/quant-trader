"""Tune 2026-11-27: sizing variants on top of the spec-fixed DDR (dev only).

V1: scale the TQQQ window by min(1, vol_target / realised 20-session TQQQ vol),
    realised vol from daily closes through session k-1. Targets 40/60/80%.
V2: 50/50 TQQQ/QQQ in the window (half the leverage).
    python research/revisit/drawdown-regime/variants.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
from tune import metrics  # noqa: E402
bt = S.bt


def main():
    ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
    dates, first, last = S._sessions(ts)
    rbd = S._daily_returns(bt.run(ts, o, c, S.baseline_weights(ts, c), S.DEV_START, 0.02, 1.0))
    w, info = S.build_weights(ts, o, c)
    T = info["targets"]
    print("exposure (session share in window):", round(T.mean(), 4))

    tq = pd.Series(c[last, 1])
    vol = (np.log(tq).diff().rolling(20).std() * np.sqrt(252)).to_numpy()
    vol_prev = np.r_[np.nan, vol[:-1]]          # known at session k's open
    ws, names = [w], ["DDR spec-fixed"]
    for vt in (0.4, 0.6, 0.8):
        scale = np.where(np.isfinite(vol_prev), np.minimum(1.0, vt / vol_prev), 1.0)
        ws.append(S.weights_from_targets(T * scale, first, last, 1)); names.append(f"V1 voltarget {vt:.0%}")
    wb = S.weights_from_targets(T, first, last, 1)
    wb[:, 0] = wb[:, 1] * 0.5; wb[:, 1] *= 0.5
    ws.append(wb); names.append("V2 50/50 TQQQ/QQQ")
    rs = bt.run_many(ts, o, c, ws, S.DEV_START, 0.02, 1.0)
    for n, r in zip(names, rs):
        m = metrics(r, rbd)
        print(f"{n:22s} CAGR {m['cagr']*100:6.2f}% DD {m['max_drawdown']*100:5.1f}% Sh {m['sharpe']:.2f} "
              f"corr {m['corr165']:.2f} | " +
              " ".join(f"{k} {m[k]['cagr']*100:5.1f}%/{m[k]['dd']*100:4.1f}%" for k in ("2016-19", "2020-21", "2022-23")))


if __name__ == "__main__":
    main()
