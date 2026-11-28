"""Month-end five-session TQQQ overweight - `family-day-of-month`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  No 2024+ bar is loaded.

Primary object
--------------
The position of a session inside its calendar month.  The strategy holds a
60% TQQQ core and raises TQQQ to 100% for the last five sessions of each
month (the month-end flow window).  Idle weight is BIL.  The clock is the
day-of-month / session-in-month rank, not weekday, month-of-year, FOMC, OpEx,
trend, volatility, drawdown, opening range, close flow, ML or relative
strength.

Hypothesis
----------
Month-end is a predictable flow window: pension and mutual-fund rebalancing,
index and model-portfolio adjustments, and payroll/401(k) contributions are
concentrated in the last few sessions of the calendar month.  The flow is
predominantly into large-cap equity, so the last five sessions should carry a
higher TQQQ drift than the rest of the month.  A core TQQQ position harvests
the unconditional equity premium; the month-end overweight harvests the
seasonal flow.  The last five sessions are known from the calendar at the
prior close.

Decision clock
--------------
For session k, the target is known at the close of session k-1 (the calendar
rank of k is known in advance).  The target is written on the 15:59 bar of
k-1 and fills at the 09:30 open of k.  The harness's next-open rule is
unchanged.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/family-day-of-month/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2

# Pre-registered centre.
CORE_WEIGHT = 0.60
EVENT_WEIGHT = 1.00
EVENT_SESSIONS = 5
IDLE = "BIL"

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
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


# --------------------------------------------------------------------------- #
# calendar signal
# --------------------------------------------------------------------------- #
def month_rank(ts) -> tuple[np.ndarray, np.ndarray]:
    """Session-in-month rank (1..n) and month length for each session."""
    dates, first, _ = bt.day_bounds(ts)
    sd = pd.to_datetime(dates[first])
    df = pd.DataFrame({"d": sd})
    period = df["d"].dt.to_period("M")
    rank = df.groupby(period).cumcount().to_numpy() + 1
    nmon = df.groupby(period)["d"].transform("size").to_numpy()
    return rank, nmon


def target_from_rank(rank: np.ndarray, nmon: np.ndarray,
                     core: float = CORE_WEIGHT,
                     event: float = EVENT_WEIGHT,
                     sessions: int = EVENT_SESSIONS) -> np.ndarray:
    """Per-session TQQQ target.  Known at the prior close."""
    event_mask = rank > (nmon - sessions)
    return np.where(event_mask, event, core)


def broadcast(ts, target: np.ndarray) -> np.ndarray:
    """Map per-session targets to the (n,3) 1-minute weight matrix."""
    day_id = bt.day_ids(ts)
    _, _, last = bt.day_bounds(ts)
    w = np.zeros((len(ts), 3))
    w[:, COL_T] = target[day_id]
    w[:, COL_B] = 1.0 - target[day_id]
    w[last[:-1], COL_T] = target[1:]
    w[last[:-1], COL_B] = 1.0 - target[1:]
    assert w.min() >= -1e-12
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9)
    return w


def build_weights_params(ts, o, c, core: float = CORE_WEIGHT,
                         sessions: int = EVENT_SESSIONS) -> np.ndarray:
    rank, nmon = month_rank(ts)
    target = target_from_rank(rank, nmon, core=core, sessions=sessions)
    return broadcast(ts, target)


def build_weights(ts, opens, closes):
    """Pre-registered centre."""
    return build_weights_params(ts, opens, closes)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def run_range(ts, o, c, w, lo=DEV_START, hi=DEV_END, bp=1.0):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York")
                            + pd.Timedelta(days=1)))
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=0.02,
                       slippage_bps=bp, start_equity=bt.START_EQUITY)


def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def stats_block(ts, o, c, w, bp=1.0, lo=DEV_START, hi=DEV_END):
    res = run_range(ts, o, c, w, lo, hi, bp)
    return pack(bt.stats(res, BARS_1M)), res


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min()), "years": float(years)}


def daily_approx(target: np.ndarray, t_open: np.ndarray,
                 b_open: np.ndarray) -> float:
    """Causal daily open-to-open approximation for placebos/controls.

    target[k] is the weight for session k, known at the close of k-1.  The
    capturable return is open[k+1]/open[k]-1, so use target[:-1] against the
    return array shifted by one.
    """
    t_oo = np.r_[np.nan, t_open[1:] / t_open[:-1] - 1.0]
    b_oo = np.r_[np.nan, b_open[1:] / b_open[:-1] - 1.0]
    s = np.asarray(target, dtype=float)[:-1]
    r = np.nan_to_num(s * t_oo[1:] + (1.0 - s) * b_oo[1:])
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    return float(eq[-1] ** (1.0 / years) - 1.0)


# --------------------------------------------------------------------------- #
# correlation with the nine current winners
# --------------------------------------------------------------------------- #
def archived_dev_returns(slug: str) -> pd.Series:
    d = json.loads((HERE.parent / "curves" / f"{slug}.json").read_text())
    dates = pd.to_datetime(d["dates"])
    vals = np.asarray(d["values"], dtype=float)
    keep = dates <= pd.Timestamp(DEV_END)
    return pd.Series(vals[keep], index=dates[keep]).pct_change()


def correlation_block(eqd: pd.Series, winners) -> dict:
    r = eqd.pct_change().dropna()
    out = {"winners": {}}
    for slug in winners:
        rr = archived_dev_returns(slug)
        idx = r.index.intersection(rr.dropna().index)
        out["winners"][slug] = {"corr": float(r.loc[idx].corr(rr.loc[idx])),
                                "n": int(len(idx))}
    vals = [v["corr"] for v in out["winners"].values()]
    out["min"] = float(min(vals))
    out["max"] = float(max(vals))
    out["mean"] = float(np.mean(vals))
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=30)
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    print(f"panel {len(ts):,} bars, {nd} sessions, {ts[0].date()} .. {ts[-1].date()}")

    rank, nmon = month_rank(ts)
    target = target_from_rank(rank, nmon)
    w = broadcast(ts, target)
    event_mask = rank > (nmon - EVENT_SESSIONS)

    out = {
        "strategy": "family-day-of-month",
        "family": "day-of-month",
        "directory": "research/new/family-day-of-month",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": IDLE,
                   "holdout": "not loaded"},
        "rules": {
            "primary": "session rank inside the calendar month",
            "event_window": "last 5 sessions of each month",
            "core_tqqq": CORE_WEIGHT,
            "event_tqqq": EVENT_WEIGHT,
            "idle": "BIL 1.0",
            "decision": "target known at the prior close; fill next open",
            "bar": BAR,
        },
        "dev": {},
    }

    results = {}
    for bp in (0.0, 1.0, 5.0, 10.0):
        s, res = stats_block(ts, o, c, w, bp)
        results[bp] = (s, res)
        if bp in (1.0, 5.0, 10.0):
            out["dev"][f"{int(bp)}bp"] = s
        print(f"centre {bp:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"fills {s['fills']:,}  turnover {s['turnover']:.0f}  "
              f"exposure {s['exposure']*100:.1f}%")

    s1, res1 = results[1.0]
    eq_series = bt.daily_last(res1["equity"], res1["ts"])
    eq_series.index = pd.to_datetime(eq_series.index)

    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    print(f"bench TQQQ  CAGR {bench['cagr']*100:6.2f}%  "
          f"DD {bench['max_drawdown']*100:5.2f}%  Sharpe {bench['sharpe']:4.2f}")

    out["exposure"] = {
        "mean_tqqq_weight_session": float(np.mean(target[1:])),
        "mean_tqqq_weight_bar": float(w[:, COL_T].mean()),
        "fraction_sessions_event": float(np.mean(event_mask[1:])),
        "fraction_sessions_core": float(np.mean(~event_mask[1:])),
        "stats_exposure_incl_bil": float(s1["exposure"]),
        "signal_changes": int(np.sum(np.diff(np.r_[0.0, target]) != 0)),
    }

    bench_slice = c[i0 : i0 + len(res1["ts"]), COL_T]
    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], bench_slice).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-01", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }

    # ---- pre-registered 8-cell core-weight grid ----------------------------
    grid = []
    for core in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        wt = build_weights_params(ts, o, c, core=core)
        ss, _ = stats_block(ts, o, c, wt)
        grid.append({"core_weight": core, "event_weight": EVENT_WEIGHT,
                     "event_sessions": EVENT_SESSIONS, **ss,
                     "passes_bar": bool(ss["cagr"] > BAR["cagr"]
                                        and ss["max_drawdown"] < BAR["max_drawdown"])})
        print(f"grid core {core:.2f}  CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
              f"fills {ss['fills']:,}")
    out["grid"] = grid

    # ---- neighbours: event-window length -----------------------------------
    neigh = []
    for sessions in (3, 4, 5, 6, 7):
        wt = build_weights_params(ts, o, c, sessions=sessions)
        ss, _ = stats_block(ts, o, c, wt)
        neigh.append({"name": f"event_sessions {sessions}", **ss})
        print(f"neigh window {sessions}  CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
              f"fills {ss['fills']:,}")
    out["neighbours"] = neigh

    # ---- controls ----------------------------------------------------------
    controls = {}
    wt = np.zeros((len(ts), 3))
    wt[:, COL_T] = 1.0
    ss, _ = stats_block(ts, o, c, wt)
    controls["tqqq_buy_hold"] = ss
    print(f"control TQQQ          CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")

    mean_w = float(np.mean(target[1:]))
    wt = np.zeros((len(ts), 3))
    wt[:, COL_T] = mean_w
    wt[:, COL_B] = 1.0 - mean_w
    ss, _ = stats_block(ts, o, c, wt)
    controls["constant_exposure_same_mean"] = {**ss, "tqqq_weight": mean_w}
    print(f"control constant {mean_w:.3f}  CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")

    pure = event_mask.astype(float)
    wt = broadcast(ts, pure)
    ss, _ = stats_block(ts, o, c, wt)
    controls["pure_event_no_core"] = {**ss, "tqqq_exposure": float(np.mean(pure[1:]))}
    print(f"control pure event    CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}  "
          f"fills {ss['fills']:,}")

    # same-length wrong window: first 5 sessions of the month
    wrong = rank <= EVENT_SESSIONS
    wt = broadcast(ts, np.where(wrong, EVENT_WEIGHT, CORE_WEIGHT))
    ss, _ = stats_block(ts, o, c, wt)
    controls["first5_same_length_placebo"] = ss
    print(f"control first5        CAGR {ss['cagr']*100:6.2f}%  "
          f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")
    out["controls"] = controls

    # ---- event study -------------------------------------------------------
    t_open = o[first, COL_T]
    t_oo = np.r_[np.nan, t_open[1:] / t_open[:-1] - 1.0]
    # forward capturable return for a target on session k: open k -> open k+1
    fwd = np.r_[t_oo[1:], np.nan]
    def desc(mask):
        x = fwd[mask]
        x = x[np.isfinite(x)]
        return {"n": int(len(x)), "mean_bp": float(np.mean(x) * 1e4),
                "median_bp": float(np.median(x) * 1e4),
                "win": float(np.mean(x > 0)),
                "t": float(np.mean(x) / (np.std(x) / np.sqrt(len(x))))}
    ev = {"event_last5": desc(event_mask),
          "core_other": desc(~event_mask),
          "first5_placebo": desc(rank <= EVENT_SESSIONS)}
    ev["spread_bp"] = ev["event_last5"]["mean_bp"] - ev["core_other"]["mean_bp"]
    out["event_study"] = ev
    print("event study", ev)

    # ---- shifted-day and random-block placebos -----------------------------
    # Circular shifts of the event mask by +/-5 and +/-10 sessions preserve the
    # event count and window length but move the window away from month-end.
    shifted = {}
    for shift in (-10, -5, 5, 10):
        m2 = np.roll(event_mask, shift)
        tgt = np.where(m2, EVENT_WEIGHT, CORE_WEIGHT)
        ss, _ = stats_block(ts, o, c, broadcast(ts, tgt))
        shifted[f"shift_{shift:+d}"] = {
            "cagr": ss["cagr"], "max_drawdown": ss["max_drawdown"],
            "sharpe": ss["sharpe"], "fills": ss["fills"]}
        print(f"shift {shift:+3d}  CAGR {ss['cagr']*100:6.2f}%  "
              f"DD {ss['max_drawdown']*100:5.2f}%  Sh {ss['sharpe']:.2f}")

    rng = np.random.default_rng(20261127)
    n_event = int(event_mask.sum())
    real_daily = daily_approx(target, t_open, o[first, COL_B])
    draws = []
    for _ in range(300):
        m = np.zeros(nd, dtype=bool)
        m[rng.choice(nd, n_event, replace=False)] = True
        tgt = np.where(m, EVENT_WEIGHT, CORE_WEIGHT)
        draws.append(daily_approx(tgt, t_open, o[first, COL_B]))
    draws = np.asarray(draws)
    out["placebo"] = {
        "shifted_days": shifted,
        "random_blocks": {
            "n_draws": int(len(draws)), "marks": "1D open-to-open approximation",
            "n_events": n_event,
            "real_daily_cagr": float(real_daily),
            "real_1m_cagr_1bp": float(s1["cagr"]),
            "mean": float(draws.mean()), "p95": float(np.quantile(draws, 0.95)),
            "p99": float(np.quantile(draws, 0.99)), "max": float(draws.max()),
            "p_value": float((draws >= real_daily).mean()),
        },
    }
    print("placebo random", {k: (round(v, 4) if isinstance(v, float) else v)
                             for k, v in out["placebo"]["random_blocks"].items()})

    # ---- correlation vs nine winners ---------------------------------------
    corr = correlation_block(eq_series, WINNERS)
    out["corr_winners"] = corr["winners"]
    out["corr_summary"] = {"min": corr["min"], "max": corr["max"],
                           "mean": corr["mean"]}
    print("corr winners", {k: round(v["corr"], 3) for k, v in corr["winners"].items()})

    # ---- causality truncation ---------------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "compare_through": "2021-12-29",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:j2], w[:j2])),
    }
    print("causality", out["causality"])

    # ---- verdict / kill criteria ------------------------------------------
    passes = (s1["cagr"] > BAR["cagr"]
              and s1["max_drawdown"] < BAR["max_drawdown"])
    out["verdict"] = {
        "dev_pass_1bp": bool(passes),
        "cagr_margin_pp": float((s1["cagr"] - BAR["cagr"]) * 100),
        "dd_margin_pp": float((BAR["max_drawdown"] - s1["max_drawdown"]) * 100),
        "fills_floor": bool(s1["fills"] >= 100),
        "status": "PASS" if passes and s1["fills"] >= 100 else "FAIL",
    }
    out["kill_criteria"] = [
        "Kill if the 1 bp dev CAGR is at or below 36.72% or max DD at or above 82.29%.",
        "Kill if full-window fills are below 100.",
        "Kill if the shifted-day or random-block placebo matches the real result.",
        "Kill if the 5 bp result turns the CAGR below the bar.",
        "Kill if the sign flips in either 2016-2019 or 2022-2023.",
        "Kill if daily correlation with any current winner exceeds 0.90.",
        "Kill if the event-window neighbours 3-7 sessions are not all positive.",
    ]

    (HERE / "result.json").write_text(json.dumps(out, indent=1, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
