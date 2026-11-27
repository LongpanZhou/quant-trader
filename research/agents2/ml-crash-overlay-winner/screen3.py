"""Screen 3: trend-confirmed and graduated crash overlays (fast daily sim)."""
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
from proto import walk_forward  # noqa: E402
from screen import DailyPath, sim_override, daily_stats  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}
FEATS = ["rv1", "rv5", "rv20", "rv60", "rv_ratio", "rv_pct", "skew1", "skew20",
         "dvol", "dvol20", "vwap_dist", "dd_high", "first30", "last30", "close_loc",
         "gap", "gap20", "intraday", "up20", "dd20", "dd252", "sma20", "sma165",
         "rsi14", "decay5", "decay20", "bil5", "dow", "range", "range20",
         "vol_ratio", "vol_z20", "rv_x_trend", "skew_x_dd"]


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w_win, opened, stopped, last, first = winner_daily(ts, o, c)
    dp = DailyPath(ts, o, c)
    dts = dp.dts
    r = bt.run(ts, o, c, w_win, START, band=0.02, slippage_bps=1.0)
    i0 = bt.start_index(ts, START)
    eq1m = pd.Series(r["equity"], index=ts[i0:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dts).to_numpy()
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    f = f.reindex(dts).ffill()
    x = f[FEATS].to_numpy()
    t = pd.Series(dp.dc[:, 1], index=dts)

    ft = t.shift(-20) / t - 1.0
    y = (ft < -0.15).astype(float)
    y[~np.isfinite(ft)] = np.nan
    p = walk_forward(dts, x, y, 20)
    rank = pd.Series(p).rolling(252, min_periods=60).rank(pct=True).to_numpy()

    def eval_weights(rw, over):
        eq, sk = sim_override(dp, base_eq, w_win, over, rw, opened)
        out = []
        for lab, st in STARTS.items():
            j = dts.searchsorted(pd.Timestamp(st)) - sk
            ss = daily_stats(eq[j:] / eq[j] * 100000, dts[j + sk:])
            out += [ss["cagr"], ss["max_drawdown"], ss["sharpe"]]
        return out

    def fmt(v):
        return (f"{v[0]*100:5.1f}/{v[1]*100:5.1f}/{v[2]:.2f}  "
                f"{v[3]*100:5.1f}/{v[4]*100:5.1f}/{v[5]:.2f}")

    print("winner:", fmt(eval_weights(np.tile([0., 0., 1.], (len(dts), 1)),
                                     np.zeros(len(dts), bool))))
    print(f"{'variant':44s}   10y CAGR/DD/Sh   5y CAGR/DD/Sh")

    # simple BIL with trend filters
    for name, filt in (("no filter", np.ones(len(dts), bool)),
                       ("QQQ<SMA20", (f["sma20"] < 0).to_numpy()),
                       ("QQQ<SMA50", (f["sma20"] < -0.02).to_numpy()),
                       ("QQQ<SMA20*1.02", (f["sma20"] < 0.02).to_numpy())):
        for q in (0.90, 0.95):
            raw = np.isfinite(rank) & (rank >= q) & filt
            over = np.r_[False, raw[:-1]]
            v = eval_weights(np.tile([0., 0., 1.], (len(dts), 1)), over)
            print(f"BIL q{q:.2f} {name:24s} " + fmt(v))

    # graduated: BIL above q_hi, QQQ between q_lo and q_hi
    for q_lo, q_hi in ((0.80, 0.95), (0.85, 0.95), (0.90, 0.95), (0.80, 0.90), (0.90, 0.97)):
        rw = np.tile([0., 1., 0.], (len(dts), 1)).astype(float)
        raw_hi = np.r_[False, (np.isfinite(rank) & (rank >= q_hi))[:-1]]
        raw_lo = np.r_[False, (np.isfinite(rank) & (rank >= q_lo) & (rank < q_hi))[:-1]]
        rw[raw_lo] = [1.0, 0.0, 0.0]   # QQQ
        rw[raw_hi] = [0.0, 0.0, 1.0]   # BIL
        over = raw_lo | raw_hi
        v = eval_weights(rw, over)
        print(f"grad BIL>={q_hi:.2f} QQQ>={q_lo:.2f}          " + fmt(v))

    # continuous: TQQQ weight = 1 in top? use rank-based throttle to BIL
    for q_lo, q_hi in ((0.80, 0.99), (0.85, 0.99), (0.90, 0.995)):
        w_t = np.clip((q_hi - rank) / (q_hi - q_lo), 0, 1)
        w_t = np.where(np.isfinite(rank), w_t, 1.0)
        rw = np.zeros((len(dts), 3))
        rw[:, 1] = w_t
        rw[:, 2] = 1 - w_t
        over = w_t < 0.999
        over = np.r_[False, over[:-1]]
        # rw must be lagged too: weight for day d comes from rank at d-1
        rw = np.vstack([rw[:1], rw[:-1]])
        v = eval_weights(rw, over)
        print(f"throttle {q_lo:.2f}-{q_hi:.3f}              " + fmt(v))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
