"""Failed-breakdown spring, repaired — `drawdown-stop-overlay-v2`.

Development window only: 2016-01-04 .. 2023-12-29. The 2024-2026 holdout is
never loaded. See HYPOTHESIS.md for the pre-registered grid.

The signal is unchanged from the old rebuild: QQQ undercuts its prior
20-session low intraday, closes back above that low, and closes in the upper
half of the day's range. The repair tests a 200-day trend filter, a 30%
volatility cap, a one-session instead of five-session hold, a wider/no stop,
and a close (MOC) exit instead of a next-open exit.

Run:
    python research/new/drawdown-stop-overlay-v2/strategy.py
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
from minute_marks import to_minutes  # noqa: E402

DEV0 = "2016-01-04"
DEV1 = "2023-12-29"
BARS_1M = 252 * 390
LOOKBACK = 20
RANGE_POS = 0.50
SIZE = 1.0

# Pre-registered grid. `stop_mode`: close = TQQQ close vs entry*(1-stop),
# intraday = TQQQ low vs entry*(1-stop). `exit_mode`: close = decide at 15:58,
# fill 15:59 open; next_open = decide at 15:59, fill next session open.
GRID = {
    "orig": dict(hold=5, trend=None, vol_cap=None, stop=0.08,
                 stop_mode="close", exit_mode="next_open"),
    "h5_trend_vol_stop12_close": dict(hold=5, trend=200, vol_cap=0.30, stop=0.12,
                                      stop_mode="close", exit_mode="close"),
    "h5_trend_vol_stop8_close": dict(hold=5, trend=200, vol_cap=0.30, stop=0.08,
                                     stop_mode="close", exit_mode="close"),
    "h1_trend_vol_nostop_close": dict(hold=1, trend=200, vol_cap=0.30, stop=None,
                                      stop_mode="close", exit_mode="close"),
    "h1_trend_vol_stop8_close": dict(hold=1, trend=200, vol_cap=0.30, stop=0.08,
                                     stop_mode="intraday", exit_mode="close"),
    "h3_trend_vol_stop8_close": dict(hold=3, trend=200, vol_cap=0.30, stop=0.08,
                                     stop_mode="intraday", exit_mode="close"),
    "h1_vol_stop8_close": dict(hold=1, trend=None, vol_cap=0.30, stop=0.08,
                               stop_mode="intraday", exit_mode="close"),
    "h1_trend_stop8_close": dict(hold=1, trend=200, vol_cap=None, stop=0.08,
                                 stop_mode="intraday", exit_mode="close"),
}
PRIMARY = "h1_trend_vol_nostop_close"


# ---------------------------------------------------------------------------
# data and signal
# ---------------------------------------------------------------------------
def load_daily():
    """Daily QQQ OHLC plus TQQQ open/close, development window only."""
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1D")
    q = bt.load_1m("QQQ")
    q = q[(q["ts"] >= pd.Timestamp(DEV0, tz="America/New_York"))
          & (q["ts"] < pd.Timestamp(DEV1, tz="America/New_York") + pd.Timedelta(days=1))].copy()
    q["day"] = pd.to_datetime(q["ts"].dt.date)
    g = q.groupby("day").agg(open=("open", "first"), high=("high", "max"),
                            low=("low", "min"), close=("close", "last"))
    days = pd.DatetimeIndex(tsd).tz_localize(None).normalize()
    g = g.reindex(days).ffill()
    t = bt.load_1m("TQQQ")
    t = t[(t["ts"] >= pd.Timestamp(DEV0, tz="America/New_York"))
          & (t["ts"] < pd.Timestamp(DEV1, tz="America/New_York") + pd.Timedelta(days=1))].copy()
    t["day"] = pd.to_datetime(t["ts"].dt.date)
    tg = t.groupby("day").agg(tq_open=("open", "first"), tq_close=("close", "last"))
    g = g.join(tg.reindex(days).ffill())
    if g.isna().any().any():
        raise ValueError("daily QQQ/TQQQ OHLC has gaps in the development window")
    return tsd, od, cd, g


def signal_arrays(g, lookback=LOOKBACK, range_pos=RANGE_POS):
    close = g["close"].to_numpy()
    low = g["low"].to_numpy()
    high = g["high"].to_numpy()
    low_n = pd.Series(low).rolling(lookback).min().shift(1).to_numpy()
    high_10 = pd.Series(close).rolling(10).max().shift(1).to_numpy()
    rng = np.where(high > low, (close - low) / (high - low), 0.0)
    sig = (np.isfinite(low_n) & (low < low_n) & (close > low_n)
           & (rng >= range_pos))
    return sig, high_10


def filters(g, trend, vol_cap):
    close = g["close"].to_numpy()
    vol20 = (pd.Series(close).pct_change().rolling(20).std(ddof=0).to_numpy()
             * np.sqrt(252.0))
    ok = np.ones(len(close), bool)
    if trend:
        sma = pd.Series(close).rolling(trend).mean().to_numpy()
        ok &= np.isfinite(sma) & (close > sma)
    if vol_cap:
        ok &= np.isfinite(vol20) & (vol20 < vol_cap)
    return ok, vol20


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def build_weights(g, ts1, params):
    """Build minute target weights and the trade list for one variant."""
    sig0, high10 = signal_arrays(g)
    ok, _ = filters(g, params["trend"], params["vol_cap"])
    sig = sig0 & ok

    close = g["close"].to_numpy()
    tq_open = g["tq_open"].to_numpy()
    tq_close = g["tq_close"].to_numpy()
    n = len(close)

    dates, first, last = bt.day_bounds(ts1)
    q = bt.load_1m("TQQQ").set_index("ts").reindex(ts1).ffill()
    q_low = q["low"].to_numpy()
    q_open = q["open"].to_numpy()
    q_close = q["close"].to_numpy()
    qq = bt.load_1m("QQQ").set_index("ts").reindex(ts1).ffill()
    qq_close = qq["close"].to_numpy()

    w = np.zeros((len(ts1), 3))
    w[:, 2] = 1.0  # BIL default
    trades = []
    busy_until = 0
    hold = int(params["hold"])
    stop = params["stop"]
    stop_mode = params["stop_mode"]
    exit_mode = params["exit_mode"]

    for d in np.flatnonzero(sig):
        if d < busy_until or d + 1 >= n:
            continue
        entry_day = d + 1
        entry_px = float(tq_open[entry_day])
        if not np.isfinite(entry_px) or entry_px <= 0:
            continue
        stop_px = entry_px * (1.0 - stop) if stop is not None else None
        exit_bar = None
        exit_day = None
        reason = None

        for x in range(entry_day, min(entry_day + hold, n)):
            # Intraday stop: first minute whose low trades through the stop.
            if stop_px is not None and stop_mode == "intraday":
                a, b = first[x], last[x]
                hit = np.flatnonzero(q_low[a:b] <= stop_px)  # through 15:58
                if len(hit):
                    exit_bar = a + int(hit[0])
                    exit_day = x
                    reason = "stop"
                    break
            # Close stop: with a close exit use the 15:58 close and fill at
            # the 15:59 open; the original next-open exit uses the 15:59
            # close and fills at the next session's open.
            if stop_px is not None and stop_mode == "close":
                if exit_mode == "close":
                    hit_close = q_close[last[x] - 1] <= stop_px
                    bar = last[x] - 1
                else:
                    hit_close = tq_close[x] <= stop_px
                    bar = last[x]
                if hit_close:
                    exit_bar = bar
                    exit_day = x
                    reason = "stop"
                    break
            # Recovery: QQQ repairs the prior 10-day high. With a close exit,
            # use the 15:58 QQQ close (known before the 15:59 fill).
            rec_px = qq_close[last[x] - 1] if exit_mode == "close" else close[x]
            if np.isfinite(high10[x]) and rec_px >= high10[x]:
                exit_day = x
                reason = "recovery"
                exit_bar = last[x] - 1 if exit_mode == "close" else last[x]
                break
            # Time.
            if x == entry_day + hold - 1:
                exit_day = x
                reason = "time"
                exit_bar = last[x] - 1 if exit_mode == "close" else last[x]
                break

        if exit_bar is None:
            continue
        start = last[d]
        if exit_bar <= start:
            continue
        w[start:exit_bar, 1] = SIZE
        w[start:exit_bar, 2] = 1.0 - SIZE
        w[exit_bar, 1] = 0.0
        w[exit_bar, 2] = 1.0

        exit_px = float(q_open[exit_bar + 1]) if exit_bar + 1 < len(q_open) else float(q_low[exit_bar])
        trades.append({
            "signal_date": str(g.index[d].date()),
            "entry_date": str(g.index[entry_day].date()),
            "exit_date": str(g.index[exit_day].date()),
            "entry_px": entry_px,
            "exit_px": exit_px,
            "return": exit_px / entry_px - 1.0,
            "hold_sessions": int(exit_day - entry_day + 1),
            "reason": reason,
        })
        busy_until = exit_day + 1

    info = {
        "signal_days": int(sig.sum()),
        "signal_days_unfiltered": int(sig0.sum()),
        "entries": len(trades),
        "trades": trades,
        "exit_reasons": {r: int(sum(t["reason"] == r for t in trades))
                         for r in ("stop", "recovery", "time")},
        "tqqq_minutes": float((w[:, 1] > 0).mean()),
        "avg_tqqq_weight": float(w[:, 1].mean()),
        "bil_minutes": float((w[:, 2] > 0).mean()),
        "gross_leverage": float(3.0 * w[:, 1].mean()),
        "params": params,
    }
    return w, info


# ---------------------------------------------------------------------------
# statistics and attribution
# ---------------------------------------------------------------------------
def stats(run, slip):
    s = bt.stats(run, BARS_1M)
    return {k: float(s[k]) for k in ("cagr", "total_return", "max_drawdown",
                                     "sharpe", "sortino", "volatility", "fills",
                                     "turnover", "exposure", "ending_equity")}


def daily_returns(run):
    df = pd.DataFrame({"ts": run["ts"], "eq": run["equity"]})
    e = df.groupby(df.ts.dt.date)["eq"].last()
    e.index = pd.to_datetime(e.index)
    return e.pct_change().dropna()


def yearly(equity, bench):
    """Yearly returns from daily equity / benchmark Series."""
    equity = pd.Series(equity).dropna()
    bench = pd.Series(bench).dropna()
    out = {}
    for y in sorted(set(equity.index.year)):
        e = equity[equity.index.year == y]
        b = bench[bench.index.year == y]
        if len(e) < 2 or len(b) < 2:
            continue
        out[int(y)] = {"strategy": float(e.iloc[-1] / e.iloc[0] - 1.0),
                       "benchmark": float(b.iloc[-1] / b.iloc[0] - 1.0)}
    return out


def daily_equity(run):
    s = pd.Series(run["equity"], index=pd.DatetimeIndex(run["ts"]))
    d = s.groupby(s.index.date).last()
    d.index = pd.to_datetime(d.index)
    return d


def subperiods(run):
    e = pd.Series(run["equity"], index=pd.DatetimeIndex(run["ts"]))
    d = e.groupby(e.index.date).last()
    d.index = pd.to_datetime(d.index)
    out = {}
    for lo, hi in ((2016, 2019), (2020, 2021), (2022, 2023)):
        s = d[(d.index.year >= lo) & (d.index.year <= hi)]
        prev = d[d.index.year < lo]
        start = prev.iloc[-1] if len(prev) else s.iloc[0]
        years = (s.index[-1] - (prev.index[-1] if len(prev) else s.index[0])).days / 365.25
        out[f"{lo}-{hi}"] = {
            "total_return": float(s.iloc[-1] / start - 1.0),
            "cagr": float((s.iloc[-1] / start) ** (1.0 / years) - 1.0),
        }
    return out


def event_study(g, sig, horizon):
    close = g["tq_close"].to_numpy()
    op = g["tq_open"].to_numpy()
    n = len(close)
    fwd = np.full(n, np.nan)
    ok = np.arange(n) + horizon < n
    fwd[ok] = close[np.arange(n)[ok] + horizon] / op[np.arange(n)[ok] + 1] - 1.0
    valid = np.isfinite(fwd)
    si = np.flatnonzero(sig & valid)
    pool = fwd[valid]
    rng = np.random.default_rng(7)
    boots = np.array([pool[rng.integers(0, len(pool), len(si))].mean()
                      for _ in range(5000)])
    return {
        "n": int(len(si)),
        "mean": float(fwd[si].mean()),
        "unconditional": float(pool.mean()),
        "hit_rate": float((fwd[si] > 0).mean()),
        "unconditional_hit": float((pool > 0).mean()),
        "bootstrap_p": float((boots >= fwd[si].mean()).mean()),
    }


def baseline_weights(tsd, cd):
    qqq = cd[:, 0]
    sma = pd.Series(qqq).rolling(165).mean().to_numpy()
    on = np.zeros(len(qqq), bool)
    ok = np.isfinite(sma)
    on[ok] = qqq[ok] > sma[ok]
    w = np.zeros((len(qqq), 3))
    w[:, 1] = on
    w[:, 2] = 1.0 - on
    return w


def main():
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    tsd, od, cd, g = load_daily()

    names, weights, infos = [], [], {}
    for name, params in GRID.items():
        w, info = build_weights(g, ts1, params)
        names.append(name)
        weights.append(w)
        infos[name] = info

    runs = {}
    for slip in (1.0, 5.0, 10.0):
        runs[slip] = bt.run_many(ts1, o1, c1, weights, DEV0, band=0.02,
                                 slippage_bps=slip)

    # Benchmarks and the old 165-day baseline.
    itq = bt.start_index(tsd, DEV0)
    bench = {
        "tqqq": bt.benchmark(cd[itq:, 1], tsd[itq:], 252),
        "qqq": bt.benchmark(cd[itq:, 0], tsd[itq:], 252),
    }
    wb = to_minutes(tsd, baseline_weights(tsd, cd), ts1, "1D")
    rb = bt.run(ts1, o1, c1, wb, DEV0, band=0.02, slippage_bps=1.0)
    bench["baseline_165d"] = stats(rb, 1.0)

    out = {
        "agent": "drawdown-stop-overlay-v2",
        "original": "research/revisit/drawdown-stop-overlay",
        "status": "development-only",
        "window": [DEV0, DEV1],
        "primary": PRIMARY,
        "variants_tried": len(GRID),
        "universe": ["QQQ signal", "TQQQ long", "BIL cash"],
        "direction": "long TQQQ, flat/BIL otherwise; no short",
        "idea": ("Failed-breakdown spring: QQQ undercuts a prior 20-day low and "
                 "closes back above it in the upper half of the day's range; "
                 "buy TQQQ for the one-day liquidity bounce in an uptrend."),
        "benchmarks": {k: ({m: float(v[m]) for m in v
                            if isinstance(v[m], (int, float, np.floating))}
                           if isinstance(v, dict) else v)
                       for k, v in bench.items()},
        "variants": {},
    }

    base_ret = daily_returns(rb)
    for j, name in enumerate(names):
        v = {"params": GRID[name], "signal_days": infos[name]["signal_days"],
             "signal_days_unfiltered": infos[name]["signal_days_unfiltered"],
             "entries": infos[name]["entries"],
             "exit_reasons": infos[name]["exit_reasons"],
             "exposure": {k: infos[name][k] for k in
                          ("tqqq_minutes", "avg_tqqq_weight", "bil_minutes",
                           "gross_leverage")},
             "trades": infos[name]["trades"],
             "costs": {}}
        for slip in (1.0, 5.0, 10.0):
            v["costs"][f"{slip:g}bp"] = stats(runs[slip][j], slip)
        v["per_year"] = yearly(daily_equity(runs[1.0][j]),
                               pd.Series(cd[itq:, 1],
                                         index=pd.to_datetime(tsd[itq:]).tz_localize(None).normalize()))
        v["subperiods"] = subperiods(runs[1.0][j])
        v["corr_vs_165d"] = float(
            daily_returns(runs[1.0][j]).corr(base_ret))
        v["corr_vs_qqq"] = float(
            daily_returns(runs[1.0][j]).corr(
                pd.Series(cd[itq:, 0],
                          index=pd.to_datetime(tsd[itq:]).tz_localize(None).normalize())
                .pct_change().dropna()))
        out["variants"][name] = v

    # Static TQQQ/BIL mix with the primary's average TQQQ weight: the honest
    # opportunity-cost benchmark for event timing.
    pw = weights[names.index(PRIMARY)]
    avg_w = float(pw[:, 1].mean())
    ws = np.zeros_like(pw)
    ws[:, 1] = avg_w
    ws[:, 2] = 1.0 - avg_w
    rs = bt.run(ts1, o1, c1, ws, DEV0, band=0.02, slippage_bps=1.0)
    out["static_mix_same_exposure"] = {
        "avg_tqqq_weight": avg_w,
        "stats": stats(rs, 1.0),
    }

    # Event study on the primary's filtered signal.
    sig0, _ = signal_arrays(g)
    fok, _ = filters(g, GRID[PRIMARY]["trend"], GRID[PRIMARY]["vol_cap"])
    psig = sig0 & fok
    out["event_study"] = {f"{h}d": event_study(g, psig, h) for h in (1, 3, 5, 10)}
    out["event_study"]["n_filtered"] = int(psig.sum())
    out["event_study"]["n_unfiltered"] = int(sig0.sum())

    out["note"] = ("Development window only 2016-01-04..2023-12-29. The "
                   "2024-2026 holdout and the 10y/5y windows were not loaded. "
                   "All fills are next-open 1-minute fills; the 'close' exit "
                   "sets the target at 15:58 and fills at the 15:59 open.")
    path = Path(__file__).resolve().parent / "result.json"
    path.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: {c: round(v["costs"][c]["cagr"] * 100, 2)
                          for c in ("1bp", "5bp", "10bp")}
                      for k, v in out["variants"].items()}, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
