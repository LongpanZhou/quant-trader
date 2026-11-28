"""Weekday seasonality: half-sized Friday de-risk.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
For each regular session k:

    w_tqqq(k) = 0.50   if weekday(k) == Friday
              = 1.00   otherwise
    w_cash(k) = 1 - w_tqqq(k)

The centre uses cash, not BIL, on the de-risked leg: BIL adds a second leg and
roughly doubles the weekly turnover for a ~1.4%/yr yield on 10% of the book.
The BIL-idle variant is a control.

The Friday/Monday calendar is known at the prior close; the target for Friday
is set at Thursday's 16:00 close and the target for Monday at Friday's 16:00
close.  The delivered centre is (friday_weight=0.50, other_weight=1.00).  The
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
FRI_W = 0.50
OTHER_W = 1.00

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
PANEL_BAR = {"cagr": 0.3629, "max_drawdown": 0.8157, "sharpe": 0.80}

WINNERS = (
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
)
DOW_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


# --------------------------------------------------------------------------- #
# calendar and weights
# --------------------------------------------------------------------------- #
def calendar(ts):
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    sd = pd.to_datetime(pd.Series(dates[first]))
    return {"dates": dates, "first": first, "last": last, "nd": nd,
            "dow": sd.dt.day_of_week.to_numpy(),
            "month": sd.dt.month.to_numpy(),
            "year": sd.dt.year.to_numpy()}


def weights_from_target(ts, first, last, nd, target, idle_bil=False):
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


def build_weights_params(ts, o, c, fri_w=FRI_W, other_w=OTHER_W,
                         idle_bil=False, de_risk_day=4):
    cal = calendar(ts)
    target = np.where(cal["dow"] == de_risk_day, fri_w, other_w)
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
    cal = calendar(ts)
    first, last, nd = cal["first"], cal["last"], cal["nd"]
    t_open = np.asarray(o)[first, COL_T]
    t_close = np.asarray(c)[last, COL_T]
    b_open = np.asarray(o)[first, COL_B]
    q_close = np.asarray(c)[last, COL_Q]
    t_oo = np.r_[t_open[1:] / t_open[:-1] - 1.0, 0.0]
    b_oo = np.r_[b_open[1:] / b_open[:-1] - 1.0, 0.0]
    q_oo = np.r_[q_close[1:] / q_close[:-1] - 1.0, 0.0]
    t_oc = t_close / t_open - 1.0
    q_oc = np.asarray(c)[last, COL_Q] / np.asarray(o)[first, COL_Q] - 1.0
    return {"cal": cal, "t_oo": t_oo, "b_oo": b_oo, "q_oo": q_oo,
            "t_oc": t_oc, "q_oc": q_oc}


def daily_cagr(frac, frame, idle_bil=False):
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
    i0 = bt.start_index(ts, DEV_START)
    bench_bars = np.asarray(c)[i0:, COL_T]
    bench = bt.benchmark(bench_bars, ts[i0:], BARS_1M)

    out = {
        "strategy": "family-weekday-seasonality",
        "directory": "research/new/family-weekday-seasonality",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "cash"},
        "rules": {
            "clock": "day of week of the session, set at the prior close",
            "friday_weight": FRI_W,
            "other_weight": OTHER_W,
            "idle": "cash (BIL control reported)",
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

    wbar = w[:, COL_T]
    wsess = w[cal["first"], COL_T]
    out["exposure"] = {
        "mean_tqqq_weight_bar": float(wbar.mean()),
        "mean_tqqq_weight_session": float(wsess.mean()),
        "fraction_sessions_full": float((wsess > 0.99).mean()),
        "fraction_sessions_reduced": float(((wsess > 0.01) & (wsess < 0.99)).mean()),
        "fraction_sessions_out": float((wsess < 0.01).mean()),
        "mean_bil_weight": float(w[:, COL_B].mean()),
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
    grid_spec = [(0.00, "full Friday de-risk (gross-max)"),
                 (0.20, "neighbour"), (0.35, "neighbour"),
                 (0.50, "centre"), (0.65, "neighbour"),
                 (0.80, "neighbour"), (0.90, "neighbour"),
                 (1.00, "TQQQ control")]
    grid = []
    for fw, role in grid_spec:
        wt = build_weights_params(ts, o, c, fri_w=fw)
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        grid.append({"friday_weight": fw, "other_weight": 1.0,
                     "role": role, **pack(s), "ten_bp": pack(s10)})
        print(f"grid fri={fw:.2f} {role:30s} 1bp CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
              f"10bp CAGR {s10['cagr']*100:6.2f}%")
    out["grid"] = grid

    # ---- controls -----------------------------------------------------------
    controls = {}
    wt = build_weights_params(ts, o, c, fri_w=1.0, other_w=1.0)
    _, s = run_weights(ts, o, c, wt)
    controls["tqqq_buy_hold"] = pack(s)
    print(f"control TQQQ               CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    wt = build_weights_params(ts, o, c, fri_w=0.0, other_w=1.0)
    _, s = run_weights(ts, o, c, wt)
    _, s10 = run_weights(ts, o, c, wt, slip=10.0)
    controls["full_friday_derisk_cash"] = {"1bp": pack(s), "10bp": pack(s10)}
    print(f"control full Fri cash      1bp CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
          f"10bp CAGR {s10['cagr']*100:6.2f}%")

    wt = build_weights_params(ts, o, c, fri_w=0.0, other_w=1.0, idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    _, s10 = run_weights(ts, o, c, wt, slip=10.0)
    controls["full_friday_derisk_bil"] = {"1bp": pack(s), "10bp": pack(s10)}
    print(f"control full Fri BIL       1bp CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
          f"10bp CAGR {s10['cagr']*100:6.2f}%")

    wt = build_weights_params(ts, o, c, fri_w=0.5, other_w=1.0, idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    _, s10 = run_weights(ts, o, c, wt, slip=10.0)
    controls["centre_bil_idle"] = {"1bp": pack(s), "10bp": pack(s10)}
    print(f"control centre BIL         1bp CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
          f"10bp CAGR {s10['cagr']*100:6.2f}%")

    # other-weekday controls, same 50% de-risk
    weekday_controls = {}
    for d in range(5):
        wt = build_weights_params(ts, o, c, fri_w=0.5, other_w=1.0,
                                  de_risk_day=d)
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        weekday_controls[DOW_NAMES[d]] = {"derisk_weight": 0.5,
                                          "1bp": pack(s), "10bp": pack(s10)}
        print(f"control 50% off {DOW_NAMES[d]:9s} 1bp CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
              f"10bp CAGR {s10['cagr']*100:6.2f}%")
    controls["same_derisk_other_weekdays"] = weekday_controls

    # weekday-only long strategies
    only = {}
    for d in range(5):
        target = (cal["dow"] == d).astype(float) * 1.0
        wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                                 idle_bil=False)
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        only[DOW_NAMES[d]] = {"1bp": pack(s), "10bp": pack(s10)}
        print(f"control {DOW_NAMES[d]:9s} only  1bp CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
              f"10bp CAGR {s10['cagr']*100:6.2f}%")
    controls["weekday_only"] = only

    # Monday+Tuesday only
    target = np.isin(cal["dow"], [0, 1]).astype(float)
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=False)
    _, s = run_weights(ts, o, c, wt)
    _, s10 = run_weights(ts, o, c, wt, slip=10.0)
    controls["monday_tuesday_only"] = {"1bp": pack(s), "10bp": pack(s10)}
    print(f"control Mon+Tue only       1bp CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
          f"10bp CAGR {s10['cagr']*100:6.2f}%")
    out["controls"] = controls

    # ---- weekday diagnostics ------------------------------------------------
    diag = []
    for d in range(5):
        m = cal["dow"] == d
        for key, label in (("t_oo", "tqqq_oo"), ("t_oc", "tqqq_oc"),
                           ("q_oo", "qqq_oo")):
            x = frame[key][m]
            x = x[np.isfinite(x)]
            n = int(len(x))
            diag.append({
                "weekday": DOW_NAMES[d], "series": label, "n": n,
                "mean_bp": float(np.mean(x) * 1e4),
                "t": float(np.mean(x) / (np.std(x, ddof=0) / np.sqrt(n))),
                "win": float((x > 0).mean()),
            })
    out["weekday_diagnostics"] = diag
    print("weekday diagnostics")
    for d in range(5):
        row = [x for x in diag if x["weekday"] == DOW_NAMES[d] and x["series"] == "tqqq_oo"][0]
        print(f"  {DOW_NAMES[d]:9s} n={row['n']} mean={row['mean_bp']:+7.1f}bp t={row['t']:+5.2f}")

    # ---- placebo ------------------------------------------------------------
    n_fri = int(np.sum(cal["dow"] == 4))
    real_daily = daily_cagr(np.where(cal["dow"] == 4, FRI_W, OTHER_W),
                            frame, idle_bil=False)
    rng = np.random.default_rng(20261127)
    draws = []
    base = np.full(nd, OTHER_W)
    for _ in range(1000):
        mask = rng.choice(nd, n_fri, replace=False)
        f = base.copy()
        f[mask] = FRI_W
        draws.append(daily_cagr(f, frame, idle_bil=False))
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": int(len(draws)), "marks": "1D open-to-open",
        "n_friday_days": n_fri,
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
    c2 = dev10["cagr"] <= BAR["cagr"] + 0.0025
    c3 = out["ex2020"]["cagr"] <= 0.2835
    c4 = out["placebo"]["p_value"] > 0.10
    g35 = [g for g in grid if g["friday_weight"] == 0.35][0]
    g65 = [g for g in grid if g["friday_weight"] == 0.65][0]
    c5 = (g35["ten_bp"]["cagr"] <= BAR["cagr"]
          and g65["ten_bp"]["cagr"] <= BAR["cagr"])
    fri10 = dev10
    c6 = any(v["10bp"]["cagr"] > fri10["cagr"]
             and v["10bp"]["max_drawdown"] < fri10["max_drawdown"]
             for k, v in weekday_controls.items() if k != "Friday")
    yr = out["yearly"]
    log_total = sum(np.log1p(v["strategy"]) for v in yr.values())
    log_2020 = np.log1p(yr["2020"]["strategy"])
    c7 = log_2020 / log_total > 0.50 if log_total > 0 else False
    kills = {
        "c1_10bp_cagr_or_dd": bool(c1),
        "c2_10bp_margin_below_0.25pp": bool(c2),
        "c3_ex2020_below_tqqq": bool(c3),
        "c4_placebo_p_above_0.10": bool(c4),
        "c5_grid_spike": bool(c5),
        "c6_other_weekday_beats_friday": bool(c6),
        "c7_2020_share_above_half": bool(c7),
    }
    out["kill_criteria"] = kills
    out["verdict"] = "negative" if any(kills.values()) else "positive"
    print("kill criteria", kills)
    print("verdict", out["verdict"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
