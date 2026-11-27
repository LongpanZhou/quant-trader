"""Batch 6: stop 3% + MR re-entry variants."""
import engine3 as E

ts, o, c, feats = E.load_cached()

cases = [
    ("stop3.0 plain", dict(stop_prev=0.030)),
    ("stop3.0 + rsi2<2 reentry", dict(stop_prev=0.030, reentry="rsi2", re_thresh=2)),
    ("stop3.0 + rsi2<5 reentry", dict(stop_prev=0.030, reentry="rsi2", re_thresh=5)),
    ("stop3.0 + deeper(-4.5%) reentry", dict(stop_prev=0.030, reentry="deeper", re_deep=-0.045)),
    ("stop3.0 + deeper(-4.5%) half", dict(stop_prev=0.030, reentry="deeper", re_deep=-0.045, reentry_w=0.5)),
    ("stop3.0 + reclaim vwap reentry", dict(stop_prev=0.030, reentry="reclaim")),
    ("stop3.0 + reclaim half", dict(stop_prev=0.030, reentry="reclaim", reentry_w=0.5)),
    ("stop2.75 plain", dict(stop_prev=0.0275)),
    ("stop2.75 + reclaim", dict(stop_prev=0.0275, reentry="reclaim")),
]
for name, extra in cases:
    p = dict(signal="none", base=1.0, entry=0, exit=0, **extra)
    print("\n" + name)
    E.run_one(ts, o, c, feats, p, slip=1.0)
