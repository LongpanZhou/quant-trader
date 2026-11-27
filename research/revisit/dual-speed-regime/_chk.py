import sys; sys.path.insert(0,'.')
import strategy as S, numpy as np
ts,o,c=S.bt.panel(S.SYMS,S.DEV_START,S.DEV_END,"1min",warmup_days=500)
for kw in (dict(overnight=False, idle="bil"), dict(overnight=False, idle="cash"), dict()):
    w,info=S.build_weights(ts,o,c,**kw)
    assert np.isfinite(w).all() and (w>=0).all() and (w.sum(1)<=1+1e-12).all()
    s=S.bt.stats(S.bt.run(ts,o,c,w,S.DEV_START,0.02,1.0),S.BPY)
    print(kw, round(s['cagr']*100,2), round(s['max_drawdown']*100,2), round(s['sharpe'],3), info['entries'], info['stops'])
