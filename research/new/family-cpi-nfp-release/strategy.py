"""CPI/NFP release windows: the CPI release-day drift.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
For each month, let `cpi_day` be the first regular session whose calendar day
of month is >= 12.  This is a fixed ex-ante proxy for the CPI release, which
is published at 08:30 ET in the 10th-15th calendar-day window.  Then:

    w_tqqq(k) = 1.00   if k == cpi_day
              = 0.00   otherwise
    w_bil(k)  = 1 - w_tqqq(k)

The CPI proxy date is known at the start of the month.  The target is set at
the prior close and filled at the CPI session's open; the exit target (0) is
set at the CPI session's close and filled at the next open.

NFP (first Friday of the month) is a pre-registered control, not the centre:
the NFP day is flat on average in this sample, while the CPI day is positive.
The delivered centre is (cpi_day_offset=12, window=1, weight=1.00).  The
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
CPI_DAY = 12
CPI_WINDOW = 1
CPI_WEIGHT = 1.00

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
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    sd = pd.to_datetime(pd.Series(dates[first]))
    dom = sd.dt.day.to_numpy()
    dow = sd.dt.day_of_week.to_numpy()
    month = sd.dt.month.to_numpy()
    year = sd.dt.year.to_numpy()
    month_id = year * 100 + month
    return {"dates": dates, "first": first, "last": last, "nd": nd,
            "dom": dom, "dow": dow, "month": month, "year": year,
            "month_id": month_id}


def event_days(cal, cpi_day=CPI_DAY, include_nfp=False):
    """Boolean per-session flags for the CPI proxy and the NFP proxy."""
    nd = cal["nd"]
    cpi = np.zeros(nd, dtype=bool)
    nfp = np.zeros(nd, dtype=bool)
    for m in np.unique(cal["month_id"]):
        idx = np.flatnonzero(cal["month_id"] == m)
        hit = idx[cal["dom"][idx] >= cpi_day]
        if len(hit):
            cpi[hit[0]] = True
        fri = idx[cal["dow"][idx] == 4]
        if len(fri):
            nfp[fri[0]] = True
    return cpi, nfp


def window_flag(flag, length):
    """True for `length` consecutive sessions starting at each event day."""
    out = flag.copy()
    for j in range(1, length):
        out = out | np.r_[flag[j:], np.zeros(j, dtype=bool)]
    return out


def weights_from_target(ts, first, last, nd, target, idle_bil=True):
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


def build_weights_params(ts, o, c, cpi_day=CPI_DAY, window=CPI_WINDOW,
                         weight=CPI_WEIGHT, include_nfp=False,
                         idle_bil=True):
    cal = calendar(ts)
    cpi, nfp = event_days(cal, cpi_day=cpi_day)
    flag = cpi | nfp if include_nfp else cpi
    flag = window_flag(flag, window)
    target = flag.astype(float) * weight
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


def daily_frame(ts, o, c):
    cal = calendar(ts)
    first, last, nd = cal["first"], cal["last"], cal["nd"]
    t_open = np.asarray(o)[first, COL_T]
    t_close = np.asarray(c)[last, COL_T]
    b_open = np.asarray(o)[first, COL_B]
    q_open = np.asarray(o)[first, COL_Q]
    q_close = np.asarray(c)[last, COL_Q]
    t_oo = np.r_[t_open[1:] / t_open[:-1] - 1.0, 0.0]
    b_oo = np.r_[b_open[1:] / b_open[:-1] - 1.0, 0.0]
    q_oo = np.r_[q_open[1:] / q_open[:-1] - 1.0, 0.0]
    t_oc = t_close / t_open - 1.0
    q_oc = q_close / q_open - 1.0
    return {"cal": cal, "t_oo": t_oo, "b_oo": b_oo, "q_oo": q_oo,
            "t_oc": t_oc, "q_oc": q_oc}


def daily_cagr(frac, frame, idle_bil=True):
    r = frac * frame["t_oo"]
    if idle_bil:
        r = r + (1.0 - frac) * frame["b_oo"]
    eq = np.cumprod(1.0 + r)
    years = len(r) / 252.0
    return float(eq[-1] ** (1 / years) - 1.0)


def stat(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return {"n": int(n), "mean_bp": float("nan"), "t": float("nan"),
                "win": float("nan"), "sd_bp": float("nan")}
    return {"n": int(n), "mean_bp": float(np.mean(x) * 1e4),
            "t": float(np.mean(x) / (np.std(x, ddof=0) / np.sqrt(n))),
            "win": float((x > 0).mean()),
            "sd_bp": float(np.std(x, ddof=0) * 1e4)}


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
        "strategy": "family-cpi-nfp-release",
        "directory": "research/new/family-cpi-nfp-release",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "rules": {
            "clock": "CPI proxy = first session on/after calendar day 12; "
                     "NFP proxy = first Friday session",
            "cpi_day_offset": CPI_DAY,
            "cpi_window": CPI_WINDOW,
            "cpi_weight": CPI_WEIGHT,
            "nfp_role": "control, not centre",
            "cpi_assumption": "CPI is released at 08:30 ET in the 10th-15th "
                              "calendar-day window; day 12 is the midpoint "
                              "proxy, not the actual release date",
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
        "fraction_sessions_in": float((wsess > 0.99).mean()),
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

    # ---- event diagnostics --------------------------------------------------
    cpi, nfp = event_days(cal)
    ev = cpi | nfp
    prev = np.r_[False, ev[:-1]]
    nxt = np.r_[ev[1:], False]
    rows = []
    for name, flag in (("cpi_day12", cpi), ("nfp_first_friday", nfp),
                       ("cpi_or_nfp", ev)):
        rows.append({
            "event": name,
            "n": int(flag.sum()),
            "day_tqqq_oo": stat(frame["t_oo"][flag]),
            "day_tqqq_oc": stat(frame["t_oc"][flag]),
            "day_qqq_oo": stat(frame["q_oo"][flag]),
            "day_qqq_oc": stat(frame["q_oc"][flag]),
            "pre_tqqq_oo": stat(frame["t_oo"][np.r_[False, flag[:-1]]]),
            "next_tqqq_oo": stat(frame["t_oo"][np.r_[flag[1:], False]]),
            "two_day_tqqq_oo": stat(frame["t_oo"][flag] +
                                    frame["t_oo"][np.r_[flag[1:], False]]),
        })
    out["event_diagnostics"] = rows
    for row in rows:
        print(f"{row['event']:18s} n={row['n']:3d} day {row['day_tqqq_oo']['mean_bp']:+7.1f}bp "
              f"t {row['day_tqqq_oo']['t']:+5.2f}  next {row['next_tqqq_oo']['mean_bp']:+7.1f}bp  "
              f"2day {row['two_day_tqqq_oo']['mean_bp']:+7.1f}bp")

    # by-year CPI-day mean
    by_year = []
    for y in range(2016, 2024):
        m = cpi & (cal["year"] == y)
        by_year.append({"year": y, "n": int(m.sum()),
                        **stat(frame["t_oo"][m])})
    out["cpi_day_by_year"] = by_year
    print("CPI day by year", [(d["year"], round(d["mean_bp"], 1)) for d in by_year])

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (10, 1, 1.0, False, "proxy neighbour"),
        (11, 1, 1.0, False, "proxy neighbour"),
        (12, 1, 1.0, False, "centre"),
        (13, 1, 1.0, False, "proxy neighbour"),
        (12, 2, 1.0, False, "window neighbour"),
        (12, 1, 1.0, True, "CPI+NFP control"),
        (12, 1, 1.0, False, "NFP-only control"),
        (12, 1, 0.5, False, "exposure neighbour"),
    ]
    grid = []
    for cpi_day, window, weight, inc_nfp, role in grid_spec:
        if role == "NFP-only control":
            # special case: NFP only is not expressible with the CPI builder
            cpi_f, nfp_f = event_days(cal)
            flag = window_flag(nfp_f, window)
            target = flag.astype(float) * weight
            wt = weights_from_target(ts, cal["first"], cal["last"], nd,
                                     target, idle_bil=True)
            event = "nfp_only"
        else:
            wt = build_weights_params(ts, o, c, cpi_day=cpi_day, window=window,
                                      weight=weight, include_nfp=inc_nfp)
            event = "cpi_plus_nfp" if inc_nfp else "cpi_only"
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        grid.append({"cpi_day": cpi_day, "window": window, "weight": weight,
                     "include_nfp": inc_nfp, "event": event, "role": role,
                     **pack(s), "ten_bp": pack(s10)})
        print(f"grid cpi={cpi_day} win={window} w={weight:.2f} nfp={inc_nfp} "
              f"{role:20s} 1bp CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}  "
              f"10bp CAGR {s10['cagr']*100:6.2f}%")
    out["grid"] = grid

    # ---- controls -----------------------------------------------------------
    controls = {}
    wt = build_weights_params(ts, o, c, cpi_day=12, window=1, weight=1.0,
                              include_nfp=False, idle_bil=False)
    _, s = run_weights(ts, o, c, wt)
    controls["centre_cash_idle"] = pack(s)
    print(f"control centre cash idle   CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    # pre-release de-risk: the rejected alternative, disclosed
    cpi_f, nfp_f = event_days(cal)
    ev_f = cpi_f | nfp_f
    pre = np.r_[False, ev_f[:-1]]
    target = (~pre).astype(float)
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["pre_release_derisk_100_except_pre"] = pack(s)
    print(f"control pre-release de-risk CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    # NFP day + next
    flag = window_flag(nfp_f, 2)
    target = flag.astype(float)
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["nfp_day_plus_next"] = pack(s)
    print(f"control NFP day+next       CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    # CPI day + next
    flag = window_flag(cpi_f, 2)
    target = flag.astype(float)
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["cpi_day_plus_next"] = pack(s)
    print(f"control CPI day+next       CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    out["controls"] = controls

    # ---- placebo ------------------------------------------------------------
    n_event = int(cpi.sum())
    real_daily = daily_cagr(cpi.astype(float), frame, idle_bil=True)
    rng = np.random.default_rng(20261127)
    draws = []
    base = np.zeros(nd)
    for _ in range(1000):
        mask = rng.choice(nd, n_event, replace=False)
        f = base.copy()
        f[mask] = 1.0
        draws.append(daily_cagr(f, frame, idle_bil=True))
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": int(len(draws)), "marks": "1D open-to-open",
        "n_event_days": n_event,
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
    cpi_row = [x for x in rows if x["event"] == "cpi_day12"][0]
    nfp_row = [x for x in rows if x["event"] == "nfp_first_friday"][0]
    c1 = dev10["cagr"] <= BAR["cagr"]
    c2 = cpi_row["day_tqqq_oo"]["mean_bp"] <= 0 or cpi_row["day_tqqq_oo"]["t"] < 1.5
    c3 = not (cpi_row["day_tqqq_oo"]["mean_bp"] > nfp_row["day_tqqq_oo"]["mean_bp"]
              and s1["cagr"] > [g for g in grid if g["role"] == "NFP-only control"][0]["cagr"])
    c4 = out["placebo"]["p_value"] > 0.10
    yr = out["yearly"]
    log_total = sum(np.log1p(v["strategy"]) for v in yr.values())
    log_2023 = np.log1p(yr["2023"]["strategy"])
    c5 = log_2023 / log_total > 0.50 if log_total > 0 else False
    # neighbour conditional means, computed directly
    c11 = event_days(cal, cpi_day=11)[0]
    c13 = event_days(cal, cpi_day=13)[0]
    c6 = (stat(frame["t_oo"][c11])["mean_bp"] <= 0
          and stat(frame["t_oo"][c13])["mean_bp"] <= 0)
    kills = {
        "c1_10bp_cagr_below_bar": bool(c1),
        "c2_cpi_day_mean_or_t_fails": bool(c2),
        "c3_cpi_not_better_than_nfp": bool(c3),
        "c4_placebo_p_above_0.10": bool(c4),
        "c5_2023_share_above_half": bool(c5),
        "c6_proxy_spike": bool(c6),
    }
    out["kill_criteria"] = kills
    out["verdict"] = "negative" if any(kills.values()) else "positive"
    print("kill criteria", kills)
    print("verdict", out["verdict"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
