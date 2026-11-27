"""Diagnostic: reproduce the README daily baseline exactly; check TQQQ DD."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D")
i0 = bt.start_index(tsd, START)
print("daily bars", len(tsd), "test", len(tsd) - i0, tsd[0].date(), tsd[-1].date())
b = bt.benchmark(cd[i0:, 1], tsd[i0:], 252)
print(f"TQQQ B&H daily CAGR {b['cagr']*100:.2f}% DD {b['max_drawdown']*100:.2f}% Sharpe {b['sharpe']:.2f}")

qqq = cd[:, 0]
day = pd.DataFrame({"c": qqq}, index=pd.Index(tsd))
sma = day["c"].rolling(165).mean()
reg = (day["c"] > sma).astype(float)

# variant 1: regime from close of i, fill open i+1 (README description)
for shift in (0, 1):
    sig = reg.shift(shift).fillna(0.0).to_numpy()
    w = np.zeros((len(tsd), 3))
    w[:, 1] = sig
    w[:, 2] = 1 - sig
    res = bt.run(tsd, od, cd, w, START, band=0.02, slippage_bps=1.0)
    s = bt.stats(res, 252)
    print(f"\nshift={shift}")
    bt.print_summary("regime baseline", s, b)

# variant 2: signal at close of i-1 (shift 1) but band on signal? try SMA +/- 2%
enter = (day["c"] > sma * 1.0).astype(float)
for band in (0.0, 0.01, 0.02):
    st = np.zeros(len(day))
    state = 0.0
    for i in range(len(day)):
        px = day["c"].iloc[i]
        sm = sma.iloc[i]
        if np.isnan(sm):
            st[i] = 0.0
            continue
        if state == 0 and px > sm * (1 + band):
            state = 1.0
        elif state == 1 and px < sm * (1 - band):
            state = 0.0
        st[i] = state
    w = np.zeros((len(tsd), 3))
    w[:, 1] = st
    w[:, 2] = 1 - st
    res = bt.run(tsd, od, cd, w, START, band=0.02, slippage_bps=1.0)
    s = bt.stats(res, 252)
    print(f"\nhysteresis band={band}")
    bt.print_summary("regime hysteresis", s, b)
