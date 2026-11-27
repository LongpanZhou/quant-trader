"""Hunt for bad prints in 1m-derived daily bars."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt

ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
dates = np.array([t.date() for t in ts])
for k, sym in enumerate(("QQQ", "TQQQ", "BIL")):
    o, c = opens[:, k], closes[:, k]
    intr = c / o - 1
    gap = o[1:] / c[:-1] - 1
    print(f"\n{sym}: intraday |max| {np.abs(intr).max()*100:.1f}%  p99.9 {np.percentile(np.abs(intr),99.9)*100:.2f}%")
    idx = np.argsort(-np.abs(intr))[:8]
    for j in idx:
        print(f"   {dates[j]}  open {o[j]:.4f} close {c[j]:.4f} intraday {intr[j]*100:7.1f}%")
    print(f"  gaps: |max| {np.abs(gap).max()*100:.1f}%")
    idx = np.argsort(-np.abs(gap))[:8]
    for j in idx:
        print(f"   {dates[j+1]}  prev close {c[j]:.4f} open {o[j+1]:.4f} gap {gap[j]*100:7.1f}%")
