"""Shared evaluation helpers for the new family strategies.

All four strategies use the local 1-minute QQQ/TQQQ/BIL panel through
``research/bt.py``.  Signals are computed from the close of session ``t`` and
the target is executed at the next bar open.  This module only contains
plumbing; the signal lives in each ``strategy.py``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
BARS_PER_YEAR = 252 * 390
BAND = 0.02
WINNERS = [
    "ratio-froth",
    "vol-scaled-crash-stop",
    "relative-value-tqqq",
    "fomc-opex-window",
    "family-session-timing",
    "family-short-reversal",
    "family-rebalance-flow",
    "family-intraday-microstructure-day",
    "family-ml-microstructure",
]
CURVES = ROOT / "research" / "new" / "curves"
SPY_DAILY = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"


def load_panel(start: str = START, end: str = END):
    return bt.panel(("QQQ", "TQQQ", "BIL"), start=start, end=end,
                    rule="1min", warmup_days=0)


def daily_closes(ts, closes):
    dates, first, last = bt.day_bounds(ts)
    return pd.DatetimeIndex(pd.to_datetime(dates[first])), closes[last]


def expand(ts, daily_w: np.ndarray) -> np.ndarray:
    """Apply the target set at the close of day t to all bars of day t+1."""
    daily_w = np.asarray(daily_w, dtype=float)
    _, first, last = bt.day_bounds(ts)
    nd = len(first)
    if len(daily_w) != nd:
        raise ValueError(f"daily weights {len(daily_w)} != sessions {nd}")
    shifted = np.vstack([np.zeros((1, daily_w.shape[1])), daily_w[:-1]])
    return shifted[np.repeat(np.arange(nd), np.diff(np.r_[first, len(ts)]))]


def simulate(ts, o, c, w, bp=1.0, fill_log=False):
    return bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=bp,
                  fill_log=fill_log)


def metrics(res):
    return bt.stats(res, BARS_PER_YEAR)


def daily_equity(ts, res) -> pd.Series:
    dates, first, last = bt.day_bounds(ts)
    return pd.Series(res["equity"][last],
                     index=pd.DatetimeIndex(pd.to_datetime(dates[first])))


def load_spy(dates) -> pd.Series:
    """SPY adjusted close on the strategy's session dates, dev-window only."""
    # Push the date bound into the parquet reader so 2024-2026 rows are never
    # materialised during the development run.
    df = pd.read_parquet(
        SPY_DAILY,
        filters=[("date", "<=", pd.Timestamp(dates[-1]))],
    )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    s = df.set_index("date")["adjclose"]
    return s.reindex(dates).ffill().bfill()


def winner_corr(ret: pd.Series) -> dict:
    out = {}
    for slug in WINNERS:
        d = json.loads((CURVES / f"{slug}.json").read_text())
        s = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        r = s.pct_change()
        joined = pd.concat([ret.rename("s"), r.rename("w")], axis=1,
                           join="inner").dropna()
        out[slug] = float(joined["s"].corr(joined["w"]))
    return out


def yearly(ts, eq: pd.Series) -> dict:
    out = {}
    for year in range(2016, 2024):
        m = eq.index.year == year
        if int(np.sum(m)) < 2:
            continue
        e = eq[m].values
        out[str(year)] = float(e[-1] / e[0] - 1.0)
    return out


def subperiods(eq: pd.Series) -> dict:
    spans = [
        ("2016-2019", "2016-01-04", "2019-12-31"),
        ("2020-2021", "2020-01-02", "2021-12-31"),
        ("2022-2023", "2022-01-03", "2023-12-29"),
    ]
    out = {}
    for name, a, b in spans:
        m = (eq.index >= pd.Timestamp(a)) & (eq.index <= pd.Timestamp(b))
        e = eq[m].values
        years = (eq.index[m][-1] - eq.index[m][0]).days / 365.25
        r = np.diff(e) / e[:-1]
        out[name] = {
            "cagr": float((e[-1] / e[0]) ** (1.0 / years) - 1.0),
            "max_drawdown": float(-(e / np.maximum.accumulate(e) - 1.0).min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(BARS_PER_YEAR)),
        }
    return out


def static_weights(daily_w: np.ndarray) -> np.ndarray:
    avg = daily_w.mean(axis=0)
    return np.tile(avg, (len(daily_w), 1))


def placebo(ts, o, c, daily_w: np.ndarray, real_cagr: float, real_sharpe: float,
            n: int = 100, seed: int = 7) -> dict:
    """Circular shifts preserve the allocation path but destroy its timing."""
    rng = np.random.default_rng(seed)
    nd = len(daily_w)
    shifts = rng.choice(np.arange(30, nd - 30), size=min(n, nd - 60), replace=False)
    cagrs, sharpes, dds = [], [], []
    for s in shifts:
        w = np.roll(daily_w, int(s), axis=0)
        r = simulate(ts, o, c, expand(ts, w), bp=1.0)
        st = metrics(r)
        cagrs.append(st["cagr"])
        sharpes.append(st["sharpe"])
        dds.append(st["max_drawdown"])
    cagrs = np.asarray(cagrs)
    sharpes = np.asarray(sharpes)
    return {
        "n": int(len(shifts)),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p50": float(np.percentile(cagrs, 50)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
        "cagr_percentile_of_real": float((cagrs < real_cagr).mean()),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "sharpe_percentile_of_real": float((sharpes < real_sharpe).mean()),
        "dd_p50": float(np.percentile(dds, 50)),
    }


def evaluate(ts, o, c, daily_w: np.ndarray, n_placebo: int = 100) -> dict:
    """Core metrics, subperiods, correlations and placebos."""
    w_min = expand(ts, daily_w)
    r1 = simulate(ts, o, c, w_min, bp=1.0, fill_log=True)
    stats = {}
    for bp in (1.0, 5.0, 10.0):
        res = simulate(ts, o, c, w_min, bp=bp)
        stats[f"{int(bp)}bp"] = metrics(res)
    events = len({row["ts"] for row in r1["fills_log"]})
    eq = daily_equity(ts, r1)
    ret = eq.pct_change()
    static = simulate(ts, o, c,
                      expand(ts, static_weights(daily_w)), bp=1.0)
    return {
        "stats": stats,
        "events": int(events),
        "yearly": yearly(ts, eq),
        "subperiods": subperiods(eq),
        "corr_winners": winner_corr(ret),
        "avg_weights": [float(x) for x in daily_w.mean(axis=0)],
        "static_avg_weights": metrics(static),
        "placebo": placebo(ts, o, c, daily_w,
                           stats["1bp"]["cagr"], stats["1bp"]["sharpe"],
                           n=n_placebo),
        "_daily_ret": ret,
    }


def write_result(path: Path, payload: dict) -> None:
    payload = {k: v for k, v in payload.items() if not k.startswith("_")}
    path.write_text(json.dumps(payload, indent=1, default=float))


def summary_line(st: dict) -> str:
    return (f"CAGR {st['cagr'] * 100:.2f}%  DD {st['max_drawdown'] * 100:.1f}%  "
            f"Sharpe {st['sharpe']:.2f}  Sortino {st['sortino']:.2f}  "
            f"vol {st['volatility'] * 100:.1f}%  exposure {st['exposure'] * 100:.1f}%  "
            f"fills {st['fills']}  turnover {st['turnover']:.0f}x")
