"""Shared plumbing for the three external cross-sectional / risk-appetite families.

Signals are built from daily closes in ``data/external/`` and mapped to the
local 1-minute QQQ/TQQQ/BIL panel with ``research/external.py``:

    targets[k]  = weights decided from the close of session k
    fill        = first bar open of session k+1

The development window is 2016-01-04 .. 2023-12-29.  Nothing here reads or
reports 2024-2026 performance during a development run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "research") not in sys.path:
    sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import external  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
BAND = 0.02
BARS_PER_YEAR = 252 * 390
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

TQQQ_BAR = {
    "cagr": 0.3672,
    "max_drawdown": 0.8229,
    "sharpe": 0.82,
}


def load_panel(start: str = START, end: str = END):
    return bt.panel(("QQQ", "TQQQ", "BIL"), start=start, end=end,
                    rule="1min", warmup_days=0)


def daily_closes(ts, closes):
    dates, first, last = bt.day_bounds(ts)
    return pd.DatetimeIndex(pd.to_datetime(dates[first])), closes[last]


def aligned(ts, symbols, end=None) -> pd.DataFrame:
    """External adjusted closes on the panel's session calendar (dev only)."""
    idx = external.session_index(ts)
    limit = pd.Timestamp(end) if end is not None else pd.Timestamp(END)
    if len(idx) == 0 or idx[-1] > limit:
        raise RuntimeError("development window exceeded; 2024-2026 is not loaded")
    return external.align(ts, list(symbols), end=limit)


def rolling_z(s: pd.Series, window: int = 252, min_periods: int = 120) -> pd.Series:
    """Trailing z-score; strictly backward-looking."""
    m = s.rolling(window, min_periods=min_periods).mean()
    sd = s.rolling(window, min_periods=min_periods).std()
    return (s - m) / sd


def state_weights(score: pd.Series, hi: float, lo: float) -> np.ndarray:
    """Three-state long-only map: TQQQ above `hi`, BIL below `lo`, else QQQ.

    Missing warm-up scores stay in QQQ (the neutral asset), never in leverage.
    """
    a = np.asarray(score, dtype=float)
    w = np.zeros((len(a), 3))
    w[:, 0] = 1.0
    good = np.isfinite(a)
    up = good & (a >= hi)
    dn = good & (a <= lo)
    w[up] = 0.0
    w[up, 1] = 1.0
    w[dn] = 0.0
    w[dn, 2] = 1.0
    return w


def to_minutes(ts, targets) -> np.ndarray:
    """Targets set at session close k are filled at session k+1's open."""
    return external.daily_targets_to_weights(ts, np.asarray(targets, dtype=float))


def simulate(ts, o, c, targets, bp: float = 1.0, fill_log: bool = False):
    return bt.run(ts, o, c, to_minutes(ts, targets), start=START, band=BAND,
                  slippage_bps=bp, fill_log=fill_log)


def metrics(res) -> dict:
    return bt.stats(res, BARS_PER_YEAR)


def daily_equity(ts, res) -> pd.Series:
    return bt.daily_last(res["equity"], ts)


def yearly(eq: pd.Series) -> dict:
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
        t = eq.index[m]
        years = (t[-1] - t[0]).days / 365.25
        r = np.diff(e) / e[:-1]
        out[name] = {
            "cagr": float((e[-1] / e[0]) ** (1.0 / years) - 1.0),
            "max_drawdown": float(-(e / np.maximum.accumulate(e) - 1.0).min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0,
        }
    return out


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


def placebo(ts, o, c, targets, real_cagr: float, real_sharpe: float,
            n: int = 100, seed: int = 7) -> dict:
    """Circular shifts preserve the allocation mix but destroy the timing."""
    rng = np.random.default_rng(seed)
    nd = len(targets)
    shifts = rng.choice(np.arange(30, nd - 30), size=min(n, nd - 60), replace=False)
    cagrs, sharpes, dds = [], [], []
    for s in shifts:
        w = np.roll(np.asarray(targets), int(s), axis=0)
        st = metrics(simulate(ts, o, c, w, bp=1.0))
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


def evaluate(ts, o, c, targets, n_placebo: int = 100) -> dict:
    targets = np.asarray(targets, dtype=float)
    r1 = simulate(ts, o, c, targets, bp=1.0, fill_log=True)
    stats = {}
    for bp in (1.0, 5.0, 10.0):
        stats[f"{int(bp)}bp"] = metrics(simulate(ts, o, c, targets, bp=bp))
    events = len({row["ts"] for row in r1["fills_log"]})
    eq = daily_equity(ts, r1)
    ret = eq.pct_change()
    static = simulate(ts, o, c, np.tile(targets.mean(axis=0), (len(targets), 1)),
                      bp=1.0)
    return {
        "stats": stats,
        "events": int(events),
        "yearly": yearly(eq),
        "subperiods": subperiods(eq),
        "corr_winners": winner_corr(ret),
        "avg_weights": [float(x) for x in targets.mean(axis=0)],
        "static_avg_weights": metrics(static),
        "placebo": placebo(ts, o, c, targets, stats["1bp"]["cagr"],
                           stats["1bp"]["sharpe"], n=n_placebo),
        "_daily_ret": ret,
    }


def plateau(ts, o, c, make_targets, grid) -> list[dict]:
    out = []
    for cell in grid:
        t = make_targets(cell)
        st = metrics(simulate(ts, o, c, t, bp=1.0))
        out.append({
            "cell": {k: (list(v) if isinstance(v, tuple) else v)
                     for k, v in cell.items()},
            "cagr": st["cagr"], "max_drawdown": st["max_drawdown"],
            "sharpe": st["sharpe"], "fills": st["fills"],
            "turnover": st["turnover"],
        })
    return out


def trend_control(ts, o, c, hi: float, lo: float):
    """QQQ 20/60 momentum with the same state map, as a trend-proxy control.

    Returns (stats, daily_returns).  If an external family only reproduces a
    QQQ price-trend switch, its return correlation to this control is high and
    the control's CAGR is close to the family's.
    """
    dates, closes = daily_closes(ts, c)
    q = pd.Series(np.log(closes[:, 0]), index=dates)
    s = (rolling_z(q.diff(20)) + rolling_z(q.diff(60))) / 2.0
    w = state_weights(s, hi, lo)
    r = simulate(ts, o, c, w, bp=1.0)
    return metrics(r), daily_equity(ts, r).pct_change()


def kill_checks(ev: dict, min_cagr: float = TQQQ_BAR["cagr"]) -> dict:
    st = ev["stats"]["1bp"]
    checks = {
        "cagr_below_tqqq_bar": st["cagr"] <= min_cagr,
        "drawdown_above_tqqq": st["max_drawdown"] >= TQQQ_BAR["max_drawdown"],
        "cost_10bp_below_bar": ev["stats"]["10bp"]["cagr"] <= min_cagr,
        "placebo_below_90pct": ev["placebo"]["cagr_percentile_of_real"] < 0.90,
        "correlation_above_0.95": max(ev["corr_winners"].values()) > 0.95,
        "fewer_than_100_fills": st["fills"] < 100,
        "fewer_than_30_events": ev["events"] < 30,
        "negative_subperiod": any(v["cagr"] < 0 for v in ev["subperiods"].values()),
        "static_blend_matches": (
            ev["static_avg_weights"]["cagr"] >= st["cagr"] - 0.01),
    }
    return {k: bool(v) for k, v in checks.items()}


def perturb_audit(ext: pd.DataFrame, make_targets, cutoff_offset: int = 0,
                  n: int = 25, seed: int = 11) -> dict:
    """Replace all external values after the decision cutoff with garbage.

    A causal signal at date i must not change.  `cutoff_offset=0` allows the
    same-session ETF close; `1` is used when the source bar closes after the
    US equity close (BTC).
    """
    base = make_targets(ext)
    rng = np.random.default_rng(seed)
    lo = 200
    hi = len(ext) - 5
    idxs = rng.choice(np.arange(lo, hi), size=min(n, hi - lo), replace=False)
    ok = 0
    for i in idxs:
        cut = int(i) - cutoff_offset
        e2 = ext.copy()
        future = np.arange(len(e2)) > cut
        e2.loc[future, :] = e2.loc[future, :].to_numpy() * 3.0 + 17.0
        t2 = make_targets(e2)
        ok += int(np.array_equal(base[int(i)], t2[int(i)]))
    return {"n": int(len(idxs)), "pass": int(ok),
            "cutoff_sessions_before_decision": int(cutoff_offset)}


def mapping_audit(ts, targets, n: int = 25, seed: int = 13) -> dict:
    """Check close-of-D target -> all bars of D+1 -> fill at D+1 first open."""
    w = to_minutes(ts, targets)
    dates, first, last = bt.day_bounds(ts)
    rng = np.random.default_rng(seed)
    idxs = rng.choice(np.arange(100, len(first) - 2),
                      size=min(n, len(first) - 102), replace=False)
    ok = 0
    for i in idxs:
        i = int(i)
        a, b = int(first[i + 1]), int(last[i + 1])
        held = np.allclose(w[a:b], targets[i])
        nxt = np.allclose(w[b], targets[i + 1])
        carried = np.allclose(w[int(last[i])], targets[i])
        ok += int(held and nxt and carried)
    return {"n": int(len(idxs)), "pass": int(ok)}


def write_result(path: Path, payload: dict) -> None:
    payload = {k: v for k, v in payload.items() if not k.startswith("_")}
    path.write_text(json.dumps(payload, indent=1, default=float))


def summary_line(st: dict) -> str:
    return (f"CAGR {st['cagr'] * 100:.2f}%  DD {st['max_drawdown'] * 100:.1f}%  "
            f"Sharpe {st['sharpe']:.2f}  Sortino {st['sortino']:.2f}  "
            f"vol {st['volatility'] * 100:.1f}%  exposure {st['exposure'] * 100:.1f}%  "
            f"fills {st['fills']}  turnover {st['turnover']:.0f}x")
