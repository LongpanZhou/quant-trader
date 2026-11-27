"""Post-Capitulation Session Reversal (PCSR).

Standalone rebuild of `intraday-mean-reversion` for research/revisit.

WHAT IS GENUINELY NEW
---------------------
The original strategy was a daily QQQ>SMA165 trend base with a 3% intraday
stop. The only non-trend effect inside it was the *re-entry*: after a >=3%
intraday QQQ drawdown the rest of that session does not recover (+0.13%), the
overnight gap is weak (-0.69% in the regime-on sample), and the *next* session's
open-to-close is strongly positive (+1.17% TQQQ).  That effect is the whole
strategy here.

This rebuild is not the old base minus the MA gate.  It holds TQQQ for
approximately 4-5% of sessions instead of ~78%, never holds overnight, and its
return driver is liquidity provision after forced selling, not trend.  There is
no moving-average gate on QQQ/TQQQ/SPY/NDX of any length.

RULES
-----
1. Sessions are regular-session days of the 1-minute panel (half days included,
   indexed by bar, not by clock time).
2. Signal: for each session k, dd_k = min over the session's 1-minute QQQ
   closes of (QQQ_t / QQQ_prev_session_close - 1).  If dd_k <= -3.0% the session
   is an event session.  The event is fully known at that session's 15:59 close.
3. Position: at the open of session k+1, buy TQQQ with 100% of equity; sell at
   the open of the final bar of session k+1 (≈15:59), i.e. exit before the
   close.  The position is never held overnight.
4. Otherwise hold BIL.  No stop, no leverage beyond TQQQ, no pyramiding.
5. Consecutive events are separate one-session trades: the book goes flat
   between the close of one held session and the open of the next.

NO LOOK-AHEAD
-------------
- The event uses only bars of session k; the weight that acts on it is set at
  session k's last bar and filled at session k+1's first bar open.
- The exit weight is set at session k+1's second-to-last bar and filled at the
  final bar's open (15:59), never at that bar's close.
- No 165-day (or any 100-250 day) moving average is used anywhere.

Run (only after the user authorises backtests):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/intraday-mean-reversion/strategy.py
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
W10_START, W5_START, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_1M = 252 * 390
OUT = Path(__file__).resolve().parent
ORIGINAL = "research/agents/intraday-mean-reversion"


# ---------------------------------------------------------------------------
# sessions and signal
# ---------------------------------------------------------------------------
def session_bounds(ts: pd.DatetimeIndex):
    """First/last bar index of every regular-session day."""
    d = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, d[1:] != d[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return d, first, last


def session_features(ts: pd.DatetimeIndex, closes: np.ndarray):
    """Per-session previous close, intraday drawdown and 20-day volatility."""
    d, first, last = session_bounds(ts)
    nd = len(first)
    qqq = closes[:, 0]
    prev = np.full(nd, np.nan)
    prev[1:] = qqq[last[:-1]]

    dd = np.full(len(ts), np.nan)
    for k in range(nd):
        a, b = first[k], last[k] + 1
        dd[a:b] = qqq[a:b] / prev[k] - 1.0
    dmin = np.array([np.nanmin(dd[first[k]:last[k] + 1]) for k in range(nd)])

    qclose = np.array([qqq[last[k]] for k in range(nd)])
    dret = np.full(nd, np.nan)
    dret[1:] = qclose[1:] / qclose[:-1] - 1.0
    s = pd.Series(dret)
    sigma20 = s.rolling(20, min_periods=10).std(ddof=0).to_numpy()
    sigma20 = np.r_[np.nan, sigma20[:-1]]  # known at the prior session's close

    return dict(d=d, first=first, last=last, nd=nd, prev=prev, dd=dd,
                dmin=dmin, qclose=qclose, sigma20=sigma20)


def build_weights(ts: pd.DatetimeIndex, opens: np.ndarray, closes: np.ndarray,
                  threshold: float = 0.03, asset: int = 1, size: float = 1.0,
                  vol_target: float | None = None, cluster_cap: int | None = None,
                  stop: float | None = None, signal_rule: str = "1min"):
    """Return (weights, info) for the PCSR strategy.

    threshold   : QQQ intraday drawdown that defines a capitulation session.
    asset       : 1 = TQQQ, 0 = QQQ.
    vol_target  : optional daily vol target; size = min(1, vol_target/sigma20).
    cluster_cap : optional; halve size if another event occurred within this
                  many sessions before the current one.
    stop        : optional intraday stop on the held session (fraction).
    """
    n = len(ts)
    F = session_features(ts, closes)
    nd, first, last = F["nd"], F["first"], F["last"]

    event = np.zeros(nd, dtype=bool)
    event[1:] = F["dmin"][1:] <= -threshold

    sess_w = np.zeros(nd)
    for k in range(1, nd):
        if not event[k - 1]:
            continue
        w = size
        if vol_target is not None and np.isfinite(F["sigma20"][k]) and F["sigma20"][k] > 0:
            w *= min(1.0, vol_target / F["sigma20"][k])
        if cluster_cap is not None:
            lo = max(0, (k - 1) - cluster_cap)
            if event[lo:k - 1].any():
                w *= 0.5
        sess_w[k] = w

    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    for k in range(nd):
        a, b = first[k], last[k]
        if sess_w[k] > 0:
            # held during the session; exit at the final bar's open (≈15:59)
            w[a:b - 1, asset] = sess_w[k]
            w[b - 1, asset] = 0.0
        nxt = sess_w[k + 1] if k + 1 < nd else 0.0
        w[b, asset] = nxt
    w[:, 2] = np.clip(1.0 - w[:, 0] - w[:, 1], 0.0, 1.0)

    if stop is not None:
        for k in range(nd):
            if sess_w[k] <= 0:
                continue
            a, b = first[k], last[k]
            seg = F["dd"][a:b + 1]
            idx = np.flatnonzero(seg <= -stop)
            if len(idx):
                j = a + int(idx[0])
                w[j:b, asset] = 0.0
                w[j:b, 2] = 1.0
    w[-1] = (0.0, 0.0, 1.0)
    w[:, 2] = np.clip(1.0 - w[:, 0] - w[:, 1], 0.0, 1.0)

    info = {
        "threshold": threshold,
        "asset": "TQQQ" if asset == 1 else "QQQ",
        "sessions": int(nd),
        "event_sessions": int(event.sum()),
        "event_dates": [str(F["d"][k]) for k in np.flatnonzero(event)],
        "held_sessions": int((sess_w > 0).sum()),
    }
    return w, info


# ---------------------------------------------------------------------------
# benchmarks / correlation helpers
# ---------------------------------------------------------------------------
def correlation_baseline_weights(ts: pd.DatetimeIndex, closes: np.ndarray) -> np.ndarray:
    """The old 165-day QQQ>SMA base. Used only to measure correlation."""
    F = session_features(ts, closes)
    nd, first, last, qclose = F["nd"], F["first"], F["last"], F["qclose"]
    sma = pd.Series(qclose).rolling(165).mean()
    reg = (pd.Series(qclose) > sma).astype(float).fillna(0.0).to_numpy()
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for k in range(nd):
        a, b = first[k], last[k]
        r = reg[k - 1] if k > 0 else 0.0
        w[a:b + 1, 1] = r
        w[a:b + 1, 2] = 1.0 - r
    w[-1] = (0.0, 0.0, 1.0)
    return w


def daily_returns(result: dict) -> pd.Series:
    return bt.daily_last(result["equity"], pd.DatetimeIndex(result["ts"])).pct_change().dropna()


def daily_marked(result: dict) -> dict:
    eq = pd.Series(result["equity"], index=pd.DatetimeIndex(result["ts"]))
    cash = pd.Series(result["cash"], index=pd.DatetimeIndex(result["ts"]))
    last = eq.groupby(eq.index.date).last()
    lastc = cash.groupby(cash.index.date).last()
    tt = pd.DatetimeIndex([pd.Timestamp(x, tz="America/New_York") for x in last.index])
    return bt.stats({"equity": last.to_numpy(), "cash": lastc.to_numpy(), "fills": 0,
                     "turnover": 0.0, "ts": tt}, 252)


def window_bounds(ts, start, end):
    """Equity starts at the 15:59 mark of `start` (matches the original)."""
    i0 = int(np.flatnonzero(bt.session_dates(ts) == pd.Timestamp(start).date())[-1])
    i1 = int(np.flatnonzero(bt.session_dates(ts) == pd.Timestamp(end).date())[-1])
    return i0, i1


def run_window(ts, o, c, w, start, end, slip):
    i0, i1 = window_bounds(ts, start, end)
    res = bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1], w[i0:i1 + 1],
                      band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M), i0, i1


# ---------------------------------------------------------------------------
# event statistics and bootstrap
# ---------------------------------------------------------------------------
def event_returns(ts, o, c, threshold=0.03, asset=1):
    """TQQQ (or QQQ) next-session open->close return for each event, plus dates."""
    F = session_features(ts, c)
    nd, first, last = F["nd"], F["first"], F["last"]
    ev = np.flatnonzero(np.r_[False, F["dmin"][1:] <= -threshold])
    out = []
    for k in ev:
        if k + 1 >= nd:
            continue
        r = c[last[k + 1], asset] / o[first[k + 1], asset] - 1.0
        out.append((str(F["d"][k]), float(r)))
    return out


def cluster_bootstrap(rows, n_boot=5000, seed=7):
    """One-sided bootstrap over event clusters (gap > 7 calendar days = new cluster)."""
    if not rows:
        return None
    dates = [pd.Timestamp(r[0]) for r in rows]
    rets = np.array([r[1] for r in rows], float)
    cid = np.zeros(len(rows), int)
    for i in range(1, len(rows)):
        cid[i] = cid[i - 1] + (1 if (dates[i] - dates[i - 1]).days > 7 else 0)
    rng = np.random.default_rng(seed)
    uc = np.unique(cid)
    means = []
    for _ in range(n_boot):
        pick = rng.choice(uc, size=len(uc), replace=True)
        vals = np.concatenate([rets[cid == p] for p in pick])
        means.append(vals.mean())
    means = np.array(means)
    return {
        "n_events": int(len(rets)),
        "n_clusters": int(len(uc)),
        "mean": float(rets.mean()),
        "median": float(np.median(rets)),
        "win_rate": float((rets > 0).mean()),
        "p_mean_le_0": float((means <= 0).mean()),
        "ci95": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
    }


def spy_daily_check(threshold=0.03):
    """Out-of-universe validation on SPY daily low/prev-close (no 1m needed)."""
    path = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    factor = df["adjclose"] / df["close"]
    for col in ("open", "high", "low", "close"):
        df[col] = df[col] * factor
    prev = df["close"].shift(1)
    dd = df["low"] / prev - 1.0
    nxt = df["close"].shift(-1) / df["open"].shift(-1) - 1.0
    m = dd <= -threshold
    return {
        "threshold": threshold,
        "n": int(m.sum()),
        "mean_next_session": float(nxt[m].mean()),
        "win_rate": float((nxt[m] > 0).mean()),
        "start": str(df["date"].iloc[0].date()),
        "end": str(df["date"].iloc[-1].date()),
    }


# ---------------------------------------------------------------------------
def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, END, "1min")
    w, info = build_weights(ts, o, c, threshold=0.03, asset=1)

    base_w = correlation_baseline_weights(ts, c)  # measurement only: never used for positions
    windows = {
        "dev": (DEV_START, DEV_END, (1.0, 5.0, 10.0)),
        "10y": (W10_START, END, (1.0, 5.0)),
        "5y": (W5_START, END, (1.0, 5.0)),
    }
    out = {
        "agent": "intraday-mean-reversion",
        "original": ORIGINAL,
        "status": "pending_audit",
        "idea": "After a >=3% intraday QQQ capitulation, buy TQQQ at the next open and sell before that session's close; flat (BIL) and never overnight otherwise.",
        "hypothesis": "A capitulation session transfers stock from forced sellers to liquidity providers; the compensation is realised in the next session's open-to-close, not in the trigger session or its overnight gap.",
        "universe": ["QQQ", "TQQQ", "BIL", "SPY (daily validation/benchmark only)"],
        "frozen_commit": None,
        "variants_tried": 12,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": {}, "10y": {}, "5y": {}},
        "marks": "1m",
        "benchmarks": {},
        "event_study": {},
        "correlation": {},
        "spy_validation": {},
        "notes": "Backtests paused by user instruction on 2026-11-26. This file is generated only when authorised.",
    }

    corr = float("nan")
    for name, (start, end, slips) in windows.items():
        for slip in slips:
            res, s, i0, i1 = run_window(ts, o, c, w, start, end, slip)
            dm = daily_marked(res)
            out["windows"][name][f"{slip:.0f}bp"] = {
                "cagr": round(float(s["cagr"]), 6),
                "max_drawdown": round(float(s["max_drawdown"]), 6),
                "max_drawdown_daily": round(float(dm["max_drawdown"]), 6),
                "sharpe": round(float(s["sharpe"]), 4),
                "fills": int(s["fills"]),
                "turnover": round(float(s["turnover"]), 1),
                "years": round(float(s["years"]), 3),
                "ending_equity": round(float(s["ending_equity"]), 2),
            }
        if name == "dev":
            # benchmarks on dev (buy and hold, 15:59 start/end)
            i0, i1 = window_bounds(ts, start, end)
            out["benchmarks"]["tqqq"] = {
                "cagr": round(float(bt.benchmark(c[i0:i1 + 1, 1], ts[i0:i1 + 1], BARS_1M)["cagr"]), 6),
                "max_drawdown": round(float(bt.benchmark(c[i0:i1 + 1, 1], ts[i0:i1 + 1], BARS_1M)["max_drawdown"]), 6),
            }
            out["benchmarks"]["qqq"] = {
                "cagr": round(float(bt.benchmark(c[i0:i1 + 1, 0], ts[i0:i1 + 1], BARS_1M)["cagr"]), 6),
                "max_drawdown": round(float(bt.benchmark(c[i0:i1 + 1, 0], ts[i0:i1 + 1], BARS_1M)["max_drawdown"]), 6),
            }
            # correlation with the old 165-day base
            r_strat = daily_returns(res)
            r_base = daily_returns(bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1],
                                               base_w[i0:i1 + 1], band=0.02, slippage_bps=1.0))
            j = r_strat.index.intersection(r_base.index)
            corr = float(np.corrcoef(r_strat.loc[j], r_base.loc[j])[0, 1])
            out["corr_vs_165d_baseline"] = round(corr, 4)
            out["correlation"] = {"n_days": int(len(j)), "corr": round(corr, 4)}

    rows = event_returns(ts, o, c, threshold=0.03)
    out["event_study"] = cluster_bootstrap(rows)
    out["event_study"]["events"] = [{"date": d, "next_session": r} for d, r in rows]
    out["spy_validation"] = {"spy_3pct": spy_daily_check(0.03), "spy_2pct": spy_daily_check(0.02)}

    # original numbers, copied from the original result.json (not re-run)
    out["benchmarks"]["original"] = {
        "10y": {"cagr": 0.50957, "max_drawdown": 0.448296},
        "5y": {"cagr": 0.355048, "max_drawdown": 0.362866},
    }
    out["info"] = info

    # pre-registered status rule
    dev = out["windows"].get("dev", {}).get("1bp", {})
    ev = out["event_study"]
    passed = bool(dev.get("cagr", -1) > 0 and corr < 0.60 and ev.get("p_mean_le_0", 1) < 0.10)
    out["status"] = "passed" if passed else "rejected"

    (OUT / "result.json").write_text(json.dumps(out, indent=2))
    print("wrote", OUT / "result.json")
    print(json.dumps({k: out["windows"][k].get("1bp") for k in ("dev", "10y", "5y")}, indent=2))
    print("corr vs 165d base:", out["corr_vs_165d_baseline"])
    print("event study:", {k: out["event_study"][k] for k in ("n_events", "n_clusters", "mean", "win_rate", "p_mean_le_0")})


if __name__ == "__main__":
    main()
