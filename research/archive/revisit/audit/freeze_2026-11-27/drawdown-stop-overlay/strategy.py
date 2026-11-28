"""Failed-breakdown spring: stand-alone rebuild of `drawdown-stop-overlay`.

Original idea (research/agents/drawdown-stop-overlay)
-----------------------------------------------------
An intraday stop at the exact 165-day QQQ SMA threshold, plus a 10-day-high
TQQQ re-entry.  That is a risk overlay on the 165-day QQQ -> TQQQ base; the
stop only decides when to step aside from the base's long position.

This rebuild
------------
The new idea is the *failure* of the breakdown, not the stop itself.  When QQQ
undercuts its prior 20-session low intraday but closes back above that low,
with the close in the upper half of the day's range, the break was a stop run
/ liquidity sweep (Wyckoff "spring").  The forced sellers are exhausted.  Buy
TQQQ at the next open, hold up to 5 sessions, and exit on a new 10-day QQQ
high, an 8% hard stop from the entry, or time.

This is a complete event-driven long strategy with its own universe, signal,
holding period, sizing and risk.  It does **not** use:
  - any 100-250 day QQQ/TQQQ/SPY/NDX moving-average gate;
  - the old 165-day baseline weights;
  - any old build_weights code.

Development window only: 2016-01-04 .. 2023-12-29.
The 2024-2026 holdout is intentionally not touched here; the lead runs it once
after audit.  10y/5y windows are also left to the lead because they overlap
the holdout.

Backtests are currently PAUSED.  `main()` is complete but must not be run
until the lead/user authorises the test.
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
from minute_marks import to_minutes  # noqa: E402

DEV0 = "2016-01-04"
DEV1 = "2023-12-29"
BARS_1M = 252 * 390

# One-at-a-time parameter neighbourhood around the primary spec.
VARIANTS = {
    "primary":   dict(lookback=20, hold=5, stop=0.08, range_pos=0.50, size=1.00),
    "lookback10": dict(lookback=10, hold=5, stop=0.08, range_pos=0.50, size=1.00),
    "lookback30": dict(lookback=30, hold=5, stop=0.08, range_pos=0.50, size=1.00),
    "hold3":     dict(lookback=20, hold=3, stop=0.08, range_pos=0.50, size=1.00),
    "hold10":    dict(lookback=20, hold=10, stop=0.08, range_pos=0.50, size=1.00),
    "stop6":     dict(lookback=20, hold=5, stop=0.06, range_pos=0.50, size=1.00),
    "stop10":    dict(lookback=20, hold=5, stop=0.10, range_pos=0.50, size=1.00),
    "range04":   dict(lookback=20, hold=5, stop=0.08, range_pos=0.40, size=1.00),
    "range06":   dict(lookback=20, hold=5, stop=0.08, range_pos=0.60, size=1.00),
    "size50":    dict(lookback=20, hold=5, stop=0.08, range_pos=0.50, size=0.50),
}


def load_daily_qqq_ohlc(tsd: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily QQQ OHLC from the regular-session 1-minute tape, aligned to `tsd`."""
    df = bt.load_1m("QQQ")
    df = df[
        (df["ts"] >= pd.Timestamp(DEV0, tz="America/New_York"))
        & (df["ts"] < pd.Timestamp(DEV1, tz="America/New_York") + pd.Timedelta(days=1))
    ].copy()
    df["day"] = pd.to_datetime(df["ts"].dt.date)
    g = df.groupby("day").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    )
    days = pd.DatetimeIndex(tsd).tz_localize(None).normalize()
    g = g.reindex(days).ffill()
    # TQQQ session open/close: the spec's hard stop is on TQQQ, not QQQ
    # (tuning fix 2026-11-27; the original code compared QQQ prices).
    t = bt.load_1m("TQQQ")
    t = t[(t["ts"] >= pd.Timestamp(DEV0, tz="America/New_York"))
          & (t["ts"] < pd.Timestamp(DEV1, tz="America/New_York") + pd.Timedelta(days=1))].copy()
    t["day"] = pd.to_datetime(t["ts"].dt.date)
    tg = t.groupby("day").agg(tq_open=("open", "first"), tq_close=("close", "last"))
    g = g.join(tg.reindex(days).ffill())
    if g.isna().any().any():
        raise ValueError("daily QQQ/TQQQ OHLC has gaps in the development window")
    return g


def signal_and_exit_arrays(g: pd.DataFrame, lookback: int, hold: int,
                           stop: float, range_pos: float):
    """Return the daily signal and the prior-high array used for exits."""
    close = g["close"].to_numpy()
    low = g["low"].to_numpy()
    high = g["high"].to_numpy()
    low_n = pd.Series(low).rolling(lookback).min().shift(1).to_numpy()
    high_10 = pd.Series(close).rolling(10).max().shift(1).to_numpy()
    rng = np.where(high > low, (close - low) / (high - low), 0.0)
    sig = (
        np.isfinite(low_n)
        & (low < low_n)
        & (close > low_n)
        & (rng >= range_pos)
    )
    return sig, high_10


def build_daily_weights(g: pd.DataFrame, lookback: int = 20, hold: int = 5,
                        stop: float = 0.08, range_pos: float = 0.50,
                        size: float = 1.00):
    """Daily target weights set at the close, filled at the next open.

    Returns (w_daily, info).  `w_daily[d]` is the target set at the close of
    day d and held during day d+1.  The state machine is flat initially.
    """
    sig, _ = signal_and_exit_arrays(g, lookback, hold, stop, range_pos)
    w, info = build_daily_weights_from_signal(g, sig, hold=hold, stop=stop, size=size)
    info.update({"signal_days": int(sig.sum()), "lookback": lookback,
                 "range_pos": range_pos})
    return w, info


def build_daily_weights_from_signal(g: pd.DataFrame, sig: np.ndarray, hold: int = 5,
                                    stop: float = 0.08, size: float = 1.00):
    """The entry/exit state machine for an arbitrary boolean daily signal.

    Used by the headline and by the random-entry placebo, so both share the
    exact same holding, stop and recovery rules.
    """
    close = g["close"].to_numpy()
    tq_open = g["tq_open"].to_numpy()
    tq_close = g["tq_close"].to_numpy()
    high_10 = pd.Series(close).rolling(10).max().shift(1).to_numpy()

    n = len(close)
    target = np.zeros(n)
    pos = 0
    entry_day = -1
    entry_px = np.nan
    entries = []
    exits = []
    reasons = {"stop": 0, "recovery": 0, "time": 0}

    for d in range(n - 1):
        if pos == 1:
            held = d - entry_day + 1
            stop_hit = tq_close[d] <= entry_px * (1.0 - stop)
            high_hit = np.isfinite(high_10[d]) and close[d] >= high_10[d]
            time_hit = held >= hold
            new_pos = 0 if (stop_hit or high_hit or time_hit) else 1
            if new_pos == 0:
                exits.append(str(g.index[d].date()))
                reasons["stop" if stop_hit else "recovery" if high_hit else "time"] += 1
        else:
            new_pos = 1 if sig[d] else 0
            if new_pos == 1:
                entry_day = d + 1
                entry_px = float(tq_open[d + 1])
                entries.append(
                    {
                        "signal_date": str(g.index[d].date()),
                        "entry_date": str(g.index[d + 1].date()),
                        "entry_px_tqqq": entry_px,
                        "qqq_low": float(g["low"].iloc[d]),
                        "qqq_close": float(close[d]),
                    }
                )
        target[d] = new_pos
        pos = new_pos

    w = np.zeros((n, 3))
    w[:, 1] = size * target
    w[:, 2] = 1.0 - size * target
    info = {
        "entries": entries,
        "exits": exits,
        "exit_reasons": reasons,
        "hold": hold,
        "stop": stop,
        "size": size,
    }
    return w, info


def control_dip_weights(g: pd.DataFrame, hold: int = 5, stop: float = 0.08,
                        size: float = 1.0, dip: float = -0.01):
    """Placebo control: buy after any QQQ close-to-close day <= `dip`.

    This keeps the same holding/exit machinery but removes the failed-
    breakdown condition.  If the primary does not beat this control, the
    20-day-low reclaim adds nothing.
    """
    close = g["close"].to_numpy()
    ret = np.r_[np.nan, np.diff(close) / close[:-1]]
    sig = np.isfinite(ret) & (ret <= dip)
    return build_daily_weights_from_signal(g, sig, hold=hold, stop=stop, size=size)[0]


def _stats(run: dict, bars: int = BARS_1M):
    s = bt.stats(run, bars)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "fills", "turnover", "exposure")}


def _daily_returns(run: dict) -> pd.Series:
    df = pd.DataFrame({"ts": run["ts"], "eq": run["equity"]})
    e = df.groupby(df.ts.dt.date)["eq"].last()
    e.index = pd.to_datetime(e.index)
    return e.pct_change().dropna()


def _corr(a: pd.Series, b: pd.Series) -> float:
    x, y = a.align(b, join="inner")
    return float(np.corrcoef(x.to_numpy(), y.to_numpy())[0, 1])


def build_baseline(tsd: pd.DatetimeIndex, cd: np.ndarray):
    """The old 165-day baseline, used only for comparison/correlation."""
    qqq = cd[:, 0]
    sma = pd.Series(qqq).rolling(165).mean().to_numpy()
    on = np.zeros(len(tsd), bool)
    ok = np.isfinite(sma)
    on[ok] = qqq[ok] > sma[ok]
    w = np.zeros((len(tsd), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    return w


def main() -> None:
    # Panels: 1-minute marks and daily decisions, development window only.
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1D")
    g = load_daily_qqq_ohlc(tsd)

    # Build every variant's daily target, then map to 1-minute bars.
    names, w1_list, infos = [], [], {}
    for name, params in VARIANTS.items():
        w_d, info = build_daily_weights(g, **params)
        w_m = to_minutes(tsd, w_d, ts1, "1D")
        names.append(name)
        w1_list.append(w_m)
        infos[name] = info

    # The 165-day baseline, for comparison and correlation only.
    wb_d = build_baseline(tsd, cd)
    wb_m = to_minutes(tsd, wb_d, ts1, "1D")

    # Headline at 1 bp; costs at 5/10 bp for the primary only (plus neighbours).
    r1 = bt.run_many(ts1, o1, c1, w1_list, DEV0, band=0.02, slippage_bps=1.0)
    r5 = bt.run_many(ts1, o1, c1, w1_list, DEV0, band=0.02, slippage_bps=5.0)
    r10 = bt.run_many(ts1, o1, c1, w1_list, DEV0, band=0.02, slippage_bps=10.0)
    rb = bt.run(ts1, o1, c1, wb_m, DEV0, band=0.02, slippage_bps=1.0)

    base_ret = _daily_returns(rb)
    out = {}
    for j, name in enumerate(names):
        s1, s5, s10 = _stats(r1[j]), _stats(r5[j]), _stats(r10[j])
        out[name] = {
            "1bp": s1, "5bp": s5, "10bp": s10,
            "corr_vs_165d_baseline": _corr(_daily_returns(r1[j]), base_ret),
            "signal_days": infos[name]["signal_days"],
            "entries": infos[name]["entries"][:20],
            "exits": infos[name]["exits"][:20],
        }

    # Placebo control on the primary holding/exit rules.
    wc_d = control_dip_weights(g)
    wc_m = to_minutes(tsd, wc_d, ts1, "1D")
    rc = bt.run(ts1, o1, c1, wc_m, DEV0, band=0.02, slippage_bps=1.0)
    control = {"1bp": _stats(rc),
               "corr_vs_165d_baseline": _corr(_daily_returns(rc), base_ret)}

    # Benchmarks on daily closes (and the baseline minute marks).
    itq = bt.start_index(tsd, DEV0)
    bench = {
        "tqqq": bt.benchmark(cd[itq:, 1], tsd[itq:], 252),
        "qqq": bt.benchmark(cd[itq:, 0], tsd[itq:], 252),
        "spy": None,  # only 60 days of SPY in data/cache/dukascopy; not usable for 2016-2023
        "original": json.load(open(ROOT / "research/agents/drawdown-stop-overlay/result.json"))
        if (ROOT / "research/agents/drawdown-stop-overlay/result.json").exists() else None,
        "baseline_165d": _stats(rb),
    }

    result = {
        "agent": "drawdown-stop-overlay",
        "original": "research/agents/drawdown-stop-overlay",
        "status": "pending",
        "idea": "A failed breakdown / stop-run reclaim: buy TQQQ after QQQ undercuts its prior 20-day low intraday but closes back above it.",
        "hypothesis": "Forced selling from a failed breakdown is exhausted; the next few days tend to rebound, so an event-driven TQQQ long with a 5-day hold beats a pure stop overlay and has low correlation with the old 165-day base.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": len(VARIANTS) + 1,
        "corr_vs_165d_baseline": out["primary"]["corr_vs_165d_baseline"],
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": {k: out["primary"][k] for k in ("1bp", "5bp", "10bp")},
            "holdout": None,
            "10y": None,
            "5y": None,
        },
        "marks": "1m",
        "benchmarks": bench,
        "control": control,
        "variants": out,
        "note": "Development window only 2016-01-04..2023-12-29. Holdout 2024-2026 and the 10y/5y windows were not run; the lead runs the frozen strategy on the holdout once.",
    }
    out_path = Path(__file__).resolve().parent / "result.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "corr_vs_165d_baseline", "windows")}, indent=2))
    print("wrote", out_path)


if __name__ == "__main__":
    main()
