"""Dev-only exploration for the ratio-pairs rebuild.

PRE-PAUSE SCRATCH — DO NOT RUN.  Backtests were paused on 2026-11-26; the
numbers in explore.log were produced before the pause and are unaudited.

No QQQ/TQQQ/SPY/NDX moving-average gate.  The only state variable is the
TQQQ/QQQ ratio's own extension and its short-term change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BARS = 252 * 390
HERE = Path(__file__).resolve().parent


def load():
    ts, op, cl = bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=420)
    return ts, op, cl


def sessions(ts):
    dates = np.asarray(ts.date)
    ch = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    starts = np.concatenate(([0], ch))
    ends = np.concatenate((ch - 1, [len(ts) - 1]))
    return dates, starts, ends


def daily(ts, cl, starts, ends):
    d = pd.DataFrame({
        "qqq_c": cl[ends, 0], "tqqq_c": cl[ends, 1], "bil_c": cl[ends, 2],
        "qqq_o": cl[starts, 0],
    }, index=pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize())
    d["ratio"] = d["tqqq_c"] / d["qqq_c"]
    d["logr"] = np.log(d["ratio"])
    for n in (60, 120, 200):
        d[f"ext{n}"] = d["logr"] - d["logr"].rolling(n).mean()
    d["dd252"] = d["ratio"] / d["ratio"].rolling(252).max() - 1.0
    d["r20"] = d["logr"].diff(20)
    d["r5"] = d["logr"].diff(5)
    return d


def broadcast(ts, starts, ends, day_w):
    n = len(ts)
    w = np.zeros((n, 3))
    for k, (a, b) in enumerate(zip(starts, ends)):
        w[a:b + 1] = day_w[k]
    return w


def to_daily_returns(res):
    eq = pd.Series(res["equity"], index=res["ts"])
    d = eq.groupby(eq.index.date).last()
    return d.pct_change().dropna()


def main():
    ts, op, cl = load()
    dates, starts, ends = sessions(ts)
    d = daily(ts, cl, starts, ends)
    nd = len(d)
    print(f"panel {len(ts):,} bars, {nd} sessions, {ts[0]} .. {ts[-1]}")

    # per-session arrays aligned to sessions (d is built from ends, same order)
    day_ret_tq = np.r_[np.nan, d["tqqq_c"].to_numpy()[1:] / d["tqqq_c"].to_numpy()[:-1] - 1]
    day_ret_qq = np.r_[np.nan, d["qqq_c"].to_numpy()[1:] / d["qqq_c"].to_numpy()[:-1] - 1]

    ext = d["ext200"].shift(1).to_numpy()
    ext60 = d["ext60"].shift(1).to_numpy()
    r20 = d["r20"].shift(1).to_numpy()
    r5 = d["r5"].shift(1).to_numpy()
    dev_mask = (d.index >= pd.Timestamp(DEV_START)) & (d.index <= pd.Timestamp(DEV_END))

    print("\next200 prior-close distribution (dev)")
    e = ext[dev_mask]
    print(pd.Series(e).describe(percentiles=[.05, .1, .25, .5, .75, .9, .95]).to_string())
    print("share > 0.18 %.3f   share < -0.20 %.3f   share < -0.30 %.3f"
          % (np.nanmean(e > 0.18), np.nanmean(e < -0.20), np.nanmean(e < -0.30)))

    print("\nforward 20d TQQQ by ext200 bucket (dev)")
    f20 = np.r_[d["tqqq_c"].to_numpy()[20:] / d["tqqq_c"].to_numpy()[:-20] - 1, np.full(20, np.nan)]
    b = pd.cut(pd.Series(ext[dev_mask]), [-9, -0.3, -0.15, 0, 0.15, 0.25, 9])
    t = pd.DataFrame({"b": b, "f20": f20[dev_mask]}).dropna()
    print(t.groupby("b", observed=True)["f20"].agg(["size", "mean", "median",
                                                     lambda v: float((v > 0).mean())]).to_string())

    # ---------------- rules ----------------
    base = np.zeros((nd, 3))
    qqq_dc = d["qqq_c"]
    sma165 = qqq_dc.rolling(165).mean()
    reg = (qqq_dc.shift(1) > sma165.shift(1)).fillna(False).to_numpy()
    base[reg, 1] = 1.0
    base[~reg, 2] = 1.0
    wb = broadcast(ts, starts, ends, base)
    rb = bt.run(ts, op, cl, wb, DEV_START, band=0.02, slippage_bps=1.0)
    sb = bt.stats(rb, BARS)
    bdr = to_daily_returns(rb)
    print(f"\n165d baseline dev: CAGR {sb['cagr']*100:.2f}%  DD {sb['max_drawdown']*100:.2f}%  "
          f"Sharpe {sb['sharpe']:.2f}  exp {sb['exposure']*100:.1f}%")

    rules = {}

    # froth-avoid with a QQQ base
    for hi in (0.12, 0.18, 0.25):
        w = np.zeros((nd, 3))
        ok = np.nan_to_num(ext, nan=-9) <= hi
        w[ok, 0] = 1.0
        w[~ok, 2] = 1.0
        rules[f"QQQ base, ext>{hi:.2f}->BIL"] = w

    # contrarian 3-state
    for hi, lo in ((0.18, -0.25), (0.18, -0.15), (0.25, -0.20), (0.12, -0.20)):
        w = np.zeros((nd, 3))
        x = np.nan_to_num(ext, nan=0.0)
        w[x <= lo, 1] = 1.0
        w[(x > lo) & (x <= hi), 0] = 1.0
        w[x > hi, 2] = 1.0
        rules[f"3state hi{hi:.2f} lo{lo:.2f} TQQQ/QQQ/BIL"] = w

    # continuous fade: TQQQ weight 1 at lo, 0 at hi; rest BIL
    for hi, lo in ((0.18, -0.25), (0.18, 0.0), (0.25, -0.20)):
        x = np.nan_to_num(ext, nan=hi)
        f = np.clip((hi - x) / (hi - lo), 0, 1)
        w = np.zeros((nd, 3))
        w[:, 1] = f
        w[:, 2] = 1 - f
        rules[f"fade hi{hi:.2f} lo{lo:.2f} TQQQ/BIL"] = w

    # cheap and rising
    for lo, k in ((-0.20, 5), (-0.25, 5), (-0.20, 10), (-0.10, 5)):
        x = np.nan_to_num(ext, nan=0.0)
        up = np.nan_to_num(ext - (d["ext200"].shift(1 + k).to_numpy()), nan=0.0) > 0
        on = (x < lo) & up
        w = np.zeros((nd, 3))
        w[on, 1] = 1.0
        w[~on, 2] = 1.0
        rules[f"cheap<{lo:.2f} & rising{k} TQQQ/BIL"] = w

    # QQQ when not froth, TQQQ when cheap and rising
    for hi, lo, k in ((0.18, -0.20, 5), (0.20, -0.15, 5), (0.18, -0.10, 5)):
        x = np.nan_to_num(ext, nan=0.0)
        up = np.nan_to_num(ext - (d["ext200"].shift(1 + k).to_numpy()), nan=0.0) > 0
        w = np.zeros((nd, 3))
        w[:, 0] = 1.0
        w[(x >= lo) & (x <= hi), 1] = 0.0
        w[(x >= lo) & (x <= hi), 0] = 1.0
        w[x < lo, 1] = 1.0
        w[x < lo, 0] = 0.0
        w[x > hi, 1] = 0.0
        w[x > hi, 0] = 0.0
        w[x > hi, 2] = 1.0
        if k:
            # only allow TQQQ when rising; otherwise QQQ
            w[x < lo, 0] = (~up[x < lo]).astype(float)
            w[x < lo, 1] = up[x < lo].astype(float)
        rules[f"QQQ base / TQQQ cheap<{lo:.2f} rising{k} / BIL froth>{hi:.2f}"] = w

    names = list(rules)
    mats = [broadcast(ts, starts, ends, rules[n]) for n in names]
    many = bt.run_many(ts, op, cl, mats, start=DEV_START, band=0.02, slippage_bps=1.0)
    print("\nrules (dev, 1bp):")
    print(f"{'rule':58s} {'CAGR':>7s} {'DD':>6s} {'Sharpe':>6s} {'exp':>5s} {'fills':>5s} {'corr':>5s}")
    for n, m, r in zip(names, mats, many):
        s = bt.stats(r, BARS)
        corr = float(to_daily_returns(r).corr(bdr))
        exp = float(m.mean())
        print(f"{n:58s} {s['cagr']*100:6.2f}% {s['max_drawdown']*100:5.2f}% "
              f"{s['sharpe']:6.2f} {exp:5.2f} {s['fills']:5d} {corr:5.2f}")


if __name__ == "__main__":
    main()
