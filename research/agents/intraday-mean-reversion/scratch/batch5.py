"""Batch 5: gross vs net MR, stop slippage sensitivity, yearly tables."""
import numpy as np
import pandas as pd

import engine3 as E

ts, o, c, feats = E.load_cached()

print("=== MR variants: gross (0bp) vs 1bp vs 5bp ===")
for name, p in [
    ("M1b rsi2<10", dict(signal="rsi2", base=0.0, entry=10, exit=60, exit_bar=75, entry_bars=(1, 66))),
    ("M3b vwap<-0.4%", dict(signal="vwap", base=0.0, entry=-0.0040, exit=0.0, exit_bar=75, entry_bars=(1, 66))),
    ("M4 drop<-1%", dict(signal="drop", base=0.0, entry=-0.010, exit=0.0, exit_bar=75, entry_bars=(1, 18))),
]:
    line = f"{name:20s}"
    for slip in (0.0, 1.0, 5.0):
        out, _ = E.run_one(ts, o, c, feats, p, slip=slip, verbose=False)
        line += f" | {slip:.0f}bp 10y {out['10y']['stats']['cagr']*100:6.2f}% {out['10y']['stats']['max_drawdown']*100:5.1f}%"
    print(line, flush=True)

print("\n=== stop overlay: slippage sensitivity ===")
for x in (0.025, 0.030, 0.035):
    line = f"stop {x*100:.1f}%"
    for slip in (0.0, 1.0, 5.0, 10.0, 20.0):
        out, _ = E.run_one(ts, o, c, feats, dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=x),
                           slip=slip, verbose=False)
        s10, s5 = out["10y"]["stats"], out["5y"]["stats"]
        line += f" | {slip:4.0f}bp {s10['cagr']*100:5.2f}/{s10['max_drawdown']*100:4.1f} {s5['cagr']*100:5.2f}/{s5['max_drawdown']*100:4.1f}"
    print(line, flush=True)

print("\n=== yearly returns ===")
for label, p in [
    ("base", dict(signal="none", base=1.0, entry=0, exit=0)),
    ("stop2.5", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.025)),
    ("stop3.0", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.030)),
    ("stop3.5", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.035)),
]:
    out, w = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
    res = out["10y"]["res"]
    i0 = E.bt.start_index(ts, E.START10)
    y = E.bt.yearly(res["ts"], res["equity"], c[i0:, 1])
    print(f"\n{label}: " + "  ".join(f"{k}:{v['strategy']*100:+.1f}%/{v['benchmark']*100:+.1f}%" for k, v in y.items()))

# drawdown with/without stop: show worst 5 episodes for stop3.0
print("\n=== stop3.0 DD episodes ===")
p = dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.030)
out, w = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
eq = out["10y"]["res"]["equity"]
t = out["10y"]["res"]["ts"]
peak = np.maximum.accumulate(eq)
dd = eq / peak - 1
in_dd, st, eps = False, 0, []
for i in range(len(eq)):
    if not in_dd and dd[i] < -0.02:
        in_dd, st = True, i
    elif in_dd and dd[i] >= -1e-9:
        in_dd = False
        j = st + int(np.argmin(dd[st:i]))
        eps.append((dd[st:i].min(), t[st], t[j], t[i]))
for v, a, b_, cc in sorted(eps)[:6]:
    print(f"  {v*100:6.1f}%  {a.date()} -> {b_.date()} -> {cc.date()}")
