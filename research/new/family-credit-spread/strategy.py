"""Credit-risk-appetite regime on QQQ, TQQQ and BIL.

Development window only: 2016-01-04 .. 2023-12-29.

Mechanism
---------
The HYG/IEF total-return ratio is the price of high-yield credit relative to
duration.  A rising ratio means credit investors are accepting default risk in
exchange for spread; a falling ratio means the marginal credit buyer is
de-risking.  The strategy trades a long-only TQQQ/BIL book on a hysteresis
machine:

    risk-on   if cr20 >= +0.005
    risk-off  if cr20 <= -0.010
    hold      otherwise

where cr20 is the 20-session log change of HYG/IEF (both adjusted closes).
The 0.5%-1.0% band is the deadband.

The decision is taken from the session's official external close, written at
that session's 15:59 bar and filled at the next session's 09:30 open.  No
2024+ row is loaded.  Idle capital is BIL, not cash.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "4"
    python research/new/family-credit-spread/strategy.py
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
import external  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2
BPY_1M = 252 * 390
BPY_1D = 252
BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

# Pre-registered centre.
ON = 0.005
OFF = -0.010
WIN = 20
BAND = 0.02
SLIPS = (1.0, 5.0, 10.0)

WINNERS = (
    "ratio-froth",
    "vol-scaled-crash-stop",
    "relative-value-tqqq",
    "fomc-opex-window",
    "family-session-timing",
    "family-short-reversal",
    "family-rebalance-flow",
    "family-intraday-microstructure-day",
    "family-ml-microstructure",
)


# --------------------------------------------------------------------------- #
# credit features
# --------------------------------------------------------------------------- #
def credit_features(end: str | None = None) -> pd.DataFrame:
    """HYG/IEF log ratio and its changes, indexed by external date.

    `end` truncates both series before any feature is computed, so a
    development run never touches a post-development row.
    """
    hyg = external.load("HYG")
    ief = external.load("IEF")
    if end is not None:
        hyg = hyg.loc[:pd.Timestamp(end)]
        ief = ief.loc[:pd.Timestamp(end)]
    cr = np.log(hyg / ief).dropna()
    out = pd.DataFrame(index=cr.index)
    out["cr"] = cr
    out["cr20"] = cr.diff(20)
    out["cr60"] = cr.diff(60)
    out["cr120"] = cr.diff(120)
    return out


def _machine(x: pd.Series, on: float = ON, off: float = OFF,
             state0: int = 1) -> np.ndarray:
    v = x.to_numpy(dtype=float)
    out = np.empty(len(v), dtype=np.int8)
    s = int(state0)
    for i in range(len(v)):
        if np.isfinite(v[i]):
            if v[i] >= on:
                s = 1
            elif v[i] <= off:
                s = 0
        out[i] = s
    return out.astype(bool)


def state_series(session_dates: pd.DatetimeIndex, on: float = ON,
                 off: float = OFF, win: int = WIN, end: str | None = None,
                 feature_override: pd.Series | None = None,
                 return_prior: bool = False):
    if feature_override is None:
        end = end or str(pd.Timestamp(session_dates[-1]).date())
        feat = credit_features(end)
        x = feat["cr"].diff(win)
    else:
        x = feature_override.diff(win)
    raw = _machine(x, on, off)
    s = pd.Series(raw, index=x.index)
    state = s.reindex(session_dates, method="ffill").to_numpy(dtype=bool)
    prior = s.loc[s.index < session_dates[0]]
    prior_on = bool(prior.iloc[-1]) if len(prior) else True
    if return_prior:
        return state, prior_on
    return state


def build_weights(ts, opens, closes, on: float = ON, off: float = OFF,
                  win: int = WIN, state_override: np.ndarray | None = None,
                  return_state: bool = False):
    """Return the (n, 3) long-only weight matrix (col 1 TQQQ, col 2 BIL)."""
    w = np.zeros((len(ts), 3), dtype=float)
    dates, first, last = bt.day_bounds(ts)
    session_dates = pd.DatetimeIndex(dates[first])
    if state_override is not None:
        state = np.asarray(state_override, dtype=bool)
        if len(state) != len(first):
            raise ValueError("state_override length does not match sessions")
        prior_on = bool(state[0])
    else:
        state, prior_on = state_series(session_dates, on, off, win,
                                       return_prior=True)

    nd = len(first)
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        held = prior_on if k == 0 else bool(state[k - 1])
        w[f:l, CT] = 1.0 if held else 0.0
        w[f:l, CB] = 0.0 if held else 1.0
        w[l, CT] = 1.0 if state[k] else 0.0
        w[l, CB] = 0.0 if state[k] else 1.0

    w[-1] = w[-2]
    if w.min() < -1e-12 or w.sum(axis=1).max() > 1.0 + 1e-9:
        raise AssertionError("invalid weights")
    if return_state:
        return w, state
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def _pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def _session_end_equity(ts, equity):
    dates, _, last = bt.day_bounds(ts)
    return pd.Series(equity[last], index=pd.to_datetime(dates[last]))


def _subperiod(eq: pd.Series, start, end):
    x = eq.loc[start:end]
    if len(x) < 2:
        return None
    years = (x.index[-1] - x.index[0]).total_seconds() / (365.25 * 86400)
    rets = x.pct_change().dropna().to_numpy()
    peak = np.maximum.accumulate(x.to_numpy())
    return {
        "start": str(x.index[0].date()), "end": str(x.index[-1].date()),
        "cagr": float((x.iloc[-1] / x.iloc[0]) ** (1.0 / years) - 1.0),
        "max_drawdown": float(-(x.to_numpy() / peak - 1.0).min()),
        "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(BPY_1D))
        if np.std(rets) > 0 else 0.0,
        "total_return": float(x.iloc[-1] / x.iloc[0] - 1.0),
    }


def _trade_stats(state, fill_log):
    entries = int(np.sum((~state[:-1]) & state[1:]))
    exits = int(np.sum(state[:-1] & (~state[1:])))
    runs, cur, ln = [], bool(state[0]), 1
    for x in state[1:]:
        if bool(x) == cur:
            ln += 1
        else:
            runs.append((cur, ln))
            cur, ln = bool(x), 1
    runs.append((cur, ln))
    on_runs = [ln for flag, ln in runs if flag]
    t_buys = [f for f in fill_log if f["symbol"] == CT and f["side"] == "buy"]
    t_sells = [f for f in fill_log if f["symbol"] == CT and f["side"] == "sell"]
    return {
        "entries_state": entries, "exits_state": exits,
        "state_changes": entries + exits,
        "tqqq_buys": len(t_buys), "tqqq_sells": len(t_sells),
        "avg_on_run_sessions": float(np.mean(on_runs)) if on_runs else 0.0,
        "median_on_run_sessions": float(np.median(on_runs)) if on_runs else 0.0,
        "on_sessions": int(state.sum()), "on_fraction": float(state.mean()),
        "first_tqqq_buy": str(t_buys[0]["ts"]) if t_buys else None,
        "last_tqqq_buy": str(t_buys[-1]["ts"]) if t_buys else None,
        "last_tqqq_sell": str(t_sells[-1]["ts"]) if t_sells else None,
        "final_state": "risk_on" if state[-1] else "risk_off",
    }


def _daily_sim(tsd, od, cd, state):
    tgt = np.column_stack([np.zeros(len(state)), state.astype(float),
                           1.0 - state.astype(float)])
    w = external.daily_targets_to_weights(tsd, tgt)
    r = bt.simulate(tsd, od, cd, w, band=BAND, slippage_bps=1.0)
    return bt.stats(r, BPY_1D)


def _forward_state_test(tsd, od, cd, state):
    """Average next-session open-to-close TQQQ return by state, plus t-stat."""
    dates, first, last = bt.day_bounds(tsd)
    n = len(first)
    ret = np.full(n, np.nan)
    for k in range(n - 1):
        ret[k] = cd[first[k + 1], CT] / od[first[k + 1], CT] - 1.0
    on = np.asarray(state, dtype=bool)
    good = np.isfinite(ret)
    a, b = ret[good & on], ret[good & ~on]
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    t = (a.mean() - b.mean()) / se if se > 0 else 0.0
    return {
        "risk_on_mean": float(a.mean()), "risk_off_mean": float(b.mean()),
        "difference": float(a.mean() - b.mean()),
        "t_stat": float(t), "risk_on_days": int(len(a)),
        "risk_off_days": int(len(b)),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    w, state = build_weights(ts, o, c, return_state=True)

    runs = {}
    for slip in SLIPS:
        r = bt.simulate(ts, o, c, w, band=BAND, slippage_bps=slip, fill_log=True)
        runs[slip] = (r, bt.stats(r, BPY_1M))

    bench = bt.simulate(ts, o, c, np.tile([0.0, 1.0, 0.0], (len(ts), 1)),
                        band=BAND, slippage_bps=1.0)
    b = bt.stats(bench, BPY_1M)
    qbench = bt.simulate(ts, o, c, np.tile([1.0, 0.0, 0.0], (len(ts), 1)),
                         band=BAND, slippage_bps=1.0)
    qb = bt.stats(qbench, BPY_1M)

    eq = _session_end_equity(ts, runs[1.0][0]["equity"])
    tqqq_close = _session_end_equity(ts, c[:, CT])
    qqq_close = _session_end_equity(ts, c[:, CQ])

    # Daily cross-check and the directional sign test.
    tsd, od, cd = bt.panel(SYMBOLS, DEV_START, DEV_END, "1D", warmup_days=0)
    wd, stated = build_weights(tsd, od, cd, return_state=True)
    rd = bt.simulate(tsd, od, cd, wd, band=BAND, slippage_bps=1.0)
    sd = bt.stats(rd, BPY_1D)
    obs_daily_cagr = sd["cagr"]
    fwd = _forward_state_test(tsd, od, cd, stated)

    # 8-cell plateau: 3 x 3 around the centre, eight neighbours.
    grid = []
    for on in (0.000, 0.005, 0.010):
        for off in (-0.015, -0.010, -0.005):
            if (on, off) == (ON, OFF):
                continue
            grid.append((on, off))
    cell_W = [build_weights(ts, o, c, on=a, off=bb) for a, bb in grid]
    cell_res = bt.simulate_many(ts, o, c, cell_W, band=BAND,
                                slippage_bps=1.0, threads=4)
    plateau = {}
    for (on, off), rr in zip(grid, cell_res):
        s = bt.stats(rr, BPY_1M)
        plateau[f"on={on:+.3f},off={off:+.3f}"] = {
            "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]), "fills": int(s["fills"]),
            "clears_bar": bool(s["cagr"] > BAR["cagr"]
                               and s["max_drawdown"] < BAR["max_drawdown"]
                               and s["sharpe"] > BAR["sharpe"]),
        }
    centre_stats = runs[1.0][1]
    plateau["centre"] = {
        "cagr": float(centre_stats["cagr"]),
        "max_drawdown": float(centre_stats["max_drawdown"]),
        "sharpe": float(centre_stats["sharpe"]),
        "fills": int(centre_stats["fills"]),
        "clears_bar": bool(centre_stats["cagr"] > BAR["cagr"]
                           and centre_stats["max_drawdown"] < BAR["max_drawdown"]
                           and centre_stats["sharpe"] > BAR["sharpe"]),
    }

    # 60-session ablation.
    w60 = build_weights(ts, o, c, win=60)
    r60 = bt.simulate(ts, o, c, w60, band=BAND, slippage_bps=1.0)
    abl60 = bt.stats(r60, BPY_1M)

    # Circular-shift placebo on the daily panel.
    dates_d, first_d, _ = bt.day_bounds(tsd)
    session_dates_d = pd.DatetimeIndex(dates_d[first_d])
    feat = credit_features(DEV_END)
    cr = feat["cr"].reindex(session_dates_d, method="ffill")
    base = cr.to_numpy(dtype=float)
    rng = np.random.default_rng(20261127)
    n_shift = 500
    shifts = rng.integers(30, len(base) - 30, n_shift)
    placebo = []
    for sh in shifts:
        shifted = pd.Series(np.roll(base, int(sh)), index=session_dates_d)
        state_p = state_series(session_dates_d, feature_override=shifted)
        placebo.append(float(_daily_sim(tsd, od, cd, state_p)["cagr"]))
    placebo = np.array(placebo)
    p_val = float((1 + np.sum(placebo >= obs_daily_cagr)) / (1 + n_shift))

    # Second placebo: circular shift of the state path (matched exposure, run
    # lengths and trade count).
    state_shifts = rng.integers(30, len(stated) - 30, n_shift)
    placebo_state = []
    for sh in state_shifts:
        s = np.roll(stated, int(sh))
        placebo_state.append(float(_daily_sim(tsd, od, cd, s)["cagr"]))
    placebo_state = np.array(placebo_state)
    p_state = float((1 + np.sum(placebo_state >= obs_daily_cagr)) / (1 + n_shift))

    # Correlation with the nine existing winners.
    strat_ret = eq.pct_change().dropna()
    corrs = {}
    for slug in WINNERS:
        p = ROOT / "research" / "new" / "curves" / f"{slug}.json"
        if not p.exists():
            corrs[slug] = None
            continue
        d = json.loads(p.read_text())
        x = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        x = x.loc[DEV_START:DEV_END].pct_change().dropna()
        j = strat_ret.index.intersection(x.index)
        corrs[slug] = float(strat_ret.loc[j].corr(x.loc[j]))
    cvals = [v for v in corrs.values() if v is not None]

    subs = {
        "2016_2019": _subperiod(eq, "2016-01-04", "2019-12-31"),
        "2020_2021": _subperiod(eq, "2020-01-01", "2021-12-31"),
        "2022_2023": _subperiod(eq, "2022-01-01", "2023-12-29"),
    }
    yearly = {}
    for y in sorted(set(eq.index.year)):
        s = eq.loc[str(y)]
        t = tqqq_close.loc[str(y)]
        q = qqq_close.loc[str(y)]
        yearly[int(y)] = {
            "strategy": float(s.iloc[-1] / s.iloc[0] - 1.0),
            "tqqq": float(t.iloc[-1] / t.iloc[0] - 1.0),
            "qqq": float(q.iloc[-1] / q.iloc[0] - 1.0),
        }

    out = {
        "strategy": "credit-spread-hyg-ief-momentum",
        "directory": "research/new/family-credit-spread",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1min",
                   "fills": "next session 09:30 open, 2% band", "idle": "BIL"},
        "rules": {
            "cr": "ln(HYG adjclose / IEF adjclose)",
            "cr20": "cr - cr.shift(20)",
            "risk_on": f"cr20 >= {ON:+.3f}",
            "risk_off": f"cr20 <= {OFF:+.3f}",
            "deadband": f"{OFF:+.3f} .. {ON:+.3f}",
            "decision": "official external close; written at 15:59, filled next 09:30 open",
            "no": "price trend, realised-vol target, drawdown event, calendar window, opening range, ML, relative strength",
        },
        "dev": {f"{int(slip)}bp": _pack(runs[slip][1]) for slip in SLIPS},
        "benchmark_tqqq": _pack(b),
        "benchmark_qqq": _pack(qb),
        "exposure_tqqq": float(w[:, CT].mean()),
        "exposure_bil": float(w[:, CB].mean()),
        "trade_stats": _trade_stats(state, runs[1.0][0]["fills_log"]),
        "subperiods": subs,
        "yearly": yearly,
        "plateau": plateau,
        "plateau_clears_bar": int(sum(v["clears_bar"] for v in plateau.values())),
        "ablation_60d": {
            "cagr": float(abl60["cagr"]), "max_drawdown": float(abl60["max_drawdown"]),
            "sharpe": float(abl60["sharpe"]), "fills": int(abl60["fills"]),
        },
        "directional_test": fwd,
        "placebo": {
            "method": "circular shift of the HYG/IEF ratio, 500 draws, daily panel",
            "observed_daily_cagr": float(obs_daily_cagr),
            "p_value_cagr": p_val,
            "placebo_cagr_p05": float(np.percentile(placebo, 5)),
            "placebo_cagr_p50": float(np.percentile(placebo, 50)),
            "placebo_cagr_p95": float(np.percentile(placebo, 95)),
            "state_shift_p_value_cagr": p_state,
            "state_shift_p05": float(np.percentile(placebo_state, 5)),
            "state_shift_p50": float(np.percentile(placebo_state, 50)),
            "state_shift_p95": float(np.percentile(placebo_state, 95)),
        },
        "correlations": corrs,
        "correlation_min": float(min(cvals)), "correlation_max": float(max(cvals)),
        "daily_crosscheck": {"1bp": _pack(sd)},
        "bar": BAR,
        "kill_criteria": {
            "cagr_above_bar": bool(runs[1.0][1]["cagr"] > BAR["cagr"]),
            "sharpe_above_bar": bool(runs[1.0][1]["sharpe"] > BAR["sharpe"]),
            "dd_below_bar": bool(runs[1.0][1]["max_drawdown"] < BAR["max_drawdown"]),
            "activity_floor": bool(runs[1.0][1]["fills"] >= 100
                                   or _trade_stats(state, runs[1.0][0]["fills_log"])["state_changes"] >= 30),
            "plateau_at_least_6": bool(sum(v["clears_bar"] for v in plateau.values()) >= 6),
            "placebo_p_below_010": bool(p_val < 0.10),
            "direction_positive": bool(fwd["difference"] > 0 and fwd["t_stat"] > 0),
            "max_corr_below_085": bool(max(cvals) < 0.85),
            "cost_10bp_above_bar": bool(runs[10.0][1]["cagr"] > BAR["cagr"]),
        },
    }
    out["kill_criteria"]["all_pass"] = all(out["kill_criteria"].values())
    (HERE / "result.json").write_text(json.dumps(out, indent=2) + "\n")

    print(json.dumps({
        "dev": out["dev"], "benchmark_tqqq": out["benchmark_tqqq"],
        "exposure_tqqq": out["exposure_tqqq"],
        "trade_stats": out["trade_stats"], "subperiods": out["subperiods"],
        "yearly": out["yearly"], "plateau": out["plateau"],
        "directional_test": out["directional_test"],
        "placebo": out["placebo"], "correlations": out["correlations"],
        "daily_crosscheck": out["daily_crosscheck"],
        "kill_criteria": out["kill_criteria"],
    }, indent=2))


if __name__ == "__main__":
    main()
