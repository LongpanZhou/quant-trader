"""Reusable 5m research engine for the intraday mean-reversion agent.

Features are computed on QQQ 5-minute bars; trades happen in TQQQ (3x) or BIL.
No look-ahead: a weight set at bar i is filled at open i+1 by bt.run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 78


def load_panel(rule: str = "5min"):
    """Return ts, opens, closes (3 cols), plus 5m features and daily regime."""
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, rule)
    qqq = c[:, 0]

    date = pd.Series(ts.date)
    bars = date.groupby(date).cumcount().to_numpy()
    # 1m/5m volume for VWAP
    raw = bt.load_1m("QQQ")
    raw = raw.set_index("ts")
    if rule == "5min":
        vol = raw["volume"].resample("5min", origin="start_day").sum().reindex(ts).to_numpy()
        hi = raw["high"].resample("5min", origin="start_day").max().reindex(ts).to_numpy()
        lo = raw["low"].resample("5min", origin="start_day").min().reindex(ts).to_numpy()
    else:
        vol, hi, lo = raw["volume"].to_numpy(), raw["high"].to_numpy(), raw["low"].to_numpy()
    vol = np.nan_to_num(vol, nan=0.0)

    # intraday cumulative VWAP (resets each day)
    pv = qqq * vol
    dfv = pd.DataFrame({"d": date, "pv": pv, "v": vol, "tp": (hi + lo + qqq) / 3.0})
    cs = dfv.groupby("d")[["pv", "v"]].cumsum()
    cs2 = dfv.groupby("d")["tp"].cumsum()
    cnt = dfv.groupby("d").cumcount() + 1
    vwap = cs["pv"].to_numpy() / cs["v"].to_numpy()
    twap = cs2.to_numpy() / cnt.to_numpy()
    dev_vwap = qqq / vwap - 1.0
    dev_twap = qqq / twap - 1.0

    # RSI
    def rsi(n):
        d = np.diff(qqq, prepend=qqq[0])
        au = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
        ad = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
        return 100 * au / np.where(au + ad > 0, au + ad, np.nan)

    rsi2, rsi5 = rsi(2), rsi(5)

    s = pd.Series(qqq)
    m20 = s.rolling(20).mean().to_numpy()
    sd20 = s.rolling(20).std(ddof=0).to_numpy()
    z20 = (qqq - m20) / np.where(sd20 > 0, sd20, np.nan)

    # daily close / regime from the 1D panel (matches README baseline exactly)
    tsd, _, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
    qd = cd[:, 0]
    dd = pd.DataFrame({"c": qd}, index=pd.Index([t.date() for t in tsd]))
    sma = dd["c"].rolling(165).mean()
    reg = (dd["c"] > sma).astype(float)
    reg_prev = reg.shift(1)  # used intraday: last completed daily close
    reg_map = reg_prev.to_dict()

    feats = {
        "date": date.to_numpy(),
        "bars": bars,
        "rsi2": rsi2,
        "rsi5": rsi5,
        "z20": z20,
        "dev_vwap": dev_vwap,
        "dev_twap": dev_twap,
        "regime": np.array([reg_map.get(d, 0.0) for d in date.to_numpy()], dtype=float),
        "regime_today": np.array([reg.to_dict().get(d, 0.0) for d in date.to_numpy()], dtype=float),
        "qqq": qqq,
        "tqqq": c[:, 1],
        "vol": vol,
    }
    return ts, o, c, feats


def precompute_day_ref(feats, ts, closes):
    """Previous daily close per bar (for intraday stop from prior close)."""
    date = feats["date"]
    s = pd.Series(closes[:, 0])
    last = pd.Series(closes[:, 0]).groupby(date).last()
    prev = last.shift(1)
    feats["qqq_prev_close"] = np.array([prev.get(d, np.nan) for d in date], dtype=float)
    lastt = pd.Series(closes[:, 1]).groupby(date).last()
    prevt = lastt.shift(1)
    feats["tqqq_prev_close"] = np.array([prevt.get(d, np.nan) for d in date], dtype=float)
    return feats


def make_weights(feats, o, n, p):
    """State machine -> target weights (n,3). Decision at close of bar i, fill open i+1."""
    date = feats["date"]
    rsi2, rsi5 = feats["rsi2"], feats["rsi5"]
    z20, dev = feats["z20"], feats["dev_vwap"]
    reg = feats["regime"]
    qqq, tqqq = feats["qqq"], feats["tqqq"]
    qpc, tpc = feats["qqq_prev_close"], feats["tqqq_prev_close"]
    bars = feats["bars"]
    last_bar = int(bars.max())

    # entry/exit signals
    sig_entry = np.zeros(n, bool)
    if p["signal"] == "rsi":
        sig_entry = rsi2 < p["entry"]
        sig_exit = rsi2 > p["exit"]
    elif p["signal"] == "boll":
        sig_entry = z20 < p["entry"]
        sig_exit = z20 > p["exit"]
    elif p["signal"] == "vwap":
        sig_entry = dev < p["entry"]
        sig_exit = dev > p["exit"]
    elif p["signal"] == "none":
        sig_entry = np.zeros(n, bool)
        sig_exit = np.zeros(n, bool)

    w = np.zeros((n, 3))
    pos = 0
    entry_px = np.nan
    held = 0
    max_held = p.get("max_bars", 10 ** 9)
    stop = p.get("stop", np.inf)          # stop on position P&L (fraction)
    stop_prev = p.get("stop_prev", np.inf)  # stop on move from prior daily close
    eod = p.get("eod_flat", False)
    base = p.get("base", 0.0)            # weight held when regime on and no MR signal
    reentry = p.get("reentry", None)     # re-entry threshold when flat
    cooldown = p.get("cooldown", 0)
    cd_left = 0

    for i in range(n - 1):
        target = 0.0
        in_regime = reg[i] > 0.5
        if not in_regime:
            pos = 0 if pos else pos
            if pos:
                pos = 0
            held = 0
            entry_px = np.nan
            w[i] = (0.0, 0.0, 1.0)
            continue
        if not np.isfinite(entry_px):
            pos = 0
        if pos:
            pnl = qqq[i] / entry_px - 1.0 if p["pnl_on"] == "qqq" else tqqq[i] / entry_px - 1.0
            move_prev = qqq[i] / qpc[i] - 1.0
            hit_stop = pnl <= -stop or move_prev <= -stop_prev or held >= max_held
            hit_sig = sig_exit[i]
            at_eod = eod and bars[i] >= last_bar - 1
            if hit_stop or hit_sig or at_eod or cd_left > 0:
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                pos = 0
                held = 0
                entry_px = np.nan
                cd_left = cooldown
            else:
                w[i, 1] = 1.0
                held += 1
        else:
            if cd_left > 0:
                cd_left -= 1
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                continue
            if eod and bars[i] >= last_bar - 2:
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                continue
            enter = False
            if base > 0:
                enter = True
                if p.get("require_dip", False):
                    enter = sig_entry[i] or (reentry is not None and rsi2[i] < reentry)
            else:
                enter = bool(sig_entry[i]) or (reentry is not None and rsi2[i] < reentry)
            if enter:
                w[i, 1] = 1.0
                pos = 1
                entry_px = tqqq[i + 1]  # filled at next open
                held = 1
            else:
                w[i, 1] = 0.0
                w[i, 2] = 1.0
        w[i, 1] = max(0.0, min(1.0, w[i, 1]))
        w[i, 2] = 1.0 - w[i, 1]
    w[-1] = (0.0, 0.0, 1.0)
    return w


def evaluate(ts, o, c, w, start, slip=1.0, label=""):
    res = bt.run(ts, o, c, w, start, band=0.0, slippage_bps=slip)
    s = bt.stats(res, BARS_PER_YEAR)
    i0 = bt.start_index(ts, start)
    b = bt.benchmark(c[i0:, 1], ts[i0:], 252)
    return s, b, res


def summarize(ts, o, c, feats, p, slip=1.0, verbose=True):
    w = make_weights(feats, o, len(ts), p)
    out = {}
    for start, key in ((START10, "10y"), (START5, "5y")):
        s, b, res = evaluate(ts, o, c, w, start, slip)
        out[key] = {"stats": s, "bench": b}
        if verbose:
            print(f"  {key} slip={slip:.0f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
                  f"Sharpe {s['sharpe']:4.2f}  expo {s['exposure']*100:5.1f}%  fills {s['fills']:5d}  "
                  f"turn {s['turnover']:7.1f}x")
    return out, w
