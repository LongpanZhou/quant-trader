r"""Regime-gated overnight drift + first-hour intraday momentum on QQQ/TQQQ/BIL.

Rules (long-only, regular session only, next-bar-open fills):
  1. Regime (daily): QQQ close > 165-day SMA of QQQ closes -> risk-on, else BIL.
     The regime for day d uses the close of day d-1 (no look-ahead).
  2. Risk-on days: hold TQQQ overnight (from 15:59 open through the next 09:31
     open) and during the first hour (09:30-10:30).
  3. First-hour signal: r60 = QQQ close(10:29) / QQQ open(09:30) - 1.
     - r60 >= 0: hold TQQQ for the rest of the session (10:30 open -> 15:59 open).
     - r60 <  0: move to cash at the 10:30 open, re-enter TQQQ at the 15:59 open
       for the next overnight.
  4. Overnight entry/exit is decided with data available by 15:58 (QQQ 15:58 close
     vs the SMA through the prior day) and filled at the 15:59 open.

Signals are evaluated on bar i and filled at the open of bar i+1. Weights are
fractions of equity; the strategy never uses leverage beyond 100% TQQQ.

Usage:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/agents/intraday-momentum/strategy.py
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

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"
SMA_LEN = 165
THRESHOLD = 0.0
MINUTES_60 = 10 * 60 + 29
MINUTES_1558 = 15 * 60 + 58


def build_weights(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    sma_len: int = SMA_LEN,
    threshold: float = THRESHOLD,
) -> tuple[np.ndarray, dict]:
    """Return (n, 3) target weights and diagnostics.

    Columns are QQQ, TQQQ, BIL. The default is 100% BIL (risk-off).
    """
    n = len(ts)
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    day = ts.values.astype("datetime64[D]")
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], n]
    ndays = len(starts)

    # Daily QQQ closes from the 1-minute panel (15:59 close == official close),
    # used for the 165-day SMA. The daily panel would also work; this keeps the
    # regime and the trading prices on the same adjusted series.
    day_close = np.array([closes[b - 1, 0] for b in ends])
    day_dates = pd.to_datetime([str(x) for x in day[starts]])
    qclose = pd.Series(day_close, index=day_dates)
    sma = qclose.rolling(sma_len).mean()

    # Regime for day d: QQQ close(d-1) > SMA(d-1). Shift once; no look-ahead.
    regime_prev = (qclose.shift(1) > sma.shift(1)).to_numpy()
    regime_prev = np.where(np.isfinite(sma.shift(1).to_numpy()), regime_prev, False)

    # Overnight gate at 15:58 of day d: QQQ 15:58 price vs SMA through d-1.
    q1558 = np.full(ndays, np.nan)
    for d in range(ndays):
        a, b = starts[d], ends[d]
        cand = np.flatnonzero(mins[a:b] <= MINUTES_1558)
        if len(cand):
            q1558[d] = closes[a + cand[-1], 0]
    sma_prev = sma.shift(1).to_numpy()
    regime_now = np.where(np.isfinite(sma_prev), q1558 > sma_prev, False)

    weights = np.zeros((n, 3))
    weights[:, 2] = 1.0  # default: T-bills
    first_hour = np.full(ndays, np.nan)

    for d in range(ndays):
        a, b = int(starts[d]), int(ends[d])
        if b - a < 3:
            continue
        # Last bar at or before 10:29 is the signal bar; fill at the next open.
        cand60 = np.flatnonzero(mins[a:b] <= MINUTES_60)
        if not len(cand60):
            continue
        i60 = a + int(cand60[-1])
        r60 = closes[i60, 0] / opens[a, 0] - 1.0
        first_hour[d] = r60

        if regime_prev[d]:
            # Morning: 09:30 bar through the 10:29 signal bar.
            weights[a:i60, :] = (0.0, 1.0, 0.0)
            if r60 < threshold:
                # Exit at the 10:30 open, stay in cash until 15:58.
                weights[i60 : b - 1, :] = 0.0
            else:
                # Hold through the 15:57 bar; exit at the 15:59 open.
                weights[i60 : b - 2, :] = (0.0, 1.0, 0.0)

        # Overnight: target TQQQ on the 15:58 and 15:59 bars -> fill at 15:59 open.
        if regime_now[d] and d + 1 < ndays:
            weights[b - 2 : b, :] = (0.0, 1.0, 0.0)

    diag = {
        "days": int(ndays),
        "regime_on_share": float(np.mean(regime_prev)),
        "tqqq_time_share": float(np.mean(weights[:, 1] > 0)),
        "mean_r60_bp": float(np.nanmean(first_hour) * 1e4),
        "r60_positive_share": float(np.nanmean(first_hour > 0)),
    }
    return weights, diag


def daily_marks(result: dict) -> dict:
    eq = pd.Series(result["equity"], index=pd.to_datetime(result["ts"]))
    de = eq.groupby(eq.index.normalize()).last()
    rets = de.pct_change().dropna().to_numpy()
    years = len(de) / 252.0
    peak = np.maximum.accumulate(de.to_numpy())
    return {
        "cagr": float((de.iloc[-1] / de.iloc[0]) ** (1 / years) - 1),
        "max_drawdown": float(-(de.to_numpy() / peak - 1.0).min()),
        "sharpe": float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)),
        "volatility": float(rets.std(ddof=0) * np.sqrt(252)),
    }


def run_window(ts, opens, closes, weights, start, slippage_bps):
    result = bt.run(
        ts, opens, closes, weights, start, band=0.02, slippage_bps=slippage_bps
    )
    s = bt.stats(result, bars_per_year=252 * 390)
    i0 = bt.start_index(ts, start)
    bench = bt.benchmark(closes[i0:, 1], ts[i0:], 252 * 390)
    return {
        "stats": s,
        "daily": daily_marks(result),
        "benchmark": bench,
        "yearly": bt.yearly(result["ts"], result["equity"], closes[i0:, 1]),
    }


def main() -> None:
    ts, opens, closes = bt.panel(
        ("QQQ", "TQQQ", "BIL"), START10, END, "1min"
    )
    weights, diag = build_weights(ts, opens, closes)

    out = {"params": {"sma_len": SMA_LEN, "threshold": THRESHOLD, "band": 0.02},
           "diagnostics": diag, "windows": {}}
    for start in (START10, START5):
        for slip in (1.0, 5.0):
            key = f"{start}_{int(slip)}bp"
            out["windows"][key] = run_window(ts, opens, closes, weights, start, slip)

    for key, w in out["windows"].items():
        s, d, b = w["stats"], w["daily"], w["benchmark"]
        print(f"\n{key}")
        print(
            f"  minute marks: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
            f"Sharpe {s['sharpe']:4.2f}  vol {s['volatility']*100:5.2f}%  "
            f"fills {s['fills']:,}  turnover {s['turnover']:.0f}x  end ${s['ending_equity']:,.0f}"
        )
        print(
            f"  daily  marks: CAGR {d['cagr']*100:6.2f}%  DD {d['max_drawdown']*100:5.2f}%  "
            f"Sharpe {d['sharpe']:4.2f}  vol {d['volatility']*100:5.2f}%"
        )
        print(
            f"  TQQQ bench  : CAGR {b['cagr']*100:6.2f}%  DD {b['max_drawdown']*100:5.2f}%  "
            f"Sharpe {b['sharpe']:4.2f}"
        )
        print("  yearly: " + " ".join(
            f"{y}:{v['strategy']*100:+.1f}%/{v['benchmark']*100:+.1f}%"
            for y, v in w["yearly"].items()
        ))

    print("\ndiagnostics:", json.dumps(diag, indent=1))
    print("\npass vs TQQQ (39.28%/81.68% 10y, 13.47%/81.68% 5y):")
    for start, label in ((START10, "10y"), (START5, "5y")):
        s = out["windows"][f"{start}_1bp"]["stats"]
        ok = s["cagr"] > (0.3928 if start == START10 else 0.1347) and s["max_drawdown"] < 0.8168
        print(f"  {label}: {'PASS' if ok else 'FAIL'}  "
              f"(CAGR {s['cagr']*100:.2f}%, DD {s['max_drawdown']*100:.2f}%)")


if __name__ == "__main__":
    main()
