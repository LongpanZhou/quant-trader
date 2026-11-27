"""Standalone rebuild: Opening-Range Failed-Breakdown Reclaim (long-only).

Research area: opening-range behaviour.  This is NOT the old overlay.

Old strategy (agents/opening-range-breakout): buy the first close ABOVE the
30-minute opening-range high, stop at the range low, then HOLD OVERNIGHT for
weeks while QQQ is above its 165-day SMA.

This rebuild: wait for price to break BELOW the 30-minute opening-range low,
then reclaim it (a failed breakdown / liquidity sweep).  Buy the reclaim,
stop at the sweep low, target the opposite side of the range, exit by the
close.  Long-only, intraday-only, QQQ, no moving-average gate of any kind.
Position size is a fixed fractional risk budget, not the old 100% TQQQ base.

Backtests are PAUSED by the lead.  This file is a complete, runnable spec but
has not been executed.  `main()` is development-only by default (2016-01-04 ..
2023-12-29); the holdout is the lead's single run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # research/
REPO = Path(__file__).resolve().parents[3]          # repo root
sys.path.insert(0, str(REPO / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390

CFG = dict(
    or_min=30,               # opening-range minutes (09:30-09:59)
    break_buffer_bps=5.0,    # trade must pierce ORL by this much
    reclaim_buffer_bps=5.0,  # close must recover above ORL by this much
    reclaim_window=30,       # max bars between the breakdown and the reclaim
    entry_cutoff_bars=30,    # no entries in the last 30 minutes
    target="orh",            # orh | mid | eod
    min_reward_r=1.0,        # require (ORH-entry) >= min_reward_r * risk
    risk_per_trade=0.005,    # 0.50% of equity at the stop
    max_weight=1.0,
    asset="QQQ",             # primary QQQ; TQQQ is a leverage sensitivity
)


# ---------------------------------------------------------------------------
# data / session helpers
# ---------------------------------------------------------------------------
def load_dev(start=DEV_START, end=DEV_END):
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), start, end, "1min")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("QQQ"), prep("TQQQ"), prep("BIL")


def sessions(ts):
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return dates, starts, ends


# ---------------------------------------------------------------------------
# strategy
# ---------------------------------------------------------------------------
def build_weights(ts, opens, closes, q, t, cfg=CFG):
    """Failed-breakdown reclaim weights, shape (n, 3): QQQ, TQQQ, BIL.

    State machine per session:
      1. Opening range from the first `or_min` bars: ORH, ORL, ORM.
      2. Flat until a bar's low < ORL*(1-break_buffer).
      3. Track the sweep low.  If the close recovers above ORL*(1+reclaim_buffer)
         within `reclaim_window` bars, signal a long at that close.
      4. Entry fills at the next bar's open.  Stop = sweep low.  Target = ORH
         (or ORM / EOD).  Exit signal on a stop/target breach, fill next open.
      5. Force exit at the second-to-last bar of the session (fills at the last
         bar's open).  Flat overnight in BIL.  One trade per session.
    """
    c = dict(CFG)
    c.update(cfg)
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    dates, starts, ends = sessions(ts)
    sym = q if c["asset"] == "QQQ" else t
    col = 0 if c["asset"] == "QQQ" else 1
    hi = sym["high"].to_numpy()
    lo = sym["low"].to_numpy()
    cl = sym["close"].to_numpy()
    brk = c["break_buffer_bps"] / 1e4
    rcl = c["reclaim_buffer_bps"] / 1e4
    info = {"breakdowns": 0, "reclaims": 0, "entries": 0, "skipped_reward": 0,
            "skipped_geometry": 0, "stopped": 0, "targeted": 0, "eod": 0}

    # Session timing from the clock, not from the last bar present in the data
    # (tuning fix 2026-11-27): a full session's last bar is 15:59, a half
    # day's (bt.HALF_DAYS) is 13:00. The opening range is the bars stamped
    # before 09:30 + or_min, so a halt in the first minutes (2020-03) does
    # not stretch the range past 10:00.
    tod = np.asarray(ts.hour * 60 + ts.minute)
    half = np.isin(dates, list(bt.HALF_DAYS))
    open_min = 9 * 60 + 30
    or_end_min = open_min + c["or_min"]

    for k, (s, e) in enumerate(zip(starts, ends)):
        last_min = 13 * 60 if half[s] else 15 * 60 + 59
        cutoff_min = last_min + 1 - c["entry_cutoff_bars"]   # entries only before this
        force_min = last_min - 1                              # exit signal here, fills last bar
        n_or = int(np.searchsorted(tod[s:e], or_end_min))     # bars inside the opening range
        if n_or < 1 or last_min - or_end_min < 10:
            continue
        orh = hi[s:s + n_or].max()
        orl = lo[s:s + n_or].min()
        orm = 0.5 * (orh + orl)

        state = 0          # 0 flat, 1 long
        broke = False
        break_i = -1
        sweep = np.inf
        entry_px = np.nan
        stop = np.nan
        target = np.inf
        size = 0.0
        traded = False

        for i in range(s + n_or, e):
            if state == 0:
                if traded:
                    w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                    continue
                if not broke:
                    if lo[i] < orl * (1.0 - brk):
                        broke = True
                        break_i = i
                        sweep = lo[i]
                        info["breakdowns"] += 1
                if broke:
                    sweep = min(sweep, lo[i])
                    if (i - break_i <= c["reclaim_window"]
                            and tod[i] < cutoff_min
                            and cl[i] > orl * (1.0 + rcl)):
                        info["reclaims"] += 1
                        entry_px = cl[i]
                        stop = sweep
                        risk = entry_px - stop
                        if not np.isfinite(risk) or risk <= 0 or entry_px <= 0:
                            info["skipped_geometry"] += 1
                            traded = True
                            w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                            continue
                        if c["target"] == "orh":
                            target = orh
                        elif c["target"] == "mid":
                            target = orm
                        else:
                            target = np.inf
                        reward = target - entry_px
                        if np.isfinite(reward) and reward < c["min_reward_r"] * risk:
                            info["skipped_reward"] += 1
                            traded = True
                            w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                            continue
                        size = min(c["max_weight"], c["risk_per_trade"] * entry_px / risk)
                        if size <= 0:
                            info["skipped_geometry"] += 1
                            traded = True
                            w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                            continue
                        state = 1
                        traded = True
                        info["entries"] += 1
                        w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 0.0
                        w[i, col] = size
                        w[i, 2] = 1.0 - size
                        continue
                w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                continue

            # state == 1: manage the long
            hit_stop = np.isfinite(stop) and lo[i] <= stop
            hit_tgt = np.isfinite(target) and hi[i] >= target
            # clock exit; i == e-1 is only a guard so nothing is carried
            # overnight if a session's data ends early
            force = tod[i] >= force_min or i == e - 1
            if hit_stop or hit_tgt or force:
                if hit_stop:
                    info["stopped"] += 1
                elif hit_tgt:
                    info["targeted"] += 1
                else:
                    info["eod"] += 1
                w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 1.0
                state = 0
            else:
                w[i, 0] = 0.0; w[i, 1] = 0.0; w[i, 2] = 0.0
                w[i, col] = size
                w[i, 2] = 1.0 - size

    return w, info


# ---------------------------------------------------------------------------
# evaluation (only run after the lead authorises backtests)
# ---------------------------------------------------------------------------
def daily_equity(res):
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(s.index.date).last()


def stats_window(ts, o, c, w, start, slip):
    res = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(res, BARS_1M)
    d = daily_equity(res)
    dr = d.pct_change().dropna()
    sharpe_d = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
    peak = np.maximum.accumulate(d.to_numpy())
    dd_d = float(-(d.to_numpy() / peak - 1.0).min())
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": dd_d,
        "sharpe": float(s["sharpe"]),
        "sharpe_daily": sharpe_d,
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure": float(s["exposure"]),
        "ending_equity": float(s["ending_equity"]),
        "daily": d,
    }


def baseline_165_daily(start=DEV_START, end=DEV_END):
    """Benchmark only.  NOT used by build_weights; used for the correlation."""
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), start, end, "1D")
    q = cd[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=120).mean().to_numpy()
    on = (q > sma).astype(float)  # known at this close; fills next open
    w = np.zeros((len(tsd), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    res = bt.run(tsd, od, cd, w, start, band=0.02, slippage_bps=1.0)
    # tuning fix 2026-11-27: the old groupby used a Series with a RangeIndex as
    # the key, which aligned to nothing and left the baseline empty, so the
    # correlation came out None.
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(s.index.date).last()


def correlate(a, b):
    x = pd.concat([a.pct_change(), b.pct_change()], axis=1, join="inner").dropna()
    if len(x) < 20:
        return None
    return float(np.corrcoef(x.iloc[:, 0], x.iloc[:, 1])[0, 1])


def spy_daily_benchmark(start=DEV_START, end=DEV_END):
    """Daily SPY benchmark from the round-3 Yahoo file, if present."""
    path = REPO / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        dcol = "date" if "date" in df.columns else df.columns[0]
        df[dcol] = pd.to_datetime(df[dcol])
        df = df[(df[dcol] >= start) & (df[dcol] <= end)].sort_values(dcol)
        px = (df["adjclose"] if "adjclose" in df.columns else df["close"]).to_numpy(float)
        if len(px) < 2:
            return None
        rets = np.diff(px) / px[:-1]
        years = (df[dcol].iloc[-1] - df[dcol].iloc[0]).days / 365.25
        peak = np.maximum.accumulate(px)
        return {
            "cagr": float((px[-1] / px[0]) ** (1.0 / years) - 1.0),
            "max_drawdown": float(-(px / peak - 1.0).min()),
            "sharpe": float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)) if rets.std() > 0 else 0.0,
        }
    except Exception:
        return None


def main(write=True):
    ts, o, c, q, t, b = load_dev()
    w, info = build_weights(ts, o, c, q, t)
    print("signals", info)

    out = {        "agent": "opening-range-breakout",
        "original": "research/agents/opening-range-breakout",
        "status": "pending_backtest",
        "idea": "A failed breakdown of the 30-minute opening range that reclaims the range low is a liquidity-sweep reversal; buy the reclaim and target the opposite side of the range before the close.",
        "hypothesis": "After a brief break below the opening-range low, the reclaim traps breakout sellers and the reversal continues to the opening-range high; the edge is intraday and independent of the overnight TQQQ drift.",
        "universe": ["QQQ", "TQQQ sensitivity", "BIL"],
        "frozen_commit": "pending",
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "marks": "1m",
        "windows": {},
        "benchmarks": {},
        "notes": [
            "Development only (2016-01-04..2023-12-29); holdout not inspected.",
            "Backtests were paused by the lead; numbers are generated only when main() is authorised.",
            "Only QQQ/TQQQ/BIL 1-minute data covers the development period; SPY 1-minute exists only for 2026.",
        ],
    }
    out["events"] = info
    for slip, key in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        out["windows"].setdefault("dev", {})[key] = stats_window(ts, o, c, w, DEV_START, slip)

    base_d = baseline_165_daily()
    strat_d = out["windows"]["dev"]["1bp"].pop("daily")
    out["corr_vs_165d_baseline"] = correlate(strat_d, base_d)
    for key in ("5bp", "10bp"):
        out["windows"]["dev"][key].pop("daily", None)

    # benchmarks (daily, sliced to the development window)
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1D")
    j0 = bt.start_index(tsd, DEV_START)
    for j, name in ((1, "tqqq"), (0, "qqq")):
        bb = bt.benchmark(cd[j0:, j], tsd[j0:], 252)
        out["benchmarks"][name] = {"cagr": float(bb["cagr"]),
                                   "max_drawdown": float(bb["max_drawdown"]),
                                   "sharpe": float(bb["sharpe"])}
    out["benchmarks"]["spy"] = spy_daily_benchmark()
    out["benchmarks"]["original"] = "not run: old base weights are not reused"

    # yearly, sub-periods, neighbourhood, placebo are filled by the authorised run
    out["windows"]["holdout"] = None
    out["windows"]["10y"] = None
    out["windows"]["5y"] = None

    if write:
        (Path(__file__).resolve().parent / "result.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8")
        print("wrote result.json")
    return out


if __name__ == "__main__":
    main()
