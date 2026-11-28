"""Step-2 diagnosis for ensemble-signals (dev only)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[2]))
import bt, strategy as S

ts, o, c = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
w, info = S.build_weights(ts, o, c)
i0 = bt.start_index(ts, S.DEV_START)
ww = w[i0:]
print("exposure frac minutes QQQ>0 %.3f TQQQ>0 %.3f BIL>0.999 %.3f" % ((ww[:,0]>0).mean(), (ww[:,1]>0).mean(), (ww[:,2]>0.999).mean()))
print("avg weights", ww.mean(0), "avg gross lev", (ww[:,0]+3*ww[:,1]).mean())

def dret(r):
    e = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().dropna(); return e.pct_change().dropna()
res = {b: bt.run(ts,o,c,w,S.DEV_START,band=0.02,slippage_bps=b) for b in (1,5,10)}
for b,r in res.items():
    s = bt.stats(r, S.BARS_PER_YEAR); print(b,"bp cagr %.4f dd %.4f sh %.3f fills %d turnover %.1f" % (s["cagr"],s["max_drawdown"],s["sharpe"],s["fills"],s["turnover"]))
r1 = res[1]; yrs = bt.stats(r1,S.BARS_PER_YEAR)["years"]
print("trades/yr %.1f, turnover/yr %.2f" % (r1["fills"]/yrs, r1["turnover"]/yrs))

# benchmarks + leverage matched
lev = (ww[:,0]+3*ww[:,1]).mean()
def static(wq, wt):
    m = np.zeros_like(w); m[:,0]=wq; m[:,1]=wt; m[:,2]=1-wq-wt; return m
bm = {"TQQQ": static(0,1), "QQQ": static(1,0), "levmatch_TQQQ": static(0,lev/3), "QQQ_avgw": static(ww[:,0].mean(),0)}
bmr = {k: bt.run(ts,o,c,m,S.DEV_START,band=0.02,slippage_bps=1) for k,m in bm.items()}
for k,r in bmr.items():
    s=bt.stats(r,S.BARS_PER_YEAR); print(k,"cagr %.4f dd %.4f sh %.3f" % (s["cagr"],s["max_drawdown"],s["sharpe"]))

# per-year
def yr(r):
    e = pd.Series(r["equity"], index=r["ts"]); g = e.groupby(e.index.year); return g.last()/g.first()-1
tab = pd.DataFrame({"strat": yr(r1), "TQQQ": yr(bmr["TQQQ"]), "QQQ": yr(bmr["QQQ"]), "levmatch": yr(bmr["levmatch_TQQQ"])})
print(tab.round(4))

# state attribution
daily = S.daily_closes(ts, c)
# rebuild states
p = S.DEFAULTS
rv_fast = S._realized_vol(daily, p["vol_fast"]); rv_mid = S._realized_vol(daily, p["vol_mid"])
pct = S._percentile_rank(rv_mid, p["pct_window"]); slope = rv_fast/rv_mid - 1
raw = np.array([S._raw_state(pct.iloc[i], slope.iloc[i], stress_pct=p["stress_pct"], calm_pct=p["calm_pct"], stress_slope=p["stress_slope"], complacency_slope=p["complacency_slope"]) for i in range(len(daily))], dtype=object)
st = S._state_path(raw, slope.to_numpy(float), min_hold=p["min_hold"], max_recovery=p["max_recovery"], reaccel_slope=p["reaccel_slope"])
st = pd.Series(st, index=pd.Index(daily.index.date))
print("pct NaN days:", int(pct.isna().sum()), "first valid", pct.first_valid_index())
sr = dret(r1); sr.index = sr.index.date
dq = dret(bmr["QQQ"]); dq.index = dq.index.date
dt = dret(bmr["TQQQ"]); dt.index = dt.index.date
df = pd.DataFrame({"s": sr, "q": dq, "t": dt, "state": st}).dropna()
g = df.groupby("state")
print(pd.DataFrame({"days": g.size(), "strat_sum_logret": g["s"].apply(lambda x: np.log1p(x).sum()), "qqq_sum_logret": g["q"].apply(lambda x: np.log1p(x).sum()), "tqqq_sum_logret": g["t"].apply(lambda x: np.log1p(x).sum())}).round(3))
for per,(a,b) in {"16-19":("2016","2019"),"20-21":("2020","2021"),"22-23":("2022","2023")}.items():
    sub = df[(pd.to_datetime(df.index) >= a) & (pd.to_datetime(df.index) <= b+"-12-31")]
    print(per, sub.groupby("state")["s"].apply(lambda x: round(np.log1p(x).sum(),3)).to_dict(), "tqqq in rec:", round(np.log1p(sub[sub.state=="recovery"]["t"]).sum(),3))
# missed up days: BIL state days where QQQ up
off = df[df.state.isin(["panic","complacency"])]
print("off-days QQQ sum logret %.3f, TQQQ %.3f" % (np.log1p(off.q).sum(), np.log1p(off.t).sum()))
# recovery events: forward excess TQQQ-QQQ from entry
rec = (st=="recovery"); ent = rec & ~rec.shift(1, fill_value=False)
dates = list(st.index); qd = daily.copy(); qd.index = qd.index.date
td = pd.Series(c[:,1], index=ts).resample("1D").last().dropna(); td.index=td.index.date
ent_dates = [d for d in st.index[ent.values]]
print("recovery entries", len(ent_dates))
rng = np.random.default_rng(0)
for H in (5,10,20):
    ex=[]; tq=[]
    for d in ent_dates:
        k = dates.index(d)
        if k-1<0 or k-1+H >= len(dates): continue
        a, b2 = dates[k-1], dates[k-1+H]   # state for day k is known at close k-1
        ex.append(td[b2]/td[a]-qd[b2]/qd[a]); tq.append(td[b2]/td[a]-1)
    ex=np.array(ex); tq=np.array(tq)
    boot = np.array([rng.choice(ex, len(ex)).mean() for _ in range(5000)])
    # unconditional: all days
    allex = []
    for k in range(1, len(dates)-H):
        a,b2=dates[k-1],dates[k-1+H]; allex.append(td[b2]/td[a]-qd[b2]/qd[a])
    allex=np.array(allex)
    perm = np.array([rng.choice(allex, len(ex)).mean() for _ in range(5000)])
    print(f"H={H} n={len(ex)} mean TQQQ-QQQ {ex.mean():.4f} hit {np.mean(ex>0):.2f} TQQQ mean {tq.mean():.4f} hit {np.mean(tq>0):.2f} boot p(mean<=0) {np.mean(boot<=0):.3f} | uncond mean {allex.mean():.4f} random-date p {np.mean(perm>=ex.mean()):.3f}")
# corr with QQQ
print("corr strat vs QQQ daily %.3f, vs TQQQ %.3f" % (df.s.corr(df.q), df.s.corr(df.t)))
