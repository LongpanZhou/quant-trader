"""First batch: pure MR vs regime-base + stop overlays."""
import pickle
from pathlib import Path

import numpy as np

import engine as E

CACHE = Path(__file__).with_name("panel5.pkl")
if CACHE.exists():
    ts, o, c, feats = pickle.loads(CACHE.read_bytes())
else:
    ts, o, c, feats = E.load_panel("5min")
    feats = E.precompute_day_ref(feats, ts, c)
    CACHE.write_bytes(pickle.dumps((ts, o, c, feats)))
print("loaded", len(ts), "bars", flush=True)

runs = [
    ("pure RSI2<10 exit>60 eod", dict(signal="rsi", entry=10, exit=60, eod_flat=True, base=0.0, pnl_on="tqqq", max_bars=20)),
    ("pure RSI2<5 exit>55 eod", dict(signal="rsi", entry=5, exit=55, eod_flat=True, base=0.0, pnl_on="tqqq", max_bars=20)),
    ("pure RSI5<20 exit>60 eod", dict(signal="rsi", entry=20, exit=60, eod_flat=True, base=0.0, pnl_on="tqqq", max_bars=20)),
    ("pure boll z<-2 exit>0 eod", dict(signal="boll", entry=-2.0, exit=0.0, eod_flat=True, base=0.0, pnl_on="tqqq", max_bars=20)),
    ("pure vwap -0.25% exit 0", dict(signal="vwap", entry=-0.0025, exit=0.0, eod_flat=True, base=0.0, pnl_on="tqqq", max_bars=20)),
    ("base only (control)", dict(signal="none", entry=0, exit=0, base=1.0, pnl_on="tqqq")),
    ("base + stop_prev 1.5% QQQ", dict(signal="none", entry=0, exit=0, base=1.0, pnl_on="tqqq", stop_prev=0.015)),
    ("base + stop_prev 2.0% QQQ", dict(signal="none", entry=0, exit=0, base=1.0, pnl_on="tqqq", stop_prev=0.02)),
    ("base + stop_prev 2.5% QQQ", dict(signal="none", entry=0, exit=0, base=1.0, pnl_on="tqqq", stop_prev=0.025)),
    ("base + stop_prev 3.0% QQQ", dict(signal="none", entry=0, exit=0, base=1.0, pnl_on="tqqq", stop_prev=0.03)),
]

for name, p in runs:
    print("\n" + name, p)
    E.summarize(ts, o, c, feats, p, slip=1.0)
