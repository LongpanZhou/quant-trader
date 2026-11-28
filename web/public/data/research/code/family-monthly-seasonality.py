"""Month-of-year seasonality: full winter, reduced summer, flat September.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
For each regular session k:

    w_tqqq(k) = 1.00   if month(k) in {Nov, Dec, Jan, Feb, Mar, Apr}
              = 0.70   if month(k) in {May, Jun, Jul, Aug, Oct}
              = 0.00   if month(k) == Sep
    w_bil(k)  = 1 - w_tqqq(k)

The month is known at the prior close.  The target for the first session of a
new month is set at the previous month's last close and filled at the next
open.  Idle is BIL.  The 2% rebalance band is the harness default.

The delivered centre is (summer_weight=0.70, september_weight=0.00).  The
8-cell pre-registered grid is in HYPOTHESIS.md.  No 2024+ bar is loaded.
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
SUMMER_W = 0.70
SEP_W = 0.00
SUMMER_MONTHS = (5, 6, 7, 8, 10)
WINTER_MONTHS = (11, 12, 1, 2, 3, 4)

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
PANEL_BAR = {"cagr": 0.3629, "max_drawdown": 0.8157, "sharpe": 0.80}

WINNERS = (
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
)


# --------------------------------------------------------------------------- #
# calendar and weights
# --------------------------------------------------------------------------- #
def calendar(ts):
    """Per-session calendar arrays.  All values are known ex-ante."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    sd = pd.to_datetime(pd.Series(dates[first]))
    month = sd.dt.month.to_numpy()
    year = sd.dt.year.to_numpy()
    return {"dates": dates, "first": first, "last": last, "nd": nd,
            "month": month, "year": year}


def schedule(month, summer_w=SUMMER_W, sep_w=SEP_W):
    """Target TQQQ weight for each session from its calendar month."""
    out = np.ones(len(month), dtype=float)
    out[np.isin(month, SUMMER_MONTHS)] = summer_w
    out[month == 9] = sep_w
    return out


def weights_from_target(ts, first, last, nd, target, idle_bil=True):
    """Map a per-session target to (n, 3) bar weights, next-open fills."""
    w = np.zeros((len(ts), 3))
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        x = float(target[k])
        w[f:l, COL_T] = x
        if idle_bil:
            w[f:l, COL_B] = 1.0 - x
        xn = float(target[k + 1]) if k + 1 < nd else x
        w[l, COL_T] = xn
        if idle_bil:
            w[l, COL_B] = 1.0 - xn
    assert w.min() >= -1e-12, "negative weight"
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9), "weights sum > 1"
    return w


def build_weights_params(ts, o, c, summer_w=SUMMER_W, sep_w=SEP_W,
                         idle_bil=True):
    cal = calendar(ts)
    target = schedule(cal["month"], summer_w, sep_w)
    return weights_from_target(ts, cal["first"], cal["last"], cal["nd"],
                               target, idle_bil=idle_bil)


def build_weights(ts, o, c):
    """Pre-registered centre."""
    return build_weights_params(ts, o, c)


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s):
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, slip=1.0, start=DEV_START):
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_equity(res):
    s = pd.Series(res["equity"], index=res["ts"])
    d = s.groupby(res["ts"].date).last()
    d.index = pd.to_datetime(d.index)
    return d


def daily_returns(res):
    return daily_equity(res).pct_change().dropna()


def annual_returns(de, start_equity=100_000.0):
    out = {}
    prev = start_equity
    for year in range(2016, 2024):
        x = de[de.index.year == year]
        if len(x) == 0:
            continue
        out[str(year)] = float(x.iloc[-1] / prev - 1.0)
        prev = x.iloc[-1]
    return out


def subperiod(de, lo, hi):
    x = de[(de.index >= lo) & (de.index <= hi)]
    if len(x) < 2:
        return None
    years = (x.index[-1] - x.index[0]).days / 365.25
    return {"cagr": float((x.iloc[-1] / x.iloc[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / x.cummax() - 1).min()),
            "years": float(years)}


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def _compound(r):
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


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
    """Session-level frame for the placebo / event study."""
    cal = calendar(ts)
    first, last, nd = cal["first"], cal["last"], cal["nd"]
    t_open = np.asarray(o)[first, COL_T]
    t_close = np.asarray(c)[last, COL_T]
    b_open = np.asarray(o)[first, COL_B]
    b_close = np.asarray(c)[last, COL_B]
    q_close = np.asarray(c)[last, COL_Q]
    t_oo = np.r_[t_open[1:] / t_open[:-1] - 1.0, 0.0]
    b_oo = np.r_[b_open[1:] / b_open[:-1] - 1.0, 0.0]
    q_oo = np.r_[q_close[1:] / q_close[:-1] - 1.0, 0.0]
    t_oc = t_close / t_open - 1.0
    q_oc = np.asarray(c)[last, COL_Q] / np.asarray(o)[first, COL_Q] - 1.0
    return {"cal": cal, "t_oo": t_oo, "b_oo": b_oo, "q_oo": q_oo,
            "t_oc": t_oc, "q_oc": q_oc, "t_close": t_close,
            "t_open": t_open}


def daily_cagr(frac, frame, idle_bil=True):
    r = frac * frame["t_oo"]
    if idle_bil:
        r = r + (1.0 - frac) * frame["b_oo"]
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    return float(eq[-1] ** (1 / years) - 1.0)


def correlation_to_winners(r):
    out = {}
    for slug in WINNERS:
        path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
        d = json.loads(path.read_text())
        idx = pd.to_datetime(d["dates"])
        v = pd.Series(d["values"], index=idx)
        # development window only: never inspect 2024+
        v = v[v.index <= pd.Timestamp(DEV_END)]
        rr = v.pct_change().dropna()
        j = pd.concat([r, rr], axis=1, join="inner").dropna()
        out[slug] = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
    vals = np.array(list(out.values()))
    return {"by_slug": out, "min": float(vals.min()),
            "max": float(vals.max()), "mean": float(vals.mean())}


def causality_check(ts, o, c, builder):
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = builder(ts[:j], o[:j], c[:j])
    w_full = builder(ts, o, c)
    return {"truncation_date": "2022-01-03", "compare_through": "2021-12-29",
            "prior_weights_unchanged": bool(np.allclose(w_trunc[:j2], w_full[:j2]))}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=5)
    cal = calendar(ts)
    frame = daily_frame(ts, o, c)
    nd = cal["nd"]
    print(f"panel {len(ts):,} bars, {nd} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    w = build_weights(ts, o, c)
    dclose = np.asarray(c)[cal["last"], COL_T]
    i0 = bt.start_index(ts, DEV_START)
    bench_bars = np.asarray(c)[i0:, COL_T]
    bench = bt.benchmark(bench_bars, ts[i0:], BARS_1M)

    out = {
        "strategy": "family-monthly-seasonality",
        "directory": "research/new/family-monthly-seasonality",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "rules": {
            "clock": "calendar month of the session, set at the prior close",
            "winter_months": list(WINTER_MONTHS),
            "summer_months": list(SUMMER_MONTHS),
            "winter_weight": 1.00,
            "summer_weight": SUMMER_W,
            "september_weight": SEP_W,
            "bar": BAR,
            "panel_bar": PANEL_BAR,
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

    # exposure: bt.stats counts BIL as invested; the TQQQ weight is the signal
    wbar = w[:, COL_T]
    wsess = w[cal["first"], COL_T]
    out["exposure"] = {
        "mean_tqqq_weight_bar": float(wbar.mean()),
        "mean_tqqq_weight_session": float(wsess.mean()),
        "fraction_sessions_full": float((wsess > 0.99).mean()),
        "fraction_sessions_reduced": float(((wsess > 0.01) & (wsess < 0.99)).mean()),
        "fraction_sessions_out": float((wsess < 0.01).mean()),
        "mean_bil_weight": float(1.0 - wbar.mean()),
        "stats_exposure_incl_bil": float(s1["exposure"]),
    }
    print("exposure", {k: round(v, 3) for k, v in out["exposure"].items()})

    de = daily_equity(res1)
    r = de.pct_change().dropna()
    out["yearly"] = {
        y: {"strategy": v,
            "benchmark": float(bt.yearly(res1["ts"], res1["equity"],
                                         bench_bars)[int(y)]["benchmark"])}
        for y, v in annual_returns(de).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(de, "2016-01-04", "2019-12-31"),
        "2020_2023": subperiod(de, "2020-01-02", "2023-12-29"),
    }
    ex = de[de.index.year != 2020]
    yrs = (ex.index[-1] - ex.index[0]).days / 365.25
    out["ex2020"] = {"cagr": float((ex.iloc[-1] / ex.iloc[0]) ** (1 / yrs) - 1),
                     "max_drawdown": float(-(ex / ex.cummax() - 1).min())}
    out["monthly"] = monthly_stats(res1["ts"], res1["equity"], bench_bars)
    print("monthly excess mean %.2f%% median %.2f%% t %.2f win %.1f%%" % (
        out["monthly"]["mean_excess"] * 100, out["monthly"]["median_excess"] * 100,
        out["monthly"]["t_excess"], out["monthly"]["win_rate"] * 100))

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (0.60, 0.00, "summer neighbour"),
        (0.65, 0.00, "summer neighbour"),
        (0.70, 0.00, "centre"),
        (0.75, 0.00, "summer neighbour"),
        (0.80, 0.00, "summer neighbour"),
        (0.85, 0.00, "summer neighbour"),
        (0.90, 0.00, "summer neighbour"),
        (0.70, 0.25, "September partial"),
    ]
    grid = []
    for sw, sep, role in grid_spec:
        wt = build_weights_params(ts, o, c, summer_w=sw, sep_w=sep)
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        grid.append({"summer_weight": sw, "september_weight": sep,
                     "role": role, **pack(s), "ten_bp": pack(s10)})
        print(f"grid summer={sw:.2f} sep={sep:.2f} {role:20s} "
              f"1bp CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:.2f}  10bp CAGR {s10['cagr']*100:6.2f}%")
    out["grid"] = grid

    # ---- neighbours / controls ---------------------------------------------
    controls = {}
    wt = build_weights_params(ts, o, c, summer_w=1.0, sep_w=1.0)
    _, s = run_weights(ts, o, c, wt)
    controls["tqqq_buy_hold"] = pack(s)
    print(f"control TQQQ               CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    wt = build_weights_params(ts, o, c, summer_w=0.0, sep_w=0.0)
    _, s = run_weights(ts, o, c, wt)
    controls["nov_apr_only"] = pack(s)
    print(f"control Nov-Apr only       CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    wt = build_weights_params(ts, o, c, summer_w=1.0, sep_w=0.0)
    _, s = run_weights(ts, o, c, wt)
    controls["september_off_only"] = pack(s)
    print(f"control Sep-off only       CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    wt = build_weights_params(ts, o, c, summer_w=0.70, sep_w=0.00,
                              idle_bil=False)
    _, s = run_weights(ts, o, c, wt)
    controls["centre_cash_idle"] = pack(s)
    print(f"control centre cash idle   CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    mean_w = float(wbar.mean())
    wc = np.zeros((len(ts), 3))
    wc[:, COL_T] = mean_w
    wc[:, COL_B] = 1.0 - mean_w
    _, s = run_weights(ts, o, c, wc)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": mean_w}
    print(f"control constant {mean_w:.3f}    CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    out["controls"] = controls

    # ---- monthly signal diagnostics ----------------------------------------
    month = cal["month"]
    diag = []
    for m in range(1, 13):
        x = frame["t_oo"][month == m]
        x = x[np.isfinite(x)]
        n = int(len(x))
        diag.append({
            "month": m, "n": n,
            "mean_bp": float(np.mean(x) * 1e4),
            "t": float(np.mean(x) / (np.std(x, ddof=0) / np.sqrt(n))),
            "win": float((x > 0).mean()),
            "weight": float(schedule(np.array([m]))[0]),
        })
    out["monthly_diagnostics"] = diag
    print("monthly diagnostics", [(d["month"], round(d["mean_bp"], 1), round(d["t"], 2))
                                  for d in diag])

    # ---- placebos -----------------------------------------------------------
    # (a) deterministic: each other month is the off month, same summer set
    off_month = []
    for m in range(1, 13):
        if m == 9:
            continue
        f = np.where(month == m, 0.0,
                     np.where(np.isin(month, SUMMER_MONTHS), SUMMER_W, 1.0))
        off_month.append({"off_month": m,
                          "daily_cagr": daily_cagr(f, frame, idle_bil=True)})
    out["placebo_off_month"] = off_month
    print("off-month placebo", [(d["off_month"], round(d["daily_cagr"], 4))
                                for d in off_month])

    # (b) shift the whole schedule by +1 / -1 month
    shifted = []
    for shift, label in ((1, "+1 month"), (-1, "-1 month")):
        sm = ((month - 1 + shift) % 12) + 1
        f = np.where(sm == 9, 0.0,
                     np.where(np.isin(sm, SUMMER_MONTHS), SUMMER_W, 1.0))
        shifted.append({"shift": label,
                        "daily_cagr": daily_cagr(f, frame, idle_bil=True)})
    out["placebo_shifted_month"] = shifted
    print("shifted schedule", shifted)

    # (c) random off month + five random summer months
    rng = np.random.default_rng(20261127)
    real_daily = daily_cagr(schedule(month), frame, idle_bil=True)
    draws = []
    for _ in range(1000):
        off = int(rng.integers(1, 13))
        candidates = [x for x in range(1, 13) if x != off]
        summer = rng.choice(candidates, 5, replace=False)
        f = np.where(month == off, 0.0,
                     np.where(np.isin(month, summer), SUMMER_W, 1.0))
        draws.append(daily_cagr(f, frame, idle_bil=True))
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": int(len(draws)), "marks": "1D open-to-open",
        "real_daily_cagr": float(real_daily),
        "real_1m_cagr_1bp": float(s1["cagr"]),
        "mean": float(draws.mean()),
        "p95": float(np.quantile(draws, 0.95)),
        "p99": float(np.quantile(draws, 0.99)),
        "max": float(draws.max()),
        "p_value": float((draws >= real_daily).mean()),
    }
    print("placebo", {k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in out["placebo"].items()})

    # ---- correlations -------------------------------------------------------
    out["correlation"] = correlation_to_winners(r)
    print("corr winners min %.3f max %.3f mean %.3f" % (
        out["correlation"]["min"], out["correlation"]["max"],
        out["correlation"]["mean"]))
    print("corr", {k: round(v, 3) for k, v in out["correlation"]["by_slug"].items()})

    # ---- causality ----------------------------------------------------------
    out["causality"] = causality_check(ts, o, c, build_weights)
    print("causality", out["causality"])

    # ---- kill criteria ------------------------------------------------------
    dev10 = out["dev"]["10bp"]
    c1 = dev10["cagr"] <= BAR["cagr"] or dev10["max_drawdown"] >= BAR["max_drawdown"]
    c2 = out["ex2020"]["cagr"] <= 0.2835
    off_vals = {d["off_month"]: d["daily_cagr"] for d in off_month}
    c3 = real_daily < max(off_vals.values())
    c4 = any(d["daily_cagr"] > real_daily for d in shifted)
    c5 = any(g["summer_weight"] in (0.60, 0.80) and g["september_weight"] == 0.0
             and g["ten_bp"]["cagr"] <= BAR["cagr"] for g in grid)
    # c6: 2020 share of total log return
    yr = out["yearly"]
    log_total = sum(np.log1p(v["strategy"]) for v in yr.values())
    log_2020 = np.log1p(yr["2020"]["strategy"])
    c6 = log_2020 / log_total > 0.50 if log_total > 0 else False
    kills = {
        "c1_10bp_cagr_or_dd": bool(c1),
        "c2_ex2020_below_tqqq": bool(c2),
        "c3_september_not_best_off_month": bool(c3),
        "c4_shifted_month_beats_real": bool(c4),
        "c5_grid_spike": bool(c5),
        "c6_2020_share_above_half": bool(c6),
    }
    out["kill_criteria"] = kills
    out["verdict"] = "negative" if any(kills.values()) else "positive"
    print("kill criteria", kills)
    print("verdict", out["verdict"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
