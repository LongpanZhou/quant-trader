"""Range-compression family: NR7 / inside-session compression -> expansion.

Development window only: 2016-01-04 .. 2023-12-29.

Signal at the 15:59 close:
    rng[d] = (QQQ_session_high - QQQ_session_low) / QQQ_close[d]
    nr7[d] = rng[d] < min(rng[d-7 .. d-1])
If nr7, buy TQQQ at the next open and hold 3 sessions; otherwise BIL.
No trend gate, vol target, calendar window, opening range or ML.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent
PARAMS = dict(look=7, hold=3)


def session_ranges(ts, o, c):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    qh = np.array([c[first[i]:last[i] + 1, 0].max() for i in range(n)])
    ql = np.array([c[first[i]:last[i] + 1, 0].min() for i in range(n)])
    qc = c[last, 0]
    return (qh - ql) / np.maximum(qc, 1e-12)


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    _, first, last = bt.day_bounds(ts)
    nd = len(first)
    rng = session_ranges(ts, o, c)
    look, hold = int(p["look"]), int(p["hold"])
    target = np.zeros(nd)
    for d in range(look + 1, nd):
        if rng[d] < rng[d - look:d].min():
            target[d] = 1.0
    pos = np.zeros(nd)
    until = -1
    for d in range(nd):
        if target[d] > 0:
            until = max(until, d + hold)
        if d < until:
            pos[d] = 1.0
    n = len(ts)
    w = np.zeros((n, 3))
    prev = 0.0
    for d in range(nd):
        a, b = int(first[d]), int(last[d])
        w[a:b + 1, 1] = prev
        w[a:b + 1, 2] = 1.0 - prev
        w[b, 1] = pos[d]
        w[b, 2] = 1.0 - pos[d]
        prev = pos[d]
    info = {
        "params": p,
        "signals": int((target > 0).sum()),
        "active_sessions": int((pos > 0).sum()),
        "tqqq_exposure": float(pos.mean()),
    }
    return w, info


def stats(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                    "volatility", "exposure", "turnover", "fills",
                                    "ending_equity", "years")}


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w, info = build_weights(ts, o, c)
    out = {
        "slug": "family-range-compression",
        "family": "range-compression",
        "idea": "NR7/inside-session range compression precedes an expansion move.",
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "rules": "QQQ session range < min prior 7 ranges -> TQQQ next open, hold 3 sessions; else BIL.",
        "params": info["params"],
        "info": info,
        "dev": {f"{b}bp": stats(w, ts, o, c, b) for b in (1, 5, 10)},
        "grid": [],
    }
    for look in (5, 7, 9):
        for hold in (2, 3, 4):
            ww, _ = build_weights(ts, o, c, dict(look=look, hold=hold))
            out["grid"].append({"look": look, "hold": hold, **stats(ww, ts, o, c, 1)})
    (OUT / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    d = out["dev"]["1bp"]
    print(f"dev {d['cagr']*100:.2f}% CAGR {d['max_drawdown']*100:.2f}% DD "
          f"{d['sharpe']:.2f} Sharpe fills {int(d['fills'])} exposure {d['exposure']*100:.1f}%")
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
