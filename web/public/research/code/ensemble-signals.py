"""Ensemble signals: daily trend gate + volatility filter + 1-minute crash vote.

Signals
-------
1. Daily trend (gate): QQQ close vs its 165-day SMA.
2. Daily volatility budget: 20-day realised QQQ volatility vs 1/3.
3. Intraday trend vote: QQQ below its 60-minute EMA.
4. Intraday momentum vote: QQQ 30-minute return below zero.
5. Mean-reversion vote: 1-minute RSI(14) below 30.

The first two are evaluated on completed daily bars and set the session's
default position.  The last three are a same-session circuit breaker: while
holding TQQQ, if QQQ is at least 3% below the prior close and all three
intraday votes agree (QQQ below its 60-minute EMA, 30-minute return below zero,
RSI(14) not below 30), sell to BIL at the next minute open and stay there for
the rest of the session.  The EMA and momentum are computed on the continuous
1-minute QQQ series up to and including bar i.  The next
session's open is set from that day's completed close.

All weights are set at the close of bar i and filled at the open of bar i+1 by
the shared harness.  Long-only, weights sum to 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# strategy.py lives in research/agents/ensemble-signals/; bt.py is in research/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bt  # noqa: E402

SYMBOLS = ("QQQ", "TQQQ", "BIL")
START = "2017-01-03"
END = "2026-10-23"
WINDOWS = (("10y", "2017-01-03"), ("5y", "2021-10-25"))
BARS_PER_YEAR = 252 * 390
BAND = 0.02

DEFAULTS = dict(
    sma_len=165,
    vol_len=20,
    vol_max=1.0 / 3.0,
    crash_drop=0.03,
    rsi_len=14,
    rsi_floor=30.0,
    ema_len=60,
    mom_len=30,
    high_asset="BIL",
)


def _rsi(x: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(x, prepend=x[0])
    up = np.maximum(d, 0.0)
    dn = np.maximum(-d, 0.0)
    au = pd.Series(up).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()
    ad = pd.Series(dn).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()
    return 100.0 - 100.0 / (1.0 + au / np.maximum(ad, 1e-12))


def build_weights(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    *,
    sma_len: int = 165,
    vol_len: int = 20,
    vol_max: float = 1.0 / 3.0,
    crash_drop: float = 0.03,
    rsi_len: int = 14,
    rsi_floor: float = 30.0,
    ema_len: int = 60,
    mom_len: int = 30,
    high_asset: str = "BIL",
    crash_on: bool = True,
    vol_on: bool = True,
    ema_on: bool = True,
    mom_on: bool = True,
) -> np.ndarray:
    """Build long-only (QQQ, TQQQ, BIL) weights at 1-minute resolution."""
    q = closes[:, 0]
    dates = pd.Series(ts.date)
    dvals = dates.to_numpy()

    daily = pd.Series(q, index=ts).resample("1D").last().dropna()
    dret = daily.pct_change()
    trend = daily > daily.rolling(sma_len).mean()
    vol = dret.rolling(vol_len).std() * np.sqrt(252.0)

    trend.index = trend.index.date
    vol.index = vol.index.date
    trend_prev = trend.shift(1)
    vol_prev = vol.shift(1)

    reg_prev = dates.map(trend_prev).to_numpy(dtype=float)
    reg_prev = np.where(np.isnan(reg_prev), 0.0, reg_prev).astype(bool)
    reg_curr = dates.map(trend).to_numpy(dtype=float)
    reg_curr = np.where(np.isnan(reg_curr), 0.0, reg_curr).astype(bool)
    vol_prev = dates.map(vol_prev).to_numpy(dtype=float)
    vol_prev = np.where(np.isnan(vol_prev), 1.0, vol_prev)
    vol_curr = dates.map(vol).to_numpy(dtype=float)
    vol_curr = np.where(np.isnan(vol_curr), 1.0, vol_curr)

    daily_map = daily.copy()
    daily_map.index = daily_map.index.date
    prev_close = dates.map(daily_map.shift(1)).to_numpy()
    intraday = q / prev_close - 1.0
    rsi = _rsi(q, rsi_len)
    # Intraday votes, both causal (bar i uses closes up to i).
    ema = pd.Series(q).ewm(span=ema_len, adjust=False).mean().to_numpy()
    trend_down = (q < ema) if ema_on else np.ones(len(q), bool)
    mom = np.full(len(q), np.nan)
    mom[mom_len:] = q[mom_len:] / q[:-mom_len] - 1.0
    mom_down = (mom < 0.0) if mom_on else np.ones(len(q), bool)

    bod = np.r_[0, np.flatnonzero(dvals[1:] != dvals[:-1]) + 1]
    eod = np.r_[bod[1:], len(ts)]

    def target(reg: bool, v: float) -> str:
        if not reg:
            return "BIL"
        if (not vol_on) or (not np.isfinite(v)) or v <= vol_max:
            return "TQQQ"
        return high_asset

    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for b, e in zip(bod, eod):
        w[b:e] = 0.0
        t = target(reg_prev[b], vol_prev[b])
        if t == "TQQQ":
            w[b:e, 1] = 1.0
        elif t == "QQQ":
            w[b:e, 0] = 1.0
        else:
            w[b:e, 2] = 1.0

        if crash_on and t == "TQQQ":
            for i in range(b, e - 1):
                if (intraday[i] <= -crash_drop and trend_down[i]
                        and mom_down[i] and not (rsi[i] < rsi_floor)):
                    w[i:e, 1] = 0.0
                    w[i:e, 0] = 0.0
                    w[i:e, 2] = 1.0
                    break

        # The last bar is a completed daily close; it sets the next open.
        tc = target(reg_curr[e - 1], vol_curr[e - 1])
        w[e - 1] = 0.0
        if tc == "TQQQ":
            w[e - 1, 1] = 1.0
        elif tc == "QQQ":
            w[e - 1, 0] = 1.0
        else:
            w[e - 1, 2] = 1.0
    return w


def _daily_dd(result: dict) -> tuple[float, str, str]:
    eq = pd.Series(result["equity"], index=result["ts"]).resample("1D").last().dropna()
    peak = eq.cummax()
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(eq.iloc[: j + 1]))
    return float(-dd.iloc[j]), str(eq.index[p].date()), str(eq.index[j].date())


def evaluate(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    weights: np.ndarray,
    start: str,
    slippage_bps: float = 1.0,
) -> dict:
    result = bt.run(
        ts, opens, closes, weights, start, band=BAND, slippage_bps=slippage_bps
    )
    stats = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    bench = bt.benchmark(closes[i:, 1], ts[i:], 252)
    yearly = bt.yearly(result["ts"], result["equity"], closes[i:, 1])
    day_dd, peak_date, trough_date = _daily_dd(result)
    return {
        "result": result,
        "stats": stats,
        "benchmark": bench,
        "yearly": {
            int(y): {
                "strategy": round(float(v["strategy"]), 4),
                "benchmark": round(float(v["benchmark"]), 4),
            }
            for y, v in yearly.items()
        },
        "daily_max_drawdown": day_dd,
        "daily_dd_peak": peak_date,
        "daily_dd_trough": trough_date,
    }


def _metrics(ev: dict) -> dict:
    s = ev["stats"]
    b = ev["benchmark"]
    return {
        "cagr": round(float(s["cagr"]), 6),
        "total_return": round(float(s["total_return"]), 6),
        "max_drawdown": round(float(s["max_drawdown"]), 6),
        "daily_max_drawdown": round(float(ev["daily_max_drawdown"]), 6),
        "daily_dd_peak": ev["daily_dd_peak"],
        "daily_dd_trough": ev["daily_dd_trough"],
        "volatility": round(float(s["volatility"]), 6),
        "sharpe": round(float(s["sharpe"]), 4),
        "sortino": round(float(s["sortino"]), 4),
        "exposure": round(float(s["exposure"]), 4),
        "fills": int(s["fills"]),
        "turnover": round(float(s["turnover"]), 1),
        "ending_equity": round(float(s["ending_equity"]), 2),
        "years": round(float(s["years"]), 4),
        "benchmark_cagr": round(float(b["cagr"]), 6),
        "benchmark_max_drawdown": round(float(b["max_drawdown"]), 6),
        "benchmark_sharpe": round(float(b["sharpe"]), 4),
        "yearly": ev["yearly"],
    }


def _pass_fail(m: dict) -> dict:
    """Pass vs the README TQQQ benchmark on both windows."""
    bench = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
    out = {}
    for label, (cagr, dd) in bench.items():
        key = "10y_1bp" if label == "10y" else "5y_1bp"
        mm = m[key]
        out[label] = {
            "cagr_gt_tqqq": bool(mm["cagr"] > cagr),
            "maxdd_lt_tqqq": bool(mm["max_drawdown"] < dd),
            "pass": bool(mm["cagr"] > cagr and mm["max_drawdown"] < dd),
            "tqqq_cagr": cagr,
            "tqqq_maxdd": dd,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--quick", action="store_true", help="skip ablation/stability")
    args = parser.parse_args()

    ts, opens, closes = bt.panel(SYMBOLS, START, END, "1min")
    print(f"panel: {len(ts):,} bars, {ts[0]} .. {ts[-1]}")

    w = build_weights(ts, opens, closes, **DEFAULTS)
    evals = {}
    metrics = {}
    for label, start in WINDOWS:
        for slip in (1.0, 5.0):
            key = f"{label}_{int(slip)}bp"
            ev = evaluate(ts, opens, closes, w, start, slip)
            evals[key] = ev
            metrics[key] = _metrics(ev)
            s = ev["stats"]
            print(
                f"{key:9s} CAGR {s['cagr']*100:6.2f}%  "
                f"DD(1m) {s['max_drawdown']*100:5.2f}%  "
                f"DD(day) {ev['daily_max_drawdown']*100:5.2f}%  "
                f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:4d}  "
                f"turnover {s['turnover']:.0f}x"
            )

    # Ablations at 1 bp.
    ablations = {
        "daily_trend_only": dict(crash_on=False, vol_on=False),
        "trend_plus_vol": dict(crash_on=False, vol_on=True),
        "trend_plus_crash": dict(crash_on=True, vol_on=False),
        "no_rsi_veto": dict(rsi_floor=0.0),
        "drop_and_rsi_only": dict(ema_on=False, mom_on=False),
        "high_asset_qqq": dict(high_asset="QQQ"),
    }
    ablation_metrics = {}
    for name, over in ablations.items():
        params = dict(DEFAULTS)
        params.update(over)
        wa = build_weights(ts, opens, closes, **params)
        vals = {}
        for label, start in WINDOWS:
            ev = evaluate(ts, opens, closes, wa, start, 1.0)
            vals[f"{label}_1bp"] = _metrics(ev)
        ablation_metrics[name] = vals

    stability = {"vol_max_x_crash_drop": [], "sma_len": [], "vol_len": [], "rsi_floor": []}
    if not args.quick:
        for vmax in (0.30, 1.0 / 3.0, 0.36, 0.40):
            for drop in (0.025, 0.03, 0.035, 0.04):
                params = dict(DEFAULTS, vol_max=vmax, crash_drop=drop)
                ww = build_weights(ts, opens, closes, **params)
                row = {"vol_max": round(vmax, 4), "crash_drop": drop}
                for label, start in WINDOWS:
                    ev = evaluate(ts, opens, closes, ww, start, 1.0)
                    row[label] = {
                        "cagr": round(float(ev["stats"]["cagr"]), 6),
                        "max_drawdown": round(float(ev["stats"]["max_drawdown"]), 6),
                    }
                stability["vol_max_x_crash_drop"].append(row)
        for sma in (150, 165, 180):
            params = dict(DEFAULTS, sma_len=sma)
            ww = build_weights(ts, opens, closes, **params)
            row = {"sma_len": sma}
            for label, start in WINDOWS:
                ev = evaluate(ts, opens, closes, ww, start, 1.0)
                row[label] = {
                    "cagr": round(float(ev["stats"]["cagr"]), 6),
                    "max_drawdown": round(float(ev["stats"]["max_drawdown"]), 6),
                }
            stability["sma_len"].append(row)
        for vl in (15, 20, 30):
            params = dict(DEFAULTS, vol_len=vl)
            ww = build_weights(ts, opens, closes, **params)
            row = {"vol_len": vl}
            for label, start in WINDOWS:
                ev = evaluate(ts, opens, closes, ww, start, 1.0)
                row[label] = {
                    "cagr": round(float(ev["stats"]["cagr"]), 6),
                    "max_drawdown": round(float(ev["stats"]["max_drawdown"]), 6),
                }
            stability["vol_len"].append(row)
        for rf in (20.0, 30.0, 40.0):
            params = dict(DEFAULTS, rsi_floor=rf)
            ww = build_weights(ts, opens, closes, **params)
            row = {"rsi_floor": rf}
            for label, start in WINDOWS:
                ev = evaluate(ts, opens, closes, ww, start, 1.0)
                row[label] = {
                    "cagr": round(float(ev["stats"]["cagr"]), 6),
                    "max_drawdown": round(float(ev["stats"]["max_drawdown"]), 6),
                }
            stability["rsi_floor"].append(row)

    out = {
        "strategy": "ensemble_signals",
        "description": (
            "QQQ 165-day trend gate; 20-day realised-vol budget (TQQQ when "
            "<=1/3, BIL otherwise); 1m crash vote (-3% intraday, 60m EMA, "
            "30m momentum, RSI(14) veto) exits TQQQ to BIL for the session."
        ),
        "symbols": list(SYMBOLS),
        "windows": {"10y": [START, END], "5y": ["2021-10-25", END]},
        "parameters": {
            k: (round(v, 6) if isinstance(v, float) else v)
            for k, v in DEFAULTS.items()
        },
        "metrics": metrics,
        "pass_fail_vs_tqqq": _pass_fail(metrics),
        "baseline_daily_reference": {
            "10y": {"cagr": 0.4531, "max_drawdown": 0.5871},
            "5y": {"cagr": 0.3461, "max_drawdown": 0.3686},
        },
        "ablations_1bp": ablation_metrics,
        "stability": stability,
    }

    if not args.no_write:
        path = Path(__file__).with_name("result.json")
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"wrote {path}")
    print(json.dumps(_pass_fail(metrics), indent=2))


if __name__ == "__main__":
    main()
