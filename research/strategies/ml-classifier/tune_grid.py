"""Tune grid (2026-11-27), development period only (<= 2023-12-29).

    python research/strategies/ml-classifier/tune_grid.py   -> tune_grid.csv

Variants: k x train window x forward horizon x confirm days x mapping.
mapping: orig   = best->TQQQ, second->QQQ, rest->BIL   (shipped)
         tb     = best->TQQQ, rest->BIL
         tq     = best->TQQQ, rest->QQQ
For each variant: dev (2017-01-03 -> 2023-12-29) CAGR / DD / Sharpe at 1 bp,
sub-period CAGRs, average gross leverage, the leverage-matched static
TQQQ+BIL mix Sharpe, and the daily-return correlation with the 165d baseline.
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
from strategy import bt, to_minutes  # noqa: E402

ORIG_MAP = S._map_clusters


def make_map(mode):
    def m(ft, fq, labels, k, min_members=20):
        mapping, stats = ORIG_MAP(ft, fq, labels, k, min_members)
        if mode == "orig":
            return mapping, stats
        best = stats[0]
        out = {s[0]: (2 if mode == "tb" else 0) for s in stats}
        out[best[0]] = 1 if best[1] > 0 else (2 if mode == "tb" else 0)
        return out, stats
    return m


def daily_eq(r):
    s = pd.Series(r["equity"], index=r["ts"])
    return s.groupby(s.index.normalize()).last()


def sub_cagr(eq, y0, y1):
    e = eq[(eq.index.year >= y0) & (eq.index.year <= y1)]
    prev = eq[eq.index.year < y0]
    base = prev.iloc[-1] if len(prev) else e.iloc[0]
    yrs = (e.index[-1] - (prev.index[-1] if len(prev) else e.index[0])).days / 365.25
    return (e.iloc[-1] / base) ** (1 / yrs) - 1


def main():
    ts5, o5, c5 = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "5min")
    tsd, od, cd = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1D")
    ts1, o1, c1 = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
    assert tsd[-1] <= pd.Timestamp("2023-12-29", tz="America/New_York")
    feats = S.build_features(ts5, o5, c5, tsd, od, cd)
    i0 = bt.start_index(tsd, S.TRADE_START)
    wb = S.correlation_benchmark_weights(tsd, cd)
    rb = bt.run(ts1, o1, c1, to_minutes(tsd, wb, ts1, "1D"), S.TRADE_START, band=S.BAND)
    base_ret = daily_eq(rb).pct_change().dropna()
    mix_cache = {}

    rows = []
    grid = list(itertools.product((2, 3, 4), (500, 750, 1000), (10, 20, 40), (1, 2, 3),
                                  ("orig", "tb", "tq")))
    t0 = time.time()
    for n, (k, tw, h, cf, mp) in enumerate(grid):
        if mp == "orig" and k == 2:
            pass  # k=2 'orig' is identical to tb (no second cluster); still run, cheap
        S._map_clusters = make_map(mp)
        w, info = S.build_weights(tsd, feats, od, cd, k=k, train_window=tw, horizon=h,
                                  confirm_days=cf)
        S._map_clusters = ORIG_MAP
        r = bt.run(ts1, o1, c1, to_minutes(tsd, w, ts1, "1D"), S.TRADE_START, band=S.BAND)
        s = bt.stats(r, S.BARS_1M)
        eq = daily_eq(r)
        held = np.argmax(w[i0 - 1:-1], axis=1)
        lev = float(np.mean(np.where(held == 1, 3.0, np.where(held == 0, 1.0, 0.0))))
        key = round(lev / 3, 2)
        if key not in mix_cache:
            wm = np.tile([0, key, 1 - key], (len(tsd), 1))
            rm = bt.run(ts1, o1, c1, to_minutes(tsd, wm, ts1, "1D"), S.TRADE_START, band=S.BAND)
            mix_cache[key] = bt.stats(rm, S.BARS_1M)
        mix = mix_cache[key]
        corr = float(eq.pct_change().dropna().corr(base_ret))
        rows.append(dict(k=k, train=tw, horizon=h, confirm=cf, map=mp,
                         cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                         c1719=sub_cagr(eq, 2017, 2019), c2021=sub_cagr(eq, 2020, 2021),
                         c2223=sub_cagr(eq, 2022, 2023), lev=lev,
                         mix_cagr=mix["cagr"], mix_sharpe=mix["sharpe"],
                         corr=corr, switches=info["switches"]))
        if n % 20 == 0:
            print(n, len(grid), f"{time.time()-t0:.0f}s", rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "tune_grid.csv", index=False, float_format="%.4f", lineterminator="\n")
    print("wrote tune_grid.csv", len(df))


if __name__ == "__main__":
    main()
