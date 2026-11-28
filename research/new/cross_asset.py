"""Shared plumbing for the reserve cross-asset families.

The four strategies use external daily series for the signal and the local
1-minute QQQ/TQQQ/BIL panel for execution:

    * signals are computed on daily closes through session ``k``;
    * ``targets[k]`` is the target written at session ``k``'s 15:59 close and
      filled at session ``k+1``'s 09:30 open;
    * ``research/external.daily_targets_to_weights`` performs that mapping, so
      every bar inside session ``k`` carries the target set at ``k-1``'s close.

External parquet files are read with a date filter tied to the panel's last
session.  A development panel ending 2023-12-29 therefore never materialises
2024-2026 rows; a later replay panel extends the bound to its own end.  QQQ's
daily signal leg comes from the local Yahoo daily file (also filtered); the
QQQ/TQQQ/BIL execution prices come from the 1-minute panel.

Only plumbing lives here; each ``strategy.py`` owns its signal.
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
FULL_END = "2026-10-23"
DEV_END = pd.Timestamp(END)
BARS_PER_YEAR = 252 * 390
BAND = 0.02
WARM_START = pd.Timestamp("2015-01-02")
CURVES = ROOT / "research" / "new" / "curves"

# Published development bar (winner.md / FAMILY_POLICY.md).
TQQQ_BAR_CAGR = 0.3672
TQQQ_BAR_DD = 0.8229

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


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load_panel():
    return bt.panel(("QQQ", "TQQQ", "BIL"), start=START, end=END,
                    rule="1min", warmup_days=0)


def session_index(ts) -> pd.DatetimeIndex:
    """Panel session dates, tz-naive (delegates to ``external.session_index``)."""
    return external.session_index(ts)


def _filtered_external(symbol: str, end=DEV_END) -> pd.Series:
    """`external.load` with the date bound pushed into the parquet reader."""
    name = symbol.replace("^", "").replace("=", "_")
    path = ROOT / "data" / "external" / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path, filters=[("date", "<=", end)])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _qqq_daily(end=DEV_END) -> pd.Series:
    path = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    df = pd.read_parquet(path, filters=[("date", "<=", end)])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def daily_frame(ts, symbols: list[str]) -> pd.DataFrame:
    """Daily total-return levels on the QQQ session calendar.

    The frame starts at 2015-01-02 so a 252-session normalisation is already
    warm at the first development session.  QQQ comes from the local Yahoo
    daily file; the other legs come from ``data/external``.

    The read bound follows the panel: 2023-12-29 for the development panel, or
    the panel's own last session for a later replay.
    """
    sess = session_index(ts)
    end = pd.Timestamp(FULL_END) if sess[-1] > pd.Timestamp(END) else DEV_END
    cal = _qqq_daily(end)
    cal = cal[(cal.index >= WARM_START) & (cal.index <= end)]
    if cal.index.min() > WARM_START:
        raise ValueError("QQQ daily history does not reach the warm-up start")
    if cal.index.max() < sess[-1]:
        raise ValueError("QQQ daily history ends before the panel")
    out = pd.DataFrame(index=cal.index)
    for sym in symbols:
        if sym == "QQQ":
            s = cal
        else:
            s = _filtered_external(sym, end)
        s = s.reindex(cal.index).ffill()
        if s.isna().any():
            raise ValueError(f"{sym}: NaN inside the daily signal frame")
        out[sym] = s
    return out


def relative_z(daily: pd.DataFrame, left: str, right: str, lookback: int,
               norm_window: int = 252, min_periods: int = 120) -> pd.Series:
    """Volatility-normalised ``left/right`` relative momentum.

    ``rel = log(left_t/left_{t-L}) - log(right_t/right_{t-L})``; the z-score
    divides by the trailing standard deviation of ``rel``.  Both legs use data
    through the same close, so the signal is synchronous.
    """
    rel = (np.log(daily[left].astype(float)) - np.log(daily[left].astype(float).shift(lookback))
           - np.log(daily[right].astype(float)) + np.log(daily[right].astype(float).shift(lookback)))
    sd = rel.rolling(norm_window, min_periods=min_periods).std()
    return rel / sd


def map_relative(z: pd.Series, threshold: float, mapping: str) -> pd.DataFrame:
    """TQQQ when relative leadership is intact; QQQ/BIL when it breaks down.

    binary: z > threshold -> TQQQ, else QQQ.
    ladder: z > threshold -> TQQQ; threshold-0.5 < z <= threshold -> QQQ;
            z <= threshold-0.5 -> BIL.
    """
    tq = (z > threshold).to_numpy()
    out = np.zeros((len(z), 3))
    if mapping == "binary":
        out[tq] = (0.0, 1.0, 0.0)          # leadership -> TQQQ
        out[~tq] = (1.0, 0.0, 0.0)         # large-cap defensive -> QQQ
    elif mapping == "ladder":
        mid = (z > threshold - 0.5).to_numpy()
        out[tq] = (0.0, 1.0, 0.0)
        out[~tq & mid] = (1.0, 0.0, 0.0)
        out[~mid] = (0.0, 0.0, 1.0)
    else:
        raise ValueError(mapping)
    return pd.DataFrame(out, index=z.index, columns=("QQQ", "TQQQ", "BIL"))


def targets_for_sessions(ts, daily_targets: pd.DataFrame) -> np.ndarray:
    """Select the panel's sessions from a daily target frame."""
    sess = session_index(ts)
    x = daily_targets.reindex(sess)
    if x.isna().any().any():
        raise ValueError("daily target frame does not cover every panel session")
    t = x.to_numpy(dtype=float)
    if t.min() < -1e-12 or t.sum(axis=1).max() > 1.0 + 1e-9:
        raise ValueError("targets violate long-only / sum <= 1")
    return t


# ---------------------------------------------------------------------------
# simulation and metrics
# ---------------------------------------------------------------------------
def weights(ts, targets: np.ndarray) -> np.ndarray:
    return external.daily_targets_to_weights(ts, targets)


def simulate(ts, o, c, w, bp=1.0, fill_log=False):
    return bt.run(ts, o, c, w, start=START, band=BAND, slippage_bps=bp,
                  fill_log=fill_log)


def metrics(res) -> dict:
    return bt.stats(res, BARS_PER_YEAR)


def daily_equity(ts, res) -> pd.Series:
    dates, _, last = bt.day_bounds(ts)
    idx = pd.DatetimeIndex(pd.to_datetime(dates[last])).tz_localize(None).normalize()
    return pd.Series(res["equity"][last], index=idx)


def _corr(a: pd.Series, b: pd.Series) -> float:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if len(j) < 10:
        return float("nan")
    return float(j["a"].corr(j["b"]))


def winner_corr(ret: pd.Series) -> dict:
    out = {}
    for slug in WINNERS:
        d = json.loads((CURVES / f"{slug}.json").read_text(encoding="utf-8"))
        s = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        s = s[s.index <= DEV_END]
        out[slug] = _corr(ret, s.pct_change())
    return out


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
        if len(e) < 10:
            continue
        years = (eq.index[m][-1] - eq.index[m][0]).days / 365.25
        r = np.diff(e) / e[:-1]
        out[name] = {
            "cagr": float((e[-1] / e[0]) ** (1.0 / years) - 1.0),
            "max_drawdown": float(-(e / np.maximum.accumulate(e) - 1.0).min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252.0)) if r.std() > 0 else 0.0,
        }
    return out


def static_blend(ts, o, c, targets: np.ndarray):
    avg = targets.mean(axis=0)
    w = external.daily_targets_to_weights(ts, np.tile(avg, (len(targets), 1)))
    return simulate(ts, o, c, w, bp=1.0), avg


def placebo(ts, o, c, targets: np.ndarray, real_cagr: float, real_sharpe: float,
            n: int = 100, seed: int = 11) -> dict:
    """Circular shifts preserve the allocation path but destroy its timing."""
    rng = np.random.default_rng(seed)
    nd = len(targets)
    shifts = rng.choice(np.arange(30, nd - 30), size=min(n, nd - 60), replace=False)
    cagrs, sharpes, dds = [], [], []
    for s in shifts:
        t = np.roll(targets, int(s), axis=0)
        r = simulate(ts, o, c, weights(ts, t), bp=1.0)
        st = metrics(r)
        cagrs.append(st["cagr"])
        sharpes.append(st["sharpe"])
        dds.append(st["max_drawdown"])
    cagrs = np.asarray(cagrs)
    sharpes = np.asarray(sharpes)
    dds = np.asarray(dds)
    return {
        "n": int(len(shifts)),
        "seed": int(seed),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p50": float(np.percentile(cagrs, 50)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
        "cagr_max": float(cagrs.max()),
        "cagr_percentile_of_real": float((cagrs < real_cagr).mean()),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "sharpe_percentile_of_real": float((sharpes < real_sharpe).mean()),
        "dd_p50": float(np.percentile(dds, 50)),
        "dd_p95": float(np.percentile(dds, 95)),
    }


def evaluate(ts, o, c, targets: np.ndarray, n_placebo: int = 100) -> dict:
    """Headline metrics, subperiods, correlations, static blend and placebo."""
    w = weights(ts, targets)
    first = simulate(ts, o, c, w, bp=1.0, fill_log=True)
    stats = {}
    for bp in (1.0, 5.0, 10.0):
        res = simulate(ts, o, c, w, bp=bp)
        stats[f"{int(bp)}bp"] = metrics(res)
    events = len({row["ts"] for row in first["fills_log"]}) if "fills_log" in first else 0
    eq = daily_equity(ts, first)
    ret = eq.pct_change()
    static_res, avg = static_blend(ts, o, c, targets)
    return {
        "stats": stats,
        "events": int(events),
        "yearly": yearly(eq),
        "subperiods": subperiods(eq),
        "corr_winners": winner_corr(ret),
        "avg_weights": [float(x) for x in avg],
        "static_avg_weights": metrics(static_res),
        "placebo": placebo(ts, o, c, targets,
                           stats["1bp"]["cagr"], stats["1bp"]["sharpe"],
                           n=n_placebo),
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def cut_test(ts, o, c, build_fn, cut: str = "2020-03-12 11:07") -> dict:
    """Rebuild weights on a truncated panel and compare every prior weight."""
    full = build_fn(ts, o, c)
    i = int(ts.searchsorted(pd.Timestamp(cut, tz="America/New_York")))
    if i <= 0 or i >= len(ts):
        raise ValueError(f"cut {cut} outside the panel")
    part = build_fn(ts[: i + 1], o[: i + 1], c[: i + 1])
    diff = float(np.abs(full[: i + 1] - part).max())
    return {
        "cut": cut,
        "bars_checked": int(i + 1),
        "max_abs_weight_diff": diff,
        "pass": bool(diff <= 1e-12),
    }


def kill_checks(ev: dict, n_pass_cells: int) -> dict:
    st = ev["stats"]["1bp"]
    max_corr = max(ev["corr_winners"].values())
    return {
        "cagr_1bp_below_tqqq_bar": bool(st["cagr"] <= TQQQ_BAR_CAGR),
        "drawdown_1bp_above_tqqq": bool(st["max_drawdown"] >= TQQQ_BAR_DD),
        "cagr_10bp_below_tqqq_bar": bool(ev["stats"]["10bp"]["cagr"] <= TQQQ_BAR_CAGR),
        "plateau_below_5_of_8": bool(n_pass_cells < 5),
        "placebo_below_90th": bool(ev["placebo"]["cagr_percentile_of_real"] < 0.90),
        "winner_correlation_above_0.95": bool(max_corr > 0.95),
        "fewer_than_100_fills_and_30_events": bool(
            st["fills"] < 100 and ev["events"] < 30),
        "negative_subperiod": bool(any(v["cagr"] < 0 for v in ev["subperiods"].values())),
        "static_blend_matches": bool(
            ev["static_avg_weights"]["cagr"] >= st["cagr"] - 0.01),
    }


def write_result(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")


def summary_line(st: dict) -> str:
    return (f"CAGR {st['cagr'] * 100:.2f}%  DD {st['max_drawdown'] * 100:.1f}%  "
            f"Sharpe {st['sharpe']:.2f}  Sortino {st['sortino']:.2f}  "
            f"vol {st['volatility'] * 100:.1f}%  exposure {st['exposure'] * 100:.1f}%  "
            f"fills {st['fills']}  turnover {st['turnover']:.0f}x")
