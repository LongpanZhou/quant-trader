"""Engine v3: clean state machine with one-trade-per-day, entry windows, time exits."""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 78


def load_cached():
    import engine2
    return engine2.load_cached()


def make_weights(feats, o, n, p):
    date, bars, last_bar = feats["date"], feats["bars"], feats["last_bar"]
    rsi2, rsi5, z20, dev = feats["rsi2"], feats["rsi5"], feats["z20"], feats["dev_vwap"]
    reg = feats["regime"]
    qqq, tqqq = feats["qqq"], feats["tqqq"]
    qpc = feats["qpc"]
    dopen = feats["dopen"]

    sig = p.get("signal", "none")
    if sig == "rsi2":
        ent, ext = rsi2 < p["entry"], rsi2 > p["exit"]
    elif sig == "rsi5":
        ent, ext = rsi5 < p["entry"], rsi5 > p["exit"]
    elif sig == "boll":
        ent, ext = z20 < p["entry"], z20 > p["exit"]
    elif sig == "vwap":
        ent, ext = dev < p["entry"], dev > p["exit"]
    elif sig == "drop":
        dd = qqq / dopen - 1.0
        ent, ext = dd < p["entry"], dd > p["exit"]
    else:
        ent = np.zeros(n, bool)
        ext = np.zeros(n, bool)

    w = np.zeros((n, 3))
    pos = 0
    entry_px = np.nan
    held = 0
    blocked = None
    peak = np.nan
    entry_bar = -1
    max_held = p.get("max_bars", 10 ** 9)
    exit_bar = p.get("exit_bar", last_bar + 1)
    stop_pnl = p.get("stop_pnl", np.inf)
    trail = p.get("trail", np.inf)
    stop_prev = p.get("stop_prev", np.inf)
    base = p.get("base", 0.0)
    b0, b1 = p.get("entry_bars", (0, last_bar))
    one_day = p.get("one_per_day", True)
    reentry = p.get("reentry", None)  # None | 'rsi2' | 'deeper' | 'reclaim'
    re_deep = p.get("re_deep", -0.04)
    stop_bar_min = p.get("stop_bar_min", 0)
    re_w = p.get("reentry_w", 1.0)
    n_trades = 0
    re_used = False

    for i in range(n - 1):
        d = date[i]
        b = bars[i]
        if i > 0 and date[i] != date[i - 1]:
            re_used = False
        in_reg = reg[i] > 0.5
        if pos:
            pnl = tqqq[i] / entry_px - 1.0
            peak = max(peak, tqqq[i])
            give = tqqq[i] / peak - 1.0
            mv = qqq[i] / qpc[i] - 1.0 if np.isfinite(qpc[i]) else 0.0
            hit = (pnl <= -stop_pnl) or (give <= -trail) or (held >= max_held) or (b >= stop_bar_min and mv <= -stop_prev)
            do_exit = hit or ext[i] or (b >= exit_bar) or (not in_reg) or (one_day and held >= 1 and b >= exit_bar)
            if do_exit:
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                pos = 0
                entry_px, peak, held, entry_bar = np.nan, np.nan, 0, -1
                blocked = d
                continue
            w[i, 1] = 1.0
            w[i, 2] = 0.0
            held += 1
            continue
        # flat
        target = 0.0
        blocked_today = one_day and blocked == d
        re_ok = False
        if blocked_today and reentry is not None and not re_used:
            if reentry == "rsi2":
                re_ok = bool(rsi2[i] < p.get("re_thresh", 5))
            elif reentry == "deeper":
                mv = qqq[i] / qpc[i] - 1.0 if np.isfinite(qpc[i]) else 0.0
                re_ok = bool(mv <= re_deep and qqq[i] > qqq[i - 1])
            elif reentry == "reclaim":
                re_ok = bool(dev[i] > 0 and dev[i - 1] <= 0 and qqq[i] > qqq[i - 1])
        if in_reg and (not blocked_today or re_ok) and b0 <= b <= b1:
            if base > 0:
                target = 1.0
            elif ent[i]:
                target = 1.0
            if re_ok and blocked_today:
                target *= re_w
                re_used = True
        if target > 0:
            pos = 1
            entry_px = tqqq[i + 1]
            peak = entry_px
            held = 1
            entry_bar = b
            n_trades += 1
        w[i, 1] = target
        w[i, 2] = 1.0 - target
    w[-1] = (0.0, 0.0, 1.0)
    return w


def run_one(ts, o, c, feats, p, slip=1.0, verbose=True):
    w = make_weights(feats, o, len(ts), p)
    out = {}
    for start, key in ((START10, "10y"), (START5, "5y")):
        res = bt.run(ts, o, c, w, start, band=0.0, slippage_bps=slip)
        s = bt.stats(res, BARS_PER_YEAR)
        i0 = bt.start_index(ts, start)
        bm = bt.benchmark(c[i0:, 1], ts[i0:], 252)
        out[key] = dict(stats=s, bench=bm, res=res)
        if verbose:
            print(f"  {key} {slip:.0f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:5d} turn {s['turnover']:7.0f}x")
    return out, w
