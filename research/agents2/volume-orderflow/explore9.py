"""Step 11: anatomy of the 5y max drawdown (2026 summer) and the 10y one (2019)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_rows", 200)


def show(D, a, b, w, label):
    i0 = engine.bt.start_index(D.ts, engine.START10)
    r = engine.fastsim.fast_sim(D.op[i0:], D.cl[i0:], w[i0:], slippage_bps=1.0)
    idx = D.ts[i0:]
    eq = pd.Series(r["equity"], index=idx).groupby(idx.date).last()
    ret = eq.pct_change()
    hold = w[i0:, 1]
    hold_d = pd.Series(hold, index=idx).groupby(idx.date).mean()
    df = pd.DataFrame({"ret": ret, "eq": eq, "expo": hold_d})
    days = np.array(list(df.index))
    pos_map = {d: k for k, d in enumerate(D.dates[D.first])}
    pos = np.array([pos_map[d] for d in days])
    df["qqq"] = D.qc[pos] / np.r_[np.nan, D.qc[pos][:-1]] - 1
    df["rvol"] = D.rvol_day[pos]
    df["dev"] = D.dev_q[pos, 359]
    sub = df[(df.index >= pd.Timestamp(a).date()) & (df.index <= pd.Timestamp(b).date())]
    print(f"\n=== {label} {a}..{b}")
    print(sub.assign(ret=sub.ret * 100, qqq=sub.qqq * 100, dev=sub.dev * 100,
                     expo=sub.expo * 100).round(2).to_string())


def main():
    D = engine.Data()
    w, _ = engine.winner_weights(D)
    show(D, "2026-06-10", "2026-08-07", w, "5y max DD window")
    show(D, "2019-04-15", "2019-06-14", w, "10y DD tail")


if __name__ == "__main__":
    main()
