"""Quiet oversold capitulation reversal — revisit rebuild.

Not the old 165-day overlay. The position is owned entirely by the event:

  event at the close of day d:
      (QQQ close-to-close <= -2% OR QQQ intraday low <= -3% vs prior close)
      AND event-day volume <= 1.2x the prior 20-day average
      AND QQQ 20-day return <= -3%

  entry at the open of day d+1, in TQQQ if QQQ 20-day realised vol <= 30%,
  otherwise in QQQ.  Hold 3 sessions.  Exit on the close of the third session,
  on a QQQ close below the event-day low, or on an 8% hard stop from entry.

No 100-250 day moving average is used by the strategy.  The 165-day baseline
is built only in benchmark_weights() for the correlation/benchmark table.

Backtests are currently paused; this file is the pre-registered implementation.
Run only when the lead/user authorises the test:

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/gap-capitulation-reversal/strategy.py
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
START10, START5, HOLDOUT_END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 390
OUT = Path(__file__).resolve().parent

# Pre-registered base parameters.  The neighbourhood is in SPEC.md.
PARAMS = dict(
    drop=0.020,
    intraday=0.030,
    rvol_max=1.20,
    oversold=0.030,
    hold=3,
    vol_max=0.30,
    hard_stop=0.08,
    event_low_stop=True,
    size=1.0,
)


# ----------------------------------------------------------------------------
# daily helpers
# ----------------------------------------------------------------------------
def daily_extras(ts):
    """QQQ daily low and volume, aligned to the panel's session dates."""
    q = bt.load_1m("QQQ")
    lo = pd.Timestamp(ts[0].date(), tz="America/New_York")
    hi = pd.Timestamp(ts[-1].date(), tz="America/New_York") + pd.Timedelta(days=1)
    q = q[(q["ts"] >= lo) & (q["ts"] < hi)].copy()
    q["date"] = q["date"].astype("datetime64[ns]")
    g = q.groupby("date")
    sess = pd.DatetimeIndex(sorted(set(pd.Timestamp(t.date()) for t in ts)))
    low = g["low"].min().reindex(sess).to_numpy()
    vol = g["volume"].sum().reindex(sess).to_numpy()
    return low, vol


def prepare_daily(ts, opens, closes, qlow, qvol):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    nd = len(first)
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
    day_id = np.repeat(np.arange(nd), np.diff(np.r_[first, len(ts)]))
    return dict(dates=dates, first=first, last=last, nd=nd,
                qo=qo, qc=qc, to=to, tc=tc, qlow=qlow, qvol=qvol,
                qret=qret, qdd=qdd, q20=q20, rvol=rvol, vol20=vol20,
                day_id=day_id)


# ----------------------------------------------------------------------------
# strategy
# ----------------------------------------------------------------------------
def event_masks(d, p):
    cap = (d["qret"] <= -p["drop"]) | (d["qdd"] <= -p["intraday"])
    quiet = d["rvol"] <= p["rvol_max"]
    oversold = d["q20"] <= -p["oversold"]
    finite = (np.isfinite(d["qret"]) & np.isfinite(d["qdd"])
              & np.isfinite(d["rvol"]) & np.isfinite(d["q20"])
              & np.isfinite(d["vol20"]))
    return dict(
        cap=cap, quiet=quiet, oversold=oversold, finite=finite,
        base=cap & quiet & oversold & finite,
        heavy=cap & (~quiet) & oversold & finite,
        no_volume=cap & oversold & finite,
    )


def build_weights(ts, opens, closes, qlow, qvol, params=None):
    """Return (weights (n,3), info).  See SPEC.md for the exact rules."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    d = prepare_daily(ts, opens, closes, qlow, qvol)
    nd, n = d["nd"], len(ts)

    ev = event_masks(d, p)["base"]

    pos = np.zeros(n, dtype=np.int8)          # 0 BIL, 1 QQQ, 2 TQQQ
    active_until = -1
    stop_low = np.nan
    asset = 0
    entry_px = np.nan
    event_dates = []
    trade_dates = []
    n_starts = 0
    n_event_low_stops = 0
    n_hard_stops = 0
    n_time_exits = 0

    for s in range(1, nd):
        # The event on s-1 is known at the close of s-1; act at the open of s.
        if ev[s - 1]:
            event_dates.append(str(d["dates"][d["first"][s - 1]]))
            was_active = s <= active_until
            active_until = max(active_until, (s - 1) + p["hold"])
            stop_low = d["qlow"][s - 1]
            asset = 2 if d["vol20"][s - 1] <= p["vol_max"] else 1
            f = int(d["first"][s])
            entry_px = float(opens[f, asset - 1])
            if not was_active:
                n_starts += 1
                trade_dates.append(str(d["dates"][f]))

        if s > active_until:
            continue

        f, l = int(d["first"][s]), int(d["last"][s])
        state = asset
        for i in range(f, l + 1):
            if state and p["event_low_stop"] and closes[i, 0] < stop_low:
                state = 0
                active_until = -1
                n_event_low_stops += 1
            elif state and closes[i, state - 1] < entry_px * (1.0 - p["hard_stop"]):
                state = 0
                active_until = -1
                n_hard_stops += 1
            pos[i] = state

        # Time exit: sell at the 15:59 open of the last held session.
        if s == active_until and state:
            if l - 1 > f:
                pos[l - 1] = 0
            pos[l] = 0
            active_until = -1
            n_time_exits += 1

    q = (pos == 1).astype(float) * p["size"]
    t = (pos == 2).astype(float) * p["size"]
    w = np.zeros((n, 3))
    w[:, 0] = q
    w[:, 1] = t
    w[:, 2] = 1.0 - q - t

    info = dict(
        params=p,
        n_events=len(event_dates),
        n_trade_starts=n_starts,
        n_event_low_stops=n_event_low_stops,
        n_hard_stops=n_hard_stops,
        n_time_exits=n_time_exits,
        event_dates=event_dates,
        trade_dates=trade_dates,
        exposure=float(np.mean(pos > 0)),
        qqq_share=float(np.mean(pos == 1)),
        tqqq_share=float(np.mean(pos == 2)),
    )
    return w, info


# ----------------------------------------------------------------------------
# benchmark only (not part of the strategy)
# ----------------------------------------------------------------------------
def benchmark_weights(ts, closes):
    """165-day baseline, used ONLY for the correlation column and benchmarks."""
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


def forward_event_stats(d, opens, closes, mask, hold=3, asset=2):
    """Raw TQQQ forward return per event: entry at next open, exit at close
    of the hold-th session.  Used for the event-study table and bootstrap."""
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


def placebo_event_stats(d, opens, closes, n_events, hold=3, n=1000, seed=11,
                        real_mean=None):
    """Random-event placebo for the event mean: same count and hold, random
    entry sessions.  Returns the placebo distribution and, if `real_mean` is
    given, the fraction of placebo draws at least as large."""
    if n_events < 3:
        return None
    rng = np.random.default_rng(seed)
    starts = rng.integers(1, d["nd"] - hold, size=(n, n_events))
    means = np.empty(n)
    for j in range(n):
        rs = []
        for s in starts[j]:
            entry = float(opens[d["first"][s], 1])
            exit_i = int(d["last"][s + hold - 1])
            rs.append(float(closes[exit_i, 1] / entry - 1.0))
        means[j] = float(np.mean(rs))
    out = {"n_draws": int(n), "placebo_mean": float(means.mean()),
           "placebo_std": float(means.std(ddof=1)),
           "p95": float(np.quantile(means, 0.95))}
    if real_mean is not None:
        out["p_value"] = float((means >= real_mean).mean())
    return out


# ----------------------------------------------------------------------------
# evaluation
# ----------------------------------------------------------------------------
def window_metrics(ts, opens, closes, weights, start, slip):
    r = bt.run(ts, opens, closes, weights, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    eq = r["equity"]
    peak = np.maximum.accumulate(eq)
    s["max_drawdown"] = float(-(eq / peak - 1.0).min())
    return r, s


def main():
    # Dev only. The lead runs the 10y/5y/holdout on the frozen file.
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    qlow, qvol = daily_extras(ts)
    w, info = build_weights(ts, o, c, qlow, qvol, PARAMS)

    d = prepare_daily(ts, o, c, qlow, qvol)
    m = event_masks(d, PARAMS)
    out_event = {}
    for name in ("base", "heavy", "no_volume"):
        st = forward_event_stats(d, o, c, m[name], hold=PARAMS["hold"], asset=2)
        rs = st.pop("returns", None)
        st["bootstrap_p"] = bootstrap_pvalue(rs) if rs is not None else None
        out_event[name] = st
    placebo = placebo_event_stats(d, o, c, out_event["base"].get("n", 0),
                                  hold=PARAMS["hold"],
                                  real_mean=out_event["base"].get("mean"))

    out = {
        "agent": "gap-capitulation-reversal",
        "original": "research/agents2/gap-capitulation-reversal",
        "status": None,  # set below; the lead may override after audit
        "idea": "Buy a quiet, short-term-oversold capitulation in QQQ, not a "
                "generic gap-down in a 165-day bull regime.",
        "hypothesis": "A large QQQ decline on below-average volume while the "
                      "market is already 20-day oversold reverses over the "
                      "next 3 sessions; high-volume declines do not.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,  # no git repo in this workspace; lead commits
        "variants_tried": 23,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "event_study": out_event,
        "placebo": placebo,
        "info": info,
    }

    corr = None
    for slip, lab in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r, s = window_metrics(ts, o, c, w, DEV_START, slip)
        out["windows"]["dev"][lab] = {
            "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "ending_equity": s["ending_equity"],
        }
        if slip == 1.0:
            strat_ret = daily_returns(r)
            bw = benchmark_weights(ts, c)
            rb, _ = window_metrics(ts, o, c, bw, DEV_START, 1.0)
            base_ret = daily_returns(rb)
            j = strat_ret.index.intersection(base_ret.index)
            corr = float(np.corrcoef(strat_ret.loc[j], base_ret.loc[j])[0, 1])
            out["corr_vs_165d_baseline"] = corr
            out["benchmarks"]["original"] = _load_original()
            out["benchmarks"]["tqqq"] = bt.benchmark(c[:, 1], ts, BARS_PER_YEAR)
            out["benchmarks"]["qqq"] = bt.benchmark(c[:, 0], ts, BARS_PER_YEAR)
            out["benchmarks"]["spy"] = _spy_benchmark()

    dev = out["windows"]["dev"]["1bp"]
    out["status"] = ("passed" if dev["cagr"] >= 0.03 and dev["sharpe"] >= 0.30
                     else "retired_overlay_only")

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in
                      ("status", "corr_vs_165d_baseline", "windows")}, indent=2))
    print("wrote", OUT / "result.json")


def _load_original():
    p = ROOT / "research" / "agents2" / "gap-capitulation-reversal" / "result.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        cs = d.get("cost_sensitivity", {})
        key = "standalone_event_qgap_1.5_1d_stop4"
        return {"strategy": "original standalone gap <= -1.5%, 1-day, 4% stop",
                "cost_sensitivity": cs.get(key), "all_variants": list(cs.keys())}
    except Exception:
        return None


def _spy_benchmark():
    p = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= pd.Timestamp(DEV_START))
            & (df["date"] <= pd.Timestamp(DEV_END))]
    if len(df) < 2:
        return None
    px = df["adjclose"].to_numpy()
    years = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    peak = np.maximum.accumulate(px)
    rets = np.diff(px) / px[:-1]
    return {"cagr": float((px[-1] / px[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(px / peak - 1).min()),
            "volatility": float(np.std(rets) * np.sqrt(252)),
            "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(252)),
            "marks": "daily", "note": "SPY daily is benchmark-only per SOURCE.md"}


if __name__ == "__main__":
    main()
