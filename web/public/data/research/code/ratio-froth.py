"""Ratio-froth: frozen wrapper around the legacy ratio-pairs strategy.

Base: QQQ close > 165-day SMA -> TQQQ, else BIL; 4% intraday stop.
Overlay: hold QQQ instead of TQQQ while the prior close's log(TQQQ/QQQ ratio /
200-day MA) > 0.18.  The wrapper exists so the shared holdout/audit runner can
load the frozen strategy from `research/agents2/ratio-pairs/strategy.py`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py"
spec = importlib.util.spec_from_file_location("ratio_pairs_base", BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def build_weights(ts, o, c):
    return base.build_weights(ts, o, c)
