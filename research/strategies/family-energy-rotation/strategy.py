"""Energy-vs-tech rotation: XLE/XLK relative momentum as an inflation signal.

Development window only.  Signal at session d close; TQQQ at d+1 open.
If energy is leading technology over 20 sessions, treat it as inflation/commodity
stress and hold BIL; otherwise hold TQQQ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import external  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent
PARAMS = dict(look=20, deadband=0.0)


def build_weights(ts, o, c, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    d = external.align(ts, ["XLE", "XLK"])
    ratio = d["XLE"] / d["XLK"]
    mom = ratio / ratio.shift(int(p["look"])) - 1.0
    state = np.zeros(len(d))
    state[mom.to_numpy() <= float(p["deadband"])] = 1.0
    targets = np.zeros((len(d), 3))
    targets[:, 1] = state
    targets[:, 2] = 1.0 - state
    w = external.daily_targets_to_weights(ts, targets)
    info = {"params": p, "tqqq_exposure": float(state.mean()),
            "signals": int((np.diff(state) != 0).sum())}
    return w, info


def run(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                    "volatility", "exposure", "turnover", "fills",
                                    "ending_equity", "years")}


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w, info = build_weights(ts, o, c)
    out = {"slug": "family-energy-rotation", "family": "energy-rotation",
           "idea": "Energy-vs-tech leadership as an inflation/commodity-stress signal.",
           "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
           "rules": "XLE/XLK 20-session relative momentum <= 0 -> TQQQ next open; else BIL.",
           "params": info["params"], "info": info,
           "dev": {f"{b}bp": run(w, ts, o, c, b) for b in (1, 5, 10)}}
    out["grid"] = []
    for look in (10, 20, 40):
        for band in (0.0, 0.01):
            ww, _ = build_weights(ts, o, c, dict(look=look, deadband=band))
            out["grid"].append({"look": look, "deadband": band, **run(ww, ts, o, c, 1)})
    (OUT / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["dev"]["1bp"]
    print(f"dev {s['cagr']*100:.2f}% CAGR {s['max_drawdown']*100:.2f}% DD "
          f"{s['sharpe']:.2f} Sharpe fills {int(s['fills'])}")


if __name__ == "__main__":
    main()
