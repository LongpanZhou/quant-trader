"""Development-only screen for a standalone rebuild of the stop-re-entry idea.

Period: 2016-01-04 .. 2023-12-29.  Holdout 2024-2026 is NOT loaded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")


def load():
    ts, o, c = bt.panel(SYMS, START, END, "1min")
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return ts, o, c, dates, first, last


def day_weights(target, first, last, n):
    w = np.empty((n, 3))
    for k, (f, z) in enumerate(zip(first, last)):
        w[f:z + 1] = target[k]
    return w


def daily_returns(result, dates, first):
    eq = result["equity"]
    # last equity value per day
    last_eq = eq[first[1:] - 1] if len(first) > 1 else eq[[-1]]
    last_eq = np.r_[eq[0], last_eq]
    return np.diff(last_eq) / last_eq[:-1]


def summarize(label, result, dates, first, baseline_ret, nd):
    s = bt.stats(result, BPY)
    r = daily_returns(result, dates, first)
    n = min(len(r), len(baseline_ret))
    corr = float(np.corrcoef(r[-n:], baseline_ret[-n:])[0, 1]) if n > 2 else np.nan
    print(f"{label:42s} CAGR {s['cagr']*100:7.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
          f"Sharpe {s['sharpe']:5.2f}  exp {s['exposure']*100:5.1f}%  fills {s['fills']:5d}  "
          f"corr {corr:5.2f}")
    return dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                exposure=s["exposure"], fills=s["fills"], corr=corr)


def dip_buy_weights(ts, o, c, dates, first, last, hold=1, add_on="none",
                    trend_ma=0, trend_sym=0, stop=0.02, stop_anchor="entry",
                    size0=0.5, size1=1.0):
    """Buy after a 4% close-below-open TQQQ day; hold `hold` sessions; optional add-on.

    add_on: none | next_close | next_open
      next_close: if the first session closes above its open, add at 15:59 same day.
      next_open:  add at 09:31 of the second session if the first session closed above open.
    trend_ma: 0 = no filter; else require the chosen symbol's prior close > its MA.
    """
    n = len(ts)
    nd = len(first)
    dclose = c[last]
    dopen = o[first]
    w = np.zeros((n, 3))
    ma = None
    if trend_ma:
        ma = pd.Series(dclose[:, trend_sym]).rolling(trend_ma).mean().to_numpy()
    events = 0
    for k in range(1, nd):
        if not (dclose[k, 1] < dopen[k, 1] * 0.96):
            continue
        if trend_ma and not (np.isfinite(ma[k - 1]) and dclose[k - 1, trend_sym] > ma[k - 1]):
            continue
        events += 1
        entry_day = k + 1
        if entry_day >= nd:
            continue
        # first session
        f, z = first[entry_day], last[entry_day]
        anchor = o[f + 1, 1] if (stop_anchor == "entry" and f + 1 <= z) else o[f, 1]
        pos = size0
        stopped = False
        for i in range(f, z + 1):
            if pos > 0 and stop > 0 and c[i, 1] < anchor * (1 - stop):
                pos = 0.0
                stopped = True
            w[i, 1] = pos
            w[i, 2] = 1.0 - pos
        # add-on
        if not stopped and add_on == "next_close" and c[z, 1] > o[f, 1] and f + 1 <= z:
            # add at the 15:59 open: set the last bar's target to size1
            w[z - 1:z + 1, 1] = size1
            w[z - 1:z + 1, 2] = 1.0 - size1
            pos = size1
        # remaining hold days
        for d in range(entry_day + 1, min(entry_day + hold, nd)):
            f2, z2 = first[d], last[d]
            if stopped:
                break
            if add_on == "next_open" and d == entry_day + 1 and c[last[entry_day], 1] > o[first[entry_day], 1]:
                pos = size1
            for i in range(f2, z2 + 1):
                if pos > 0 and stop > 0 and c[i, 1] < anchor * (1 - stop):
                    pos = 0.0
                    stopped = True
                w[i, 1] = pos
                w[i, 2] = 1.0 - pos
    return w, dict(events=events)


def stop_overlay(base_tqqq_day, o, c, first, last, stop=0.04, reentry=True,
                 tight=0.02, block=0.5):
    """Apply a 4% session-open stop and the gradual re-entry to a daily TQQQ base."""
    n = len(o)
    nd = len(first)
    w = np.zeros((n, 3))
    prev_stopped = prev_weak = False
    for k in range(nd):
        f, z = first[k], last[k]
        if not base_tqqq_day[k]:
            prev_stopped = prev_weak = False
            continue
        if reentry and prev_weak:
            w[f:z + 1, 1] = 1.0 - block
            w[f:z + 1, 2] = block
            prev_stopped = prev_weak = False
            continue
        was_stopped = prev_stopped
        prev_stopped = prev_weak = False
        day_stop = tight if (was_stopped and reentry) else stop
        base = o[f, 1]
        pos = 1.0
        stopped = False
        for i in range(f, z + 1):
            if pos > 0 and c[i, 1] < base * (1 - day_stop):
                pos = 0.0
                stopped = True
            w[i, 1] = pos
            w[i, 2] = 1.0 - pos
        if stopped:
            prev_stopped = True
            prev_weak = bool(c[z, 1] < base * (1 - day_stop))
    return w


def main():
    ts, o, c, dates, first, last = load()
    nd = len(first)
    n = len(ts)
    dclose = c[last]
    dopen = o[first]
    print(f"dev {ts[0]} -> {ts[-1]}  bars {n}  sessions {nd}")

    # 165-day baseline (benchmark only, never used by the rebuild)
    sma = pd.Series(dclose[:, 0]).rolling(165).mean().to_numpy()
    reg = np.zeros(nd, bool)
    reg[1:] = dclose[:-1, 0] > sma[:-1]
    tgt = np.zeros((nd, 3)); tgt[reg, 1] = 1; tgt[~reg, 2] = 1
    wb = day_weights(tgt, first, last, n)
    rb = bt.run(ts, o, c, wb, START, band=0.02, slippage_bps=1.0)
    sbase = bt.stats(rb, BPY)
    base_ret = daily_returns(rb, dates, first)
    print(f"{'BASELINE 165d (benchmark)':42s} CAGR {sbase['cagr']*100:7.2f}%  "
          f"DD {sbase['max_drawdown']*100:5.2f}%  Sharpe {sbase['sharpe']:5.2f}  "
          f"exp {sbase['exposure']*100:5.1f}%  fills {sbase['fills']:5d}")

    variants = {}
    # buy and hold
    for j, name in ((1, "tqqq_bh"), (0, "qqq_bh"), (2, "bil_bh")):
        t = np.zeros((nd, 3)); t[:, j] = 1.0
        variants[name] = day_weights(t, first, last, n)

    # fast MA bases
    for nma in (10, 20, 50):
        ma = pd.Series(dclose[:, 1]).rolling(nma).mean().to_numpy()
        on = np.zeros(nd, bool)
        on[1:] = dclose[:-1, 1] > ma[:-1]
        t = np.zeros((nd, 3)); t[on, 1] = 1; t[~on, 2] = 1
        variants[f"tqqq_ma{nma}"] = day_weights(t, first, last, n)

    # dip-buy variants
    for hold in (1, 3, 5):
        for add in ("none", "next_close", "next_open"):
            for tr in (0, 20, 50):
                w, info = dip_buy_weights(ts, o, c, dates, first, last, hold=hold,
                                          add_on=add, trend_ma=tr, trend_sym=0)
                variants[f"dip_h{hold}_{add}_tr{tr}"] = w

    # naive always-long + stop/re-entry
    variants["always_stop_reentry"] = stop_overlay(np.ones(nd, bool), o, c, first, last)
    variants["always_stop"] = stop_overlay(np.ones(nd, bool), o, c, first, last, reentry=False)
    for nma in (20, 50):
        ma = pd.Series(dclose[:, 1]).rolling(nma).mean().to_numpy()
        on = np.zeros(nd, bool)
        on[1:] = dclose[:-1, 1] > ma[:-1]
        variants[f"ma{nma}_stop_reentry"] = stop_overlay(on, o, c, first, last)
        variants[f"ma{nma}_stop"] = stop_overlay(on, o, c, first, last, reentry=False)

    rows = {}
    for name, w in variants.items():
        r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
        rows[name] = summarize(name, r, dates, first, base_ret, nd)

    # sort by corr then cagr
    print("\nlowest correlation:")
    for name, row in sorted(rows.items(), key=lambda kv: kv[1]["corr"])[:12]:
        print(f"  {name:42s} corr {row['corr']:5.2f}  CAGR {row['cagr']*100:7.2f}%  DD {row['dd']*100:5.2f}%")


if __name__ == "__main__":
    main()
