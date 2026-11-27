"""Dev-only exploration: can the ATR-scaled conditional stop stand alone?

No 165-day (or any 100-250 day) MA gate. The only position logic is
"hold TQQQ by default; the ATR stop decides when to be out".

Development window only: 2016-01-04 .. 2023-12-29. The panel is physically
truncated at 2023-12-29, so no holdout bar is ever loaded.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/vol-scaled-crash-stop/explore.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
BARS = 252 * 390
CACHE = HERE / "dev_panel.npz"


# --------------------------------------------------------------------------- #
def load_panel(start=DEV_START, end=DEV_END, warmup_days=90):
    """1m QQQ/TQQQ/BIL o/h/l/c, mirroring bt.panel's alignment."""
    if CACHE.exists():
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)
                              .tz_convert("America/New_York"))
        return ts, z["opens"], z["highs"], z["lows"], z["closes"]
    start_ts = pd.Timestamp(start, tz="America/New_York")
    load_start = start_ts - pd.Timedelta(days=warmup_days)
    end_ts = pd.Timestamp(end, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    frames = {}
    for s in SYMBOLS:
        df = bt.load_1m(s)
        df = df[(df["ts"] >= load_start) & (df["ts"] < end_ts)].set_index("ts")
        frames[s] = bt.resample(df, "1min")
    base = frames["QQQ"].index
    out = {k: [] for k in ("open", "high", "low", "close")}
    for s in SYMBOLS:
        f = frames[s].reindex(base).ffill().bfill()
        for k in out:
            out[k].append(f[k].to_numpy())
    arrays = {k: np.column_stack(v) for k, v in out.items()}
    np.savez_compressed(CACHE, ts=base.asi8, opens=arrays["open"],
                        highs=arrays["high"], lows=arrays["low"],
                        closes=arrays["close"])
    return base, arrays["open"], arrays["high"], arrays["low"], arrays["close"]


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def atr_series(highs, lows, closes, first, last, n=14):
    high = np.maximum.reduceat(highs[:, 1], first)
    low = np.minimum.reduceat(lows[:, 1], first)
    close = closes[last, 1]
    prev = np.r_[np.nan, close[:-1]]
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    atr = pd.Series(tr).rolling(n).mean().to_numpy() / close
    return np.r_[np.nan, atr[:-1]]  # prior-close information only


# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, first, last, dist, arm=None,
                  cooldown=0, reentry=None):
    """Always-long TQQQ by default; the stop is the only exit rule.

    dist[k]     stop distance for session k (fraction of the session open)
    arm[k]      optional bool: is the stop live on session k
    cooldown    sessions to stay in BIL after a trigger (0 = re-enter next open)
    reentry[k]  optional bool array: if given, stay out until it is True
    """
    n = len(ts)
    w = np.zeros((n, 3))
    out = False
    out_left = 0
    events = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if out:
            if reentry is not None:
                if not reentry[k]:
                    w[f:l + 1, 2] = 1.0
                    continue
                out = False
            elif out_left > 0:
                out_left -= 1
                w[f:l + 1, 2] = 1.0
                continue
            else:
                out = False
        w[f:l + 1, 1] = 1.0
        if arm is not None and not arm[k]:
            continue
        d = dist[k]
        if d != d:
            continue
        base = opens[f, 1]
        idx = np.flatnonzero(closes[f:l + 1, 1] < base * (1.0 - d))
        if len(idx):
            i = f + int(idx[0])
            w[i, 1] = 0.0
            w[i, 2] = 1.0
            w[i + 1:l + 1, 1] = 0.0
            w[i + 1:l + 1, 2] = 1.0
            events += 1
            out = True
            out_left = cooldown
    return w, events


def dev_stats(w, ts, opens, closes, slip=1.0):
    r = bt.run(ts, opens, closes, w, DEV_START, band=0.02, slippage_bps=slip)
    return bt.stats(r, BARS), r


def daily_returns(ts, eq):
    dates = bt.session_dates(ts)
    last = np.r_[np.flatnonzero(dates[1:] != dates[:-1]), len(dates) - 1]
    de = eq[last]
    return pd.Series(np.diff(de) / de[:-1])


def baseline_weights(ts, opens, closes, first, last, n=165):
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(n).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = dc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def subperiod(ts, eq, a, b):
    m = (ts >= pd.Timestamp(a, tz="America/New_York")) & (ts < pd.Timestamp(b, tz="America/New_York"))
    e = eq[m]
    yrs = (ts[m][-1] - ts[m][0]).total_seconds() / (365.25 * 86400)
    return (e[-1] / e[0]) ** (1 / yrs) - 1, float(-(e / np.maximum.accumulate(e) - 1).min())


# --------------------------------------------------------------------------- #
def main():
    t0 = time.time()
    ts, opens, highs, lows, closes = load_panel()
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    atr = atr_series(highs, lows, closes, first, last)
    nd = len(first)
    i0 = bt.start_index(ts, DEV_START)
    print(f"panel {len(ts):,} bars, {nd} sessions, {ts[0]} .. {ts[-1]} ({time.time()-t0:.0f}s)")

    d = {
        "k055": np.clip(0.55 * atr, 0.025, 0.040),
        "k070": np.clip(0.70 * atr, 0.025, 0.040),
        "k100": np.clip(1.00 * atr, 0.025, 0.040),
        "fix4": np.full(nd, 0.040),
    }
    qqq_open, qqq_prev = opens[first, 0], np.r_[np.nan, closes[last[:-1], 0]]
    arm_gap = qqq_open < qqq_prev
    ma20 = pd.Series(closes[last, 0]).rolling(20).mean().to_numpy()
    arm_ma20 = closes[first, 0] < np.r_[np.nan, ma20[:-1]] * 1.01
    med60 = pd.Series(atr).rolling(60).median().to_numpy()

    base = baseline_weights(ts, opens, closes, first, last)
    base_s, base_r = dev_stats(base, ts, opens, closes)
    base_ret = daily_returns(ts, base_r["equity"])
    tq_s = bt.benchmark(closes[i0:, 1], ts[i0:], BARS)
    print(f"BASELINE 165d  CAGR {base_s['cagr']*100:6.2f}%  DD {base_s['max_drawdown']*100:5.2f}%  "
          f"Sharpe {base_s['sharpe']:.2f}")
    print(f"TQQQ B&H       CAGR {tq_s['cagr']*100:6.2f}%  DD {tq_s['max_drawdown']*100:5.2f}%  "
          f"Sharpe {tq_s['sharpe']:.2f}")

    cases = []
    for k in ("k055", "k070", "k100"):
        for cd in (0, 1, 2, 3, 5):
            cases.append((f"{k} cooldown {cd}", dict(dist=d[k], cooldown=cd)))
    cases += [
        ("fix4 cooldown 0", dict(dist=d["fix4"], cooldown=0)),
        ("k070 arm gap-down", dict(dist=d["k070"], arm=arm_gap)),
        ("k070 arm MA20", dict(dist=d["k070"], arm=arm_ma20)),
        ("k070 vol-reentry (ATR<=med60)", dict(dist=d["k070"], reentry=atr <= med60)),
        ("k070 vol-reentry (ATR<=med120)", dict(dist=d["k070"],
                                                reentry=atr <= pd.Series(atr).rolling(120).median().to_numpy())),
    ]

    out = {}
    print(f"\n{'variant':34s} {'ev':>4s}  CAGR      DD     Sharpe  corr  fills")
    for label, kw in cases:
        w, ev = build_weights(ts, opens, closes, first, last, **kw)
        s, r = dev_stats(w, ts, opens, closes)
        ret = daily_returns(ts, r["equity"])
        corr = float(pd.concat([ret, base_ret], axis=1).dropna().corr().iloc[0, 1])
        tqqq_time = float(np.mean(w[i0:, 1] > 0.5))
        out[label] = dict(events=ev, cagr=s["cagr"], dd=s["max_drawdown"],
                          sharpe=s["sharpe"], fills=s["fills"], corr=corr,
                          turnover=s["turnover"], tqqq_time=tqqq_time,
                          sp=[subperiod(ts, r["equity"], a, b) for a, b in
                              (("2016-01-04", "2020-01-01"), ("2020-01-01", "2022-01-01"),
                               ("2022-01-01", "2023-12-30"))])
        print(f"{label:34s} {ev:4d}  {s['cagr']*100:6.2f}  {s['max_drawdown']*100:5.2f}  "
              f"{s['sharpe']:6.2f}  {corr:4.2f}  {s['fills']:5d}")

    (HERE / "explore.json").write_text(json.dumps(out, indent=2, default=float))

    # diagnostics for the pure stop
    w, _ = build_weights(ts, opens, closes, first, last, dist=d["k070"])
    s, r = dev_stats(w, ts, opens, closes)
    eq = r["equity"]
    print("\nS1 per-year (pure stop vs TQQQ vs baseline)")
    for y in range(2016, 2024):
        m = ts.year == y
        e = eq[m]
        tq = closes[m, 1]
        be = base_r["equity"][m]
        print(f"  {y}  strat {e[-1]/e[0]-1:8.2%}   TQQQ {tq[-1]/tq[0]-1:8.2%}   base {be[-1]/be[0]-1:8.2%}")

    print(f"\nS1 total: CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  "
          f"Sharpe {s['sharpe']:.2f}  fills {s['fills']}  time in TQQQ {np.mean(w[i0:,1]>0.5)*100:.1f}%")
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
