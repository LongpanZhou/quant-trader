"""FOMC + post-OpEx calendar TQQQ with a causal volatility throttle.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Universe: QQQ (event study only), TQQQ (position), BIL (idle).

Hardcoded calendars:
  * 85 scheduled FOMC decision days, 2016 through 2026-10-23.  The 2016-2023
    development panel uses 63 of them.  Unscheduled emergency meetings are
    excluded; the cancelled 2020-03-18 meeting is excluded from the centre (a
    sensitivity adds it).
  * 130 monthly OpEx dates, 2016 through 2026-10-23 (96 in the development
    panel): third Friday, rolled back to Thursday when the Friday is a market
    holiday.

The 2024-2026 calendar dates are ex-ante schedule entries only: they are not
used by the development backtest and no 2024+ price or return data is read.
They make the same build_weights() call holdout-ready without a code change.

For an event at session k:

    FOMC:  long TQQQ from the open of k+3 through 15:59 of k+20
    OpEx:  long TQQQ from the open of k+1 through 15:59 of k+3

The union of the two window sets is held; adjacent windows are continuous.

Volatility throttle (causal):
    scale(k) = 0.5 if sigma20(k-1) / sigma100(k-1) > 1.25 else 1.0
where sigma20/sigma100 are annualised standard deviations of TQQQ daily log
returns over the last 20 / 100 sessions through the prior close.

Idle weight is BIL.  Entry targets are set on the prior session's last bar and
filled at the next session's open; calendar block ends are exited at the 15:59
open.  The harness's next-open fill rule is used unchanged.

The panel is physically truncated at 2023-12-29; no 2024+ bar is loaded.
The volatility warmup uses TQQQ daily closes 2015-01-02..2015-12-31 only.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T, COL_B = 0, 1, 2
BARS_1M = 252 * 390
BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

# Pre-registered centre.
FOMC_ENTRY, FOMC_EXIT = 3, 20
OPEX_ENTRY, OPEX_EXIT = 1, 3
RATIO_CUT = 1.25
HALF = 0.5
VOL_SHORT, VOL_LONG = 20, 100
BAND = 0.02

# Hardcoded, ex-ante calendars.  Source: Federal Reserve FOMC calendars and
# the standard monthly options-expiry rule.  No network access at run time.
FOMC = """
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
"""

OPEX = """
2016-01-15 2016-02-19 2016-03-18 2016-04-15 2016-05-20 2016-06-17 2016-07-15 2016-08-19 2016-09-16 2016-10-21 2016-11-18 2016-12-16
2017-01-20 2017-02-17 2017-03-17 2017-04-21 2017-05-19 2017-06-16 2017-07-21 2017-08-18 2017-09-15 2017-10-20 2017-11-17 2017-12-15
2018-01-19 2018-02-16 2018-03-16 2018-04-20 2018-05-18 2018-06-15 2018-07-20 2018-08-17 2018-09-21 2018-10-19 2018-11-16 2018-12-21
2019-01-18 2019-02-15 2019-03-15 2019-04-18 2019-05-17 2019-06-21 2019-07-19 2019-08-16 2019-09-20 2019-10-18 2019-11-15 2019-12-20
2020-01-17 2020-02-21 2020-03-20 2020-04-17 2020-05-15 2020-06-19 2020-07-17 2020-08-21 2020-09-18 2020-10-16 2020-11-20 2020-12-18
2021-01-15 2021-02-19 2021-03-19 2021-04-16 2021-05-21 2021-06-18 2021-07-16 2021-08-20 2021-09-17 2021-10-15 2021-11-19 2021-12-17
2022-01-21 2022-02-18 2022-03-18 2022-04-14 2022-05-20 2022-06-17 2022-07-15 2022-08-19 2022-09-16 2022-10-21 2022-11-18 2022-12-16
2023-01-20 2023-02-17 2023-03-17 2023-04-21 2023-05-19 2023-06-16 2023-07-21 2023-08-18 2023-09-15 2023-10-20 2023-11-17 2023-12-15
2024-01-19 2024-02-16 2024-03-15 2024-04-19 2024-05-17 2024-06-21 2024-07-19 2024-08-16 2024-09-20 2024-10-18 2024-11-15 2024-12-20
2025-01-17 2025-02-21 2025-03-21 2025-04-17 2025-05-16 2025-06-20 2025-07-18 2025-08-15 2025-09-19 2025-10-17 2025-11-21 2025-12-19
2026-01-16 2026-02-20 2026-03-20 2026-04-17 2026-05-15 2026-06-19 2026-07-17 2026-08-21 2026-09-18 2026-10-16
"""


def _dates(block: str) -> list[date]:
    return [date.fromisoformat(token) for token in block.split()]


FOMC_DATES = _dates(FOMC)
OPEX_DATES = _dates(OPEX)
CALENDAR_END = date(2026, 10, 23)
assert max(FOMC_DATES) <= CALENDAR_END, "FOMC date beyond the holdout end"
assert max(OPEX_DATES) <= CALENDAR_END, "OpEx date beyond the holdout end"
assert FOMC_DATES == sorted(FOMC_DATES), "FOMC dates not sorted"
assert OPEX_DATES == sorted(OPEX_DATES), "OpEx dates not sorted"


# --------------------------------------------------------------------------- #
# calendar
# --------------------------------------------------------------------------- #
def _sessions(ts):
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    sess = dates[first]
    day_of = {d: k for k, d in enumerate(sess)}
    return dates, first, last, sess, day_of


def event_windows(sess, day_of, events, a_off: int, b_off: int):
    """Inclusive session windows [k+a_off, k+b_off], clipped to the panel."""
    out = []
    n = len(sess)
    for d in events:
        k = day_of.get(d)
        if k is None:
            continue
        ka, kb = k + a_off, k + b_off
        if ka < 0 or ka >= n:
            continue
        kb = min(kb, n - 1)
        if kb >= ka:
            out.append((ka, kb))
    return out


def union_mask(n: int, windows) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for a, b in windows:
        mask[a:b + 1] = True
    return mask


def modular_mask(n: int, anchors, a_off: int, b_off: int) -> np.ndarray:
    """Window mask with wrap-around, used by the circular-shift placebo."""
    mask = np.zeros(n, dtype=bool)
    for k in anchors:
        for i in range(a_off, b_off + 1):
            mask[(k + i) % n] = True
    return mask


# --------------------------------------------------------------------------- #
# volatility throttle
# --------------------------------------------------------------------------- #
def _warm_tqqq_closes(first_session_date) -> np.ndarray:
    """TQQQ daily total-return closes strictly before the intraday archive.

    A parquet row filter is used so the 2024+ holdout rows are never read into
    memory, not merely discarded after loading.
    """
    path = bt.DATA_DIR / "TQQQ-1d-yahoo.parquet"
    daily = pd.read_parquet(
        path, columns=["date", "adjclose"],
        filters=[("date", "<", pd.Timestamp(first_session_date))])
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    return pre["adjclose"].to_numpy(dtype=float)


def _sigma(daily_closes: np.ndarray, warm: np.ndarray, window: int) -> np.ndarray:
    """Annualised stdev of log returns through each session's close."""
    allc = np.r_[warm, daily_closes]
    r = np.zeros(len(allc))
    r[1:] = np.log(allc[1:] / allc[:-1])
    vol = pd.Series(r).rolling(window, min_periods=window).std(ddof=0).to_numpy()
    return vol[len(warm):] * np.sqrt(252.0)


def vol_scale(ts, c, ratio_cut: float = RATIO_CUT, half: float = HALF,
              mode: str = "half", vol_short: int = VOL_SHORT,
              vol_long: int = VOL_LONG):
    """Per-session TQQQ scale, known at the prior session's close.

    ``mode``: "half" -> half at the cut, "flat" -> zero at the cut,
    "none" -> no throttle.  Returns (scale, ratio, sigma20, sigma100).
    """
    dates, first, last, sess, _ = _sessions(ts)
    dclose = np.asarray(c, dtype=float)[last, COL_T]
    warm = _warm_tqqq_closes(sess[0])
    s20 = _sigma(dclose, warm, vol_short)
    s100 = _sigma(dclose, warm, vol_long)
    ratio = s20 / np.maximum(s100, 1e-12)
    if mode == "none":
        raw = np.ones(len(sess))
    elif mode == "flat":
        raw = np.where(ratio > ratio_cut, 0.0, 1.0)
    else:
        raw = np.where(ratio > ratio_cut, half, 1.0)
    raw = np.where(np.isfinite(raw), raw, 0.0)
    scale = np.ones(len(sess))
    scale[1:] = raw[:-1]          # session k uses the ratio through close k-1
    return np.clip(scale, 0.0, 1.0), ratio, s20, s100


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def weights_from_mask(ts, mask: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """0..1 TQQQ targets from a session mask and a per-session scale.

    The target during session j is mask[j] * scale[j].  It is set on the last
    bar of session j-1 and filled at the open of session j.  A calendar block
    end is sold at the 15:59 open of its last session, so the position is not
    carried overnight after the window.  A pure scale change inside a live
    block is rebalanced at the next open, which keeps the vol signal causal.
    """
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    n = len(first)
    target = np.asarray(mask, dtype=float) * np.asarray(scale, dtype=float)
    bar = np.zeros(len(ts), dtype=float)
    for j in range(n):
        bar[first[j]:last[j] + 1] = target[j]
    for j in range(n - 1):
        if mask[j] and not mask[j + 1]:
            bar[last[j]] = 0.0
    w = np.zeros((len(ts), 3))
    if len(ts) > 1:
        w[:-1, COL_T] = bar[1:]
    w[:, COL_B] = 1.0 - w[:, COL_T]
    assert w.min() >= -1e-12, "negative weight"
    assert np.all(w.sum(axis=1) <= 1.0 + 1e-9), "weights sum > 1"
    return w


def calendar_mask(ts, fomc_off=(FOMC_ENTRY, FOMC_EXIT),
                  opex_off=(OPEX_ENTRY, OPEX_EXIT),
                  fomc_dates=FOMC_DATES, opex_dates=OPEX_DATES) -> np.ndarray:
    _, _, _, sess, day_of = _sessions(ts)
    windows = []
    if fomc_off is not None:
        windows += event_windows(sess, day_of, fomc_dates, *fomc_off)
    if opex_off is not None:
        windows += event_windows(sess, day_of, opex_dates, *opex_off)
    return union_mask(len(sess), windows)


def build_weights(ts, o, c, fomc_off=(FOMC_ENTRY, FOMC_EXIT),
                  opex_off=(OPEX_ENTRY, OPEX_EXIT),
                  ratio_cut: float = RATIO_CUT, half: float = HALF,
                  mode: str = "half", use_vol: bool = True) -> np.ndarray:
    """Primary weight matrix for 1-minute bars (column 1 = TQQQ)."""
    mask = calendar_mask(ts, fomc_off, opex_off)
    if use_vol and mode != "none":
        scale, _, _, _ = vol_scale(ts, c, ratio_cut, half, mode)
    else:
        scale = np.ones(int(mask.size))
    return weights_from_mask(ts, mask, scale)


# --------------------------------------------------------------------------- #
# metrics helpers
# --------------------------------------------------------------------------- #
def pack(s: dict, exposure: float | None = None) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "turnover", "fills", "ending_equity", "years")
    out = {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}
    out["calmar"] = float(s["cagr"] / s["max_drawdown"]) if s["max_drawdown"] else None
    out["exposure"] = float(s["exposure"] if exposure is None else exposure)
    return out


def run_weights(ts, o, c, w, slip: float = 1.0):
    res = bt.run(ts, o, c, w, DEV_START, band=BAND, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def mean_weight(ts, w) -> float:
    i0 = bt.start_index(ts, DEV_START)
    return float(w[i0:, COL_T].mean())


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(res["ts"].date).last().pct_change().dropna()


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def _compound_daily(r: np.ndarray, years: float | None = None) -> dict:
    eq = np.cumprod(1.0 + r)
    years = float(len(r) / 252.0) if years is None else years
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0,
            "max_drawdown": float(-(eq / peak - 1.0).min()) if len(eq) else 0.0,
            "years": float(years), "total_return": float(eq[-1] - 1.0)}


def leave_one_year_out(res: dict, year: int) -> dict:
    r = daily_returns(res)
    keep = np.array([d.year != year for d in r.index])
    return _compound_daily(r.to_numpy()[keep])


def drop_month(res: dict, year: int, month: int) -> dict:
    r = daily_returns(res)
    keep = np.array([not (d.year == year and d.month == month) for d in r.index])
    return _compound_daily(r.to_numpy()[keep])


def subperiod(ts, equity, lo: str, hi: str):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = np.asarray(equity)[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1.0 / years) - 1.0),
            "max_drawdown": float(-(x / peak - 1.0).min()),
            "years": float(years)}


def event_returns(ts, o, c, event_dates, a_off: int, b_off: int,
                  col: int) -> np.ndarray:
    """Open-to-close return of the whole window for each complete event."""
    _, first, last, sess, day_of = _sessions(ts)
    op, cl = np.asarray(o), np.asarray(c)
    out = []
    for d in event_dates:
        k = day_of.get(d)
        if k is None:
            continue
        ka, kb = k + a_off, k + b_off
        if ka < 0 or kb >= len(sess):
            continue
        out.append(cl[last[kb], col] / op[first[ka], col] - 1.0)
    return np.array(out, dtype=float)


def event_cycles(ts, o, c, event_dates, a_off: int, b_off: int,
                 col: int) -> list[dict]:
    """Per-event window return with dates, for the worst/best-cycle table."""
    _, first, last, sess, day_of = _sessions(ts)
    op, cl = np.asarray(o), np.asarray(c)
    out = []
    for d in event_dates:
        k = day_of.get(d)
        if k is None:
            continue
        ka, kb = k + a_off, k + b_off
        if ka < 0 or kb >= len(sess):
            continue
        out.append({"event": str(d), "start": str(sess[ka]),
                    "end": str(sess[kb]),
                    "ret": float(cl[last[kb], col] / op[first[ka], col] - 1.0)})
    return out


def describe_events(x: np.ndarray) -> dict:
    if len(x) < 2:
        return {"n": int(len(x))}
    se = x.std(ddof=1) / np.sqrt(len(x))
    return {"n": int(len(x)), "mean": float(x.mean()),
            "median": float(np.median(x)), "sd": float(x.std(ddof=1)),
            "t": float(x.mean() / se) if se > 0 else 0.0,
            "positive": float((x > 0).mean()),
            "min": float(x.min()), "max": float(x.max())}


def offset_profile(ts, c, event_dates, lo: int, hi: int, col: int) -> dict:
    """Mean close-to-close return at each session offset around the events."""
    _, first, last, sess, day_of = _sessions(ts)
    cl = np.asarray(c)
    out = {}
    for off in range(lo, hi + 1):
        x = []
        for d in event_dates:
            k = day_of.get(d)
            if k is None or k + off - 1 < 0 or k + off >= len(sess):
                continue
            x.append(cl[last[k + off], col] / cl[last[k + off - 1], col] - 1.0)
        x = np.array(x, dtype=float)
        if len(x) > 1:
            se = x.std(ddof=1) / np.sqrt(len(x))
            out[str(off)] = {"mean_bp": float(x.mean() * 1e4),
                             "t": float(x.mean() / se) if se > 0 else 0.0,
                             "positive": float((x > 0).mean()), "n": int(len(x))}
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    dates, first, last, sess, day_of = _sessions(ts)
    i0 = bt.start_index(ts, DEV_START)
    n_sess = len(sess)
    print(f"panel {len(ts):,} bars, {n_sess} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    # warmup sanity: the pre-2016 daily series must join the panel scale
    warm = _warm_tqqq_closes(sess[0])
    dclose = np.asarray(c, float)[last, COL_T]
    print(f"vol warmup {len(warm)} rows, last {warm[-1]:.4f}, "
          f"first panel close {dclose[0]:.4f} "
          f"({dclose[0] / warm[-1] - 1:+.2%} first-session move)")

    w = build_weights(ts, o, c)
    mask = calendar_mask(ts)
    scale, ratio, s20, s100 = vol_scale(ts, c)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)

    out = {
        "strategy": "fomc-opex-window",
        "directory": "research/new/fomc-opex-window",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "BIL"},
        "idea": "Own TQQQ in the post-decision FOMC drift and the post-OpEx "
                "flow window; BIL otherwise; halve exposure in vol spikes.",
        "rules": {
            "fomc": {"entry_offset": FOMC_ENTRY, "exit_offset": FOMC_EXIT,
                     "hold_sessions": FOMC_EXIT - FOMC_ENTRY + 1,
                     "exit": "15:59 open of the last session"},
            "opex": {"entry_offset": OPEX_ENTRY, "exit_offset": OPEX_EXIT,
                     "hold_sessions": OPEX_EXIT - OPEX_ENTRY + 1,
                     "expiry": "third Friday, holiday-rolled to Thursday"},
            "union": "sessions in either window are held; adjacent blocks merge",
            "vol_filter": {"ratio": "sigma20 / sigma100 of TQQQ daily log returns",
                           "cut": RATIO_CUT, "scale_above_cut": HALF,
                           "signal_clock": "prior session close",
                           "warmup": "TQQQ daily closes 2015-01-02..2015-12-31"},
            "costs_bp": [1.0, 5.0, 10.0],
            "band": BAND,
            "bar": BAR,
        },
        "event_count": {
            "calendar_through": CALENDAR_END.isoformat(),
            "scheduled_fomc": len(FOMC_DATES),
            "scheduled_fomc_in_dev": len(event_windows(
                sess, day_of, FOMC_DATES, FOMC_ENTRY, FOMC_EXIT)),
            "fomc_windows": len(event_windows(sess, day_of, FOMC_DATES,
                                              FOMC_ENTRY, FOMC_EXIT)),
            "opex": len(OPEX_DATES),
            "opex_in_dev": len(event_windows(
                sess, day_of, OPEX_DATES, OPEX_ENTRY, OPEX_EXIT)),
            "opex_windows": len(event_windows(sess, day_of, OPEX_DATES,
                                              OPEX_ENTRY, OPEX_EXIT)),
            "note": "totals include the 2024-2026 ex-ante calendar; the "
                    "development panel uses only the 2016-2023 events",
            "excluded": ["unscheduled emergency FOMC 2020-03-03, 2020-03-15",
                         "scheduled 2020-03-18 meeting (cancelled) in the centre"],
        },
        "dev": {},
    }

    results = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip)
        results[slip] = (res, s)
        out["dev"][f"{int(slip)}bp"] = pack(s, mean_weight(ts, w))
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"fills {s['fills']:,}  turnover {s['turnover']:.0f}")

    res1, s1 = results[1.0]
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["symbol"] = "TQQQ"
    out["benchmark_tqqq"]["bar_from_brief"] = BAR
    print(f"bench  CAGR {bench['cagr']*100:6.2f}%  "
          f"DD {bench['max_drawdown']*100:5.2f}%  Sharpe {bench['sharpe']:.2f}")

    # exposure / correlation / beta
    i0w = w[i0:, COL_T]
    target_sess = (mask * scale)
    out["exposure"] = {
        "mean_tqqq_weight_bar": float(i0w.mean()),
        "mean_tqqq_weight_session": float(target_sess[i0:].mean()),
        "fraction_sessions_full": float((target_sess[i0:] > 0.99).mean()),
        "fraction_sessions_half": float(
            ((target_sess[i0:] > 0.49) & (target_sess[i0:] < 0.51)).mean()),
        "fraction_sessions_zero": float((target_sess[i0:] < 0.01).mean()),
        "fraction_sessions_ratio_above_cut": float((ratio[i0:] > RATIO_CUT).mean()),
        "mean_bil_weight": float(1.0 - i0w.mean()),
    }
    dr = daily_returns(res1)
    br = daily_returns({"equity": c[i0:, COL_T], "ts": ts[i0:]})
    out["corr_daily_tqqq"] = float(dr.corr(br))
    out["beta_daily_tqqq"] = float(np.polyfit(br.to_numpy(), dr.to_numpy(), 1)[0])
    print("exposure", {k: round(v, 3) for k, v in out["exposure"].items()},
          "corr", round(out["corr_daily_tqqq"], 3),
          "beta", round(out["beta_daily_tqqq"], 3))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]),
                 "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"],
                              c[i0:, COL_T]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    deq = pd.Series(res1["equity"], index=res1["ts"]).groupby(res1["ts"].date).last()
    out["max_drawdown_daily"] = float(-(deq / deq.cummax() - 1.0).min())
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"],
                               "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"],
                               "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"],
                               "2022-01-03", "2023-12-29"),
    }
    print("dd window", out["dd_window"])
    print("subperiods", {k: (round(v["cagr"] * 100, 2),
                             round(v["max_drawdown"] * 100, 2))
                         for k, v in out["subperiods"].items()})

    # ---- pre-registered grid (8 cells, 1 bp) ------------------------------
    grid_spec = [
        ("G1", (3, 20), (1, 3), True, "primary: mechanism centre"),
        ("G2", (3, 15), (1, 3), True, "shorter FOMC tail"),
        ("G3", (3, 18), (1, 3), True, "shorter FOMC tail"),
        ("G4", (3, 22), (1, 3), True, "longer FOMC tail"),
        ("G5", (5, 20), (1, 3), True, "later FOMC entry"),
        ("G6", (3, 20), (1, 2), True, "shorter OpEx sleeve"),
        ("G7", (3, 20), (1, 4), True, "longer OpEx sleeve"),
        ("G8", (3, 20), (1, 3), False, "no vol filter"),
    ]
    grid = []
    for cid, fo, oo, use_vol, note in grid_spec:
        wt = build_weights(ts, o, c, fo, oo, use_vol=use_vol)
        _, s = run_weights(ts, o, c, wt)
        row = {"cell": cid, "fomc": list(fo), "opex": list(oo),
               "vol_filter": use_vol, "note": note,
               **pack(s, mean_weight(ts, wt))}
        grid.append(row)
        print(f"grid {cid} F{fo[0]}..{fo[1]} O{oo[0]}..{oo[1]} "
              f"vol={int(use_vol)}  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}")
    out["grid"] = grid

    # ---- neighbours: window ladders and filter ladders --------------------
    neigh = []

    def add_neigh(name, wt):
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": name, **pack(s, mean_weight(ts, wt))})
        print(f"neigh {name:44s} CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")

    for fo in [(2, 18), (3, 18), (4, 18), (2, 20), (4, 20),
               (3, 22), (3, 24), (3, 15), (5, 20)]:
        add_neigh(f"fomc {fo[0]}..{fo[1]}", build_weights(ts, o, c, fo))
    for oo in [(0, 2), (1, 2), (1, 4), (0, 3), (2, 4)]:
        add_neigh(f"opex {oo[0]}..{oo[1]}", build_weights(ts, o, c, opex_off=oo))
    for cut, half, mode in [(1.0, 0.5, "half"), (1.1, 0.5, "half"),
                            (1.4, 0.5, "half"), (1.5, 0.5, "half"),
                            (1.75, 0.5, "half"), (1.0, 0.0, "flat"),
                            (1.25, 0.0, "flat"), (1.5, 0.0, "flat"),
                            (1.25, 0.25, "half"), (1.25, 0.75, "half")]:
        add_neigh(f"cut {cut} {mode} {half}",
                  build_weights(ts, o, c, ratio_cut=cut, half=half, mode=mode))
    for vt in (0.45, 0.55, 0.65, 0.75):
        mask_v = calendar_mask(ts)
        sc = np.minimum(1.0, vt / np.maximum(s20, 1e-12))
        sc = np.where(np.isfinite(sc), sc, 0.0)
        sc = np.r_[1.0, sc[:-1]]
        add_neigh(f"abs vol target {vt}",
                  weights_from_mask(ts, mask_v, sc))
    out["neighbours"] = neigh

    # ---- decomposition: sleeves and constant-exposure control -------------
    controls = {}
    for name, fo, oo in [("fomc_only", (3, 20), None),
                         ("opex_only", None, (1, 3)),
                         ("union", (3, 20), (1, 3))]:
        wt = build_weights(ts, o, c, fo, oo)
        _, s = run_weights(ts, o, c, wt)
        controls[name] = pack(s, mean_weight(ts, wt))
        print(f"control {name:10s} CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")
    mean_w = float(target_sess[i0:].mean())
    wc = np.zeros((len(ts), 3))
    wc[:, COL_T] = mean_w
    wc[:, COL_B] = 1.0 - mean_w
    _, s = run_weights(ts, o, c, wc)
    controls["constant_exposure_same_mean"] = {**pack(s, mean_w), "weight": mean_w}
    print(f"control constant {mean_w:.3f}  CAGR {s['cagr']*100:6.2f}%  "
          f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}")
    wq = build_weights(ts, o, c, (3, 20), (1, 3), use_vol=False)
    _, s = run_weights(ts, o, c, wq)
    controls["union_no_filter"] = pack(s, mean_weight(ts, wq))
    out["controls"] = controls
    fomc_sess_mask = calendar_mask(ts, (3, 20), None)
    opex_sess_mask = calendar_mask(ts, None, (1, 3))
    union_sess_mask = calendar_mask(ts, (3, 20), (1, 3))
    out["sleeve_exposure"] = {
        "fomc_session_fraction": float(fomc_sess_mask[i0:].mean()),
        "opex_session_fraction": float(opex_sess_mask[i0:].mean()),
        "union_session_fraction": float(union_sess_mask[i0:].mean()),
        "overlap_session_fraction": float(
            (fomc_sess_mask & opex_sess_mask)[i0:].mean()),
    }

    # ---- event study -------------------------------------------------------
    fomc_ret_t = event_returns(ts, o, c, FOMC_DATES, 3, 20, COL_T)
    fomc_ret_q = event_returns(ts, o, c, FOMC_DATES, 3, 20, COL_Q)
    opex_ret_t = event_returns(ts, o, c, OPEX_DATES, 1, 3, COL_T)
    opex_ret_q = event_returns(ts, o, c, OPEX_DATES, 1, 3, COL_Q)
    out["event_study"] = {
        "fomc_3_20": {"tqqq": describe_events(fomc_ret_t),
                      "qqq": describe_events(fomc_ret_q)},
        "opex_1_3": {"tqqq": describe_events(opex_ret_t),
                     "qqq": describe_events(opex_ret_q)},
        "fomc_worst_cycles": sorted(
            event_cycles(ts, o, c, FOMC_DATES, 3, 20, COL_T),
            key=lambda x: x["ret"])[:5],
        "fomc_best_cycles": sorted(
            event_cycles(ts, o, c, FOMC_DATES, 3, 20, COL_T),
            key=lambda x: -x["ret"])[:5],
        "opex_worst_cycles": sorted(
            event_cycles(ts, o, c, OPEX_DATES, 1, 3, COL_T),
            key=lambda x: x["ret"])[:5],
        "opex_best_cycles": sorted(
            event_cycles(ts, o, c, OPEX_DATES, 1, 3, COL_T),
            key=lambda x: -x["ret"])[:5],
        "fomc_offset_profile_tqqq": offset_profile(ts, c, FOMC_DATES,
                                                    -8, 25, COL_T),
        "opex_offset_profile_tqqq": offset_profile(ts, c, OPEX_DATES,
                                                    -4, 5, COL_T),
    }
    print("FOMC TQQQ", {k: round(v, 3) for k, v in
                        describe_events(fomc_ret_t).items()})
    print("OpEx TQQQ", {k: round(v, 3) for k, v in
                        describe_events(opex_ret_t).items()})

    # held / unheld open-to-open
    op = np.asarray(o)[first, COL_T]
    ro = op[1:] / op[:-1] - 1.0
    held = mask[1:]
    out["held_unheld"] = {
        "held_n": int(held.sum()),
        "held_mean_bp": float(ro[held].mean() * 1e4),
        "held_t": float(ro[held].mean() / (ro[held].std(ddof=1)
                                           / np.sqrt(held.sum()))),
        "unheld_n": int((~held).sum()),
        "unheld_mean_bp": float(ro[~held].mean() * 1e4),
        "unheld_t": float(ro[~held].mean() / (ro[~held].std(ddof=1)
                                              / np.sqrt((~held).sum()))),
    }
    print("held/unheld", {k: round(v, 2) if isinstance(v, float) else v
                          for k, v in out["held_unheld"].items()})

    # ---- shift curve -------------------------------------------------------
    def shifted_weights(fomc_shift: int, opex_shift: int):
        n = n_sess
        m = np.zeros(n, dtype=bool)
        for d in FOMC_DATES:
            k = day_of.get(d)
            if k is None:
                continue
            ka, kb = k + fomc_shift + FOMC_ENTRY, k + fomc_shift + FOMC_EXIT
            if ka < 0 or kb >= n:
                continue
            m[ka:kb + 1] = True
        for d in OPEX_DATES:
            k = day_of.get(d)
            if k is None:
                continue
            ka, kb = k + opex_shift + OPEX_ENTRY, k + opex_shift + OPEX_EXIT
            if ka < 0 or kb >= n:
                continue
            m[ka:kb + 1] = True
        return weights_from_mask(ts, m, scale)

    shifts = {}
    for sft in range(-10, 11):
        wt = shifted_weights(sft, sft)
        _, st = run_weights(ts, o, c, wt)
        shifts[str(sft)] = {**pack(st, mean_weight(ts, wt)),
                            "note": "joint shift; full windows only"}
        print(f"shift {sft:+3d}  CAGR {st['cagr']*100:6.2f}%  "
              f"DD {st['max_drawdown']*100:5.2f}%")
    fomc_shifts = {}
    for sft in range(-10, 11):
        wt = shifted_weights(sft, 0)
        _, st = run_weights(ts, o, c, wt)
        fomc_shifts[str(sft)] = {"cagr": float(st["cagr"]),
                                 "max_drawdown": float(st["max_drawdown"])}
    opex_shifts = {}
    for sft in range(-5, 6):
        wt = shifted_weights(0, sft)
        _, st = run_weights(ts, o, c, wt)
        opex_shifts[str(sft)] = {"cagr": float(st["cagr"]),
                                 "max_drawdown": float(st["max_drawdown"])}
    out["shift_curve"] = {"joint": shifts, "fomc_only": fomc_shifts,
                          "opex_only": opex_shifts}
    best = max(shifts, key=lambda k: shifts[k]["cagr"])
    print("shift peak", best, "cagr", round(shifts[best]["cagr"] * 100, 2))

    # ---- random-calendar placebo ------------------------------------------
    rng = np.random.default_rng(20261127)
    fomc_idx = [day_of[d] for d in FOMC_DATES if d in day_of]
    opex_idx = [day_of[d] for d in OPEX_DATES if d in day_of]

    def placebo_stats(m, sc=None):
        sc = scale if sc is None else sc
        wt = weights_from_mask(ts, m, sc)
        r = bt.run(ts, o, c, wt, DEV_START, band=BAND, slippage_bps=1.0)
        st = bt.stats(r, BARS_1M)
        return (float(st["cagr"]), float(st["max_drawdown"]),
                float(st["sharpe"]), float((m[i0:] * sc[i0:]).mean()))

    real_expo = mean_weight(ts, w)
    draws = 1000
    circ = np.empty((draws, 4))
    for j in range(draws):
        sft = int(rng.integers(1, n_sess))
        m = (modular_mask(n_sess, [(k + sft) % n_sess for k in fomc_idx],
                          FOMC_ENTRY, FOMC_EXIT)
             | modular_mask(n_sess, [(k + sft) % n_sess for k in opex_idx],
                            OPEX_ENTRY, OPEX_EXIT))
        circ[j] = placebo_stats(m)
    rng2 = np.random.default_rng(20261128)

    years = np.array([d.year for d in sess])
    months = np.array([d.month for d in sess])
    by_year, by_month = {}, {}
    for k in range(n_sess):
        by_year.setdefault(int(years[k]), []).append(k)
        by_month.setdefault((int(years[k]), int(months[k])), []).append(k)
    rand = np.empty((draws, 4))
    rand_match = np.empty((draws, 4))
    for j in range(draws):
        f_anch = []
        for y, idx in by_year.items():
            f_anch += list(rng2.choice(idx, size=min(8, len(idx)), replace=False))
        o_anch = [int(rng2.choice(idx)) for idx in by_month.values()]
        m = np.zeros(n_sess, dtype=bool)
        for k in f_anch:
            m[k + FOMC_ENTRY:min(k + FOMC_EXIT, n_sess - 1) + 1] = True
        for k in o_anch:
            m[k + OPEX_ENTRY:min(k + OPEX_EXIT, n_sess - 1) + 1] = True
        base = placebo_stats(m)
        rand[j] = base
        # Exposure-matched null: same calendar, position scaled so the mean
        # TQQQ weight equals the primary's.  Clipped at 100% TQQQ, so very
        # low-exposure draws cannot reach the primary's exposure.
        mult = real_expo / max(base[3], 1e-9)
        rand_match[j] = placebo_stats(m, np.clip(scale * mult, 0.0, 1.0))

    # Jittered calendar: keep every event count and spacing, shift each event
    # independently within a small window.  This destroys the exact phase but
    # preserves the duty cycle much more closely than uniform random anchors.
    rng3 = np.random.default_rng(20261129)
    jitter = np.empty((draws, 4))
    for j in range(draws):
        m = np.zeros(n_sess, dtype=bool)
        for k in fomc_idx:
            sft = int(rng3.integers(-10, 11))
            ka, kb = k + FOMC_ENTRY + sft, k + FOMC_EXIT + sft
            if ka < 0 or kb >= n_sess:
                continue
            m[ka:kb + 1] = True
        for k in opex_idx:
            sft = int(rng3.integers(-5, 6))
            ka, kb = k + OPEX_ENTRY + sft, k + OPEX_EXIT + sft
            if ka < 0 or kb >= n_sess:
                continue
            m[ka:kb + 1] = True
        jitter[j] = placebo_stats(m)

    real = (float(s1["cagr"]), float(s1["max_drawdown"]), float(s1["sharpe"]))

    def placebo_summary(a, label):
        cg, dd, sh, ex = a.T
        return {
            "label": label, "n_draws": int(len(a)),
            "cagr": {"median": float(np.median(cg)),
                     "p90": float(np.quantile(cg, 0.90)),
                     "p95": float(np.quantile(cg, 0.95)),
                     "p99": float(np.quantile(cg, 0.99)),
                     "max": float(cg.max()),
                     "percentile_of_real": float((cg < real[0]).mean())},
            "max_drawdown": {"median": float(np.median(dd)),
                             "p05": float(np.quantile(dd, 0.05)),
                             "min": float(dd.min()),
                             "percentile_of_real": float((dd < real[1]).mean())},
            "sharpe": {"median": float(np.median(sh)),
                       "p95": float(np.quantile(sh, 0.95)),
                       "max": float(sh.max()),
                       "percentile_of_real": float((sh < real[2]).mean())},
            "exposure": {"median": float(np.median(ex)),
                         "p05": float(np.quantile(ex, 0.05)),
                         "p95": float(np.quantile(ex, 0.95))},
            "n_cagr_ge_real": int((cg >= real[0]).sum()),
            "n_dd_le_real": int((dd <= real[1]).sum()),
            "n_joint": int(((cg >= real[0]) & (dd <= real[1])).sum()),
            "joint_fraction": float(((cg >= real[0]) & (dd <= real[1])).mean()),
        }

    out["placebo"] = {
        "real": {"cagr": real[0], "max_drawdown": real[1], "sharpe": real[2],
                 "exposure": mean_weight(ts, w)},
        "circular_shift": placebo_summary(circ, "whole calendar shifted 1..n"),
        "random_calendar": placebo_summary(
            rand, "8 FOMC anchors/year, 1 OpEx anchor/month, random phase"),
        "random_calendar_exposure_matched": placebo_summary(
            rand_match, "same random calendars, scaled to the primary exposure"),
        "jittered_calendar": placebo_summary(
            jitter, "each event shifted independently, same counts/spacing"),
    }
    for key in ("circular_shift", "random_calendar",
                "random_calendar_exposure_matched", "jittered_calendar"):
        p = out["placebo"][key]
        print(f"placebo {key}: CAGR median {p['cagr']['median']*100:.1f}% "
              f"p95 {p['cagr']['p95']*100:.1f}% max {p['cagr']['max']*100:.1f}% "
              f"joint {p['n_joint']}/{p['n_draws']} "
              f"expo {p['exposure']['median']*100:.1f}%")

    # ---- cut tests ---------------------------------------------------------
    best_month = None
    mret = daily_returns(res1)
    midx = pd.to_datetime(mret.index)
    monthly = (1.0 + mret).groupby([midx.year, midx.month]).prod() - 1.0
    by = monthly.idxmax()
    best_month = (int(by[0]), int(by[1]))
    cuts = {}
    for year in (2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023):
        cuts[f"ex_{year}"] = leave_one_year_out(res1, year)
    cuts["drop_best_month"] = drop_month(res1, *best_month)
    cuts["best_month"] = {"year": best_month[0], "month": best_month[1],
                          "return": float(monthly.max())}
    out["cut_tests"] = cuts
    print("cut ex-2020", {k: round(v, 4) for k, v in cuts["ex_2020"].items()})
    print("cut drop best month", best_month,
          {k: round(v, 4) for k, v in cuts["drop_best_month"].items()})

    # ---- sensitivities -----------------------------------------------------
    sens = {}
    extra = FOMC_DATES + [date(2020, 3, 18)]
    wt = build_weights(ts, o, c)
    m_extra = union_mask(n_sess,
                         event_windows(sess, day_of, extra, FOMC_ENTRY, FOMC_EXIT)
                         + event_windows(sess, day_of, OPEX_DATES,
                                         OPEX_ENTRY, OPEX_EXIT))
    wt_extra = weights_from_mask(ts, m_extra, scale)
    _, s = run_weights(ts, o, c, wt_extra)
    sens["include_cancelled_2020_03_18"] = pack(s, mean_weight(ts, wt_extra))
    print("sens cancelled 2020-03-18  CAGR", round(s["cagr"] * 100, 2),
          "DD", round(s["max_drawdown"] * 100, 2))
    out["sensitivities"] = sens

    # ---- causality: truncation test ---------------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j2 = bt.start_index(ts, "2021-12-30")
    w_trunc = build_weights(ts[:j], o[:j], c[:j])
    diff = np.abs(w_trunc[:j2] - w[:j2]).max()
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "compare_through": "2021-12-29",
        "prior_weights_unchanged": bool(diff < 1e-12),
        "max_abs_diff": float(diff),
    }
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
