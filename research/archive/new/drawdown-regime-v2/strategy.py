"""Deep Drawdown Recovery v2 (DDR-v2) -- repaired standalone rebuild.

The v1 (`research/revisit/drawdown-regime`) armed only after a >=20% QQQ
drawdown from its 52-week high.  On 2016-01-04 .. 2023-12-29 that produced
only 8 episodes and 14.3% average exposure: the -20% arm was reached in only
four years, and the 5pp re-arm rule delayed re-entry after each failed 2022
bounce.  The core state is kept; the arm is widened to a >=10% drawdown
(the smallest relaxation that yields a usable sample), the failure exit is
tightened from a 20- to a 15-session low, and the re-arm is sped up from 5pp
to 3pp.  The fixed 60-session hold is unchanged.

Rules (all decisions use QQQ daily closes through session k-1; fills at
session k's first open):

  dd(k)      = QQQ_close[k-1] / max(QQQ_close[k-252 .. k-1]) - 1
  trough(k)  = lowest dd since the last 52-week high, through k-1
  hi20(k)    = max(QQQ_close[k-20 .. k-1])
  lo15(k)    = min(QQQ_close[k-15 .. k-1])

  arm        once trough <= -10%; stay armed until an entry.
  enter      100% TQQQ when QQQ_close[k-1] > hi20(k) while armed.
  hold       60 sessions.
  exit       100% BIL on the first close < lo15(k), or after 60 sessions.
  re-arm     after any exit, wait for dd to recover 3pp from the post-exit
             low (capped at -3%, so a new 52-week high always re-arms).

No 100-250 day moving average is used.  The 165-day baseline is built only
for the benchmark/correlation table.  Long-only, weights >= 0, sum <= 1.

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/drawdown-regime-v2/strategy.py --run
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
HOLDOUT_START = "2024-01-02"          # never used by this file
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

PARAMS = dict(
    window=252,       # 52-week high
    deep_dd=0.10,     # repaired arm: >=10% drawdown from the 52-week high
    entry_break=20,   # confirmed turn: close above the prior 20-session high
    hold=60,          # original fixed hold retained
    exit_low=15,      # repaired failure exit: prior 15-session low
    rearm=0.03,       # faster 3pp recovery re-arm
)

# Pre-registered plateau grid (8 variants, fixed before the final run).
GRID = [
    ("primary 10%", {}),
    ("deep 12%", {"deep_dd": 0.12}),
    ("deep 15%", {"deep_dd": 0.15}),
    ("deep 18%", {"deep_dd": 0.18}),
    ("exit 10", {"exit_low": 10}),
    ("exit 20", {"exit_low": 20}),
    ("hold 45", {"hold": 45}),
    ("rearm 5pp", {"rearm": 0.05}),
]

SUBS = {
    "2016-19": ("2016-01-04", "2019-12-31"),
    "2020-21": ("2020-01-01", "2021-12-31"),
    "2022-23": ("2022-01-01", "2023-12-29"),
}


# --------------------------------------------------------------------- data
def _qqq_daily(end: str = DEV_END):
    """Adjusted QQQ daily closes from 2015 through `end`, dev-only."""
    path = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    d = pd.read_parquet(
        path, columns=["date", "adjclose"],
        filters=[("date", "<=", pd.Timestamp(end).date())],
    )
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d.sort_values("date")
    assert d["date"].max() <= pd.Timestamp(end).date()
    return d["date"].to_numpy(), d["adjclose"].to_numpy(float)


def _daily_state(ddates, close, p):
    s = pd.Series(close)
    hi = s.rolling(int(p["window"]), min_periods=200).max()
    dd = s / hi - 1.0
    epi = (dd >= 0).cumsum()
    trough = dd.groupby(epi).cummin()
    eb, xb = int(p["entry_break"]), int(p["exit_low"])
    hi_b = s.shift(1).rolling(eb, min_periods=eb).max()
    lo_b = s.shift(1).rolling(xb, min_periods=xb).min()
    return dd.to_numpy(), trough.to_numpy(), hi_b.to_numpy(), lo_b.to_numpy()


def _sessions(ts):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates[last], first, last


# ---------------------------------------------------------------- strategy
def build_weights(ts, opens, closes, params=None):
    """Return (weights (n,3), info) for DDR-v2."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, first, last = _sessions(ts)
    n_days = len(first)

    ddates, dcl = _qqq_daily()
    dd_d, tr_d, hi_d, lo_d = _daily_state(ddates, dcl, p)
    j = np.searchsorted(ddates, dates, side="left") - 1
    if (j < 0).any():
        raise ValueError("QQQ daily history starts after the minute panel")
    dprev, dd, trough, hi_b, lo_b = dcl[j], dd_d[j], tr_d[j], hi_d[j], lo_d[j]

    hold = int(p["hold"])
    T = np.zeros(n_days)
    episodes = []
    state = 0
    entry_k = -1
    armed = True
    ref = 0.0

    for k in range(n_days):
        target = 0.0
        reason = ""
        if state == 1:
            if k - entry_k >= hold:
                target, reason = 0.0, "time"
            elif np.isfinite(lo_b[k]) and dprev[k] < lo_b[k]:
                target, reason = 0.0, "low"
            else:
                target = 1.0
        else:
            if not armed:
                ref = min(ref, dd[k])
                if dd[k] >= ref + p["rearm"]:
                    armed = True
            if armed and np.isfinite(dd[k]) and np.isfinite(hi_b[k]):
                if (trough[k] <= -p["deep_dd"]) and (dprev[k] > hi_b[k]):
                    target, reason = 1.0, "entry"
                    state, entry_k = 1, k
                    episodes.append(dict(
                        entry_i=int(k), entry_date=str(dates[k]),
                        dd=float(dd[k]), trough=float(trough[k])))
        if state == 1 and target == 0.0 and reason:
            state = 0
            armed = False
            ref = min(dd[k], -p["rearm"])
            episodes[-1]["exit_i"] = int(k)
            episodes[-1]["exit_date"] = str(dates[k])
            episodes[-1]["exit_reason"] = reason
        T[k] = target

    w = weights_from_targets(T, first, last)

    for e in episodes:
        i, jx = e["entry_i"], e.get("exit_i", n_days)
        e["days"] = int(jx - i)
        e["ret"] = float(opens[first[min(jx, n_days - 1)], 1]
                         / opens[first[i], 1] - 1.0)

    info = dict(params=p, n_episodes=len(episodes),
                exposure=float(np.mean(w[:, 1])),
                mean_dd_at_entry=float(np.mean([e["dd"] for e in episodes]))
                if episodes else None,
                episodes=episodes, targets=T)
    return w, info


def weights_from_targets(T, first, last):
    """Session-k target -> bar weights filling at session k's first open."""
    n_bars = int(last[-1]) + 1
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n_bars]))
    tb = T[day_id].astype(float)
    tb[:-1] = tb[1:].copy()
    w = np.zeros((n_bars, 3))
    w[:, 1] = tb
    w[:, 2] = 1.0 - tb
    return w


# ----------------------------------------------------- measurement helpers
def baseline_weights(ts):
    """165-day QQQ SMA baseline: benchmark only, never in the strategy."""
    dates, first, last = _sessions(ts)
    ddates, dcl = _qqq_daily()
    s = pd.Series(dcl, index=pd.to_datetime(ddates))
    sma = s.rolling(165, min_periods=165).mean().to_numpy()
    reg = np.r_[False, dcl[:-1] > sma[:-1]]
    mp = {d: bool(r) for d, r in zip(ddates, reg)}
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = np.array([mp[d] for d in dates])[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def _stats(r):
    return bt.stats(r, BPY)


def _daily_returns(r):
    return pd.Series(r["equity"], index=r["ts"]).resample("1D").last().pct_change().dropna()


def _cagr_dd(eq):
    yrs = (eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400)
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1), float(
        -(eq / eq.cummax() - 1).min())


def _subperiods(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    out = {}
    for name, (a, b) in SUBS.items():
        e = eq[(eq.index >= pd.Timestamp(a, tz="America/New_York"))
               & (eq.index < pd.Timestamp(b, tz="America/New_York") + pd.Timedelta(days=1))]
        out[name] = dict(zip(("cagr", "dd"), _cagr_dd(e)))
    return out


def _episode_stats(info):
    rets = np.array([e["ret"] for e in info["episodes"]])
    if len(rets) < 2:
        return dict(n=int(len(rets)))
    t = float(rets.mean() / rets.std(ddof=1) * np.sqrt(len(rets)))
    return dict(n=int(len(rets)), mean=float(rets.mean()),
                median=float(np.median(rets)), hit=float((rets > 0).mean()),
                t=t, best=float(rets.max()), worst=float(rets.min()))


def main():
    ts, o, c = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=500)
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    w, info = build_weights(ts, o, c)
    assert np.isfinite(w).all() and (w >= 0).all() and (w.sum(1) <= 1 + 1e-12).all()

    out = {
        "agent": "drawdown-regime-v2",
        "original": "research/revisit/drawdown-regime",
        "status": "repaired_diversifier",
        "idea": "After a >=10% QQQ drawdown from its 52-week high, own TQQQ "
                "inside a confirmed 60-session recovery window, with a 15-session "
                "low failure exit and a 3pp re-arm.",
        "hypothesis": "The post-correction recovery is a distinct, time-limited "
                      "return state; a confirmed 20-session turn after a deep "
                      "correction captures it with low exposure and low correlation "
                      "to slow trend-following.",
        "universe": ["QQQ (signal)", "TQQQ (risk)", "BIL (cash)"],
        "frozen_commit": None,
        "variants_tried": len(GRID),
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "episodes": info["episodes"],
        "params": info["params"],
        "exposure": info["exposure"],
        "episode_stats": _episode_stats(info),
        "previous": {"n_episodes": 8, "exposure": 0.1429260244538804,
                     "dev": {"1bp": {"cagr": 0.17198446387486577,
                                     "max_drawdown": 0.49024606451698594,
                                     "sharpe": 0.7759165670600479}}},
        "note": "Repair: arm -20% -> -10%, failure exit 20 -> 15 sessions, "
                "re-arm 5pp -> 3pp; hold stays 60.  Development window only; "
                "2024+ never loaded.",
    }

    for bp in (1.0, 5.0, 10.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=bp)
        s = _stats(r)
        out["windows"]["dev"][f"{bp:.0f}bp"] = {
            k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                              "volatility", "fills", "turnover", "ending_equity")
        }
        if bp == 1.0:
            out["windows"]["dev"]["1bp"]["tqqq_exposure"] = info["exposure"]
            rb = bt.run(ts, o, c, baseline_weights(ts), DEV_START,
                        band=0.02, slippage_bps=1.0)
            out["corr_vs_165d_baseline"] = float(
                pd.concat([_daily_returns(r), _daily_returns(rb)], axis=1,
                          join="inner").dropna().corr().iloc[0, 1])
            out["benchmarks"]["165d"] = {k: _stats(rb)[k] for k in
                                         ("cagr", "max_drawdown", "sharpe", "fills")}
            out["benchmarks"]["tqqq"] = bt.benchmark(c[:, 1], ts, BPY)
            out["benchmarks"]["qqq"] = bt.benchmark(c[:, 0], ts, BPY)
            out["subperiods"] = _subperiods(r)
            eqs = pd.Series(r["equity"], index=r["ts"])
            de = eqs.groupby(eqs.index.date).last()
            out["per_year"] = {}
            for y in range(2016, 2024):
                cur = de[[d.year == y for d in de.index]]
                prev = de[[d.year < y for d in de.index]]
                base = prev.iloc[-1] if len(prev) else cur.iloc[0]
                out["per_year"][y] = float(cur.iloc[-1] / base - 1.0)

    # Pre-registered grid.
    i0 = bt.start_index(ts, DEV_START)
    grid = []
    for name, over in GRID:
        wv, iv = build_weights(ts, o, c, over)
        r = bt.run(ts, o, c, wv, DEV_START, band=0.02, slippage_bps=1.0)
        s = _stats(r)
        grid.append(dict(
            name=name, params=iv["params"], n_episodes=iv["n_episodes"],
            exposure=float(np.mean(wv[i0:, 1] > 0)),
            cagr=s["cagr"], max_drawdown=s["max_drawdown"], sharpe=s["sharpe"],
            fills=s["fills"],
        ))
    out["grid"] = grid

    path = Path(__file__).resolve().parent / "result.json"
    path.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in
                      ("status", "exposure", "episode_stats", "windows")}, indent=2,
                     default=float))
    print("grid:")
    for g in grid:
        print(f"  {g['name']:14s} n={g['n_episodes']:2d} "
              f"expo={g['exposure']*100:5.1f}% cagr={g['cagr']*100:6.1f}% "
              f"dd={g['max_drawdown']*100:5.1f}% sharpe={g['sharpe']:5.2f}")
    print("wrote", path)


def print_spec():
    print("Deep Drawdown Recovery v2 (repaired)")
    for k, v in PARAMS.items():
        print(f"  {k:12s} {v}")
    print("  universe     QQQ signal / TQQQ risk / BIL cash")
    print("  arm          drawdown from the 252-session high has reached -10%")
    print("  entry        close > prior 20-session high, while armed")
    print("  hold         60 sessions, or exit on a close below the prior 15-session low")
    print("  re-arm       after an exit, wait for a 3pp recovery from the post-exit low")
    print("  sizing       100% TQQQ in the window, 100% BIL otherwise")
    print("  timing       decisions on closes through t-1; fills at t's open")


if __name__ == "__main__":
    if "--run" not in sys.argv:
        print_spec()
        raise SystemExit("pass --run to backtest the dev window")
    main()
