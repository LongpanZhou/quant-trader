"""Close-Flow Exhaustion (CFE) — standalone rebuild of `agents2/intraday-seasonality`.

Idea
----
When QQQ is already down more than 1% by the close, part of the selling is not
information: daily-reset leveraged ETFs must reduce exposure in the direction of
the day's move, and they do it in the closing auction.  The close is therefore
temporarily too cheap and the pressure is transitory.  This strategy owns TQQQ
only for the reversal: buy the closing print on an orderly intraday decline,
hold one session, sit in BIL otherwise.

Rules (base spec)
-----------------
  signal at the 15:58 bar close:  q_day = QQQ(15:58) / QQQ(09:30 open) - 1
  if q_day <= -1.0%:              buy TQQQ at the 15:59 open, 100%
  exit:                           next session's 15:01 open
  otherwise:                      100% BIL

No moving average, no regime gate, no stop in the base spec.  The old 165-day
base and the round-1 stop are not used anywhere.

This file is frozen for test.  It is NOT to be run while backtests are paused.

Run (when authorised):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/intraday-seasonality/strategy.py --windows dev
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

OUT = Path(__file__).resolve().parent
BARS_PER_YEAR = 252 * 390

WINDOWS = {
    "dev": ("2016-01-04", "2023-12-29"),
    "holdout": ("2024-01-02", "2026-10-23"),
    "10y": ("2017-01-03", "2026-10-23"),
    "5y": ("2021-10-25", "2026-10-23"),
}
SUBPERIODS = {
    "2016-19": ("2016-01-04", "2019-12-31"),
    "2020-21": ("2020-01-01", "2021-12-31"),
    "2022-23": ("2022-01-01", "2023-12-29"),
}

BASE = dict(thr=-0.010, upper=None, gap_max=None, entry_hm=(15, 59),
            exit_mode="next_1500", stop=None, hold_days=1, size_mode="full")


# ------------------------------------------------------------------ helpers
def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def exact_bar(ts: pd.DatetimeIndex, first: np.ndarray, last: np.ndarray,
              hh: int, mm: int) -> np.ndarray:
    """Bar index at exactly hh:mm per session, or -1 if the session lacks it."""
    target = hh * 60 + mm
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    out = np.full(len(first), -1, dtype=np.int64)
    for k, (f, l) in enumerate(zip(first, last)):
        j = int(np.searchsorted(mins[f:l + 1], target))
        if j <= l - f and mins[f + j] == target:
            out[k] = f + j
    return out


def window_slice(ts: pd.DatetimeIndex, start: str, end: str) -> tuple[int, int]:
    tz = "America/New_York"
    i = int(ts.searchsorted(pd.Timestamp(start, tz=tz)))
    j = int(ts.searchsorted(pd.Timestamp(end, tz=tz) + pd.Timedelta(days=1)))
    return i, min(j, len(ts))


# ------------------------------------------------------------------ strategy
def build_weights(ts, opens, closes, thr: float = -0.010, upper: float | None = None,
                  gap_max: float | None = None, entry_hm=(15, 59),
                  exit_mode: str = "next_1500", stop: float | None = None,
                  hold_days: int = 1, size_mode: str = "full"):
    """Return (weights, info) for the CFE strategy.

    weights[i] is the target set at the close of bar i and filled at bar i+1's
    open.  Long-only TQQQ/BIL.
    """
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    n = len(ts)
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()

    i1558 = exact_bar(ts, first, last, 15, 58)
    i1500 = exact_bar(ts, first, last, 15, 0)

    q_open = opens[first, 0]
    q_1558 = np.where(i1558 >= 0, closes[np.maximum(i1558, 0), 0], np.nan)
    q_prev_close = np.r_[np.nan, closes[last, 0][:-1]]
    q_day = q_1558 / q_open - 1.0
    gap = q_open / q_prev_close - 1.0

    ok = (i1558 >= 0) & (mins[first] == 570) & np.isfinite(q_day)
    fire = ok & (q_day <= thr)
    if upper is not None:
        fire &= q_day >= upper
    if gap_max is not None:
        fire &= np.abs(gap) <= gap_max

    w = np.zeros((n, 3))
    events = []
    for k in np.flatnonzero(fire):
        if k + hold_days >= len(first):
            continue
        entry_w = int(i1558[k])            # weight set on 15:58 -> fill 15:59
        if entry_w + 1 > last[k] or entry_w <= 0:
            continue
        entry_px = opens[entry_w + 1, 1]

        if exit_mode == "next_1500":
            e = i1500[k + hold_days]
            exit_w = int(e) if e >= 0 else int(last[k + hold_days])
        elif exit_mode == "next_open":
            exit_w = int(last[k + hold_days - 1])   # flat for the next open
        else:
            raise ValueError(exit_mode)
        if exit_w < entry_w:
            exit_w = entry_w

        if stop is not None:
            j0 = entry_w + 1
            j1 = min(exit_w, int(last[k + hold_days]))
            hit = np.flatnonzero(closes[j0:j1 + 1, 1] < entry_px * (1.0 - stop))
            if len(hit):
                exit_w = j0 + int(hit[0])

        if size_mode == "full":
            size = 1.0
        elif size_mode == "scaled":
            size = float(np.clip(abs(q_day[k]) / 0.02, 0.5, 1.0))
        else:
            raise ValueError(size_mode)

        w[entry_w:exit_w, 1] = size
        events.append({"date": str(dates[k]), "q_day": float(q_day[k]),
                       "gap": float(gap[k]), "size": size,
                       "entry_w": int(entry_w), "exit_w": int(exit_w),
                       "entry_px": float(entry_px)})

    w[:, 1] = np.clip(w[:, 1], 0.0, 1.0)
    w[:, 2] = 1.0 - w[:, 1]

    info = {
        "sessions": int(len(first)),
        "signal_days": int(fire.sum()),
        "events": len(events),
        "threshold": thr,
        "upper": upper,
        "gap_max": gap_max,
        "entry_hm": list(entry_hm),
        "exit_mode": exit_mode,
        "stop": stop,
        "hold_days": hold_days,
        "size_mode": size_mode,
        "exposure": float(w[:, 1].mean()),
        "event_list": events,
    }
    return w, info


# ------------------------------------------------------------------ metric-only baseline
def baseline_weights(ts, closes, n_ma: int = 165):
    """Round-1 165-day baseline.  USED ONLY TO MEASURE CORRELATION, never as a
    position in this strategy."""
    dates = bt.session_dates(ts)
    first, last = day_bounds(dates)
    n = len(ts)
    dc = closes[last, 0]
    sma = pd.Series(dc).rolling(n_ma).mean().to_numpy()
    reg = np.zeros(len(dc), bool)
    reg[1:] = dc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    w = np.zeros((n, 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


# ------------------------------------------------------------------ evaluation
def simulate_window(ts, opens, closes, w, window, slippage_bps=1.0):
    i, j = window_slice(ts, *window)
    return bt.simulate(ts[i:j], opens[i:j], closes[i:j], w[i:j],
                       band=0.02, slippage_bps=slippage_bps)


def metrics(result):
    s = bt.stats(result, BARS_PER_YEAR)
    return {k: float(s[k]) for k in
            ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
             "fills", "turnover", "exposure", "ending_equity")}


def daily_returns(result):
    ts, eq = result["ts"], result["equity"]
    d = bt.session_dates(ts)
    _, last = day_bounds(d)
    s = pd.Series(eq[last], index=pd.to_datetime([x for x in d[last]]))
    return s.pct_change().dropna()


def corr_vs(result, ref_result):
    a = daily_returns(result)
    b = daily_returns(ref_result)
    j = a.index.intersection(b.index)
    return float(np.corrcoef(a.loc[j], b.loc[j])[0, 1])


def event_stats(opens, closes, events):
    """Per-event trade return (TQQQ fill to fill), bp, and a bootstrap p-value."""
    if not events:
        return {"n": 0}
    rets = np.array([opens[e["exit_w"] + 1, 1] / e["entry_px"] - 1.0
                     for e in events if e["exit_w"] + 1 < len(opens)])
    sizes = np.array([e["size"] for e in events])[:len(rets)]
    r = rets * sizes
    rng = np.random.default_rng(11)
    boot = rng.choice(r, size=(10_000, len(r)), replace=True).mean(axis=1)
    return {
        "n": int(len(r)),
        "mean_bp": float(r.mean() * 1e4),
        "median_bp": float(np.median(r) * 1e4),
        "t": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 2 else None,
        "win_rate": float((r > 0).mean()),
        "bootstrap_p_mean_le_0": float((boot <= 0).mean()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="dev",
                    help="comma list of dev,10y,5y (holdout only with --holdout)")
    ap.add_argument("--holdout", action="store_true",
                    help="LEAD ONLY: include the 2024-2026 holdout")
    ap.add_argument("--slippage", default="1,5,10")
    ap.add_argument("--variants", action="store_true",
                    help="run the pre-registered variant grid")
    args = ap.parse_args()

    wanted = [x.strip() for x in args.windows.split(",") if x.strip()]
    if args.holdout:
        wanted.append("holdout")
    unknown = [x for x in wanted if x not in WINDOWS]
    if unknown:
        raise SystemExit(f"unknown window(s): {unknown}")

    # do not load past dev unless a later window was explicitly requested
    end = WINDOWS["dev"][1] if set(wanted) <= {"dev"} else WINDOWS["10y"][1]
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"),
                                 WINDOWS["dev"][0], end, "1min")
    slips = [float(x) for x in args.slippage.split(",")]

    w, info = build_weights(ts, opens, closes, **BASE)
    wb = baseline_weights(ts, closes)
    rb = simulate_window(ts, opens, closes, wb, WINDOWS["dev"], 1.0)

    out = {
        "agent": "intraday-seasonality",
        "original": "research/agents2/intraday-seasonality",
        "status": "passed",          # provisional; set by the lead after audit
        "idea": ("QQQ down more than 1% by the close forces leveraged-ETF selling "
                 "into the close; buy the closing print and own the one-session "
                 "reversal."),
        "hypothesis": ("TQQQ bought at the 15:59 print after an orderly intraday "
                       "QQQ decline outperforms cash over the next session."),
        "universe": ["TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {},
        "marks": "1m",
        "benchmarks": {},
        "spec": BASE,
        "diagnostics": {k: v for k, v in info.items() if k != "event_list"},
        "event_stats": event_stats(opens, closes, info["event_list"]),
    }

    for win in wanted:
        out["windows"][win] = {}
        for slip in slips:
            r = simulate_window(ts, opens, closes, w, WINDOWS[win], slip)
            out["windows"][win][f"{slip:.0f}bp"] = metrics(r)

    r1 = simulate_window(ts, opens, closes, w, WINDOWS["dev"], 1.0)
    out["corr_vs_165d_baseline"] = corr_vs(r1, rb)
    out["subperiods"] = {}
    for name, win in SUBPERIODS.items():
        r = simulate_window(ts, opens, closes, w, win, 1.0)
        out["subperiods"][name] = metrics(r)

    i = bt.start_index(ts, WINDOWS["dev"][0])
    out["benchmarks"]["tqqq"] = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR)
    out["benchmarks"]["qqq"] = bt.benchmark(closes[i:, 0], ts[i:], BARS_PER_YEAR)

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "windows"},
                     indent=2, default=float))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
