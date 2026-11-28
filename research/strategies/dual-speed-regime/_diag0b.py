import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
import strategy as S
ts, o, c = S.bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
w, info = S.build_weights(ts, o, c)
dates, first, last, day_id = S.day_index(ts)
h=w[:,1]; chg = np.flatnonzero(np.diff(h)!=0)+1
print(pd.Series([ts[i].strftime('%H:%M') for i in chg]).value_counts().head(12))
print("TQQQ>0 on last 2 bars of a session:", int(sum(h[last[k]-1]>0 or h[last[k]]>0 for k in range(len(first)))))
for slip in (1,5,10):
    r=S.bt.run(ts,o,c,w,S.DEV_START,0.02,slip); st=S.bt.stats(r,S.BPY)
    print(slip, round(st['cagr']*100,2), round(st['max_drawdown']*100,2), round(st['sharpe'],3), st['fills'], round(st['turnover']))
print(info)
