"""Autocorrelation-regime TQQQ sleeve - `family-autocorrelation-regime`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.  Pre-2016 QQQ daily closes (2015) are used only to warm up the
rolling autocorrelation.

Rules (all known at the 15:59 ET close of session d; fills at the next open):

    qret[d] = QQQ close-to-close return
    rho[d]  = lag-1 autocorrelation of qret over the last L sessions
    cont[d] = rho[d] >= theta_cont
    rev[d]  = rho[d] <= -theta_rev and qret[d] < 0
    held[d] = rev[d] or rev[d-1] or ... or rev[d-hold+1]
    target[d+1] = TQQQ 1.0 if cont[d] or held[d], else BIL 1.0

The primary is L=120, theta_cont=0.03, theta_rev=0.05, hold=3, daily clock.
Execution is research/bt.py: 1-minute marks, next-open fills, 2% band,
long-only, weights >= 0, row sum <= 1, headline 1 bp plus 5/10 bp.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-autocorrelation-regime/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BARS_PER_YEAR = 252 * 390
BAND = 0.02
OUT = Path(__file__).resolve().parent
CURVES = OUT.parent / "curves"

# Pre-registered primary.  See HYPOTHESIS.md section 3 for the 12-cell grid.
PARAMS = dict(L=120, lag=1, theta_cont=0.03, theta_rev=0.05, hold=3)

WINNERS = [
    "ratio-froth",
    "vol-scaled-crash-stop",
    "relative-value-tqqq",
    "fomc-opex-window",
    "family-session-timing",
    "family-short-reversal",
    "family-rebalance-flow",
    "family-intraday-microstructure-day",
    "family-ml-microstructure",
]

# The published development bar for TQQQ on 1-minute marks.
BAR = dict(cagr=0.3672, max_dd=0.8229, sharpe=0.82)


# ---------------------------------------------------------------------------
# data and signal
# ---------------------------------------------------------------------------
def load_panel():
    """1-minute QQQ/TQQQ/BIL panel, physically restricted to the dev window."""
    return bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=30)


def _warmup_closes(first_session: pd.Timestamp) -> np.ndarray:
    """QQQ adjusted daily closes strictly before the panel's first session.

    The local Yahoo daily file starts in 2015.  For a 2016-01-04 panel this
    supplies about 250 returns, enough for the L=250 check.  The slice is
    always < first_session, so no panel data is duplicated and no 2024+ row
    can enter: the panel itself ends in 2023.
    """
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"])
    lo = first_session - pd.Timedelta(days=600)
    d = daily[(daily["date"] >= lo) & (daily["date"] < first_session)]
    return d["adjclose"].to_numpy(dtype=float)


def daily_features(ts, c):
    """Per-session QQQ closes, returns and rolling lag-1 autocorrelation.

    Returns arrays of length nd (one per session).  `qret[0]` and the first
    autocorrelation values use only pre-panel QQQ closes; they never use a
    future session.
    """
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    qc = c[last, 0]
    warm = _warmup_closes(pd.Timestamp(dates[first[0]]))
    all_close = np.r_[warm, qc]
    all_ret = np.r_[np.nan, all_close[1:] / all_close[:-1] - 1.0]
    off = len(warm)
    qret = all_ret[off:]
    return dict(dates=dates, first=first, last=last, nd=nd, qc=qc,
                qret=qret, all_ret=all_ret, off=off)


def rolling_ac(all_ret, off, L, lag=1):
    """Rolling lag-`lag` autocorrelation, sliced to the panel sessions."""
    s = pd.Series(all_ret)
    rho = s.rolling(L).apply(
        lambda a: np.corrcoef(a[:-lag], a[lag:])[0, 1], raw=True
    ).to_numpy()
    return rho[off:]


def target_series(rho, qret, params=None):
    """Daily target: 1 = TQQQ for session d, 0 = BIL.

    `target[d]` is written at the close of d-1.  `held` is the rolling hold of
    the reversal signal; a new signal extends the hold.
    """
    p = dict(PARAMS)
    if params:
        p.update(params)
    cont = rho >= p["theta_cont"]
    rev = (rho <= -p["theta_rev"]) & (qret < 0)
    held = rev.copy()
    for k in range(1, int(p["hold"])):
        held[k:] |= rev[:-k]
    tgt = np.zeros(len(rho), dtype=float)
    tgt[1:] = (cont | held)[:-1]
    # Warmup: require a finite autocorrelation at the decision close.
    bad = ~np.isfinite(rho)
    tgt[1:][bad[:-1]] = 0.0
    return tgt, dict(cont=cont, rev=rev, held=held)


def broadcast(ts, tgt):
    """Map per-session targets to the (n,3) 1-minute weight matrix.

    Every bar of session d carries `tgt[d]`; the 15:59 bar of session d
    carries `tgt[d+1]`, so the change fills at the 09:30 open of d+1.
    """
    day_id = bt.day_ids(ts)
    _, _, last = bt.day_bounds(ts)
    w = np.zeros((len(ts), 3))
    w[:, 1] = tgt[day_id]
    w[:, 2] = 1.0 - tgt[day_id]
    w[last[:-1], 1] = tgt[1:]
    w[last[:-1], 2] = 1.0 - tgt[1:]
    return w


def build_weights(ts, opens, closes):
    """Return the (n,3) long-only weight matrix for the pre-registered primary."""
    return build_weights_p(ts, opens, closes, PARAMS)


def build_weights_p(ts, opens, closes, params=None):
    f = daily_features(ts, closes)
    p = dict(PARAMS)
    if params:
        p.update(params)
    rho = rolling_ac(f["all_ret"], f["off"], int(p["L"]), int(p["lag"]))
    tgt, _ = target_series(rho, f["qret"], p)
    return broadcast(ts, tgt)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def run_range(ts, o, c, w, lo=DEV_START, hi=DEV_END, bp=1.0):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    # `hi` is a session date: include the whole final session, not just the
    # bars before midnight.
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York")
                            + pd.Timedelta(days=1)))
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=BAND,
                       slippage_bps=bp, start_equity=bt.START_EQUITY)


def _daily_returns(res):
    eq = bt.daily_last(res["equity"], res["ts"])
    return eq, eq.pct_change().dropna()


def stats_block(ts, o, c, w, bp=1.0, lo=DEV_START, hi=DEV_END):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York")
                            + pd.Timedelta(days=1)))
    res = run_range(ts, o, c, w, lo, hi, bp)
    s = bt.stats(res, BARS_PER_YEAR)
    eqd, r = _daily_returns(res)
    out = dict(
        cagr=float(s["cagr"]),
        max_drawdown=float(s["max_drawdown"]),
        sharpe=float(s["sharpe"]),
        sortino=float(s["sortino"]),
        volatility=float(s["volatility"]),
        fills=int(s["fills"]),
        turnover=float(s["turnover"]),
        ending_equity=float(s["ending_equity"]),
        exposure=float(s["exposure"]),
        tqqq_exposure=float(np.mean(w[i:j, 1])),
        bil_exposure=float(np.mean(w[i:j, 2])),
        daily_vol=float(r.std() * np.sqrt(252)) if len(r) > 2 else None,
        daily_sharpe=float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 2 and r.std() > 0 else None,
        days=int(len(eqd)),
    )
    return out, res, eqd


def activity(tgt, info):
    p = np.asarray(tgt, dtype=int)
    entries = int(((p[1:] == 1) & (p[:-1] == 0)).sum())
    exits = int(((p[1:] == 0) & (p[:-1] == 1)).sum())
    held = int(p.sum())
    cuts = np.flatnonzero(np.diff(np.r_[0, p, 0]) != 0)
    lens = cuts[1::2] - cuts[0::2]
    cont = info["cont"]
    return dict(
        entries=entries,
        exits=exits,
        open_at_end=bool(p[-1] == 1),
        held_sessions=held,
        tqqq_exposure=float(p.mean()),
        bil_exposure=float(1.0 - p.mean()),
        avg_hold_sessions=float(held / entries) if entries else None,
        episode_median=float(np.median(lens)) if len(lens) else None,
        episode_max=int(lens.max()) if len(lens) else None,
        episode_min=int(lens.min()) if len(lens) else None,
        rev_signal_days=int(info["rev"].sum()),
        cont_days=int(cont.sum()),
        cont_regime_entries=int(((cont[1:]) & (~cont[:-1])).sum()),
        held_days=int(info["held"].sum()),
    )


def subperiod_block(ts, o, c, w):
    out = {}
    for name, lo, hi in (
        ("2016-2019", "2016-01-04", "2019-12-31"),
        ("2020-2021", "2020-01-01", "2021-12-31"),
        ("2022-2023", "2022-01-01", "2023-12-29"),
    ):
        s, _, _ = stats_block(ts, o, c, w, 1.0, lo, hi)
        out[name] = s
    return out


def yearly_table(eqd, qc, sess_dates):
    """Full-year returns from the previous year-end close."""
    series = pd.Series(np.asarray(eqd, dtype=float), index=pd.DatetimeIndex(eqd.index))
    qser = pd.Series(np.asarray(qc, dtype=float), index=pd.DatetimeIndex(sess_dates))
    out = {}
    prev_e, prev_q = None, None
    for y in range(2016, 2024):
        e = series[series.index.year == y]
        q = qser[qser.index.year == y]
        if len(e) < 2 or len(q) < 2:
            continue
        base_e = prev_e if prev_e is not None else e.iloc[0]
        base_q = prev_q if prev_q is not None else q.iloc[0]
        out[str(y)] = dict(
            strategy=float(e.iloc[-1] / base_e - 1.0),
            tqqq=float(q.iloc[-1] / base_q - 1.0),
        )
        prev_e, prev_q = e.iloc[-1], q.iloc[-1]
    return out


def drawdown_episode(ts, res):
    eq = res["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    t = int(np.argmin(dd))
    p = int(np.argmax(eq[:t + 1]))
    return dict(depth=float(-dd[t]), peak=str(pd.Timestamp(ts[p])),
                trough=str(pd.Timestamp(ts[t])),
                recovery=None if not np.any(eq[t:] >= peak[p]) else
                str(pd.Timestamp(ts[t + int(np.argmax(eq[t:] >= peak[p]))])))


# ---------------------------------------------------------------------------
# robustness blocks
# ---------------------------------------------------------------------------
def plateau_block(ts, o, c):
    """The 12 pre-registered cells plus the L=60/L=250 window checks."""
    cells = []
    grid = []
    for tc in (0.00, 0.03, 0.05):
        for tr in (0.05, 0.10, 0.15):
            grid.append((120, tc, tr, 3))
    for h in (1, 2, 5):
        grid.append((120, 0.03, 0.05, h))
    for L in (60, 250):
        grid.append((L, 0.03, 0.05, 3))
    for L, tc, tr, h in grid:
        p = dict(L=L, lag=1, theta_cont=tc, theta_rev=tr, hold=h)
        w = build_weights_p(ts, o, c, p)
        s, _, _ = stats_block(ts, o, c, w, 1.0)
        s.update(L=L, theta_cont=tc, theta_rev=tr, hold=h,
                 tqqq_exposure=float(w[:, 1].mean()),
                 bil_exposure=float(w[:, 2].mean()),
                 passes_bar=bool(s["cagr"] > BAR["cagr"] and s["max_drawdown"] < BAR["max_dd"]))
        cells.append(s)
    return cells


def _archived_dev_returns(slug):
    """Official archived curve, parsed only up to the development end.

    The curve files also contain 2024-2026 values.  The dates are parsed to
    find the development cut, then only the first `n` values are read from the
    text; the 2024+ numbers are never converted to floats or used.  The dev
    slice reproduces the published dev CAGR to within about 0.2 pp.
    """
    text = (CURVES / f"{slug}.json").read_text(encoding="utf-8")
    ds = text.index('"dates": [') + len('"dates": [')
    de = text.index("]", ds)
    dates = pd.to_datetime([x.strip().strip('"') for x in text[ds:de].split(",")])
    n = int((dates <= pd.Timestamp(DEV_END)).sum())
    vs = text.index('"values": [') + len('"values": [')
    vals = np.fromstring(text[vs:], sep=",", count=n)
    return pd.Series(vals, index=dates[:n]).pct_change()


def correlation_block(eqd, qc, dates):
    r = pd.Series(eqd).pct_change().dropna()
    tq = pd.Series(qc, index=pd.to_datetime(dates)).pct_change()
    both = pd.DataFrame({"r": r, "tq": tq}).dropna()
    out = dict(
        corr_tqqq=float(both["r"].corr(both["tq"])),
        beta_tqqq=float(np.cov(both["r"], both["tq"])[0, 1] / np.var(both["tq"])),
        winners={},
    )
    for slug in WINNERS:
        rr = _archived_dev_returns(slug)
        idx = r.index.intersection(rr.dropna().index)
        out["winners"][slug] = dict(
            corr=float(r.loc[idx].corr(rr.loc[idx])), n=int(len(idx))
        )
    vals = [v["corr"] for v in out["winners"].values()]
    out["winner_corr_min"] = float(min(vals))
    out["winner_corr_max"] = float(max(vals))
    out["winner_corr_mean"] = float(np.mean(vals))
    return out


def placebo_block(ts, o, c, tgt, rho, qret, n=100, seed=20261127):
    """Circular-shift placebo for the timing.

    Two nulls:
      * shift the target series: preserves the exact holding lengths and the
        exposure, destroys the alignment with returns;
      * shift the autocorrelation series: preserves the AC marginal
        distribution, destroys the alignment with the return sign.
    """
    rng = np.random.default_rng(seed)
    nd = len(tgt)
    true, _, _ = stats_block(ts, o, c, broadcast(ts, tgt), 1.0)
    true_cagr = true["cagr"]

    def _draw(kind):
        vals = []
        for k in rng.integers(30, nd - 30, n):
            k = int(k)
            if kind == "target":
                t = np.roll(tgt, k)
            else:
                r = np.roll(rho, k)
                t, _ = target_series(r, qret, PARAMS)
            s, _, _ = stats_block(ts, o, c, broadcast(ts, t), 1.0)
            vals.append(s["cagr"])
        vals = np.asarray(vals)
        return dict(
            n=int(len(vals)), mean=float(vals.mean()), median=float(np.median(vals)),
            p5=float(np.percentile(vals, 5)), p95=float(np.percentile(vals, 95)),
            min=float(vals.min()), max=float(vals.max()),
            true=true_cagr,
            percentile=float((vals < true_cagr).mean()),
            p_one_sided=float((np.sum(vals >= true_cagr) + 1) / (len(vals) + 1)),
        )

    return {"shift_target": _draw("target"), "shift_ac": _draw("ac")}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ts, o, c = load_panel()
    f = daily_features(ts, c)
    rho = rolling_ac(f["all_ret"], f["off"], PARAMS["L"], PARAMS["lag"])
    tgt, info = target_series(rho, f["qret"], PARAMS)
    w = broadcast(ts, tgt)

    # sanity: weights are long-only and sum to one
    assert w.min() >= 0.0 and w.sum(axis=1).max() <= 1.0 + 1e-9

    windows = {}
    results = {}
    for bp in (0.0, 1.0, 5.0, 10.0):
        s, res, eqd = stats_block(ts, o, c, w, bp)
        windows[f"{bp:g}bp"] = s
        results[bp] = (res, eqd)

    res1, eqd1 = results[1.0]
    act = activity(tgt, info)
    act["episodes"] = act["entries"]
    bench = bt.benchmark(c[f["last"], 1],
                         pd.to_datetime(f["dates"][f["last"]]), 252)

    corr = correlation_block(eqd1, f["qc"], f["dates"][f["last"]])
    yearly = yearly_table(eqd1, f["qc"], f["dates"][f["last"]])
    sub = subperiod_block(ts, o, c, w)

    # leg attribution: four explicit constructions
    legs = {}
    cont = rho >= PARAMS["theta_cont"]
    t_cont = np.zeros(len(rho), dtype=float)
    t_cont[1:] = cont[:-1]
    rev = (rho <= -PARAMS["theta_rev"]) & (f["qret"] < 0)
    held = rev.copy()
    for k in range(1, int(PARAMS["hold"])):
        held[k:] |= rev[:-k]
    t_rev = np.zeros(len(rho), dtype=float)
    t_rev[1:] = held[:-1]
    rev_ng = f["qret"] < 0
    held_ng = rev_ng.copy()
    for k in range(1, int(PARAMS["hold"])):
        held_ng[k:] |= rev_ng[:-k]
    t_ng = np.zeros(len(rho), dtype=float)
    t_ng[1:] = held_ng[:-1]
    for name, t in (("continuation_only", t_cont), ("reversal_only", t_rev),
                    ("union_primary", tgt), ("reversal_no_ac_gate", t_ng)):
        ss, _, _ = stats_block(ts, o, c, broadcast(ts, t), 1.0)
        legs[name] = dict(cagr=ss["cagr"], max_drawdown=ss["max_drawdown"],
                          sharpe=ss["sharpe"], fills=ss["fills"],
                          tqqq_exposure=float(np.mean(t)))

    plateau = plateau_block(ts, o, c)
    placebo = placebo_block(ts, o, c, tgt, rho, f["qret"], n=100)

    n_pass = sum(1 for x in plateau if x["passes_bar"])
    grid_pass = [x for x in plateau if x["hold"] == 3 and x["L"] == 120]
    reg_pass = sum(1 for x in grid_pass if x["passes_bar"])
    rev_gate_pass = {round(x["theta_rev"], 2) for x in grid_pass if x["passes_bar"]}

    result = dict(
        agent="family-autocorrelation-regime",
        family="autocorrelation regime",
        idea=("Rolling lag-1 autocorrelation of QQQ daily returns switches the "
              "sleeve between TQQQ continuation, TQQQ reversal and BIL."),
        hypothesis=("Positive QQQ return autocorrelation makes continuation "
                    "profitable; negative autocorrelation makes post-down-day "
                    "reversal profitable; near-zero autocorrelation is a BIL state."),
        universe=list(SYMS),
        window=dict(dev=[DEV_START, DEV_END], holdout="not loaded"),
        execution=dict(engine="research/bt.py", marks="1min", fills="next open",
                       band=BAND, headline_bps=1.0, also_bps=[5.0, 10.0],
                       weight_cap=1.0, long_only=True,
                       exposure_state="TQQQ 1.0 when on, BIL 1.0 otherwise"),
        params=dict(PARAMS),
        info=dict(params=PARAMS, **act),
        bars=int(len(ts)), sessions=int(f["nd"]),
        windows=windows,
        benchmarks=dict(
            tqqq_buy_hold=bench,
            bar=BAR,
        ),
        activity=act,
        leg_attribution=legs,
        plateau=plateau,
        plateau_summary=dict(
            cells=len(plateau),
            passes=n_pass,
            core_cells=len(grid_pass),
            core_passes=reg_pass,
            passing_rev_thresholds=sorted(rev_gate_pass),
        ),
        subperiods=sub,
        yearly=yearly,
        corr_tqqq=dict(corr=corr["corr_tqqq"], beta=corr["beta_tqqq"]),
        corr_winners=corr["winners"],
        corr_summary=dict(min=corr["winner_corr_min"], max=corr["winner_corr_max"],
                          mean=corr["winner_corr_mean"]),
        placebo=placebo,
        drawdown=drawdown_episode(res1["ts"], res1),
        status="dev-only",
        verdict=("Numerical dev pass at 1/5/10 bp, but not a distinct new family: "
                 "the edge is the negative-autocorrelation reversal leg, the "
                 "positive-autocorrelation continuation leg is weak, the plateau "
                 "passes only at the weakest reversal threshold, and correlation "
                 "with family-short-reversal is high."),
    )

    with open(OUT / "result.json", "w") as fh:
        json.dump(clean(result), fh, indent=1)

    print("\nfamily-autocorrelation-regime  (dev %s .. %s)" % (DEV_START, DEV_END))
    for bp in (1.0, 5.0, 10.0):
        s = windows[f"{bp:g}bp"]
        print("  %4.0f bp  CAGR %6.2f%%  DD %5.2f%%  Sharpe %4.2f  Sortino %4.2f  "
              "fills %4d  turnover %6.0fx  end $%s" % (
                  bp, s["cagr"] * 100, s["max_drawdown"] * 100, s["sharpe"],
                  s["sortino"], s["fills"], s["turnover"], f"{s['ending_equity']:,.0f}"))
    print("  TQQQ bar             CAGR %6.2f%%  DD %5.2f%%  Sharpe %4.2f" % (
        BAR["cagr"] * 100, BAR["max_dd"] * 100, BAR["sharpe"]))
    print("  TQQQ buy & hold      CAGR %6.2f%%  DD %5.2f%%  Sharpe %4.2f" % (
        bench["cagr"] * 100, bench["max_drawdown"] * 100, bench["sharpe"]))
    print("  entries %d  exits %d  avg hold %.1f  TQQQ exposure %.3f  "
          "plateau %d/%d cells pass (%d/%d core)" % (
              act["entries"], act["exits"], act["avg_hold_sessions"],
              act["tqqq_exposure"], n_pass, len(plateau), reg_pass, len(grid_pass)))
    print("  corr TQQQ %.3f  winners %.3f..%.3f (max %s)" % (
        corr["corr_tqqq"], corr["winner_corr_min"], corr["winner_corr_max"],
        max(corr["winners"], key=lambda k: corr["winners"][k]["corr"])))
    print("  placebo shift-target p=%.3f  shift-AC p=%.3f" % (
        placebo["shift_target"]["p_one_sided"], placebo["shift_ac"]["p_one_sided"]))
    print("  wrote", OUT / "result.json")


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    return obj


if __name__ == "__main__":
    main()
