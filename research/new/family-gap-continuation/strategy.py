"""Gap-continuation TQQQ: a large gap confirmed in the first 30 minutes.

Standalone development-window strategy (2016-01-04 .. 2023-12-29).

Hypothesis
----------
A large opening gap is information, not automatically an overreaction.  When
the first 30 minutes trade in the gap direction, the move continues through
the session.  This family tests *continuation*, not the gap fade.

Rules
-----
Signal, measured on QQQ at the close of the 10:00 bar (offset 30):

    gap_k  = QQQ_open(09:30) / QQQ_close(previous 15:59) - 1
    r30_k  = QQQ_close(10:00) / QQQ_open(09:30) - 1

    gap_k >= 0.50%  and  r30_k >= 0.20%   -> long TQQQ

Execution: enter at the 10:01 open (the bar after the 10:00 signal close),
exit at the 15:59 open (target zero at the 15:58 close).  Long-only, weight
1.0, cash otherwise.  No overnight position in the primary rule.

No trend gate, no volatility targeting, no drawdown event, no ML, no
relative-strength input.  The gap and the first-30-minute confirmation are the
only signals.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-gap-continuation/strategy.py
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
BPY = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2
N_BARS = 390

# Pre-registered centre.
GAP_TH = 0.0050      # 0.50% QQQ gap = about 1.5% TQQQ
R30_TH = 0.0020      # first 30 minutes up at least 0.20%
ENTRY_OFF = 30       # 10:00 close decides; fill at 10:01
EXIT_OFF = 389       # 15:59 open

WINNERS = (
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
)


# --------------------------------------------------------------------------- #
# data / signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def session_features(ts, o, c, sig_col: int = CQ):
    """Gap and first-30-minute return for every full session."""
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    gap = np.full(n, np.nan)
    r30 = np.full(n, np.nan)
    full = np.zeros(n, dtype=bool)
    prev_close = None
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        if l - f == N_BARS - 1:
            full[k] = True
            r30[k] = c[f + ENTRY_OFF, sig_col] / o[f, sig_col] - 1.0
            if prev_close is not None:
                gap[k] = o[f, sig_col] / prev_close - 1.0
        prev_close = float(c[l, sig_col])
    return gap, r30, full


def build_flags(gap, r30, full, gap_th: float = GAP_TH, r30_th: float = R30_TH):
    return (full & np.isfinite(gap) & np.isfinite(r30)
            & (gap >= gap_th) & (r30 >= r30_th))


def build_weights(ts, o, c, gap_th: float = GAP_TH, r30_th: float = R30_TH,
                  entry_off: int = ENTRY_OFF, exit_off: int = EXIT_OFF,
                  sig_col: int = CQ, trade_col: int = CT, size: float = 1.0,
                  flags_override=None, entry_random: np.ndarray | None = None,
                  return_diag: bool = False):
    """Return the (n, 3) weight matrix.

    `weights[i]` is the target after bar i's close; it fills at bar i+1's
    open.  With entry_off=30 and exit_off=389 the position runs from the
    10:01 open to the 15:59 open.
    """
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    if flags_override is None:
        gap, r30, full = session_features(ts, o, c, sig_col)
        flags = build_flags(gap, r30, full, gap_th, r30_th)
    else:
        flags = np.asarray(flags_override, dtype=bool)
    w = np.zeros((len(ts), 3))
    for k in range(n):
        if not flags[k]:
            continue
        f, l = int(first[k]), int(last[k])
        if l - f != N_BARS - 1:
            continue
        en = f + entry_off if entry_random is None else f + int(entry_random[k])
        en = min(max(en, f + 1), f + N_BARS - 2)
        if exit_off < N_BARS:
            ex = f + exit_off
            w[en:ex - 1, trade_col] = size
            w[ex - 1, trade_col] = 0.0
        else:
            # Hold through the 15:59 close and exit at the next 09:31 open.
            w[en:f + N_BARS, trade_col] = size
            if k + 1 < n:
                w[int(first[k + 1]), trade_col] = 0.0
    w[-1] = w[-2]
    assert w.min() >= -1e-12 and w.max() <= 1.0 + 1e-12
    assert w.sum(axis=1).max() <= 1.0 + 1e-9
    if return_diag:
        return w, flags
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
    return r, bt.stats(r, BPY)


def daily_equity(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=pd.to_datetime(res["ts"]))
    out = s.groupby(s.index.date).last()
    out.index = pd.to_datetime(out.index)
    return out


def daily_close_returns(ts, close) -> pd.Series:
    s = pd.Series(close, index=pd.to_datetime(ts))
    out = s.groupby(s.index.date).last()
    out.index = pd.to_datetime(out.index)
    return out.pct_change().dropna()


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
            "max_drawdown": float(-(x / peak - 1).min())}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(equity, index=pd.to_datetime(ts))
    d = s.groupby(s.index.date).last()
    d.index = pd.to_datetime(d.index)
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def event_stats(ts, o, c, flags, trade_col=CT, entry_off=ENTRY_OFF,
                exit_off=EXIT_OFF):
    dates, first, last = bt.day_bounds(ts)
    rets = []
    for k in np.flatnonzero(flags):
        f = int(first[k])
        if int(last[k]) - f != N_BARS - 1:
            continue
        rets.append(o[f + exit_off, trade_col] / o[f + entry_off + 1, trade_col] - 1.0)
    r = np.array(rets)
    return {
        "n_events": int(len(r)),
        "events_per_year": float(len(r) / 7.98),
        "mean_bp": float(1e4 * r.mean()) if len(r) else None,
        "median_bp": float(1e4 * np.median(r)) if len(r) else None,
        "win_rate": float((r > 0).mean()) if len(r) else None,
        "t_stat": float(r.mean() / r.std() * np.sqrt(len(r))) if len(r) > 1 else None,
        "worst_bp": float(1e4 * r.min()) if len(r) else None,
        "best_bp": float(1e4 * r.max()) if len(r) else None,
        "total_log": float(np.log1p(r).sum()) if len(r) else None,
    }


def correlation_table(daily_ret: pd.Series) -> dict:
    out = {}
    for slug in WINNERS:
        path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        ser = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        ser = ser[ser.index <= pd.Timestamp(DEV_END)]
        j = pd.concat([daily_ret, ser.pct_change()], axis=1, join="inner").dropna()
        out[slug] = {"corr": float(j.iloc[:, 0].corr(j.iloc[:, 1])),
                     "n_days": int(len(j))}
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    print(f"panel {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    w, flags = build_weights(ts, o, c, return_diag=True)
    wraw = np.zeros((len(ts), 3))
    wraw[:, CT] = 1.0

    out = {
        "strategy": "gap-continuation-tqqq",
        "directory": "research/new/family-gap-continuation",
        "window": {
            "start": DEV_START, "end": DEV_END, "marks": "1min",
            "fills": "next-minute open, 2% band", "idle": "cash (0%)",
            "holdout": "not loaded; panel sliced at 2023-12-29",
        },
        "data_provenance": {
            "panel": "research/bt.py bt.panel(('QQQ','TQQQ','BIL'), dev window, '1min')",
            "extra": "none; gap and r30 come from the shared panel",
            "no_2024": "the returned panel ends 2023-12-29 15:59 ET; no 2024 bar is used",
        },
        "rules": {
            "signal": "QQQ gap >= 0.50% and QQQ 09:30-10:00 return >= 0.20%",
            "entry": "10:01 open (decision at the 10:00 close)",
            "exit": "15:59 open (target zero at the 15:58 close)",
            "instrument": "TQQQ, weight 1.0",
            "no": "trend gate, volatility target, drawdown event, ML, relative strength",
        },
        "event_stats": event_stats(ts, o, c, flags),
        "dev": {},
    }

    results = {}
    for slip in (0.0, 1.0, 2.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        key = "gross_0bp" if slip == 0.0 else f"{int(slip)}bp"
        out["dev"][key] = pack(s)
        print(f"centre {slip:4.1f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  Sortino {s['sortino']:4.2f}  vol {s['volatility']*100:5.1f}%  "
              f"expo {s['exposure']*100:5.2f}%  fills {s['fills']:,}  turnover {s['turnover']:.0f}")

    res1, s1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, CT], ts[i0:], BPY)
    out["benchmark_tqqq_sim"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq_brief"] = {"cagr": 0.3672, "max_drawdown": 0.8229,
                                   "sharpe": 0.82,
                                   "note": "brief's official dev bar, daily-close marks"}

    # Exposure: bar-time and clock-time.
    held_minutes = EXIT_OFF - (ENTRY_OFF + 1)   # 10:01..15:58
    n_events = int(flags.sum())
    out["exposure"] = {
        "bar_time_mean_weight": float(np.mean(w[:, CT])),
        "bar_time_held_fraction": float(np.mean(w[:, CT] > 0)),
        "clock_time_held_frac": float(n_events * held_minutes / (len(flags) * 1440.0)),
        "held_minutes_per_event": int(held_minutes),
        "n_events": n_events,
        "events_per_year": float(n_events / 7.98),
        "mean_size": 1.0,
    }

    out["corr_daily_tqqq"] = float(
        daily_equity(res1).pct_change().corr(daily_close_returns(ts, c[:, CT])))
    out["correlations"] = correlation_table(daily_equity(res1).pct_change())

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, CT]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_specs = []
    for gth in (0.0030, 0.0050, 0.0075, 0.0100):
        for rth in (0.0, 0.0020):
            grid_specs.append((gth, rth))
    grid = []
    for gth, rth in grid_specs:
        wt = build_weights(ts, o, c, gap_th=gth, r30_th=rth)
        row = {"cell": f"gap {gth*100:.2f}% / r30 {rth*100:.2f}%",
               "gap_th": gth, "r30_th": rth,
               "centre": bool(abs(gth - GAP_TH) < 1e-12 and abs(rth - R30_TH) < 1e-12)}
        for slip in (1.0, 5.0):
            _, ss = run_weights(ts, o, c, wt, slip=slip)
            row[f"{int(slip)}bp"] = pack(ss)
        grid.append(row)
        print(f"grid {row['cell']:34s} 1bp {row['1bp']['cagr']*100:6.2f}% / "
              f"{row['1bp']['max_drawdown']*100:5.2f}%  Sh {row['1bp']['sharpe']:.2f}  "
              f"5bp {row['5bp']['cagr']*100:6.2f}%  fills {row['1bp']['fills']:,}")
    out["grid"] = grid

    # ---- neighbours ---------------------------------------------------------
    neigh = []

    def add_neigh(name, **kw):
        wt = build_weights(ts, o, c, **kw)
        _, ss = run_weights(ts, o, c, wt, slip=1.0)
        _, s5 = run_weights(ts, o, c, wt, slip=5.0)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        neigh.append({"name": name, **pack(ss),
                      "5bp_cagr": float(s5["cagr"]), "5bp_dd": float(s5["max_drawdown"]),
                      "10bp_cagr": float(s10["cagr"])})
        print(f"neigh {name:30s} 1bp {ss['cagr']*100:6.2f}% / {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}%")

    add_neigh("gap 0.40%", gap_th=0.0040)
    add_neigh("gap 0.60%", gap_th=0.0060)
    add_neigh("r30 0.10%", r30_th=0.0010)
    add_neigh("r30 0.30%", r30_th=0.0030)
    add_neigh("r30 0.50%", r30_th=0.0050)
    add_neigh("entry 10:16", entry_off=45)
    add_neigh("entry 10:31", entry_off=60)
    add_neigh("entry 11:01", entry_off=90)
    add_neigh("exit 15:30", exit_off=360)
    add_neigh("exit 15:45", exit_off=375)
    add_neigh("next-open exit", exit_off=390)
    add_neigh("size 0.50", size=0.5)
    add_neigh("QQQ trade", trade_col=CQ)
    add_neigh("TQQQ signal 1.5%/0.5%", sig_col=CT, gap_th=0.015, r30_th=0.005)
    out["neighbours"] = neigh

    # ---- controls -----------------------------------------------------------
    controls = {}

    def add_control(name, wt):
        _, ss = run_weights(ts, o, c, wt)
        controls[name] = pack(ss)
        print(f"control {name:28s} CAGR {ss['cagr']*100:6.2f}%  DD {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}")

    add_control("buy_hold_tqqq_sim", wraw)
    # gap only, no confirmation
    wg = build_weights(ts, o, c, r30_th=-1.0)
    add_control("gap_only_no_confirmation", wg)
    # confirmation only, no gap
    wr = build_weights(ts, o, c, gap_th=-1.0)
    add_control("confirmation_only_no_gap", wr)
    # gap but confirmation in the opposite direction (fade)
    gap, r30, full = session_features(ts, o, c, CQ)
    fade_flags = full & np.isfinite(gap) & np.isfinite(r30) & (gap >= GAP_TH) & (r30 < 0)
    add_control("gap_up_r30_down_fade", build_weights(ts, o, c, flags_override=fade_flags))
    # QQQ execution
    add_control("qqq_execution", build_weights(ts, o, c, trade_col=CQ))
    out["controls"] = controls

    # ---- placebos -----------------------------------------------------------
    rng = np.random.default_rng(20261127)
    dates, first, last = bt.day_bounds(ts)
    full_idx = np.flatnonzero(np.array([int(last[k]) - int(first[k]) == N_BARS - 1
                                        for k in range(len(first))]))
    real_cagr = float(s1["cagr"])
    real_dd = float(s1["max_drawdown"])
    n_sig = int(flags.sum())
    NPL = 200

    cagrs = np.empty(NPL); dds = np.empty(NPL)
    for j in range(NPL):
        pick = rng.choice(full_idx, n_sig, replace=False)
        m = np.zeros(len(first), dtype=bool); m[pick] = True
        _, sj = run_weights(ts, o, c, build_weights(ts, o, c, flags_override=m))
        cagrs[j] = sj["cagr"]; dds[j] = sj["max_drawdown"]
    out["placebo_random_days"] = {
        "n_draws": NPL, "n_events": n_sig, "real_cagr": real_cagr, "real_dd": real_dd,
        "mean_cagr": float(cagrs.mean()), "p95_cagr": float(np.percentile(cagrs, 95)),
        "max_cagr": float(cagrs.max()), "p_value_cagr": float((cagrs >= real_cagr).mean()),
        "mean_dd": float(dds.mean()), "p05_dd": float(np.percentile(dds, 5)),
        "min_dd": float(dds.min()), "dd_percentile": float((dds >= real_dd).mean()),
    }
    print("placebo random days", {k: round(float(v), 4)
                                   for k, v in out["placebo_random_days"].items()})

    cagrs2 = np.empty(NPL); dds2 = np.empty(NPL)
    for j in range(NPL):
        er = rng.integers(30, 60, len(first))   # 10:01..10:30 fill
        _, sj = run_weights(ts, o, c,
                            build_weights(ts, o, c, entry_random=er))
        cagrs2[j] = sj["cagr"]; dds2[j] = sj["max_drawdown"]
    out["placebo_random_entry"] = {
        "n_draws": NPL, "entry_window": "10:01..10:30", "real_cagr": real_cagr,
        "real_dd": real_dd,
        "mean_cagr": float(cagrs2.mean()), "p95_cagr": float(np.percentile(cagrs2, 95)),
        "max_cagr": float(cagrs2.max()), "p_value_cagr": float((cagrs2 >= real_cagr).mean()),
        "mean_dd": float(dds2.mean()), "p05_dd": float(np.percentile(dds2, 5)),
        "dd_percentile": float((dds2 >= real_dd).mean()),
    }
    print("placebo random entry", {k: round(float(v), 4)
                                    for k, v in out["placebo_random_entry"].items()
                                    if isinstance(v, (int, float, np.floating))})

    stale = np.zeros(len(first), dtype=bool)
    stale[1:] = flags[:-1]
    _, sstale = run_weights(ts, o, c, build_weights(ts, o, c, flags_override=stale))
    out["placebo_stale_signal"] = pack(sstale)
    print(f"placebo stale signal  CAGR {sstale['cagr']*100:.2f}%  "
          f"DD {sstale['max_drawdown']*100:.2f}%  Sh {sstale['sharpe']:.2f}")

    # ---- cut tests ----------------------------------------------------------
    cuts = {}
    for year in (2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, CT], year),
        }
    out["cut_tests"] = cuts
    for y, v in cuts.items():
        print(f"cut ex-{y}: strat {v['strategy']['cagr']*100:6.2f}% / "
              f"{v['strategy']['max_drawdown']*100:5.2f}%  "
              f"bench {v['benchmark_ex_year']['cagr']*100:6.2f}% / "
              f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")

    # ---- causality: truncation ---------------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    out["causality_day_boundary"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:j], w[:j])),
        "max_abs_diff": float(np.max(np.abs(w_trunc[:j] - w[:j]))),
    }
    print("causality day boundary", out["causality_day_boundary"])

    j2 = bt.start_index(ts, "2020-03-12 11:07")
    w_trunc2 = build_weights(ts[:j2], o[:j2], c[:j2])
    n_cmp2 = bt.start_index(ts, "2020-03-12")
    out["causality_intraday_cut"] = {
        "truncation_date": "2020-03-12 11:07",
        "prior_weights_unchanged": bool(np.allclose(w_trunc2[:n_cmp2], w[:n_cmp2])),
        "max_abs_diff": float(np.max(np.abs(w_trunc2[:n_cmp2] - w[:n_cmp2]))),
    }
    print("causality intraday cut", out["causality_intraday_cut"])

    # ---- kill criteria ------------------------------------------------------
    corr_max = max(v["corr"] for v in out["correlations"].values())
    n_pos_sub = sum(1 for v in out["subperiods"].values() if v and v["cagr"] > 0)
    out["kill_criteria"] = [
        {"criterion": "dev CAGR at 1 bp below the 36.72% TQQQ bar",
         "value": float(s1["cagr"]), "threshold": 0.3672,
         "failed": bool(s1["cagr"] < 0.3672)},
        {"criterion": "5 bp CAGR below 0",
         "value": float(results[5.0][1]["cagr"]), "threshold": 0.0,
         "failed": bool(results[5.0][1]["cagr"] < 0.0)},
        {"criterion": "fewer than 30 independent events",
         "value": int(n_events), "threshold": 30,
         "failed": bool(n_events < 30)},
        {"criterion": "fewer than 100 fills",
         "value": int(s1["fills"]), "threshold": 100,
         "failed": bool(s1["fills"] < 100)},
        {"criterion": "fewer than 6 of 8 grid cells positive at 1 bp",
         "value": int(sum(1 for r in grid if r["1bp"]["cagr"] > 0)), "threshold": 6,
         "failed": bool(sum(1 for r in grid if r["1bp"]["cagr"] > 0) < 6)},
        {"criterion": "negative CAGR in 2 or more of 3 subperiods",
         "value": int(3 - n_pos_sub), "threshold": 2,
         "failed": bool(n_pos_sub < 2)},
        {"criterion": "placebo random-day p-value above 0.10",
         "value": float(out["placebo_random_days"]["p_value_cagr"]), "threshold": 0.10,
         "failed": bool(out["placebo_random_days"]["p_value_cagr"] > 0.10)},
        {"criterion": "daily correlation above 0.70 with an existing winner",
         "value": float(corr_max), "threshold": 0.70,
         "failed": bool(corr_max > 0.70)},
        {"criterion": "causality max weight drift above 1e-12",
         "value": float(max(out["causality_day_boundary"]["max_abs_diff"],
                            out["causality_intraday_cut"]["max_abs_diff"])),
         "threshold": 1e-12,
         "failed": bool(max(out["causality_day_boundary"]["max_abs_diff"],
                            out["causality_intraday_cut"]["max_abs_diff"]) > 1e-12)},
    ]
    out["verdict"] = {
        "headline": "positive and robust, but below the above-TQQQ CAGR bar",
        "passed": [k["criterion"] for k in out["kill_criteria"] if not k["failed"]],
        "failed": [k["criterion"] for k in out["kill_criteria"] if k["failed"]],
    }
    for k in out["kill_criteria"]:
        print(f"kill {'FAIL' if k['failed'] else 'pass'}  {k['criterion']}  value={k['value']:.6g}")

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
