"""Flag-date diagnostics + placebo for the h20 crash overlay."""
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
from validate import build  # noqa: E402
from screen import DailyPath, sim_override, daily_stats  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w, flag, opened, dts, f, p, rank = build(ts, o, c, 20, -0.15, 0.90, "bil")
    m = dts >= pd.Timestamp("2017-01-03")
    tq = pd.Series(c[:, 1], index=ts)
    tqd = tq.groupby(tq.index.date).last()
    tqd.index = pd.DatetimeIndex(tqd.index)
    fwd = tqd.pct_change().shift(-1)
    fl = flag & opened

    print("flag dates by year:")
    for y in range(2017, 2027):
        sel = fl & (dts.year == y)
        dates = [str(x.date()) for x in dts[sel]]
        if dates:
            print(f"  {y} ({len(dates)}): " + " ".join(dates))

    print("\nflagged-day next-day TQQQ return by year:")
    for y in range(2017, 2027):
        sel = fl & (dts.year == y)
        if sel.sum():
            print(f"  {y}: n={sel.sum():3d} mean {fwd[sel].mean()*100:+.2f}% "
                  f"median {fwd[sel].median()*100:+.2f}% min {fwd[sel].min()*100:+.1f}%")

    print("\nmonthly strategy returns 2025-2026 vs winner (1m):")
    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
    eq = pd.Series(r["equity"], index=ts)
    me = eq.resample("ME").last().pct_change()
    # winner monthly
    from analyze2 import winner_daily
    w0, op0, st0, la0, fi0 = winner_daily(ts, o, c)
    r0 = bt.run(ts, o, c, w0, START, band=0.02, slippage_bps=1.0)
    eq0 = pd.Series(r0["equity"], index=ts)
    me0 = eq0.resample("ME").last().pct_change()
    for t, v in me.items():
        if t.year >= 2025:
            print(f"  {t.strftime('%Y-%m')}: strat {v*100:6.1f}%  winner {me0[t]*100:6.1f}%")

    # ex-year CAGRs from daily equity
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    for drop in (None, 2020, 2023, 2025):
        keep = np.ones(len(d), bool)
        if drop:
            keep = d.index.year != drop
        dd = d[keep]
        yrs = (dd.index[-1] - dd.index[0]).days / 365.25
        cagr = (dd.iloc[-1] / dd.iloc[0]) ** (1 / yrs) - 1
        print(f"  drop {drop}: CAGR {cagr*100:.2f}%")

    # placebo on fast sim: random flags with same count on held days
    dp = DailyPath(ts, o, c)
    i0 = bt.start_index(ts, START)
    eq1m = pd.Series(r0["equity"], index=ts[i0:])
    deq = eq1m.groupby(eq1m.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    base_eq = deq.reindex(dp.dts).to_numpy()
    bil = np.tile([0.0, 0.0, 1.0], (len(dp.dts), 1))
    n_flag = int((fl & m).sum())
    cand = np.where(opened & m)[0]
    rng = np.random.default_rng(7)
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
    print(f"\nplacebo ({n_flag} random flags, 300 draws), fast-sim daily marks:")
    for k, nm in ((0, "10y CAGR"), (1, "10y DD"), (2, "10y Sh"), (3, "5y CAGR"), (4, "5y DD"), (5, "5y Sh")):
        print(f"  {nm}: mean {out[:,k].mean():.3f}  p5 {np.percentile(out[:,k],5):.3f}  "
              f"p95 {np.percentile(out[:,k],95):.3f}  max {out[:,k].max():.3f}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
