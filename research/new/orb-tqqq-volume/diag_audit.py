"""Audit: look-ahead truncation, trade log, and a few raw-bar checks."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

ts, o, c, bars = S.load_dev()
w_full, info = S._build(ts, o, c, S.CFG, bars)
print(f"full entries {info['entries']} stops {info['stops']} eod {info['eod']}")

print("\n=== look-ahead truncation test ===")
for cut in ("2020-03-12 11:07", "2022-09-13 10:41", "2018-10-10 14:33"):
    j = int(ts.searchsorted(pd.Timestamp(cut, tz="America/New_York")))
    ts_c, o_c, c_c = ts[:j + 1], o[:j + 1], c[:j + 1]
    bars_c = bars.iloc[:j + 1]
    w_c, _ = S._build(ts_c, o_c, c_c, S.CFG, bars_c)
    # compare every bar before the start of the truncated session
    d = ts_c.date
    session_start = int(np.flatnonzero(d == d[-1])[0])
    same = np.array_equal(w_full[:session_start], w_c[:session_start])
    print(f"  cut {cut}: bars {len(ts_c)}  session_start {session_start}  "
          f"weights identical before cut: {same}")
    if not same:
        bad = np.flatnonzero((w_full[:session_start] != w_c[:session_start]).any(axis=1))
        print("    first diffs:", bad[:10])

print("\n=== trade log: all trades ===")
log = []
S._build(ts, o, c, S.CFG, bars, log=log)
tr = pd.DataFrame(log)
print(tr.groupby("kind")["ret"].agg(["count", "mean", "median"]))
print("\n2022 trades:")
y22 = tr[tr["date"].apply(lambda x: x.year == 2022)]
print(y22[["date", "entry_min", "entry_px", "exit_px", "ret", "kind", "gap", "rvol",
           "atr"]].to_string(index=False))
print(f"\n2022 total return compounded: {(np.prod(1 + y22['ret']) - 1) * 100:.2f}%  "
      f"n={len(y22)}")
print(f"2022 win rate: {np.mean(y22['ret'] > 0) * 100:.1f}%")

print("\n=== yearly compounded trade returns (100% sizing, before costs) ===")
for y, g in tr.groupby(tr["date"].apply(lambda x: x.year)):
    print(f"  {y}: {((np.prod(1 + g['ret']) - 1) * 100):7.2f}%  n={len(g):3d}  "
          f"win={np.mean(g['ret'] > 0) * 100:4.1f}%  "
          f"avg={g['ret'].mean() * 100:6.3f}%")

print("\n=== raw-bar check of the 5 best 2022 trades ===")
for _, r in y22.nlargest(5, "ret").iterrows():
    k = list(tr.index).index(r.name) if False else None
    i = int(r["entry_i"])
    print(f"{r['date']} entry {r['entry_min']} px {r['entry_px']:.2f} -> "
          f"exit px {r['exit_px']:.2f} ret {r['ret']*100:.2f}% {r['kind']}")
    # print the OR high and the first 3 post-entry closes/highs/lows
    d = r["date"]
    day = np.flatnonzero(ts.date == d)
    s0, e0 = day[0], day[-1]
    print(f"   day open {bars['open'].to_numpy()[s0]:.2f} close "
          f"{bars['close'].to_numpy()[e0]:.2f} high {bars['high'].to_numpy()[s0:e0+1].max():.2f} "
          f"low {bars['low'].to_numpy()[s0:e0+1].min():.2f}")

print("\n=== exposure / holding time ===")
print(tr["entry_min"].describe())
print("median hold minutes:", (tr["exit_i"] - tr["entry_i"]).median())
