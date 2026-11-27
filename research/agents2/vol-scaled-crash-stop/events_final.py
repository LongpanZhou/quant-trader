"""Final stop-event stats for the capped ATR stop (no backtests)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))

from sweep1 import build_measures, load_cache, regime_arrays  # noqa: E402


def stats(name, ts, opens, closes, first, last, risk_on, armed, dist):
    ev = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k] or not armed[k]:
            continue
        base = opens[f, 1]
        for i in range(f, l + 1):
            if dist[k] == dist[k] and closes[i, 1] < base * (1 - dist[k]):
                px = opens[i + 1, 1] if i + 1 < len(ts) else closes[i, 1]
                nxt = opens[f + 390, 1] if f + 390 < len(opens) else closes[-1, 1]
                ev.append((nxt / px - 1.0, closes[l, 1] / px - 1.0))
                break
    ev = [e for e in ev if e[0] == e[0]]
    a = np.array(ev)
    print(f"{name}: {len(a)} events  mean exit->next open {a[:,0].mean()*100:+.2f}%  "
          f"median {np.median(a[:,0])*100:+.2f}%  share negative {np.mean(a[:,0]<0)*100:.0f}%  "
          f"mean exit->close {a[:,1].mean()*100:+.2f}%")
    return a


ts, opens, highs, lows, closes, _ = load_cache()
m = build_measures(ts, opens, highs, lows, closes)
first, last, dates = m["first"], m["last"], m["dates"]
risk_on, armed, _ = regime_arrays(ts, closes, first, last)
a = m["atr14"]
nd = len(first)
i0 = 2017
sel = np.array([d.year >= i0 for d in dates[last]])

for name, d in (("fixed4", np.full(nd, 0.04)),
                ("cap4 k0.70", np.clip(0.70 * a, 0.025, 0.040)),
                ("cap4 k0.55", np.clip(0.55 * a, 0.025, 0.040))):
    # restrict to the test window by zeroing pre-2017
    dd = np.where(sel, d, 1.0)
    stats(name, ts, opens, closes, first, last, risk_on, armed, dd)

arm = risk_on & armed & sel & np.isfinite(a)
print(f"\ncapped stop on armed days: median {np.median(np.clip(0.7*a,0.025,0.04)[arm])*100:.2f}%")
print(f"share at 2.5% floor {np.mean(np.clip(0.7*a,0.025,0.04)[arm]<=0.0251)*100:.0f}%  "
      f"at 4% cap {np.mean(np.clip(0.7*a,0.025,0.04)[arm]>=0.0399)*100:.0f}%")
