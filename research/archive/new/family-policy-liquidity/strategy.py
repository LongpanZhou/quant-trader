"""Policy-liquidity / short-rate regime on QQQ, TQQQ and BIL.

Development window only: 2016-01-04 .. 2023-12-29.

Mechanism
---------
BIL is a 1-3 month T-bill ETF.  Its total-return path is the short rate net of
its expense ratio, so the annualised 20- and 60-session log slopes of BIL's
adjusted close are a direct, local proxy for the policy front end.  The
strategy trades a long-only TQQQ/BIL book on a five-state short-rate machine:

    LOW        y60 < 1.0%                             -> risk-on
    HIGH       y60 >= 4.0%                            -> risk-on
    TIGHTENING 1.0% <= y60 < 4.0% and dy60 >= 0.40%   -> risk-off
    STRESS     1.0% <= y60 < 4.0% and y20-y60 >= 0.15%-> risk-off
    STABLE     1.0% <= y60 < 4.0% otherwise           -> risk-on

where y20 and y60 are annualised BIL total-return yields and dy60 is the
60-session change in y60.  The LOW state treats the zero bound as abundant
liquidity and ignores the 1-cent BIL price grid, which dominates the yield
estimate below 1%.  The HIGH state treats a restrictive but already-priced
short rate as investable; above 4% the marginal front-end spike is more likely
a T-bill supply/technical move than a new policy shock.

The decision is taken at each session's 15:59 close and filled at the next
session's 09:30 open.  No 2024+ data is loaded.  Idle capital is BIL, not cash.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-policy-liquidity/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2
BPY_1M = 252 * 390
BPY_1D = 252
BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

# Pre-registered centre.
LO = 1.00          # % annualised; below this the short rate is at the low bound
HI = 4.00          # % annualised; above this a restrictive rate is priced
FRONT_T = 0.15     # % annualised; 20d yield minus 60d yield
SLOPE_T = 0.40     # % annualised; 60d change in the 60d yield
BAND = 0.02
SLIPS = (1.0, 5.0, 10.0)


# --------------------------------------------------------------------------- #
# short-rate proxy
# --------------------------------------------------------------------------- #
def bil_features(end=None) -> pd.DataFrame:
    """Annualised BIL total-return yields and their changes, indexed by date.

    yN = (log adjclose_t - log adjclose_{t-N}) / N * 252 * 100, i.e. the
    average annualised total return over the last N sessions.  This is the
    short rate inferred from BIL, not an external Treasury series.  The
    adjusted close includes BIL's monthly distributions and the 2017-11-30
    reverse split is already reflected in Yahoo's adjusted series.

    `end` truncates the frame before any feature is computed, so a development
    run never touches a post-development row.
    """
    daily = pd.read_parquet(bt.DATA_DIR / "BIL-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").set_index("date")
    if end is not None:
        daily = daily.loc[:pd.Timestamp(end)]
    la = np.log(daily["adjclose"].astype(float))
    out = pd.DataFrame(index=daily.index)
    out["y20"] = la.diff(20) / 20.0 * 252.0 * 100.0
    out["y60"] = la.diff(60) / 60.0 * 252.0 * 100.0
    out["dy60"] = out["y60"] - out["y60"].shift(60)
    out["front"] = out["y20"] - out["y60"]
    return out


def _state(feat: pd.DataFrame, lo: float = LO, hi: float = HI,
           front_t: float = FRONT_T, slope_t: float = SLOPE_T) -> np.ndarray:
    """Boolean risk-on state from a feature frame (NaN -> risk-on)."""
    y = feat["y60"].to_numpy(dtype=float)
    dy = feat["dy60"].to_numpy(dtype=float)
    fr = feat["front"].to_numpy(dtype=float)
    mid = (y >= lo) & (y < hi)
    stress = mid & ((fr >= front_t) | (dy >= slope_t))
    on = ~stress
    # An unavailable estimate is not a signal; stay invested and let the next
    # completed session produce one.
    on = np.where(np.isfinite(y) & np.isfinite(dy) & np.isfinite(fr), on, True)
    return on.astype(bool)


def _session_arrays(ts):
    dates, first, last = bt.day_bounds(ts)
    return pd.to_datetime(dates[first]), first, last


def clock_state(on: np.ndarray, session_dates: pd.DatetimeIndex,
                clock: str = "D") -> np.ndarray:
    """Hold the state constant between weekly/monthly decision points."""
    if clock == "D":
        return on
    s = pd.Series(on.astype(float), index=session_dates)
    if clock == "W":
        last = s.groupby([s.index.isocalendar().year,
                          s.index.isocalendar().week]).tail(1).index
    elif clock == "M":
        last = s.groupby([s.index.year, s.index.month]).tail(1).index
    else:
        raise ValueError(clock)
    out = pd.Series(np.nan, index=s.index)
    out.loc[last] = s.loc[last].to_numpy()
    return out.ffill().bfill().to_numpy() > 0.5


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, lo: float = LO, hi: float = HI,
                  front_t: float = FRONT_T, slope_t: float = SLOPE_T,
                  clock: str = "D", state_override: np.ndarray | None = None,
                  return_state: bool = False):
    """Return the (n, 3) long-only weight matrix (col 1 = TQQQ, col 2 = BIL).

    The state is decided at the close of session k and executed at the open of
    session k+1.  Bars inside session k carry the state decided at the close of
    session k-1.  The first session uses the last completed pre-panel state.
    """
    o = np.asarray(opens, dtype=float)
    c = np.asarray(closes, dtype=float)
    session_dates, first, last = _session_arrays(ts)
    if state_override is None:
        feat = bil_features(session_dates[-1])
        aligned = feat.reindex(session_dates, method="ffill")
        on = _state(aligned, lo, hi, front_t, slope_t)
        prior = feat.loc[feat.index < session_dates[0]]
        prior_on = True
        if len(prior):
            prior_on = bool(_state(prior.iloc[[-1]], lo, hi, front_t, slope_t)[0])
    else:
        on = np.asarray(state_override, dtype=bool)
        if len(on) != len(first):
            raise ValueError("state_override length does not match sessions")
        prior_on = bool(on[0])
    on = clock_state(on, session_dates, clock)
    prior_on = bool(prior_on)

    w = np.zeros((len(ts), 3), dtype=float)
    nd = len(first)
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        held = prior_on if k == 0 else bool(on[k - 1])
        w[f:l, CT] = 1.0 if held else 0.0
        w[f:l, CB] = 0.0 if held else 1.0
        # Decision at this session's close, executed at the next session open.
        w[l, CT] = 1.0 if on[k] else 0.0
        w[l, CB] = 0.0 if on[k] else 1.0

    w[-1] = w[-2]
    if w.min() < -1e-12 or w.sum(axis=1).max() > 1.0 + 1e-9:
        raise AssertionError("invalid weights")
    if return_state:
        return w, on
    return w


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def _pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def _session_end_equity(ts, equity):
    dates, first, last = bt.day_bounds(ts)
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


def _trade_stats(ts, on, fill_log):
    entries = int(np.sum((~on[:-1]) & on[1:]))
    exits = int(np.sum(on[:-1] & (~on[1:])))
    runs = []
    cur, ln = bool(on[0]), 1
    for x in on[1:]:
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
        "tqqq_buys": len(t_buys), "tqqq_sells": len(t_sells),
        "avg_on_run_sessions": float(np.mean(on_runs)) if on_runs else 0.0,
        "median_on_run_sessions": float(np.median(on_runs)) if on_runs else 0.0,
        "on_sessions": int(on.sum()), "on_fraction": float(on.mean()),
        "first_tqqq_buy": str(t_buys[0]["ts"]) if t_buys else None,
        "last_tqqq_buy": str(t_buys[-1]["ts"]) if t_buys else None,
        "last_tqqq_sell": str(t_sells[-1]["ts"]) if t_sells else None,
        "final_state": "risk_on" if on[-1] else "risk_off",
    }


def main():
    # Primary: the 1-minute panel, one decision per session at 15:59.
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    w, on = build_weights(ts, o, c, return_state=True)
    runs = {}
    for slip in SLIPS:
        r = bt.simulate(ts, o, c, w, band=BAND, slippage_bps=slip, fill_log=True)
        runs[slip] = (r, bt.stats(r, BPY_1M))

    bench = bt.simulate(ts, o, c, np.tile([0.0, 1.0, 0.0], (len(ts), 1)),
                        band=BAND, slippage_bps=1.0)
    b = bt.stats(bench, BPY_1M)
    eq = _session_end_equity(ts, runs[1.0][0]["equity"])
    tqqq_close = _session_end_equity(ts, c[:, CT])

    # Daily cross-check: identical decision clock, daily bars.
    tsd, od, cd = bt.panel(SYMBOLS, DEV_START, DEV_END, "1D", warmup_days=0)
    wd, ond = build_weights(tsd, od, cd, return_state=True)
    rd = bt.simulate(tsd, od, cd, wd, band=BAND, slippage_bps=1.0)
    sd = bt.stats(rd, BPY_1D)

    out = {
        "strategy": "policy-liquidity-short-rate",
        "directory": "research/new/family-policy-liquidity",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1min",
                   "fills": "next session 09:30 open, 2% band", "idle": "BIL"},
        "rules": {
            "y20": "annualised 20-session BIL total-return slope",
            "y60": "annualised 60-session BIL total-return slope",
            "dy60": "y60 - y60.shift(60)",
            "front": "y20 - y60",
            "low": f"y60 < {LO:.2f}% -> risk-on",
            "high": f"y60 >= {HI:.2f}% -> risk-on",
            "tightening": f"{LO:.2f}% <= y60 < {HI:.2f}% and dy60 >= {SLOPE_T:.2f}% -> risk-off",
            "stress": f"{LO:.2f}% <= y60 < {HI:.2f}% and front >= {FRONT_T:.2f}% -> risk-off",
            "stable": "otherwise -> risk-on",
            "decision": "15:59 close, executed at next session 09:30 open",
            "no": "moving-average trend, volatility target, drawdown event, calendar window, opening range, ML, relative strength",
        },
        "dev": {f"{int(slip)}bp": _pack(runs[slip][1]) for slip in SLIPS},
        "benchmark_tqqq": _pack(b),
        "exposure_tqqq": float(w[:, CT].mean()),
        "exposure_bil": float(w[:, CB].mean()),
        "trade_stats": _trade_stats(ts, on, runs[1.0][0]["fills_log"]),
        "subperiods": {
            "2016_2019": _subperiod(eq, "2016-01-04", "2019-12-31"),
            "2020_2021": _subperiod(eq, "2020-01-01", "2021-12-31"),
            "2022_2023": _subperiod(eq, "2022-01-01", "2023-12-29"),
        },
        "yearly": {
            int(y): {"strategy": float(eq.loc[str(y)].iloc[-1] / eq.loc[str(y)].iloc[0] - 1.0),
                     "benchmark": float(tqqq_close.loc[str(y)].iloc[-1] / tqqq_close.loc[str(y)].iloc[0] - 1.0)}
            for y in sorted(set(eq.index.year))
        },
        "state_counts": {"risk_on_sessions": int(on.sum()),
                         "risk_off_sessions": int((~on).sum())},
        "daily_crosscheck": {"1bp": _pack(sd)},
        "bar": BAR,
        "passed_dev_bar": bool(
            runs[1.0][1]["cagr"] > BAR["cagr"]
            and runs[1.0][1]["max_drawdown"] < BAR["max_drawdown"]
            and runs[1.0][1]["sharpe"] > BAR["sharpe"]
            and runs[1.0][1]["fills"] >= 100),
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("dev", "benchmark_tqqq", "exposure_tqqq",
                                          "trade_stats", "subperiods", "yearly",
                                          "daily_crosscheck", "passed_dev_bar")},
                     indent=2))


if __name__ == "__main__":
    main()
