"""Nasdaq Leveraged Trend: Python version of the rule the Rust bot trades from `bot.toml` in this folder.

QQQ above its 165-day average -> a QQQ/TQQQ blend sized to a 40% annualised volatility target; below it -> BIL.

The rule lives in `research/strategies/leveraged_index.py`, a line-for-line
port of `LeveragedIndex` in `src/strategy.rs`.  This file only pins the
bot.toml parameters.  Daily strategy: run it with

    python research/strategies/run_holdout.py nasdaq-leveraged-trend --daily
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "leveraged_index.py"
_spec = importlib.util.spec_from_file_location("leveraged_index", _PATH)
leveraged_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(leveraged_index)

PARAMS = {"sma_days": 165, "target_vol": 0.40, "vol_days": 20, "leverage": 3.0}


def build_weights(ts, opens, closes):
    """Daily (QQQ, TQQQ, BIL) target weights, set at each session's close."""
    return leveraged_index.daily_weights(closes, **PARAMS)
