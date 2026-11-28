"""Low-overlap sector/commodity families replacing high-Jaccard names."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import external  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent

KINDS = {
    "homebuilder": dict(look=60, symbols=["XHB", "SPY"]),
    "financials": dict(look=60, symbols=["XLF", "XLK"]),
    "natgas": dict(look=20, symbols=["UNG", "USO"]),
    "retail": dict(look=60, symbols=["XRT", "SPY"]),
}


def make_weights(ts, o, c, kind, params=None):
    p = dict(KINDS[kind])
    if params:
        p.update(params)
    d = external.align(ts, p["symbols"])
    a, b = d.columns[0], d.columns[1]
    rel = np.log(d[a] / d[b])
    x = rel - rel.shift(int(p["look"]))
    if kind == "natgas":
        # gas shock relative to oil -> inflation/energy stress -> BIL
        state = (x < 0.08).astype(float).to_numpy()
    else:
        # cyclical/industry leadership -> risk-on TQQQ
        state = (x > 0.0).astype(float).to_numpy()
    state = np.where(np.isfinite(state), state, 1.0)
    targets = np.zeros((len(state), 3))
    targets[:, 1] = state
    targets[:, 2] = 1.0 - state
    w = external.daily_targets_to_weights(ts, targets)
    return w, {"params": p, "tqqq_exposure": float(state.mean()),
               "switches": int((np.diff(state) != 0).sum())}


def stats(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "exposure", "turnover", "fills",
                                     "ending_equity", "years")}


def run_main(kind):
    slug = f"family-{ {'homebuilder':'homebuilder-rotation','financials':'financials-rotation','natgas':'natural-gas-shock','retail':'retail-rotation'}[kind] }"
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w, info = make_weights(ts, o, c, kind)
    out = {"slug": slug, "family": slug.removeprefix("family-"),
           "idea": f"{kind} sector/commodity gate",
           "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
           "params": info["params"], "info": info,
           "dev": {f"{b}bp": stats(w, ts, o, c, b) for b in (1, 5, 10)}}
    (OUT / slug / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["dev"]["1bp"]
    print(f"{slug} dev {s['cagr']*100:.2f}% CAGR {s['max_drawdown']*100:.2f}% DD "
          f"{s['sharpe']:.2f} Sharpe fills {int(s['fills'])}")
