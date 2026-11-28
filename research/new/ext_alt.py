"""Four low-overlap families from unused external dimensions.

  skew-change      : 20-session change in CBOE SKEW (tail-risk pricing)
  vvix-ratio       : VVIX / VIX (vol-of-vol premium)
  sector-dispersion: cross-sectional dispersion of 10 sector ETFs
  breakeven        : 60-session TIP/IEF change (inflation compensation)

Signals use a 252-session percentile rank shifted one session, then fill at the
next QQQ open.  Primary directions are pre-registered from the economics:
  - rising tail-risk pricing / vol-of-vol panic -> contrarian TQQQ
  - low sector dispersion (broad macro move) -> TQQQ
  - rising TIP/IEF (easier real rates) -> TQQQ
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
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE"]

KINDS = {
    "skew_change": dict(look=20, low=0.45, high=0.55, flip=True),
    "vvix_ratio": dict(look=252, low=0.45, high=0.55, flip=True),
    "sector_dispersion": dict(look=10, low=0.45, high=0.55, flip=False),
    "breakeven": dict(look=10, low=0.45, high=0.55, flip=True),
    "efa_spy": dict(look=60, low=0.45, high=0.55, flip=True),
    "qual_spy": dict(look=60, low=0.45, high=0.55, flip=True),
    "mtum_spy": dict(look=60, low=0.45, high=0.55, flip=False),
    "hyg_spy": dict(look=20, low=0.45, high=0.55, flip=False),
}
GRID_LOOKS = {
    "skew_change": (10, 20, 40),
    "sector_dispersion": (10, 20, 40),
    "breakeven": (10, 20, 40),
    "efa_spy": (40, 60, 90),
    "qual_spy": (40, 60, 90),
    "mtum_spy": (40, 60, 90),
    "hyg_spy": (10, 20, 40),
}


def raw_signal(ts, kind, look):
    if kind == "skew_change":
        s = external.align(ts, ["^SKEW"])["^SKEW"]
        return s.diff(int(look))
    if kind == "vvix_ratio":
        d = external.align(ts, ["^VVIX", "^VIX"])
        return d["^VVIX"] / d["^VIX"]
    if kind == "sector_dispersion":
        sec = external.align(ts, SECTORS)
        return sec.pct_change().std(axis=1).rolling(int(look), min_periods=10).mean()
    if kind == "breakeven":
        d = external.align(ts, ["TIP", "IEF"])
        return np.log(d["TIP"] / d["IEF"]).diff(int(look))
    if kind == "efa_spy":
        d = external.align(ts, ["EFA", "SPY"])
        return np.log(d["EFA"] / d["SPY"]).diff(int(look))
    if kind == "qual_spy":
        d = external.align(ts, ["QUAL", "SPY"])
        return np.log(d["QUAL"] / d["SPY"]).diff(int(look))
    if kind == "mtum_spy":
        d = external.align(ts, ["MTUM", "SPY"])
        return np.log(d["MTUM"] / d["SPY"]).diff(int(look))
    if kind == "hyg_spy":
        d = external.align(ts, ["HYG", "SPY"])
        return np.log(d["HYG"] / d["SPY"]).diff(int(look))
    raise KeyError(kind)


def state_from_signal(x, low, high, flip):
    pct = (pd.Series(x).rolling(252, min_periods=120).rank(pct=True).shift(1)
           .to_numpy())
    state = np.zeros(len(pct))
    prev = 1.0
    for i, v in enumerate(pct):
        if np.isfinite(v):
            if v < low:
                prev = 1.0
            elif v > high:
                prev = 0.0
        state[i] = prev
    return 1.0 - state if flip else state


def make_weights(ts, o, c, kind, params=None):
    p = dict(KINDS[kind])
    if params:
        p.update(params)
    x = raw_signal(ts, kind, int(p["look"]))
    state = state_from_signal(x, float(p["low"]), float(p["high"]), bool(p["flip"]))
    targets = np.zeros((len(state), 3))
    targets[:, 1] = state
    targets[:, 2] = 1.0 - state
    w = external.daily_targets_to_weights(ts, targets)
    return w, {"params": p, "tqqq_exposure": float(state.mean()),
               "switches": int((np.diff(state) != 0).sum()),
               "events": int((np.diff(state) != 0).sum() / 2)}


def stats(w, ts, o, c, bps):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bps)
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "exposure", "turnover", "fills",
                                     "ending_equity", "years")}


def run_main(kind):
    slug = "family-" + kind.replace("_", "-")
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END,
                        "1min", warmup_days=0)
    w, info = make_weights(ts, o, c, kind)
    out = {"slug": slug, "family": slug.removeprefix("family-"),
           "idea": f"{kind} external gate",
           "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
           "params": info["params"], "info": info,
           "dev": {f"{b}bp": stats(w, ts, o, c, b) for b in (1, 5, 10)},
           "grid": []}
    for look in GRID_LOOKS[kind]:
        for low, high in ((0.40, 0.60), (0.45, 0.55)):
            p = dict(look=look, low=low, high=high)
            ww, ii = make_weights(ts, o, c, kind, p)
            out["grid"].append({"look": look, "low": low, "high": high,
                                "events": ii["events"], **stats(ww, ts, o, c, 1)})
    (OUT / slug / "result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["dev"]["1bp"]
    print(f"{slug} dev {s['cagr']*100:.2f}% CAGR {s['max_drawdown']*100:.2f}% DD "
          f"{s['sharpe']:.2f} Sharpe fills {int(s['fills'])} events {info['events']}")
