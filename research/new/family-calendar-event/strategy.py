"""FOMC + monthly-OpEx calendar TQQQ, development window only.

Rule
----
Hold TQQQ at 100% inside the union of two hardcoded calendar windows, BIL
otherwise:

    FOMC decision +2 .. +15 trading sessions   (primary)
    monthly OpEx  -1 .. +3 trading sessions    (primary)

The calendar is the primary signal.  A causal TQQQ realised-vol gate is
available only as a pre-registered risk variant (G7 soft, G8 hard); the
delivered primary G3 has no gate.

Calendars
---------
FOMC decision dates and monthly third-Friday OpEx dates are hardcoded for
2015-12 through 2026-10-23.  The 2024-2026 entries are ex-ante schedule dates
and are never used by this development run: the panel is truncated at
2023-12-29.  They exist so the same ``build_weights`` works on a holdout panel
without editing the calendar.  Unscheduled FOMC actions (2020-03-03 and
2020-03-15) are excluded because their dates were not knowable in advance;
the March 2020 scheduled meeting is also excluded because the actual decision
was the 2020-03-15 emergency action.  OpEx is the third Friday, moved to the
preceding Thursday when the third Friday is Good Friday (2019-04-18,
2022-04-14, 2025-04-17).

Timing and fills
----------------
``target[k]`` is the TQQQ fraction held during session k, decided at the close
of session k-1.  The weight written on the last bar of k-1 is filled by the
shared ``research/bt.py`` simulator at the next session's 09:30 open.  The 2%
band and 1 bp headline / 5 bp / 10 bp costs are the harness defaults.

Development window: 2016-01-04 .. 2023-12-29.  No 2024+ bar enters the weights
or the simulation.  The panel is asserted to end on 2023-12-29.

Run:
    cd C:\\Users\\27175\\Desktop\\quant-trader-research
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-calendar-event/strategy.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
START_DATE = date.fromisoformat(START)
END_DATE = date.fromisoformat(END)
BARS_PER_YEAR = 252 * 390
BAND = 0.02
COSTS = (1.0, 5.0, 10.0)
TQQQ_BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
TARGET_DD = 0.60

# Primary / pre-registered centre (G3).
P_FOMC_START = 2
P_FOMC_END = 15
P_OPEX_START = -1
P_OPEX_END = 3

# Vol risk variants only.
P_GATE_Q = 0.75
P_GATE_WIN = 20
P_GATE_LOOK = 252

# ---------------------------------------------------------------------------
# Hardcoded ex-ante calendars.
# FOMC = second day of each scheduled meeting.  2015-12 is included so the
# post-decision window that crosses into 2016 is known; 2024-2026 are future
# schedule dates and are inert in the development run.
# ---------------------------------------------------------------------------
FOMC_TXT = """
2015-12-16
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
FOMC = sorted({date.fromisoformat(tok) for tok in FOMC_TXT.split()})

# Monthly OpEx: third Friday, moved to Thursday when the third Friday is a
# market holiday (Good Friday).  2015-12 and 2024-2026 included for the same
# boundary / holdout-readiness reason.
OPEX_TXT = """
2015-12-18
2016-01-15 2016-02-19 2016-03-18 2016-04-15 2016-05-20 2016-06-17
2016-07-15 2016-08-19 2016-09-16 2016-10-21 2016-11-18 2016-12-16
2017-01-20 2017-02-17 2017-03-17 2017-04-21 2017-05-19 2017-06-16
2017-07-21 2017-08-18 2017-09-15 2017-10-20 2017-11-17 2017-12-15
2018-01-19 2018-02-16 2018-03-16 2018-04-20 2018-05-18 2018-06-15
2018-07-20 2018-08-17 2018-09-21 2018-10-19 2018-11-16 2018-12-21
2019-01-18 2019-02-15 2019-03-15 2019-04-18 2019-05-17 2019-06-21
2019-07-19 2019-08-16 2019-09-20 2019-10-18 2019-11-15 2019-12-20
2020-01-17 2020-02-21 2020-03-20 2020-04-17 2020-05-15 2020-06-19
2020-07-17 2020-08-21 2020-09-18 2020-10-16 2020-11-20 2020-12-18
2021-01-15 2021-02-19 2021-03-19 2021-04-16 2021-05-21 2021-06-18
2021-07-16 2021-08-20 2021-09-17 2021-10-15 2021-11-19 2021-12-17
2022-01-21 2022-02-18 2022-03-18 2022-04-14 2022-05-20 2022-06-17
2022-07-15 2022-08-19 2022-09-16 2022-10-21 2022-11-18 2022-12-16
2023-01-20 2023-02-17 2023-03-17 2023-04-21 2023-05-19 2023-06-16
2023-07-21 2023-08-18 2023-09-15 2023-10-20 2023-11-17 2023-12-15
2024-01-19 2024-02-16 2024-03-15 2024-04-19 2024-05-17 2024-06-21
2024-07-19 2024-08-16 2024-09-20 2024-10-18 2024-11-15 2024-12-20
2025-01-17 2025-02-21 2025-03-21 2025-04-17 2025-05-16 2025-06-20
2025-07-18 2025-08-15 2025-09-19 2025-10-17 2025-11-21 2025-12-19
2026-01-16 2026-02-20 2026-03-20 2026-04-17 2026-05-15 2026-06-19
2026-07-17 2026-08-21 2026-09-18 2026-10-16
"""
OPEX = sorted({date.fromisoformat(tok) for tok in OPEX_TXT.split()})

# The 1-minute archive starts on 2016-01-04, so the only event whose window
# straddles the development start is the 2015-12-16 FOMC.  Dec 17 2015 is +1,
# and 2016-01-04 is +11 sessions (Dec 24 is a half session, Dec 25 closed).
# A virtual anchor of -11 makes Jan 4 2016 index 0 = anchor +11.
VIRTUAL_ANCHORS = {date(2015, 12, 16): -11}


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def _calendar(ts):
    dates, first, last = bt.day_bounds(ts)
    return dates, first, last, dates[first]


def _anchor(sess, d: date):
    """First trading session on/after d, or a virtual pre-panel anchor."""
    if d in VIRTUAL_ANCHORS:
        return VIRTUAL_ANCHORS[d]
    if d < sess[0]:
        return None
    i = int(np.searchsorted(sess, d))
    if i >= len(sess):
        return None
    return i


def _event_windows(sess, dates, start: int, end: int, shift: int = 0,
                   exclude=frozenset()):
    """(event date, anchor, first held session, last held session)."""
    out = []
    n = len(sess)
    for d in dates:
        if d in exclude:
            continue
        a = _anchor(sess, d)
        if a is None:
            continue
        a2 = a + shift
        s = max(0, a2 + start)
        e = min(n - 1, a2 + end)
        if s <= e:
            out.append((d, a2, s, e))
    return out


def _held_sessions(n_sess: int, windows) -> np.ndarray:
    held = np.zeros(n_sess, dtype=bool)
    for _, _, s, e in windows:
        held[s:e + 1] = True
    return held


def _vol_gate(c, first, last, floor: float):
    """One-session-shifted TQQQ vol gate.

    ``gate[k]`` uses the close of session k-1 only.  A NaN vol (warm-up) leaves
    the gate open.  The threshold is the trailing 252-session 75th percentile
    of the 20-session realised vol, with at least 60 observations.
    """
    close = np.asarray(c[last, 1], dtype=float)
    r = np.zeros(len(close), dtype=float)
    r[1:] = np.log(close[1:] / close[:-1])
    vol = pd.Series(r).rolling(P_GATE_WIN, min_periods=P_GATE_WIN).std(ddof=0)
    vol = (vol * np.sqrt(252.0)).to_numpy()
    thr = pd.Series(vol).rolling(P_GATE_LOOK, min_periods=60).quantile(P_GATE_Q)
    thr = thr.to_numpy()
    state = np.isfinite(vol) & np.isfinite(thr) & (vol > thr)
    gate = np.ones(len(close), dtype=float)
    gate[1:] = np.where(state[:-1], float(floor), 1.0)
    return gate, vol, thr


def _weights_from_held(ts, first, last, held, gate=None) -> np.ndarray:
    """Map a per-session boolean/multiplier to per-minute [QQQ, TQQQ, BIL].

    For bar i, the weight is the target of the session containing bar i+1;
    the last bar of a session therefore carries the next session's target and
    is filled at the next open.  This is the harness's next-open convention.
    """
    n_bars = len(ts)
    n_sess = len(first)
    held = np.asarray(held)
    if held.shape != (n_sess,):
        raise ValueError("held shape does not match session count")
    if gate is None:
        gate = np.ones(n_sess, dtype=float)
    tgt = held.astype(float) * np.asarray(gate, dtype=float)
    tgt = np.clip(tgt, 0.0, 1.0)

    w = np.zeros((n_bars, 3), dtype=float)
    sess_of_bar = np.repeat(np.arange(n_sess), np.diff(np.r_[first, n_bars]))
    if n_bars > 1:
        w[:-1, 1] = tgt[sess_of_bar[1:]]
    w[-1, 1] = tgt[sess_of_bar[-1]]
    w[:, 2] = 1.0 - w[:, 1]

    if not np.isfinite(w).all():
        raise ValueError("non-finite weight")
    if w.min() < -1e-12:
        raise ValueError("negative weight")
    if w.sum(axis=1).max() > 1.0 + 1e-9:
        raise ValueError("weights sum > 1")
    return w


def build_weights(ts, o, c, f_start=P_FOMC_START, f_end=P_FOMC_END,
                  o_start=P_OPEX_START, o_end=P_OPEX_END,
                  gate_floor=None, include_fomc=True, include_opex=True,
                  fomc_dates=None, opex_dates=None, exclude=frozenset(),
                  shift: int = 0, return_diag: bool = False):
    """Primary and grid weights.  Pure calendar unless ``gate_floor`` is set."""
    dates, first, last, sess = _calendar(ts)
    n_sess = len(sess)
    fomc_dates = FOMC if fomc_dates is None else fomc_dates
    opex_dates = OPEX if opex_dates is None else opex_dates

    fw = _event_windows(sess, fomc_dates, f_start, f_end, shift, exclude) if include_fomc else []
    ow = _event_windows(sess, opex_dates, o_start, o_end, shift, exclude) if include_opex else []
    held = _held_sessions(n_sess, fw + ow)

    if gate_floor is None:
        gate = np.ones(n_sess, dtype=float)
        vol = thr = None
    else:
        gate, vol, thr = _vol_gate(c, first, last, gate_floor)

    w = _weights_from_held(ts, first, last, held, gate)

    diag = {
        "fomc_windows": len(fw),
        "opex_windows": len(ow),
        "held_sessions": int(held.sum()),
        "session_share": float(held.mean()),
        "weight_share": float(w[:, 1].mean()),
        "gate_shut_share_of_held": (
            float(np.mean(gate[held] < 1.0)) if held.any() and gate_floor is not None else 0.0
        ),
        "vol20_median": float(np.nanmedian(vol)) if vol is not None else None,
        "vol20_thr_median": float(np.nanmedian(thr)) if thr is not None else None,
    }
    if return_diag:
        return w, diag
    return w


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def _daily(ts, values):
    return pd.Series(np.asarray(values, float), index=ts).groupby(ts.date).last()


def _lite(ts, o, c, w, slip: float = 1.0, start: str = START):
    r = bt.run(ts, o, c, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "exposure_tqqq": float(w[i:, 1].mean()),
    }


def _metrics(ts, o, c, w, slip: float = 1.0, start: str = START):
    r = bt.run(ts, o, c, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    eq = np.asarray(r["equity"], float)
    dts = ts[i:]
    deq = _daily(dts, eq)
    dd = deq / deq.cummax() - 1.0
    j_dd = int(np.argmin(dd.to_numpy()))
    p_dd = int(np.argmax(deq.to_numpy()[: j_dd + 1]))
    yr = bt.yearly(dts, eq, c[i:, 1])
    years = float(s["years"])
    out = {
        "cagr": float(s["cagr"]),
        "total_return": float(s["total_return"]),
        "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": float(-dd.min()),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "calmar": float(s["cagr"] / s["max_drawdown"]) if s["max_drawdown"] > 0 else None,
        "exposure_tqqq": float(w[i:, 1].mean()),
        "exposure_bil": float(w[i:, 2].mean()),
        "exposure_harness": float(s["exposure"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "turnover_per_year": float(s["turnover"] / years) if years > 0 else None,
        "ending_equity": float(s["ending_equity"]),
        "years": years,
        "dd_peak": str(deq.index[p_dd]),
        "dd_trough": str(deq.index[j_dd]),
        "yearly": {
            str(k): {"strategy": float(v["strategy"]), "tqqq": float(v["benchmark"])}
            for k, v in yr.items()
        },
    }
    return out, r, dts, deq


def _corr_beta(dts, equity, price):
    a = _daily(dts, equity).pct_change()
    b = _daily(dts, price).pct_change()
    j = pd.concat([a.rename("s"), b.rename("b")], axis=1).dropna()
    corr = float(j["s"].corr(j["b"]))
    beta = float(np.cov(j["s"], j["b"])[0, 1] / np.var(j["b"], ddof=1))
    return corr, beta


def _slice(ts, o, c, w, a: date, b: date, slip: float = 1.0):
    _, first, last, sess = _calendar(ts)
    idx = np.flatnonzero((sess >= a) & (sess <= b))
    if len(idx) == 0:
        return None
    i0, i1 = int(first[idx[0]]), int(last[idx[-1]]) + 1
    r = bt.simulate(ts[i0:i1], o[i0:i1], c[i0:i1], w[i0:i1],
                    band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    return {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "exposure_tqqq": float(w[i0:i1, 1].mean()),
        "ending_equity": float(s["ending_equity"]),
    }


def _year_logs(deq):
    ye = deq.groupby(deq.index.map(lambda d: d.year)).last()
    logs, prev = {}, deq.iloc[0]
    for y, v in ye.items():
        logs[int(y)] = float(np.log(v / prev))
        prev = v
    return logs


def _window_arithmetic(held, sess, first, last, o, c, years):
    """Raw TQQQ open-to-open capture of the held blocks, before BIL/costs."""
    dopen = np.asarray(o[first, 1], float)
    dclose = np.asarray(c[last, 1], float)
    n = len(sess)
    runs = []
    k = 0
    while k < n:
        if held[k]:
            j = k
            while j + 1 < n and held[j + 1]:
                j += 1
            runs.append((k, j))
            k = j + 1
        else:
            k += 1
    logs = []
    for s, e in runs:
        if e + 1 < n:
            ret = dopen[e + 1] / dopen[s] - 1.0
        else:
            ret = dclose[e] / dopen[s] - 1.0
        logs.append(float(np.log1p(ret)))
    window_log = float(np.sum(logs))
    held_n = int(held.sum())
    return {
        "held_sessions": held_n,
        "session_share": float(held.mean()),
        "held_blocks": int(len(runs)),
        "window_log": window_log,
        "window_cagr": float(np.exp(window_log / years) - 1.0),
        "log_per_held_session": float(window_log / held_n) if held_n else None,
    }


def _event_table(sess, first, last, o, c, windows):
    """Open-to-open return of each event window."""
    dopen = np.asarray(o[first, 1], float)
    dclose = np.asarray(c[last, 1], float)
    n = len(sess)
    rows = []
    for d, a, s, e in windows:
        length = e - s + 1
        if s + length < n:
            exit_px = dopen[s + length]
        else:
            exit_px = dclose[-1]
        ret = float(exit_px / dopen[s] - 1.0)
        rows.append({
            "event": str(d),
            "anchor": str(sess[a]) if 0 <= a < n else "pre-panel",
            "start": str(sess[s]),
            "end": str(sess[e]),
            "sessions": int(length),
            "ret": ret,
        })
    return rows


def _event_summary(rows, n_sess, dopen, dclose, label, seed=20261127):
    if not rows:
        return {"label": label, "n": 0}
    v = np.asarray([r["ret"] for r in rows], float)
    lengths = np.asarray([r["sessions"] for r in rows], int)
    rng = np.random.default_rng(seed)
    draws = 4000
    null = np.empty((draws, len(rows)), dtype=float)
    for j, L in enumerate(lengths):
        starts = rng.integers(0, n_sess - L + 1, size=draws)
        end = starts + L
        exit_px = np.where(end < n_sess, dopen[np.minimum(end, n_sess - 1)], dclose[-1])
        null[:, j] = exit_px / dopen[starts] - 1.0
    null_means = null.mean(axis=1)
    t = float(v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))) if v.std(ddof=1) > 0 else None
    return {
        "label": label,
        "n": int(len(v)),
        "mean": float(v.mean()),
        "median": float(np.median(v)),
        "sd": float(v.std(ddof=1)),
        "t": t,
        "positive_share": float((v > 0).mean()),
        "sum_log": float(np.log1p(v).sum()),
        "null_mean_of_means": float(null_means.mean()),
        "null_sd_of_means": float(null_means.std(ddof=1)),
        "null_p95": float(np.percentile(null_means, 95)),
        "percentile_of_primary": float((null_means < v.mean()).mean()),
        "worst": sorted(rows, key=lambda r: r["ret"])[:5],
        "best": sorted(rows, key=lambda r: r["ret"])[-5:],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=500,
                    help="random-calendar placebo draws (default 500)")
    ap.add_argument("--skip-placebo", action="store_true")
    args = ap.parse_args()

    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min",
                        warmup_days=10)
    dates, first, last, sess = _calendar(ts)
    n_sess = len(sess)
    n_bars = len(ts)
    assert ts[-1].date() <= END_DATE, f"panel leaks past dev end: {ts[-1]}"
    assert sess[-1] <= END_DATE
    print(f"panel {ts[0]} .. {ts[-1]}  bars {n_bars:,}  sessions {n_sess}")

    # --- calendar checks -------------------------------------------------
    ss = set(sess)
    fomc_dev = [d for d in FOMC if START_DATE <= d <= END_DATE]
    opex_dev = [d for d in OPEX if START_DATE <= d <= END_DATE]
    fomc_not_session = [str(d) for d in fomc_dev if d not in ss]
    opex_not_session = [str(d) for d in opex_dev if d not in ss]
    fomc_future = [d for d in FOMC if d > END_DATE]
    opex_future = [d for d in OPEX if d > END_DATE]
    print(f"calendar: FOMC {len(FOMC)} ({len(fomc_dev)} dev, {len(fomc_future)} future), "
          f"OpEx {len(OPEX)} ({len(opex_dev)} dev, {len(opex_future)} future)")
    print(f"  FOMC dates not sessions in dev: {fomc_not_session}")
    print(f"  OpEx dates not sessions in dev: {opex_not_session}")

    # Future dates must not change the dev weights.  Full calendar vs a
    # calendar truncated at the dev end, on the same truncated panel.
    w_full = build_weights(ts, o, c)
    w_dev = build_weights(ts, o, c,
                          fomc_dates=[d for d in FOMC if d <= END_DATE],
                          opex_dates=[d for d in OPEX if d <= END_DATE])
    future_effect = float(np.max(np.abs(w_full - w_dev)))
    assert future_effect == 0.0, f"future calendar changed dev weights: {future_effect}"
    print(f"  full-vs-dev calendar max weight diff: {future_effect:.1e}")

    # --- benchmark -------------------------------------------------------
    i0 = bt.start_index(ts, START)
    bench = bt.benchmark(c[i0:, 1], ts[i0:], BARS_PER_YEAR)
    print(f"TQQQ 1m bench: CAGR {bench['cagr']*100:.2f}%  DD {bench['max_drawdown']*100:.2f}%  "
          f"Sharpe {bench['sharpe']:.2f}")

    out = {
        "agent": "family-calendar-event",
        "idea": "Hold TQQQ only inside hardcoded scheduled FOMC post-decision "
                "and monthly OpEx windows, BIL otherwise.",
        "hypothesis": "The FOMC-cycle (post-decision even-week) premium and the "
                      "monthly OpEx flow week are concentrated calendar returns; "
                      "a 3x Nasdaq fund captures them without bearing the "
                      "odd-week drawdown.",
        "family": "calendar/event",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "window": {"start": START, "end": END, "marks": "1m"},
        "bar": TQQQ_BAR,
        "target_dd": TARGET_DD,
        "primary_id": "G3",
        "params": {
            "fomc_start": P_FOMC_START, "fomc_end": P_FOMC_END,
            "opex_start": P_OPEX_START, "opex_end": P_OPEX_END,
            "band": BAND, "costs_bp": list(COSTS), "out_asset": "BIL",
            "vol_gate": None,
        },
        "calendar": {
            "fomc_listed": len(FOMC),
            "opex_listed": len(OPEX),
            "fomc_dev": len(fomc_dev), "opex_dev": len(opex_dev),
            "fomc_future_2024_2026": len(fomc_future),
            "opex_future_2024_2026": len(opex_future),
            "fomc_dates_not_sessions_in_dev": fomc_not_session,
            "opex_dates_not_sessions_in_dev": opex_not_session,
            "future_calendar_max_weight_diff": future_effect,
            "unscheduled_fomc_excluded": ["2020-03-03", "2020-03-15",
                                          "2020-03-18 scheduled/actual mismatch"],
            "opex_good_friday_moves": ["2019-04-18", "2022-04-14", "2025-04-17"],
            "holdout_ready": True,
            "note": "2024-2026 dates are ex-ante schedule dates, included in "
                    "the hardcoded lists, but no 2024+ bar enters the panel, "
                    "weights or simulation of this development run.",
        },
        "benchmark_1min": {k: float(bench[k]) for k in
                           ("cagr", "max_drawdown", "sharpe", "volatility",
                            "years", "ending_equity")},
        "panel_check": {
            "first": str(ts[0]), "last": str(ts[-1]),
            "last_session": str(sess[-1]), "bars": int(n_bars),
            "sessions": int(n_sess), "no_2024_bars": bool(ts[-1].date() <= END_DATE),
        },
    }

    # Replay the development backtest with and without the 2024-2026 calendar
    # entries.  The weights are identical; this records the metric equality
    # explicitly for the audit trail.
    m_fullcal = _lite(ts, o, c, w_full, 1.0)
    m_devcal = _lite(ts, o, c, w_dev, 1.0)
    out["calendar"]["dev_only_calendar_replay"] = {
        "full_calendar": m_fullcal,
        "dev_only_calendar": m_devcal,
        "cagr_delta": float(m_fullcal["cagr"] - m_devcal["cagr"]),
        "max_drawdown_delta": float(m_fullcal["max_drawdown"] - m_devcal["max_drawdown"]),
        "sharpe_delta": float(m_fullcal["sharpe"] - m_devcal["sharpe"]),
        "identical": bool(
            abs(m_fullcal["cagr"] - m_devcal["cagr"]) < 1e-12
            and abs(m_fullcal["max_drawdown"] - m_devcal["max_drawdown"]) < 1e-12
            and abs(m_fullcal["sharpe"] - m_devcal["sharpe"]) < 1e-12
        ),
        "note": "the 2024-2026 calendar entries are inert in the dev window; "
                "adding them does not change the 2016-2023 result.",
    }

    # Standard causality audit: rebuild weights on a panel truncated at
    # 2020-03-12 11:07 and compare every bar strictly before the cut.
    cut_ts = pd.Timestamp("2020-03-12 11:07", tz="America/New_York")
    cut = int(ts.searchsorted(cut_ts))
    precut = {}
    for lab, floor in (("G3", None), ("G7", 0.5), ("G8", 0.0)):
        wf = build_weights(ts, o, c, gate_floor=floor)
        wc = build_weights(ts[:cut], o[:cut], c[:cut], gate_floor=floor)
        precut[lab] = (float(np.max(np.abs(wf[:cut - 1] - wc[:cut - 1])))
                       if cut > 1 else 0.0)
    out["precut_test"] = {
        "cut_ts": str(cut_ts), "cut_bar": cut,
        "max_abs_weight_diff": precut,
        "note": "weights strictly before 2020-03-12 11:07 rebuilt on a panel "
                "truncated at the cut; the calendar-only primary should be exact.",
    }

    # --- primary ---------------------------------------------------------
    w_primary, diag = build_weights(ts, o, c, return_diag=True)
    per_cost = {}
    for slip in COSTS:
        m, r, dts, deq = _metrics(ts, o, c, w_primary, slip)
        per_cost[f"{slip:.0f}bp"] = m
        if slip == 1.0:
            p_eq, p_dts, p_deq = np.asarray(r["equity"]), dts, deq
    corr_t, beta_t = _corr_beta(p_dts, p_eq, c[i0:, 1])
    corr_q, beta_q = _corr_beta(p_dts, p_eq, c[i0:, 0])
    p = per_cost["1bp"]

    out["primary"] = {
        "id": "G3",
        "params": {"fomc_start": P_FOMC_START, "fomc_end": P_FOMC_END,
                   "opex_start": P_OPEX_START, "opex_end": P_OPEX_END,
                   "vol_gate": None},
        "diagnostics": diag,
        "dev": per_cost,
        "corr_tqqq_daily": corr_t, "beta_tqqq_daily": beta_t,
        "corr_qqq_daily": corr_q, "beta_qqq_daily": beta_q,
    }
    out["dev_1bp"] = p
    out["exposure"] = p["exposure_tqqq"]
    out["exposure_bil"] = p["exposure_bil"]
    out["corr_vs_tqqq"] = corr_t
    out["beta_vs_tqqq"] = beta_t
    out["yearly"] = p["yearly"]
    print(f"primary G3 1bp: CAGR {p['cagr']*100:.2f}%  DD {p['max_drawdown']*100:.2f}%  "
          f"Sharpe {p['sharpe']:.2f}  wTQQQ {p['exposure_tqqq']*100:.1f}%  "
          f"corr {corr_t:.2f}  fills {p['fills']}  turnover {p['turnover']:.0f}x")

    # --- pre-registered grid --------------------------------------------
    grid_defs = [
        ("G1", 2, 10, -1, 3, None, "short FOMC; centred OpEx"),
        ("G2", 2, 10, 1, 4, None, "short FOMC; post-expiry OpEx"),
        ("G3", 2, 15, -1, 3, None, "primary: median FOMC; centred OpEx"),
        ("G4", 2, 15, 1, 4, None, "median FOMC; post-expiry OpEx"),
        ("G5", 2, 20, -1, 3, None, "long FOMC; centred OpEx"),
        ("G6", 2, 20, 1, 4, None, "long FOMC; post-expiry OpEx"),
        ("G7", 2, 15, -1, 3, 0.5, "G3 + soft vol gate (x0.5 above q75)"),
        ("G8", 2, 15, -1, 3, 0.0, "G3 + hard vol gate (0 above q75)"),
    ]
    grid = {}
    for cid, fs, fe, os_, oe, floor, note in grid_defs:
        w, dg = build_weights(ts, o, c, f_start=fs, f_end=fe,
                              o_start=os_, o_end=oe, gate_floor=floor,
                              return_diag=True)
        m, _, _, _ = _metrics(ts, o, c, w, 1.0)
        fw_cell = _event_windows(sess, FOMC, fs, fe)
        ow_cell = _event_windows(sess, OPEX, os_, oe)
        held_cell = _held_sessions(n_sess, fw_cell + ow_cell)
        arith = _window_arithmetic(held_cell, sess, first, last, o, c,
                                   float(p["years"]))
        rec = {"note": note,
               "fomc": [fs, fe], "opex": [os_, oe],
               "vol_gate_floor": floor,
               "diagnostics": dg, "dev_1bp": m,
               "window_arithmetic": arith}
        for slip in (5.0, 10.0):
            rec[f"dev_{slip:.0f}bp"] = _lite(ts, o, c, w, slip)
        grid[cid] = rec
        print(f"  {cid}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sh {m['sharpe']:4.2f}  wTQQQ {m['exposure_tqqq']*100:5.1f}%  "
              f"sess {dg['session_share']*100:5.1f}%  gate {dg['gate_shut_share_of_held']*100:4.1f}%")
    out["grid"] = grid

    # --- decomposition: FOMC only / OpEx only ---------------------------
    dec = {}
    for lab, inc_f, inc_o in (("fomc_only", True, False),
                              ("opex_only", False, True),
                              ("union", True, True)):
        w, dg = build_weights(ts, o, c, include_fomc=inc_f,
                              include_opex=inc_o, return_diag=True)
        m = _lite(ts, o, c, w, 1.0)
        dec[lab] = {"diagnostics": dg, "dev_1bp": m}
        print(f"  {lab}: CAGR {m['cagr']*100:6.2f}%  DD {m['max_drawdown']*100:5.2f}%  "
              f"Sh {m['sharpe']:4.2f}  wTQQQ {m['exposure_tqqq']*100:5.1f}%")
    out["decomposition"] = dec

    # --- event study ------------------------------------------------------
    f_windows = _event_windows(sess, FOMC, P_FOMC_START, P_FOMC_END)
    o_windows = _event_windows(sess, OPEX, P_OPEX_START, P_OPEX_END)
    f_rows = _event_table(sess, first, last, o, c, f_windows)
    o_rows = _event_table(sess, first, last, o, c, o_windows)
    dopen = np.asarray(o[first, 1], float)
    dclose = np.asarray(c[last, 1], float)
    out["event_study"] = {
        "fomc": _event_summary(f_rows, n_sess, dopen, dclose, "FOMC +2..+15"),
        "opex": _event_summary(o_rows, n_sess, dopen, dclose, "OpEx -1..+3"),
        "note": "per-event open-to-open return, same number and lengths as the "
                "primary; random null 4,000 draws",
    }
    print(f"  event FOMC: mean {out['event_study']['fomc']['mean']*100:.2f}%  "
          f"t {out['event_study']['fomc']['t']:.2f}  "
          f"null pct {out['event_study']['fomc']['percentile_of_primary']*100:.1f}%")
    print(f"  event OpEx: mean {out['event_study']['opex']['mean']*100:.2f}%  "
          f"t {out['event_study']['opex']['t']:.2f}  "
          f"null pct {out['event_study']['opex']['percentile_of_primary']*100:.1f}%")

    # --- exposure arithmetic --------------------------------------------
    # Raw TQQQ open-to-open capture of the held blocks, before BIL and costs.
    held_primary = _held_sessions(n_sess, f_windows + o_windows)
    arith = _window_arithmetic(held_primary, sess, first, last, o, c,
                               float(p["years"]))
    window_log = arith["window_log"]
    years = float(p["years"])
    bar_log = float(np.log1p(TQQQ_BAR["cagr"]) * years)
    out["exposure_arithmetic"] = {
        **arith,
        "bar_log_required": bar_log,
        "multiple_of_window_return_needed": float(bar_log / window_log) if window_log > 0 else None,
        "shortfall_log": float(bar_log - window_log),
        "note": "raw TQQQ open-to-open return of the held blocks, before BIL "
                "yield and costs.  If this CAGR is below 36.72%, no cash/cost "
                "treatment of the same calendar can clear the bar.",
    }
    print(f"  arithmetic: held {held_primary.sum()} sessions, "
          f"raw window CAGR {out['exposure_arithmetic']['window_cagr']*100:.2f}%, "
          f"required multiple {out['exposure_arithmetic']['multiple_of_window_return_needed']:.2f}x")

    # --- shift test -------------------------------------------------------
    shift_rows = {}
    for s in range(-10, 11):
        w, dg = build_weights(ts, o, c, shift=s, return_diag=True)
        m = _lite(ts, o, c, w, 1.0)
        shift_rows[str(s)] = {"cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                              "sharpe": m["sharpe"], "exposure_tqqq": m["exposure_tqqq"],
                              "held_sessions": dg["held_sessions"]}
    out["shift_test"] = {
        "note": "every FOMC and OpEx anchor shifted by N sessions; same window "
                "lengths, no gate.  A genuine calendar effect should peak at 0.",
        "by_shift": shift_rows,
        "peak_shift": max(shift_rows, key=lambda s: shift_rows[s]["cagr"]),
        "cagr_at_0": shift_rows["0"]["cagr"],
    }
    print(f"  shift: peak at {out['shift_test']['peak_shift']}  "
          f"CAGR@0 {shift_rows['0']['cagr']*100:.1f}%  "
          f"peak {shift_rows[out['shift_test']['peak_shift']]['cagr']*100:.1f}%")

    # --- subperiods / leave-one-year-out / drop-best --------------------
    cuts = {}
    for lab, a, b in (("2016-2019", date(2016, 1, 4), date(2019, 12, 31)),
                      ("2020-2021", date(2020, 1, 2), date(2021, 12, 31)),
                      ("2022-2023", date(2022, 1, 3), date(2023, 12, 29))):
        cuts[lab] = _slice(ts, o, c, w_primary, a, b)
    out["cuts"] = {"subperiods": cuts}

    ylogs = _year_logs(p_deq)
    tot = float(np.log(p_deq.iloc[-1] / p_deq.iloc[0]))
    loo = {}
    for y, lg in ylogs.items():
        loo[str(y)] = {"year_return": float(np.exp(lg) - 1.0),
                       "ex_cagr": float(np.exp((tot - lg) / 7.0) - 1.0)}
    out["cuts"]["leave_one_year_out"] = loo

    all_rows = [(r["event"], r["ret"], "fomc") for r in f_rows] + \
               [(r["event"], r["ret"], "opex") for r in o_rows]
    order = sorted(range(len(all_rows)), key=lambda i: all_rows[i][1], reverse=True)
    drop = {}
    for n in (1, 3, 5):
        bad = {date.fromisoformat(all_rows[i][0]) for i in order[:n]}
        w, dg = build_weights(ts, o, c, exclude=bad, return_diag=True)
        m = _lite(ts, o, c, w, 1.0)
        drop[f"drop_best_{n}"] = {**m, "windows": dg["fomc_windows"] + dg["opex_windows"],
                                  "excluded": sorted(str(x) for x in bad)}
    out["cuts"]["drop_best_windows"] = drop
    print(f"  cuts: drop best 1 CAGR {drop['drop_best_1']['cagr']*100:.1f}%  "
          f"drop best 5 {drop['drop_best_5']['cagr']*100:.1f}%")

    # --- random-calendar placebo ----------------------------------------
    if not args.skip_placebo:
        f_lens = [e - s + 1 for _, _, s, e in f_windows]
        o_lens = [e - s + 1 for _, _, s, e in o_windows]
        lens = f_lens + o_lens
        target_h = int(held_primary.sum())
        rng = np.random.default_rng(20261127)
        rand_rows = []
        match_rows = []
        for _ in range(args.draws):
            held_rand = np.zeros(n_sess, dtype=bool)
            for L in lens:
                st = int(rng.integers(0, n_sess - L + 1))
                held_rand[st:st + L] = True
            w_rand = _weights_from_held(ts, first, last, held_rand)
            m_rand = _lite(ts, o, c, w_rand, 1.0)
            rand_rows.append((m_rand["cagr"], m_rand["max_drawdown"],
                              m_rand["sharpe"], m_rand["exposure_tqqq"]))

            # Exposure-matched null: same held-session count as the primary,
            # with the surplus/deficit assigned to random sessions.  This asks
            # whether the *timing* of the calendar matters, not just beta.
            held_match = held_rand.copy()
            h = int(held_match.sum())
            if h < target_h:
                cand = np.flatnonzero(~held_match)
                add = rng.choice(cand, size=target_h - h, replace=False)
                held_match[add] = True
            elif h > target_h:
                cand = np.flatnonzero(held_match)
                rem = rng.choice(cand, size=h - target_h, replace=False)
                held_match[rem] = False
            w_match = _weights_from_held(ts, first, last, held_match)
            m_match = _lite(ts, o, c, w_match, 1.0)
            match_rows.append((m_match["cagr"], m_match["max_drawdown"],
                               m_match["sharpe"], m_match["exposure_tqqq"]))
        rand = np.asarray(rand_rows)
        match = np.asarray(match_rows)

        def _pct(a, col, value, greater=False):
            v = a[:, col]
            return float((v > value).mean() if greater else (v < value).mean())

        def _pack(a):
            return {
                "cagr": {"median": float(np.median(a[:, 0])),
                         "p90": float(np.percentile(a[:, 0], 90)),
                         "p95": float(np.percentile(a[:, 0], 95)),
                         "p99": float(np.percentile(a[:, 0], 99)),
                         "max": float(a[:, 0].max()),
                         "percentile_of_primary": _pct(a, 0, p["cagr"])},
                "max_drawdown": {"median": float(np.median(a[:, 1])),
                                 "p10": float(np.percentile(a[:, 1], 10)),
                                 "p05": float(np.percentile(a[:, 1], 5)),
                                 "min": float(a[:, 1].min()),
                                 "percentile_of_primary": _pct(a, 1, p["max_drawdown"], greater=True)},
                "sharpe": {"median": float(np.median(a[:, 2])),
                           "p95": float(np.percentile(a[:, 2], 95)),
                           "max": float(a[:, 2].max()),
                           "percentile_of_primary": _pct(a, 2, p["sharpe"])},
                "exposure": {"median": float(np.median(a[:, 3])),
                             "p05": float(np.percentile(a[:, 3], 5)),
                             "p95": float(np.percentile(a[:, 3], 95))},
                "percentile_of_grid_cagr": {
                    cid: _pct(a, 0, grid[cid]["dev_1bp"]["cagr"]) for cid in grid
                },
            }

        placebo = {
            "draws": int(args.draws), "seed": 20261127,
            "n_windows": int(len(lens)),
            "window_lengths": sorted(set(int(x) for x in lens)),
            "overlaps_allowed": True,
            "note": "Random session starts with the same number and lengths of "
                    "FOMC and OpEx windows.  'unmatched' preserves window "
                    "structure but random placement overlaps more, so its "
                    "exposure is lower.  'matched' adds/removes random sessions "
                    "to hold exactly the primary's number of sessions and is the "
                    "headline placebo: it asks whether the calendar timing adds "
                    "anything beyond the same TQQQ exposure.",
            "unmatched": _pack(rand),
            "matched": _pack(match),
            "matched_note": "exactly exposure-matched to the primary's held "
                            "session count",
            "joint_frac_matched_cagr_ge_primary_and_dd_le": float(np.mean(
                (match[:, 0] >= p["cagr"]) & (match[:, 1] <= p["max_drawdown"]))),
        }
        out["placebo"] = placebo
        print(f"  placebo unmatched: CAGR p50 {placebo['unmatched']['cagr']['median']*100:5.1f}%  "
              f"p95 {placebo['unmatched']['cagr']['p95']*100:5.1f}%  "
              f"primary pct {placebo['unmatched']['cagr']['percentile_of_primary']*100:4.1f}%")
        print(f"  placebo matched:   CAGR p50 {placebo['matched']['cagr']['median']*100:5.1f}%  "
              f"p95 {placebo['matched']['cagr']['p95']*100:5.1f}%  "
              f"primary pct {placebo['matched']['cagr']['percentile_of_primary']*100:4.1f}%  "
              f"joint {placebo['joint_frac_matched_cagr_ge_primary_and_dd_le']*100:4.1f}%")
    else:
        out["placebo"] = {"skipped": True}

    # --- status ----------------------------------------------------------
    passed = (p["cagr"] > TQQQ_BAR["cagr"]
              and p["max_drawdown"] < TQQQ_BAR["max_drawdown"])
    best_cell = max(grid, key=lambda cid: grid[cid]["dev_1bp"]["cagr"])
    out["best_grid_cell"] = {
        "id": best_cell,
        "cagr": grid[best_cell]["dev_1bp"]["cagr"],
        "max_drawdown": grid[best_cell]["dev_1bp"]["max_drawdown"],
        "sharpe": grid[best_cell]["dev_1bp"]["sharpe"],
        "exposure_tqqq": grid[best_cell]["dev_1bp"]["exposure_tqqq"],
    }
    out["passed_dev_bar"] = bool(passed)
    out["status"] = "passed_dev_only" if passed else "below_dev_bar"
    gap = p["cagr"] - TQQQ_BAR["cagr"]
    out["verdict"] = (
        f"{'PASS' if passed else 'FAIL'} at the development bar: G3 "
        f"{p['cagr']*100:.2f}% CAGR vs {TQQQ_BAR['cagr']*100:.2f}% "
        f"({gap*100:+.2f} pp), max DD {p['max_drawdown']*100:.2f}% vs "
        f"{TQQQ_BAR['max_drawdown']*100:.2f}%, Sharpe {p['sharpe']:.2f}. "
        f"TQQQ exposure {p['exposure_tqqq']*100:.1f}%. "
        f"Best grid cell {best_cell} at {grid[best_cell]['dev_1bp']['cagr']*100:.2f}%."
    )
    out["notes"] = [
        "The 2024-2026 calendar dates are hardcoded and ex-ante; the development "
        "panel is truncated at 2023-12-29 and the full-vs-dev weight difference "
        "is exactly 0.0.",
        "The benchmark is recomputed on the same 1-minute panel; the published "
        "36.72% / 82.29% / 0.82 bar is used for pass/fail.",
        "TQQQ exposure is the mean TQQQ weight over 1-minute bars, not "
        "bt.stats' exposure (which includes the BIL leg).",
        "The primary is pure calendar G3; G7/G8 are pre-registered risk "
        "variants and are not selection candidates.",
    ]

    (HERE / "result.json").write_text(
        json.dumps(_clean(out), indent=2, allow_nan=False), encoding="utf-8")
    print(f"\nwrote {HERE / 'result.json'}")
    print(f"status: {out['status']}  {out['verdict']}")


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    return obj


if __name__ == "__main__":
    main()
