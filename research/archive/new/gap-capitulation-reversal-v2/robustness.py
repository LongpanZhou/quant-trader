"""Robustness checks for gap-capitulation-reversal-v2 (dev window only).

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/gap-capitulation-reversal-v2/robustness.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

spec = importlib.util.spec_from_file_location("qcr_v2", HERE / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def cagr(r):
    return float(bt.stats(r, S.BARS_PER_YEAR)["cagr"])


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
    qlow, qvol = S._qqq_daily_extras()
    w, info = S.build_weights(ts, o, c, qlow, qvol)
    r = bt.run(ts, o, c, w, S.DEV_START, 0.02, 1.0)
    base = cagr(r)

    trades = sorted(S.trades_from_weights(ts, o, c, w),
                    key=lambda t: t["ret"], reverse=True)
    loo = {}
    for t in trades:
        i0 = int(ts.searchsorted(pd.Timestamp(t["entry"])))
        i1 = int(ts.searchsorted(pd.Timestamp(t["exit"]))) + 2
        wm = w.copy()
        wm[i0:i1, :] = 0
        wm[i0:i1, 2] = 1
        loo[f"{t['entry']}|{t['asset']}"] = cagr(
            bt.run(ts, o, c, wm, S.DEV_START, 0.02, 1.0))

    d = S.prepare_daily(ts, o, c, qlow, qvol)
    nd, n = d["nd"], len(ts)
    codes = np.zeros(nd, dtype=int)
    for k in range(nd):
        i = int(d["last"][k])
        if w[i, 1] > 0:
            codes[k] = 2
        elif w[i, 0] > 0:
            codes[k] = 1

    rng = np.random.default_rng(13)
    shifts = rng.integers(60, nd - 60, size=100)
    ws = []
    for sh in shifts:
        cc = np.roll(codes, int(sh))
        ww = np.zeros((n, 3))
        for k in range(nd):
            i0, i1 = int(d["first"][k]), int(d["last"][k]) + 1
            code = cc[k]
            if code == 2:
                ww[i0:i1, 1] = 1
            elif code == 1:
                ww[i0:i1, 0] = 1
            else:
                ww[i0:i1, 2] = 1
        ws.append(ww)
    rp = bt.run_many(ts, o, c, ws, S.DEV_START, 0.02, 1.0)
    pc = np.array([cagr(x) for x in rp])

    eq = pd.Series(r["equity"], index=r["ts"])
    de = eq.groupby(eq.index.date).last()
    dd = de / de.cummax() - 1.0
    trough = dd.idxmin()
    peak = de[:trough].idxmax()

    out = {
        "base_cagr": base,
        "max_dd_window": {"peak": str(peak), "trough": str(trough),
                          "daily_dd": float(dd.min())},
        "leave_one_trade_out": {
            "n": len(loo), "min": float(min(loo.values())),
            "max": float(max(loo.values())), "by_trade": loo},
        "placebo_circular_shift": {
            "n": int(len(pc)), "median_cagr": float(np.median(pc)),
            "p90_cagr": float(np.quantile(pc, 0.9)),
            "p_cagr_ge_strategy": float((pc >= base).mean())},
        "note": "Development window only; no 2024+ data loaded.",
    }
    (HERE / "robustness.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
