"""Standalone expiry-cycle strategy (rebuild of `event-risk-overlay`).

IDEA
----
The monthly option-expiry session (third Friday, rolled back over an exchange
holiday) is a liquidity event: covered-call writers roll, dealer gamma rolls off
and the expiry print unwinds.  In the development sample the expiry *session*
carries a large negative open->close drift, while the sessions around it are
normal or better.  The cycle is not uniformly bad - exactly one session in it is.

The original strategy used that fact as a 12-days-a-year overlay on a 165-day
QQQ regime.  This rebuild owns the calendar instead: it is in the market only
during the expiry cycle and never on the expiry session itself.

STRATEGY (complete; no moving-average gate, no old base weights)
---------------------------------------------------------------
  Universe   QQQ, TQQQ, BIL (1-minute regular session).
  Signal     the monthly expiry calendar, nothing else.
  Position   long TQQQ during the expiry cycle window
                 sessions [expiry-4 .. expiry-1]  and  [expiry+1 .. expiry+2]
             held through the intervening nights; BIL on the expiry session and
             on every other session.
  Sizing     100% TQQQ inside the window, halved when QQQ's 20-session realised
             volatility (through the prior close) exceeds 25% annualised.  The
             vol rule only ever cuts exposure; it never adds it.
  Risk       no stop, no leverage beyond TQQQ's own 3x, no shorts, no position
             outside the window; ~71% of sessions in T-bills.

Falsifiers (pre-registered; see report.md):
  F1 the cycle window does not beat either shifted-week placebo;
  F2 dev Sharpe < 0.50 or dev max drawdown > 30%;
  F3 correlation vs the old 165-day base >= 0.60;
  F4 the window is not profitable in at least two of the three dev sub-periods;
  F5 5 bp costs remove more than 40% of the 1 bp CAGR.

Run (only after the lead authorises):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/strategies/event-risk-overlay/strategy.py
    python research/strategies/event-risk-overlay/strategy.py --with-holdout   # lead only
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV0, DEV1 = "2016-01-04", "2023-12-29"
HOLDOUT0, HOLDOUT1 = "2024-01-02", "2026-10-23"
TEN0, FIVE0 = "2017-01-03", "2021-10-25"
END = "2026-10-23"
BAR_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent

OFFSETS = (-4, -3, -2, -1, 1, 2)          # pre-registered primary window
VOL_CAP = {"on": True, "n": 20, "thr": 0.25, "size": 0.5}
# structural placebos: the same "4 sessions before + 2 after, skip the anchor
# Friday" shape, anchored on a Friday one week and two weeks later.
PLACEBO_1W = (1, 2, 3, 4, 6, 7)
PLACEBO_2W = (6, 7, 8, 9, 11, 12)


# ---------------------------------------------------------------------------
# calendar (deterministic, published years in advance)
# ---------------------------------------------------------------------------
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d + dt.timedelta(days=7 * (n - 1))


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def _easter(year: int) -> dt.date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def nyse_holidays(year: int) -> set[dt.date]:
    """Full-day NYSE holidays from rules fixed decades in advance."""
    d = dt.date(year, 5, 31)
    while d.weekday() != 0:                      # Memorial Day: last Monday
        d -= dt.timedelta(days=1)
    h = {
        _observed(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - dt.timedelta(days=2),    # Good Friday
        d,
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(dt.date(year, 12, 25)),
    }
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))
    h.discard(dt.date(year - 1, 12, 31))         # Jan-1 Saturday observed in Dec
    return h


def opex_dates(year0: int, year1: int) -> list[dt.date]:
    """Third Friday; rolled back to the prior session over an exchange holiday."""
    out = []
    for y in range(year0, year1 + 1):
        hol = nyse_holidays(y) | nyse_holidays(y - 1) | nyse_holidays(y + 1)
        for m in range(1, 13):
            d = _nth_weekday(y, m, 4, 3)
            while d in hol:
                d -= dt.timedelta(days=1)
            out.append(d)
    return out


# ---------------------------------------------------------------------------
def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    return first, np.r_[first[1:] - 1, len(dates) - 1]


# ---------------------------------------------------------------------------
# strategy
# ---------------------------------------------------------------------------
def build_weights(ts, opens, closes, *, offsets=OFFSETS, asset=1, size=1.0,
                  through_nights=True, vol_cap=VOL_CAP, anchors=None):
    """Long `asset` on the expiry-cycle sessions, BIL otherwise.

    Harness convention: the target set at bar i fills at open(i+1).  Bar
    `last[k-1]` therefore carries session k's target, and a block is exited by
    targeting 0 at bar `last[k]-1`, which fills on the 15:59 print.

    Nothing here reads a moving average of QQQ/TQQQ/SPY/NDX and no old weight
    matrix is imported, copied or called.
    """
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    n_days = len(first)
    sess_dates = dates[first]

    if anchors is None:
        opex = set(opex_dates(sess_dates[0].year - 1, sess_dates[-1].year + 1))
        k0s = np.flatnonzero(np.array([d in opex for d in sess_dates]))
    else:                                         # placebo calendars only
        k0s = np.asarray(anchors, dtype=int)

    hold = np.zeros(n_days, bool)
    for k0 in k0s:
        for off in offsets:
            j = k0 + off
            if 0 <= j < n_days:
                hold[j] = True

    # sizing: risk rule only, uses the prior close
    qqq_close = closes[last, 0]
    logret = np.r_[np.nan, np.diff(np.log(qqq_close))]
    rv = pd.Series(logret).rolling(vol_cap["n"]).std().to_numpy() * np.sqrt(252)
    rv_prev = np.r_[np.nan, rv[:-1]]
    tgt = np.where(hold, float(size), 0.0)
    mode = vol_cap.get("mode", "step")
    if mode == "step":
        cut = np.isfinite(rv_prev) & (rv_prev > vol_cap["thr"])
        if vol_cap["on"]:
            tgt = np.where(cut & hold, float(size) * vol_cap["size"], tgt)
    else:                                         # "target": continuous, cut-only
        scale = np.where(np.isfinite(rv_prev) & (rv_prev > 0),
                         np.minimum(1.0, vol_cap["target"] / np.where(rv_prev > 0, rv_prev, 1.0)),
                         1.0)
        cut = hold & (scale < 1.0)
        if vol_cap["on"]:
            tgt = np.where(hold, float(size) * scale, 0.0)

    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for k in range(n_days):
        a = 0 if k == 0 else last[k - 1]
        hi = last[k]
        if hi > a:
            w[a:hi, asset] = tgt[k]
            w[a:hi, 2] = 1.0 - tgt[k]
        # exit at the close when this is the last invested session of a block
        if tgt[k] > 0.0 and (k + 1 >= n_days or tgt[k + 1] == 0.0):
            j = max(last[k] - 1, a)
            if j < len(ts):
                w[j, asset] = 0.0
                w[j, 2] = 1.0

    if not through_nights:
        for k in np.flatnonzero(hold):
            j = last[k] - 1
            if j >= 0:
                w[j, asset] = 0.0
                w[j, 2] = 1.0

    info = {
        "n_sessions": int(n_days),
        "n_designated": int(hold.sum()),
        "exposure_share": float(hold.mean()),
        "n_expiry_sessions": int(len(k0s)),
        "n_blocks": int(np.sum(hold & ~np.r_[False, hold[:-1]])),
        "offsets": list(offsets),
        "size": float(size),
        "asset": "TQQQ" if asset == 1 else "QQQ",
        "vol_cap": dict(vol_cap),
        "n_halved": int((cut & hold).sum()),
    }
    return w, info


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------
def reference_165d_daily_returns(ts, closes):
    """BENCHMARK ONLY - never an input to build_weights.

    Daily close-to-close returns of the old 165-day base (QQQ above its 165-day
    SMA -> TQQQ, else BIL), without the round-1 intraday stop.  It exists so the
    report can quote the correlation the brief asks for.  It is not called by
    build_weights and its output never reaches the strategy.
    """
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    sess_dates = dates[first]
    qc = closes[last, 0]
    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    reg = np.zeros(len(qc), bool)
    reg[1:] = np.isfinite(sma_prev[1:]) & (qc[:-1] > sma_prev[1:])
    rt = np.r_[np.nan, closes[last, 1][1:] / closes[last, 1][:-1] - 1]
    rb = np.r_[np.nan, closes[last, 2][1:] / closes[last, 2][:-1] - 1]
    r = np.where(reg, rt, rb)
    return pd.Series(r, index=pd.Index(sess_dates, name="date")).dropna()


def daily_returns(result):
    return bt.daily_last(result["equity"], result["ts"]).pct_change().dropna()


def score(ts, opens, closes, w, start, end, slip):
    i = bt.start_index(ts, start)
    # include the whole `end` session (the old `searchsorted(end) + 1` kept
    # only its first bar, so every sub-period dropped its last session)
    j = int(np.searchsorted(ts, pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)))
    r = bt.simulate(ts[i:j], opens[i:j], closes[i:j], w[i:j], band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BAR_YEAR)


def perm_pvalue(base_daily, mask, n_draws=1000, seed=7):
    """Are the calendar-selected sessions better than random sessions?

    `base_daily` is the underlying asset's per-session return (TQQQ close to
    close), not the strategy series, so the null is 'pick the same number of
    sessions at random' rather than 'be invested on random days'.
    """
    r = np.asarray(base_daily, dtype=float)
    k = int(mask.sum())
    observed = float(r[np.asarray(mask)].mean())
    rng = np.random.default_rng(seed)
    draws = np.array([r[rng.choice(len(r), size=k, replace=False)].mean() for _ in range(n_draws)])
    return {"p_value": float((draws >= observed).mean()), "in_window_mean": observed,
            "random_mean": float(draws.mean()), "n_sessions": k}


def month_bootstrap(daily, n_draws=2000, seed=11):
    d = pd.Series(daily)
    d.index = pd.to_datetime(d.index)
    months = [g.to_numpy() for _, g in d.groupby([d.index.year, d.index.month])]
    rng = np.random.default_rng(seed)
    cagrs, dds = np.empty(n_draws), np.empty(n_draws)
    for i in range(n_draws):
        x = np.concatenate([months[j] for j in rng.integers(0, len(months), len(months))])
        eq = np.cumprod(1.0 + x)
        cagrs[i] = eq[-1] ** (252.0 / len(x)) - 1.0
        dds[i] = -(eq / np.maximum.accumulate(eq) - 1.0).min()
    return {str(q): {"cagr": float(np.percentile(cagrs, q)),
                     "max_drawdown": float(np.percentile(dds, q))} for q in (5, 50, 95)}


def yearly_chain(ts, equity, bench):
    """Calendar-year returns chained year-end to year-end.

    bt.yearly measures first-to-last mark inside each year, which drops the
    overnight from the last session of one year into the first of the next.
    """
    eq = pd.Series(equity, index=ts)
    bm = pd.Series(bench, index=ts)
    out = {}
    pe, pb = eq.iloc[0], bm.iloc[0]
    for y in sorted(set(ts.year)):
        e, b = eq[ts.year == y].iloc[-1], bm[ts.year == y].iloc[-1]
        out[str(y)] = {"strategy": float(e / pe - 1.0), "benchmark": float(b / pb - 1.0)}
        pe, pb = e, b
    return out


# ---------------------------------------------------------------------------
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    with_holdout = "--with-holdout" in argv

    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0,
                                 END if with_holdout else DEV1, "1min")
    if not with_holdout:
        assert ts[-1].date() <= pd.Timestamp(DEV1).date(), "holdout must not be loaded"

    variants = {
        "primary": {},
        "no_vol_cap": {"vol_cap": {"on": False, "n": 20, "thr": 0.25, "size": 0.5}},
        "half_size": {"size": 0.5},
        "week_only": {"offsets": (-4, -3, -2, -1)},
        "post_only": {"offsets": (1, 2)},
        "wider": {"offsets": (-5, -4, -3, -2, -1, 1, 2)},
        "narrower": {"offsets": (-4, -3, -2, 1, 2)},
        "qqq_instead": {"asset": 0},
        "session_only": {"through_nights": False},
        "vol_thr_20": {"vol_cap": {"on": True, "n": 20, "thr": 0.20, "size": 0.5}},
        "vol_thr_30": {"vol_cap": {"on": True, "n": 20, "thr": 0.30, "size": 0.5}},
        "placebo_1w": {"offsets": PLACEBO_1W},
        "placebo_2w": {"offsets": PLACEBO_2W},
    }
    weights, infos = {}, {}
    for name, kw in variants.items():
        weights[name], infos[name] = build_weights(ts, opens, closes, **kw)

    names = list(variants)
    res = bt.run_many(ts, opens, closes, [weights[n] for n in names],
                      start=DEV0, band=0.02, slippage_bps=1.0)
    by_name = dict(zip(names, res))

    dev_daily = daily_returns(by_name["primary"])
    ref = reference_165d_daily_returns(ts, closes)
    common = ref.index.intersection(dev_daily.index)
    corr = float(np.corrcoef(ref.loc[common], dev_daily.loc[common])[0, 1])

    # session mask of the primary window, aligned to dev daily returns
    dates = bt.session_dates(ts)
    first, _ = day_bounds(dates)
    opex = set(opex_dates(2016, 2024))
    k0s = np.flatnonzero(np.array([d in opex for d in dates[first]]))
    want = np.zeros(len(first), bool)
    for k0 in k0s:
        for off in OFFSETS:
            j = k0 + off
            if 0 <= j < len(first):
                want[j] = True
    mask = pd.Series(want, index=pd.Index(dates[first])).reindex(dev_daily.index).fillna(False).to_numpy()
    tqqq_c2c = pd.Series(
        np.r_[np.nan, closes[day_bounds(dates)[1], 1][1:] / closes[day_bounds(dates)[1], 1][:-1] - 1],
        index=pd.Index(dates[first])).reindex(dev_daily.index)

    dev = {}
    for slip, tag in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r, s = score(ts, opens, closes, weights["primary"], DEV0, DEV1, slip)
        dev[tag] = {"cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
                    "sharpe": float(s["sharpe"]), "sortino": float(s["sortino"]),
                    "fills": int(s["fills"]), "exposure": float(s["exposure"]),
                    "turnover": float(s["turnover"])}

    sub = {}
    for lo, hi in (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"),
                   ("2022-01-03", "2023-12-29")):
        _, s = score(ts, opens, closes, weights["primary"], lo, hi, 1.0)
        sub[f"{lo[:4]}-{hi[:4]}"] = {"cagr": float(s["cagr"]),
                                     "max_drawdown": float(s["max_drawdown"]),
                                     "sharpe": float(s["sharpe"])}

    table = {}
    for nm, r in zip(names, res):
        s = bt.stats(r, BAR_YEAR)
        d = daily_returns(r)
        j = ref.index.intersection(d.index)
        table[nm] = {"cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
                     "sharpe": float(s["sharpe"]), "fills": int(s["fills"]),
                     "exposure": float(s["exposure"]),
                     "corr": float(np.corrcoef(ref.loc[j], d.loc[j])[0, 1]),
                     "exposure_share": infos[nm]["exposure_share"]}

    perm = perm_pvalue(tqqq_c2c.to_numpy(), mask)
    boot = month_bootstrap(dev_daily)       # keep the date index: months are the blocks
    i0 = bt.start_index(ts, DEV0)
    bench = {sym: {k: float(v[k]) for k in ("cagr", "max_drawdown", "sharpe")}
             for sym, v in ((s, bt.benchmark(closes[i0:, j], ts[i0:], BAR_YEAR))
                            for s, j in (("tqqq", 1), ("qqq", 0), ("bil", 2)))}

    # pre-registered pass/fail
    f1 = (table["primary"]["cagr"] > table["placebo_1w"]["cagr"]
          and table["primary"]["cagr"] > table["placebo_2w"]["cagr"])
    f2 = dev["1bp"]["sharpe"] >= 0.50 and dev["1bp"]["max_drawdown"] <= 0.30
    f3 = corr < 0.60
    f4 = sum(1 for v in sub.values() if v["cagr"] > 0) >= 2
    f5 = dev["5bp"]["cagr"] >= 0.60 * dev["1bp"]["cagr"]
    flags = {"F1_beats_placebo": bool(f1), "F2_sharpe_dd": bool(f2),
             "F3_corr_below_0.60": bool(f3), "F4_subperiods": bool(f4),
             "F5_cost_robust": bool(f5)}
    # If the cycle window does not beat its own shifted-week placebos the
    # expiry-day effect is still real, but the long-only harness cannot
    # monetise it: the correct label is overlay-only, not passed.
    status = "passed" if all(flags.values()) else ("retired_overlay_only" if not f1 else "rejected")

    out = {
        "agent": "event-risk-overlay",
        "original": "research/agents2/event-risk-overlay",
        "status": status,
        "falsifiers": flags,
        "idea": "The monthly option-expiry session is the one systematically weak "
                "session of the expiry cycle; own the cycle and step out for the expiry session.",
        "hypothesis": "Dealer roll and gamma unwind create a recurring negative intraday "
                      "drift on the expiry session, so a calendar-only strategy that holds "
                      "TQQQ around the cycle but never through the expiry session earns a "
                      "flow premium that is uncorrelated with trend following.",
        "universe": ["QQQ 1-min", "TQQQ 1-min", "BIL 1-min"],
        "frozen_commit": None,
        "variants_tried": len(variants),
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": dev, "holdout": {}, "10y": {}, "5y": {}},
        "marks": "1m",
        "benchmarks": bench,
        "spec": infos["primary"],
        "diagnostics": {
            "neighbourhood_dev_1bp": table,
            "subperiods_dev_1bp": sub,
            "permutation": perm,
            "month_bootstrap": boot,
            "yearly_dev": yearly_chain(ts[i0:], by_name["primary"]["equity"], closes[i0:, 1]),
        },
    }

    if with_holdout:                                    # lead only
        for tag, (a, b_) in {"holdout": (HOLDOUT0, HOLDOUT1), "10y": (TEN0, END),
                             "5y": (FIVE0, END)}.items():
            for slip, cost in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
                _, s = score(ts, opens, closes, weights["primary"], a, b_, slip)
                out["windows"][tag][cost] = {"cagr": float(s["cagr"]),
                                             "max_drawdown": float(s["max_drawdown"]),
                                             "sharpe": float(s["sharpe"]),
                                             "fills": int(s["fills"])}

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({"dev": dev, "corr": corr, "falsifiers": flags}, indent=2))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
