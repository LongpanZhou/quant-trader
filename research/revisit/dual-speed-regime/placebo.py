"""Random circular-shift placebo (whole-session shifts), matched exposure and turnover. Dev only."""
import sys, numpy as np
sys.path.insert(0, '.')
from sweep import *
rng = np.random.default_rng(7)
for nm, kw in (("ON (overnight, cash, no tiers)", dict(overnight=True, idle="cash", tiers=False)),
               ("ONT (overnight, cash, tiers)", dict(overnight=True, idle="cash"))):
    w = build(**kw); h = w[:, 1]
    real = bt.stats(bt.run(ts, o, c, w, S.DEV_START, 0.02, 1.0), S.BPY)
    ws = []
    full = np.flatnonzero((last - first + 1) == 390)
    for rep in range(100):
        k = int(rng.integers(20, len(first) - 20))
        sh = first[k]
        hp = np.roll(h, sh)
        wp = np.zeros_like(w); wp[:, 1] = hp
        ws.append(wp)
    rr = bt.run_many(ts, o, c, ws, S.DEV_START, 0.02, 1.0, threads=1)
    cg = np.array([bt.stats(r, S.BPY)["cagr"] for r in rr]); sp = np.array([bt.stats(r, S.BPY)["sharpe"] for r in rr])
    print(f"{nm}: real CAGR {real['cagr']*100:.2f}% Sharpe {real['sharpe']:.2f}; placebo CAGR mean {cg.mean()*100:.2f}% "
          f"p95 {np.percentile(cg,95)*100:.2f}%; Sharpe mean {sp.mean():.2f} p95 {np.percentile(sp,95):.2f}; "
          f"p(placebo Sharpe >= real) = {np.mean(sp >= real['sharpe']):.2f}")
    # static leverage-matched, cash and BIL
    a = h.mean()
    for idle in ("cash", "bil"):
        wsx = np.zeros_like(w); wsx[:, 1] = a
        if idle == "bil": wsx[:, 2] = 1 - a
        s = bt.stats(bt.run(ts, o, c, wsx, S.DEV_START, 0.02, 1.0), S.BPY)
        print(f"   static {a:.2f} TQQQ / {idle}: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.1f}% Sharpe {s['sharpe']:.2f}")
