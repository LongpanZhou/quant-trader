"""Gap-fill-fade round-3 rebuild: short QQQ on confirmed failed small gap-ups.

STATUS: design only. The 2026-11-26 clarification pauses backtests. This file
is complete but ``main()`` refuses to run unless REVISIT_RUN=1 is set by the
lead after authorization. It does not write result.json by default.

The strategy is deliberately not the old overlay. It is flat (BIL) by default,
never holds TQQQ, never holds overnight, and takes an outright short QQQ only
when a small gap-up in a weak, stressed tape has already failed in the first
30 minutes. See hypothesis.md and spec.md for the argument and exact rules.

Run (only after authorization):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:REVISIT_RUN = "1"
    python research/revisit/gap-fill-fade/strategy.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START_DEV = "2016-01-04"
END_DEV = "2023-12-29"
END = "2026-10-23"
START10 = "2017-01-03"
START5 = "2021-10-25"
BARS_PER_YEAR = 252 * 390

# primary parameters (see spec.md for the +/-1 neighbourhood)
GAP_LO = 0.0010
GAP_HI = 0.0075
WEAK_MA = 10
CONFIRM_R30 = 0.0          # require r30 < 0
STOP_MODE = "or"           # opening-range high, floored/capped
STOP_FLOOR = 0.002         # stop at least 0.2% above entry
STOP_CAP = 0.015           # stop at most 1.5% above entry
STOP_FIXED = 0.010         # control only
TIME_STOP_MIN = 11 * 60 + 30
VOL_TARGET = 0.10
VOL_FLOOR = 0.10
SIZE_MAX = 1.00
BORROW_ANNUAL = 0.005      # 0.5%/yr, brief minimum
ENTRY_OFFSET = 31          # 10:01 open is f+31
SIGNAL_OFFSET = 30         # 10:00 close is f+30


# ---------------------------------------------------------------------------
# sessions and the synthetic inverse-QQQ asset
# ---------------------------------------------------------------------------
def _sessions(ts: pd.DatetimeIndex):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return dates, first, last


def inverse_qqq(opens, closes, first, last, entry_offset=ENTRY_OFFSET,
                borrow_annual=BORROW_ANNUAL):
    """Session-reset, linear short-QQQ price series.

    At the entry open the value is 1.0. For every later bar t in the session:
        inv_open[t]  = 1 - (QQQ_open[t]  / QQQ_open[e] - 1)
        inv_close[t] = 1 - (QQQ_close[t] / QQQ_open[e] - 1)
    so the return from the entry open to any later open is exactly the negative
    of QQQ's return over that interval. The borrow cost is a small linear decay
    applied from e to the session end. This is an implementation device for a
    short in a long-only engine, not a tradable inverse ETF.
    """
    n = len(opens)
    inv_o = np.ones(n)
    inv_c = np.ones(n)
    borrow_daily = borrow_annual / 252.0
    for f, l in zip(first, last):
        e = f + entry_offset
        if e >= l:
            continue
        base = opens[e, 0]
        if not np.isfinite(base) or base <= 0:
            continue
        # Tuning 2026-11-27: accrue per elapsed minute of a 390-minute day.
        # The old divisor (l - e) used the session's length, which is not
        # known before the session ends.
        for i in range(e, l + 1):
            decay = 1.0 - borrow_daily * ((i - e) / 390.0)
            inv_o[i] = (1.0 - (opens[i, 0] / base - 1.0)) * decay
            inv_c[i] = (1.0 - (closes[i, 0] / base - 1.0)) * decay
    return inv_o, inv_c


def _minute_of_day(t) -> int:
    return int(t.hour) * 60 + int(t.minute)


# ---------------------------------------------------------------------------
# signal and weights
# ---------------------------------------------------------------------------
def build_weights(ts, opens, closes, high, low, gap_lo=GAP_LO, gap_hi=GAP_HI,
                  weak_ma=WEAK_MA, confirm_r30=CONFIRM_R30,
                  stop_mode=STOP_MODE, stop_floor=STOP_FLOOR,
                  stop_cap=STOP_CAP, stop_fixed=STOP_FIXED,
                  time_stop_min=TIME_STOP_MIN, vol_target=VOL_TARGET,
                  vol_floor=VOL_FLOOR, size_max=SIZE_MAX, stress_mult=1.0,
                  use_confirmation=True, random_entry=False, seed=7,
                  borrow_annual=BORROW_ANNUAL):
    """Return (weights, info).

    weights is (n, 4): QQQ, TQQQ, BIL, INV_QQQ. The strategy only ever holds
    BIL or the synthetic inverse QQQ. ``high`` and ``low`` are the QQQ 1-minute
    high/low arrays aligned to ``ts``. info contains the event list and the
    daily signal frame for diagnostics.
    """
    dates, first, last = _sessions(ts)
    n = len(ts)
    dclose = closes[last, 0]
    prior = np.r_[np.nan, dclose[:-1]]
    gap = opens[first, 0] / prior - 1.0

    sma = pd.Series(dclose).rolling(weak_ma).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ret5 = pd.Series(dclose).pct_change(5).shift(1).to_numpy()
    vol20 = (pd.Series(dclose).pct_change().rolling(20).std(ddof=0).shift(1).to_numpy()
             * np.sqrt(252.0))
    vol_med = pd.Series(vol20).rolling(252, min_periods=60).median().to_numpy()

    weak = (prior < sma_prev) & (ret5 < 0)
    stress = vol20 > vol_med * stress_mult
    band = (gap >= gap_lo) & (gap <= gap_hi)

    valid = (first + SIGNAL_OFFSET) <= last
    open0930 = opens[first, 0]
    close1000 = np.full(len(first), np.nan)
    r30 = np.full(len(first), np.nan)
    close1000[valid] = closes[first[valid] + SIGNAL_OFFSET, 0]
    r30[valid] = close1000[valid] / open0930[valid] - 1.0
    or_high = np.array([high[f:f + SIGNAL_OFFSET].max() if v else np.nan
                        for f, v in zip(first, valid)])
    gap_open = close1000 > prior
    if use_confirmation:
        confirm = (r30 < confirm_r30) & (close1000 < open0930)
    else:
        confirm = np.ones(len(first), bool)
    signal = weak & stress & band & gap_open & confirm
    signal &= np.isfinite(gap) & np.isfinite(r30) & np.isfinite(vol20) & np.isfinite(vol_med)

    size = np.clip(vol_target / vol20, vol_floor, size_max)
    size = np.where(np.isfinite(size), size, 0.0)

    w = np.zeros((n, 4))
    w[:, 2] = 1.0  # BIL default
    events = []
    rng = np.random.default_rng(seed)
    for k, (f, l) in enumerate(zip(first, last)):
        if not signal[k] or not valid[k]:
            continue
        e = f + ENTRY_OFFSET
        if e >= l:
            continue
        entry = opens[e, 0]
        if not np.isfinite(entry):
            continue
        target = prior[k]
        # Tuning 2026-11-27: the old skip tested opens[e] (the 10:01 fill bar)
        # at the 10:00 decision, a one-bar look-ahead. Use the 10:00 close.
        if closes[e - 1, 0] <= target:
            continue
        if stop_mode == "or":
            stop_px = min(max(or_high[k], entry * (1.0 + stop_floor)),
                          entry * (1.0 + stop_cap))
        else:
            stop_px = entry * (1.0 + stop_fixed)
        start_i = e
        if random_entry:
            upper = min(f + 90, l)  # 10:01-11:00, before the time stop
            if upper <= e:
                continue
            start_i = int(rng.integers(e, upper))
            entry = opens[start_i, 0]
            if closes[start_i - 1, 0] <= target:
                continue
            if stop_mode == "or":
                stop_px = min(max(or_high[k], entry * (1.0 + stop_floor)),
                              entry * (1.0 + stop_cap))
            else:
                stop_px = entry * (1.0 + stop_fixed)
        exit_i = l - 1
        reason = "eod"
        for i in range(start_i, l):
            if high[i] >= stop_px:
                exit_i, reason = i, "stop"
                break
            if low[i] <= target:
                exit_i, reason = i, "target"
                break
            if _minute_of_day(ts[i]) >= time_stop_min:
                exit_i, reason = i, "time"
                break
        exit_i = min(exit_i, l - 1)
        s = float(size[k])
        entry_sig = start_i - 1
        w[entry_sig:exit_i, 3] = s
        w[entry_sig:exit_i, 2] = 1.0 - s
        w[exit_i, 3] = 0.0
        w[exit_i, 2] = 1.0
        exit_px = opens[min(exit_i + 1, l), 0]
        events.append({
            "date": str(dates[f]), "gap": float(gap[k]), "r30": float(r30[k]),
            "vol20": float(vol20[k]), "size": s, "entry": float(entry),
            "exit": float(exit_px), "entry_i": int(start_i),
            "exit_i": int(exit_i), "hold_min": int(exit_i - start_i + 1),
            "reason": reason,
            "gross_ret": float(-(exit_px / entry - 1.0)),
            "borrow_ret": float(-(borrow_annual / 252.0) * ((exit_i - start_i + 1) / 390.0)),
        })
    info = {"events": events, "n_events": len(events),
            "signal": pd.DataFrame({"date": dates[first], "gap": gap, "r30": r30,
                                    "vol20": vol20, "weak": weak, "stress": stress,
                                    "band": band, "gap_open": gap_open,
                                    "confirm": confirm, "signal": signal,
                                    "size": size})}
    return w, info


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def _stats(result):
    s = bt.stats(result, BARS_PER_YEAR)
    return {"cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
            "sharpe": s["sharpe"], "sortino": s["sortino"],
            "volatility": s["volatility"], "fills": s["fills"],
            "turnover": s["turnover"], "exposure": s["exposure"],
            "ending_equity": s["ending_equity"]}


def _window(ts, opens, closes, weights, start, end=None, slip=1.0):
    i0 = bt.start_index(ts, start)
    i1 = len(ts) if end is None else int(ts.searchsorted(
        pd.Timestamp(end, tz="America/New_York").normalize()
        + pd.Timedelta(days=1)))
    r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], weights[i0:i1],
                    band=0.02, slippage_bps=slip)
    return _stats(r), r


def _event_stats(events, slip):
    if not events:
        return {"n": 0}
    pnl = np.array([e["gross_ret"] + e["borrow_ret"] - 2.0 * slip / 10_000.0
                    for e in events])
    n = len(pnl)
    t = pnl.mean() / pnl.std(ddof=1) * np.sqrt(n) if n > 1 and pnl.std(ddof=1) > 0 else 0.0
    rng = np.random.default_rng(11)
    boot = np.array([rng.choice(pnl, size=n, replace=True).mean() for _ in range(10_000)])
    return {
        "n": int(n), "mean": float(pnl.mean()), "median": float(np.median(pnl)),
        "win_rate": float((pnl > 0).mean()), "t_stat": float(t),
        "bootstrap_p": float((boot <= 0).mean()),
        "bootstrap_ci_low": float(np.quantile(boot, 0.025)),
        "bootstrap_ci_high": float(np.quantile(boot, 0.975)),
        "avg_hold_min": float(np.mean([e["hold_min"] for e in events])) if n else 0.0,
        "reasons": {r: int(sum(1 for e in events if e["reason"] == r))
                    for r in ("stop", "target", "time", "eod")},
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    if os.environ.get("REVISIT_RUN") != "1":
        print("Backtests are paused by the 2026-11-26 clarification.")
        print("Set REVISIT_RUN=1 only after the lead authorizes the dev run.")
        return

    overlap = os.environ.get("REVISIT_ALLOW_OVERLAP") == "1"
    panel_end = END if overlap else END_DEV
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START_DEV, panel_end, "1min")
    dates, first, last = _sessions(ts)
    inv_o, inv_c = inverse_qqq(opens, closes, first, last)
    all_opens = np.column_stack([opens, inv_o])
    all_closes = np.column_stack([closes, inv_c])

    q = bt.load_1m("QQQ").set_index("ts").reindex(ts).ffill()
    qqq_high = q["high"].to_numpy()
    qqq_low = q["low"].to_numpy()

    w, info = build_weights(ts, all_opens, all_closes, qqq_high, qqq_low)
    out = {"agent": "gap-fill-fade", "original": "research/agents2/gap-fill-fade",
           "status": "pending",
           "idea": "Short QQQ on confirmed failed small gap-ups in a weak, stressed tape.",
           "hypothesis": "The confirmed gap-failure short has positive net expectancy after 1 bp and low correlation with the 165-day base.",
           "universe": ["QQQ short (synthetic inverse in bt.py)", "BIL cash"],
           "frozen_commit": "PENDING", "variants_tried": 0,
           "corr_vs_165d_baseline": None, "max_corr_vs_other_rebuilds": None,
           "windows": {}, "marks": "1m", "benchmarks": {}}

    # Dev-only by default. The 10y/5y windows overlap the holdout, so they are
    # only computed when the lead explicitly authorizes the overlap.
    windows = [("dev", START_DEV, END_DEV)]
    if overlap:
        windows += [("10y", START10, END), ("5y", START5, END)]
    for wname, start, end in windows:
        out["windows"][wname] = {}
        for slip in (1, 5, 10):
            s, _ = _window(ts, all_opens, all_closes, w, start, end, slip)
            out["windows"][wname][f"{slip}bp"] = s
    out["windows"].setdefault("10y", {})
    out["windows"].setdefault("5y", {})
    out["windows"]["holdout"] = {}

    out["event_study"] = _event_stats(info["events"], 1.0)

    out["sub_periods"] = {}
    for name, a, b in (("2016-19", "2016-01-04", "2019-12-31"),
                       ("2020-21", "2020-01-01", "2021-12-31"),
                       ("2022-23", "2022-01-01", "2023-12-29")):
        s, _ = _window(ts, all_opens, all_closes, w, a, b, 1.0)
        out["sub_periods"][name] = s

    variants = []
    for glo, ghi in ((0.0005, 0.0060), (0.0010, 0.0075), (0.0015, 0.0090)):
        variants.append((f"gap_{glo}_{ghi}", dict(gap_lo=glo, gap_hi=ghi)))
    for ma in (5, 10, 20):
        variants.append((f"weak_ma_{ma}", dict(weak_ma=ma)))
    for sm in (0.0, 1.25):
        variants.append((f"stress_{sm}", dict(stress_mult=sm)))
    for c in (0.0, -0.0010):
        variants.append((f"confirm_{c}", dict(confirm_r30=c,
                                              use_confirmation=(c is not None))))
    for fl in (0.001, 0.003):
        variants.append((f"stop_floor_{fl}", dict(stop_floor=fl)))
    for cap in (0.010, 0.020):
        variants.append((f"stop_cap_{cap}", dict(stop_cap=cap)))
    variants.append(("fixed_1pct", dict(stop_mode="fixed", stop_fixed=0.010)))
    for tm in (11 * 60, 11 * 60 + 30, 12 * 60):
        variants.append((f"time_{tm}", dict(time_stop_min=tm)))
    for vt in (0.08, 0.10, 0.12):
        variants.append((f"vol_{vt}", dict(vol_target=vt)))
    variants.append(("no_confirmation", dict(use_confirmation=False)))
    variants.append(("random_entry", dict(random_entry=True)))

    wlist, names = [w], ["primary"]
    for name, kw in variants:
        ww, _ = build_weights(ts, all_opens, all_closes, qqq_high, qqq_low, **kw)
        wlist.append(ww)
        names.append(name)
    out["variants_tried"] = len(variants)
    results = bt.run_many(ts, all_opens, all_closes, wlist, START_DEV, band=0.02,
                          slippage_bps=1.0)
    out["neighbourhood"] = {name: _stats(r) for name, r in zip(names, results)}

    # The 165-day baseline is a benchmark, not part of the strategy. The lead's
    # correlations.json pipeline computes this number; build_weights never
    # touches a 165-day gate.
    out["corr_vs_165d_baseline"] = None

    i0 = bt.start_index(ts, START_DEV)
    i1 = int(ts.searchsorted(pd.Timestamp(END_DEV, tz="America/New_York").normalize()
                             + pd.Timedelta(days=1)))
    for nm, col in (("tqqq", 1), ("qqq", 0)):
        b = bt.benchmark(all_closes[i0:i1, col], ts[i0:i1], BARS_PER_YEAR)
        out["benchmarks"][nm] = {"cagr": b["cagr"], "max_drawdown": b["max_drawdown"],
                                 "sharpe": b["sharpe"]}
    try:
        orig = json.loads((ROOT / "research" / "agents2" / "gap-fill-fade" /
                           "result.json").read_text())
        out["benchmarks"]["original"] = {
            "10y_1bp": orig["windows"]["10y"]["1bp"],
            "5y_1bp": orig["windows"]["5y"]["1bp"],
        }
    except Exception:
        out["benchmarks"]["original"] = {}
    try:
        spy = pd.read_parquet(ROOT / "data" / "round3" / "yahoo" /
                              "SPY-1d-yahoo.parquet")
        spy["date"] = pd.to_datetime(spy["date"]).dt.date
        spy = spy[(spy.date >= pd.Timestamp(START_DEV).date()) &
                  (spy.date <= pd.Timestamp(END_DEV).date())]
        px = spy["adjclose"].to_numpy()
        yrs = (pd.Timestamp(END_DEV) - pd.Timestamp(START_DEV)).days / 365.25
        peak = np.maximum.accumulate(px)
        out["benchmarks"]["spy"] = {
            "cagr": float((px[-1] / px[0]) ** (1 / yrs) - 1),
            "max_drawdown": float(-(px / peak - 1).min())}
    except Exception:
        out["benchmarks"]["spy"] = {}

    (Path(__file__).resolve().parent / "result.json").write_text(
        json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("windows", "event_study",
                                          "corr_vs_165d_baseline")}, indent=2,
                     default=float))


if __name__ == "__main__":
    main()
