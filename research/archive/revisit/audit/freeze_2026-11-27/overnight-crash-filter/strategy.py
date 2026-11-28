"""Standalone rebuild of `overnight-crash-filter`: Night Continuation / Day Reversal.

The strategy holds the leveraged index only in the block whose return the prior
block predicts, and sizes every position so that a 3-sigma gap costs a fixed
fraction of equity.  There is no moving-average gate of any length, no 165-day
regime, no round-1 stop, and no reused weights.

Rules
-----
Universe: TQQQ (night leg), QQQ (day leg), cash.

Signals, all causal:
  r_day[k]  QQQ 15:58 close / 09:30 open - 1           (known 15:58 of day k)
  gap[k]    QQQ 09:30 open / prior session close - 1    (known 09:30 of day k)
  sig_night stdev of TQQQ overnight log returns, 20 sessions through k-1
  sig_day   stdev of QQQ open-to-close log returns, 20 sessions through k-1
  sig_tot   stdev of QQQ close-to-close log returns, 20 sessions through k-1

Night leg (decided 15:58, filled 15:59 open, exits 09:30 open):
  if r_day > 0 and sig_night <= 40% and sig_tot <= 40%:
      w = min(1, target_gap / (z * sig_night_daily))
      long TQQQ from the 15:59 open to the next 09:30 open
Day leg (decided on the 09:30 bar, filled 09:31 open, exits 15:59 open):
  if gap < 0 and sig_day <= 40% and sig_tot <= 40%:
      w = day_scale * min(1, target_gap / (z * sig_day_daily))
      long QQQ from the 09:31 open (or the night exit) to the 15:59 open
Flat otherwise; the remainder is cash.  No stop, no short, no extra leverage.

Backtests are paused: this file is frozen code plus a runnable ``main`` for the
lead.  ``python strategy.py`` evaluates the development window only;
``python strategy.py --full`` adds the 10y/5y/holdout windows (lead only).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")  # column order: 0 QQQ, 1 TQQQ, 2 BIL

DEFAULTS = dict(
    vol_win=20,
    vol_ceil=0.40,
    target_gap=0.04,
    z=3.0,
    day_scale=0.50,
    morning_min=0,
    night_leg=True,
    day_leg=True,
    night_cond=True,   # require r_day > 0 for the night leg (pre-registered rule)
)


# --------------------------------------------------------------------------
# day structure and causal signals
# --------------------------------------------------------------------------
def day_arrays(ts: pd.DatetimeIndex):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return dates, first, last


def _roll_prev(x: np.ndarray, n: int) -> np.ndarray:
    """Rolling std of x through index k-1, aligned to x's index."""
    s = pd.Series(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()
    out = np.full(len(x), np.nan)
    out[1:] = s[:-1]
    return out


def build_signals(ts, opens, closes, vol_win=20):
    dates, first, last = day_arrays(ts)
    nd = len(first)
    qq_o, qq_c = opens[:, 0], closes[:, 0]
    tq_o = opens[:, 1]

    dclose = qq_c[last]
    dc_dec = qq_c[np.maximum(last - 1, first)]   # 15:58 print
    dopen = qq_o[first]

    on_ret = np.full(nd, np.nan)                  # TQQQ overnight
    on_ret[:-1] = tq_o[first[1:]] / tq_o[last[:-1]] - 1.0
    day_ret = dc_dec / dopen - 1.0                # QQQ 09:30 -> 15:58
    gap = np.full(nd, np.nan)                     # QQQ overnight gap
    gap[1:] = dopen[1:] / dclose[:-1] - 1.0
    tot_ret = np.full(nd, np.nan)                 # QQQ close-to-close
    tot_ret[1:] = dclose[1:] / dclose[:-1] - 1.0

    ann = np.sqrt(252.0)
    sig_night = _roll_prev(np.log1p(on_ret), vol_win) * ann
    sig_day = _roll_prev(np.log1p(day_ret), vol_win) * ann
    sig_tot = _roll_prev(np.log1p(tot_ret), vol_win) * ann

    return {
        "dates": dates, "first": first, "last": last, "nd": nd,
        "r_day": day_ret, "gap": gap,
        "sig_night": sig_night, "sig_day": sig_day, "sig_tot": sig_tot,
        "on_ret": on_ret, "dclose": dclose,
    }


# --------------------------------------------------------------------------
# weights
# --------------------------------------------------------------------------
def build_weights(ts, opens, closes, **kw):
    """Return (weights, info).  weights is (n, 3): QQQ, TQQQ, BIL(cash)."""
    p = {**DEFAULTS, **kw}
    s = build_signals(ts, opens, closes, vol_win=p["vol_win"])
    first, last, nd = s["first"], s["last"], s["nd"]
    n = len(ts)
    sig_night, sig_day, sig_tot = s["sig_night"], s["sig_day"], s["sig_tot"]
    r_day, gap = s["r_day"], s["gap"]
    vol_ceil = p["vol_ceil"]
    mm = int(p["morning_min"])
    sqrt252 = np.sqrt(252.0)

    p_t = np.zeros(n)     # TQQQ position held during bar i
    p_q = np.zeros(n)     # QQQ position held during bar i
    night_w = np.zeros(nd)
    info = {"night_days": 0, "day_days": 0, "ceiling_days": 0,
            "night_w_sum": 0.0, "day_w_sum": 0.0, "morning_extends": 0}

    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        if l <= f:
            continue

        # --- continuation of last night's TQQQ leg into the first hour ----
        prev_w = float(night_w[k - 1]) if k > 0 else 0.0
        if prev_w > 0 and mm > 0:
            p_t[f:min(f + mm, l)] = prev_w
            info["morning_extends"] += 1

        vol_ok_n = (np.isfinite(sig_night[k]) and sig_night[k] <= vol_ceil
                    and np.isfinite(sig_tot[k]) and sig_tot[k] <= vol_ceil)
        vol_ok_d = (np.isfinite(sig_day[k]) and sig_day[k] <= vol_ceil
                    and np.isfinite(sig_tot[k]) and sig_tot[k] <= vol_ceil)
        if np.isfinite(sig_tot[k]) and sig_tot[k] > vol_ceil:
            info["ceiling_days"] += 1

        # --- night leg: decided 15:58, filled 15:59 ----------------------
        sign_ok = (not p["night_cond"]) or (np.isfinite(r_day[k]) and r_day[k] > 0)
        if p["night_leg"] and vol_ok_n and sign_ok:
            w = min(1.0, p["target_gap"] / (p["z"] * sig_night[k] / sqrt252))
            p_t[l] = w
            night_w[k] = w
            info["night_days"] += 1
            info["night_w_sum"] += w

        # --- day leg: decided on the 09:30 bar, filled 09:31 --------------
        if p["day_leg"] and vol_ok_d and np.isfinite(gap[k]) and gap[k] < 0:
            w = p["day_scale"] * min(1.0, p["target_gap"] / (p["z"] * sig_day[k] / sqrt252))
            start = max(f + 1, f + mm) if prev_w > 0 else f + 1
            if start < l:
                p_q[start:l] = w          # hold start..l-1, exit at the 15:59 open
                info["day_days"] += 1
                info["day_w_sum"] += w

    # safety: at most one asset at a time, never more than 100%
    overlap = (p_t > 0) & (p_q > 0)
    if overlap.any():
        p_q[overlap] = 0.0
    if (p_t + p_q > 1.0 + 1e-9).any():
        raise ValueError("gross exposure above 100%")

    w = np.zeros((n, 3))
    w[:-1, 0] = p_q[1:]
    w[:-1, 1] = p_t[1:]
    w[-1, 0] = p_q[-1]
    w[-1, 1] = p_t[-1]
    assert (w >= -1e-12).all() and (w.sum(axis=1) <= 1.0 + 1e-9).all()

    info["night_w_mean"] = (info["night_w_sum"] / info["night_days"]
                            if info["night_days"] else 0.0)
    info["day_w_mean"] = (info["day_w_sum"] / info["day_days"]
                          if info["day_days"] else 0.0)
    info["bars_long"] = float(((p_t > 0) | (p_q > 0)).mean())
    info["time_in_market"] = float((info["night_days"] * 17.5
                                    + info["day_days"] * 6.5) / (24.0 * max(nd, 1)))
    return w, info


def _benchmark_correlation_weights(ts, opens, closes):
    """CORRELATION BENCHMARK ONLY.

    The old 165-day QQQ regime lives here so the brief-required correlation can
    be computed. build_weights never calls this function and the gate is not
    part of the strategy. The gate is warmed on the daily QQQ parquet (which
    starts 2015-01-02) so the baseline is fully invested from the first
    development session instead of being cold for the first 165 days.
    """
    s = build_signals(ts, opens, closes)
    dates, first, last, nd = s["dates"], s["first"], s["last"], s["nd"]
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    d = daily.set_index("date")["adjclose"].sort_index()
    sma = d.rolling(165).mean()
    gate_daily = (d.shift(1) > sma.shift(1)).fillna(False)
    # Tuning fix (2026-11-27): `dates` is per BAR; the loop below indexes the
    # gate by SESSION k, so it must be reindexed on the session dates. The old
    # code read gate[k] from the first ~2,000 bars (the first 5 sessions), so the
    # "baseline" never left its 2016-01 state (3 fills in 8 years).
    gate = gate_daily.reindex(dates[first]).ffill().fillna(False).to_numpy()
    w = np.zeros((len(ts), 3))
    for k in range(nd):
        a, b = int(first[k]), int(last[k]) + 1
        w[a:b, 1] = 1.0 if gate[k] else 0.0
        w[a:b, 2] = 0.0 if gate[k] else 1.0
    return w


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def daily_returns(ts, equity):
    return bt.daily_last(equity, ts).pct_change().dropna()


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10], "dd": float(-dd[j])}


def window_metrics(ts, o, c, w, start, slip, bench_col=1):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    i = bt.start_index(ts, start)
    b = bt.benchmark(c[i:, bench_col], ts[i:], BARS)
    out = {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                    "volatility", "exposure", "turnover")}
    out.update({"fills": int(s["fills"]), "ending_equity": float(s["ending_equity"]),
                "years": float(s["years"]),
                "benchmark": {k: float(b[k]) for k in ("cagr", "max_drawdown", "sharpe")}})
    if slip == 1.0:
        out["dd_window"] = dd_window(ts[i:], r["equity"])
        out["yearly"] = {str(k): {"strategy": float(v["strategy"]),
                                  "benchmark": float(v["benchmark"])}
                         for k, v in bt.yearly(ts[i:], r["equity"], c[i:, bench_col]).items()}
    return out, r


def sub_periods(ts, equity):
    s = pd.Series(equity, index=ts)
    out = {}
    for tag, a, b in (("2016_19", "2016-01-04", "2020-01-01"),
                      ("2020_21", "2020-01-01", "2022-01-01"),
                      ("2022_23", "2022-01-01", "2023-12-30")):
        idx = s.index
        m = ((idx >= pd.Timestamp(a, tz="America/New_York"))
             & (idx < pd.Timestamp(b, tz="America/New_York")))
        x = s[m].to_numpy()
        if len(x) < 2:
            continue
        yrs = (idx[m][-1] - idx[m][0]).days / 365.25
        peak = np.maximum.accumulate(x)
        out[tag] = {"cagr": float((x[-1] / x[0]) ** (1 / yrs) - 1),
                    "max_drawdown": float(-(x / peak - 1).min())}
    return out


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def evaluate(ts, o, c, w, info, windows, costs=(0.0, 1.0, 5.0, 10.0)):
    base_w = _benchmark_correlation_weights(ts, o, c)
    out = {"windows": {}, "corr": {}, "sub_periods": {}, "info": info}
    for tag, start in windows:
        res = {}
        for slip in costs:
            res[f"{slip:.0f}bp"], _ = window_metrics(ts, o, c, w, start, slip)
        out["windows"][tag] = res

        i = bt.start_index(ts, start)
        r1 = bt.simulate(ts[i:], o[i:], c[i:], w[i:], band=0.02, slippage_bps=1.0)
        rb = bt.simulate(ts[i:], o[i:], c[i:], base_w[i:], band=0.02, slippage_bps=1.0)
        out["corr"][tag] = float(daily_returns(ts[i:], r1["equity"]).corr(
            daily_returns(ts[i:], rb["equity"])))
        if tag == "dev":
            sb = bt.stats(rb, BARS)
            out["baseline_dev"] = {k: float(sb[k]) for k in
                                   ("cagr", "max_drawdown", "sharpe", "volatility")}
            out["sub_periods"] = sub_periods(ts[i:], r1["equity"])
            out["bench_qqq"] = {k: float(v) for k, v in
                                bt.benchmark(c[i:, 0], ts[i:], BARS).items()}
            out["bench_tqqq"] = {k: float(v) for k, v in
                                 bt.benchmark(c[i:, 1], ts[i:], BARS).items()}
    return out


def decide_status(out):
    dev = out["windows"]["dev"]["1bp"]
    base = out["baseline_dev"]
    corr = out["corr"]["dev"]
    ok = (corr < 0.60
          and dev["sharpe"] > base["sharpe"]
          and dev["max_drawdown"] < base["max_drawdown"])
    return "passed" if ok else "rejected"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="also evaluate 10y/5y/holdout (lead only)")
    args = ap.parse_args()

    end = END if args.full else DEV_END
    ts, o, c = bt.panel(SYMBOLS, DEV_START, end, "1min", warmup_days=0)
    w, info = build_weights(ts, o, c)

    windows = [("dev", DEV_START)]
    if args.full:
        windows += [("10y", START10), ("5y", START5), ("holdout", "2024-01-02")]

    out = evaluate(ts, o, c, w, info, windows)
    out.update({
        "agent": "overnight-crash-filter",
        "original": "research/agents2/overnight-crash-filter",
        "status": decide_status(out) if (not args.full or "dev" in out["windows"]) else "pending_test",
        "idea": "Night continues an up day; the day reverses a down night; size by a 3-sigma gap budget.",
        "hypothesis": "Block-conditional positions capture the overnight/intraday premium without a moving-average regime.",
        "universe": ["TQQQ", "QQQ", "CASH"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": out["corr"].get("dev"),
        "max_corr_vs_other_rebuilds": None,
        "marks": "1m",
        "params": DEFAULTS,
        "benchmarks": {
            "tqqq": out.pop("bench_tqqq", None),
            "qqq": out.pop("bench_qqq", None),
            "spy": None,
            "original": None,
        },
    })
    out["benchmarks"]["baseline_165d_dev"] = out.pop("baseline_dev", None)
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("agent", "status", "corr_vs_165d_baseline")}, indent=2))
    for tag, _ in windows:
        m = out["windows"][tag]["1bp"]
        print(f"{tag:8s} 1bp CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sharpe {m['sharpe']:4.2f}  fills {m['fills']:,}")


# --------------------------------------------------------------------------
# pre-registered neighbourhood (run only after authorization)
# --------------------------------------------------------------------------
NEIGHBOURS = [
    {},
    {"vol_win": 10}, {"vol_win": 40},
    {"vol_ceil": 0.35}, {"vol_ceil": 0.45},
    {"target_gap": 0.03}, {"target_gap": 0.05}, {"target_gap": 0.06},
    {"day_scale": 0.25}, {"day_scale": 0.75},
    {"morning_min": 30}, {"morning_min": 60},
    {"night_leg": False}, {"day_leg": False},
]


def sweep():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    ws, names = [], []
    for kw in NEIGHBOURS:
        w, _ = build_weights(ts, o, c, **kw)
        ws.append(w)
        names.append(json.dumps(kw))
    runs = bt.run_many(ts, o, c, ws, start=DEV_START, band=0.02, slippage_bps=1.0)
    rows = []
    for name, r in zip(names, runs):
        s = bt.stats(r, BARS)
        rows.append({"params": name, "cagr": s["cagr"], "dd": s["max_drawdown"],
                     "sharpe": s["sharpe"], "fills": s["fills"]})
    (HERE / "sweep.json").write_text(json.dumps(rows, indent=2, default=float))
    for r in rows:
        print(f"{r['params']:40s} {r['cagr']*100:6.2f}/{r['dd']*100:5.2f}  "
              f"Sh {r['sharpe']:4.2f}  fills {r['fills']:,}")


if __name__ == "__main__":
    if "--sweep" in sys.argv:
        sweep()
    else:
        main()
