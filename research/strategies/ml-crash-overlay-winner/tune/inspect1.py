import sys, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, r"C:\Users\27175\Desktop\quant-trader-research\research\strategies\ml-crash-overlay-winner")
import numpy as np, pandas as pd
import strategy as S, bt
ts1,o1,c1 = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min")
tsd,od,cd = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1D")
print(ts1[0], ts1[-1], len(ts1), tsd[0], tsd[-1], len(tsd), ts1.dtype, tsd.dtype)
w1, wd, state, p, y, rank, decay, info = S.build_weights(ts1,o1,c1,tsd,od,cd)
dts = pd.DatetimeIndex(tsd).tz_localize(None)
df = pd.DataFrame({"p":p,"y":y,"rank":rank,"state":state,"decay":decay}, index=dts)
print(df.groupby(df.index.year).agg(pn=("p",lambda s:s.notna().sum()), rn=("rank",lambda s:s.notna().sum()),
   s0=("state",lambda s:(s==0).sum()), s1=("state",lambda s:(s==1).sum()), s2=("state",lambda s:(s==2).sum())))
# warm-up check of training rows for 2016
print("first decay finite", dts[np.isfinite(decay)][0])
# daily feature NaN coverage at start
vol = bt.load_1m("QQQ").set_index("ts")["volume"].reindex(ts1).fillna(0.0).to_numpy()
f = S.build_features(ts1,o1,c1,np.column_stack([vol,vol,vol]))
print(f.index[:3], len(f), f.index.dtype if hasattr(f.index,'dtype') else None)
f.index = pd.DatetimeIndex(f.index); ff = f.reindex(dts)
print("rows missing after reindex:", ff.isna().all(axis=1).sum())
# weights mapping check: for dev days, minute weight at last bar of day d == wd[d]
d1 = ts1.normalize()
k = pd.DatetimeIndex(tsd).normalize().get_indexer(d1)
last = np.r_[k[1:]!=k[:-1], True]
print("last-bar weights match daily:", np.allclose(w1[last], wd[k[last]]))
print("first-bar weights == previous day:", np.allclose(w1[~last][1:], wd[np.maximum(k[~last][1:]-1,0)]))
np.save(r"C:\Users\27175\AppData\Local\Temp\claude\cef8dbb02f8436d7\5e4b52c1-fe98-41b3-a7bc-7944fabb5f47\scratchpad\w1_before.npy", w1)
