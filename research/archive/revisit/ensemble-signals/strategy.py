"""Volatility Contraction Recovery (VCR) -- revisit of `ensemble-signals`.

The old ensemble was a 165-day QQQ trend gate plus a volatility budget and a
1-minute crash vote.  The genuinely new part was the volatility budget plus the
idea that acute stress should be treated differently from calm markets.  This
rebuild keeps that research area but changes the base, the universe weighting,
the signal horizon and the holding period:

    - no 100-250 day moving-average gate on QQQ/TQQQ/SPY/NDX;
    - QQQ is the default risk asset, not TQQQ;
    - TQQQ is used only during a high-volatility *contraction* (post-spike
      recovery), when the old trend base is usually in cash;
    - BIL is held in panic (vol still rising) and in complacency (vol rising
      from a low);
    - positions are held for days/weeks, not intraday.

The state machine is deliberately daily.  Weights are set at a bar close and
fill at the next bar's open through the shared harness.  There is no intraday
trading rule in this rebuild; the one-minute panel is used for minute marks.

Backtests are paused.  `main()` requires `--run`; without it the module only
prints the design and the state counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# strategy.py lives in research/revisit/ensemble-signals/; bt.py is in research/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_PER_YEAR = 252 * 390
BAND = 0.02
SYMBOLS = ("QQQ", "TQQQ", "BIL")

DEFAULTS = dict(
    vol_fast=5,
    vol_mid=20,
    pct_window=252,
    stress_pct=0.80,
    calm_pct=0.30,
    stress_slope=0.10,
    complacency_slope=0.25,
    reaccel_slope=0.50,
    min_hold=5,
    max_recovery=20,
    qqq_vol_target=0.20,
    tqqq_vol_target=0.35,
    max_weight=1.0,
)


def daily_closes(ts: pd.DatetimeIndex, closes: np.ndarray) -> pd.Series:
    """QQQ daily closes from the 1-minute panel (15:59 close)."""
    q = closes[:, 0]
    return pd.Series(q, index=ts).resample("1D").last().dropna()


ROOT = Path(__file__).resolve().parents[3]


def _warm_daily(daily: pd.Series) -> tuple[pd.Series, int]:
    """Prepend Yahoo daily QQQ closes from before the first 1-minute day.

    Tuning fix (2026-11-27): the 1-minute archive starts on 2016-01-04, the
    first dev day, so `bt.panel(warmup_days=500)` supplied no warm-up and the
    252-day percentile rank was undefined (state forced to `normal`) for the
    first 146 dev sessions. Only days strictly before the first 1-minute day
    are taken from Yahoo, rescaled so the splice is continuous; they are used
    only for rolling-vol warm-up and never traded.
    """
    path = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    if not path.exists():
        return daily, 0
    y = pd.read_parquet(path)
    y = pd.Series(y["adjclose"].to_numpy(float), index=pd.to_datetime(y["date"]))
    first = daily.index[0].tz_localize(None).normalize()
    pre = y[y.index < first]
    if len(pre) == 0 or first not in y.index:
        return daily, 0
    pre = pre * (float(daily.iloc[0]) / float(y.loc[first]))
    pre.index = pre.index.tz_localize(daily.index.tz)
    return pd.concat([pre, daily]), int(len(pre))


def _realized_vol(daily: pd.Series, window: int) -> pd.Series:
    """Annualised close-to-close vol known at the prior close."""
    r = daily.pct_change()
    return (r.rolling(window).std() * np.sqrt(252.0)).shift(1)


def _percentile_rank(series: pd.Series, window: int) -> pd.Series:
    """Trailing percentile rank, using only information through the bar."""
    return series.rolling(window, min_periods=max(60, window // 2)).rank(pct=True)


def _raw_state(
    pct: float,
    slope: float,
    *,
    stress_pct: float,
    calm_pct: float,
    stress_slope: float,
    complacency_slope: float,
) -> str:
    if not np.isfinite(pct) or not np.isfinite(slope):
        return "normal"
    if pct >= stress_pct:
        return "panic" if slope > stress_slope else "recovery"
    if pct <= calm_pct and slope > complacency_slope:
        return "complacency"
    return "normal"


def _state_path(
    raw: np.ndarray,
    slope: np.ndarray,
    *,
    min_hold: int,
    max_recovery: int,
    reaccel_slope: float,
) -> np.ndarray:
    """State machine with fast risk-on/risk-off entries and slow normal exits.

    - entering `panic` or `recovery` is allowed immediately;
    - leaving a state to `normal`/`complacency` waits for `min_hold` days;
    - a recovery older than `max_recovery` days is closed and cannot re-open
      until the raw state leaves `recovery`;
    - a severe short-vol re-acceleration exits recovery immediately.
    """
    n = len(raw)
    states = np.empty(n, dtype=object)
    current = "normal"
    held = 0
    recovery_days = 0
    recovery_done = False

    for i in range(n):
        r = raw[i]
        if r != "recovery":
            recovery_done = False

        if current == "recovery":
            recovery_days += 1
            if np.isfinite(slope[i]) and slope[i] > reaccel_slope:
                current = "panic"
                held = 0
                recovery_days = 0
                recovery_done = True
            elif recovery_days >= max_recovery:
                current = "normal"
                held = 0
                recovery_days = 0
                recovery_done = True

        if r == "recovery" and recovery_done:
            r = "normal"

        if r != current and (held >= min_hold or r in ("panic", "recovery")):
            current = r
            held = 0
            if current == "recovery":
                recovery_days = 0

        states[i] = current
        held += 1

    return states


def _target(state: str, rv20: float, params: dict) -> np.ndarray:
    """Target (QQQ, TQQQ, BIL) weights for one state."""
    if state in ("panic", "complacency"):
        return np.array([0.0, 0.0, 1.0])
    if not np.isfinite(rv20) or rv20 <= 0:
        return np.array([0.0, 0.0, 1.0])

    if state == "recovery":
        wt = min(float(params["max_weight"]), float(params["tqqq_vol_target"]) / rv20)
        return np.array([0.0, wt, 1.0 - wt])

    wq = min(float(params["max_weight"]), float(params["qqq_vol_target"]) / rv20)
    return np.array([wq, 0.0, 1.0 - wq])


def build_weights(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    **overrides,
) -> tuple[np.ndarray, dict]:
    """Build daily VCR weights held on the 1-minute panel.

    Day D's state uses QQQ's prior completed daily close.  The last bar of day
    D uses day D's completed close to set day D+1's target.  Weights fill at
    the next bar's open through `bt.run`/`bt.run_many`.
    """
    params = dict(DEFAULTS)
    params.update(overrides)
    daily, n_warm = _warm_daily(daily_closes(ts, closes))
    rv_fast = _realized_vol(daily, int(params["vol_fast"]))
    rv_mid = _realized_vol(daily, int(params["vol_mid"]))
    pct = _percentile_rank(rv_mid, int(params["pct_window"]))
    slope = rv_fast / rv_mid.replace(0.0, np.nan) - 1.0

    raw = np.array(
        [
            _raw_state(
                pct.iloc[i],
                slope.iloc[i],
                stress_pct=float(params["stress_pct"]),
                calm_pct=float(params["calm_pct"]),
                stress_slope=float(params["stress_slope"]),
                complacency_slope=float(params["complacency_slope"]),
            )
            for i in range(len(daily))
        ],
        dtype=object,
    )
    states = _state_path(
        raw,
        slope.to_numpy(dtype=float),
        min_hold=int(params["min_hold"]),
        max_recovery=int(params["max_recovery"]),
        reaccel_slope=float(params["reaccel_slope"]),
    )
    rv_mid_np = rv_mid.to_numpy(dtype=float)
    daily_index = pd.Index(daily.index.date)
    day_map = {d: i for i, d in enumerate(daily_index)}

    dates = pd.Series(bt.session_dates(ts))
    dvals = dates.to_numpy()
    day_idx = dates.map(day_map).to_numpy(dtype=float)
    bod = np.r_[0, np.flatnonzero(dvals[1:] != dvals[:-1]) + 1]
    eod = np.r_[bod[1:], len(ts)]

    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for b, e in zip(bod, eod):
        di = day_idx[b]
        if not np.isfinite(di):
            w[b:e] = (0.0, 0.0, 1.0)
            continue
        di = int(di)
        w[b:e] = _target(states[di], rv_mid_np[di], params)
        if di + 1 < len(daily):
            w[e - 1] = _target(states[di + 1], rv_mid_np[di + 1], params)
        else:
            w[e - 1] = _target(states[di], rv_mid_np[di], params)

    # Summaries for the report/audit.  No performance numbers here.
    state_series = pd.Series(states[n_warm:], index=daily.index.date[n_warm:])
    rec = state_series == "recovery"
    entries = int((rec & ~rec.shift(1, fill_value=False)).sum())
    runs = []
    run = 0
    for x in rec.to_numpy():
        if x:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)

    info = {
        "params": params,
        "n_daily": int(len(daily) - n_warm),
        "n_warmup_days": n_warm,
        "state_counts": {str(k): int(v) for k, v in state_series.value_counts().items()},
        "recovery_episodes": entries,
        "recovery_avg_days": float(np.mean(runs)) if runs else 0.0,
        "recovery_max_days": int(np.max(runs)) if runs else 0,
        "first_day": str(daily.index[n_warm].date()),
        "last_day": str(daily.index[-1].date()),
        "note": "Weights are daily state targets; 1m bars are used only for marks.",
    }
    return w, info


def _daily_returns(result: dict) -> pd.Series:
    eq = bt.daily_last(result["equity"], result["ts"]).dropna()
    return eq.pct_change().dropna()


def _baseline_daily_returns(ts, opens, closes) -> pd.Series:
    """165-day baseline used ONLY as a correlation benchmark, never as a rule."""
    daily = daily_closes(ts, closes)
    sma = daily.rolling(165, min_periods=100).mean()
    on = (daily > sma).shift(1)
    on.index = on.index.date
    dates = pd.Series(bt.session_dates(ts))
    reg = dates.map(on).to_numpy(dtype=float)
    reg = np.where(np.isnan(reg), 0.0, reg).astype(bool)
    wb = np.zeros((len(ts), 3))
    wb[reg, 1] = 1.0
    wb[~reg, 2] = 1.0
    r = bt.run(ts, opens, closes, wb, DEV_START, band=BAND, slippage_bps=1.0)
    return _daily_returns(r)


def _eval(ts, opens, closes, w, start, slip, baseline_returns=None) -> dict:
    r = bt.run(ts, opens, closes, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
    }
    if baseline_returns is not None:
        rr = _daily_returns(r)
        j = rr.index.intersection(baseline_returns.index)
        out["corr_vs_165d_baseline"] = float(np.corrcoef(rr.loc[j], baseline_returns.loc[j])[0, 1])
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="run the frozen dev backtest")
    parser.add_argument("--start", default=DEV_START)
    parser.add_argument("--end", default=DEV_END)
    args = parser.parse_args()

    ts, opens, closes = bt.panel(SYMBOLS, args.start, args.end, "1min")
    w, info = build_weights(ts, opens, closes)

    print(json.dumps(info, indent=2, default=str))
    if not args.run:
        print("design-only: not running the backtest; pass --run after authorization")
        return

    baseline = _baseline_daily_returns(ts, opens, closes)
    windows = {"dev": (DEV_START, DEV_END)}
    result = {
        "agent": "ensemble-signals",
        "original": "research/agents/ensemble-signals",
        "status": "pending_holdout",
        "idea": (
            "Volatility spikes mean-revert; the high-vol contraction phase is a "
            "distinct TQQQ recovery window, while rising vol from a low is a "
            "de-risking signal and QQQ is the default risk asset."
        ),
        "hypothesis": (
            "A daily volatility-percentile/slope state machine with multi-day "
            "holds captures a post-spike recovery premium that is not the old "
            "165-day trend base."
        ),
        "universe": list(SYMBOLS),
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {name: {} for name in ("dev", "holdout", "10y", "5y")},
        "marks": "1m",
        "benchmarks": {},
    }
    for name, (start, end) in windows.items():
        for slip in (1.0, 5.0, 10.0):
            key = f"{int(slip)}bp"
            result["windows"][name][key] = _eval(
                ts, opens, closes, w, start, slip, baseline
            )
    result["corr_vs_165d_baseline"] = result["windows"]["dev"]["1bp"].get(
        "corr_vs_165d_baseline"
    )
    out = Path(__file__).with_name("result.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
