"""Three style/FX families replacing correlated macro betas.

Primary objects:
  yen    : USDJPY 60-session change (yen carry / safe-haven unwind)
  style  : IWF/IWD growth-vs-value leadership
  lowvol : USMV/SPY low-vol-vs-market leadership
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import external  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
OUT = Path(__file__).resolve().parent

KINDS = {
    "yen": dict(look=40, enter=0.0, exit=0.0, symbols=["JPY=X"]),
    "style": dict(look=40, enter=0.0, exit=0.0, symbols=["IWF", "IWD"]),
    "lowvol": dict(look=60, enter=-0.01, exit=0.01, symbols=["USMV", "SPY"]),
}


def _state(kind, d, look, enter, exit):
    if kind == "yen":
        x = d["JPY=X"] / d["JPY=X"].shift(look) - 1.0
        # risk-on when USDJPY stable/rising; risk-off on sharp yen strength
        s = np.zeros(len(x))
        prev = 1.0
        for i, v in enumerate(x.to_numpy()):
            if np.isfinite(v):
                if v > enter:
                    prev = 1.0
                elif v < exit:
                    prev = 0.0
            s[i] = prev
        return s
    left, right = d.columns[0], d.columns[1]
    rel = np.log(d[left] / d[right])
    x = rel - rel.shift(look)
    s = np.zeros(len(x))
    prev = 1.0
    for i, v in enumerate(x.to_numpy()):
        if np.isfinite(v):
            if v > enter:
                prev = 1.0
            elif v < exit:
                prev = 0.0
        s[i] = prev
    return s


def make_weights(ts, o, c, kind, params=None):
    p = dict(KINDS[kind])
    if params:
        p.update(params)
    d = external.align(ts, p["symbols"])
    s = _state(kind, d, int(p["look"]), float(p["enter"]), float(p["exit"]))
    targets = np.zeros((len(s), 3))
    targets[:, 1] = s
    targets[:, 2] = 1.0 - s
    w = external.daily_targets_to_weights(ts, targets)
    return w, {"params": p, "tqqq_exposure": float(s.mean()),
               "switches": int((np.diff(s) != 0).sum())}


def _stats(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    st = bt.stats(r, BPY)
    return {k: float(st[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "exposure", "turnover", "fills",
                                     "ending_equity", "years")}


def run_main(kind):
    slug = f"family-{ {'yen':'yen-carry','style':'style-rotation','lowvol':'lowvol-rotation'}[kind] }"
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    w, info = make_weights(ts, o, c, kind)
    out = {"slug": slug, "family": slug.removeprefix("family-"),
           "idea": f"{kind} style/FX primary object",
           "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
           "params": info["params"], "info": info,
           "dev": {f"{b}bp": _stats(w, ts, o, c, b) for b in (1, 5, 10)},
           "grid": []}
    look, enter, exit = int(info["params"]["look"]), float(info["params"]["enter"]), float(info["params"]["exit"])
    for lk in (40, 60, 90):
        for en, ex in ((enter, exit), (0.0, -0.0)):
            ww, _ = make_weights(ts, o, c, kind, dict(look=lk, enter=en, exit=ex))
            out["grid"].append({"look": lk, "enter": en, "exit": ex, **_stats(ww, ts, o, c, 1)})
    (OUT / slug / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["dev"]["1bp"]
    print(f"{slug} dev {s['cagr']*100:.2f}% CAGR {s['max_drawdown']*100:.2f}% DD "
          f"{s['sharpe']:.2f} Sharpe fills {int(s['fills'])}")
