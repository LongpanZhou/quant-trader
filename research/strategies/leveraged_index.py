"""Python port of the Rust `LeveragedIndex` strategy (src/strategy.rs).

Rule, evaluated on each daily close:
  index close <= its `sma_days` average  -> 100% safe asset (BIL)
  index above, no volatility target      -> 100% leveraged fund (TQQQ)
  index above, with volatility target    -> exposure = min(target_vol / vol, leverage)
      exposure >= 1: blend the leveraged fund and the index so that
                     w_fund * leverage + w_index * 1 = exposure
      exposure <  1: `exposure` in the index, the rest in the safe asset

`vol` is the population standard deviation of the last `vol_days` daily index
returns, annualised with sqrt(252), as in `src/indicators.rs::stddev`.
Before `sma_days` closes exist there is no signal and the book stays in cash,
which is what the Rust engine does when `sma()` returns None.

Weights are set at session k's close and traded at session k+1's open,
matching the Rust backtest's `lag_bars = 1`, `fill_open = true`.

Columns follow the shared research panel: 0 = QQQ (index), 1 = TQQQ
(leveraged fund), 2 = BIL (safe asset).
"""
from __future__ import annotations

import numpy as np

BARS_PER_YEAR = 252.0  # src/config.rs, Timeframe::D1


def blend_exposure(exposure: float, leverage: float) -> tuple[float, float]:
    """Split market exposure into (leveraged fund, plain index) weights."""
    if leverage <= 1.0:
        return 0.0, 1.0
    w = min(1.0, max(0.0, (exposure - 1.0) / (leverage - 1.0)))
    return w, 1.0 - w


def target(closes_index: np.ndarray, *, sma_days: int, target_vol: float,
           vol_days: int, leverage: float) -> tuple[float, float, float] | None:
    """Target (index, fund, safe) weights from index closes up to and including today."""
    c = closes_index
    if len(c) < sma_days:
        return None
    if c[-1] <= c[-sma_days:].mean():
        return 0.0, 0.0, 1.0
    if target_vol <= 0.0:
        return 0.0, 1.0, 0.0
    tail = c[max(0, len(c) - vol_days - 1):]
    rets = tail[1:] / tail[:-1] - 1.0
    vol = float(rets.std()) * np.sqrt(BARS_PER_YEAR) if len(rets) else 0.0  # population std
    exposure = min(target_vol / vol, leverage) if vol > 1e-9 else 1.0
    if exposure >= 1.0:
        w_fund, w_index = blend_exposure(exposure, leverage)
        return w_index, w_fund, 0.0
    return exposure, 0.0, 1.0 - exposure


def daily_weights(closes: np.ndarray, *, sma_days: int, target_vol: float,
                  vol_days: int, leverage: float = 3.0) -> np.ndarray:
    """(n, 3) daily target weights; rows before warmup are all zero (cash)."""
    closes = np.asarray(closes, dtype=float)
    index = closes[:, 0]
    out = np.zeros((len(index), 3))
    for k in range(len(index)):
        t = target(index[: k + 1], sma_days=sma_days, target_vol=target_vol,
                   vol_days=vol_days, leverage=leverage)
        if t is not None:
            out[k] = t
    return out
