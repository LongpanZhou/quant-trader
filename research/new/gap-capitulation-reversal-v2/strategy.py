"""Quiet Capitulation Reversal v2 (QCR-v2) -- repaired standalone event sleeve.

v1 (`research/revisit/gap-capitulation-reversal`) required a QQQ close <= -2%
(or an intraday low <= -3%), volume <= 1.2x the prior 20-day average, and a
20-day return <= -3%.  It produced 30 events / 24 starts and only 3.95% average
exposure; with a 3-session hold and a 30% volatility cap it was in QQQ for 20
of 24 trades, so the reversal was monetised at 1x.

The repair keeps the same quiet-oversold capitulation event and changes only
three things:

  * the one-day decline threshold is -1.5% instead of -2.0% (the -3% intraday
    leg is unchanged), which lifts the sample from 30 to 39 events;
  * the hold is 5 sessions instead of 3 (the pre-registered event study found
    the 5-session TQQQ mean at least as strong as the 3-session mean);
  * the volatility cap is 35% instead of 30%, so TQQQ is used for the 30-35%
    volatility events instead of falling back to QQQ.  The 2020 crash
    (79-92% vol) and the 2022 May/June cluster (36-45%) still use QQQ.

Rules (event known at the close of day d; fill at d+1's open):

  qret = QQQ_close[d] / QQQ_close[d-1] - 1
  qdd  = QQQ_low[d]   / QQQ_close[d-1] - 1
  q20  = QQQ_close[d] / QQQ_close[d-20] - 1
  rvol = QQQ_volume[d] / mean(QQQ_volume[d-20 .. d-1])
  vol20 = annualised stdev(QQQ daily returns, last 20 sessions)

  event = (qret <= -1.5% OR qdd <= -3.0%)
          AND rvol <= 1.2
          AND q20 <= -3.0%

  if event:
      buy at the next open, 100% of TQQQ if vol20 <= 35%, else QQQ
      hold 5 sessions (the entry session plus four)
      exit at the 15:59 open of the fifth session, or at the next minute open
      on an 8% hard stop from entry
      a new event during the hold resets the clock and the entry price

No 165-day (or any 100-250-day) moving average is used.  Long-only, weights
>= 0, sum <= 1.  The 165-day baseline is benchmark-only.

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/gap-capitulation-reversal-v2/strategy.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
HOLDOUT_START = "2024-01-02"
END = "2026-10-23"
BARS_PER_YEAR = 252 * 390
TZ = "America/New_York"
OUT = Path(__file__).resolve().parent

PARAMS = dict(
    drop=0.015,          # repaired one-day close threshold (was 0.020)
    intraday=0.030,      # unchanged
    rvol_max=1.20,       # unchanged
    oversold=0.030,      # unchanged
    hold=5,              # repaired hold (was 3)
    vol_max=0.35,        # repaired cap (was 0.30)
    hard_stop=0.08,      # unchanged
    event_low_stop=False,  # v1 tuning: the event-low stop destroyed the edge
    size=1.0,
    high_vol="QQQ",      # asset above the cap: "QQQ" or "HALF"
)

# Pre-registered plateau grid (8 one-at-a-time variants).
GRID = [
    ("primary", {}),
    ("drop 1.25", {"drop": 0.0125}),
    ("drop 1.75", {"drop": 0.0175}),
    ("hold 3", {"hold": 3}),
    ("hold 8", {"hold": 8}),
    ("vol cap 30", {"vol_max": 0.30}),
    ("vol cap 40", {"vol_max": 0.40}),
    ("rvol 1.3", {"rvol_max": 1.30}),
]


# ----------------------------------------------------------------------------
# dev-only daily helpers
# ----------------------------------------------------------------------------
HALF_DAYS = {
    date(2016, 11, 25), date(2017, 7, 3), date(2017, 11, 24),
    date(2018, 7, 3), date(2018, 11, 23), date(2018, 12, 24),
    date(2019, 7, 3), date(2019, 11, 29), date(2019, 12, 24),
    date(2020, 11, 27), date(2020, 12, 24), date(2021, 11, 26),
    date(2022, 11, 25), date(2023, 7, 3), date(2023, 11, 24),
}


def _qqq_daily_extras(ts=None, end=DEV_END):
    """QQQ daily low and volume, physically filtered to ``end``.

    Replicates `bt.load_1m("QQQ")`: regular session only, half-day after-hours
    prints dropped, prices multiplied by the daily adjclose/close factor.

    ``ts`` is only supplied for the authorized full-window holdout.  It lets us
    detect post-2023 half-days from the panel's session lengths instead of
    relying on the development-window calendar above.
    """
    p = ROOT / "data" / "intraday-hf" / "QQQ-1m.parquet"
    lo = pd.Timestamp("2015-01-01", tz=TZ)
    hi = pd.Timestamp(end, tz=TZ) + pd.Timedelta(days=1)
    df = pd.read_parquet(
        p, columns=["ts", "low", "volume"],
        filters=[("ts", ">=", lo.tz_convert("UTC")),
                 ("ts", "<", hi.tz_convert("UTC"))],
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(TZ)
    df = df[(df["ts"].dt.time >= pd.Timestamp("09:30").time())
            & (df["ts"].dt.time < pd.Timestamp("16:00").time())].copy()
    df["date"] = df["ts"].dt.date
    half = set(HALF_DAYS)
    if ts is not None:
        days, first, last = bt.day_bounds(ts)
        half |= {
            pd.Timestamp(days[a]).date()
            for a, b in zip(first, last)
            if int(b) - int(a) + 1 < 300
        }
    after = df["date"].isin(half) & (df["ts"].dt.time > time(13, 0))
    if after.any():
        df = df.loc[~after].copy()

    dp = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    daily = pd.read_parquet(
        dp, columns=["date", "close", "adjclose"],
        filters=[("date", "<=", pd.Timestamp(end).date())])
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily["factor"] = daily["adjclose"] / daily["close"]
    df = df.merge(daily[["date", "factor"]], on="date", how="left")
    df["factor"] = df["factor"].ffill().bfill()
    df["low"] = df["low"] * df["factor"]
    g = df.groupby("date")
    return g["low"].min(), g["volume"].sum()


def prepare_daily(ts, opens, closes, qlow_s, qvol_s):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    nd = len(first)
    sess = pd.DatetimeIndex(sorted(set(pd.Timestamp(t.date()) for t in ts)))
    qlow = qlow_s.reindex(pd.Index([d.date() for d in sess])).to_numpy(float)
    qvol = qvol_s.reindex(pd.Index([d.date() for d in sess])).to_numpy(float)
    qo = opens[first, 0]
    qc = closes[last, 0]
    to = opens[first, 1]
    tc = closes[last, 1]
    prior_q = np.r_[np.nan, qc[:-1]]
    qret = qc / prior_q - 1.0
    qdd = qlow / prior_q - 1.0
    q20 = pd.Series(qc).pct_change(20).to_numpy()
    rvol = qvol / pd.Series(qvol).shift(1).rolling(20).mean().to_numpy()
    vol20 = pd.Series(qret).rolling(20).std(ddof=0).to_numpy() * np.sqrt(252.0)
    return dict(dates=dates, first=first, last=last, nd=nd, qo=qo, qc=qc,
                to=to, tc=tc, qlow=qlow, qvol=qvol, qret=qret, qdd=qdd,
                q20=q20, rvol=rvol, vol20=vol20)


# ----------------------------------------------------------------------------
# strategy
# ----------------------------------------------------------------------------
_COL = {1: 0, 2: 1, 3: 1}   # 1 QQQ, 2 TQQQ, 3 half TQQQ


def event_masks(d, p):
    cap = (d["qret"] <= -p["drop"]) | (d["qdd"] <= -p["intraday"])
    quiet = d["rvol"] <= p["rvol_max"]
    oversold = d["q20"] <= -p["oversold"]
    finite = (np.isfinite(d["qret"]) & np.isfinite(d["qdd"])
              & np.isfinite(d["rvol"]) & np.isfinite(d["q20"])
              & np.isfinite(d["vol20"]))
    return dict(cap=cap, quiet=quiet, oversold=oversold, finite=finite,
                base=cap & quiet & oversold & finite,
                heavy=cap & (~quiet) & oversold & finite,
                no_volume=cap & oversold & finite)


def build_weights(ts, opens, closes, qlow_s, qvol_s, params=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    d = prepare_daily(ts, opens, closes, qlow_s, qvol_s)
    nd, n = d["nd"], len(ts)

    ev = event_masks(d, p)["base"]
    pos = np.zeros(n, dtype=np.int8)
    active_until = -1
    asset = 0
    entry_px = np.nan
    event_dates = []
    trade_dates = []
    n_starts = 0
    n_hard_stops = 0
    n_time_exits = 0

    for s in range(1, nd):
        if ev[s - 1]:
            event_dates.append(str(d["dates"][d["first"][s - 1]]))
            was_active = s <= active_until
            active_until = max(active_until, (s - 1) + p["hold"])
            if d["vol20"][s - 1] <= p["vol_max"]:
                asset = 2
            else:
                asset = 3 if p["high_vol"] == "HALF" else 1
            f = int(d["first"][s])
            entry_px = float(opens[f, _COL[asset]])
            # decision at the event day's close -> fill at the next open
            pos[int(d["last"][s - 1])] = asset
            if not was_active:
                n_starts += 1
                trade_dates.append(str(d["dates"][f]))

        if s > active_until:
            continue

        f, l = int(d["first"][s]), int(d["last"][s])
        state = asset
        for i in range(f, l + 1):
            if state and closes[i, _COL[state]] < entry_px * (1.0 - p["hard_stop"]):
                state = 0
                active_until = -1
                n_hard_stops += 1
            pos[i] = state

        if s == active_until and state:
            if l - 1 > f:
                pos[l - 1] = 0
            pos[l] = 0
            active_until = -1
            n_time_exits += 1

    q = (pos == 1).astype(float) * p["size"]
    t = ((pos == 2).astype(float) + 0.5 * (pos == 3)) * p["size"]
    w = np.zeros((n, 3))
    w[:, 0] = q
    w[:, 1] = t
    w[:, 2] = 1.0 - q - t

    info = dict(params=p, n_events=len(event_dates), n_trade_starts=n_starts,
                n_hard_stops=n_hard_stops, n_time_exits=n_time_exits,
                event_dates=event_dates, trade_dates=trade_dates,
                exposure=float(np.mean(pos > 0)),
                qqq_share=float(np.mean(pos == 1)),
                tqqq_share=float(np.mean(pos == 2)),
                half_tqqq_share=float(np.mean(pos == 3)))
    return w, info


def build_holdout_weights(ts, opens, closes):
    """Authorized 2016-2026 adapter: same rules, full-panel QQQ low/volume."""
    qlow_s, qvol_s = _qqq_daily_extras(ts=ts, end=END)
    return build_weights(ts, opens, closes, qlow_s, qvol_s)


# ----------------------------------------------------------------------------
# benchmark / evaluation helpers
# ----------------------------------------------------------------------------
def benchmark_weights(ts, closes):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    qc = closes[last, 0]
    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = qc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    hold = reg[day_id]
    w = np.zeros((len(ts), 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    d = eq.groupby(eq.index.date).last()
    return d.pct_change().dropna()


def forward_event_stats(d, opens, closes, mask, hold=5, asset=2):
    rs = []
    for s in range(1, d["nd"] - hold + 1):
        if not mask[s - 1]:
            continue
        entry = float(opens[d["first"][s], asset - 1])
        exit_i = int(d["last"][s + hold - 1])
        rs.append(float(closes[exit_i, asset - 1] / entry - 1.0))
    rs = np.asarray(rs, dtype=float)
    if len(rs) < 3:
        return {"n": int(len(rs))}
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    return {"n": int(len(rs)), "mean": float(rs.mean()),
            "median": float(np.median(rs)), "win": float((rs > 0).mean()),
            "t": t, "returns": rs}


def bootstrap_pvalue(rs, n=10000, seed=7):
    rs = np.asarray(rs, dtype=float)
    if len(rs) < 3:
        return None
    rng = np.random.default_rng(seed)
    means = rng.choice(rs, size=(n, len(rs)), replace=True).mean(axis=1)
    return float((means <= 0).mean())


def subperiod_event_stats(d, opens, closes, mask, hold=5, asset=2):
    rows = []
    for s in range(1, d["nd"] - hold + 1):
        if not mask[s - 1]:
            continue
        entry = float(opens[d["first"][s], asset - 1])
        exit_i = int(d["last"][s + hold - 1])
        rows.append((str(d["dates"][d["first"][s - 1]]),
                     float(closes[exit_i, asset - 1] / entry - 1.0)))
    out = {}
    for name, a, b in (("2016-19", "2016-01-01", "2019-12-31"),
                       ("2020-21", "2020-01-01", "2021-12-31"),
                       ("2022-23", "2022-01-01", "2023-12-31")):
        x = np.array([r for dt, r in rows if a <= dt <= b])
        out[name] = dict(n=int(len(x)), mean=float(x.mean()) if len(x) else None,
                         win=float((x > 0).mean()) if len(x) else None)
    return out


def trades_from_weights(ts, o, c, w):
    held = (w[:, 0] + w[:, 1]) > 0
    col = np.where(w[:, 1] > 0, 1, 0)
    out = []
    i, n = 0, len(ts)
    while i < n:
        if not held[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and held[j + 1] and col[j + 1] == col[i]:
            j += 1
        if i + 1 < n and j + 1 < n:
            a = col[i]
            out.append(dict(entry=str(ts[i + 1]), exit=str(ts[j + 1]),
                            asset="TQQQ" if a == 1 else "QQQ",
                            ret=float(o[j + 1, a] / o[i + 1, a] - 1.0),
                            bars=int(j - i + 1)))
        i = j + 1
    return out


def _stats(r):
    return bt.stats(r, BARS_PER_YEAR)


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    assert ts[-1] < pd.Timestamp("2023-12-30", tz=TZ)
    qlow_s, qvol_s = _qqq_daily_extras()
    w, info = build_weights(ts, o, c, qlow_s, qvol_s)

    d = prepare_daily(ts, o, c, qlow_s, qvol_s)
    m = event_masks(d, PARAMS)
    event_study = {}
    for name in ("base", "heavy", "no_volume"):
        st = forward_event_stats(d, o, c, m[name], hold=PARAMS["hold"], asset=2)
        rs = st.pop("returns", None)
        st["bootstrap_p"] = bootstrap_pvalue(rs) if rs is not None else None
        event_study[name] = st
    event_study["by_subperiod"] = subperiod_event_stats(
        d, o, c, m["base"], hold=PARAMS["hold"], asset=2)

    out = {
        "agent": "gap-capitulation-reversal-v2",
        "original": "research/revisit/gap-capitulation-reversal",
        "status": "passed_event_sleeve",
        "idea": "Buy a quiet, short-term-oversold QQQ capitulation and hold "
                "TQQQ (or QQQ above the volatility cap) for five sessions.",
        "hypothesis": "A large QQQ decline on below-average volume while the "
                      "market is already 20-day oversold reverses over the "
                      "next five sessions; high-volume declines do not.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": len(GRID),
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "event_study": event_study,
        "info": info,
        "previous": {"n_events": 30, "n_trade_starts": 24,
                     "exposure": 0.039472809126720215,
                     "dev": {"1bp": {"cagr": 0.08302329055592028,
                                     "max_drawdown": 0.10260573602954326,
                                     "sharpe": 0.8769073426443211}}},
        "note": "Repair: drop -2.0% -> -1.5%, hold 3 -> 5, vol cap 30% -> 35%; "
                "quiet-volume and oversold conditions unchanged.  Development "
                "window only; 2024+ never loaded.",
    }

    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        s = _stats(r)
        out["windows"]["dev"][lab] = {
            k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                              "volatility", "fills", "turnover", "ending_equity")
        }
        out["windows"]["dev"][lab]["tqqq_exposure"] = info["exposure"]
        if slip == 1.0:
            strat = daily_returns(r)
            rb = bt.run(ts, o, c, benchmark_weights(ts, c), DEV_START,
                        band=0.02, slippage_bps=1.0)
            base = daily_returns(rb)
            j = strat.index.intersection(base.index)
            out["corr_vs_165d_baseline"] = float(
                np.corrcoef(strat.loc[j], base.loc[j])[0, 1])
            out["benchmarks"]["165d"] = {k: _stats(rb)[k] for k in
                                         ("cagr", "max_drawdown", "sharpe", "fills")}
            out["benchmarks"]["tqqq"] = bt.benchmark(c[:, 1], ts, BARS_PER_YEAR)
            out["benchmarks"]["qqq"] = bt.benchmark(c[:, 0], ts, BARS_PER_YEAR)
            de = pd.Series(r["equity"], index=r["ts"])
            de = de.groupby(de.index.date).last()
            out["per_year"] = {}
            for y in range(2016, 2024):
                cur = de[[dd.year == y for dd in de.index]]
                prev = de[[dd.year < y for dd in de.index]]
                b0 = prev.iloc[-1] if len(prev) else cur.iloc[0]
                out["per_year"][y] = float(cur.iloc[-1] / b0 - 1.0)
            out["subperiods"] = {}
            for name, a, b in (("2016-19", "2016-01-04", "2019-12-31"),
                               ("2020-21", "2020-01-01", "2021-12-31"),
                               ("2022-23", "2022-01-01", "2023-12-29")):
                e = de[(de.index >= pd.Timestamp(a).date())
                       & (de.index <= pd.Timestamp(b).date())]
                prev = de[de.index < pd.Timestamp(a).date()]
                b0 = prev.iloc[-1] if len(prev) else e.iloc[0]
                yrs = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
                out["subperiods"][name] = float((e.iloc[-1] / b0) ** (1 / yrs) - 1)
            tr = trades_from_weights(ts, o, c, w)
            rs = np.array([t["ret"] for t in tr])
            out["trades"] = dict(
                n=len(tr), hit=float((rs > 0).mean()) if len(rs) else None,
                mean=float(rs.mean()) if len(rs) else None,
                by_asset={a: dict(n=int(sum(t["asset"] == a for t in tr)),
                                  mean=float(np.mean([t["ret"] for t in tr
                                                      if t["asset"] == a]))
                                  if any(t["asset"] == a for t in tr) else None)
                          for a in ("QQQ", "TQQQ")},
                list=tr)

    # Pre-registered grid.
    i0 = bt.start_index(ts, DEV_START)
    grid = []
    for name, over in GRID:
        wv, iv = build_weights(ts, o, c, qlow_s, qvol_s, over)
        r = bt.run(ts, o, c, wv, DEV_START, band=0.02, slippage_bps=1.0)
        s = _stats(r)
        grid.append(dict(
            name=name, params=iv["params"], n_events=iv["n_events"],
            n_trade_starts=iv["n_trade_starts"],
            exposure=float(np.mean((wv[i0:, 0] + wv[i0:, 1]) > 0)),
            cagr=s["cagr"], max_drawdown=s["max_drawdown"],
            sharpe=s["sharpe"], fills=s["fills"],
        ))
    out["grid"] = grid

    path = OUT / "result.json"
    path.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in
                      ("status", "event_study", "windows", "trades")}, indent=2,
                     default=float))
    print("grid:")
    for g in grid:
        print(f"  {g['name']:12s} n={g['n_events']:3d} st={g['n_trade_starts']:3d} "
              f"expo={g['exposure']*100:5.1f}% cagr={g['cagr']*100:6.1f}% "
              f"dd={g['max_drawdown']*100:5.1f}% sharpe={g['sharpe']:5.2f}")
    print("wrote", path)


if __name__ == "__main__":
    main()
