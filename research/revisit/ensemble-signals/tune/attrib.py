"""Overnight vs intraday attribution by state, and a reconstruction check of the engine's daily returns."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[2]))
import bt, strategy as S
ts, o, c = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
w, info = S.build_weights(ts, o, c)
r = bt.run(ts, o, c, w, S.DEV_START, band=0.0, slippage_bps=0.0)
d = pd.Series(bt.session_dates(ts))
bod = np.r_[0, np.flatnonzero(d.values[1:] != d.values[:-1]) + 1]; eod = np.r_[bod[1:], len(ts)] - 1
# holdings during day D intraday = w at first bar of D (filled at open of bar b+1.. approx) ; overnight into D = w at eod of D-1
rows = []
for k in range(1, len(bod)):
    b, e, pe = bod[k], eod[k], eod[k-1]
    on = c[pe]; op = o[b]; cl = c[e]
    w_on = w[pe-1]  # position held at D-1 close (filled at bar pe open from w[pe-1])
    w_id = w[pe]    # filled at D open
    ron = (w_on * (op/on - 1)).sum(); rid = (w_id * (cl/op - 1)).sum()
    rows.append((d.values[b], ron, rid, (1+ron)*(1+rid)-1))
x = pd.DataFrame(rows, columns=["date","on","id","tot"]).set_index("date")
e = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().dropna(); er = e.pct_change().dropna(); er.index = er.index.date
j = er.index.intersection(x.index)
print("reconstruction corr %.5f, mean abs diff %.2e" % (np.corrcoef(er.loc[j], x.tot.loc[j])[0,1], np.abs(er.loc[j]-x.tot.loc[j]).mean()))
# state per day
daily = S.daily_closes(ts, c); p = S.DEFAULTS
rf = S._realized_vol(daily, 5); rm = S._realized_vol(daily, 20); pct = S._percentile_rank(rm, 252); sl = rf/rm-1
raw = np.array([S._raw_state(pct.iloc[i], sl.iloc[i], stress_pct=.8, calm_pct=.3, stress_slope=.1, complacency_slope=.25) for i in range(len(daily))], dtype=object)
st = pd.Series(S._state_path(raw, sl.to_numpy(float), min_hold=5, max_recovery=20, reaccel_slope=.5), index=daily.index.date)
x["state"] = st
x = x.loc[x.index >= pd.Timestamp(S.DEV_START).date()]
print(x.groupby("state")[["on","id"]].apply(lambda g: np.log1p(g).sum()).round(3))
# TQQQ overnight vs intraday in recovery days
tq_on=[]; tq_id=[]
for k in range(1,len(bod)):
    b,e,pe=bod[k],eod[k],eod[k-1]; tq_on.append(o[b,1]/c[pe,1]-1); tq_id.append(c[e,1]/o[b,1]-1)
t = pd.DataFrame({"on":tq_on,"id":tq_id}, index=[d.values[bod[k]] for k in range(1,len(bod))]); t["state"]=st
print("TQQQ by state (on / id log sums)"); print(t.groupby("state")[["on","id"]].apply(lambda g: np.log1p(g).sum()).round(3))
