"""Leveraged-ETF rebalance flow: QQQ closing-window de-risk on TQQQ.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Mechanism
---------
A 3x daily ETF must hold 3x its NAV in index exposure. After an index move r
the required exposure changes by 9 * NAV * r, so the fund is a forced buyer at
the close after up days and a forced seller after down days. The trade is
concentrated in the closing auction. The price pressure is temporary, so the
next session reverses. The strategy de-risks TQQQ for the session after a
flow-confirmed up day: QQQ close-to-close > 1.25% and the last 30 minutes also
up. The rest of the time it holds a 50%-vol-target TQQQ position. Idle is BIL.

Rules
-----
For session k, with q_cc = QQQ close(k)/close(k-1)-1, q_l30 = QQQ
close(k)/price_at_15:30(k)-1, and sigma = annualised stdev of the last 20
completed TQQQ daily log returns through close(k):

    flow(k) = q_cc(k) > 0.0125 and q_l30(k) > 0
    w_tqqq(k+1) = 0                              if flow(k)
                = min(1, 0.50 / sigma(k))       otherwise

The decision is set at the 16:00 close (15:59 bar) and filled at the next
open. The harness's next-open rule is used unchanged. The 2015 TQQQ daily
closes warm the 20-day vol only; no 2024+ bar is loaded.

The delivered centre is (flow_thr=1.25%, l30_confirm=0, vol_target=50%,
vol_window=20). The 8-cell pre-registered grid is in HYPOTHESIS.md.
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

# pre-registered centre
FLOW_THR = 0.0125
L30_CONFIRM = 0.0
VOL_TARGET = 0.50
VOL_WINDOW = 20

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}


# --------------------------------------------------------------------------- #
# signals and weights
# --------------------------------------------------------------------------- #
def _warm_tqqq_closes(first_session_date) -> np.ndarray:
    """TQQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "TQQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def _sigma_for_sessions(daily_closes: np.ndarray, warm: np.ndarray,
                        window: int) -> np.ndarray:
    """Annualised stdev of the last `window` returns through session k-1.

    Returned array is indexed by session k: it is known at the close of k-1
    (or at the last 2015 close for k = 0). No look-ahead.
    """
    allc = np.r_[warm, daily_closes]
    r = np.zeros(len(allc))
    r[1:] = np.log(allc[1:] / allc[:-1])
    vol = pd.Series(r).rolling(window, min_periods=window).std(ddof=0).to_numpy()
    return vol[len(warm) - 1: len(warm) - 1 + len(daily_closes)] * np.sqrt(252.0)


def build_weights_params(ts, o, c, flow_thr: float = FLOW_THR,
                         l30_confirm: float = L30_CONFIRM,
                         vol_target=VOL_TARGET,
                         vol_window: int = VOL_WINDOW) -> np.ndarray:
    """Return the (n, 3) weight matrix for 1-minute bars (col 1 = TQQQ)."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    nbar = last - first + 1
    i1530 = first + np.maximum(nbar - 31, 0)

    q_close = np.asarray(c)[last, COL_Q]
    q_1530 = np.asarray(c)[i1530, COL_Q]
    q_cc = np.r_[np.nan, q_close[1:] / q_close[:-1] - 1.0]
    q_cc[0] = 0.0
    q_l30 = q_close / q_1530 - 1.0

    t_close = np.asarray(c)[last, COL_T]
    warm = _warm_tqqq_closes(dates[first][0])
    sigma = _sigma_for_sessions(t_close, warm, vol_window)

    flow = np.zeros(nd, dtype=bool)
    flow[1:] = (q_cc[:-1] > flow_thr) & (q_l30[:-1] > l30_confirm)

    if vol_target is None:
        scale = np.ones(nd)
    else:
        scale = np.minimum(1.0, vol_target / np.maximum(sigma, 1e-12))
        scale = np.where(np.isfinite(scale), scale, 0.0)
    frac = np.where(flow, 0.0, scale)
    frac = np.clip(frac, 0.0, 1.0)

    w = np.zeros((len(ts), 3))
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        w[f:l, COL_T] = frac[k]
        w[f:l, COL_B] = 1.0 - frac[k]
        nxt = frac[k + 1] if k + 1 < nd else 0.0
        w[l, COL_T] = nxt
        w[l, COL_B] = 1.0 - nxt

    assert w.min() >= -1e-12, "negative weight"
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9), "weights sum > 1"
    return w


def build_weights(ts, o, c) -> np.ndarray:
    """Pre-registered centre."""
    return build_weights_params(ts, o, c)


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, slip: float = 1.0, start: str = DEV_START):
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    d = s.groupby(res["ts"].date).last()
    d.index = pd.to_datetime(d.index)
    return d.pct_change().dropna()


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
            "max_drawdown": float(-(x / peak - 1).min()), "years": float(years)}


def _compound(r: np.ndarray):
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    return _compound(r.to_numpy())


def drop_month(ts, equity, year: int, month: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    keep = np.array([not (x.year == year and x.month == month) for x in r.index])
    return _compound(r[keep].to_numpy())


def monthly_stats(ts, equity, bench_close):
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    d.index = pd.to_datetime(d.index)
    r = d.pct_change().dropna()
    b = pd.Series(bench_close, index=pd.to_datetime(ts))
    bd = b.groupby(b.index.date).last()
    bd.index = pd.to_datetime(bd.index)
    br = bd.pct_change().dropna()
    ms = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    mb = (1 + br).groupby([br.index.year, br.index.month]).prod() - 1
    al = pd.concat([ms, mb], axis=1, keys=["s", "b"]).dropna()
    diff = al["s"] - al["b"]
    rn, bn = r.to_numpy(), br.to_numpy()
    top = np.argsort(rn)[-10:]
    return {
        "n_months": int(len(diff)),
        "mean_excess": float(diff.mean()),
        "median_excess": float(diff.median()),
        "t_excess": float(diff.mean() / diff.std(ddof=1) * np.sqrt(len(diff))),
        "win_rate": float((diff > 0).mean()),
        "mean_daily_bp": float(rn.mean() * 1e4),
        "bench_mean_daily_bp": float(bn.mean() * 1e4),
        "total_log": float(np.log1p(rn).sum()),
        "bench_total_log": float(np.log1p(bn).sum()),
        "top10_log": float(np.log1p(rn[top]).sum()),
        "top10_share_of_total": float(np.log1p(rn[top]).sum() / np.log1p(rn).sum()),
        "top10_bench_same_dates_log": float(np.log1p(bn[top]).sum()),
        "best_months": [
            {"month": f"{y}-{m:02d}", "strategy": float(v), "benchmark": float(mb[(y, m)])}
            for (y, m), v in ms.sort_values().tail(5).items()
        ],
        "worst_months": [
            {"month": f"{y}-{m:02d}", "strategy": float(v), "benchmark": float(mb[(y, m)])}
            for (y, m), v in ms.sort_values().head(5).items()
        ],
    }


def daily_frame(ts, o, c):
    """Session-level frame with the signal inputs and next-session returns."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    nbar = last - first + 1
    i1530 = first + np.maximum(nbar - 31, 0)
    q_close = c[last, COL_Q]
    q_1530 = c[i1530, COL_Q]
    t_open = o[first, COL_T]
    t_close = c[last, COL_T]
    b_open = o[first, COL_B]
    b_close = c[last, COL_B]
    q_cc = np.r_[np.nan, q_close[1:] / q_close[:-1] - 1.0]
    q_cc[0] = 0.0
    q_l30 = q_close / q_1530 - 1.0
    t_oo = np.r_[t_open[1:] / t_open[:-1] - 1.0, np.nan]
    b_oo = np.r_[b_open[1:] / b_open[:-1] - 1.0, np.nan]
    q_oo = np.r_[o[first, COL_Q][1:] / o[first, COL_Q][:-1] - 1.0, np.nan]
    return {"dates": dates, "first": first, "last": last, "nd": nd,
            "q_cc": q_cc, "q_l30": q_l30, "t_oo": t_oo, "b_oo": b_oo,
            "q_oo": q_oo, "t_close": t_close, "t_open": t_open}


def daily_cagr(frac: np.ndarray, frame: dict) -> float:
    """Daily open-to-open approximation of the strategy (for the placebo)."""
    r = np.where(np.arange(len(frac)) < len(frac) - 1,
                 frac * np.nan_to_num(frame["t_oo"])
                 + (1.0 - frac) * np.nan_to_num(frame["b_oo"]), 0.0)
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    return float(eq[-1] ** (1 / years) - 1)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=5)
    dates, first, last = bt.day_bounds(ts)
    frame = daily_frame(ts, o, c)
    nd = len(first)
    print(f"panel {len(ts):,} bars, {nd} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    warm = _warm_tqqq_closes(dates[first][0])
    dclose = c[last, COL_T]
    print(f"warmup last {warm[-1]:.4f} -> first panel close {dclose[0]:.4f} "
          f"({dclose[0]/warm[-1]-1:+.2%})")

    w = build_weights(ts, o, c)
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)

    out = {
        "strategy": "family-rebalance-flow",
        "directory": "research/strategies/family-rebalance-flow",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "rules": {
            "signal": "QQQ close-to-close and last-30-minute return",
            "decision": "16:00 close (15:59 bar), fill next open",
            "flow_thr": FLOW_THR,
            "l30_confirm": L30_CONFIRM,
            "vol_target": VOL_TARGET,
            "vol_window": VOL_WINDOW,
            "vol_input": "TQQQ daily log returns, known at the close",
            "warmup": "TQQQ daily closes 2015-01-02..2015-12-31",
            "bar": BAR,
        },
        "dev": {},
    }

    results = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"fills {s['fills']:,}  turnover {s['turnover']:.0f}  "
              f"exposure {s['exposure']*100:.1f}%")

    res1, s1 = results[1.0]
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["symbol"] = "TQQQ"
    out["benchmark_tqqq"]["bar_from_brief"] = BAR
    print(f"bench  CAGR {bench['cagr']*100:6.2f}%  DD {bench['max_drawdown']*100:5.2f}%  "
          f"Sharpe {bench['sharpe']:4.2f}")

    # exposure / correlation: bt.stats counts BIL as invested, so report the
    # TQQQ weight separately
    wbar = w[:, COL_T]
    wsess = w[first, COL_T]
    flow = wsess < 1e-9
    out["exposure"] = {
        "mean_tqqq_weight_bar": float(wbar.mean()),
        "mean_tqqq_weight_session": float(wsess.mean()),
        "fraction_sessions_out": float(flow.mean()),
        "fraction_sessions_full": float((wsess > 0.99).mean()),
        "mean_bil_weight": float(1.0 - wbar.mean()),
        "stats_exposure_incl_bil": float(s1["exposure"]),
    }
    dr = daily_returns(res1)
    dr_bench = daily_returns({"equity": c[i0:, COL_T], "ts": ts[i0:]})
    out["corr_daily_tqqq"] = float(dr.corr(dr_bench))
    print("exposure", {k: round(v, 3) for k, v in out["exposure"].items()},
          "corr", round(out["corr_daily_tqqq"], 3))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, COL_T]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2023": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2023-12-29"),
    }
    out["monthly"] = monthly_stats(res1["ts"], res1["equity"], c[i0:, COL_T])
    print("monthly excess mean %.2f%% median %.2f%% t %.2f win %.1f%%" % (
        out["monthly"]["mean_excess"] * 100, out["monthly"]["median_excess"] * 100,
        out["monthly"]["t_excess"], out["monthly"]["win_rate"] * 100))

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (0.45, 0.0125, 0.0, "vol neighbour"),
        (0.50, 0.0100, 0.0, "threshold neighbour"),
        (0.50, 0.0125, 0.0, "centre"),
        (0.50, 0.0150, 0.0, "threshold neighbour"),
        (0.55, 0.0125, 0.0, "vol neighbour"),
        (0.60, 0.0125, 0.0, "vol neighbour"),
        (0.50, 0.0125, 0.001, "confirmation neighbour"),
        (0.50, 0.0125, 0.002, "confirmation neighbour"),
    ]
    grid = []
    for vt, thr, l30, role in grid_spec:
        wt = build_weights_params(ts, o, c, flow_thr=thr, l30_confirm=l30,
                                  vol_target=vt)
        _, s = run_weights(ts, o, c, wt)
        grid.append({"vol_target": vt, "flow_thr": thr, "l30_confirm": l30,
                     "role": role, **pack(s)})
        print(f"grid vt={vt:.2f} thr={thr*100:.2f}% l30>{l30*100:+.1f}% "
              f"{role:22s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:.2f}")
    out["grid"] = grid

    # ---- neighbours: vol-target and threshold ladders ----------------------
    neigh = []
    for vt in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.85, 1.00):
        wt = build_weights_params(ts, o, c, vol_target=vt)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": f"vol_target {vt:.2f}", **pack(s)})
        print(f"neigh vol {vt:.2f}   CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    for thr in (0.0075, 0.0100, 0.0125, 0.0150, 0.0200, 0.0250):
        wt = build_weights_params(ts, o, c, flow_thr=thr)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": f"flow_thr {thr:.4f}", **pack(s)})
        print(f"neigh thr {thr*100:.2f}%  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    for l30 in (-0.002, -0.001, 0.0, 0.001, 0.002):
        wt = build_weights_params(ts, o, c, l30_confirm=l30)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": f"l30_confirm {l30:+.4f}", **pack(s)})
        print(f"neigh l30 {l30*100:+.2f}% CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    out["neighbours"] = neigh

    # ---- placebo: random de-risk dates, same count -------------------------
    frac_centre = w[first, COL_T].copy()
    n_flow = int((frac_centre < 1e-9).sum())
    real_daily_cagr = daily_cagr(frac_centre, frame)
    sigma_sessions = _sigma_for_sessions(frame["t_close"], warm, VOL_WINDOW)
    vt_sessions = np.minimum(1.0, VOL_TARGET / np.maximum(sigma_sessions, 1e-12))
    vt_sessions = np.where(np.isfinite(vt_sessions), vt_sessions, 0.0)
    rng = np.random.default_rng(20261127)
    draws = []
    for _ in range(300):
        mask = np.zeros(nd, dtype=bool)
        mask[rng.choice(nd, n_flow, replace=False)] = True
        f = np.where(mask, 0.0, vt_sessions)
        f[0] = frac_centre[0]
        draws.append(daily_cagr(f, frame))
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": len(draws), "marks": "1D open-to-open",
        "real_daily_cagr": float(real_daily_cagr),
        "real_1m_cagr_1bp": float(s1["cagr"]),
        "mean": float(draws.mean()),
        "p95": float(np.quantile(draws, 0.95)),
        "p99": float(np.quantile(draws, 0.99)),
        "max": float(draws.max()),
        "p_value": float((draws >= real_daily_cagr).mean()),
    }
    print("placebo", {k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in out["placebo"].items()})

    # ---- cut tests ----------------------------------------------------------
    cuts = {}
    for year in (2016, 2018, 2020, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, COL_T], year),
        }
    # drop the best month of the centre
    r = daily_returns(res1)
    rm = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    best = rm.idxmax()
    cuts[f"drop_best_month_{best[0]}_{best[1]:02d}"] = drop_month(
        res1["ts"], res1["equity"], best[0], best[1])
    out["cut_tests"] = cuts
    for k, v in cuts.items():
        if "strategy" in v:
            print(f"cut ex-{k}: strat {v['strategy']['cagr']*100:6.2f}% / "
                  f"{v['strategy']['max_drawdown']*100:5.2f}%  bench "
                  f"{v['benchmark_ex_year']['cagr']*100:6.2f}% / "
                  f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")
        else:
            print(f"cut {k}: {v['cagr']*100:6.2f}% / {v['max_drawdown']*100:5.2f}%")

    # ---- controls / decomposition ------------------------------------------
    controls = {}
    wt = build_weights_params(ts, o, c, flow_thr=99.0)  # no flow, VT only
    _, s = run_weights(ts, o, c, wt)
    controls["vol_target_only"] = pack(s)
    print(f"control VT only            CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    wt = build_weights_params(ts, o, c, vol_target=None)  # flow only
    _, s = run_weights(ts, o, c, wt)
    controls["flow_only"] = pack(s)
    print(f"control flow only          CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    mean_w = float(wbar.mean())
    wc = np.zeros((len(ts), 3))
    wc[:, COL_T] = mean_w
    wc[:, COL_B] = 1.0 - mean_w
    _, s = run_weights(ts, o, c, wc)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": mean_w}
    print(f"control constant {mean_w:.3f}    CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    wb = np.zeros((len(ts), 3)); wb[:, COL_T] = 1.0
    _, s = run_weights(ts, o, c, wb)
    controls["tqqq_buy_hold"] = pack(s)
    out["controls"] = controls

    # ---- signal diagnostics ------------------------------------------------
    q_cc, q_l30 = frame["q_cc"], frame["q_l30"]
    t_next = np.r_[frame["t_oo"][1:], np.nan]
    q_next = np.r_[frame["q_oo"][1:], np.nan]
    diag = []
    for thr, l30 in ((0.0075, 0.0), (0.0100, 0.0), (0.0125, 0.0),
                     (0.0150, 0.0), (0.0200, 0.0), (0.0125, 0.001),
                     (0.0125, -0.001)):
        sel = (q_cc[:-2] > thr) & (q_l30[:-2] > l30)
        x, y = t_next[:-2][sel], q_next[:-2][sel]
        n = int(sel.sum())
        diag.append({
            "flow_thr": thr, "l30_confirm": l30, "n": n,
            "tqqq_next_oo_bp": float(np.nanmean(x) * 1e4),
            "tqqq_t": float(np.nanmean(x) / (np.nanstd(x) / np.sqrt(n))),
            "qqq_next_oo_bp": float(np.nanmean(y) * 1e4),
            "qqq_t": float(np.nanmean(y) / (np.nanstd(y) / np.sqrt(n))),
        })
        print(f"diag thr {thr*100:.2f}% l30>{l30*100:+.1f}% n={n:4d} "
              f"TQQQ {np.nanmean(x)*1e4:+7.1f}bp t {np.nanmean(x)/(np.nanstd(x)/np.sqrt(n)):+5.2f}")
    out["signal_diagnostics"] = diag

    # event decomposition for the centre
    ev = np.flatnonzero((q_cc[:-1] > FLOW_THR) & (q_l30[:-1] > L30_CONFIRM)) + 1
    gap = frame["t_open"][ev] / frame["t_close"][ev - 1] - 1.0
    intra = frame["t_close"][ev] / frame["t_open"][ev] - 1.0
    ovn = np.array([frame["t_open"][e + 1] / frame["t_close"][e] - 1.0
                    if e + 1 < nd else np.nan for e in ev])
    oo = frame["t_oo"][ev]
    out["event_decomposition"] = {
        "n": int(len(ev)),
        "gap_prevclose_to_open_bp": float(np.nanmean(gap) * 1e4),
        "gap_t": float(np.nanmean(gap) / (np.nanstd(gap) / np.sqrt(len(gap)))),
        "intraday_bp": float(np.nanmean(intra) * 1e4),
        "intraday_t": float(np.nanmean(intra) / (np.nanstd(intra) / np.sqrt(len(intra)))),
        "overnight_bp": float(np.nanmean(ovn) * 1e4),
        "overnight_t": float(np.nanmean(ovn) / (np.nanstd(ovn) / np.sqrt(np.sum(np.isfinite(ovn))))),
        "skipped_oo_bp": float(np.nanmean(oo) * 1e4),
        "skipped_oo_t": float(np.nanmean(oo) / (np.nanstd(oo) / np.sqrt(len(oo)))),
    }
    print("event decomposition", {k: (round(v, 2) if isinstance(v, float) else v)
                                  for k, v in out["event_decomposition"].items()})

    # fade asymmetry (up day, last 30 min down)
    sel = (q_cc[:-2] > FLOW_THR) & (q_l30[:-2] <= L30_CONFIRM)
    x = t_next[:-2][sel]
    out["fade_asymmetry"] = {
        "n": int(sel.sum()), "tqqq_next_oo_bp": float(np.nanmean(x) * 1e4),
        "t": float(np.nanmean(x) / (np.nanstd(x) / np.sqrt(sel.sum()))),
    }
    print("fade asymmetry", out["fade_asymmetry"])

    # ---- causality: truncation test ----------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "compare_through": "2021-12-29",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:j2], w[:j2])),
    }
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
