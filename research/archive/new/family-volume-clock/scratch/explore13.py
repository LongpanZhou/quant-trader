"""Thirteenth pass: BIL headline, alpha/beta, quick placebos."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
CQ, CT, CB = 0, 1, 2


def load_all():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)
    return ts, o, c, vol


def prep(ts, o, c, vol):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    V = np.zeros((n, 390))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        V[k, :m] = vol[f:f + m]
    return dates, np.asarray(first), np.asarray(last), V


def accel_series(V, n, j=210, win=30, look=20):
    a = np.full(n, np.nan)
    w0 = j - win + 1
    for k in range(look, n):
        hist = [V[kk, w0:j + 1].sum() for kk in range(k - look, k)]
        med = np.median(hist)
        if med > 0:
            a[k] = V[k, w0:j + 1].sum() / med
    return a


def build(ts, first, last, a, enter=0.75, exit_=0.85, j=210, flat="BIL"):
    n = len(first)
    w = np.zeros((len(ts), 3))
    state = 0
    for k in range(n - 1):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if j >= m - 1 or not np.isfinite(a[k]):
            state = 0
            continue
        if state == 0 and a[k] < enter:
            state = 1
        elif state == 1 and a[k] > exit_:
            state = 0
        if state:
            fk, lk = int(first[k]), int(last[k])
            w[fk + j, CT] = 1.0
            w[fk + j + 1:lk + 1, CT] = 1.0
            w[lk, CT] = 0.0
    w[-1] = w[-2]
    if flat == "BIL":
        w[:, CB] = 1.0 - w[:, CT]
    return w


def ev(ts, o, c, w, slip=1.0):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
    return bt.stats(r, BPY), r


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V = prep(ts, o, c, vol)
    n = len(first)
    a = accel_series(V, n)
    for flat in ("BIL", "cash"):
        w = build(ts, first, last, a, flat=flat)
        print(f"\nflat={flat}")
        for slip in (1.0, 5.0, 10.0):
            s, r = ev(ts, o, c, w, slip)
            print(f"  {slip:.0f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sh {s['sharpe']:.3f} Sortino {s['sortino']:.3f} vol {s['volatility']*100:.2f}% "
                  f"expo {s['exposure']*100:.1f}% fills {s['fills']} TO {s['turnover']:.0f} "
                  f"end ${s['ending_equity']:,.0f}")
            if flat == "BIL" and slip == 1.0:
                r1 = r
        if flat == "BIL":
            wb = w

    # alpha/beta vs TQQQ daily
    eq = pd.Series(r1["equity"], index=pd.to_datetime(r1["ts"]))
    sr = eq.groupby(eq.index.normalize()).last().pct_change().dropna()
    tq = pd.Series(c[:, CT], index=pd.to_datetime(ts))
    tr = tq.groupby(tq.index.normalize()).last().pct_change().dropna()
    j = sr.index.intersection(tr.index)
    sr, tr = sr.loc[j], tr.loc[j]
    beta = np.cov(sr, tr, ddof=1)[0, 1] / np.var(tr, ddof=1)
    alpha = sr.mean() - beta * tr.mean()
    resid = sr - alpha - beta * tr
    se = np.sqrt(np.sum(resid**2) / (len(sr) - 2) / np.sum((tr - tr.mean())**2))
    t_alpha = alpha / (np.std(resid, ddof=2) / np.sqrt(len(sr)))
    print(f"\nalpha/beta vs TQQQ daily: beta {beta:.3f} alpha {alpha*1e4:.2f}bp/day "
          f"({alpha*252*100:.1f}%/yr) t_alpha {t_alpha:.2f} corr {sr.corr(tr):.3f}")

    # quick circular shift placebo
    print("\ncircular-shift placebo (100 shifts)...")
    rng = np.random.default_rng(2026)
    real_cagr = 0.0
    s0, _ = ev(ts, o, c, wb, 1.0)
    real_cagr = s0["cagr"]; real_sh = s0["sharpe"]; real_dd = s0["max_drawdown"]
    cagrs, shs, dds = [], [], []
    for L in rng.integers(1, 500, 100):
        ash = np.r_[np.full(int(L), np.nan), a[:-int(L)]]
        w = build(ts, first, last, ash)
        s, _ = ev(ts, o, c, w, 1.0)
        cagrs.append(s["cagr"]); shs.append(s["sharpe"]); dds.append(s["max_drawdown"])
    cagrs = np.array(cagrs); shs = np.array(shs); dds = np.array(dds)
    print(f"real CAGR {real_cagr*100:.2f}% Sh {real_sh:.2f} DD {real_dd*100:.1f}%")
    print(f"shift CAGR mean {cagrs.mean()*100:6.2f}% p95 {np.percentile(cagrs,95)*100:6.2f}% "
          f"max {cagrs.max()*100:6.2f}% p={np.mean(cagrs>=real_cagr):.3f}")
    print(f"shift Sh mean {shs.mean():.2f} p95 {np.percentile(shs,95):.2f} "
          f"p={np.mean(shs>=real_sh):.3f}")

    # random-night placebo
    print("\nrandom-night placebo (100 draws)...")
    n_nights = int(np.sum((wb[:, CT] > 0)[first]))  # rough count of first bars with position
    # count entries = transitions from flat to long at the decision bar
    entries = 0
    prev = 0
    for k in range(n):
        fk = int(first[k])
        cur = 1 if wb[fk + min(210, int(last[k]) - fk), CT] > 0 else 0
        if cur and not prev:
            entries += 1
        prev = cur
    print(f"entries {entries}")
    cagrs2, shs2, dds2 = [], [], []
    for _ in range(100):
        pick = rng.choice(n, size=entries, replace=False)
        w = np.zeros((len(ts), 3))
        mask = np.zeros(n, bool); mask[pick] = True
        for k in range(n - 1):
            if not mask[k]:
                continue
            fk, lk = int(first[k]), int(last[k])
            w[fk + 210, CT] = 1.0
            w[fk + 211:lk + 1, CT] = 1.0
            w[lk, CT] = 0.0
        w[-1] = w[-2]
        w[:, CB] = 1.0 - w[:, CT]
        s, _ = ev(ts, o, c, w, 1.0)
        cagrs2.append(s["cagr"]); shs2.append(s["sharpe"]); dds2.append(s["max_drawdown"])
    cagrs2 = np.array(cagrs2); shs2 = np.array(shs2); dds2 = np.array(dds2)
    print(f"random-night CAGR mean {cagrs2.mean()*100:6.2f}% p95 {np.percentile(cagrs2,95)*100:6.2f}% "
          f"max {cagrs2.max()*100:6.2f}% p={np.mean(cagrs2>=real_cagr):.3f}")
    print(f"random-night Sh mean {shs2.mean():.2f} p95 {np.percentile(shs2,95):.2f} "
          f"p={np.mean(shs2>=real_sh):.3f}")

    # stale signal
    print("\nstale signal:")
    astale = np.r_[np.nan, a[:-1]]
    wst = build(ts, first, last, astale)
    sst, _ = ev(ts, o, c, wst, 1.0)
    print(f"  prior-day accel: CAGR {sst['cagr']*100:.2f}% DD {sst['max_drawdown']*100:.1f}% "
          f"Sh {sst['sharpe']:.2f} fills {sst['fills']}")


if __name__ == "__main__":
    main()
