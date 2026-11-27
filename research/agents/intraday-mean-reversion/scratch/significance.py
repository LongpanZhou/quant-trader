"""Is the stop's edge statistically real? Event-level and daily-diff tests."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import strategy as S  # noqa: E402

RULE = "5min"
S.RULE = RULE
ts, o, c, feats = S.prepare(RULE)
n = len(ts)
w_stop, _ = S.make_weights(feats, n, 0.03)
w_base, _ = S.make_weights(feats, n, 1.0)

s1, b1, r_stop, i0 = S.metrics(ts, o, c, w_stop, S.START10, 1.0)
s0, b0, r_base, _ = S.metrics(ts, o, c, w_base, S.START10, 1.0)

# daily equity
def daily(res):
    eq = pd.Series(res["equity"], index=pd.DatetimeIndex(res["ts"]))
    return eq.groupby(eq.index.date).last()

e1, e0 = daily(r_stop), daily(r_base)
r1 = e1.pct_change().dropna()
r0 = e0.pct_change().dropna()
diff = (r1 - r0).dropna()
print("daily return diff (stop - base): mean %.4f%%  sd %.4f%%  t=%.2f  n=%d" % (
    diff.mean() * 100, diff.std() * 100, diff.mean() / diff.std() * np.sqrt(len(diff)), len(diff)))
big = diff[abs(diff) > 0.001]
print("  days with |diff|>0.1pp: n=%d  mean %.3f%%  t=%.2f  sum %.1f%%" % (
    len(big), big.mean() * 100, big.mean() / big.std() * np.sqrt(len(big)), big.sum() * 100))
print("  worst 8 daily diffs:", ", ".join(f"{x*100:+.1f}%" for x in np.sort(diff)[:8]))
print("  best  8 daily diffs:", ", ".join(f"{x*100:+.1f}%" for x in np.sort(diff)[-8:]))

# per-event: hold-vs-stop P&L from trigger to next open
date, bars = feats["dlist"], feats["bars"]
qqq, qpc = feats["qqq"], feats["qpc"]
stop_idx = [i for i in range(1, n - 1)
            if w_stop[i, 1] == 0 and w_stop[i - 1, 1] == 1 and np.isfinite(qpc[i]) and qqq[i] / qpc[i] - 1 <= -0.03]
eff = []
for i in stop_idx:
    d = date[i]
    j = max(k for k in range(i, n) if date[k] == d)
    if j + 1 >= n:
        continue
    # stop: exit at o[i+1]; base: hold to o[j+1] (next day open)
    eff.append(o[j + 1, 1] / o[i + 1, 1] - 1.0)
eff = np.array(eff)
print("\nper-event stop-vs-hold (exit fill -> next open): mean %+.3f%%  median %+.3f%%  sd %.2f%%  t=%.2f  n=%d" % (
    eff.mean() * 100, np.median(eff) * 100, eff.std() * 100, eff.mean() / eff.std() * np.sqrt(len(eff)), len(eff)))
print("  win rate %.1f%%  worst %+.2f%%  best %+.2f%%" % (
    np.mean(eff > 0) * 100, eff.min() * 100, eff.max() * 100))
print("  sum of log effects %.1f%%" % (np.log1p(eff).sum() * 100))
