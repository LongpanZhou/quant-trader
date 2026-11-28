"""Dev-only evaluation of standalone capitulation -> next-session re-entry variants.

Everything here runs on 2016-01-04 .. 2023-12-29 only. The holdout is never loaded.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2016-01-04", "2023-12-29"
BARS = 252 * 390


def sessions(ts):
    d = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, d[1:] != d[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    return d, first, last


def day_features(ts, o, c):
    d, first, last = sessions(ts)
    nd = len(first)
    qqq, tqqq = c[:, 0], c[:, 1]
    prev = np.full(nd, np.nan)
    prev[1:] = np.array([qqq[last[k]] for k in range(nd - 1)])
    # min 1m close drawdown vs prior close, and first crossing index
    ddown = np.full(len(ts), np.nan)
    for k in range(nd):
        a, b = first[k], last[k] + 1
        ddown[a:b] = qqq[a:b] / prev[k] - 1.0
    dmin = np.array([np.nanmin(ddown[first[k]:last[k] + 1]) for k in range(nd)])
    dfirst_cross = np.full(nd, -1)
    for k in range(nd):
        a, b = first[k], last[k] + 1
        seg = ddown[a:b]
        idx = np.flatnonzero(seg <= -0.03)
        if len(idx):
            dfirst_cross[k] = a + int(idx[0])
    return dict(d=d, first=first, last=last, nd=nd, qqq=qqq, tqqq=tqqq,
                prev=prev, ddown=ddown, dmin=dmin, dclose=np.array([ddown[last[k]] for k in range(nd)]),
                dfirst_cross=dfirst_cross)


def make_weights(F, thresh=0.03, hold=1, asset=1, stop=None, mask=None):
    """Per-session targets: long `asset` for `hold` sessions after an event session."""
    nd, first, last = F["nd"], F["first"], F["last"]
    n = len(F["d"])
    ev = F["dmin"] <= -thresh
    if mask is not None:
        ev = ev & mask
    target = np.zeros(nd)
    for k in np.flatnonzero(ev):
        for h in range(1, hold + 1):
            if k + h < nd:
                target[k + h] = 1.0

    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    for k in range(nd):
        a, b = first[k], last[k]
        nxt = target[k + 1] if k + 1 < nd else 0.0
        w[a:b - 1, asset] = target[k]
        # exit at the 15:59 open: set the second-to-last bar to the next target
        if b - 1 >= a:
            w[b - 1, asset] = 0.0 if (target[k] > 0 and nxt == 0) else target[k]
        w[b, asset] = nxt
    for k in range(nd):
        a, b = first[k], last[k]
        w[a:b + 1, 2] = 1.0 - w[a:b + 1, asset]
    # intraday stop on a held session: exit and stay out for the session
    if stop is not None:
        for k in range(nd):
            if target[k] <= 0:
                continue
            a, b = first[k], last[k]
            seg = F["ddown"][a:b + 1]
            idx = np.flatnonzero(seg <= -stop)
            if len(idx):
                j = a + int(idx[0])
                w[j:b, asset] = 0.0
                w[j:b, 2] = 1.0
    w[-1] = (0.0, 0.0, 1.0)
    # cleanup: weights sum to 1 exactly
    w[:, 2] = np.clip(1.0 - w[:, 0] - w[:, 1], 0.0, 1.0)
    return w, int(ev.sum())


def daily_returns(res):
    eq = pd.Series(res["equity"], index=pd.DatetimeIndex(res["ts"]))
    e = eq.groupby(eq.index.date).last()
    return e.pct_change().dropna()


def baseline_weights(ts, o, c, nd_sessions):
    """The old 165-day baseline, for correlation only (not used by the strategy)."""
    d, first, last = sessions(ts)
    nd = len(first)
    qclose = np.array([c[last[k], 0] for k in range(nd)])
    s = pd.Series(qclose)
    sma = s.rolling(165).mean()
    reg = (s > sma).astype(float).fillna(0.0).to_numpy()
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for k in range(nd):
        a, b = first[k], last[k]
        r = reg[k - 1] if k > 0 else 0.0
        w[a:b + 1, 1] = r
        w[a:b + 1, 2] = 1.0 - r
    w[-1] = (0.0, 0.0, 1.0)
    return w


def show(label, ts, o, c, w):
    out = {}
    for slip in (1.0, 5.0, 10.0):
        res = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=slip)
        s = bt.stats(res, BARS)
        out[slip] = s
        if slip == 1.0:
            print(f"  {label:28s} 1bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:4d} turn {s['turnover']:6.0f}x")
        else:
            print(f"  {'':28s}{slip:4.0f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}%")
    return out


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    F = day_features(ts, o, c)
    print("bars", len(ts), "sessions", F["nd"], ts[0], ts[-1])
    print("unconditional next-session TQQQ open->close: %.4f%%" % (
        np.nanmean([c[F['last'][k + 1], 1] / o[F['first'][k + 1], 1] - 1 for k in range(F['nd'] - 1)]) * 100))

    base = baseline_weights(ts, o, c, F["nd"])
    rb = bt.run(ts, o, c, base, START, band=0.02, slippage_bps=1.0)
    sb = bt.stats(rb, BARS)
    print("baseline dev: CAGR %.2f%% DD %.2f%% Sharpe %.2f" % (sb['cagr']*100, sb['max_drawdown']*100, sb['sharpe']))
    base_r = daily_returns(rb)

    variants = [
        ("V1 X3 hold1 TQQQ", dict(thresh=0.03, hold=1)),
        ("V2 X3 hold2 TQQQ", dict(thresh=0.03, hold=2)),
        ("V3 X3 hold3 TQQQ", dict(thresh=0.03, hold=3)),
        ("V4 X2.5 hold1", dict(thresh=0.025, hold=1)),
        ("V5 X3.5 hold1", dict(thresh=0.035, hold=1)),
        ("V6 X3 hold1 QQQ", dict(thresh=0.03, hold=1, asset=0)),
        ("V7 X3 hold1 stop3", dict(thresh=0.03, hold=1, stop=0.03)),
        ("V8 X3 hold2 stop3", dict(thresh=0.03, hold=2, stop=0.03)),
        ("V9 X4 hold1", dict(thresh=0.04, hold=1)),
    ]
    corrs = {}
    for name, p in variants:
        w, nev = make_weights(F, **p)
        show(f"{name} n={nev}", ts, o, c, w)
        r = daily_returns(bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0))
        j = r.index.intersection(base_r.index)
        corrs[name] = float(np.corrcoef(r.loc[j], base_r.loc[j])[0, 1])
        print(f"  {'':28s}corr vs 165d baseline {corrs[name]:+.3f}")

    print("\ncorrelations:", {k: round(v, 3) for k, v in corrs.items()})


if __name__ == "__main__":
    main()
