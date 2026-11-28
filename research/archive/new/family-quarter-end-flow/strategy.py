"""Quarter-end rebalancing flow: 50% base, full TQQQ in the 2+2 session window.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
For each calendar quarter, the window is the last two regular sessions of
March/June/September/December plus the first two regular sessions of
January/April/July/October.  For session k:

    w_tqqq(k) = 1.00   if k is in the 2+2 quarter-end window
              = 0.50   otherwise
    w_bil(k)  = 1 - w_tqqq(k)

The window is known from the calendar at the prior close.  The target for the
first window session is set at the previous close and filled at the next open;
the exit target (0.50) is set at the last window session's close and filled at
the next open.

The delivered centre is (base_weight=0.50, window=last2+first2).  The 8-cell
pre-registered grid, including the shifted +5-session placebo, is in
HYPOTHESIS.md.  No 2024+ bar is loaded.
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
BASE_W = 0.50
WINDOW_N = 2

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
    month = sd.dt.month.to_numpy()
    year = sd.dt.year.to_numpy()
    month_id = year * 100 + month
    sim = np.zeros(nd, dtype=int)
    prev = None
    cnt = 0
    for k in range(nd):
        key = month_id[k]
        if key != prev:
            cnt = 0
            prev = key
        sim[k] = cnt
        cnt += 1
    nsm = pd.Series(sim).groupby(month_id).transform("max").to_numpy() + 1
    return {"dates": dates, "first": first, "last": last, "nd": nd,
            "month": month, "year": year, "month_id": month_id,
            "sim": sim, "nsm": nsm, "sfe": nsm - 1 - sim,
            "qend": np.isin(month, [3, 6, 9, 12]),
            "qstart": np.isin(month, [1, 4, 7, 10])}


def window_mask(cal, n=WINDOW_N):
    return ((cal["qend"] & (cal["sfe"] <= n - 1))
            | (cal["qstart"] & (cal["sim"] <= n - 1)))


def shifted_mask(mask, shift):
    out = np.zeros(len(mask), dtype=bool)
    idx = np.flatnonzero(mask)
    out[np.clip(idx + shift, 0, len(mask) - 1)] = True
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


def build_weights_params(ts, o, c, base=BASE_W, window="both", shift=0,
                         idle_bil=True):
    cal = calendar(ts)
    if window == "both":
        mask = window_mask(cal)
    elif window == "last":
        mask = cal["qend"] & (cal["sfe"] <= WINDOW_N - 1)
    elif window == "first":
        mask = cal["qstart"] & (cal["sim"] <= WINDOW_N - 1)
    elif window == "only":
        mask = window_mask(cal)
    else:
        raise ValueError(window)
    if shift:
        mask = shifted_mask(mask, shift)
    target = np.where(mask, 1.0, base)
    if window == "only":
        target = mask.astype(float)
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
    q_close = np.asarray(c)[last, COL_Q]
    t_oo = np.r_[t_open[1:] / t_open[:-1] - 1.0, 0.0]
    b_oo = np.r_[b_open[1:] / b_open[:-1] - 1.0, 0.0]
    q_oo = np.r_[q_close[1:] / q_close[:-1] - 1.0, 0.0]
    return {"cal": cal, "t_oo": t_oo, "b_oo": b_oo, "q_oo": q_oo}


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
                "win": float("nan")}
    return {"n": int(n), "mean_bp": float(np.mean(x) * 1e4),
            "t": float(np.mean(x) / (np.std(x, ddof=0) / np.sqrt(n))),
            "win": float((x > 0).mean())}


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
        "strategy": "family-quarter-end-flow",
        "directory": "research/new/family-quarter-end-flow",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "rules": {
            "clock": "calendar quarter: last 2 sessions of Mar/Jun/Sep/Dec "
                     "plus first 2 sessions of Jan/Apr/Jul/Oct",
            "base_weight": BASE_W,
            "window_weight": 1.00,
            "window_sessions": 2,
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
        "fraction_sessions_base": float((np.abs(wsess - BASE_W) < 1e-9).mean()),
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

    # ---- window diagnostics -------------------------------------------------
    win = window_mask(cal)
    diag = {"window": stat(frame["t_oo"][win]),
            "outside": stat(frame["t_oo"][~win]),
            "window_qqq": stat(frame["q_oo"][win]),
            "outside_qqq": stat(frame["q_oo"][~win])}
    for n in (1, 2, 3, 4, 5):
        last = cal["qend"] & (cal["sfe"] <= n - 1)
        first = cal["qstart"] & (cal["sim"] <= n - 1)
        diag[f"last{n}"] = stat(frame["t_oo"][last])
        diag[f"first{n}"] = stat(frame["t_oo"][first])
    for shift in (5, -5):
        m = shifted_mask(win, shift)
        diag[f"shift{shift:+d}"] = stat(frame["t_oo"][m])
    out["window_diagnostics"] = diag
    print("window diagnostics")
    for k, v in diag.items():
        print(f"  {k:10s} n={v['n']:4d} mean={v['mean_bp']:+7.1f}bp t={v['t']:+5.2f}")

    # by quarter (window vs outside)
    by_q = []
    for q in (1, 2, 3, 4):
        m = win & (cal["month"].astype(int) % 3 == q % 3)
        # quarter-end month map: Q1->Mar, Q2->Jun, Q3->Sep, Q4->Dec
        qm = {1: 3, 2: 6, 3: 9, 4: 12}[q]
        sel = win & ((cal["month"] == qm) |
                     ((cal["month"] == qm % 12 + 1) & (cal["sim"] <= 1)))
        by_q.append({"quarter": q, **stat(frame["t_oo"][sel])})
    out["window_by_quarter"] = by_q
    print("window by quarter", [(d["quarter"], round(d["mean_bp"], 1)) for d in by_q])

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (0.30, "both", 0, "base neighbour"),
        (0.50, "both", 0, "centre"),
        (0.70, "both", 0, "base neighbour"),
        (0.90, "both", 0, "base neighbour"),
        (0.50, "last", 0, "window neighbour"),
        (0.50, "first", 0, "window neighbour"),
        (0.50, "both", 5, "placebo +5 sessions"),
        (0.00, "only", 0, "window-only"),
    ]
    grid = []
    for base, mode, shift, role in grid_spec:
        wt = build_weights_params(ts, o, c, base=base, window=mode, shift=shift)
        _, s = run_weights(ts, o, c, wt)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        grid.append({"base_weight": base, "window_mode": mode, "shift": shift,
                     "role": role, **pack(s), "ten_bp": pack(s10)})
        print(f"grid base={base:.2f} win={mode:5s} shift={shift:+d} {role:20s} "
              f"1bp CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:.2f}  10bp CAGR {s10['cagr']*100:6.2f}%")
    out["grid"] = grid

    # ---- controls -----------------------------------------------------------
    controls = {}
    wt = weights_from_target(ts, cal["first"], cal["last"], nd,
                             np.ones(nd), idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["tqqq_buy_hold"] = pack(s)
    print(f"control TQQQ               CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    mean_w = float(wbar.mean())
    wt = weights_from_target(ts, cal["first"], cal["last"], nd,
                             np.full(nd, mean_w), idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": mean_w}
    print(f"control constant {mean_w:.3f}    CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    wt = build_weights_params(ts, o, c, base=0.5, window="both", shift=-5)
    _, s = run_weights(ts, o, c, wt)
    controls["window_shift_minus5"] = pack(s)
    print(f"control shift -5 sessions  CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    # rejected negative-flow direction: de-risk the last 2 sessions
    target = np.where(cal["qend"] & (cal["sfe"] <= 1), 0.0, 1.0)
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["derisk_last2_sessions"] = pack(s)
    print(f"control de-risk last2      CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")

    # conditional alternative: de-risk first 2 after an up quarter

    def prev_month_id(mid, back):
        y, m = divmod(mid, 100)
        m -= back
        while m <= 0:
            m += 12
            y -= 1
        return y * 100 + m

    target = np.ones(nd)
    for k in range(1, nd):
        if cal["sim"][k] <= 1 and cal["qstart"][k]:
            # prior quarter = the three month blocks before this quarter
            prior = [prev_month_id(cal["month_id"][k], j) for j in (3, 2, 1)]
            m = np.isin(cal["month_id"], prior)
            if m.any() and frame["q_oo"][m].sum() > 0:
                target[k] = 0.0
    wt = weights_from_target(ts, cal["first"], cal["last"], nd, target,
                             idle_bil=True)
    _, s = run_weights(ts, o, c, wt)
    controls["derisk_first2_after_up_quarter"] = pack(s)
    print(f"control conditional upQ    CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}")
    out["controls"] = controls

    # ---- placebos -----------------------------------------------------------
    real_daily = daily_cagr(np.where(win, 1.0, BASE_W), frame, idle_bil=True)
    out["placebo_shifted"] = {
        "real_daily_cagr": float(real_daily),
        "plus5_daily_cagr": float(daily_cagr(
            np.where(shifted_mask(win, 5), 1.0, BASE_W), frame, idle_bil=True)),
        "minus5_daily_cagr": float(daily_cagr(
            np.where(shifted_mask(win, -5), 1.0, BASE_W), frame, idle_bil=True)),
    }
    print("shifted placebo", out["placebo_shifted"])

    # random 4-session windows, same number of windows
    n_windows = int(np.sum(cal["qend"] & (cal["sfe"] == 1)))
    rng = np.random.default_rng(20261127)
    draws = []
    for _ in range(1000):
        mask = np.zeros(nd, dtype=bool)
        starts = rng.choice(max(nd - 4, 1), n_windows, replace=False)
        for st in starts:
            mask[st:st + 4] = True
        draws.append(daily_cagr(np.where(mask, 1.0, BASE_W), frame,
                                idle_bil=True))
    draws = np.array(draws)
    out["placebo"] = {
        "n_draws": int(len(draws)), "marks": "1D open-to-open",
        "n_windows": n_windows,
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
    c1 = dev10["cagr"] <= BAR["cagr"]
    shift_cell = [g for g in grid if g["role"] == "placebo +5 sessions"][0]
    c2 = shift_cell["cagr"] > s1["cagr"]
    window_only = [g for g in grid if g["role"] == "window-only"][0]
    c3 = window_only["cagr"] < 0.05
    c4 = diag["window"]["t"] < 1.0
    const = controls["constant_exposure_same_mean"]
    c5 = s1["cagr"] <= const["cagr"]
    # c6: remove the best quarter and compare with the same daily constant model
    q_best = max(by_q, key=lambda d: d["mean_bp"])
    qm = {1: 3, 2: 6, 3: 9, 4: 12}[q_best["quarter"]]
    drop = win & ((cal["month"] == qm) |
                  ((cal["month"] == qm % 12 + 1) & (cal["sim"] <= 1)))
    f_drop = np.where(drop, 0.0, np.where(win, 1.0, BASE_W))
    const_daily = daily_cagr(np.full(nd, mean_w), frame, idle_bil=True)
    c6 = daily_cagr(f_drop, frame, idle_bil=True) < const_daily
    kills = {
        "c1_10bp_cagr_below_bar": bool(c1),
        "c2_shifted_placebo_beats_real": bool(c2),
        "c3_window_only_below_5pct": bool(c3),
        "c4_window_mean_t_below_1": bool(c4),
        "c5_below_constant_exposure": bool(c5),
        "c6_drop_best_quarter_below_constant": bool(c6),
    }
    out["kill_criteria"] = kills
    out["verdict"] = "negative" if any(kills.values()) else "positive"
    print("kill criteria", kills)
    print("verdict", out["verdict"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
