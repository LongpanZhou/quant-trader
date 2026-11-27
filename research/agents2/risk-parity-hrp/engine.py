"""Clean engine for the risk-parity agent.

All daily signals at session k use data through the close of session k-1 only.
Weights set at session k apply to that session's bars and fill at the next
bar's open (bt.simulate). The 4% stop is a minute-level override: when it
fires, the TQQQ sleeve is liquidated at the next minute open and stays out for
the rest of the session and the following night.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS = 252 * 390
SMA_N, MA20, STOP, ARM = 165, 20, 0.04, 0.01


def load_panel():
    z = np.load(HERE / "panel_1m.npz")
    ts = pd.DatetimeIndex(z["ts"], tz="UTC").tz_convert("America/New_York")
    return ts, z["opens"], z["closes"]


def session_bounds(ts):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    return dates, first, np.r_[first[1:] - 1, len(ts) - 1]


def lag(x):
    """Shift a daily series by one session: value known at prior close."""
    out = np.empty_like(x)
    out[0] = np.nan
    out[1:] = x[:-1]
    return out


class Signals:
    def __init__(self, ts, opens, closes):
        self.ts, self.opens, self.closes = ts, opens, closes
        self.dates, self.first, self.last = session_bounds(ts)
        d = len(self.first)
        self.n, self.d = len(ts), d
        self.dcl = closes[self.last]              # (d,3) session closes
        self.dop = opens[self.first]              # (d,3) session opens
        q = self.dcl[:, 0]
        sma = pd.Series(q).rolling(SMA_N).mean().to_numpy()
        ma20 = pd.Series(q).rolling(MA20).mean().to_numpy()
        # risk-on for session k: prior close above SMA through prior close
        self.sma_prev = lag(sma)
        self.ma20_prev = lag(ma20)
        self.risk_on = np.zeros(d, bool)
        self.risk_on[1:] = q[:-1] > self.sma_prev[1:]
        # stop armed at session k: first-minute QQQ below prior MA20 * 1.01
        self.armed = np.zeros(d, bool)
        for k in range(1, d):
            if self.risk_on[k] and np.isfinite(self.ma20_prev[k]):
                self.armed[k] = closes[self.first[k], 0] < self.ma20_prev[k] * (1 + ARM)
        self.stopped = np.zeros(self.n, bool)
        for k in range(d):
            if not self.armed[k]:
                continue
            f, l = self.first[k], self.last[k]
            base = opens[f, 1]
            dead = False
            for i in range(f, l + 1):
                if not dead and closes[i, 1] < base * (1 - STOP):
                    dead = True
                self.stopped[i] = dead
        self.day_id = np.repeat(np.arange(d), np.diff(np.r_[self.first, self.n]))
        self.rets = np.diff(self.dcl, axis=0) / self.dcl[:-1]

    def vol(self, win: int) -> np.ndarray:
        """Annualised daily-close vol through the prior close, shape (d,3)."""
        v = pd.DataFrame(self.rets).rolling(win).std().to_numpy() * np.sqrt(252)
        v = np.vstack([np.full((1, 3), np.nan), v])   # align to dcl rows
        return lag(v)                                  # use through k-1

    def drawdown(self, win: int) -> np.ndarray:
        q = self.dcl[:, 0]
        hi = pd.Series(q).rolling(win).max().to_numpy()
        dd = q / hi - 1.0
        return lag(dd)

    def weights(self, wt_tqqq: np.ndarray, dest: str = "bil") -> np.ndarray:
        """wt_tqqq: TQQQ share of the risk-on equity sleeve, per session.

        dest is where the stopped TQQQ sleeve goes: 'bil', 'qqq' or 'half'.
        """
        w = np.zeros((self.n, 3))
        on = self.risk_on[self.day_id]
        tq = np.nan_to_num(wt_tqqq, nan=1.0)[self.day_id]
        dead = self.stopped
        live = on & ~dead
        w[:, 1] = np.where(live, tq, 0.0)
        wq = np.where(on, 1.0 - tq, 0.0)          # base QQQ sleeve of the mix
        w[:, 2] = np.where(on, 0.0, 1.0)          # BIL when regime off
        if dest == "bil":
            w[:, 2] += np.where(on & dead, tq, 0.0)
        elif dest == "qqq":
            wq = wq + np.where(on & dead, tq, 0.0)
        elif dest == "half":
            wq = wq + np.where(on & dead, 0.5 * tq, 0.0)
            w[:, 2] += np.where(on & dead, 0.5 * tq, 0.0)
        else:
            raise ValueError(dest)
        w[:, 0] = wq
        # rows sum to 1 by construction
        return w


def run_window(sig, w, start, slip=1.0, band=0.02):
    r = bt.run(sig.ts, sig.opens, sig.closes, w, start, band=band, slippage_bps=slip)
    return bt.stats(r, BARS), r


def fmt(label, m10, m5, extra=""):
    return (f"{label:<30} 10y {m10['cagr']*100:6.2f}/{m10['max_drawdown']*100:5.2f} "
            f"C{m10['cagr']/m10['max_drawdown']:4.2f} "
            f"| 5y {m5['cagr']*100:6.2f}/{m5['max_drawdown']*100:5.2f} "
            f"C{m5['cagr']/m5['max_drawdown']:4.2f} f{m10['fills']:4d} {extra}")
