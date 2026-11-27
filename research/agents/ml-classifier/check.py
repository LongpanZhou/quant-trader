"""Independent check of the chosen overlay + drawdown/year diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    n = len(ts)
    q = c[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = q > sma
    p = np.load(ROOT / "research" / "agents" / "ml-classifier" / "pd_h20_w750.npy")
    thr = pd.Series(p).rolling(252, min_periods=60).quantile(0.2).shift(1).to_numpy()
    pos = base & ~(p < thr)
    w = np.zeros((n, 3)); w[:, 1] = pos.astype(float); w[:, 2] = 1 - pos
    r = bt.run(ts, o, c, w, "2017-01-03", band=0.02, slippage_bps=1.0)
    s = bt.stats(r, 252)
    print(f"harness: CAGR {s['cagr']*100:.4f} DD {s['max_drawdown']*100:.4f} Sharpe {s['sharpe']:.4f} "
          f"end {s['ending_equity']:,.2f} fills {s['fills']} turnover {s['turnover']:.1f}")

    i0 = bt.start_index(ts, "2017-01-03")
    pos_s = pos[i0:]
    op_t = o[i0:, 1]
    op_b = o[i0:, 2]
    # open-to-open returns, position set the prior close
    eq = [100_000.0]
    for j in range(len(pos_s) - 2):
        ret = pos_s[j] * (op_t[j + 2] / op_t[j + 1] - 1) + (1 - pos_s[j]) * (op_b[j + 2] / op_b[j + 1] - 1)
        eq.append(eq[-1] * (1 + ret))
    eq = np.array(eq)
    years = (ts[i0 + len(eq) - 1] - ts[i0]).total_seconds() / (365.25 * 86400)
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    dd = -(eq / peak - 1).min()
    print(f"vectorized no-cost: CAGR {cagr*100:.4f} DD {dd*100:.4f} end {eq[-1]:,.0f}")

    # drawdown dates
    e = r["equity"]
    peak = np.maximum.accumulate(e)
    ddn = e / peak - 1
    trough = int(np.argmin(ddn))
    pk = int(np.argmax(e[:trough + 1]))
    print("maxDD peak", r["ts"][pk], "trough", r["ts"][trough], f"{ddn[trough]*100:.2f}%")

    # yearly returns 5y slice
    i5 = bt.start_index(ts, "2021-10-25")
    r5 = bt.run(ts, o, c, w, "2021-10-25", band=0.02, slippage_bps=1.0)
    y5 = bt.yearly(r5["ts"], r5["equity"], c[i5:i5 + len(r5["ts"]), 1])
    print("5y yearly:", {y: (round(v["strategy"] * 100, 1), round(v["benchmark"] * 100, 1)) for y, v in y5.items()})

    # exclude 2020 from 10y
    mask = r["ts"].year != 2020
    e2 = r["equity"][mask]
    t2 = r["ts"][mask]
    yrs2 = (t2[-1] - t2[0]).total_seconds() / (365.25 * 86400)
    print(f"ex-2020 CAGR {((e2[-1]/e2[0])**(1/yrs2)-1)*100:.2f}% DD {-(e2/np.maximum.accumulate(e2)-1).min()*100:.2f}%")

    # t-test avoided vs held days (intraday next-day returns)
    d = pd.DataFrame({"base": base, "pos": pos, "p": p, "t_open": o[:, 1], "t_close": c[:, 1]})
    d["fwd"] = d.t_close.shift(-1) / d.t_open.shift(-1) - 1
    ex = d[(d.base) & (~d.pos)].fwd.dropna()
    he = d[(d.base) & (d.pos)].fwd.dropna()
    print(f"exit days n={len(ex)} mean {ex.mean()*100:.4f}% held n={len(he)} mean {he.mean()*100:.4f}% "
          f"diff {100*(he.mean()-ex.mean()):.4f}% t={ (he.mean()-ex.mean())/np.sqrt(he.var(ddof=1)/len(he)+ex.var(ddof=1)/len(ex)):.2f}")


if __name__ == "__main__":
    main()
