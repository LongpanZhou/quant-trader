"""Leveraged-ETF overshoot recovery (revisit of stop-reentry-recovery).

Standalone strategy.  It does NOT use the old 165-day QQQ/TQQQ/SPY/NDX trend
gate, and does not call or copy the old base weights.

Idea
----
A 3x ETF must reset its swap exposure every day.  After a large down day it has
to sell into the close, which can push TQQQ below 3x QQQ's move.  That temporary
overshoot tends to reverse over the next 1-3 sessions.  Buy the overshoot, not
every dip:

  signal[d] = TQQQ intraday return <= -3%
              AND (TQQQ intraday return - 3 * QQQ intraday return) <= -1pp

  entry[d+1]  : 50% TQQQ at 09:31
  add-on[d+2] : +50% at 09:31 if session d+1 closed above its open
  exit        : close of session d+3 (sell at the 15:59 open)
  stop        : 2% from the initial entry price; exit at the next bar's open and
                stay BIL for the rest of the event

If the signal does not fire, the book is 100% BIL.  Long-only, one position at
a time, max 100% TQQQ.

Development window is 2016-01-04 .. 2023-12-29.  The holdout 2024-2026 is not
loaded or inspected here; the lead runs it once after the strategy is frozen.

Backtests are paused by the user.  Running this file is the authorized test and
will write result.json.

Run (after authorization):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/stop-reentry-recovery/strategy.py
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

HERE = Path(__file__).resolve().parent
START, END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

# primary parameters (neighbourhood is evaluated by the test harness)
DROP = 0.030          # TQQQ intraday fall floor
EXCESS = 0.010        # TQQQ underperformance vs 3x QQQ, in return points
HOLD = 3              # sessions, including the entry session
STOP = 0.020          # from the initial entry price
SIZE0 = 0.50          # first tranche
SIZE1 = 1.00          # after a recovery close
ADDON = True
GAP_CANCEL = 0.0      # >0: skip entry if the first minute is down this much
SIGNAL_MODE = "intraday"   # intraday | close


def day_bounds(ts: pd.DatetimeIndex):
    return bt.day_bounds(ts)


def day_weights(target: np.ndarray, first: np.ndarray, last: np.ndarray) -> np.ndarray:
    """Repeat a daily target across each session's bars (fills at the next bar)."""
    n = int(last[-1]) + 1
    w = np.empty((n, target.shape[1]))
    for k, (f, z) in enumerate(zip(first, last)):
        w[f:z + 1] = target[k]
    return w


def build_signal(dopen, dclose, drop=DROP, excess=EXCESS, mode=SIGNAL_MODE):
    r_t = dclose[:, 1] / dopen[:, 1] - 1.0
    r_q = dclose[:, 0] / dopen[:, 0] - 1.0
    if mode == "close":
        r_t = np.r_[np.nan, dclose[1:, 1] / dclose[:-1, 1] - 1.0]
        r_q = np.r_[np.nan, dclose[1:, 0] / dclose[:-1, 0] - 1.0]
    excess_ret = r_t - 3.0 * r_q
    sig = np.isfinite(excess_ret) & (r_t <= -drop) & (excess_ret <= -excess)
    return sig, r_t, r_q, excess_ret


def build_weights(ts, opens, closes, drop=DROP, excess=EXCESS, hold=HOLD,
                  stop=STOP, size0=SIZE0, size1=SIZE1, addon=ADDON,
                  gap_cancel=GAP_CANCEL, signal_mode=SIGNAL_MODE):
    """Return (weights, info).  weights[i] is the target set at bar i's close
    and filled at bar i+1's open (research/bt.py convention)."""
    dates, first, last = day_bounds(ts)
    session_dates = dates[first]
    nd = len(first)
    n = len(ts)
    dopen = opens[first]
    dclose = closes[last]
    sig, r_t, r_q, excess_ret = build_signal(dopen, dclose, drop, excess, signal_mode)

    w = np.zeros((n, 3))
    pending = False
    pos = 0.0
    entry_day = -1
    hold_until = -1
    entry_px = np.nan
    addon_done = True
    stopped = False
    entries, stops, addons = [], [], []

    for k in range(nd):
        f, z = int(first[k]), int(last[k])
        m = z - f + 1

        # entry decided at the prior close, filled at 09:31
        if pending and pos == 0.0:
            if gap_cancel > 0 and m > 1 and closes[f, 1] < opens[f, 1] * (1 - gap_cancel):
                pending = False
            else:
                pos = float(size0)
                entry_day = k
                hold_until = k + int(hold) - 1
                entry_px = float(opens[min(f + 1, z), 1])
                addon_done = not bool(addon)
                stopped = False
                pending = False
                entries.append((str(session_dates[k]), entry_px))

        # add-on at 09:31 of the second session if the entry session closed up
        if pos > 0 and k == entry_day + 1 and not addon_done:
            addon_done = True
            if dclose[k - 1, 1] > dopen[k - 1, 1]:
                pos = float(size1)
                addons.append(str(session_dates[k]))

        # hold / stop for the day
        block = np.full(m, pos)
        start = 1 if k == entry_day else 0   # position is bought at f+1
        for j in range(start, m):
            if pos > 0 and closes[f + j, 1] < entry_px * (1.0 - stop):
                block[j:] = 0.0
                pos = 0.0
                stopped = True
                stops.append((str(session_dates[k]), str(ts[f + j].time())))
                break

        # scheduled exit at the close of the last hold session
        exit_close = (not stopped and pos > 0 and k == hold_until)
        if exit_close:
            if m >= 2:
                block[-2:] = 0.0
            else:
                block[:] = 0.0
            pos = 0.0

        w[f:z + 1, 1] = block
        w[f:z + 1, 2] = 1.0 - block

        # queue the next event only when flat and the current event is finished
        if sig[k] and pos == 0.0 and k >= hold_until:
            pending = True

    info = {
        "signal_mode": signal_mode,
        "params": dict(drop=drop, excess=excess, hold=hold, stop=stop,
                       size0=size0, size1=size1, addon=bool(addon),
                       gap_cancel=gap_cancel),
        "events": int(sig.sum()),
        "entries": len(entries),
        "stops": len(stops),
        "addons": len(addons),
        "event_dates": [str(d) for d in session_dates[sig]],
        "entry_dates": [d for d, _ in entries],
        "stop_dates": [d for d, _ in stops],
        "addon_dates": addons,
    }
    return w, info


def daily_returns(eq: np.ndarray, first: np.ndarray) -> np.ndarray:
    last_eq = np.r_[eq[0], eq[first[1:] - 1]]
    return np.diff(last_eq) / last_eq[:-1]


def window_stats(ts, opens, closes, w, start):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
    s = bt.stats(r, BPY)
    i = bt.start_index(ts, start)
    s["bench"] = bt.benchmark(closes[i:, 1], ts[i:], BPY)
    s["yearly"] = {str(k): v for k, v in bt.yearly(ts[i:], r["equity"], closes[i:, 1]).items()}
    return r, s


def baseline_weights(ts, opens, closes):
    """165-day QQQ SMA baseline — benchmark/correlation only, never the strategy base."""
    dates, first, last = day_bounds(ts)
    dclose = closes[last]
    sma = pd.Series(dclose[:, 0]).rolling(165).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = dclose[:-1, 0] > sma[:-1]
    tgt = np.zeros((len(first), 3))
    tgt[reg, 1] = 1.0
    tgt[~reg, 2] = 1.0
    return day_weights(tgt, first, last)


def spy_benchmark():
    path = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        date_col = "date" if "date" in df.columns else df.columns[0]
        px_col = "adjclose" if "adjclose" in df.columns else "close"
        d = pd.to_datetime(df[date_col]).dt.date.to_numpy()
        px = df[px_col].to_numpy(dtype=float)
        mask = (d >= pd.Timestamp(START).date()) & (d <= pd.Timestamp(END).date())
        d, px = d[mask], px[mask]
        if len(px) < 100:
            return None
        rets = np.diff(px) / px[:-1]
        years = (pd.Timestamp(d[-1]) - pd.Timestamp(d[0])).days / 365.25
        peak = np.maximum.accumulate(px)
        return {"cagr": float((px[-1] / px[0]) ** (1 / years) - 1.0),
                "max_drawdown": float(-(px / peak - 1.0).min()),
                "volatility": float(np.std(rets, ddof=0) * np.sqrt(252)),
                "years": float(years)}
    except Exception as exc:  # noqa: BLE001
        print("SPY benchmark unavailable:", exc)
        return None


def main():
    ts, opens, closes = bt.panel(SYMS, START, END, "1min")
    w, info = build_weights(ts, opens, closes)
    print(f"dev {ts[0]} -> {ts[-1]}  bars {len(ts)}  events {info['events']}  "
          f"entries {info['entries']}  stops {info['stops']}  addons {info['addons']}")

    out = {
        "agent": "stop-reentry-recovery",
        "original": "research/agents2/stop-reentry-recovery",
        "status": "pre_registered",
        "idea": ("Buy TQQQ after a leveraged-ETF downside overshoot (TQQQ falls "
                 ">=3% intraday and underperforms 3x QQQ by >=1pp), scaling in 50% "
                 "then 100% after a recovery close, with a 2% stop and a 3-session hold."),
        "hypothesis": ("The relative downside overshoot is a rebalancing/flow effect "
                       "that reverses over the next 1-3 sessions; a gradual scale-in "
                       "captures it with low correlation to the 165-day trend base."),
        "universe": ["TQQQ (long)", "BIL (cash)", "QQQ (signal only)"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "benchmarks": {},
        "diagnostics": info,
    }

    # dev cost ladder
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        out["windows"]["dev"][f"{slip:.0f}bp"] = {
            "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]), "sortino": float(s["sortino"]),
            "volatility": float(s["volatility"]), "fills": int(s["fills"]),
            "turnover": float(s["turnover"]), "exposure": float(s["exposure"]),
            "ending_equity": float(s["ending_equity"]),
        }
        print(f"dev {slip:4.0f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:4d}  exp {s['exposure']*100:5.1f}%")

    # sub-periods and correlation
    r1 = bt.run(ts, opens, closes, w, START, band=0.02, slippage_bps=1.0)
    eq = pd.Series(r1["equity"], index=r1["ts"])
    for label, a, b in (("2016-19", "2016-01-04", "2019-12-31 23:59"),
                        ("2020-21", "2020-01-02", "2021-12-31 23:59"),
                        ("2022-23", "2022-01-03", "2023-12-29 23:59")):
        seg = eq.loc[a:b]
        yrs = (seg.index[-1] - seg.index[0]).total_seconds() / (365.25 * 86400)
        out["windows"]["dev"].setdefault("subperiods", {})[label] = {
            "cagr": float((seg.iloc[-1] / seg.iloc[0]) ** (1 / yrs) - 1),
            "max_drawdown": float(-(seg / seg.cummax() - 1).min()),
        }

    wb = baseline_weights(ts, opens, closes)
    rb = bt.run(ts, opens, closes, wb, START, band=0.02, slippage_bps=1.0)
    dates, first, last = day_bounds(ts)
    r_strat = daily_returns(r1["equity"], first)
    r_base = daily_returns(rb["equity"], first)
    m = min(len(r_strat), len(r_base))
    corr = float(np.corrcoef(r_strat[-m:], r_base[-m:])[0, 1])
    out["corr_vs_165d_baseline"] = corr
    print(f"corr vs 165d baseline: {corr:.3f}")

    sb = bt.stats(rb, BPY)
    out["benchmarks"]["baseline_165d"] = {
        "cagr": float(sb["cagr"]), "max_drawdown": float(sb["max_drawdown"]),
        "sharpe": float(sb["sharpe"]), "fills": int(sb["fills"]),
    }
    for j, name in ((1, "tqqq"), (0, "qqq"), (2, "bil")):
        tgt = np.zeros((len(first), 3)); tgt[:, j] = 1.0
        wbh = day_weights(tgt, first, last)
        s = bt.stats(bt.run(ts, opens, closes, wbh, START, band=0.02, slippage_bps=1.0), BPY)
        out["benchmarks"][name] = {"cagr": float(s["cagr"]),
                                   "max_drawdown": float(s["max_drawdown"]),
                                   "sharpe": float(s["sharpe"])}
    out["benchmarks"]["spy"] = spy_benchmark()
    out["benchmarks"]["original"] = None  # lead to fill from the original result.json
    out["variants_tried"] = 1

    # preliminary hard-bar check; the lead still owns the full audit
    dev1 = out["windows"]["dev"]["1bp"]
    bil_cagr = out["benchmarks"]["bil"]["cagr"]
    base_dd = out["benchmarks"]["baseline_165d"]["max_drawdown"]
    out["status"] = ("passed" if (dev1["cagr"] > bil_cagr
                                  and dev1["max_drawdown"] < base_dd
                                  and corr < 0.60) else "retired_overlay_only")
    out["status_note"] = ("preliminary hard-bar check only; the lead must also verify "
                          "sub-periods, placebo, bootstrap and max correlation vs other rebuilds")

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
