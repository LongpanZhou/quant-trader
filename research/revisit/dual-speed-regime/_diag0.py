import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
import strategy as S
ts, o, c = S.bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
print(ts.dtype, len(ts), ts[0], ts[-1])
w, info = S.build_weights(ts, o, c)
dates, first, last, day_id = S.day_index(ts)
L = last-first+1
i0 = S.bt.start_index(ts, S.DEV_START)
d0 = day_id[i0]
print("sessions", len(first), "dev sessions", len(first)-d0)
short = [(str(dates[first[k]]), L[k], str(ts[last[k]].time())) for k in range(d0, len(first)) if L[k]!=390]
print("non-390 sessions:", len(short)); print(short)
h = w[:,1]
od = [str(dates[last[k]]) for k in range(len(first)) if h[last[k]]>0]
print("days with TQQQ weight >0 at session last bar (overnight):", len(od), od)
# times of the position changes
chg = np.flatnonzero(np.diff(h)!=0)+1
tod = pd.Series([ts[i].strftime('%H:%M') for i in chg]).value_counts().head(12)
print(tod)
