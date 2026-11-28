"""Revisit: `ratio-pairs` rebuilt as a standalone leverage-cycle allocation.

Pre-registered design (see HYPOTHESIS.md).  Backtests are paused: do not run
this file until the lead authorises the test.

Idea
----
The TQQQ/QQQ ratio is a leverage-cycle meter, not a trend filter:

    log(TQQQ/QQQ) = 2*log(QQQ) - 3*realised variance + financing/tracking noise

The strategy is unleveraged by default (QQQ), holds cash when the ratio is
frothy or when the ratio-implied variance is expanding, and holds a bounded
40% TQQQ sleeve only when the ratio is deeply discounted and turning up.

There is no QQQ/TQQQ/SPY/NDX moving-average gate anywhere in this file.  The
only moving average is on the ratio itself, used to detrend the spread.

Development window: 2016-01-04 .. 2023-12-29.  The holdout
(2024-01-02 .. 2026-10-23) must not be loaded until the lead runs the frozen
strategy once.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS_1M = 252 * 390

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
T10, T5 = "2017-01-03", "2021-10-25"
FULL_END = "2026-10-23"
# The lead flips this to FULL_END for the single frozen holdout run.
PANEL_END = DEV_END

SYMS = ("QQQ", "TQQQ", "BIL")
COL = {"QQQ": 0, "TQQQ": 1, "BIL": 2}


@dataclass(frozen=True)
class Params:
    ext_ma: int = 200        # ratio detrend window (NOT a QQQ/TQQQ MA gate)
    froth: float = 0.20      # log-extension above which we hold cash
    deep: float = -0.30      # log-extension below which leverage is cheap
    stress_hi: float = 1.75  # v20 / v60 variance-expansion kill switch
    turn_look: int = 20      # sessions used for the "ratio turning up" test
    tqqq_deep: float = 0.40  # bounded 3x sleeve in the capitulation state
    qqq_deep: float = 0.30
    qqq_core: float = 0.90   # default unleveraged core
    cash_core: float = 0.10


# --------------------------------------------------------------------------- #
# panel and session plumbing
# --------------------------------------------------------------------------- #
def load(panel_end: str = PANEL_END):
    return bt.panel(SYMS, DEV_START, panel_end, "1min", warmup_days=420)


def session_bounds(ts: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    dates = np.asarray(ts.date)
    change = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change - 1, [len(ts) - 1]))
    return starts, ends


# --------------------------------------------------------------------------- #
# ratio signals
# --------------------------------------------------------------------------- #
def ratio_table(ts, closes, starts, ends, p: Params) -> pd.DataFrame:
    """One row per session, all columns computed from that session's close."""
    d = pd.DataFrame({
        "qqq_c": closes[ends, 0],
        "tqqq_c": closes[ends, 1],
        "bil_c": closes[ends, 2],
    }, index=pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize())
    d["ratio"] = d["tqqq_c"] / d["qqq_c"]
    d["logr"] = np.log(d["ratio"])
    d["ext"] = d["logr"] - d["logr"].rolling(p.ext_ma).mean()
    # Exact daily shortfall of TQQQ against a 3x QQQ log return: ~3*r^2.
    dq = np.log(d["qqq_c"]).diff()
    dt = np.log(d["tqqq_c"]).diff()
    d["dv"] = (3.0 * dq - dt).clip(lower=0.0)
    d["v20"] = d["dv"].rolling(20).mean()
    d["v60"] = d["dv"].rolling(60).mean()
    d["stress"] = d["v20"] / d["v60"]
    d["turn"] = d["ext"] - d["ext"].shift(p.turn_look)
    return d


def day_targets(d: pd.DataFrame, p: Params) -> tuple[np.ndarray, dict]:
    """Target weights for each session, using the PRIOR session's signals.

    Row k is the target applied from session k's first bar; it uses d row k-1.
    """
    n = len(d)
    ext = d["ext"].shift(1).to_numpy()
    stress = d["stress"].shift(1).to_numpy()
    turn = d["turn"].shift(1).to_numpy()

    risk_off = (np.nan_to_num(ext, nan=-9.0) > p.froth) | \
               (np.nan_to_num(stress, nan=-9.0) > p.stress_hi)
    deep_buy = (~risk_off) & (np.nan_to_num(ext, nan=0.0) < p.deep) & \
               (np.nan_to_num(turn, nan=-9.0) > 0.0)
    core = ~(risk_off | deep_buy)

    tgt = np.zeros((n, 3))
    tgt[risk_off] = (0.0, 0.0, 1.0)
    tgt[deep_buy] = (p.qqq_deep, p.tqqq_deep,
                     1.0 - p.qqq_deep - p.tqqq_deep)
    tgt[core] = (p.qqq_core, 0.0, p.cash_core)
    if n:                      # first row has no signal
        tgt[0] = (0.0, 0.0, 1.0)
    info = {
        "sessions": int(n),
        "risk_off_sessions": int(risk_off.sum()),
        "deep_buy_sessions": int(deep_buy.sum()),
        "core_sessions": int(core.sum()),
        "mean_equity": float(1.0 - tgt[:, 2].mean()),
        "mean_tqqq": float(tgt[:, 1].mean()),
    }
    return tgt, info


def broadcast(ts, starts, ends, day_w: np.ndarray) -> np.ndarray:
    w = np.zeros((len(ts), 3))
    for k, (a, b) in enumerate(zip(starts, ends)):
        w[a:b + 1] = day_w[k]
    return w


def build_weights(ts, opens, closes, params: Params = Params()
                  ) -> tuple[np.ndarray, dict]:
    """Target weights for the leverage-cycle allocation (full warmup panel)."""
    starts, ends = session_bounds(ts)
    d = ratio_table(ts, closes, starts, ends, params)
    day, info = day_targets(d, params)
    w = broadcast(ts, starts, ends, day)
    info["params"] = asdict(params)
    return w, info


def baseline_weights(ts, closes) -> np.ndarray:
    """The old shared base, built ONLY to measure correlation against."""
    starts, ends = session_bounds(ts)
    qqq = pd.Series(closes[ends, 0],
                    index=pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize())
    sma = qqq.rolling(165).mean()
    reg = (qqq.shift(1) > sma.shift(1)).fillna(False).to_numpy()
    day = np.zeros((len(starts), 3))
    day[reg, 1] = 1.0
    day[~reg, 2] = 1.0
    return broadcast(ts, starts, ends, day)


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def slice_idx(ts, lo, hi):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York"), side="right"))
    return i, j


def run_window(w, ts, op, cl, lo, hi, slip):
    i, j = slice_idx(ts, lo, hi)
    res = bt.simulate(ts[i:j], op[i:j], cl[i:j], w[i:j],
                      band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_returns(res):
    eq = pd.Series(res["equity"], index=res["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def window_block(w, ts, op, cl, lo, hi):
    out = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_window(w, ts, op, cl, lo, hi, slip)
        out[f"{slip:.0f}bp"] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
        }
    return out


def spy_benchmark(lo, hi):
    path = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    m = (df["date"] >= pd.Timestamp(lo)) & (df["date"] <= pd.Timestamp(hi))
    c = df.loc[m, "adjclose"].to_numpy()
    if len(c) < 10:
        return None
    years = (df.loc[m, "date"].iloc[-1] - df.loc[m, "date"].iloc[0]).days / 365.25
    peak = np.maximum.accumulate(c)
    rets = np.diff(c) / c[:-1]
    return {"cagr": float((c[-1] / c[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(c / peak - 1).min()),
            "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(252))}


def main() -> None:
    ts, op, cl = load(PANEL_END)
    print(f"panel: {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0]} .. {ts[-1]}")
    w, info = build_weights(ts, op, cl)
    print("states:", {k: v for k, v in info.items() if k != "params"})

    base = baseline_weights(ts, cl)
    bres, bstats = run_window(base, ts, op, cl, DEV_START, DEV_END, 1.0)
    bdr = daily_returns(bres)
    sres, sstats = run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
    corr = float(daily_returns(sres).corr(bdr))
    print(f"dev: CAGR {sstats['cagr']*100:.2f}%  DD {sstats['max_drawdown']*100:.2f}%  "
          f"Sharpe {sstats['sharpe']:.2f}  corr {corr:.2f}")

    d0, d1 = slice_idx(ts, DEV_START, DEV_END)
    qqq_bench = bt.benchmark(cl[d0:d1, 0], ts[d0:d1], BARS_1M)
    status = "passed" if (corr < 0.60 and sstats["sharpe"] > qqq_bench["sharpe"]) else "rejected"

    w10 = window_block(w, ts, op, cl, T10, DEV_END)
    w10["note"] = "truncated at 2023-12-29; holdout not inspected"
    w5 = window_block(w, ts, op, cl, T5, DEV_END)
    w5["note"] = "truncated at 2023-12-29; holdout not inspected"

    out = {
        "agent": "ratio-pairs",
        "original": "research/agents2/ratio-pairs",
        "status": status,
        "status_note": "provisional: dev gates only, pending independent audit",
        "idea": ("The TQQQ/QQQ ratio is a leverage-cycle meter: froth precedes "
                 "amplified shocks, a deep discount with a turn precedes convex "
                 "rebounds, and the average state does not pay for 3x drag."),
        "hypothesis": ("Hold QQQ by default, cash in ratio froth or variance "
                       "expansion, and a bounded 40% TQQQ sleeve only after a "
                       "deep ratio discount turns up."),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": window_block(w, ts, op, cl, DEV_START, DEV_END),
            "holdout": None,
            "10y": w10,
            "5y": w5,
        },
        "marks": "1m",
        "benchmarks": {
            "tqqq": bt.benchmark(cl[d0:d1, 1], ts[d0:d1], BARS_1M),
            "qqq": qqq_bench,
            "spy": spy_benchmark(DEV_START, DEV_END),
            "original": _original_numbers(),
        },
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


def _original_numbers():
    path = ROOT / "research" / "agents2" / "ratio-pairs" / "result.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    return {"windows": d.get("windows", {}),
            "cost_sensitivity": d.get("cost_sensitivity", {})}


if __name__ == "__main__":
    main()
