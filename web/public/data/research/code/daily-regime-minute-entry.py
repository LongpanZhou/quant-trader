"""Revisit: the armed 4% minute stop rebuilt as a standalone crash-continuation short.

WHAT IS NEW IN THE ORIGINAL
---------------------------
The original strategy (research/agents/daily-regime-minute-entry) is the
165-day QQQ regime (the shared base) plus one new idea: a 4% break below the
session open, armed when QQQ opens below its 20-day MA, predicts continuation
into the close and the night; exiting the long TQQQ book there avoided tail
losses.  The effect is *downside continuation after an intraday break*.

THIS REBUILD
------------
The effect is traded directly instead of being used as an exit filter:

  * Universe: TQQQ (short), BIL (parking), QQQ (signal only). SPY daily is a
    benchmark only.
  * No 165-day gate, no long-TQQQ base, no reused weights.
  * Signal: TQQQ's first 1-minute close at least 4% below the session open.
  * Position: short TQQQ from the next minute's open to the session close
    (or an earlier cover if the session's loss is fully reclaimed / a +2%
    bounce), then 100% BIL until the next event.
  * Holding period: minutes to a few hours; never overnight.
  * Sizing: 1.0x equity short (0.5x variant).  Gross <= 1.0x, long-only
    collateral, 0.5%/yr borrow.
  * Risk: one trade per session, no entry after 15:45, forced cover at the
    15:59 open; the cover-on-reclaim rule caps the V-bounce tail.

Engine note: research/bt.py is long-only, so the short is expressed as a long
position in a synthetic constant-notional inverse TQQQ NAV ("-1x TQQQ" with a
0.5%/yr fee).  The NAV is built from the same 1-minute TQQQ bars; the harness
still does every fill, band check, cost charge and 1-minute mark.  On a held
bar the NAV return is exactly -(TQQQ return) - borrow/390.  If the lead
disallows synthetic instruments, this effect has no long-only expression in
this data set (no inverse ETF, VIX or options history is available) and the
honest status is retired_overlay_only.

Backtests are PAUSED by instruction.  This file is complete and ready to run,
but must not be executed until the lead/user authorizes the new test.
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
BARS = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")
BORROW = 0.005          # 0.5%/yr on the short notional, per the brief
OUT = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Data and calendar
# --------------------------------------------------------------------------- #
def load_dev():
    ts, o, c = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=0)
    return ts, o, c


_DATES_CACHE: dict = {}


def session_dates(ts: pd.DatetimeIndex) -> np.ndarray:
    """`bt.session_dates(ts)`, computed once per panel.

    The per-element conversion takes seconds on a 1-minute panel and the
    sweeps call it hundreds of times on the same timestamps.
    """
    i8 = ts.asi8
    key = (len(i8), int(i8[0]) if len(i8) else 0, int(i8[-1]) if len(i8) else 0,
           int(i8[::997].sum()) if len(i8) else 0, str(ts.tz))
    d = _DATES_CACHE.get(key)
    if d is None:
        d = bt.session_dates(ts)
        _DATES_CACHE.clear()
        _DATES_CACHE[key] = d
    return d


def day_index(ts: pd.DatetimeIndex):
    return bt.day_bounds(ts)


def levels_through_prior_close(closes, last, window):
    """Rolling mean of daily closes, shifted one session (known before the open)."""
    daily = closes[last, 0]
    ma = pd.Series(daily).rolling(window).mean().to_numpy()
    return np.r_[np.nan, ma[:-1]]


# --------------------------------------------------------------------------- #
# Synthetic -1x TQQQ NAV
# --------------------------------------------------------------------------- #
def inverse_nav(opens_tqqq, closes_tqqq, borrow=BORROW, bars_per_year=BARS):
    """Constant-notional inverse TQQQ NAV with a borrow fee.

    S_open[t]  = S_close[t-1] * (1 - gap_t  - b/2)
    S_close[t] = S_open[t]   * (1 - intra_t - b/2)
    with gap_t = open_t/close_{t-1}-1, intra_t = close_t/open_t-1.
    Holding from open[i] to open[j] therefore earns the short return from
    TQQQ open[i] to open[j] minus borrow over the holding period.
    """
    n = len(closes_tqqq)
    b = borrow / bars_per_year
    o = np.asarray(opens_tqqq, dtype=float)
    c = np.asarray(closes_tqqq, dtype=float)
    # Same recurrence as the original loop, as one cumulative product over the
    # interleaved factors [100, g1, i1, g2, i2, ...]: identical multiplication
    # order, so the result is bit-for-bit the same.
    f = np.empty(2 * n - 1) if n else np.empty(0)
    if n:
        f[0] = 100.0
        f[1::2] = 1.0 - (o[1:] / c[:-1] - 1.0) - 0.5 * b
        f[2::2] = 1.0 - (c[1:] / o[1:] - 1.0) - 0.5 * b
    path = np.cumprod(f)
    so = np.empty(n)
    sc = np.empty(n)
    if n:
        so[0] = sc[0] = 100.0
        so[1:] = path[1::2]
        sc[1:] = path[2::2]
    return so, sc


def short_nav(opens_tqqq, closes_tqqq, w_inv, borrow=BORROW, bars_per_year=BARS):
    """Constant-share short NAV, re-anchored at each entry fill (tuning fix).

    `inverse_nav` rebalances to -1x every minute, which charges a volatility
    drag that a real short does not pay (measured 2.3 bp per event on dev,
    worst 120 bp; about 1%/yr).  A real short of a fixed number of shares
    opened at open[e] is worth 2 - P_t/P_e per unit of collateral.  A held
    block starts at bar e when w_inv[e-1] > 0 and w_inv[e-2] == 0 (the target
    set at e-1's close fills at e's open) and ends at the first bar x with
    w_inv[x-1] == 0 (the exit fill at x's open).  On [e, x]:

        S_open[t]  = 2 - open[t]/open[e]  - b*(t-e)
        S_close[t] = 2 - close[t]/open[e] - b*(t-e+1)

    and 1.0 elsewhere (never held there).  Everything used at bar t is known by
    bar t, so the series is causal.  Holding from open[e] to open[x] earns
    exactly 1 - open[x]/open[e] minus borrow.
    """
    o = np.asarray(opens_tqqq, dtype=float)
    c = np.asarray(closes_tqqq, dtype=float)
    w = np.asarray(w_inv, dtype=float)
    n = len(o)
    b = borrow / bars_per_year
    so = np.ones(n)
    sc = np.ones(n)
    held = np.zeros(n, bool)
    held[1:] = w[:-1] > 0                  # position carried into bar t
    starts = np.flatnonzero(held & ~np.r_[False, held[:-1]])
    ends = np.flatnonzero(held & ~np.r_[held[1:], False])
    for e, e_last in zip(starts, ends):
        x = min(int(e_last) + 1, n - 1)    # exit fill bar (open), inclusive
        k = np.arange(x - e + 1)
        so[e:x + 1] = 2.0 - o[e:x + 1] / o[e] - b * k
        sc[e:x + 1] = 2.0 - c[e:x + 1] / o[e] - b * (k + 1)
    assert (so > 0).all() and (sc > 0).all()
    return so, sc


def priced(opens, closes, w, borrow=BORROW):
    """(opens, closes) for the [BIL, SHORT] weight columns of `w`."""
    so, sc = short_nav(opens[:, 1], closes[:, 1], w[:, 1], borrow)
    return np.column_stack([opens[:, 2], so]), np.column_stack([closes[:, 2], sc])


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, stop=0.04, size=1.0, cover="reclaim",
                  arm_ma20=False, arm_buf=0.01, borrow=BORROW,
                  last_entry_min=375, bounce=0.02):
    """Standalone crash-continuation short.

    Parameters
    ----------
    opens/closes : (n, 3) QQQ, TQQQ, BIL 1-minute bars.
    stop         : TQQQ must close this far below the session open to trigger.
    size         : short notional as a fraction of equity (<= 1.0 here).
    cover        : "reclaim" (cover if TQQQ closes back above the session
                   open), "stop2" (cover on a +`bounce` rise from the entry) or
                   "close" (hold to the forced 15:59 cover).
    arm_ma20     : if True, only trade when QQQ's 09:30 close is below its
                   20-day MA * (1 + arm_buf).  The primary rule is unarmed.
    borrow       : annual borrow fee embedded in the inverse NAV.

    Returns
    -------
    w : (n, 2) weights for [BIL, INV]
    info : dict with events, exposure, etc.
    """
    d, first, last = day_index(ts)
    n = len(ts)
    w = np.zeros((n, 2))
    w[:, 0] = 1.0

    ma20 = levels_through_prior_close(closes, last, 20)
    events = []
    short_bars = 0

    for k, (f, l) in enumerate(zip(first, last)):
        w[f:l + 1, 0] = 1.0
        w[f:l + 1, 1] = 0.0
        if arm_ma20:
            lvl = ma20[k]
            if not (lvl == lvl and opens[f, 0] < lvl * (1.0 + arm_buf)):
                continue
        base = opens[f, 1]
        mi = np.arange(l - f)
        trig = (mi <= last_entry_min) & (closes[f:l, 1] < base * (1.0 - stop))
        idx = np.flatnonzero(trig)
        if idx.size == 0:
            w[l, 0] = w[l - 1, 0]
            w[l, 1] = w[l - 1, 1]
            continue
        i = f + int(idx[0])
        entry_bar = i + 1
        if entry_bar >= l:
            continue
        exit_bar = l
        if cover in ("reclaim", "stop2", "reclaim_stop"):
            seg = closes[i + 1:l, 1]
            entry_px = opens[entry_bar, 1]
            if cover == "reclaim":
                cond = seg > base
            elif cover == "stop2":
                cond = seg > entry_px * (1.0 + bounce)
            else:
                cond = (seg > base) | (seg > entry_px * (1.0 + bounce))
            hits = np.flatnonzero(cond)
            if hits.size:
                exit_bar = min(i + 2 + int(hits[0]), l)
        short_end = exit_bar - 1
        if short_end > i:
            w[i:short_end, 0] = 0.0
            w[i:short_end, 1] = size
            short_bars += short_end - i
        events.append({
            "date": str(d[f]),
            "entry_time": str(ts[entry_bar].time()),
            "exit_time": str(ts[exit_bar].time()),
            "entry_px": float(opens[entry_bar, 1]),
            "exit_px": float(opens[exit_bar, 1]),
            "ret": float(1.0 - opens[exit_bar, 1] / opens[entry_bar, 1]),
        })
        # 15:59 bar: keep the last target so nothing trades overnight
        w[l, 0] = w[l - 1, 0]
        w[l, 1] = w[l - 1, 1]

    info = {
        "events": events,
        "n_events": len(events),
        "days": int(len(first)),
        "short_bar_fraction": float(short_bars / n),
        "stop": stop,
        "size": size,
        "cover": cover,
        "arm_ma20": bool(arm_ma20),
    }
    return w, info


def baseline_weights(ts, closes, first, last, window=165):
    """The old 165-day QQQ base, built ONLY as the correlation benchmark."""
    n = len(ts)
    daily = closes[last, 0]
    sma = pd.Series(daily).rolling(window).mean().to_numpy()
    on_day = np.zeros(len(first), bool)
    on_day[1:] = daily[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    on = on_day[day_id]
    w = np.zeros((n, 3))
    w[:, 1] = on.astype(float)
    w[:, 2] = 1.0 - on
    return w


# --------------------------------------------------------------------------- #
# Evaluation helpers
# --------------------------------------------------------------------------- #
def daily_returns(ts, equity):
    return bt.daily_last(equity, ts).pct_change().dropna()


def metric_dict(s):
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                     "volatility", "fills", "turnover",
                                     "ending_equity")}


def score(ts, o, c, w, slip=1.0):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS)


def slice_score(ts, o, c, w, start, end, slip=1.0):
    d = session_dates(ts)
    i0 = int(np.searchsorted(d, pd.Timestamp(start).date()))
    i1 = int(np.searchsorted(d, pd.Timestamp(end).date(), side="right"))
    r = bt.simulate(ts[i0:i1], o[i0:i1], c[i0:i1], w[i0:i1],
                    band=0.02, slippage_bps=slip)
    return bt.stats(r, BARS)


def event_stats(events):
    if not events:
        return {"n": 0}
    r = np.array([e["ret"] for e in events])
    n = len(r)
    mean = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else float("nan")
    t = mean / (sd / np.sqrt(n)) if n > 1 and sd > 0 else float("nan")
    # bootstrap p(mean <= 0)
    rng = np.random.default_rng(7)
    idx = rng.integers(0, n, size=(10_000, n))
    means = r[idx].mean(axis=1)
    p = float((means <= 0).mean())
    return {"n": n, "mean": mean, "median": float(np.median(r)),
            "std": sd, "t": float(t), "p_mean_le_0": p,
            "worst": float(r.min()), "best": float(r.max()),
            "hit_rate": float((r > 0).mean())}


def placebo_weights(ts, opens, closes, n_events, seed, size=1.0,
                    borrow=BORROW):
    """Random intraday shorts with the same count and holding mechanics."""
    d, first, last = day_index(ts)
    n = len(ts)
    w = np.zeros((n, 2))
    w[:, 0] = 1.0
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(first), size=min(n_events, len(first)), replace=False)
    for k in picks:
        f, l = first[k], last[k]
        mi = int(rng.integers(30, 361))          # 10:00 .. 15:30
        i = f + mi
        w[i:l - 1, 0] = 0.0
        w[i:l - 1, 1] = size
        w[l - 1, 0] = 1.0
        w[l - 1, 1] = 0.0
        w[l, 0] = 1.0
        w[l, 1] = 0.0
    return w


def load_spy_dev():
    df = pd.read_parquet(ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[(df["date"] >= pd.Timestamp(DEV_START).date())
            & (df["date"] <= pd.Timestamp(DEV_END).date())]
    px = df["adjclose"].to_numpy()
    rets = np.diff(px) / px[:-1]
    yrs = (pd.Timestamp(df["date"].iloc[-1]) - pd.Timestamp(df["date"].iloc[0])).days / 365.25
    peak = np.maximum.accumulate(px)
    return {
        "cagr": float((px[-1] / px[0]) ** (1 / yrs) - 1),
        "max_drawdown": float(-(px / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)),
        "marks": "daily (1m SPY unavailable for 2016-2023)",
    }


# --------------------------------------------------------------------------- #
# Main (do not run while backtests are paused)
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_dev()
    d, first, last = day_index(ts)

    base_w = baseline_weights(ts, c, first, last)
    w, info = build_weights(ts, o, c)
    p2, c2 = priced(o, c, w)
    r, s = score(ts, p2, c2, w)
    base_r, base_s = score(ts, o, c, base_w)

    dr = daily_returns(ts, r["equity"])
    dbase = daily_returns(ts, base_r["equity"]).reindex(dr.index)
    corr = float(dr.corr(dbase))

    # BH benchmarks and BIL carry
    tq = np.zeros((len(ts), 3)); tq[:, 1] = 1.0
    qq = np.zeros((len(ts), 3)); qq[:, 0] = 1.0
    bl = np.zeros((len(ts), 3)); bl[:, 2] = 1.0
    _, s_tq = score(ts, o, c, tq)
    _, s_qq = score(ts, o, c, qq)
    _, s_bl = score(ts, o, c, bl)

    # costs
    costs = {"1bp": metric_dict(s)}
    for bp in (5.0, 10.0):
        _, sb = score(ts, p2, c2, w, slip=bp)
        costs[f"{bp:.0f}bp"] = metric_dict(sb)

    # variants
    variants = [
        ("base", {}),
        ("stop3", dict(stop=0.03)),
        ("stop5", dict(stop=0.05)),
        ("cover_close", dict(cover="close")),
        ("cover_stop2", dict(cover="stop2")),
        ("size0.5", dict(size=0.5)),
        ("arm_ma20", dict(arm_ma20=True)),
    ]
    var_table = {}
    for name, kw in variants:
        wv, iv = build_weights(ts, o, c, **kw)
        pv, cv = priced(o, c, wv)
        _, sv = score(ts, pv, cv, wv)
        var_table[name] = {"cagr": float(sv["cagr"]),
                           "max_drawdown": float(sv["max_drawdown"]),
                           "sharpe": float(sv["sharpe"]),
                           "fills": int(sv["fills"]),
                           "n_events": int(iv["n_events"]),
                           **{k: iv[k] for k in ("stop", "size", "cover", "arm_ma20")}}

    # sub-periods
    subs = {}
    for a, b in (("2016-01-04", "2019-12-31"),
                 ("2020-01-02", "2021-12-31"),
                 ("2022-01-03", "2023-12-29")):
        ss = slice_score(ts, p2, c2, w, a, b)
        subs[f"{a[:4]}-{b[:4]}"] = {"cagr": float(ss["cagr"]),
                                    "max_drawdown": float(ss["max_drawdown"]),
                                    "sharpe": float(ss["sharpe"]),
                                    "fills": int(ss["fills"])}

    # placebo: same number of random intraday shorts
    n_ev = max(len(info["events"]), 1)
    plac = []
    seeds = list(range(100))
    for sd in seeds:
        wp = placebo_weights(ts, o, c, n_ev, seed=sd)
        pp, cp = priced(o, c, wp)
        _, sp = score(ts, pp, cp, wp)
        plac.append({"cagr": float(sp["cagr"]),
                     "max_drawdown": float(sp["max_drawdown"]),
                     "sharpe": float(sp["sharpe"])})
    pc = np.array([x["cagr"] for x in plac])
    placebo = {
        "n": len(plac),
        "cagr_mean": float(pc.mean()),
        "cagr_p05": float(np.percentile(pc, 5)),
        "cagr_p50": float(np.percentile(pc, 50)),
        "cagr_p95": float(np.percentile(pc, 95)),
        "cagr_max": float(pc.max()),
        "real_cagr_percentile": float((pc < s["cagr"]).mean()),
    }

    es = event_stats(info["events"])
    orig = json.loads((ROOT / "research" / "agents" / "daily-regime-minute-entry"
                       / "result.json").read_text())
    original = {"10y": {k: orig["windows"]["10y"][k] for k in
                        ("cagr", "max_drawdown", "sharpe", "fills")},
                "5y": {k: orig["windows"]["5y"][k] for k in
                       ("cagr", "max_drawdown", "sharpe", "fills")},
                "note": "quoted from the original result.json; 10y/5y overlap the holdout"}

    passed = (costs["1bp"]["cagr"] > s_bl["cagr"]
              and costs["1bp"]["sharpe"] >= 0.30
              and costs["1bp"]["max_drawdown"] <= 0.25
              and es.get("t", 0) >= 1.65
              and sum(1 for v in subs.values() if v["cagr"] > 0) >= 2)
    status = "passed" if (passed and corr < 0.60) else "rejected"
    if corr >= 0.60:
        status = "retired_overlay_only"

    out = {
        "agent": "daily-regime-minute-entry",
        "original": "research/agents/daily-regime-minute-entry",
        "status": status,
        "idea": "A 4% break below the TQQQ session open predicts continuation into the close; trade it as an intraday short instead of a long-book exit.",
        "hypothesis": "Shorting TQQQ from the break to the close, flat (BIL) otherwise, earns a positive net return with low correlation to the 165-day long base.",
        "universe": ["TQQQ (short via synthetic -1x inverse NAV)",
                     "BIL (parking)", "QQQ (signal only)"],
        "frozen_commit": None,
        "variants_tried": len(variants),
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": costs,
            "holdout": {"1bp": None, "5bp": None, "10bp": None},
            "10y": {"1bp": None, "5bp": None},
            "5y": {"1bp": None, "5bp": None},
        },
        "marks": "1m",
        "benchmarks": {
            "tqqq": metric_dict(s_tq),
            "qqq": metric_dict(s_qq),
            "bil": metric_dict(s_bl),
            "spy": load_spy_dev(),
            "original": original,
            "baseline_165d": metric_dict(base_s),
        },
        "event_stats": es,
        "sub_periods": subs,
        "variants": var_table,
        "placebo": placebo,
        "notes": [
            "Development window only; holdout and the overlapping 10y/5y windows are left null for the lead.",
            "Synthetic -1x NAV: on a held bar the return is -(TQQQ return) - 0.5%/yr/390; bt.py is long-only.",
            "One trade per session; no entry after 15:45; forced cover at the 15:59 open.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "dev_1bp": costs["1bp"],
                      "corr": corr, "events": es.get("n")}, indent=2))


if __name__ == "__main__":
    main()
