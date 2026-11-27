"""Batch 4: genuine MR variants, one trade/day, hold to EOD or signal exit."""
import engine3 as E

ts, o, c, feats = E.load_cached()
print("bars", len(ts), flush=True)

runs = [
    # M1 RSI2 dips, 09:35-14:30 entries, exit RSI>60 or EOD
    ("M1 rsi2<5 exit>60", dict(signal="rsi2", base=0.0, entry=5, exit=60, exit_bar=75,
                               entry_bars=(1, 66))),
    ("M1b rsi2<10 exit>60", dict(signal="rsi2", base=0.0, entry=10, exit=60, exit_bar=75,
                                 entry_bars=(1, 66))),
    ("M1c rsi2<10 exit>70 hold20", dict(signal="rsi2", base=0.0, entry=10, exit=70, exit_bar=75,
                                        entry_bars=(1, 66), max_bars=20)),
    # M2 Bollinger 20,2 lower band
    ("M2 boll z<-2 exit>0", dict(signal="boll", base=0.0, entry=-2.0, exit=0.0, exit_bar=75,
                                 entry_bars=(1, 66))),
    ("M2b boll z<-2.5 exit>0.5", dict(signal="boll", base=0.0, entry=-2.5, exit=0.5, exit_bar=75,
                                      entry_bars=(1, 66))),
    # M3 VWAP deviation
    ("M3 vwap <-0.25% exit>0", dict(signal="vwap", base=0.0, entry=-0.0025, exit=0.0, exit_bar=75,
                                    entry_bars=(1, 66))),
    ("M3b vwap <-0.40% exit>0", dict(signal="vwap", base=0.0, entry=-0.0040, exit=0.0, exit_bar=75,
                                     entry_bars=(1, 66))),
    # M4 morning capitulation: QQQ down >1% from open before 11:00
    ("M4 drop<-1% before 11:00", dict(signal="drop", base=0.0, entry=-0.010, exit=0.0, exit_bar=75,
                                      entry_bars=(1, 18))),
    ("M4b drop<-1.5% before 12:00", dict(signal="drop", base=0.0, entry=-0.015, exit=0.0, exit_bar=75,
                                         entry_bars=(1, 30))),
    # M5 regime base + MR add-on: buy extra when dip is deep (still same 100% cap) - control
    ("M6 base + stop 3% (prev best)", dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=0.03)),
]

for name, p in runs:
    print("\n" + name)
    E.run_one(ts, o, c, feats, p, slip=1.0)
