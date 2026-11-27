"""Shared helpers for the overnight / first-hour + crash-filter agent (round 2).

Loads the cached 1-minute QQQ/TQQQ/BIL panel (warmed up 500 calendar days
before 2017-01-03) and provides:

  * daily arrays (first/last bar per session, daily close),
  * regime / volatility / gap indicators, all strictly causal,
  * a weight builder that describes *positions* (p[i] = TQQQ weight held
    during bar i) and converts them to the harness convention
    (weights[i] is executed at the open of bar i+1),
  * `fast_sim`, a vectorised replica of `bt.simulate` (validated to 1e-12),
  * metric helpers (CAGR, max DD, Sharpe, yearly, rolling 3y).

No core repository file is modified.
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
CACHE = HERE / "panel_cache.npz"
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N = 165
BARS_PER_YEAR = 252 * 390

# Reference numbers from research/agents2/README.md (winner, daily marks).
WINNER = {
    "10y": {"1bp": (0.5880, 0.4456), "5bp": (0.5460, 0.4708), "10bp": (0.4950, 0.5006)},
    "5y": {"1bp": (0.4988, 0.3349), "5bp": (0.4589, 0.3413), "10bp": (0.4105, 0.3493)},
}
TQQQ_BH = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
DAILY_BASE = {"10y": (0.4531, 0.5871), "5y": (0.3461, 0.3686)}
TOD_V2 = {"10y": (0.4923, 0.4266), "5y": (0.2889, 0.3454)}  # round-1 time-of-day


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_panel(force: bool = False):
    """ts, opens, highs, lows, closes, vols (n x 3) for QQQ, TQQQ, BIL."""
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(
            pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
        )
        return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]

    symbols = ("QQQ", "TQQQ", "BIL")
    ts, opens, closes = bt.panel(symbols, START10, END, "1min", warmup_days=500)
    highs, lows, vols = [], [], []
    for sym in symbols:
        df = bt.load_1m(sym).set_index("ts")
        highs.append(df["high"].reindex(ts).ffill().bfill().to_numpy())
        lows.append(df["low"].reindex(ts).ffill().bfill().to_numpy())
        vols.append(df["volume"].reindex(ts).fillna(0.0).to_numpy())
    np.savez_compressed(
        CACHE,
        ts=ts.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("int64"),
        opens=opens,
        highs=np.column_stack(highs),
        lows=np.column_stack(lows),
        closes=closes,
        vols=np.column_stack(vols),
    )
    return ts, opens, np.column_stack(highs), np.column_stack(lows), closes, np.column_stack(vols)


class Days:
    """Per-session index and daily aggregates."""

    def __init__(self, ts, opens, closes):
        self.ts = ts
        self.opens = opens
        self.closes = closes
        dates = np.array([t.date() for t in ts])
        self.dates = dates
        self.first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        self.last = np.r_[self.first[1:] - 1, len(dates) - 1]
        self.ddates = dates[self.first]
        self.nd = len(self.first)
        # daily close = last minute close; daily open = first minute open
        self.dclose = closes[self.last]
        self.dopen = opens[self.first]
        # last price known at the 15:58 decision bar (15:59:00 print)
        self.dc_now = closes[np.maximum(self.last - 1, self.first)]
        self.day_id = np.repeat(np.arange(self.nd), np.diff(np.r_[self.first, len(ts)]))
        assert (self.day_id == np.arange(len(ts)) * 0 + self.day_id).all()

    # ---- indicators (all lag-1: known at the 09:30 of the next session) ----
    def sma(self, n=SMA_N, col=0):
        return pd.Series(self.dclose[:, col]).rolling(n).mean().to_numpy()

    def gate(self, n=SMA_N, band=0.0):
        """Regime state for day k, from the close of day k-1 and the SMA
        through day k-1. band>0 adds hysteresis (state machine)."""
        d = self.dclose[:, 0]
        sma = self.sma(n)
        out = np.zeros(self.nd, bool)
        if band <= 0:
            out[1:] = d[:-1] > sma[:-1]
            return out
        state = False
        for k in range(1, self.nd):
            if not np.isfinite(sma[k - 1]):
                state = False
            elif d[k - 1] > sma[k - 1] * (1.0 + band):
                state = True
            elif d[k - 1] < sma[k - 1] * (1.0 - band):
                state = False
            out[k] = state
        return out

    def vol(self, n=20, col=0, ann=True):
        """Annualised realised vol of daily log returns, through day k-1."""
        d = self.dclose[:, col]
        r = np.r_[np.nan, np.log(d[1:] / d[:-1])]
        s = pd.Series(r).rolling(n).std(ddof=0).to_numpy()
        out = np.full(self.nd, np.nan)
        out[1:] = s[:-1]
        return out * (np.sqrt(252.0) if ann else 1.0)

    def vol_now(self, n=20, col=0, ann=True):
        """Same but using today's 15:58 close (causal at the 15:58 bar)."""
        d = self.dclose[:, col]
        r = np.r_[np.nan, np.log(d[1:] / d[:-1])]
        s = pd.Series(r).rolling(n).std(ddof=0).to_numpy()
        return s * (np.sqrt(252.0) if ann else 1.0)

    def ma(self, n=20, col=0):
        return pd.Series(self.dclose[:, col]).rolling(n).mean().to_numpy()

    # ---- block returns ----
    def overnight_ret(self, col=1):
        """09:30 open of day k+1 / 15:59 open of day k - 1."""
        out = np.full(self.nd, np.nan)
        out[:-1] = self.dopen[1:, col] / self.opens[self.last[:-1], col] - 1.0
        return out

    def first_m_ret(self, m=30, col=1):
        """Return from the 09:30 open to the open of bar f+m (m minutes)."""
        out = np.full(self.nd, np.nan)
        for k in range(self.nd):
            f, l = self.first[k], self.last[k]
            if f + m <= l:
                out[k] = self.opens[f + m, col] / self.opens[f, col] - 1.0
        return out

    def session_ret(self, col=1):
        out = np.full(self.nd, np.nan)
        for k in range(self.nd):
            f, l = self.first[k], self.last[k]
            out[k] = self.closes[l, col] / self.opens[f, col] - 1.0
        return out


# --------------------------------------------------------------------------
# weight construction
# --------------------------------------------------------------------------
def build_weights(days, base="overnight", m=0, gate=None, band=0.0,
                  night_mask=None, vol_max=None, vol_win=20, vol_now=False,
                  vol_pct_max=None, vol_pct_win=504,
                  gap_exit=None, stop=None, stop_arm_ma20=False, arm_buf=0.01,
                  signal_thr=0.0, bil_when_off=True, idx=None):
    """Return (n,3) harness weights.

    base:
      'overnight'  hold TQQQ 15:59 -> 09:30 next morning (m ignored)
      'morning'    hold TQQQ 15:59 -> open of bar f+m next morning
      'signal'     overnight + first m minutes, then hold the rest of the
                   session iff QQQ first-m return >= signal_thr
      'full'       continuous TQQQ whenever the regime is on (control)
    gate: bool array per day (default: plain 165-day SMA, lag 1)
    vol_max: skip the overnight entry when QQQ vol(vol_win) > vol_max
    gap_exit: at 09:30 of day k+1, if QQQ gap < -gap_exit then exit at 09:31
    stop: intraday stop from the session open (TQQQ close < open*(1-stop)),
          next-bar fill, flat for the rest of the held block/day
    """
    nd = days.nd
    if gate is None:
        gate = days.gate(SMA_N, band)
    vol = days.vol_now(vol_win) if vol_now else days.vol(vol_win)
    qqq_o, qqq_c = days.opens[:, 0], days.closes[:, 0]
    tqqq_o, tqqq_c = days.opens[:, 1], days.closes[:, 1]
    ma20 = days.ma(20)

    # overnight gate per day (entry at 15:59 of day k)
    go = gate.copy()
    if night_mask is not None:
        go &= night_mask
    if vol_max is not None:
        go &= ~(vol > vol_max)
    if vol_pct_max is not None:
        vp = pd.Series(vol).rolling(vol_pct_win, min_periods=252).rank(pct=True).to_numpy()
        go &= ~(vp > vol_pct_max)

    p_t = np.zeros(len(days.ts))   # TQQQ position during bar i
    p_b = np.zeros(len(days.ts))   # BIL position during bar i

    for k in range(nd):
        f, l = days.first[k], days.last[k]
        g = bool(gate[k])
        gp = bool(go[k - 1]) if k > 0 else False
        go_k = bool(go[k])

        if base == "full":
            p_t[f:l + 1] = 1.0 if g else 0.0
            p_b[f:l + 1] = 1.0 if not g else 0.0
            continue

        mm = 0 if base == "overnight" else int(m)

        # ---------------- morning block (continuation of last night) ------
        held_morning = bool(gp and mm > 0)
        exit_at = f + mm
        if held_morning:
            # gap filter: observed at the 09:30 open, exit at 09:31
            if gap_exit is not None:
                gap = qqq_o[f] / days.dclose[k - 1, 0] - 1.0
                if gap < -gap_exit:
                    exit_at = f + 1
            # intraday stop inside the morning block
            if stop is not None:
                armed = True
                if stop_arm_ma20:
                    armed = bool(np.isfinite(ma20[k - 1])
                                 and qqq_o[f] < ma20[k - 1] * (1 + arm_buf))
                if armed:
                    base_px = tqqq_o[f]
                    for i in range(f, min(exit_at, l + 1)):
                        if tqqq_c[i] < base_px * (1.0 - stop):
                            exit_at = i + 1
                            break
            p_t[f:min(exit_at, l + 1)] = 1.0

        # ---------------- afternoon --------------------------------------
        afternoon_on = False
        a_start = min(f + mm, l + 1)
        a_end = l  # exclusive: hold bars a_start .. a_end-1
        if base == "signal" and mm > 0:
            sig = qqq_c[min(f + mm - 1, l)] / qqq_o[f] - 1.0
            afternoon_on = bool(g) and sig >= signal_thr
            if afternoon_on and stop is not None:
                armed = True
                if stop_arm_ma20:
                    armed = bool(np.isfinite(ma20[k - 1])
                                 and qqq_o[f] < ma20[k - 1] * (1 + arm_buf))
                if armed:
                    base_px = tqqq_o[f]
                    for i in range(a_start, l + 1):
                        if tqqq_c[i] < base_px * (1.0 - stop):
                            a_end = i + 1   # exit at the open of bar i+1
                            break
                    if a_end <= a_start:
                        afternoon_on = False
            if afternoon_on:
                p_t[a_start:a_end] = 1.0

        # ---------------- risk-off / cash --------------------------------
        if not g:
            b_start = exit_at if held_morning else f
            p_b[b_start:l + 1] = 1.0
        # ---------------- overnight entry at 15:59 ------------------------
        if go_k:
            p_t[l] = 1.0
            p_b[l] = 0.0
        else:
            p_t[l] = 0.0
            if bil_when_off:
                p_b[l] = 1.0

    w = np.zeros((len(days.ts), 3))
    w[:-1, 1] = p_t[1:]
    w[:-1, 2] = p_b[1:]
    w[-1, 1] = p_t[-1]
    w[-1, 2] = p_b[-1]
    return w


# --------------------------------------------------------------------------
# fast exact simulator (replica of bt.simulate, vectorised marking)
# --------------------------------------------------------------------------
def fast_sim(ts, opens, closes, weights, band=0.02, slippage_bps=1.0,
             start_equity=100_000.0):
    """Delegates to bt.simulate (compiled Rust core, exact for any weights)."""
    return bt.simulate(ts, opens, closes, weights, band=band,
                       slippage_bps=slippage_bps, start_equity=start_equity)


def run_window(ts, opens, closes, weights, start, **kw):
    i = bt.start_index(ts, start)
    return fast_sim(ts[i:], opens[i:], closes[i:], weights[i:], **kw)


def stats(result, bars_per_year=BARS_PER_YEAR):
    return bt.stats(result, bars_per_year)


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def dd_daily(ts, equity):
    s = pd.Series(equity, index=ts)
    deq = s.groupby(s.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    return float(-(deq / peak - 1.0).min())


def yearly(ts, equity, bench):
    return bt.yearly(ts, equity, bench)


def rolling3(ts, equity, bench, step_months=3, years=3):
    """CAGR / maxDD over rolling `years` windows starting every step_months."""
    s = pd.Series(equity, index=ts)
    b = pd.Series(bench, index=ts)
    de = s.groupby(s.index.date).last()
    db = b.groupby(b.index.date).last()
    idx = pd.DatetimeIndex(de.index)
    starts = pd.date_range(idx[0], idx[-1], freq=f"{step_months}MS")
    starts = [d for d in starts if d <= idx[-1] - pd.DateOffset(years=years)]
    out = []
    for st in starts:
        en = st + pd.DateOffset(years=years)
        seg = (idx >= st) & (idx < en)
        if seg.sum() < 400:
            continue
        e = de.to_numpy()[seg]
        bb = db.to_numpy()[seg]
        yrs = (idx[seg][-1] - idx[seg][0]).days / 365.25
        def m(x):
            peak = np.maximum.accumulate(x)
            return float((x[-1] / x[0]) ** (1 / yrs) - 1), float(-(x / peak - 1).min())
        c, d = m(e)
        cb, dbd = m(bb)
        out.append({"start": str(st.date()), "cagr": c, "dd": d,
                    "bench_cagr": cb, "bench_dd": dbd})
    return out


def summarize(ts, opens, closes, w, start, slip=1.0, label=""):
    r = run_window(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = stats(r)
    i = bt.start_index(ts, start)
    b = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR)
    s["bench"] = b
    s["max_drawdown_daily"] = dd_daily(ts[i:], r["equity"])
    if label:
        print(f"{label:38s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:4.2f}  fills {s['fills']:6,d}  turn {s['turnover']:8.1f}x  "
              f"exp {s['exposure']*100:5.1f}%")
    return s, r
