"""Donchian / Turtle breakout on QQQ 5-minute bars, traded in TQQQ.

Idea
----
Classic Donchian/Turtle breakout (buy a new N-bar high, exit a new M-bar low)
applied to QQQ 5-minute bars, with a daily QQQ > 165-day SMA regime filter.
The position is 100% TQQQ while long, 100% BIL otherwise.  Signals are
evaluated at a bar close and filled at the next bar's open (bt.simulate).

The headline variant ("primary") uses the Donchian channel only for entry
(55 5-min bars = 275 minutes) and lets the daily regime be the exit.  Faster
Donchian exits are tested as variants; they whipsaw badly.

Run from the repository root:

    python research/agents/donchian-breakout/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"
RULE = "5min"
BARS_PER_YEAR = {"1min": 252 * 390, "5min": 252 * 78}
PRIMARY_N = 55
REGIME_DAYS = 165

README_BENCH = {
    "10y": {"cagr": 0.3928, "max_drawdown": 0.8168, "sharpe": 0.83},
    "5y": {"cagr": 0.1347, "max_drawdown": 0.8168, "sharpe": 0.53},
}
README_BASELINE = {
    "10y": {"cagr": 0.4531, "max_drawdown": 0.5871, "sharpe": 1.00},
    "5y": {"cagr": 0.3461, "max_drawdown": 0.3686, "sharpe": 0.88},
}


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_panel(rule: str = RULE):
    """Return aligned QQQ OHLC, TQQQ ATR and the daily-regime state per bar."""
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, rule)
    start_ts = pd.Timestamp(START10, tz="America/New_York")
    load_start = start_ts - pd.Timedelta(days=500)
    end_ts = pd.Timestamp(END, tz="America/New_York").normalize() + pd.Timedelta(days=1)

    frame = bt.load_1m("QQQ")
    frame = frame[(frame["ts"] >= load_start) & (frame["ts"] < end_ts)].set_index("ts")
    qqq = bt.resample(frame, rule)
    assert qqq.index.equals(ts), "QQQ OHLC is not aligned with the panel"

    tframe = bt.load_1m("TQQQ")
    tframe = tframe[(tframe["ts"] >= load_start) & (tframe["ts"] < end_ts)].set_index("ts")
    tqqq = bt.resample(tframe, rule).reindex(ts).ffill().bfill()
    th, tl, tc = (tqqq[c].to_numpy() for c in ("high", "low", "close"))

    prev_close = np.roll(tc, 1)
    prev_close[0] = tc[0]
    true_range = np.maximum(th - tl, np.maximum(np.abs(th - prev_close), np.abs(tl - prev_close)))
    atr = pd.Series(true_range).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()

    regime = daily_regime_bars(ts, qqq["close"].to_numpy(), REGIME_DAYS)
    return ts, opens, closes, qqq["high"].to_numpy(), qqq["low"].to_numpy(), qqq["close"].to_numpy(), atr, regime


def daily_regime_bars(ts: pd.DatetimeIndex, qqq_close: np.ndarray, days: int = 165) -> np.ndarray:
    """QQQ close > `days`-day SMA, mapped to every intraday bar.

    The daily close is only known at the end of the day, so for all bars of
    day d except its last bar we use the regime through d-1; the last bar of
    day d carries the regime through d.  Its weight is filled at the next
    bar's open (next session's 09:30 for the 5-minute series), i.e. the
    standard "decide after the close, execute at the next open" rule.
    """
    daily = pd.Series(qqq_close, index=ts).resample("1D").last().dropna()
    sma = daily.rolling(days).mean()
    reg = (daily > sma) & sma.notna()
    reg_prev = reg.shift(1).fillna(False)
    by_date = {k.date(): bool(v) for k, v in reg.items()}
    by_prev = {k.date(): bool(v) for k, v in reg_prev.items()}
    dates = pd.DatetimeIndex(ts).date
    tod = ts.hour * 60 + ts.minute
    last_bar = tod >= 16 * 60 - 5
    out = np.empty(len(ts), dtype=bool)
    for i in range(len(ts)):
        d = dates[i]
        out[i] = by_date.get(d, False) if last_bar[i] else by_prev.get(d, False)
    return out


# --------------------------------------------------------------------------
# strategies (all weights are decided at the close of bar i, filled at i+1)
# --------------------------------------------------------------------------
def donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime,
                     entry_n: int, exit_n: int | None = None, stop_k: float = 0.0,
                     max_hold: int = 0, session_exit: bool = False) -> np.ndarray:
    n = len(ts)
    upper = pd.Series(high).rolling(entry_n).max().shift(1).to_numpy()
    lower = (pd.Series(low).rolling(exit_n).min().shift(1).to_numpy()
             if exit_n else np.full(n, np.nan))
    entry_sig = np.where(np.isnan(upper), False, qqq_close > upper)
    exit_sig = np.where(np.isnan(lower), False, qqq_close < lower)

    tod = ts.hour * 60 + ts.minute
    bar_min = int(round((tod[1] - tod[0]) % (24 * 60))) if n > 1 else 5
    session_last = session_exit & ((tod + bar_min) >= (16 * 60 - 5))

    w = np.zeros((n, 3))
    in_pos = False
    pending = False
    entry_px = 0.0
    entry_bar = -1
    stop = -np.inf
    pend_atr = 0.0
    for i in range(n):
        if pending:
            in_pos = True
            entry_px = opens[i, 1]
            entry_bar = i
            stop = entry_px - stop_k * pend_atr if stop_k > 0 else -np.inf
            pending = False
        if in_pos:
            hit = (not regime[i]) or exit_sig[i] or (closes[i, 1] <= stop)
            if max_hold and (i - entry_bar) >= max_hold:
                hit = True
            if session_last[i]:
                hit = True
            if hit:
                w[i, 2] = 1.0
                in_pos = False
            else:
                w[i, 1] = 1.0
        else:
            if regime[i] and entry_sig[i]:
                w[i, 1] = 1.0
                pending = True
                pend_atr = atr[i]
            else:
                w[i, 2] = 1.0
    return w


def dual_thrust_weights(ts, opens, closes, high, low, qqq_close, atr, regime,
                        k: float = 0.3, day_trade: bool = False,
                        stop_k: float = 0.0) -> np.ndarray:
    """Dual Thrust: prior-day range = max(HH-LC, HC-LL); buy above open+k*range."""
    n = len(ts)
    daily = pd.DataFrame({"h": pd.Series(high, index=ts).resample("1D").max(),
                          "l": pd.Series(low, index=ts).resample("1D").min(),
                          "c": pd.Series(qqq_close, index=ts).resample("1D").last()}).dropna()
    rng = np.maximum(daily["h"] - daily["l"].shift(1), daily["c"].shift(1) - daily["l"])
    trig_by_date = {k.date(): float(v) for k, v in (rng.shift(1) * k).items()}
    open_by_date = {k.date(): float(v) for k, v in
                    pd.Series(opens[:, 0], index=ts).resample("1D").first().items()}
    dates = pd.DatetimeIndex(ts).date
    trig = np.array([trig_by_date.get(d, np.nan) for d in dates])
    day_open = np.array([open_by_date.get(d, np.nan) for d in dates])
    buy_line = day_open + trig
    entry_sig = np.where(np.isfinite(buy_line), qqq_close > buy_line, False)

    tod = ts.hour * 60 + ts.minute
    session_last = (tod + 5) >= (16 * 60 - 5)

    w = np.zeros((n, 3))
    in_pos = False
    pending = False
    entry_px = 0.0
    stop = -np.inf
    pend_atr = 0.0
    for i in range(n):
        if pending:
            in_pos = True
            entry_px = opens[i, 1]
            stop = entry_px - stop_k * pend_atr if stop_k > 0 else -np.inf
            pending = False
        if in_pos:
            hit = (not regime[i]) or (closes[i, 1] <= stop)
            if day_trade and session_last[i]:
                hit = True
            if hit:
                w[i, 2] = 1.0
                in_pos = False
            else:
                w[i, 1] = 1.0
        else:
            if regime[i] and entry_sig[i]:
                w[i, 1] = 1.0
                pending = True
                pend_atr = atr[i]
            else:
                w[i, 2] = 1.0
    return w


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def _clean(s: dict) -> dict:
    return {k: (float(v) if isinstance(v, (float, np.floating)) else
                int(v) if isinstance(v, (int, np.integer)) else v)
            for k, v in s.items()}


def evaluate(ts, opens, closes, w, rule: str, slip: float) -> dict:
    out = {}
    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BARS_PER_YEAR[rule])
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR[rule])
        out[label] = {
            "start": start,
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "total_return": s["total_return"],
            "ending_equity": s["ending_equity"], "years": s["years"],
            "fills": s["fills"], "turnover": s["turnover"],
            "tqqq_bar_exposure": float((w[bt.start_index(ts, start):, 1] > 0).mean()),
            "benchmark_cagr": b["cagr"], "benchmark_max_drawdown": b["max_drawdown"],
            "benchmark_sharpe": b["sharpe"],
        }
    return out


def pass_fail(metrics: dict, bench: dict = README_BENCH) -> dict:
    out = {}
    for win in ("10y", "5y"):
        m = metrics[win]
        b = bench[win]
        out[win] = {
            "cagr_gt_tqqq": bool(m["cagr"] > b["cagr"]),
            "dd_lt_tqqq": bool(m["max_drawdown"] < b["max_drawdown"]),
            "sharpe_gt_tqqq": bool(m["sharpe"] > b["sharpe"]),
            "pass": bool(m["cagr"] > b["cagr"] and m["max_drawdown"] < b["max_drawdown"]),
        }
    out["pass_both"] = bool(out["10y"]["pass"] and out["5y"]["pass"])
    return out


def main() -> None:
    here = Path(__file__).resolve().parent
    ts, opens, closes, high, low, qqq_close, atr, regime = load_panel(RULE)
    print(f"bars {len(ts):,}  {ts[0]} .. {ts[-1]}  regime on {regime.mean()*100:.1f}%")

    results: dict = {"data": {"rule": RULE, "bars": len(ts), "first": str(ts[0]),
                              "last": str(ts[-1]), "regime_on_fraction": float(regime.mean())},
                     "primary": {"params": {"entry_n": PRIMARY_N, "exit": "daily regime",
                                            "regime_days": REGIME_DAYS, "asset": "TQQQ",
                                            "defensive": "BIL"}},
                     "variants": {}, "benchmark": {}}

    # primary
    w_primary = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime, PRIMARY_N)
    results["primary"]["windows"] = evaluate(ts, opens, closes, w_primary, RULE, 1.0)
    results["primary"]["cost_sensitivity"] = {
        "1bp": evaluate(ts, opens, closes, w_primary, RULE, 1.0),
        "5bp": evaluate(ts, opens, closes, w_primary, RULE, 5.0),
    }
    results["primary"]["yearly"] = {}
    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts, opens, closes, w_primary, start, band=0.02, slippage_bps=1.0)
        i = bt.start_index(ts, start)
        results["primary"]["yearly"][label] = bt.yearly(ts[i:], r["equity"], closes[i:, 1])
    results["primary"]["pass_fail"] = pass_fail(results["primary"]["windows"])

    # parameter stability around the primary
    for n in (20, 30, 40, 70, 100, 200):
        w = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime, n)
        results["variants"][f"primary_entry_{n}"] = evaluate(ts, opens, closes, w, RULE, 1.0)

    # classic Turtle exits
    for name, en, ex in (("turtle_20_10", 20, 10), ("turtle_55_20", 55, 20),
                         ("slow_390_156", 390, 156), ("sym_55_55", 55, 55)):
        w = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime, en, ex)
        results["variants"][name] = evaluate(ts, opens, closes, w, RULE, 1.0)

    # risk overlays on the primary
    w = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime,
                         PRIMARY_N, stop_k=3.0)
    results["variants"]["primary_atr_stop_3x5m"] = evaluate(ts, opens, closes, w, RULE, 1.0)
    w = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime,
                         PRIMARY_N, max_hold=78 * 5)
    results["variants"]["primary_time_exit_5d"] = evaluate(ts, opens, closes, w, RULE, 1.0)
    w = donchian_weights(ts, opens, closes, high, low, qqq_close, atr, regime,
                         PRIMARY_N, session_exit=True)
    results["variants"]["primary_flat_overnight"] = evaluate(ts, opens, closes, w, RULE, 1.0)

    # dual thrust
    for k in (0.3, 0.5):
        w = dual_thrust_weights(ts, opens, closes, high, low, qqq_close, atr, regime, k=k)
        results["variants"][f"dual_thrust_swing_k{k:g}"] = evaluate(ts, opens, closes, w, RULE, 1.0)
    w = dual_thrust_weights(ts, opens, closes, high, low, qqq_close, atr, regime, k=0.5,
                           day_trade=True, stop_k=3.0)
    results["variants"]["dual_thrust_daytrade_k0.5"] = evaluate(ts, opens, closes, w, RULE, 1.0)

    # 1-minute check of the primary entry rule
    ts1, o1, c1, h1, l1, q1, atr1, reg1 = load_panel("1min")
    w1 = donchian_weights(ts1, o1, c1, h1, l1, q1, atr1, reg1, PRIMARY_N)
    results["variants"]["primary_1m_entry_55"] = evaluate(ts1, o1, c1, w1, "1min", 1.0)

    # execution-lag sensitivity (weights shifted later by N bars)
    results["robustness"] = {"execution_lag": {}}
    for lag in (1, 2, 78):
        wd = np.zeros_like(w_primary)
        wd[lag:] = w_primary[:-lag]
        results["robustness"]["execution_lag"][f"lag_{lag}_bars"] = evaluate(
            ts, opens, closes, wd, RULE, 1.0)

    # benchmarks on the local panel
    for label, start in (("10y", START10), ("5y", START5)):
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR[RULE])
        results["benchmark"][label] = _clean(b)
    results["readme_benchmark"] = README_BENCH
    results["readme_baseline"] = README_BASELINE

    with open(here / "result.json", "w") as fh:
        json.dump(results, fh, indent=2, default=str)

    # console summary
    print("\n=== primary ===")
    for label in ("10y", "5y"):
        m = results["primary"]["windows"][label]
        print(f"{label}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sharpe {m['sharpe']:4.2f}  fills {m['fills']}  turn {m['turnover']:.1f}x  "
              f"TQQQ exposure {m['tqqq_bar_exposure']*100:.1f}%")
    print("pass vs TQQQ:", results["primary"]["pass_fail"])
    print("\n=== variants (10y / 5y CAGR, DD) ===")
    for name, v in results["variants"].items():
        print(f"{name:28s} {v['10y']['cagr']*100:6.2f}% / {v['5y']['cagr']*100:6.2f}%   "
              f"DD {v['10y']['max_drawdown']*100:5.2f}% / {v['5y']['max_drawdown']*100:5.2f}%")
    print(f"\nwrote {here / 'result.json'}")


if __name__ == "__main__":
    main()
