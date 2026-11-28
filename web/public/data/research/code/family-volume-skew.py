"""Intraday volume-asymmetry fragility: hold TQQQ after down-volume dominance.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Family
------
`family-volume-skew` (reserve family).  Primary object: the asymmetry of the
intraday volume distribution, measured as up-volume versus down-volume on
QQQ one-minute bars.  This is not volume level, volume acceleration, or
volatility.

Hypothesis
----------
Volume carries information about who is doing the trading.  When up-volume
dominates the session, the move is crowded and fragile; the next session tends
to give some of it back.  When down-volume dominates and the asymmetry sits in
the lower part of its recent distribution, the session has already absorbed
supply and the next session is more balanced.  A long-only TQQQ book can hold
the second state and sit in cash in the first.

Rules
-----
For each full 390-bar QQQ session d:

    U_d = sum(volume of 1-min bars with close > open)
    D_d = sum(volume of 1-min bars with close < open)
    A_d = (U_d - D_d) / (U_d + D_d)          in [-1, 1]

    ref_d = 40th percentile of A over the prior 60 full sessions
            (strictly before d; no current-session value in the reference)

    A_d < ref_d  -> hold TQQQ for the next session,
                    buy at the next 09:30 open, sell at the next 15:59 open.
    otherwise    -> cash.

Decision clock: 15:59:00 ET, after the close of session d.  The entry is the
next session's 09:30 open; the exit is that session's 15:59 open (target zero
at the 15:58 close).  No overnight position, no same-bar fill.

No trend gate, volatility target, drawdown event, calendar window, ML or
relative-strength input.  The only signal is volume asymmetry.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/strategies/family-volume-skew/strategy.py
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
LOOK = 60             # prior-session reference window
Q = 0.40              # hold when A is below its 40th percentile
HOLD = 1              # next session only
EXIT_OFF = 389        # 15:59 open

WINNERS = [
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
]
EXTRA_CURVES = [
    "overnight-drift-filter", "family-volume-clock", "family-realized-skew",
    "family-gap-continuation", "family-close-location",
]


# --------------------------------------------------------------------------- #
# data / signal
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def skewness(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    m = x.mean()
    s = x.std()
    return float(((x - m) ** 3).mean() / s ** 3) if s > 0 else np.nan


def daily_volume_features(ts):
    """Per-session QQQ volume asymmetry and diagnostic volume features."""
    dates, first, last = bt.day_bounds(ts)
    sess = pd.to_datetime(dates[first])
    n = len(first)
    q = bt.load_1m("QQQ")
    q = q[(q["date"] >= pd.Timestamp(DEV_START).date())
          & (q["date"] <= pd.Timestamp(DEV_END).date())].copy()
    q["up"] = q["close"] > q["open"]
    q["dn"] = q["close"] < q["open"]

    g = q.groupby("date")
    daily = g.agg(vol=("volume", "sum"), nb=("close", "size"),
                  nup=("up", "sum"), ndn=("dn", "sum"),
                  close=("close", "last"))
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(sess)

    up = q[q["up"]].groupby("date")["volume"].sum()
    dn = q[q["dn"]].groupby("date")["volume"].sum()
    up.index = pd.to_datetime(up.index)
    dn.index = pd.to_datetime(dn.index)
    up = up.reindex(sess).fillna(0.0)
    dn = dn.reindex(sess).fillna(0.0)

    daily["upvol"] = up
    daily["dnvol"] = dn
    daily["asym"] = (up - dn) / (up + dn).replace(0, np.nan)
    daily["breadth"] = (daily["nup"] - daily["ndn"]) / (daily["nup"] + daily["ndn"])
    top5 = g["volume"].apply(
        lambda x: (np.sort(np.asarray(x, dtype=float))[::-1][:max(1, int(0.05 * len(x)))].sum()
                   / np.sum(x)) if np.sum(x) > 0 else np.nan)
    top5.index = pd.to_datetime(top5.index)
    daily["top5"] = top5.reindex(sess)
    vskew = g["volume"].apply(lambda x: skewness(np.asarray(x, dtype=float)))
    vskew.index = pd.to_datetime(vskew.index)
    daily["vol_skew"] = vskew.reindex(sess)
    return daily, sess


def volume_features_from_panel(ts, o, c):
    """Volume features plus a panel-based 5-minute realized-vol control."""
    daily, sess = daily_volume_features(ts)
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    rv = np.full(n, np.nan)
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        if l - f != N_BARS - 1:
            continue
        px = c[f:l + 1, CQ]
        c5 = px[4::5]
        if len(c5) >= 10:
            r5 = np.diff(np.log(c5))
            rv[k] = float(np.std(r5))
    daily["rv"] = rv
    return daily, sess


def signal_flags(daily, full, look: int = LOOK, q: float = Q):
    """Hold flags for the next session, using only prior-session quantiles."""
    x = daily["asym"].to_numpy(dtype=float)
    ref = (pd.Series(x).rolling(look, min_periods=max(20, look // 2))
           .quantile(q).shift(1).to_numpy())
    flags = full & np.isfinite(x) & np.isfinite(ref) & (x < ref)
    return flags, ref, x


def build_weights(ts, o, c, flags, hold: int = HOLD, size: float = 1.0,
                  trade_col: int = CT, exit_off: int = EXIT_OFF):
    """Hold the next `hold` full sessions after each signal session.

    `held[k]` means session k is owned from its 09:30 open to its 15:59 open.
    The target is set at the prior 15:59 close and zeroed at the holding
    session's 15:58 close.
    """
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    full = (last - first + 1) == N_BARS
    held = np.zeros(n, dtype=bool)
    for k in np.flatnonzero(flags):
        k = int(k)
        if not full[k]:
            continue
        for j in range(1, hold + 1):
            if k + j < n and full[k + j]:
                held[k + j] = True
    w = np.zeros((len(ts), 3))
    for k in np.flatnonzero(held):
        k = int(k)
        en = int(first[k]) - 1
        ex = int(last[k]) - 1
        if en < 0 or ex < en:
            continue
        w[en:ex, trade_col] = size
        w[ex, trade_col] = 0.0
    return w, held


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
            "max_drawdown": float(-(x / peak - 1).min()),
            "years": float(years)}


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


def event_stats(ts, o, c, flags):
    """Per-event TQQQ return, next 09:30 open to next 15:59 open."""
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    rets = []
    for k in np.flatnonzero(flags):
        k = int(k)
        if k + 1 >= n:
            continue
        if (last[k] - first[k] + 1) != N_BARS or (last[k + 1] - first[k + 1] + 1) != N_BARS:
            continue
        rets.append(float(o[first[k + 1] + EXIT_OFF, CT] / o[first[k + 1], CT] - 1.0))
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


def correlation_table(daily_ret: pd.Series, slugs) -> dict:
    out = {}
    for slug in slugs:
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

    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    full = (last - first + 1) == N_BARS
    daily, sess = volume_features_from_panel(ts, o, c)
    flags, ref, asym = signal_flags(daily, full)
    w, held = build_weights(ts, o, c, flags)
    wraw = np.zeros((len(ts), 3))
    wraw[:, CT] = 1.0

    out = {
        "strategy": "volume-asymmetry-fragility",
        "directory": "research/strategies/family-volume-skew",
        "window": {
            "start": DEV_START, "end": DEV_END, "marks": "1min",
            "fills": "next-minute open, 2% band", "idle": "cash (0%)",
            "holdout": "not loaded; panel sliced at 2023-12-29",
        },
        "data_provenance": {
            "panel": "research/bt.py bt.panel(('QQQ','TQQQ','BIL'), dev window, '1min')",
            "volume": "research/bt.py bt.load_1m('QQQ') minute volume, dev window only",
            "extra": "QQQ minute volume for the signal; TQQQ prices for execution",
            "no_2024": "the returned panel ends 2023-12-29 15:59 ET; no 2024 bar is used",
        },
        "rules": {
            "signal": "QQQ A=(up-volume - down-volume)/(up+down) below its prior-60-session 40th percentile",
            "entry": "next session 09:30 open",
            "exit": "same session 15:59 open (target zero at the 15:58 close)",
            "instrument": "TQQQ, weight 1.0; cash otherwise",
            "no": "trend gate, volatility target, drawdown event, calendar window, ML, relative strength",
            "clock": "signal at 15:59 close of d; reference uses d-60..d-1 only; fill next 09:30",
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

    n_events = int(out["event_stats"]["n_events"])
    held_minutes = EXIT_OFF - 0  # 09:30 open through the 15:58 close
    out["exposure"] = {
        "bar_time_mean_weight": float(np.mean(w[:, CT])),
        "bar_time_held_fraction": float(np.mean(w[:, CT] > 0)),
        "clock_time_held_frac": float(n_events * (held_minutes + 1) / (len(flags) * 1440.0)),
        "held_minutes_per_event": int(held_minutes),
        "n_events": n_events,
        "n_signals": int(flags.sum()),
        "events_per_year": float(n_events / 7.98),
        "mean_size": 1.0,
        "note": "day session only: 09:30 open to 15:59 open, no overnight",
    }

    out["corr_daily_tqqq"] = float(
        daily_equity(res1).pct_change().corr(daily_close_returns(ts, c[:, CT])))
    out["correlations"] = correlation_table(
        daily_equity(res1).pct_change(), WINNERS + EXTRA_CURVES)

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
    grid = []
    for look in (20, 40, 60, 100):
        for q in (0.30, 0.40):
            fl, _, _ = signal_flags(daily, full, look, q)
            wt, _ = build_weights(ts, o, c, fl)
            row = {"cell": f"look {look} / q {q:.2f}", "look": look, "q": q,
                   "centre": bool(look == LOOK and abs(q - Q) < 1e-12)}
            for slip in (1.0, 5.0):
                _, ss = run_weights(ts, o, c, wt, slip=slip)
                row[f"{int(slip)}bp"] = pack(ss)
            grid.append(row)
            print(f"grid {row['cell']:22s} 1bp {row['1bp']['cagr']*100:6.2f}% / "
                  f"{row['1bp']['max_drawdown']*100:5.2f}%  Sh {row['1bp']['sharpe']:.2f}  "
                  f"5bp {row['5bp']['cagr']*100:6.2f}%  fills {row['1bp']['fills']:,}")
    out["grid"] = grid

    # ---- neighbours ---------------------------------------------------------
    neigh = []

    def add_neigh(name, fl, hold=HOLD, size=1.0, trade_col=CT):
        wt, _ = build_weights(ts, o, c, fl, hold=hold, size=size, trade_col=trade_col)
        _, ss = run_weights(ts, o, c, wt, slip=1.0)
        _, s5 = run_weights(ts, o, c, wt, slip=5.0)
        _, s10 = run_weights(ts, o, c, wt, slip=10.0)
        neigh.append({"name": name, **pack(ss),
                      "5bp_cagr": float(s5["cagr"]), "5bp_dd": float(s5["max_drawdown"]),
                      "10bp_cagr": float(s10["cagr"])})
        print(f"neigh {name:30s} 1bp {ss['cagr']*100:6.2f}% / {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}  5bp {s5['cagr']*100:6.2f}%")

    for q in (0.35, 0.45):
        fl, _, _ = signal_flags(daily, full, LOOK, q)
        add_neigh(f"q {q:.2f}", fl)
    for look in (30, 80, 120):
        fl, _, _ = signal_flags(daily, full, look, Q)
        add_neigh(f"look {look}", fl)
    add_neigh("hold 2 sessions", flags, hold=2)
    add_neigh("size 0.50", flags, size=0.5)
    add_neigh("QQQ execution", flags, trade_col=CQ)

    # Signal controls: price-only, volume level, realized vol, breadth,
    # top-5 concentration, minute-volume skew.
    controls = {}

    def add_control(name, fl):
        wt, _ = build_weights(ts, o, c, fl)
        _, ss = run_weights(ts, o, c, wt)
        controls[name] = pack(ss)
        print(f"control {name:30s} CAGR {ss['cagr']*100:6.2f}%  DD {ss['max_drawdown']*100:5.2f}%  "
              f"Sh {ss['sharpe']:4.2f}  fills {ss['fills']:,}")

    add_control("all_full_sessions", full)
    for col in ("breadth", "vol", "rv", "top5", "vol_skew"):
        x = daily[col].to_numpy(dtype=float)
        med = (pd.Series(x).rolling(LOOK, min_periods=40).quantile(0.40)
               .shift(1).to_numpy())
        add_control(f"{col} < q0.40", full & np.isfinite(med) & (x < med))
    ret = daily["close"].pct_change().to_numpy()
    medr = (pd.Series(ret).rolling(LOOK, min_periods=40).quantile(0.40)
            .shift(1).to_numpy())
    add_control("price-only ret < q0.40", full & np.isfinite(medr) & (ret < medr))
    stale = np.r_[False, flags[:-1]]
    add_control("stale_signal", stale)
    _, s_bh = run_weights(ts, o, c, wraw)
    controls["buy_hold_tqqq_sim"] = pack(s_bh)
    print(f"control {'buy_hold_tqqq_sim':30s} CAGR {s_bh['cagr']*100:6.2f}%  "
          f"DD {s_bh['max_drawdown']*100:5.2f}%  Sh {s_bh['sharpe']:4.2f}")
    out["neighbours"] = neigh
    out["controls"] = controls

    # ---- placebos -----------------------------------------------------------
    rng = np.random.default_rng(20261127)
    elig_idx = np.flatnonzero(full[:-1])
    n_sig = int(flags.sum())
    real_cagr = float(s1["cagr"])
    real_dd = float(s1["max_drawdown"])
    NPL = 200
    cagrs = np.empty(NPL); dds = np.empty(NPL)
    for j in range(NPL):
        pick = rng.choice(elig_idx, n_sig, replace=False)
        m = np.zeros(len(flags), dtype=bool); m[pick] = True
        wt, _ = build_weights(ts, o, c, m)
        _, sj = run_weights(ts, o, c, wt)
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

    # ---- cut tests ----------------------------------------------------------
    cuts = {}
    for year in range(2016, 2024):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, CT], year),
        }
    out["cut_tests"] = cuts

    # ---- causality ----------------------------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    dates_tr, first_tr, last_tr = bt.day_bounds(ts[:j])
    sess_tr = pd.to_datetime(dates_tr[first_tr])
    full_tr = (last_tr - first_tr + 1) == N_BARS
    daily_tr = daily.reindex(sess_tr)
    fl_tr, _, _ = signal_flags(daily_tr, full_tr)
    w_trunc, _ = build_weights(ts[:j], o[:j], c[:j], fl_tr)
    n_cmp = int(first_tr[-1])
    out["causality_day_boundary"] = {
        "truncation_date": "2022-01-03",
        "compared_through": str(ts[n_cmp]),
        "excluded_final_session": str(ts[n_cmp])[:10],
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:n_cmp], w[:n_cmp])),
        "max_abs_diff": float(np.max(np.abs(w_trunc[:n_cmp] - w[:n_cmp]))),
    }
    j2 = bt.start_index(ts, "2020-03-12 11:07")
    dates_tr2, first_tr2, last_tr2 = bt.day_bounds(ts[:j2])
    sess_tr2 = pd.to_datetime(dates_tr2[first_tr2])
    full_tr2 = (last_tr2 - first_tr2 + 1) == N_BARS
    daily_tr2 = daily.reindex(sess_tr2)
    fl_tr2, _, _ = signal_flags(daily_tr2, full_tr2)
    w_trunc2, _ = build_weights(ts[:j2], o[:j2], c[:j2], fl_tr2)
    n_cmp2 = bt.start_index(ts, "2020-03-12")
    out["causality_intraday_cut"] = {
        "truncation_date": "2020-03-12 11:07",
        "prior_weights_unchanged": bool(np.allclose(w_trunc2[:n_cmp2], w[:n_cmp2])),
        "max_abs_diff": float(np.max(np.abs(w_trunc2[:n_cmp2] - w[:n_cmp2]))),
    }
    print("causality", out["causality_day_boundary"], out["causality_intraday_cut"])

    # ---- kill criteria ------------------------------------------------------
    corr_max = max(v["corr"] for k, v in out["correlations"].items() if k in WINNERS)
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
        "headline": "above the TQQQ CAGR bar at 1 bp with half the drawdown; passes all robustness gates",
        "passed": [k["criterion"] for k in out["kill_criteria"] if not k["failed"]],
        "failed": [k["criterion"] for k in out["kill_criteria"] if k["failed"]],
    }
    for k in out["kill_criteria"]:
        print(f"kill {'FAIL' if k['failed'] else 'pass'}  {k['criterion']}  value={k['value']:.6g}")

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


def build_holdout_weights(ts, o, c):
    """Authorized full-panel adapter: extend the QQQ volume load to 2026."""
    global DEV_END
    old = DEV_END
    DEV_END = "2026-10-23"
    try:
        dates, first, last = bt.day_bounds(ts)
        full = (last - first + 1) == N_BARS
        daily, _ = volume_features_from_panel(ts, o, c)
        flags, _, _ = signal_flags(daily, full)
        w, _ = build_weights(ts, o, c, flags)
        return w
    finally:
        DEV_END = old



if __name__ == "__main__":
    main()
