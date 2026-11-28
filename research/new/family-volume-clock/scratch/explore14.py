"""Fourteenth exploration: smoothed acceleration variants for time robustness."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as st  # noqa: E402

ts, o, c, vol = st.load_panel()
dates, first, last = st.bt.day_bounds(ts)
n = len(first)
CQ, CT, CB = 0, 1, 2


def acc_at(dec, win=30, look=20):
    return st.volume_acceleration(ts, vol, dec, win, look)


def run_mask(mask, label, slip=1.0):
    w, d = st.weights_from_mask(ts, mask, 210)
    r, s = st.run_w(ts, o, c, w, slip=slip)
    print(f"  {label:44s} ent {d:4d} CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.1f}% "
          f"Sh {s['sharpe']:4.2f} 5bp {st.run_w(ts,o,c,w,5.0)[1]['cagr']*100:6.2f}%")
    return s


def state(a, enter, exit_):
    return st.state_mask(a, enter, exit_, hysteresis=True)


print("=== 60-minute window at 13:00 ===")
a60 = acc_at(210, 60, 20)
print("quantiles", np.nanpercentile(a60, [5, 10, 20, 30, 40, 50, 60, 70, 80, 90]).round(3))
for ent, ext in ((0.75, 0.85), (0.80, 0.90), (0.85, 0.95), (0.90, 1.00), (0.80, 1.00)):
    run_mask(state(a60, ent, ext), f"60m 13:00 e{ent:.2f} x{ext:.2f}")

print("\n=== 60-minute window time plateau, e0.85 x0.95 ===")
for dec in (180, 195, 210, 225, 240):
    a = acc_at(dec, 60, 20)
    run_mask(state(a, 0.85, 0.95), f"60m {9+(30+dec)//60:02d}:{(30+dec)%60:02d}")

print("\n=== 90-minute composite (mean of 30m accel at 12:45/13:00/13:15) ===")
a1, a2, a3 = acc_at(195), acc_at(210), acc_at(225)
comp = np.nanmean(np.vstack([a1, a2, a3]), axis=0)
print("quantiles", np.nanpercentile(comp, [5, 10, 20, 30, 40, 50, 60, 70, 80, 90]).round(3))
for ent, ext in ((0.80, 0.90), (0.85, 0.95), (0.90, 1.00), (0.95, 1.05), (0.90, 1.10)):
    run_mask(state(comp, ent, ext), f"comp90 e{ent:.2f} x{ext:.2f}")

print("\n=== 60-minute composite (mean of 30m accel at 12:45/13:15) ===")
comp2 = np.nanmean(np.vstack([a1, a3]), axis=0)
print("quantiles", np.nanpercentile(comp2, [5, 10, 20, 30, 40, 50, 60, 70, 80, 90]).round(3))
for ent, ext in ((0.80, 0.90), (0.85, 0.95), (0.90, 1.00), (0.95, 1.05)):
    run_mask(state(comp2, ent, ext), f"comp60 e{ent:.2f} x{ext:.2f}")

print("\n=== 3-day smoothed 30m accel at 13:00 ===")
a3d = pd.Series(a2).rolling(3, min_periods=3).mean().to_numpy()
print("quantiles", np.nanpercentile(a3d, [5, 10, 20, 30, 40, 50, 60, 70, 80, 90]).round(3))
for ent, ext in ((0.80, 0.90), (0.85, 0.95), (0.90, 1.00), (0.95, 1.05)):
    run_mask(state(a3d, ent, ext), f"3d e{ent:.2f} x{ext:.2f}")

print("\n=== 5-day smoothed 30m accel at 13:00 ===")
a5d = pd.Series(a2).rolling(5, min_periods=5).mean().to_numpy()
for ent, ext in ((0.85, 0.95), (0.90, 1.00), (0.95, 1.05)):
    run_mask(state(a5d, ent, ext), f"5d e{ent:.2f} x{ext:.2f}")
