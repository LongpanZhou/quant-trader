"""Volatility-scaled (ATR) crash stop on the daily QQQ 165-day regime.

Base strategy (round-1 winner, `daily-regime-minute-entry`):
  * risk-on  = QQQ daily close > 165-day SMA (signal from the prior close)
  * risk-off = BIL
  * armed    = QQQ first-minute close < 20-day SMA (prior close) * 1.01
  * stop     = TQQQ trades 4% below the session open -> BIL at next bar's open,
               out for the rest of the session and the night.

This agent replaces the fixed 4% with a volatility-scaled distance:

      stop_dist[d] = clip(0.70 * ATR14(TQQQ daily, through prior close),
                          2.5%, 4.0%)

i.e. tighten the stop when volatility is low, but never widen it beyond the
round-1 4%: in high-volatility regimes a wider stop misses exactly the gap
nights the overlay exists to avoid. The 4% cap makes the 2026 drawdown
identical to the round-1 winner while the tighter calm-market stop adds return.
Partial de-risking (50% QQQ / 50% BIL) is tested and does not help.

All signals use bars <= i; the harness fills at open[i+1]. Long only.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/strategy.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
SMA_N = 165
MA_FAST = 20
ARM_BUF = 0.01
ATR_N = 14
ATR_MULT = 0.70
FLOOR, CAP = 0.025, 0.040
BARS = 252 * 390
BIL = (0.0, 0.0, 1.0)
WIN = {"10y": START10, "5y": START5}
CACHE = HERE / "panel_cache.npz"


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_panel(force: bool = False):
    """1m QQQ/TQQQ/BIL opens/highs/lows/closes, 500 calendar days of warm-up.

    Mirrors bt.panel() exactly (same filtering, resampling and reindexing) but
    keeps the highs and lows needed for ATR.
    """
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        raw = z["ts"]
        if raw.max() < 1e17:  # microsecond cache written by pandas 3
            raw = raw * 1_000
        ts = pd.DatetimeIndex(pd.to_datetime(raw, unit="ns", utc=True)
                              .tz_convert("America/New_York"))
        return ts, z["opens"], z["highs"], z["lows"], z["closes"]

    start_ts = pd.Timestamp(START10, tz="America/New_York")
    load_start = start_ts - pd.Timedelta(days=500)
    end_ts = pd.Timestamp(END, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    frames = {}
    for s in SYMBOLS:
        df = bt.load_1m(s)
        df = df[(df["ts"] >= load_start) & (df["ts"] < end_ts)].set_index("ts")
        frames[s] = bt.resample(df, "1min")

    base = frames["QQQ"].index
    opens, highs, lows, closes = [], [], [], []
    for s in SYMBOLS:
        f = frames[s].reindex(base).ffill().bfill()
        opens.append(f["open"].to_numpy())
        highs.append(f["high"].to_numpy())
        lows.append(f["low"].to_numpy())
        closes.append(f["close"].to_numpy())
    opens, highs = np.column_stack(opens), np.column_stack(highs)
    lows, closes = np.column_stack(lows), np.column_stack(closes)
    np.savez_compressed(
        CACHE, ts=base.asi8,  # nanoseconds since epoch, resolution-safe
        opens=opens, highs=highs, lows=lows, closes=closes,
    )
    return base, opens, highs, lows, closes


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_atr_pct(highs, lows, closes, first, last, n=ATR_N):
    """ATR(n)/price on TQQQ daily bars aggregated from the 1m panel, shifted one
    day so only prior-close information is used for session k."""
    high = np.maximum.reduceat(highs[:, 1], first)
    low = np.minimum.reduceat(lows[:, 1], first)
    close = closes[last, 1]
    prev = np.r_[np.nan, close[:-1]]
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    atr = pd.Series(tr).rolling(n).mean().to_numpy() / close
    return np.r_[np.nan, atr[:-1]]


def regime_arrays(closes, first, last, sma_n=SMA_N, ma_fast=MA_FAST, buf=ARM_BUF):
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dc).rolling(ma_fast).mean().to_numpy()
    k = np.arange(len(first))
    risk_on = np.zeros(len(first), bool)
    armed = np.zeros(len(first), bool)
    ok = k > 0
    risk_on[ok] = dc[:-1] > sma[:-1]
    armed[ok] = closes[first, 0][ok] < ma20[:-1] * (1.0 + buf)
    return risk_on, armed, dc


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, first, last, risk_on, armed, dist,
                  alloc1=BIL):
    """Per-day state machine. `dist` is per-day, in fractions of the session open."""
    n = len(ts)
    w = np.zeros((n, 3))
    alloc1 = np.asarray(alloc1, float)
    nstops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k]:
            w[f:l + 1, 2] = 1.0
            continue
        base = opens[f, 1]
        d = dist[k]
        stopped = False
        for i in range(f, l + 1):
            if not stopped:
                w[i, 1] = 1.0
                if armed[k] and d == d and closes[i, 1] < base * (1.0 - d):
                    stopped = True
                    nstops += 1
                    w[i, :] = alloc1
            else:
                w[i, :] = alloc1
    return w, nstops


def daily_marks(ts, eq):
    dates = np.array([t.date() for t in ts])
    last = np.r_[np.flatnonzero(dates[1:] != dates[:-1]), len(dates) - 1]
    return last, eq[last]


def window_stats(eq, bench, n_days):
    yrs = n_days / 252.0
    peak = np.maximum.accumulate(eq)
    bpk = np.maximum.accumulate(bench)
    return dict(
        cagr=float((eq[-1] / eq[0]) ** (1.0 / yrs) - 1.0),
        dd=float(-(eq / peak - 1.0).min()),
        bench_cagr=float((bench[-1] / bench[0]) ** (1.0 / yrs) - 1.0),
        bench_dd=float(-(bench / bpk - 1.0).min()),
    )


def rolling3y(ts_win, eq, bench, n=756, step=63):
    last, deq = daily_marks(ts_win, eq)
    _, db = daily_marks(ts_win, bench)
    out = []
    for i in range(0, len(deq) - n + 1, step):
        s = window_stats(deq[i:i + n], db[i:i + n], n)
        s["start"] = str(pd.Timestamp(ts_win[last[i]]).date())
        out.append(s)
    return out


def metrics(ts, opens, closes, w, start, slip=1.0):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    i = bt.start_index(ts, start)
    b = bt.benchmark(closes[i:, 1], ts[i:], BARS)
    dd = r["equity"] / np.maximum.accumulate(r["equity"]) - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(r["equity"][: j + 1]))
    return dict(
        cagr=s["cagr"], total_return=s["total_return"], dd=s["max_drawdown"],
        sharpe=s["sharpe"], sortino=s["sortino"], vol=s["volatility"],
        fills=s["fills"], turnover=s["turnover"], end=s["ending_equity"],
        dd_peak=str(r["ts"][p]), dd_trough=str(r["ts"][j]),
        tqqq_time=float(np.mean(w[i:, 1] > 0.5)),
        bench=b,
        yearly={str(k): v for k, v in bt.yearly(r["ts"], r["equity"], closes[i:, 1]).items()},
        _r=r, _i=i,
    )


# --------------------------------------------------------------------------- #
def main():
    t0 = time.time()
    ts, opens, highs, lows, closes = load_panel()
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    risk_on, armed, dc = regime_arrays(closes, first, last)
    nd = len(first)
    atr = daily_atr_pct(highs, lows, closes, first, last)

    variants = {
        "winner_fixed4_bil": dict(dist=np.full(nd, 0.04), alloc1=BIL),
        f"atr{int(round(ATR_MULT*100)):02d}_cap4_bil": dict(
            dist=np.clip(ATR_MULT * atr, FLOOR, CAP), alloc1=BIL),
        "atr055_cap4_bil": dict(dist=np.clip(0.55 * atr, FLOOR, CAP), alloc1=BIL),
        "atr085_cap4_bil": dict(dist=np.clip(0.85 * atr, FLOOR, CAP), alloc1=BIL),
        "atr070_cap6_bil": dict(dist=np.clip(0.70 * atr, FLOOR, 0.060), alloc1=BIL),
        "fixed4_partial50": dict(dist=np.full(nd, 0.04), alloc1=(0.5, 0.0, 0.5)),
        f"atr{int(round(ATR_MULT*100)):02d}_cap4_partial50": dict(
            dist=np.clip(ATR_MULT * atr, FLOOR, CAP), alloc1=(0.5, 0.0, 0.5)),
    }

    out = dict(
        agent="vol-scaled-crash-stop",
        created=str(pd.Timestamp.now()),
        headline="atr70_cap4_bil",
        rules=dict(
            regime="QQQ daily close > 165-day SMA (prior close) -> TQQQ, else BIL",
            arm="QQQ first-minute close < 20-day SMA (prior close) * 1.01",
            stop="stop_dist = clip(0.70 * ATR14(TQQQ daily, prior close), 2.5%, 4%); "
                 "TQQQ close < session open * (1 - stop_dist) -> BIL at next bar open, "
                 "out for the rest of the session and the night",
            partial="50% QQQ / 50% BIL after the stop (tested, does not help)",
            fills="next bar open", costs="1 bp one-way, 5/10 bp reported",
        ),
        diagnostics=dict(days=int(nd), risk_on_share=float(risk_on.mean()),
                         armed_share=float(armed.mean()),
                         atr_stop_median=float(np.nanmedian(np.clip(ATR_MULT*atr, FLOOR, CAP))),
                         n_stops_note="n_stops counts the whole warm-up+test panel "
                                      "(2016-2026); the 2017-2026 test-window counts are "
                                      "204 for atr70_cap4_bil vs 153 for the winner",
                         n_stops={}),
        variants={},
        pass_vs_tqqq={}, pass_vs_winner={},
    )

    tqqq = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
    winner = {}

    for name, cfg in variants.items():
        t1 = time.time()
        w, ns = build_weights(ts, opens, closes, first, last, risk_on, armed,
                              cfg["dist"], alloc1=cfg["alloc1"])
        out["diagnostics"]["n_stops"][name] = int(ns)
        v = dict(alloc=list(cfg["alloc1"]), stops=int(ns), windows={}, rolling3y={}, costs={})
        for lab, start in WIN.items():
            m = metrics(ts, opens, closes, w, start, 1.0)
            v["rolling3y"][lab] = rolling3y(m["_r"]["ts"], m["_r"]["equity"],
                                            closes[m["_i"]:, 1])
            del m["_r"], m["_i"]
            v["windows"][lab] = m
            v["costs"][lab] = {}
            for slip in (5.0, 10.0):
                c = metrics(ts, opens, closes, w, start, slip)
                del c["_r"], c["_i"]
                v["costs"][lab][f"{slip:.0f}bp"] = {
                    k: c[k] for k in ("cagr", "dd", "sharpe", "fills", "turnover")}
        out["variants"][name] = v
        if name == "winner_fixed4_bil":
            winner = v
        (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
        print(f"{name:22s} stops {ns:4d}  10y "
              f"{v['windows']['10y']['cagr']*100:5.2f}/{v['windows']['10y']['dd']*100:5.2f}"
              f"  5y {v['windows']['5y']['cagr']*100:5.2f}/{v['windows']['5y']['dd']*100:5.2f}"
              f"  [{time.time()-t1:.0f}s]", flush=True)

    # rolling-window consistency vs the winner and vs TQQQ
    for name, v in out["variants"].items():
        if name == "winner_fixed4_bil":
            continue
        summary = {}
        for lab in WIN:
            rw, rwin = v["rolling3y"][lab], winner["rolling3y"][lab]
            assert len(rw) == len(rwin)
            n = len(rw)
            summary[lab] = dict(
                windows=n,
                beat_tqqq_cagr=int(sum(x["cagr"] > x["bench_cagr"] for x in rw)),
                beat_tqqq_dd=int(sum(x["dd"] < x["bench_dd"] for x in rw)),
                beat_both_tqqq=int(sum(x["cagr"] > x["bench_cagr"] and x["dd"] < x["bench_dd"]
                                       for x in rw)),
                beat_winner_cagr=int(sum(a["cagr"] > b["cagr"] for a, b in zip(rw, rwin))),
                beat_winner_dd=int(sum(a["dd"] < b["dd"] for a, b in zip(rw, rwin))),
                beat_winner_both=int(sum(a["cagr"] > b["cagr"] and a["dd"] < b["dd"]
                                         for a, b in zip(rw, rwin))),
                median_cagr_edge=float(np.median([a["cagr"] - b["cagr"]
                                                  for a, b in zip(rw, rwin)])),
                median_dd_edge=float(np.median([a["dd"] - b["dd"]
                                                for a, b in zip(rw, rwin)])),
            )
        v["rolling3y_summary"] = summary

    # pass/fail
    for name, v in out["variants"].items():
        out["pass_vs_tqqq"][name] = {
            lab: bool(v["windows"][lab]["cagr"] > tqqq[lab][0]
                      and v["windows"][lab]["dd"] < tqqq[lab][1]) for lab in WIN}
        if name == "winner_fixed4_bil":
            continue
        strict, ddok, tie = {}, {}, {}
        for lab in WIN:
            c, d = v["windows"][lab]["cagr"], v["windows"][lab]["dd"]
            wc, wd = winner["windows"][lab]["cagr"], winner["windows"][lab]["dd"]
            tie[lab] = bool(abs(d - wd) <= 1e-9)
            strict[lab] = bool(c > wc and d < wd - 1e-9)
            ddok[lab] = bool(d < wd - 1e-9 and c >= wc - 0.02)
        out["pass_vs_winner"][name] = dict(strict_dominance=strict,
                                           dd_tie=tie,
                                           lower_dd_within_2pp=ddok)

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    for name in out["pass_vs_winner"]:
        p, q = out["pass_vs_winner"][name], out["pass_vs_tqqq"][name]
        print(f"  {name:30s} vs winner strict {p['strict_dominance']} "
              f"dd/2pp {p['lower_dd_within_2pp']}  vs TQQQ {q}", flush=True)
    print(f"\nwrote {HERE / 'result.json'}  ({time.time()-t0:.0f}s total)", flush=True)


if __name__ == "__main__":
    main()
