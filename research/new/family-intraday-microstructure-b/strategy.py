"""Opening-drive continuation with close-strength persistence (intraday only).

Frozen development-window strategy for the intraday-microstructure family.

Rules (09:45 center)
--------------------
Signal asset : QQQ 1-minute bars, regular session 09:30-16:00 ET.
Position     : TQQQ when long, BIL when flat. Long only, weights sum to <= 1.

At 09:45 ET each session:
    p     = QQQ close of the 09:45 bar
    open  = QQQ open of the 09:30 bar (session open)
    vwap  = volume-weighted average of QQQ typical price, 09:30..09:45
    signal = (p > open) and (p > vwap)

Entry:
    If flat and signal is true, target 100% TQQQ on the 09:45 bar close;
    the harness fills at the 09:46 open (next bar).

While in a position:
    1. Close-strength check at 15:00 ET: if QQQ at 15:00 is not above both
       the session open and the session VWAP (09:30..15:00), target 100% BIL
       on the 15:00 bar close; fill at 15:01 open.  On half-days, the check
       uses the second-to-last bar of the session and fills at the last open.
    2. Minimum hold: five sessions from entry, refreshed to five sessions
       from today whenever the 09:45 signal is true.  After the minimum hold
       has elapsed, a false 09:45 signal targets BIL on the 09:45 bar close;
       fill at 09:46 open.
    3. If the 09:45 signal is true, the position continues and the minimum
       hold window is refreshed.

No daily trend SMA, no volatility/drawdown regime, no relative strength.
No hard stop or vol-target overlay in the primary.  The close-strength exit
is the mandate's "close-auction strength" variant.  The entry-day-VWAP stop,
hard stops and trailing stops are tested as overlays and reported.

All signals are causal: the 09:45 signal uses bars through 09:45, the 15:00
check uses bars through 15:00, and every fill is at the next bar's open.
No full-sample normalisation is used.

Development window only: 2016-01-04 .. 2023-12-29.  The 2024-2026 holdout is
never loaded.
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

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
OUT = Path(__file__).resolve().parent

# Frozen center.  The 8-cell grid is below.
CFG = dict(
    decision="i945",       # i945 / i10 / i1030
    threshold_bps=0.0,     # 0 / 20 / 50
    min_hold=5,            # sessions; refreshed while the signal confirms
    close_check="i1500",   # 15:00 close-strength check
    close_mode="not_both", # exit when QQQ is not above both open and VWAP
    refresh=True,          # extend the minimum hold while the signal confirms
    flat="BIL",
)

# Pre-registered 8-cell grid (fixed before the final run; see HYPOTHESIS.md).
GRID = [
    ("center_0945_thr0_N5_close15", {}),
    ("decision_1000", dict(decision="i10")),
    ("decision_1030", dict(decision="i1030")),
    ("threshold_20bp", dict(threshold_bps=20.0)),
    ("threshold_50bp", dict(threshold_bps=50.0)),
    ("min_hold_3", dict(min_hold=3)),
    ("min_hold_2", dict(min_hold=2)),
    ("fixed_5_session_exit", dict(close_check=None, refresh=False)),
]


def load_dev():
    """1-minute QQQ/TQQQ/BIL panel on the development window only."""
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END,
                                 "1min", warmup_days=0)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(symbol):
        df = bt.load_1m(symbol)
        df = df[(df["ts"] >= lo) & (df["ts"] <= hi)]
        return df.set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("QQQ"), prep("TQQQ")


def session_tables(ts, qqq):
    """Per-session opening drive, VWAP and close-strength inputs.

    All fields are built from bars at or before the decision/check bar.  The
    per-session tables are only containers; no future bar is used.
    """
    dates, first, last = bt.day_bounds(ts)
    tod = np.asarray(ts.hour * 60 + ts.minute)
    qh = qqq["high"].to_numpy()
    ql = qqq["low"].to_numpy()
    qc = qqq["close"].to_numpy()
    qo = qqq["open"].to_numpy()
    qv = qqq["volume"].to_numpy()
    n_sessions = len(first)
    out = []
    for k in range(n_sessions):
        s, e = int(first[k]), int(last[k])
        d = {"k": k, "s": s, "e": e, "date": dates[s]}
        # Decision bars: 09:40, 09:45, 09:50, 10:00, 10:30.
        for minute, key in ((580, "i940"), (585, "i945"), (590, "i950"),
                            (600, "i10"), (630, "i1030")):
            j = int(np.searchsorted(tod[s:e], minute))
            d[key] = s + j if (j < e - s and tod[s + j] == minute) else -1
        # 15:00 close-strength bar; half-days fall back to the penultimate bar.
        j15 = int(np.searchsorted(tod[s:e], 900))
        if j15 < e - s and tod[s + j15] == 900:
            d["i1500"] = s + j15
        else:
            d["i1500"] = e - 2 if e - s >= 2 else -1
        # Cumulative VWAP at each decision/check bar.
        tp = (qh[s:e] + ql[s:e] + qc[s:e]) / 3.0
        vol = qv[s:e]
        cv = np.cumsum(tp * vol)
        cvv = np.cumsum(vol)
        for key in ("i940", "i945", "i950", "i10", "i1030", "i1500"):
            i = d[key]
            if i >= 0 and i >= s:
                j = i - s
                d["vw_" + key] = float(cv[j] / cvv[j]) if cvv[j] > 0 else np.nan
                d["p_" + key] = float(qc[i])
            else:
                d["vw_" + key] = np.nan
                d["p_" + key] = np.nan
        d["qopen"] = float(qo[s])
        d["qclose158"] = float(qc[e - 2]) if e - s >= 2 else np.nan
        d["qclose"] = float(qc[e - 1])
        out.append(d)
    return out


def build_weights(ts, qqq, cfg=None):
    """Build (n, 3) QQQ/TQQQ/BIL weights and a trade log.

    Weights are 0/1.  BIL is held whenever TQQQ is not.  `weights[i]` is the
    target set on bar i's close and fills at bar i+1's open.
    """
    c = dict(CFG)
    if cfg:
        c.update(cfg)
    sess = session_tables(ts, qqq)
    n_sessions = len(sess)
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    thr = c["threshold_bps"] / 10_000.0
    in_pos = False
    entry_k = -1
    entry_bar = -1
    hold_until = -1
    trades = []

    def close_pos(exit_bar, k, reason):
        nonlocal in_pos
        if exit_bar <= entry_bar:
            exit_bar = entry_bar + 1
        exit_bar = min(exit_bar, len(ts))
        w[entry_bar:exit_bar, 1] = 1.0
        w[entry_bar:exit_bar, 2] = 0.0
        # From exit_bar onward the default BIL weight applies.
        w[exit_bar:, 1] = 0.0
        w[exit_bar:, 2] = 1.0
        trades.append({"entry_k": entry_k, "exit_k": k, "reason": reason,
                       "entry_bar": int(entry_bar), "exit_bar": int(exit_bar)})
        in_pos = False

    for k in range(n_sessions):
        d = sess[k]
        dec = c["decision"]
        i = d[dec]
        if i < 0 or not np.isfinite(d["vw_" + dec]):
            continue
        sig = (d["p_" + dec] > d["qopen"] * (1.0 + thr)) and \
              (d["p_" + dec] > d["vw_" + dec] * (1.0 + thr))

        if not in_pos:
            if sig:
                in_pos = True
                entry_k = k
                entry_bar = i
                hold_until = k + c["min_hold"] - 1
            continue

        # 1) Close-strength exit (can shorten the hold, including the entry day).
        if c["close_check"] is not None:
            ik = d[c["close_check"]]
            if ik >= 0 and np.isfinite(d["vw_" + c["close_check"]]):
                p = d["p_" + c["close_check"]]
                op = d["qopen"]
                vw = d["vw_" + c["close_check"]]
                mode = c["close_mode"]
                if mode == "not_both":
                    weak = not (p > op and p > vw)
                elif mode == "both":
                    weak = (p < op) and (p < vw)
                elif mode == "vwap":
                    weak = p < vw
                else:
                    weak = False
                if weak:
                    close_pos(ik, k, "close_weak")
                    continue

        # 2) Minimum hold not elapsed: keep the position.
        if k < hold_until:
            continue

        # 3) At/after the minimum hold: extend on confirmation, exit on failure.
        if sig:
            if c["refresh"]:
                hold_until = max(hold_until, k + c["min_hold"] - 1)
            else:
                close_pos(d["e"] - 2, k, "time")
        else:
            if c["refresh"]:
                close_pos(i, k, "fail")
            else:
                close_pos(d["e"] - 2, k, "time")

    if in_pos:
        close_pos(len(ts) - 1, n_sessions - 1, "eod")
    return w, trades, sess


def metrics(ts, opens, closes, w, slip):
    """Harness metrics plus daily marks, exposure and correlation."""
    res = bt.run(ts, opens, closes, w, DEV_START, band=0.02,
                 slippage_bps=slip)
    s = bt.stats(res, BARS_1M)
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(closes[i0:, 1], ts[i0:], BARS_1M)
    eq = pd.Series(res["equity"], index=res["ts"])
    daily = eq.groupby(eq.index.date).last()
    dr = daily.pct_change().dropna()
    peak_d = np.maximum.accumulate(daily.to_numpy())
    dd_d = float(-(daily.to_numpy() / peak_d - 1.0).min())
    sharpe_d = (float(dr.mean() / dr.std(ddof=0) * np.sqrt(252))
                if dr.std(ddof=0) > 0 else 0.0)
    bench_daily = pd.Series(closes[i0:, 1], index=ts[i0:])
    bench_daily = bench_daily.groupby(bench_daily.index.date).last().pct_change().dropna()
    corr = float(dr.corr(bench_daily.reindex(dr.index)))
    yr = bt.yearly(res["ts"], res["equity"],
                   closes[i0:i0 + len(res["ts"]), 1])
    wslice = w[i0:i0 + len(res["ts"])]
    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": dd_d,
        "sharpe": float(s["sharpe"]),
        "sharpe_daily": sharpe_d,
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "total_return": float(s["total_return"]),
        "ending_equity": float(s["ending_equity"]),
        "years": float(s["years"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "exposure_total": float(s["exposure"]),
        "tqqq_exposure": float(np.mean(wslice[:, 1] > 0)),
        "tqqq_avg_weight": float(np.mean(wslice[:, 1])),
        "bil_exposure": float(np.mean(wslice[:, 2] > 0)),
        "corr_to_tqqq_daily": corr,
        "yearly": {str(y): {"strategy": float(v["strategy"]),
                            "benchmark": float(v["benchmark"])}
                   for y, v in yr.items()},
        "benchmark": {"cagr": float(bench["cagr"]),
                      "max_drawdown": float(bench["max_drawdown"]),
                      "sharpe": float(bench["sharpe"]),
                      "volatility": float(bench["volatility"])},
    }
    return out, res, daily


def trade_stats(trades, sess):
    """Entry count, holding period and exit reasons."""
    if not trades:
        return {"entries": 0, "avg_hold_sessions": 0.0,
                "median_hold_sessions": 0.0, "reasons": {}}
    holds = [t["exit_k"] - t["entry_k"] + 1 for t in trades]
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    first = sess[0]["date"]
    last = sess[-1]["date"]
    return {
        "entries": len(trades),
        "avg_hold_sessions": float(np.mean(holds)),
        "median_hold_sessions": float(np.median(holds)),
        "reasons": reasons,
        "first_entry": str(trades[0]["entry_k"]),
        "last_entry": str(trades[-1]["entry_k"]),
        "sessions": len(sess),
        "calendar": [str(first), str(last)],
    }


def cut_stats(daily):
    """Two equal calendar halves and odd/even years."""
    out = {}
    halves = [("2016-2019", "2016-01-04", "2019-12-31"),
              ("2020-2023", "2020-01-01", "2023-12-29")]
    for name, lo, hi in halves:
        v = daily[(daily.index >= pd.Timestamp(lo).date()) &
                  (daily.index <= pd.Timestamp(hi).date())]
        if len(v) < 2:
            continue
        peak = np.maximum.accumulate(v.to_numpy())
        dd = float(-(v.to_numpy() / peak - 1.0).min())
        cagr = float((v.iloc[-1] / v.iloc[0]) ** (252.0 / len(v)) - 1.0)
        out[name] = {"cagr": cagr, "max_drawdown": dd, "sessions": int(len(v))}
    # Odd/even calendar-year split of daily returns.
    years = np.array([x.year for x in daily.index])
    rets = daily.pct_change().dropna()
    years_r = years[1:]
    for label, mask in (("odd_years", years_r % 2 == 1),
                        ("even_years", years_r % 2 == 0)):
        r = rets[mask]
        if len(r) < 2:
            continue
        eq = (1.0 + r).cumprod()
        peak = np.maximum.accumulate(eq.to_numpy())
        out[label] = {
            "cagr": float(eq.iloc[-1] ** (252.0 / len(eq)) - 1.0),
            "max_drawdown": float(-(eq.to_numpy() / peak - 1.0).min()),
        }
    return out


def placebo(ts, qqq, sess, observed_cagr_1, observed_cagr_5, n_draws=300,
            seed=11):
    """Shuffle the 09:45 signal days and rerun the same state machine."""
    base = np.zeros(len(sess), dtype=bool)
    for k, d in enumerate(sess):
        i = d["i945"]
        if i < 0 or not np.isfinite(d["vw_i945"]):
            continue
        base[k] = (d["p_i945"] > d["qopen"]) and (d["p_i945"] > d["vw_i945"])
    rng = np.random.default_rng(seed)
    n = len(sess)
    # Fast path: build weights from a signal array, reusing the session tables.
    def build_from_sig(sig):
        w = np.zeros((len(ts), 3))
        w[:, 2] = 1.0
        in_pos = False
        entry_k = -1
        entry_bar = -1
        hold_until = -1

        def close_pos(exit_bar, k):
            nonlocal in_pos
            if exit_bar <= entry_bar:
                exit_bar = entry_bar + 1
            exit_bar = min(exit_bar, len(ts))
            w[entry_bar:exit_bar, 1] = 1.0
            w[entry_bar:exit_bar, 2] = 0.0
            w[exit_bar:, 1] = 0.0
            w[exit_bar:, 2] = 1.0
            in_pos = False

        for k in range(n):
            d = sess[k]
            i = d["i945"]
            if i < 0:
                continue
            s = bool(sig[k])
            if not in_pos:
                if s:
                    in_pos = True
                    entry_k = k
                    entry_bar = i
                    hold_until = k + 5 - 1
                continue
            ik = d["i1500"]
            if ik >= 0 and np.isfinite(d["vw_i1500"]):
                p = d["p_i1500"]
                weak = not (p > d["qopen"] and p > d["vw_i1500"])
                if weak:
                    close_pos(ik, k)
                    continue
            if k < hold_until:
                continue
            if s:
                hold_until = max(hold_until, k + 5 - 1)
            else:
                close_pos(i, k)
        if in_pos:
            close_pos(len(ts) - 1, n - 1)
        return w

    c1, c5, dd5 = [], [], []
    for _ in range(n_draws):
        perm = base.copy()
        rng.shuffle(perm)
        w = build_from_sig(perm)
        m1, _, _ = metrics(ts, None, None, w, 1.0) if False else (None, None, None)
        # metrics() needs opens/closes; call bt directly here for speed.
        r1 = bt.run(ts, _OPENS, _CLOSES, w, DEV_START, band=0.02,
                    slippage_bps=1.0)
        s1 = bt.stats(r1, BARS_1M)
        r5 = bt.run(ts, _OPENS, _CLOSES, w, DEV_START, band=0.02,
                    slippage_bps=5.0)
        s5 = bt.stats(r5, BARS_1M)
        c1.append(float(s1["cagr"]))
        c5.append(float(s5["cagr"]))
        dd5.append(float(s5["max_drawdown"]))
    c1 = np.array(c1)
    c5 = np.array(c5)
    dd5 = np.array(dd5)
    return {
        "draws": n_draws,
        "signal_days": int(base.sum()),
        "observed_1bp_cagr": float(observed_cagr_1),
        "observed_5bp_cagr": float(observed_cagr_5),
        "placebo_1bp_mean": float(c1.mean()),
        "placebo_1bp_median": float(np.median(c1)),
        "placebo_1bp_p95": float(np.quantile(c1, 0.95)),
        "p_1bp": float((c1 >= observed_cagr_1).mean()),
        "placebo_5bp_mean": float(c5.mean()),
        "placebo_5bp_median": float(np.median(c5)),
        "placebo_5bp_p95": float(np.quantile(c5, 0.95)),
        "p_5bp": float((c5 >= observed_cagr_5).mean()),
        "placebo_5bp_dd_mean": float(dd5.mean()),
        "placebo_5bp_dd_median": float(np.median(dd5)),
    }


_OPENS = None
_CLOSES = None


def main():
    global _OPENS, _CLOSES
    ts, opens, closes, qqq, tqqq = load_dev()
    _OPENS, _CLOSES = opens, closes
    w, trades, sess = build_weights(ts, qqq, CFG)
    trades_stats = trade_stats(trades, sess)
    i0 = bt.start_index(ts, DEV_START)

    def bench(col):
        b = bt.benchmark(closes[i0:, col], ts[i0:], BARS_1M)
        return {"cagr": float(b["cagr"]),
                "max_drawdown": float(b["max_drawdown"]),
                "sharpe": float(b["sharpe"]),
                "volatility": float(b["volatility"])}

    result = {
        "agent": "family-intraday-microstructure-b",
        "family": "intraday-microstructure",
        "status": "dev_1bp_pass_cost_fragile",
        "strategy": "Opening-drive continuation with close-strength persistence",
        "window": {"start": DEV_START, "end": DEV_END},
        "frozen_center": {
            "decision_time": "09:45 ET",
            "confirmation_threshold_bps": CFG["threshold_bps"],
            "min_hold_sessions": CFG["min_hold"],
            "close_check": "15:00 ET QQQ above session open and session VWAP",
            "close_exit_fill": "15:01 open (next bar)",
            "failed_signal_exit": "09:46 open after a false 09:45 signal once the minimum hold has elapsed",
            "min_hold_refresh": "extended to 5 sessions from today while the 09:45 signal is true",
            "flat_asset": "BIL",
            "hard_stop": None,
            "vol_target": None,
            "band": 0.02,
            "slippage_bps": [1.0, 5.0, 10.0],
        },
        "rules": {
            "signal": "QQQ close(09:45) > QQQ open(09:30) and > VWAP(09:30..09:45, typical price x volume)",
            "entry": "100% TQQQ at the 09:45 bar close; fill at 09:46 open",
            "close_strength": "at 15:00, hold overnight only if QQQ is above both the session open and the session VWAP (09:30..15:00); otherwise BIL at the 15:00 close, fill at 15:01 open",
            "minimum_hold": "5 sessions; refreshed while the 09:45 signal is true",
            "failed_signal": "once the minimum hold has elapsed, a false 09:45 signal exits at 09:46 open",
            "half_days": "close-strength check falls back to the penultimate session bar and fills at the last open",
            "costs": "1 bp headline; 5 bp and 10 bp reported; 2% band; next-open fills",
            "overlays": "entry-day-VWAP stop, hard stop and trailing stop tested and rejected (report)",
        },
        "bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82,
                "source": "task brief; harness-computed dev benchmark also below"},
        "benchmarks": {"tqqq": bench(1), "qqq": bench(0), "bil": bench(2)},
        "headline": {},
        "grid": {},
        "sensitivity": {},
        "placebo": {},
        "cuts": {},
        "trades": trades_stats,
        "reconciliation_10am_daily": {},
        "pass": {},
        "verdict": "",
    }

    for slip, key in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        m, res, daily = metrics(ts, opens, closes, w, slip)
        result["headline"][key] = m
        if key == "1bp":
            result["cuts"] = cut_stats(daily)

    m1 = result["headline"]["1bp"]
    m5 = result["headline"]["5bp"]
    result["pass"] = {
        "cagr_above_bar_1bp": bool(m1["cagr"] > 0.3672),
        "drawdown_below_60_1bp": bool(m1["max_drawdown"] < 0.60),
        "sharpe_above_bar_1bp": bool(m1["sharpe"] > 0.82),
        "cagr_above_bar_5bp": bool(m5["cagr"] > 0.3672),
        "drawdown_below_60_5bp": bool(m5["max_drawdown"] < 0.60),
        "calmar_1bp": float(m1["cagr"] / m1["max_drawdown"]),
        "benchmark_calmar": float(m1["benchmark"]["cagr"] /
                                  m1["benchmark"]["max_drawdown"]),
        "note": ("1 bp dev pass; 5 bp fails the CAGR bar.  The result is "
                 "cost-fragile and is not a robust above-TQQQ strategy."),
    }
    result["verdict"] = (
        "Frozen 09:45 center passes the 1 bp dev bar (CAGR 38.20% > 36.72%, "
        "DD 58.54% < 60%) but fails at 5 bp (CAGR 25.4%) and 10 bp (CAGR 11.0%). "
        "The lead's 10:00 center fails even at 1 bp (CAGR 27.3%).  The 43.65% "
        "prototype is not reproducible with a causal 10:00->15:59 hold; the "
        "causal version is 6.60% at 1 bp.  Best honest result: a fragile, "
        "1-bp-only near-pass, not a cost-robust family winner."
    )

    # Pre-registered 8-cell grid at 1 bp.
    for name, over in GRID:
        wg, trg, sessg = build_weights(ts, qqq, dict(CFG, **over))
        mg, _, _ = metrics(ts, opens, closes, wg, 1.0)
        result["grid"][name] = {
            "overrides": over,
            "cagr": mg["cagr"],
            "max_drawdown": mg["max_drawdown"],
            "sharpe": mg["sharpe"],
            "tqqq_exposure": mg["tqqq_exposure"],
            "fills": mg["fills"],
            "turnover": mg["turnover"],
            "corr_to_tqqq_daily": mg["corr_to_tqqq_daily"],
            "entries": trade_stats(trg, sessg)["entries"],
        }

    # The lead's 10:00 one-session version, reproduced causally.
    w10 = np.zeros((len(ts), 3))
    w10[:, 2] = 1.0
    for d in sess:
        i = d["i10"]
        if i < 0 or not np.isfinite(d["vw_i10"]):
            continue
        if d["p_i10"] > d["qopen"] and d["p_i10"] > d["vw_i10"]:
            w10[i:d["e"] - 1, 1] = 1.0
            w10[i:d["e"] - 1, 2] = 0.0
            w10[d["e"] - 1:, 1] = 0.0
            w10[d["e"] - 1:, 2] = 1.0
    for slip, key in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        m10, _, _ = metrics(ts, opens, closes, w10, slip)
        result["reconciliation_10am_daily"][key] = {
            "cagr": m10["cagr"],
            "max_drawdown": m10["max_drawdown"],
            "sharpe": m10["sharpe"],
            "turnover": m10["turnover"],
            "tqqq_exposure": m10["tqqq_exposure"],
        }
    # Signal-day attribution: pre-10:00, post-10:00 and close-to-close.
    tqqq_close = tqqq["close"].to_numpy()
    tqqq_open = tqqq["open"].to_numpy()
    post = []
    cc = []
    for k, d in enumerate(sess):
        i = d["i10"]
        if i < 0:
            continue
        if d["p_i10"] > d["qopen"] and d["p_i10"] > d["vw_i10"]:
            e = d["e"]
            post.append(tqqq_close[e - 1] / tqqq_close[i] - 1.0)
            if k > 0:
                cc.append(tqqq_close[e - 1] / tqqq_close[sess[k - 1]["e"] - 1] - 1.0)
    result["reconciliation_10am_daily"]["signal_day_tqqq"] = {
        "n_signal_days": len(post),
        "mean_10am_to_close_pct": float(np.mean(post) * 100.0),
        "mean_close_to_close_pct": float(np.mean(cc) * 100.0),
        "note": ("close-to-close includes the overnight and the 09:30-10:00 "
                 "move and is not tradable from a 10:00 signal; the causal "
                 "10:00->close mean is the post figure."),
    }

    # Overlay/falsifier tests (not part of the 8-cell grid).
    overlays = {
        "entry_day_vwap_stop": dict(close_check=None, refresh=True),
        "hard_stop_15pct": dict(hard_stop=0.15),
        "trailing_stop_20pct": dict(trail=0.20),
        "hard_cap_5_no_close": dict(close_check=None, refresh=False),
        "decision_0940": dict(decision="i940"),
        "decision_0950": dict(decision="i950"),
        "min_hold_4": dict(min_hold=4),
        "min_hold_6": dict(min_hold=6),
        "threshold_10bp": dict(threshold_bps=10.0),
    }
    for name, over in overlays.items():
        if name == "entry_day_vwap_stop":
            # The entry-day VWAP stop is implemented by the 15:58 close check
            # in the exploratory code; reproduce it with a dedicated build.
            wg, trg, sessg = build_weights_entry_vwap_stop(ts, qqq, CFG)
        elif name == "hard_stop_15pct":
            wg, trg, sessg = build_weights_stop(ts, qqq, CFG, hard=0.15)
        elif name == "trailing_stop_20pct":
            wg, trg, sessg = build_weights_stop(ts, qqq, CFG, trail=0.20)
        else:
            wg, trg, sessg = build_weights(ts, qqq, dict(CFG, **over))
        mg, _, _ = metrics(ts, opens, closes, wg, 1.0)
        result["sensitivity"][name] = {
            "overrides": over,
            "cagr": mg["cagr"],
            "max_drawdown": mg["max_drawdown"],
            "sharpe": mg["sharpe"],
            "tqqq_exposure": mg["tqqq_exposure"],
            "fills": mg["fills"],
            "entries": trade_stats(trg, sessg)["entries"],
        }

    # Placebo: shuffled 09:45 signal days, same state machine.
    result["placebo"] = placebo(ts, qqq, sess, m1["cagr"], m5["cagr"],
                                n_draws=300)

    # Sanity checks.
    for key in ("1bp", "5bp", "10bp"):
        for k, v in result["headline"][key].items():
            if isinstance(v, float) and not np.isfinite(v):
                raise ValueError(f"non-finite {key} {k}")
    if result["headline"]["1bp"]["cagr"] < 0.30:
        raise ValueError("center result unexpectedly low; check the build")

    (OUT / "result.json").write_text(json.dumps(result, indent=2),
                                     encoding="utf-8")

    print("\nOpening-drive continuation, frozen 09:45 center")
    for key in ("1bp", "5bp", "10bp"):
        m = result["headline"][key]
        print(f"  {key:3s}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:6.2f}%  "
              f"Sharpe {m['sharpe']:.2f}  TQQQ exp {m['tqqq_exposure']*100:.1f}%  "
              f"fills {m['fills']}  turnover {m['turnover']:.0f}x  "
              f"corr {m['corr_to_tqqq_daily']:.2f}")
    b = result["benchmarks"]["tqqq"]
    print(f"  TQQQ bench: CAGR {b['cagr']*100:.2f}%  DD {b['max_drawdown']*100:.2f}%  "
          f"Sharpe {b['sharpe']:.2f}")
    print("\nPre-registered grid (1 bp):")
    for name, g in result["grid"].items():
        print(f"  {name:34s} CAGR {g['cagr']*100:6.2f}%  DD {g['max_drawdown']*100:6.2f}%  "
              f"Sharpe {g['sharpe']:.2f}  exp {g['tqqq_exposure']*100:4.1f}%  "
              f"entries {g['entries']}")
    print("\nYearly (1 bp):")
    for y, v in result["headline"]["1bp"]["yearly"].items():
        print(f"  {y}: {v['strategy']*100:8.2f}%  TQQQ {v['benchmark']*100:8.2f}%")
    print("\nPlacebo:", result["placebo"])
    print(f"\nwrote {OUT / 'result.json'}")


def build_weights_entry_vwap_stop(ts, qqq, cfg):
    """Overlay: exit when QQQ closes below the entry-day VWAP.

    This is the lead's suggested entry-day VWAP stop.  It is not the primary
    and is reported only as a falsifier.  The entry-day VWAP is the 09:45
    VWAP (or the decision-time VWAP for other decision times).
    """
    c = dict(CFG)
    if cfg:
        c.update(cfg)
    sess = session_tables(ts, qqq)
    n_sessions = len(sess)
    qc = qqq["close"].to_numpy()
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    thr = c["threshold_bps"] / 10_000.0
    in_pos = False
    entry_k = -1
    entry_bar = -1
    entry_vwap = np.nan
    hold_until = -1
    trades = []

    def close_pos(exit_bar, k, reason):
        nonlocal in_pos
        if exit_bar <= entry_bar:
            exit_bar = entry_bar + 1
        exit_bar = min(exit_bar, len(ts))
        w[entry_bar:exit_bar, 1] = 1.0
        w[entry_bar:exit_bar, 2] = 0.0
        w[exit_bar:, 1] = 0.0
        w[exit_bar:, 2] = 1.0
        trades.append({"entry_k": entry_k, "exit_k": k, "reason": reason})
        in_pos = False

    for k in range(n_sessions):
        d = sess[k]
        dec = c["decision"]
        i = d[dec]
        if i < 0 or not np.isfinite(d["vw_" + dec]):
            continue
        sig = (d["p_" + dec] > d["qopen"] * (1.0 + thr)) and \
              (d["p_" + dec] > d["vw_" + dec] * (1.0 + thr))
        if not in_pos:
            if sig:
                in_pos = True
                entry_k = k
                entry_bar = i
                entry_vwap = d["vw_" + dec]
                hold_until = k + c["min_hold"] - 1
            continue
        if d["qclose158"] < entry_vwap:
            close_pos(d["e"] - 1, k, "entry_vwap_stop")
            continue
        if k < hold_until:
            continue
        if sig:
            hold_until = max(hold_until, k + c["min_hold"] - 1)
        else:
            close_pos(i, k, "fail")
    if in_pos:
        close_pos(len(ts) - 1, n_sessions - 1, "eod")
    return w, trades, sess


def build_weights_stop(ts, qqq, cfg, hard=None, trail=None):
    """Overlay: hard or trailing stop on the TQQQ 15:58 close."""
    c = dict(CFG)
    if cfg:
        c.update(cfg)
    sess = session_tables(ts, qqq)
    n_sessions = len(sess)
    tqqq = bt.load_1m("TQQQ")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    tqqq = tqqq[(tqqq["ts"] >= lo) & (tqqq["ts"] <= hi)]
    tqqq = tqqq.set_index("ts").reindex(ts).ffill()
    tc = tqqq["close"].to_numpy()
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    thr = c["threshold_bps"] / 10_000.0
    in_pos = False
    entry_k = -1
    entry_bar = -1
    entry_px = np.nan
    peak = np.nan
    hold_until = -1
    trades = []

    def close_pos(exit_bar, k, reason):
        nonlocal in_pos
        if exit_bar <= entry_bar:
            exit_bar = entry_bar + 1
        exit_bar = min(exit_bar, len(ts))
        w[entry_bar:exit_bar, 1] = 1.0
        w[entry_bar:exit_bar, 2] = 0.0
        w[exit_bar:, 1] = 0.0
        w[exit_bar:, 2] = 1.0
        trades.append({"entry_k": entry_k, "exit_k": k, "reason": reason})
        in_pos = False

    for k in range(n_sessions):
        d = sess[k]
        dec = c["decision"]
        i = d[dec]
        if i < 0 or not np.isfinite(d["vw_" + dec]):
            continue
        sig = (d["p_" + dec] > d["qopen"] * (1.0 + thr)) and \
              (d["p_" + dec] > d["vw_" + dec] * (1.0 + thr))
        if not in_pos:
            if sig:
                in_pos = True
                entry_k = k
                entry_bar = i
                entry_px = tc[i]
                peak = entry_px
                hold_until = k + c["min_hold"] - 1
            continue
        peak = max(peak, tc[d["e"] - 2])
        stop_hit = False
        if hard is not None and tc[d["e"] - 2] < entry_px * (1.0 - hard):
            stop_hit = True
        if trail is not None and tc[d["e"] - 2] < peak * (1.0 - trail):
            stop_hit = True
        if stop_hit:
            close_pos(d["e"] - 1, k, "stop")
            continue
        ik = d[c["close_check"]] if c["close_check"] else -1
        if ik >= 0 and np.isfinite(d["vw_" + c["close_check"]]):
            p = d["p_" + c["close_check"]]
            weak = not (p > d["qopen"] and p > d["vw_" + c["close_check"]])
            if weak:
                close_pos(ik, k, "close_weak")
                continue
        if k < hold_until:
            continue
        if sig:
            if c["refresh"]:
                hold_until = max(hold_until, k + c["min_hold"] - 1)
            else:
                close_pos(d["e"] - 2, k, "time")
        else:
            if c["refresh"]:
                close_pos(i, k, "fail")
            else:
                close_pos(d["e"] - 2, k, "time")
    if in_pos:
        close_pos(len(ts) - 1, n_sessions - 1, "eod")
    return w, trades, sess


if __name__ == "__main__":
    main()
