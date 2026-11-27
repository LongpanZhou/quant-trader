"""Final diagnostics: year-removal, bootstrap, placebo, exit alpha."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402
from strategy import build_strategy  # noqa: E402


def main():
    ts5, o5, c5 = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    w, pos, base, bear, rank, ps, f = build_strategy(ts5, o5, c5, tsd, od, cd)
    r = bt.run(tsd, od, cd, w, "2017-01-03", band=0.02, slippage_bps=1.0)
    ts, eq = r["ts"], r["equity"]
    rets = np.diff(eq) / eq[:-1]
    years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)
    print(f"full: CAGR {(eq[-1]/eq[0])**(1/years)-1:.4f} years {years:.2f}")

    yr = np.array([t.year for t in ts[1:]])
    for y in (2017, 2018, 2020, 2023, 2024, 2026):
        keep = yr != y
        eq2 = np.concatenate([[eq[0]], eq[0] * np.cumprod(1 + rets[keep])])
        yy = years - 1
        cagr = (eq2[-1] / eq2[0]) ** (1 / yy) - 1
        peak = np.maximum.accumulate(eq2)
        print(f"ex-{y}: CAGR {cagr*100:6.2f}%  DD {-(eq2/peak-1).min()*100:5.2f}%")

    # 5y through 2025-12-31 (no 2026)
    for end in ("2025-12-31", "2026-10-23"):
        i5 = bt.start_index(tsd, "2021-10-25")
        iend = bt.start_index(tsd, end)
        r2 = bt.simulate(tsd[i5:iend], od[i5:iend], cd[i5:iend], w[i5:iend],
                         band=0.02, slippage_bps=1.0)
        s2 = bt.stats(r2, 252)
        print(f"5y to {end}: CAGR {s2['cagr']*100:6.2f}% DD {s2['max_drawdown']*100:5.2f}%")

    # exit alpha (next intraday)
    d = pd.DataFrame({"base": base, "pos": pos, "p": rank,
                      "t_open": od[:, 1], "t_close": cd[:, 1]})
    d["fwd"] = d.t_close.shift(-1) / d.t_open.shift(-1) - 1
    ex = d[(d.base) & (~d.pos)].fwd.dropna()
    he = d[(d.base) & (d.pos)].fwd.dropna()
    diff = he.mean() - ex.mean()
    se = np.sqrt(he.var(ddof=1) / len(he) + ex.var(ddof=1) / len(ex))
    print(f"exit n={len(ex)} mean {ex.mean()*100:.4f}% | held n={len(he)} mean {he.mean()*100:.4f}% | "
          f"diff {diff*100:.4f}% t={diff/se:.2f}")

    # block bootstrap of CAGR (20-day blocks)
    rng = np.random.default_rng(11)
    blk = 20
    n = len(rets)
    nb = int(np.ceil(n / blk))
    cagrs = []
    for _ in range(1000):
        idx = rng.integers(0, n - blk, nb)
        sample = np.concatenate([rets[i:i + blk] for i in idx])[:n]
        cagrs.append((np.prod(1 + sample)) ** (1 / years) - 1)
    cagrs = np.array(cagrs)
    print(f"bootstrap CAGR: mean {cagrs.mean()*100:.1f}%  p5 {np.percentile(cagrs,5)*100:.1f}%  "
          f"p95 {np.percentile(cagrs,95)*100:.1f}%  p1 {np.percentile(cagrs,1)*100:.1f}%")

    # placebo: random exit days at same rate (rank replaced by random)
    cagrs = []
    i0 = bt.start_index(tsd, "2017-01-03")
    for _ in range(200):
        pr = rng.random(len(tsd))
        rr = pd.Series(pr).rolling(252, min_periods=60).rank(pct=True).to_numpy()
        posr = base & ~(rr < 0.2)
        wr = np.zeros((len(tsd), 3)); wr[:, 1] = posr.astype(float); wr[:, 2] = 1 - wr[:, 1]
        r3 = bt.run(tsd, od, cd, wr, "2017-01-03", band=0.02, slippage_bps=1.0)
        s3 = bt.stats(r3, 252)
        cagrs.append(s3["cagr"])
    cagrs = np.array(cagrs)
    print(f"placebo CAGR mean {cagrs.mean()*100:.1f}% p5 {np.percentile(cagrs,5)*100:.1f}% "
          f"p95 {np.percentile(cagrs,95)*100:.1f}% max {cagrs.max()*100:.1f}% "
          f"ML percentile {(cagrs < 0.7495).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
