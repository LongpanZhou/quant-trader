"""Batch 2: control + stop overlays (correct regime mapping, no same-day re-entry after stop)."""
import engine2 as E

ts, o, c, feats = E.load_cached()
print("bars", len(ts), "last_bar", feats["last_bar"], flush=True)

runs = [
    ("BASE (daily regime, 5m exec)", {}),
    ("stop_prev 1.0%", dict(stop_prev=0.010)),
    ("stop_prev 1.5%", dict(stop_prev=0.015)),
    ("stop_prev 2.0%", dict(stop_prev=0.020)),
    ("stop_prev 2.5%", dict(stop_prev=0.025)),
    ("stop_prev 3.0%", dict(stop_prev=0.030)),
    ("stop_prev 1.5% reentry rsi2<5", dict(stop_prev=0.015, reentry=5)),
    ("stop_prev 2.0% reentry rsi2<5", dict(stop_prev=0.020, reentry=5)),
    ("trail 12%", dict(trail=0.12)),
    ("trail 20%", dict(trail=0.20)),
    ("trail 12% + stop_prev 2%", dict(trail=0.12, stop_prev=0.02)),
    ("stop_pnl 10%", dict(stop_pnl=0.10)),
]

for name, extra in runs:
    p = dict(signal="none", base=1.0, entry=0, exit=0, **extra)
    print("\n" + name)
    E.run_one(ts, o, c, feats, p, slip=1.0)
