"""Robustness: placebo, ex-year, 5y-to-2025, AUC/decile, rolling comparison."""
from __future__ import annotations

import json
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
from validate import build  # noqa: E402
from screen import DailyPath, sim_override, daily_stats  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390


def daily_eq(r, ts):
    eq = pd.Series(r["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def cagr_dd(d):
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    cagr = (d.iloc[-1] / d.iloc[0]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(d)
    return float(cagr), float(-(d / peak - 1).min())


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w0, op0, st0, la0, fi0 = winner_daily(ts, o, c)
    w, flag, opened, dts, f, p, rank = build(ts, o, c, 20, -0.15, 0.90, "bil")
    dp = DailyPath(ts, o, c)
    i10 = bt.start_index(ts, "2017-01-03")
    i5 = bt.start_index(ts, "2021-10-25")

    r0 = bt.run(ts, o, c, w0, "2017-01-03", band=0.02, slippage_bps=1.0)
    r1 = bt.run(ts, o, c, w, "2017-01-03", band=0.02, slippage_bps=1.0)
    d0 = daily_eq(r0, ts[i10:])
    d1 = daily_eq(r1, ts[i10:])

    print("ex-year CAGRs (10y, daily marks; year's returns set to zero):")
    for drop in (None, 2020, 2021, 2022, 2023, 2024, 2025, 2026):
        row = []
        for nm, d in (("overlay", d1), ("winner", d0)):
            rets = d.pct_change().fillna(0.0)
            if drop:
                rets = rets.copy()
                rets[rets.index.year == drop] = 0.0
            eq = (1 + rets).cumprod()
            n_days = int((rets.index.year != drop).sum()) if drop else len(rets)
            yrs = n_days / 252.0
            cagr = eq.iloc[-1] ** (1 / yrs) - 1
            peak = np.maximum.accumulate(eq)
            dd = float(-(eq / peak - 1).min())
            row.append((cagr, dd))
        print(f"  drop {drop}: overlay {row[0][0]*100:5.1f}%/{row[0][1]*100:4.1f}%   "
              f"winner {row[1][0]*100:5.1f}%/{row[1][1]*100:4.1f}%")

    print("\n5y window 2021-10-25..2025-12-31 (no 2026):")
    for nm, d in (("overlay", d1), ("winner", d0)):
        seg = d[(d.index >= pd.Timestamp("2021-10-25")) & (d.index <= pd.Timestamp("2025-12-31"))]
        rets = seg.pct_change().fillna(0.0)
        eq = (1 + rets).cumprod()
        yrs = len(seg) / 252.0
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eq)
        dd = float(-(eq / peak - 1).min())
        print(f"  {nm}: CAGR {cagr*100:5.2f}% DD {dd*100:5.2f}%")

    print("\n5y ending 2026-10-23:")
    for nm, d in (("overlay", d1), ("winner", d0)):
        seg = d[d.index >= pd.Timestamp("2021-10-25")]
        a = cagr_dd(seg)
        print(f"  {nm}: CAGR {a[0]*100:5.2f}% DD {a[1]*100:5.2f}%")

    # AUC / decile (20-day crash label, OOS p)
    print("\nOOS diagnostics for the 20-day crash model:")
    tq = pd.Series(dp.dc[:, 1], index=dts)
    fut = (tq.shift(-20) / tq - 1.0)
    y20 = (fut.to_numpy() < -0.15).astype(float)
    ok = np.isfinite(p) & np.isfinite(fut.to_numpy()) & np.isfinite(rank) & (dts >= pd.Timestamp("2017-01-03"))
    print(f"  usable rows: {int(ok.sum())}")
    y20 = (fut.to_numpy() < -0.15).astype(float)
    for y in range(2017, 2027):
        m = ok & (dts.year == y)
        if m.sum() < 40:
            continue
        # rank AUC via Mann-Whitney
        pp = p[m]; yy = y20[m]
        pos = pp[yy == 1]; neg = pp[yy == 0]
        if len(pos) and len(neg):
            auc = (np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg))
        else:
            auc = np.nan
        print(f"  {y}: n={m.sum():4d} base={yy.mean():.2f} AUC={auc:.3f}")
    m = ok
    qs = np.quantile(rank[m], np.linspace(0, 1, 11)); qs[0] -= 1e-12
    idx = np.clip(np.searchsorted(qs, rank[m], side="right") - 1, 0, 9)
    print("  rank decile -> crash rate / mean next-20d TQQQ:")
    for k in range(10):
        sel = idx == k
        print(f"    {k}: {(y20[m][sel]).mean()*100:4.1f}%  {fut.to_numpy()[m][sel].mean()*100:+5.1f}%")

    corr_rv = np.corrcoef(rank[m & np.isfinite(f['rv_pct'].to_numpy())],
                          f['rv_pct'].to_numpy()[m & np.isfinite(f['rv_pct'].to_numpy())])[0, 1]
    corr_sma = np.corrcoef(rank[m & np.isfinite(f['sma165'].to_numpy())],
                           f['sma165'].to_numpy()[m & np.isfinite(f['sma165'].to_numpy())])[0, 1]
    print(f"  corr(rank, rv_pct)={corr_rv:.2f}  corr(rank, sma165 dist)={corr_sma:.2f}")

    # placebo
    dp = DailyPath(ts, o, c)
    i0 = bt.start_index(ts, START)
    eq1m = pd.Series(r0["equity"], index=ts[i0:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dp.dts).to_numpy()
    bil = np.tile([0.0, 0.0, 1.0], (len(dp.dts), 1))
    mm = dp.dts >= pd.Timestamp("2017-01-03")
    fl = flag & opened
    n_flag = int((fl & mm).sum())
    cand = np.where(opened & mm)[0]
    rng = np.random.default_rng(11)
    out = []
    for _ in range(300):
        over = np.zeros(len(dp.dts), bool)
        over[rng.choice(cand, n_flag, replace=False)] = True
        eqp, sk = sim_override(dp, base_eq, w0, over, bil, opened)
        vals = []
        for st in ("2017-01-03", "2021-10-25"):
            j = dp.dts.searchsorted(pd.Timestamp(st)) - sk
            ss = daily_stats(eqp[j:] / eqp[j] * 100000, dp.dts[j + sk:])
            vals += [ss["cagr"], ss["max_drawdown"], ss["sharpe"]]
        out.append(vals)
    out = np.array(out)
    print(f"\nplacebo ({n_flag} random flags, 300 draws, fast daily marks):")
    for k, nm in ((0, "10y CAGR"), (1, "10y DD"), (2, "10y Sh"), (3, "5y CAGR"), (4, "5y DD"), (5, "5y Sh")):
        print(f"  {nm}: mean {out[:,k].mean():.3f} p5 {np.percentile(out[:,k],5):.3f} "
              f"p95 {np.percentile(out[:,k],95):.3f} max {out[:,k].max():.3f}")

    # rolling 3y comparison from eval_out.json
    ev = json.loads((Path(__file__).parent / "eval_out.json").read_text())
    a = ev["q0.90_10y_rolling3"]; b = ev["winner_10y"]["rolling3"]
    n = min(len(a), len(b))
    beat_c = sum(a[i]["cagr"] > b[i]["cagr"] for i in range(n))
    beat_d = sum(a[i]["dd"] < b[i]["dd"] for i in range(n))
    print(f"\nrolling 3y vs winner: {beat_c}/{n} higher CAGR, {beat_d}/{n} lower DD")
    print(f"  overlay median CAGR {np.median([x['cagr'] for x in a])*100:.1f}% "
          f"median DD {np.median([x['dd'] for x in a])*100:.1f}% "
          f"worst DD {max(x['dd'] for x in a)*100:.1f}%")
    print(f"  winner  median CAGR {np.median([x['cagr'] for x in b])*100:.1f}% "
          f"median DD {np.median([x['dd'] for x in b])*100:.1f}% "
          f"worst DD {max(x['dd'] for x in b)*100:.1f}%")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
