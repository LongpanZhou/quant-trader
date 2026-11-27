"""Overnight-drift capture with a volatility / short-trend crash throttle.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (signal), TQQQ (position), cash.  One decision per session at
15:58 ET, filled at the 15:59 open; the position is then held through the
overnight block and the whole of the next session, and re-decided at the next
15:58.

    q_k      QQQ close of the 15:58 bar of session k
    sigma_k  annualised stdev of the last 10 completed QQQ daily log returns
    sma20_k  mean of q over the last 20 sessions including k
    base_k   min(1, 0.20 / sigma_k)
    trend_k  1.0 if q_k >= sma20_k else 0.5
    w_k      base_k * trend_k

There is no 165-day (or any 100-250 day) moving average, no intraday stop, no
BIL sleeve, no closing-pressure signal and no gap-continuation selection.
Idle weight is cash at 0%.

Indicator warmup uses QQQ daily closes from 2015-01-02..2015-12-31 only (the
1-minute archive begins 2016-01-04).  The panel is physically truncated at
2023-12-29; no 2024+ bar is loaded.
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
COL_Q, COL_T = 0, 1

# pre-registered centre
VOL_TARGET = 0.20
TREND_FLOOR = 0.50
VOL_WINDOW = 10
SMA_WINDOW = 20

# diagnostic only: the "bad-gap risk" channel that is reported but not used
GAP_WINDOW = 10
GAP_THRESHOLD = -0.03


# --------------------------------------------------------------------------- #
# panel / signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def _warm_daily_closes(first_session_date) -> np.ndarray:
    """QQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def _rolling_mean(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def _rolling_std_lagged(x: np.ndarray, n: int) -> np.ndarray:
    """Std of x through index k-1, aligned to index k."""
    s = pd.Series(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()
    out = np.full(len(x), np.nan)
    out[1:] = s[:-1]
    return out


def session_signals(ts, opens, closes, vol_window: int = VOL_WINDOW,
                    sma_window: int = SMA_WINDOW):
    """Causal daily signals; q is the 15:58 QQQ print known before the fill."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    q58 = np.asarray(closes, dtype=float)[np.maximum(last - 1, first), COL_Q]

    pre = _warm_daily_closes(dates[first][0])
    npre = len(pre)
    q_all = np.r_[pre, q58]
    r_all = np.full(len(q_all), np.nan)
    r_all[1:] = np.log(q_all[1:] / q_all[:-1])

    vol_all = _rolling_std_lagged(r_all, vol_window) * np.sqrt(252.0)
    sma_all = _rolling_mean(q_all, sma_window)

    gap = np.full(nd, np.nan)
    gap[1:] = np.asarray(opens)[first[1:], COL_Q] / np.asarray(closes)[last[:-1], COL_Q] - 1.0
    return {
        "dates": dates, "first": first, "last": last, "nd": nd,
        "q58": q58, "vol": vol_all[npre:], "sma": sma_all[npre:], "gap": gap,
    }


def targets_from_signals(sig: dict, vol_target: float = VOL_TARGET,
                         floor: float = TREND_FLOOR) -> np.ndarray:
    vol, sma, q = sig["vol"], sig["sma"], sig["q58"]
    base = np.minimum(1.0, vol_target / np.maximum(vol, 1e-12))
    trend = np.where(q >= sma, 1.0, floor)
    t = base * trend
    t = np.where(np.isfinite(t), t, 0.0)
    return np.clip(t, 0.0, 1.0)


def weights_from_targets(sig: dict, t: np.ndarray, night_only: bool = False,
                         day_only: bool = False) -> np.ndarray:
    """Map session decisions to per-bar targets.

    A decision made at 15:58 of session k fills at the 15:59 open and governs
    the night of k (bar l-1) and the whole of session k+1 (bar l and the
    following intraday bars).  The weight on the last bar of session k fills at
    the next 09:30 open.
    """
    first, last, nd = sig["first"], sig["last"], sig["nd"]
    n = int(last[-1]) + 1
    w = np.zeros(n)
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        prev = t[k - 1] if k > 0 else 0.0
        if night_only:
            w[f:l] = 0.0
            w[l - 1] = t[k]
            w[l] = 0.0
        elif day_only:
            w[f:l] = prev
            w[l - 1] = 0.0
            w[l] = t[k]
        else:
            w[f:max(l - 1, f)] = prev
            w[l - 1] = t[k]
            w[l] = t[k]
    w[-1] = w[-2]
    return w


def build_weights(ts, opens, closes, vol_target: float = VOL_TARGET,
                  floor: float = TREND_FLOOR, vol_window: int = VOL_WINDOW,
                  sma_window: int = SMA_WINDOW, **kw) -> np.ndarray:
    """Return the (n, 3) weight matrix: column 1 is TQQQ, the rest cash."""
    sig = session_signals(ts, opens, closes, vol_window, sma_window)
    t = targets_from_signals(sig, vol_target, floor)
    w1 = weights_from_targets(sig, t, **kw)
    w = np.zeros((len(ts), 3))
    w[:, COL_T] = w1[:len(ts)]
    assert (w >= 0).all() and (w.sum(axis=1) <= 1.0 + 1e-9).all()
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, start=DEV_START, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_1M)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(res["ts"].date).last().pct_change().dropna()


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10], "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min())}


def calendar_year_cut(ts, equity, year: int) -> dict:
    """Compound the daily returns with one calendar year removed."""
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


# --------------------------------------------------------------------------- #
# attribution
# --------------------------------------------------------------------------- #
def attribution(ts, o, c, t, years):
    """Split the P&L into the overnight and day blocks.

    night: 15:59 open -> next 09:30 open.  day: 09:30 open -> 15:59 open.
    The decision made at the close of session k owns the night of k and the
    day of k+1, so both use weight t[k].
    """
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    to = np.asarray(o)[:, COL_T]
    night = to[first[1:]] / to[last[:-1]] - 1.0
    day = to[last] / to[first] - 1.0
    n_dec = nd - 1
    night = night[:n_dec]
    day_next = day[1:n_dec + 1]
    wn = t[:n_dec]

    c_night = float(np.nansum(np.log1p(wn * night)))
    c_day = float(np.nansum(np.log1p(wn * day_next)))
    b_night = float(np.nansum(np.log1p(night)))
    b_day = float(np.nansum(np.log1p(day_next)))

    bad = wn < 0.5
    foregone = float(np.nansum(np.log1p(night[bad])))
    worst = np.argsort(night)[:10]
    w10 = worst[:10]
    worst_full = float(np.nansum(np.log1p(night[w10])))
    worst_strat = float(np.nansum(np.log1p(wn[w10] * night[w10])))
    return {
        "log_contrib_strategy_night": c_night,
        "log_contrib_strategy_day": c_day,
        "log_contrib_bh_night": b_night,
        "log_contrib_bh_day": b_day,
        "ann_strategy_night": float(np.exp(c_night / years) - 1),
        "ann_strategy_day": float(np.exp(c_day / years) - 1),
        "ann_bh_night": float(np.exp(b_night / years) - 1),
        "ann_bh_day": float(np.exp(b_day / years) - 1),
        "night_share_of_strategy_log_pnl": float(c_night / (c_night + c_day)),
        "nights_below_half_weight": int(bad.sum()),
        "log_return_foregone_on_half_weight_nights": foregone,
        "mean_foregone_bp_per_half_weight_night": float(
            (np.exp(foregone / max(int(bad.sum()), 1)) - 1) * 1e4),
        "worst10_log_full_exposure": worst_full,
        "worst10_log_at_strategy_weight": worst_strat,
        "worst_10_tqqq_nights": [
            {"date": str(dates[first][i])[:10], "tqqq_overnight": float(night[i]),
             "strategy_night_weight": float(wn[i])} for i in worst
        ],
        "mean_tqqq_overnight_bp": float(np.nanmean(night) * 1e4),
        "mean_strategy_night_bp": float(np.nanmean(wn * night) * 1e4),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    print(f"panel {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    sig = session_signals(ts, o, c)
    t = targets_from_signals(sig)
    w = build_weights(ts, o, c)

    out = {
        "strategy": "overnight-drift-filter",
        "directory": "research/new/overnight-drift-filter",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "cash at 0%"},
        "rules": {
            "vol_target": VOL_TARGET, "trend_floor": TREND_FLOOR,
            "vol_window": VOL_WINDOW, "sma_window": SMA_WINDOW,
            "signal_clock": "15:58 ET", "hold": "15:59 open -> next 15:58",
            "base": "min(1, 0.20 / sigma10_ann)",
            "trend": "1.0 if QQQ 15:58 close >= SMA20 else 0.5",
            "warmup": "QQQ daily closes 2015-01-02..2015-12-31",
        },
        "dev": {},
    }

    results = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:,}  exposure {s['exposure']*100:.1f}%")

    res1, s1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["symbol"] = "TQQQ"
    out["benchmark_tqqq"]["bar_from_brief"] = {"cagr": 0.3672, "max_drawdown": 0.8229,
                                               "sharpe": 0.82}

    out["corr_daily_tqqq"] = float(
        daily_returns(res1).corr(daily_returns({"equity": c[i0:, COL_T], "ts": ts[i0:]})))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, COL_T]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }

    # ---- pre-registered grid -------------------------------------------------
    grid = []
    for tgt in (0.15, 0.20, 0.25, 0.30):
        for fl in (0.30, 0.50):
            wt = build_weights(ts, o, c, vol_target=tgt, floor=fl)
            _, s = run_weights(ts, o, c, wt)
            grid.append({"vol_target": tgt, "trend_floor": fl, **pack(s)})
            print(f"grid {tgt:.2f}/{fl:.2f}  CAGR {s['cagr']*100:6.2f}%  "
                  f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}  "
                  f"exp {s['exposure']*100:5.1f}%")
    out["grid"] = grid

    # ---- neighbours (robustness, not used to choose the centre) --------------
    neigh = []
    for name, kw in [
        ("vol_window 5", {"vol_window": 5}),
        ("vol_window 20", {"vol_window": 20}),
        ("sma 10", {"sma_window": 10}),
        ("sma 50", {"sma_window": 50}),
        ("target 0.18", {"vol_target": 0.18}),
        ("target 0.22", {"vol_target": 0.22}),
        ("floor 0.35", {"floor": 0.35}),
        ("floor 0.65", {"floor": 0.65}),
    ]:
        wt = build_weights(ts, o, c, **kw)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": name, **pack(s)})
        print(f"neigh {name:16s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:4.2f}")
    out["neighbours"] = neigh

    # ---- components / controls ----------------------------------------------
    controls = {}
    wt = build_weights(ts, o, c, floor=1.0)
    _, s = run_weights(ts, o, c, wt)
    controls["vol_only_floor_1.0"] = pack(s)

    w_trend = np.zeros((len(ts), 3))
    tt = np.where(sig["q58"] >= sig["sma"], 1.0, TREND_FLOOR)
    tt = np.where(np.isfinite(tt), tt, 0.0)
    w_trend[:, COL_T] = weights_from_targets(sig, tt)
    _, s = run_weights(ts, o, c, w_trend)
    controls["trend_only_floor_0.5"] = pack(s)

    const = float(np.mean(t))
    w_const = np.zeros((len(ts), 3))
    w_const[:, COL_T] = const
    _, s = run_weights(ts, o, c, w_const)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": const}

    w_night = np.zeros((len(ts), 3))
    w_night[:, COL_T] = weights_from_targets(sig, np.ones(sig["nd"]), night_only=True)
    _, s = run_weights(ts, o, c, w_night)
    controls["overnight_only_unconditional"] = pack(s)

    w_night_f = np.zeros((len(ts), 3))
    w_night_f[:, COL_T] = weights_from_targets(sig, t, night_only=True)
    _, s = run_weights(ts, o, c, w_night_f)
    controls["overnight_only_throttled"] = pack(s)
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:32s} CAGR {v['cagr']*100:6.2f}%  DD {v['max_drawdown']*100:5.2f}%  "
              f"Sh {v['sharpe']:4.2f}")

    # ---- bad-gap diagnostic (tested, not used) ------------------------------
    mingap = pd.Series(sig["gap"]).rolling(GAP_WINDOW, min_periods=GAP_WINDOW).min().to_numpy()
    skip = np.where(np.isfinite(mingap), mingap < GAP_THRESHOLD, False)
    w_gap = np.zeros((len(ts), 3))
    w_gap[:, COL_T] = weights_from_targets(sig, t)
    for k in range(sig["nd"]):
        if skip[k]:
            w_gap[int(sig["last"][k]) - 1, COL_T] = 0.0
    _, s = run_weights(ts, o, c, w_gap)
    out["gap_channel"] = {"threshold": GAP_THRESHOLD, "window": GAP_WINDOW,
                          "nights_skipped": int(skip.sum()), **pack(s)}
    print(f"gap channel      {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
          f"Sh {s['sharpe']:4.2f}  skipped {int(skip.sum())}")

    # ---- attribution ---------------------------------------------------------
    out["attribution"] = attribution(ts, o, c, t, s1["years"])

    # ---- placebo: shuffle the decision series -------------------------------
    rng = np.random.default_rng(7)
    real = s1["cagr"]
    cagrs = []
    for _ in range(200):
        perm = rng.permutation(len(t))
        wt = np.zeros((len(ts), 3))
        wt[:, COL_T] = weights_from_targets(sig, t[perm])
        _, sp = run_weights(ts, o, c, wt)
        cagrs.append(sp["cagr"])
    cagrs = np.array(cagrs)
    out["placebo"] = {"n_draws": 200, "real_cagr": float(real),
                      "mean": float(cagrs.mean()), "p95": float(np.percentile(cagrs, 95)),
                      "p_value": float((cagrs >= real).mean())}
    print("placebo", {k: round(float(v), 4) for k, v in out["placebo"].items()})

    # ---- cut tests -----------------------------------------------------------
    cuts = {}
    for year in (2020, 2016, 2023, 2022):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, COL_T], year),
        }
    out["cut_tests"] = cuts
    for y, v in cuts.items():
        print(f"cut ex-{y}: strat {v['strategy']['cagr']*100:6.2f}% / "
              f"{v['strategy']['max_drawdown']*100:5.2f}%  "
              f"bench {v['benchmark_ex_year']['cagr']*100:6.2f}% / "
              f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")

    # ---- causality: truncation at 2022-01-03 --------------------------------
    j = bt.start_index(ts, "2022-01-03")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {"truncation_date": "2022-01-03",
                        "prior_weights_unchanged": bool(np.allclose(w_trunc, w[:j]))}
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
