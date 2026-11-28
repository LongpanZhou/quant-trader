"""Volatility-scaled crash system (VSCS) - standalone rebuild of the
ATR-scaled conditional stop. DEVELOPMENT WINDOW ONLY.

Idea (extracted from `research/agents2/vol-scaled-crash-stop`):
    A stop distance should be proportional to recent volatility (about 0.7
    daily ATR), but it must never be widened past the level that actually
    protects against the gap nights it exists to avoid (4%). In the original
    this was a one-sided, volatility-scaled barrier on top of the 165-day QQQ
    regime. Here the barrier *is* the strategy, with its own exposure rule and
    its own volatility-scaled position size.

This rebuild uses:
    * no 165-day (or any 100-250 day) QQQ/TQQQ/SPY/NDX moving-average gate;
    * no round-1 weights or `build_weights`;
    * its own signal (TQQQ daily ATR), holding period (default long, out for the
      rest of the trigger session and the night) and sizing (inverse-vol).

The engine is `research/bt.py`; weights set at bar i fill at bar i+1's open with
a 2% band and 1/5/10 bp slippage. Marks are 1-minute.

Development window: 2016-01-04 .. 2023-12-29. The panel is physically truncated
at 2023-12-29, so no holdout bar can be loaded. The holdout/10y/5y windows are
left null here for the lead to run once on the frozen strategy.

Run (only after the lead authorises the test):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/vol-scaled-crash-stop/strategy.py
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

# frozen parameters (chosen from the pre-pause exploration, not tuned here)
TARGET_ATR = 0.040      # inverse-vol sizing target (TQQQ daily ATR)
SIZE_FLOOR = 0.40       # never less than 40% TQQQ on a normal day
ATR_MULT = 0.70         # barrier = 0.70 x ATR14
DIST_FLOOR = 0.025
DIST_CAP = 0.040
COOLDOWN = 0            # re-enter at the next session's open


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_dev_panel(start=DEV_START, end=DEV_END, warmup_days=90):
    """1m QQQ/TQQQ/BIL o/h/l/c over the development window only."""
    if CACHE.exists():
        z = np.load(CACHE)
        # Epoch nanoseconds. Caches written before the pandas-3 fix hold
        # microseconds (values < 1e17), which read as 1970 if taken as ns.
        unit = "ns" if z["ts"].max() > 1e17 else "us"
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit=unit, utc=True)
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
    cols = {k: [] for k in ("open", "high", "low", "close")}
    for s in SYMBOLS:
        f = frames[s].reindex(base).ffill().bfill()
        for k in cols:
            cols[k].append(f[k].to_numpy())
    a = {k: np.column_stack(v) for k, v in cols.items()}
    np.savez_compressed(CACHE, ts=base.as_unit("ns").asi8,
                        opens=a["open"], highs=a["high"],
                        lows=a["low"], closes=a["close"])
    return base, a["open"], a["high"], a["low"], a["close"]


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def atr_series(highs, lows, closes, first, last, n=14):
    """ATR(n)/close on TQQQ daily bars, through the prior close only.

    The first n-1 sessions have no ATR (the 1m archive starts 2016-01-04 and
    there is no pre-2016 intraday warm-up); those sessions trade at full size
    with the stop disabled, which is causal.
    """
    high = np.maximum.reduceat(highs[:, 1], first)
    low = np.minimum.reduceat(lows[:, 1], first)
    close = closes[last, 1]
    prev = np.r_[np.nan, close[:-1]]
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    atr = pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy() / close
    return np.r_[np.nan, atr[:-1]]


# --------------------------------------------------------------------------- #
# signals
# --------------------------------------------------------------------------- #
def baseline_weights(ts, first, last, sma_n=165):
    """165-day QQQ SMA baseline, used only as a correlation/benchmark reference.

    Daily closes come from the QQQ daily parquet so the 165-day SMA is warm at
    2016-01-04 (the 1-minute archive has no pre-2016 bars). This function is
    never used by the strategy's positions.
    """
    daily = pd.read_parquet(ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily = daily[daily["date"] <= pd.Timestamp(DEV_END).date()].copy()  # dev only
    daily["adj"] = daily["adjclose"].astype(float)
    daily = daily.sort_values("date").set_index("date")
    sma = daily["adj"].rolling(sma_n).mean()
    prev_close = daily["adj"].shift(1)
    reg = (prev_close > sma).astype(bool)
    reg.index = pd.Index(reg.index)
    sess = pd.Index([d for d in bt.session_dates(ts)[last]])
    reg = reg.reindex(sess).ffill().fillna(False).to_numpy()
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w, reg


def build_weights(ts, opens, closes, first, last, atr,
                  target_atr=TARGET_ATR, size_floor=SIZE_FLOOR,
                  atr_mult=ATR_MULT, dist_floor=DIST_FLOOR, dist_cap=DIST_CAP,
                  cooldown=COOLDOWN, use_sizing=True, placebo=None):
    """Return (weights, info).

    Rules
    -----
    * Default position: TQQQ at size s[k] = clip(target_atr / ATR14[k], floor, 1),
      remainder BIL.  s[k] uses ATR through session k-1's close.
    * Barrier: d[k] = clip(atr_mult * ATR14[k], dist_floor, dist_cap).
    * If, at any minute of session k, TQQQ's 1m close < session_open * (1 - d[k]),
      the TQQQ sleeve goes to BIL on that bar (fills at the next bar's open) and
      stays BIL for the rest of the session and the night.
    * Re-entry: the next session's open at the target size (cooldown=0). With
      cooldown>0 the book stays BIL for that many extra sessions.
    * `placebo` is a {session_index: bar_index} dict that replaces the ATR
      trigger with a pre-drawn random (session, minute) pair - the matched-
      frequency placebo control.
    """
    n = len(ts)
    nd = len(first)
    w = np.zeros((n, 3))
    atr_ok = np.isfinite(atr)
    if use_sizing:
        size = np.clip(target_atr / np.where(atr_ok, atr, target_atr), size_floor, 1.0)
    else:
        size = np.ones(nd)
    dist = np.clip(atr_mult * atr, dist_floor, dist_cap)
    events = 0
    event_list = []
    out_left = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if out_left > 0:
            w[f:l + 1, 2] = 1.0
            out_left -= 1
            continue
        s = float(size[k])
        w[f:l + 1, 1] = s
        w[f:l + 1, 2] = 1.0 - s
        if placebo is not None:
            if k not in placebo:
                continue
            i = int(placebo[k])
            d_used = float("nan")
        else:
            d = dist[k]
            if not np.isfinite(d):
                continue
            base = opens[f, 1]
            idx = np.flatnonzero(closes[f:l + 1, 1] < base * (1.0 - d))
            if len(idx) == 0:
                continue
            i = f + int(idx[0])
            d_used = float(d)
        w[i, 1] = 0.0
        w[i, 2] = 1.0
        w[i + 1:l + 1, 1] = 0.0
        w[i + 1:l + 1, 2] = 1.0
        events += 1
        if placebo is None:
            event_list.append((k, i, d_used))
        out_left = cooldown
    return w, dict(events=events, event_list=event_list,
                   size_mean=float(np.mean(size)), size_min=float(np.min(size)))


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def daily_returns(ts, eq):
    dates = bt.session_dates(ts)
    last = np.r_[np.flatnonzero(dates[1:] != dates[:-1]), len(dates) - 1]
    de = eq[last]
    return pd.Series(np.diff(de) / de[:-1])


def subperiod(ts, eq, a, b):
    m = (ts >= pd.Timestamp(a, tz="America/New_York")) & (ts < pd.Timestamp(b, tz="America/New_York"))
    e = eq[m]
    yrs = (ts[m][-1] - ts[m][0]).total_seconds() / (365.25 * 86400)
    return dict(cagr=float((e[-1] / e[0]) ** (1 / yrs) - 1),
                dd=float(-(e / np.maximum.accumulate(e) - 1).min()))


def event_study(ts, opens, closes, first, last, info, n_boot=10000, seed=11):
    """Forward return from the trigger fill to the next session's open."""
    ev = []
    for k, i, d in info["event_list"]:
        fill = opens[i + 1, 1] if i + 1 < len(ts) else closes[i, 1]
        nxt = opens[first[k + 1], 1] if k + 1 < len(first) else closes[-1, 1]
        ev.append(nxt / fill - 1.0)
    ev = np.array(ev, dtype=float)
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(ev, size=len(ev), replace=True).mean()
                     for _ in range(n_boot)]) if len(ev) else np.array([])
    return dict(n_events=int(len(ev)),
                mean=float(ev.mean()) if len(ev) else None,
                median=float(np.median(ev)) if len(ev) else None,
                share_negative=float(np.mean(ev < 0)) if len(ev) else None,
                p_mean_ge_0=float(np.mean(boot >= 0)) if len(boot) else None)


# --------------------------------------------------------------------------- #
def main():
    t0 = time.time()
    ts, opens, highs, lows, closes = load_dev_panel()
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    atr = atr_series(highs, lows, closes, first, last)
    i0 = bt.start_index(ts, DEV_START)

    base_w, reg = baseline_weights(ts, first, last)
    base_r = bt.run(ts, opens, closes, base_w, DEV_START, band=0.02, slippage_bps=1.0)
    base_s = bt.stats(base_r, BARS)
    base_ret = daily_returns(base_r["ts"], base_r["equity"])

    primary = dict(target_atr=TARGET_ATR, size_floor=SIZE_FLOOR, atr_mult=ATR_MULT,
                   dist_floor=DIST_FLOOR, dist_cap=DIST_CAP, cooldown=COOLDOWN,
                   use_sizing=True)
    variants = {
        "primary": primary,
        "binary_sizing": dict(primary, use_sizing=False),
        "cooldown_1": dict(primary, cooldown=1),
        "cooldown_2": dict(primary, cooldown=2),
        "cooldown_5": dict(primary, cooldown=5),
        "atr_mult_055": dict(primary, atr_mult=0.55),
        "atr_mult_100": dict(primary, atr_mult=1.00),
        "fixed_4pct": dict(primary, atr_mult=0.0, dist_floor=0.04, dist_cap=0.04),
        "size_floor_030": dict(primary, size_floor=0.30),
        "size_floor_050": dict(primary, size_floor=0.50),
        "target_atr_030": dict(primary, target_atr=0.030),
        "target_atr_050": dict(primary, target_atr=0.050),
    }

    weights, infos = [], {}
    for name, kw in variants.items():
        w, info = build_weights(ts, opens, closes, first, last, atr, **kw)
        weights.append(w)
        infos[name] = info
    results = bt.run_many(ts, opens, closes, weights, DEV_START, band=0.02,
                          slippage_bps=1.0)

    out = {}
    for name, w, r in zip(variants, weights, results):
        s = bt.stats(r, BARS)
        ret = daily_returns(r["ts"], r["equity"])
        j = pd.concat([ret.rename("s"), base_ret.rename("b")], axis=1).dropna()
        out[name] = dict(
            events=infos[name]["events"], cagr=s["cagr"],
            max_drawdown=s["max_drawdown"], sharpe=s["sharpe"],
            sortino=s["sortino"], volatility=s["volatility"], fills=s["fills"],
            turnover=s["turnover"], tqqq_time=float(np.mean(w[i0:, 1])),
            corr_vs_165d=float(j["s"].corr(j["b"])),
            sp={str(y): subperiod(r["ts"], r["equity"], f"{y}-01-01", f"{y + 1}-01-01")
                for y in (2016, 2020, 2022)},
            yearly={str(y): float(r["equity"][r["ts"].year == y][-1] /
                                  r["equity"][r["ts"].year == y][0] - 1)
                    for y in range(2016, 2024)},
        )

    costs = {}
    for name in ("primary", "binary_sizing"):
        k = list(variants).index(name)
        costs[name] = {}
        for slip in (5.0, 10.0):
            rr = bt.run(ts, opens, closes, weights[k], DEV_START, band=0.02,
                        slippage_bps=slip)
            ss = bt.stats(rr, BARS)
            costs[name][f"{slip:.0f}bp"] = dict(cagr=ss["cagr"],
                                                max_drawdown=ss["max_drawdown"],
                                                sharpe=ss["sharpe"], fills=ss["fills"])

    # matched-frequency placebo: same number of exits, random session and minute
    rng = np.random.default_rng(7)
    n_ev = infos["primary"]["events"]
    placebo_sets = []
    for _ in range(40):
        ks = rng.choice(len(first), size=n_ev, replace=False)
        placebo_sets.append({int(k): int(first[k] + rng.integers(0, last[k] - first[k] + 1))
                             for k in ks})
    placebos = []
    for b in range(0, len(placebo_sets), 8):
        pw = [build_weights(ts, opens, closes, first, last, atr, **primary,
                            placebo=ties)[0] for ties in placebo_sets[b:b + 8]]
        for r in bt.run_many(ts, opens, closes, pw, DEV_START, band=0.02,
                             slippage_bps=1.0):
            s = bt.stats(r, BARS)
            placebos.append(dict(cagr=s["cagr"], dd=s["max_drawdown"],
                                 sharpe=s["sharpe"]))

    ev = event_study(ts, opens, closes, first, last, infos["primary"])

    out_doc = dict(
        agent="vol-scaled-crash-stop",
        original="research/agents2/vol-scaled-crash-stop",
        status="pending_test",
        idea="A stop distance should scale with volatility (0.7 daily ATR) but never widen past the 4% level that protects against gap nights.",
        hypothesis=("Always-long TQQQ, with an inverse-vol position size and a "
                    "one-sided ATR barrier that exits to BIL for the rest of the "
                    "trigger session and the night, should beat the old "
                    "165-day base's drawdown with a daily-return correlation "
                    "below 0.60."),
        universe=["TQQQ (long)", "BIL (cash)"],
        frozen_commit=None,
        variants_tried=len(variants),
        corr_vs_165d_baseline=out["primary"]["corr_vs_165d"],
        max_corr_vs_other_rebuilds=None,
        windows=dict(dev={"1bp": out["primary"],
                          "5bp": costs["primary"]["5bp"],
                          "10bp": costs["primary"]["10bp"]},
                     holdout=None, **{"10y": None, "5y": None}),
        marks="1m",
        benchmarks=dict(tqqq=bt.benchmark(closes[i0:, 1], ts[i0:], BARS),
                        qqq=bt.benchmark(closes[i0:, 0], ts[i0:], BARS),
                        baseline=base_s, original=None),
        variants=out, placebo=placebos, event_study=ev,
    )
    (HERE / "result.json").write_text(json.dumps(out_doc, indent=2, default=float))
    print(json.dumps({k: (round(v["cagr"], 4), round(v["max_drawdown"], 4),
                          round(v["corr_vs_165d"], 3), v["events"])
                      for k, v in out.items()}, indent=2))
    print(f"done {time.time()-t0:.0f}s -> result.json")


if __name__ == "__main__":
    main()
