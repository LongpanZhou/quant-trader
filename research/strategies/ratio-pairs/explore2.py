"""Dev-only exploration 2: QQQ base + froth de-risk, with a cheap-leverage kicker.

PRE-PAUSE SCRATCH — DO NOT RUN.  Backtests were paused on 2026-11-26; the
numbers in explore2.log were produced before the pause and are unaudited.
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
BARS = 252 * 390


def load():
    return bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=420)


def sessions(ts):
    dates = np.asarray(ts.date)
    ch = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    return dates, np.concatenate(([0], ch)), np.concatenate((ch - 1, [len(ts) - 1]))


def daily(ts, cl, starts, ends):
    d = pd.DataFrame({
        "qqq_c": cl[ends, 0], "tqqq_c": cl[ends, 1], "bil_c": cl[ends, 2],
    }, index=pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize())
    d["ratio"] = d["tqqq_c"] / d["qqq_c"]
    d["logr"] = np.log(d["ratio"])
    for n in (60, 120, 150, 200, 250):
        d[f"ext{n}"] = d["logr"] - d["logr"].rolling(n).mean()
    d["m20"] = d["ratio"].rolling(20).mean()
    return d


def broadcast(ts, starts, ends, day_w):
    w = np.zeros((len(ts), 3))
    for k, (a, b) in enumerate(zip(starts, ends)):
        w[a:b + 1] = day_w[k]
    return w


def dr(res):
    eq = pd.Series(res["equity"], index=res["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def main():
    ts, op, cl = load()
    dates, starts, ends = sessions(ts)
    d = daily(ts, cl, starts, ends)
    nd = len(d)
    idx = d.index
    dev = (idx >= pd.Timestamp(DEV_START)) & (idx <= pd.Timestamp(DEV_END))

    ext = d["ext200"].shift(1).to_numpy()
    x = np.nan_to_num(ext, nan=0.0)

    qqq_dc = d["qqq_c"]
    reg = (qqq_dc.shift(1) > qqq_dc.rolling(165).mean().shift(1)).fillna(False).to_numpy()

    def base_w():
        w = np.zeros((nd, 3))
        w[reg, 1] = 1
        w[~reg, 2] = 1
        return w

    def bh(k):
        w = np.zeros((nd, 3))
        w[dev, k] = 1
        return w

    rules = {"baseline165": base_w(), "QQQ_BH": bh(0), "TQQQ_BH": bh(1), "BIL": bh(2)}

    # froth de-risk, QQQ base, with partial cash
    for hi in (0.14, 0.16, 0.18, 0.20, 0.22, 0.25):
        for frac in (1.0, 0.5):
            w = np.zeros((nd, 3))
            fr = x > hi
            w[~fr, 0] = 1
            w[fr, 0] = 1 - frac
            w[fr, 2] = frac
            rules[f"QQQ; ext>{hi:.2f}->cash{frac:.1f}"] = w

    # cheap kicker: in cheap zone, move a slice of QQQ into TQQQ
    for hi in (0.18, 0.20):
        for lo in (-0.20, -0.30):
            for kick in (0.25, 0.50):
                w = np.zeros((nd, 3))
                fr = x > hi
                cheap = x < lo
                w[~fr, 0] = 1
                w[~fr & cheap, 0] = 1 - kick
                w[~fr & cheap, 1] = kick
                w[fr, 2] = 1
                rules[f"QQQ; froth{hi:.2f}->cash; cheap{lo:.2f} kick{kick:.2f}"] = w

    # TQQQ selective by state bands
    bands = {
        "TQQQ<0.15 or <-0.3": (x < 0.15) | (x < -0.30),
        "TQQQ<0.15": x < 0.15,
        "TQQQ<0.10": x < 0.10,
        "TQQQ in(0,0.15) or <-0.3": ((x > 0) & (x < 0.15)) | (x < -0.30),
    }
    for name, on in bands.items():
        w = np.zeros((nd, 3))
        w[on, 1] = 1
        w[~on, 2] = 1
        rules[name] = w

    names = list(rules)
    mats = [broadcast(ts, starts, ends, rules[n]) for n in names]
    many = bt.run_many(ts, op, cl, mats, start=DEV_START, band=0.02, slippage_bps=1.0)
    bdr = dr(many[0])
    print(f"{'rule':48s} {'CAGR':>7s} {'DD':>6s} {'Sharpe':>6s} {'inv':>5s} {'fills':>5s} {'corr':>5s}")
    for n, m, r in zip(names, mats, many):
        s = bt.stats(r, BARS)
        corr = float(dr(r).corr(bdr))
        inv = float(m.sum(axis=1).mean())
        print(f"{n:48s} {s['cagr']*100:6.2f}% {s['max_drawdown']*100:5.2f}% "
              f"{s['sharpe']:6.2f} {inv:5.2f} {s['fills']:5d} {corr:5.2f}")

    # yearly for the leading QQQ/froth rules
    print("\nyearly returns")
    show = [n for n in names if n.startswith("QQQ; ext>0.18") or n in ("QQQ_BH", "baseline165")]
    for n in show:
        r = many[names.index(n)]
        y = bt.yearly(r["ts"], r["equity"], cl[bt.start_index(ts, DEV_START):, 0])
        print(f"{n:32s} " + " ".join(f"{k}:{v['strategy']*100:6.1f}" for k, v in y.items()))

    # placebo: same number of froth days per year, random placement, 300 draws
    print("\nplacebo: QQQ with random cash days, same count per year (300 draws)")
    rng = np.random.default_rng(11)
    years = idx.year.to_numpy()
    base = np.zeros((nd, 3)); base[dev, 0] = 1
    fr = x > 0.18
    cs = []
    for _ in range(300):
        g = np.zeros(nd, bool)
        for y in np.unique(years):
            m = (years == y) & dev
            k = int((fr & (years == y) & dev).sum())
            if k:
                g[rng.choice(np.flatnonzero(m), size=k, replace=False)] = True
        w = np.zeros((nd, 3)); w[~g, 0] = 1; w[g, 2] = 1
        r = bt.simulate(ts[bt.start_index(ts, DEV_START):], op[bt.start_index(ts, DEV_START):],
                        cl[bt.start_index(ts, DEV_START):],
                        broadcast(ts, starts, ends, w)[bt.start_index(ts, DEV_START):],
                        band=0.02, slippage_bps=1.0)
        cs.append(bt.stats(r, BARS)["cagr"])
    real = bt.stats(many[names.index("QQQ; ext>0.18->cash1.0")], BARS)["cagr"]
    cs = np.array(cs)
    print(f"  real {real*100:.2f}%  random p50 {np.median(cs)*100:.2f}%  "
          f"p95 {np.percentile(cs,95)*100:.2f}%  share>=real {(cs>=real).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
