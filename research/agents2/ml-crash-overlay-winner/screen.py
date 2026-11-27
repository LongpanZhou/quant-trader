"""Fast daily-equivalent screener for daily overrides on the winner.

The base winner's 1-minute equity path is computed once.  An override at the
close of day d-1 replaces session d's *intraday* return with another asset
(the overnight gap is already held by the position at the close of d-1).
This is exact for close-decision overrides, up to the harness's 2% band.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze2 import winner_daily  # noqa: E402
from proto import walk_forward, logistic_fit  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}


class DailyPath:
    def __init__(self, ts, o, c):
        dates = np.array([t.date() for t in ts])
        first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        last = np.r_[first[1:] - 1, len(dates) - 1]
        self.ts = ts
        self.first, self.last = first, last
        self.dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
        self.do = o[first]          # (n, 3) day open
        self.dc = c[last]           # (n, 3) day close
        self.overnight = np.full((len(first), 3), np.nan)
        self.overnight[1:] = self.do[1:] / self.dc[:-1] - 1.0
        self.intraday = self.dc / self.do - 1.0
        self.day_of_bar = pd.Index(dates).map(
            {d: k for k, d in enumerate(self.dts.date)}).to_numpy()


def eq_from_daily(rets):
    eq = np.empty(len(rets) + 1)
    eq[0] = 100_000.0
    for i, r in enumerate(rets):
        eq[i + 1] = eq[i] * (1.0 + r)
    return eq


def daily_stats(eq, idx):
    eq = np.asarray(eq)
    rets = np.diff(eq) / eq[:-1]
    years = (idx[-1] - idx[0]).days / 365.25
    peak = np.maximum.accumulate(eq)
    return {
        "cagr": (eq[-1] / eq[0]) ** (1 / years) - 1,
        "max_drawdown": float(-(eq / peak - 1).min()),
        "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(252)),
        "vol": float(np.std(rets) * np.sqrt(252)),
    }


def sim_override(dp, base_eq, w_win, override, repl_w, held_day, start_k=None):
    """Exact daily splice: keep the base overnight of the *modified* position and
    replace only the intraday leg on overridden days."""
    n = len(dp.dts)
    if start_k is None:
        start_k = int(np.flatnonzero(np.isfinite(base_eq))[0])
    close_w = np.zeros((n, 3))
    for k in range(n):
        close_w[k] = w_win[dp.last[k]]
    cur_close = close_w.copy()
    rets = np.zeros(n - start_k)
    for k in range(start_k + 1, n):
        base_ret = base_eq[k] / base_eq[k - 1] - 1
        over_base = float(close_w[k - 1] @ dp.overnight[k])
        intra_base = (1 + base_ret) / (1 + over_base) - 1
        over_mod = float(cur_close[k - 1] @ dp.overnight[k])
        if override[k] and held_day[k]:
            intra_mod = float(repl_w[k] @ dp.intraday[k])
            cur_close[k] = repl_w[k]
        else:
            intra_mod = intra_base
            cur_close[k] = close_w[k]
        rets[k - start_k] = (1 + over_mod) * (1 + intra_mod) - 1
    return eq_from_daily(rets), start_k


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dp = DailyPath(ts, o, c)
    dts = dp.dts

    r = bt.run(ts, o, c, w_win, START, band=0.02, slippage_bps=1.0)
    i_start = bt.start_index(ts, START)
    eq1m = pd.Series(r["equity"], index=ts[i_start:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dts).to_numpy()

    print("winner 1m:", f"{bt.stats(r, BARS)['cagr']*100:.2f}/{bt.stats(r, BARS)['max_drawdown']*100:.2f}")
    i0 = dts.searchsorted(pd.Timestamp("2017-01-03"))
    print("winner daily approx:", {k: round(v * 100, 2) if k != "sharpe" else round(v, 3)
                                   for k, v in daily_stats(base_eq[i0:] / base_eq[i0] * 100000,
                                                           dts[i0:]).items()})

    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    tqc = pd.Series(dp.dc[:, 1], index=dts)
    bil = pd.Series(dp.dc[:, 2], index=dts)
    tot = tqc.pct_change().shift(-1)
    bilr = bil.pct_change().shift(-1)
    ex = tot - bilr
    gap = pd.Series(dp.overnight[:, 1], index=dts)
    intra = pd.Series(dp.intraday[:, 1], index=dts)
    labels = {}
    for nm, thr in (("c15", -0.015), ("c2", -0.02), ("c25", -0.025), ("c3", -0.03), ("c4", -0.045)):
        y = (tot < thr).astype(float); y[~np.isfinite(tot)] = np.nan
        labels[nm] = y
    # NOTE: gap/intraday labels must be lagged by one day to be tradable at the
    # close of the prior session; they are excluded from this close-decision grid.

    feats = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
             "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
             "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
             "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
             "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]
    x = f[feats].to_numpy()

    repl = {
        "bil": np.tile([0.0, 0.0, 1.0], (len(dts), 1)),
        "qqq": np.tile([1.0, 0.0, 0.0], (len(dts), 1)),
        "half": np.tile([0.0, 0.5, 0.5], (len(dts), 1)),
        "third": np.tile([0.5, 0.0, 0.5], (len(dts), 1)),
    }

    rows = []
    print(f"\n{'label':7s} {'q':>4s} {'mode':5s}  " +
          "  ".join(f"{k:>18s}" for k in STARTS))
    for yname, y in labels.items():
        p = walk_forward(dts, x, y, 1)
        rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()
        base_rate = np.nanmean(y[dts >= pd.Timestamp("2017-01-03")])
        corr = np.corrcoef(p[np.isfinite(p) & np.isfinite(y)],
                           y[np.isfinite(p) & np.isfinite(y)])[0, 1]
        for q in (0.80, 0.90, 0.95):
            # p[t] predicts session t+1, so the tradable flag for day t is rank[t-1].
            raw = np.isfinite(rank) & (rank >= q)
            flag = np.r_[False, raw[:-1]]
            for mode, rw in repl.items():
                eq, sk = sim_override(dp, base_eq, w_win, flag, rw, opened)
                parts = []
                for lab, st in STARTS.items():
                    j = dts.searchsorted(pd.Timestamp(st)) - sk
                    ss = daily_stats(eq[j:] / eq[j] * 100000, dts[j + sk:])
                    parts.append(f"{ss['cagr']*100:5.1f}/{ss['max_drawdown']*100:5.1f}/{ss['sharpe']:.2f}")
                rows.append((yname, q, mode, parts))
        print(f"{yname:7s} base {base_rate:4.2f} corr {corr: .3f}")
        for row in rows[-12:]:
            print(f"  {row[0]:7s} {row[1]:4.2f} {row[2]:5s}  " + "  ".join(row[3]))
    pd.to_pickle(rows, Path(__file__).parent / "screen_rows.pkl")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
