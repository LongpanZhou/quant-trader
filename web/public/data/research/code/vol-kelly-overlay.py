r"""Vol-spike reflation: standalone 1-minute realized-volatility strategy.

STATUS: SPEC + CODE ONLY. Backtests are paused by the lead. Do not run this
file, `bt.run`, `bt.run_many`, or generate `result.json` until authorized.

The strategy has no 165-day QQQ/TQQQ/SPY/NDX moving-average gate. It waits in
BIL, then buys a volatility-scaled TQQQ position after a fast 1-minute-RV
spike, an oversold 10-day drawdown, and the first up-close. It exits on
volatility normalization, a 3-session time stop, or a 4% QQQ price stop.

Development period: 2016-01-04 .. 2023-12-29. Holdout 2024-2026 is reserved
for the lead and is not loaded here.

Run from the repo root (only after authorization):
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/revisit/vol-kelly-overlay/strategy.py
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

HERE = Path(__file__).resolve().parent
DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BARS_1M = 252 * 390
BAND = 0.02
STATUS = "pending_test"  # set to passed / retired_overlay_only / rejected after audit

# Default parameters. The report lists the +/-1-step neighbourhood for each.
PARAMS = dict(
    spike_ratio=1.50,
    dd_window=10,
    dd_x=0.05,
    hold_sessions=3,      # includes the entry session
    target_vol=0.35,      # TQQQ volatility budget
    w_min=0.25,
    w_max=0.75,
    stop_x=0.04,          # QQQ stop from the actual next-open entry
    exit_ratio=1.00,      # v5/v20 normalization exit
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_daily():
    ts, opens, closes = bt.panel(SYMS, DEV_START, DEV_END, "1D")
    return ts, opens, closes


def load_rv(symbol: str, ts: pd.DatetimeIndex) -> np.ndarray:
    """Per-day within-day 1-minute realized variance, aligned to daily `ts`."""
    cache = HERE / "rv_dev.parquet"
    if cache.exists():
        rv = pd.read_parquet(cache)
        series = rv[symbol]
    else:
        df = bt.load_1m(symbol).sort_values("ts")
        df = df[df["ts"] < pd.Timestamp(DEV_END, tz="America/New_York")
                + pd.Timedelta(days=1)]
        prev = df.groupby("date")["close"].shift(1)
        r = np.log(df["close"] / prev)
        r = r.where(np.isfinite(r), 0.0)
        series = (r * r).groupby(df["date"]).sum()
    idx = pd.to_datetime(series.index)
    if idx.tz is None:
        idx = idx.tz_localize("America/New_York")
    else:
        idx = idx.tz_convert("America/New_York")
    series.index = idx
    series = series.reindex(pd.DatetimeIndex(ts).normalize()).ffill()
    return series.to_numpy()


# ---------------------------------------------------------------------------
# Signal and weights
# ---------------------------------------------------------------------------
def build_weights(ts, opens, closes, rv_t, params=None):
    """Return (weights, info) for the vol-spike reflation strategy.

    weights[i] is the target set at the close of day i and filled at the open
    of day i+1. The strategy is BIL by default. No moving-average gate.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)

    qqq = closes[:, 0]
    n = len(qqq)
    v5 = np.sqrt(pd.Series(rv_t).rolling(5).mean().to_numpy() * 252.0)
    v20 = np.sqrt(pd.Series(rv_t).rolling(20).mean().to_numpy() * 252.0)
    ratio = v5 / v20
    high = pd.Series(qqq).rolling(int(p["dd_window"])).max().to_numpy()
    dd = qqq / high - 1.0
    up = np.zeros(n, dtype=bool)
    up[1:] = qqq[1:] > qqq[:-1]

    spike = np.isfinite(ratio) & (ratio >= p["spike_ratio"])
    oversold = np.isfinite(dd) & (dd <= -p["dd_x"])
    signal = spike & oversold & up

    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    in_pos = False
    pending = False
    entry_i = 0
    entry_px = 0.0
    weight = 0.0
    events = []

    for i in range(n):
        # Fill the pending entry at today's open.
        if pending:
            pending = False
            in_pos = True
            entry_i = i
            entry_px = float(opens[i, 0])
            events.append({
                "signal_i": int(i - 1),
                "entry_i": int(i),
                "entry_px": entry_px,
                "weight": float(weight),
            })

        if in_pos:
            days = i - entry_i
            exit_now = (
                days >= int(p["hold_sessions"]) - 1
                or (np.isfinite(ratio[i]) and ratio[i] < p["exit_ratio"])
                or (qqq[i] <= entry_px * (1.0 - p["stop_x"]))
            )
            if exit_now:
                in_pos = False
                events[-1]["exit_i"] = int(i)
                if i + 1 < n:
                    events[-1]["exit_px"] = float(opens[i + 1, 0])
                else:
                    events[-1]["exit_px"] = float(closes[i, 0])
                w[i, 2] = 1.0
            else:
                w[i, 1] = weight
                w[i, 2] = 1.0 - weight
        else:
            if signal[i] and np.isfinite(v20[i]) and v20[i] > 0:
                weight = float(np.clip(p["target_vol"] / v20[i],
                                       p["w_min"], p["w_max"]))
                pending = True
                w[i, 1] = weight
                w[i, 2] = 1.0 - weight
            else:
                w[i, 2] = 1.0

    info = {
        "params": p,
        "v5": v5,
        "v20": v20,
        "ratio": ratio,
        "dd": dd,
        "signal": signal,
        "events": events,
        "n_events": len(events),
    }
    return w, info


def baseline_weights(ts, closes):
    """The old 165-day daily base, computed ONLY for correlation/benchmark.

    It never enters the strategy weights.
    """
    qqq = closes[:, 0]
    sma = pd.Series(qqq).rolling(165).mean().to_numpy()
    on = qqq > sma
    on[:165] = False
    w = np.zeros((len(qqq), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    return w


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def daily_returns(res):
    eq = res["equity"]
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    return r


def event_returns(res, info):
    """Strategy daily-return product over each event's holding window."""
    rets = daily_returns(res)
    out = []
    for e in info["events"]:
        a, b = e["entry_i"], e.get("exit_i")
        if b is None or b < a:
            continue
        out.append(float(np.prod(1.0 + rets[a:b + 1]) - 1.0))
    return np.asarray(out, dtype=float)


def bootstrap_p(vals, n_boot=10_000, seed=0):
    """One-sided bootstrap p-value for mean <= 0."""
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(n_boot, len(vals)))
    means = vals[idx].mean(axis=1)
    return float((means <= 0.0).mean())


def slice_stats(res, start, end, bars_per_year=252):
    ts = res["ts"]
    m = (ts >= pd.Timestamp(start, tz="America/New_York")) & (
        ts <= pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1))
    sub = {"ts": ts[m], "equity": res["equity"][m], "cash": res["cash"][m],
           "fills": res["fills"], "turnover": res["turnover"]}
    return bt.stats(sub, bars_per_year)


def stats_row(s):
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
    }


def run_dev(slip, marks="1D"):
    """Run one cost on the development period. marks='1D' or '1min'."""
    ts, op, cl = load_daily()
    rv = load_rv("TQQQ", ts)
    w, info = build_weights(ts, op, cl, rv)
    if marks == "1D":
        res = bt.run(ts, op, cl, w, start=DEV_START, band=BAND,
                     slippage_bps=slip)
        s = bt.stats(res, 252)
    else:
        ts1, o1, c1 = bt.panel(SYMS, DEV_START, DEV_END, "1min")
        w1 = to_minutes(ts, w, ts1, "1D")
        res = bt.run(ts1, o1, c1, w1, start=DEV_START, band=BAND,
                     slippage_bps=slip)
        s = bt.stats(res, BARS_1M)
    return res, s, info


def main():
    # This function writes result.json. It is intentionally not run while the
    # backtests are paused. The lead will authorize it.
    ts, op, cl = load_daily()
    rv = load_rv("TQQQ", ts)
    w, info = build_weights(ts, op, cl, rv)

    daily = {}
    minute = {}
    ts1, o1, c1 = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    w1 = to_minutes(ts, w, ts1, "1D")
    for slip in (1.0, 5.0, 10.0):
        rd = bt.run(ts, op, cl, w, start=DEV_START, band=BAND,
                    slippage_bps=slip)
        daily[str(int(slip))] = stats_row(bt.stats(rd, 252))
        rm = bt.run(ts1, o1, c1, w1, start=DEV_START, band=BAND,
                    slippage_bps=slip)
        minute[str(int(slip))] = stats_row(bt.stats(rm, BARS_1M))

    # Baseline: old 165-day base, for correlation only.
    wb = baseline_weights(ts, cl)
    rb = bt.run(ts, op, cl, wb, start=DEV_START, band=BAND, slippage_bps=1.0)
    sb = bt.stats(rb, 252)
    rd1 = bt.run(ts, op, cl, w, start=DEV_START, band=BAND, slippage_bps=1.0)
    corr_start = 165  # after the baseline SMA warmup
    corr = float(np.corrcoef(daily_returns(rd1)[corr_start:],
                             daily_returns(rb)[corr_start:])[0, 1])

    er = event_returns(rd1, info)
    ex = {
        "n_events": int(len(er)),
        "marks": "1D",
        "mean_event_return": float(np.mean(er)) if len(er) else None,
        "median_event_return": float(np.median(er)) if len(er) else None,
        "hit_rate": float(np.mean(er > 0)) if len(er) else None,
        "bootstrap_p": bootstrap_p(er) if len(er) else None,
        "best_event": float(np.max(er)) if len(er) else None,
        "worst_event": float(np.min(er)) if len(er) else None,
    }

    sub = {}
    for label, a, b in (("2016_19", "2016-01-04", "2019-12-31"),
                        ("2020_21", "2020-01-02", "2021-12-31"),
                        ("2022_23", "2022-01-03", "2023-12-29")):
        sub[label] = stats_row(slice_stats(rd1, a, b))

    b_t = bt.benchmark(cl[:, 1], ts, 252)
    b_q = bt.benchmark(cl[:, 0], ts, 252)
    out = {
        "agent": "vol-kelly-overlay",
        "original": "research/agents/vol-kelly-overlay",
        "status": STATUS,
        "idea": "Buy a volatility-scaled TQQQ position after a 1-minute-RV spike, an oversold QQQ drawdown and the first up-close; exit on vol normalization, a short time stop or a price stop.",
        "hypothesis": "Post-spike volatility mean reversion plus TQQQ convexity gives a positive 1-3 session rebound that is independent of the 165-day trend.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": {f"{k}bp": v for k, v in minute.items()},
            "holdout": {},
            "10y": {},
            "5y": {},
        },
        "dev_daily_marks": {f"{k}bp": v for k, v in daily.items()},
        "dev_events": ex,
        "dev_subperiods": sub,
        "marks": "1m",
        "benchmarks": {
            "tqqq": {"cagr": b_t["cagr"], "max_drawdown": b_t["max_drawdown"],
                     "sharpe": b_t["sharpe"]},
            "qqq": {"cagr": b_q["cagr"], "max_drawdown": b_q["max_drawdown"],
                    "sharpe": b_q["sharpe"]},
            "spy": "not available for 2016-2023 in the local archive",
            "original": {"cagr10": 0.4753, "dd10": 0.4532,
                         "cagr5": 0.3459, "dd5": 0.3629},
        },
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
