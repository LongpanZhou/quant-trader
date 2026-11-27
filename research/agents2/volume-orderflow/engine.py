"""Shared strategy engine for the volume / order-flow family."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import vlib  # noqa: E402
import fastsim  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
SMA_N = 165


class Data:
    """Panel + per-minute features, computed once."""

    def __init__(self):
        t0 = time.time()
        self.ts, self.op, self.cl, self.hi, self.lo, self.vo = vlib.build_panel()
        self.dates, self.first, self.last, self.day_id = vlib.session_index(self.ts)
        self.tod = vlib.tod_minutes(self.ts)
        self.nd = len(self.first)
        self.n = len(self.ts)
        self._features()
        self.build_time = time.time() - t0

    # ---- per-day matrices
    def _mat(self, arr):
        M = np.full((self.nd, 390), np.nan)
        M[self.day_id, self.tod] = arr
        return M

    def _features(self):
        self.qc_m = self._mat(self.cl[:, 0])
        self.tc_m = self._mat(self.cl[:, 1])
        q = self.qc_m
        v = np.nan_to_num(self._mat(self.vo[:, 0]))
        typ = np.nan_to_num((self._mat(self.hi[:, 0]) + self._mat(self.lo[:, 0]) + q) / 3.0)
        cv = np.cumsum(v, axis=1)
        cpv = np.cumsum(typ * v, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.vwap_q = np.where(cv > 0, cpv / cv, np.nan)
            self.dev_q = q / self.vwap_q - 1.0
        self.cv_q = cv
        self.v_q = v
        self.cv_q_m = cv

        # same-time-of-day 20d mean of cumulative volume (excludes today)
        dfc = pd.DataFrame(cv)
        mean20 = dfc.rolling(20, min_periods=10).mean().shift(1).to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            self.rvol_cum_q = np.where(mean20 > 0, cv / mean20, np.nan)
        # per-bar rvol
        vb = pd.DataFrame(self.v_q)
        m20 = vb.rolling(20, min_periods=10).mean().shift(1).to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            self.rvol_bar_q = np.where(m20 > 0, self.v_q / m20, np.nan)

        # daily closes
        self.qc = np.array([q[d, np.isfinite(q[d]).nonzero()[0][-1]] if np.isfinite(q[d]).any()
                            else np.nan for d in range(self.nd)])
        self.tc = np.array([self.tc_m[d, np.isfinite(self.tc_m[d]).nonzero()[0][-1]]
                            if np.isfinite(self.tc_m[d]).any() else np.nan
                            for d in range(self.nd)])
        self.qo = np.array([self.op[self.first[d], 0] for d in range(self.nd)])
        self.to = np.array([self.op[self.first[d], 1] for d in range(self.nd)])
        self.qv_day = v.sum(1)
        base = pd.Series(self.qv_day).rolling(20, min_periods=10).mean().shift(1).to_numpy()
        self.rvol_day = self.qv_day / base

        sma = pd.Series(self.qc).rolling(SMA_N).mean().to_numpy()
        ma20 = pd.Series(self.qc).rolling(20).mean().to_numpy()
        self.sma = sma
        self.ma20 = ma20
        reg = np.zeros(self.nd, bool)
        reg[1:] = self.qc[:-1] > sma[:-1]
        self.reg = reg
        # per-bar regime flag (signal known at prior close)
        self.reg_bar = reg[self.day_id]

    # ---- helpers
    def fwd_open_return(self):
        """TQQQ close[d] -> open[d+1]."""
        r = np.full(self.nd, np.nan)
        r[:-1] = self.to[1:] / self.tc[:-1] - 1.0
        return r

    def bar_index(self, d, m):
        return self.first[d] + m if m < self._daylen(d) else self.last[d]

    def _daylen(self, d):
        return int(self.last[d] - self.first[d] + 1)


def base_weights(D):
    w = np.zeros((D.n, 3))
    w[:, 1] = D.reg_bar.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def winner_weights(D, stop=0.04, arm_buf=0.01):
    """Round-1 winner: 165d regime + 4% stop armed below MA20*1.01."""
    w = np.zeros((D.n, 3))
    hold = np.zeros(D.n, bool)
    arm_ma = np.r_[np.nan, D.ma20[:-1]]
    stop_bar = np.zeros(D.n, bool)
    for d in range(D.nd):
        f, l = D.first[d], D.last[d]
        if not D.reg[d]:
            continue
        armed = bool(np.isfinite(arm_ma[d]) and D.qc_m[d, 0] < arm_ma[d] * (1 + arm_buf))
        base = D.to[d]
        state = True
        for i in range(f, l + 1):
            if armed and state and D.cl[i, 1] < base * (1 - stop):
                state = False
                stop_bar[i] = True
            hold[i] = state
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, stop_bar


def metrics(res, D, start, bench_k=1):
    s = bt.stats({**res, "ts": D.ts[bt.start_index(D.ts, start):]}, BARS)
    i = bt.start_index(D.ts, start)
    b = bt.benchmark(D.cl[i:, bench_k], D.ts[i:], BARS)
    s["bench"] = b
    s["yearly"] = bt.yearly(D.ts[i:], res["equity"], D.cl[i:, bench_k])
    return s


def evaluate(D, w, label="", slip=1.0, starts=(("10y", START10), ("5y", START5))):
    out = {}
    for name, start in starts:
        i = bt.start_index(D.ts, start)
        r = fastsim.fast_sim(D.op[i:], D.cl[i:], w[i:], band=0.02,
                             slippage_bps=slip)
        r["ts"] = D.ts[i:]
        out[name] = metrics(r, D, start)
    if label:
        txt = "  ".join(
            f"{k}: {v['cagr']*100:6.2f}%/{v['max_drawdown']*100:5.2f}%"
            for k, v in out.items())
        print(f"{label:52s} {txt}")
    return out


def rolling3y(D, w, start=START10, slip=1.0):
    """27 overlapping 3-year windows from 10y start (step 3 months)."""
    r = bt.run(D.ts, D.op, D.cl, w, start, band=0.02, slippage_bps=slip)
    eq = r["equity"]
    ts = r["ts"]
    idx = pd.DatetimeIndex(ts)
    out = []
    t0 = idx[0]
    end = idx[-1]
    t = t0
    while True:
        t_end = t + pd.DateOffset(years=3)
        if t_end > end:
            break
        m = (idx >= t) & (idx <= t_end)
        if m.sum() > 1000:
            e = eq[m]
            b = D.cl[bt.start_index(D.ts, start) + np.flatnonzero(m)[0]:
                     bt.start_index(D.ts, start) + np.flatnonzero(m)[-1] + 1, 1]
            yrs = (ts[np.flatnonzero(m)[-1]] - ts[np.flatnonzero(m)[0]]).total_seconds() / (365.25 * 86400)
            peak = np.maximum.accumulate(e)
            bpk = np.maximum.accumulate(b)
            out.append({
                "start": str(t.date()), "end": str(t_end.date()),
                "cagr": (e[-1] / e[0]) ** (1 / yrs) - 1,
                "dd": float(-(e / peak - 1).min()),
                "bench_cagr": (b[-1] / b[0]) ** (1 / yrs) - 1,
                "bench_dd": float(-(b / bpk - 1).min()),
            })
        t = t + pd.DateOffset(months=3)
    return out
