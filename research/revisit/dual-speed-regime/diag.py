"""Tuning diagnostics for dual-speed-regime (development period only)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, '.')
import strategy as S
bt = S.bt
ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
dates, first, last, day_id = S.day_index(ts)
n = len(ts)
w, info = S.build_weights(ts, o, c)
h = w[:, 1]

def st(wm, slip=1.0):
    r = bt.run(ts, o, c, wm, S.DEV_START, 0.02, slip)
    s = bt.stats(r, S.BPY); s["r"] = r; return s

def line(name, s):
    return f"| {name} | {s['cagr']*100:.2f}% | {s['max_drawdown']*100:.2f}% | {s['sharpe']:.2f} |"

wb = S.baseline_165_for_correlation(ts, c, first, last, day_id)
rb = bt.run(ts, o, c, wb, S.DEV_START, 0.02, 1.0)
db = S.daily_returns(rb["equity"], rb["ts"])
def corr(s):
    a = S.daily_returns(s["r"]["equity"], s["r"]["ts"])
    j = pd.concat([a, db], axis=1, join="inner").dropna()
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))

out = {}
print("## exposure")
print(f"minutes TQQQ>0: {np.mean(h>0):.3f}; BIL>0: {np.mean(w[:,2]>0):.3f}; QQQ 0; short 0")
print(f"avg TQQQ weight {h.mean():.3f}; avg gross leverage (3x TQQQ) {3*h.mean():.3f}; when long {3*h[h>0].mean():.2f}")
# share of exposure by tier
print(f"minutes at 100%: {np.mean(h==1):.3f}, at 50%: {np.mean(h==0.5):.3f}")

print("## costs")
for slip in (0, 1, 5, 10):
    s = st(w, slip); print(line(f"strategy {slip}bp", s), f"fills/yr {s['fills']/s['years']:.0f}")
s1 = st(w, 1.0)
yrs = s1["years"]
print("corr vs 165d:", round(corr(s1), 3))

print("## leverage-matched static and placebos (1bp)")
avg = h.mean()
ws = np.zeros((n, 3)); ws[:, 1] = avg; ws[:, 2] = 1 - avg
s = st(ws); print(line(f"static {avg:.2f} TQQQ / BIL", s), "corr", round(corr(s), 3))
# daily-rebalanced static
ws2 = ws.copy()
# intraday buy-and-hold 10:30-15:30 at the strategy's average size when long
sz = h[h > 0].mean()
wi = np.zeros((n, 3)); wi[:, 2] = 1.0
for f, l in zip(first, last):
    L = l - f + 1
    a = f + 59
    z = f + 359 if L >= 390 else (f + 179 if L < 300 else f + (L // 60 - 1) * 60 - 1)
    wi[a:z, 1] = sz; wi[a:z, 2] = 1 - sz
s = st(wi); print(line(f"intraday TQQQ {sz:.2f} 10:30-15:30 every day", s), "corr", round(corr(s), 3))
wi0 = wi.copy(); wi0[:, 2] = 0
s = st(wi0); print(line("  same, cash instead of BIL", s))
s = st(wi, 0); print(line("  same, 0bp", s))
# lagged EMA: shift the spread one 60m bar -> emulate by shifting the hold profile by 60 minutes is not the same; do proper lag
import types
orig_ema = S.ema
def lagged(x, span):
    e = orig_ema(x, span); return np.r_[e[0], e[:-1]]
S.ema = lagged
wl, _ = S.build_weights(ts, o, c); S.ema = orig_ema
s = st(wl); print(line("lagged-EMA (1 bar) placebo", s))
# random-day permutation placebo: same intraday profile, assigned to random days
rng = np.random.default_rng(0)
full = [k for k in range(len(first)) if last[k] - first[k] + 1 == 390]
prof = {k: h[first[k]:last[k] + 1] for k in full}
res = []
for rep in range(20):
    perm = rng.permutation(full)
    wp = np.zeros((n, 3))
    hp = h.copy()
    for k, k2 in zip(full, perm):
        hp[first[k]:last[k] + 1] = prof[k2]
    wp[:, 1] = hp; wp[:, 2] = 1 - hp
    res.append(wp)
rr = bt.run_many(ts, o, c, res, S.DEV_START, 0.02, 1.0, threads=1)
cg = np.array([bt.stats(r, S.BPY)["cagr"] for r in rr]); sh = np.array([bt.stats(r, S.BPY)["sharpe"] for r in rr])
print(f"random-day permutation (20): CAGR mean {cg.mean()*100:.2f}% [{cg.min()*100:.2f},{cg.max()*100:.2f}], Sharpe mean {sh.mean():.2f} max {sh.max():.2f}; strategy beats {np.mean(s1['sharpe']>sh)*100:.0f}%")

print("## per year (1bp)")
yr = bt.yearly(s1["r"]["ts"], s1["r"]["equity"], c[:, 1])
yq = bt.yearly(ts, c[:, 0], c[:, 0])
for y in yr: print(f"| {y} | {yr[y]['strategy']*100:.1f}% | {yr[y]['benchmark']*100:.1f}% | {yq[y]['strategy']*100:.1f}% |")

print("## TQQQ return decomposition by window (sum of log returns, dev)")
T = c[:, 1]; TO = o[:, 1]
lg = {"overnight (close->open)": 0, "09:30-10:30": 0, "10:30-15:30": 0, "15:30-16:00": 0}
for k, (f, l) in enumerate(zip(first, last)):
    if k > 0: lg["overnight (close->open)"] += np.log(TO[f] / T[last[k-1]])
    L = l - f + 1
    a = f + 59; z = f + 359 if L >= 390 else min(l, f + 179)
    lg["09:30-10:30"] += np.log(T[a] / TO[f]); lg["10:30-15:30"] += np.log(T[z] / T[a]); lg["15:30-16:00"] += np.log(T[l] / T[z])
for k, v in lg.items(): print(f"| {k} | {v:+.3f} | {np.exp(v/yrs)-1:+.1%}/yr |")
# what the strategy captured in 10:30-15:30: in-position vs out of position TQQQ log return in window
mret = np.r_[0, np.log(TO[1:] / TO[:-1])]  # open-to-open; held weight at i-1 earns open[i-1]->open[i] approx
held = np.r_[0, h[:-1]] > 0
held_prev = np.r_[0, np.r_[0, h[:-2]]]
# position from fill at open i+1: weight h[i] earns open[i+1]->open[i+2]
pos = np.r_[0, 0, h[:-2]]  # weight active over interval open[i-1]->open[i]
inwin = np.zeros(n, bool)
for f, l in zip(first, last):
    inwin[f + 61:min(l, f + 361) + 1] = True
lr = np.r_[0, np.log(TO[1:] / TO[:-1])]
print(f"TQQQ log ret inside 10:30-15:30 while strategy long: {lr[inwin & (pos>0)].sum():+.3f}; while flat: {lr[inwin & (pos==0)].sum():+.3f}")
print(f"  sized (weight x TQQQ simple ret) while long: {(pos*(np.exp(lr)-1))[inwin].sum():+.3f}")

print("## trades")
seg = np.flatnonzero(np.diff(np.r_[0, (h > 0).astype(int), 0]))
st_, en_ = seg[::2], seg[1::2]   # h>0 on [st_, en_)
gr = []
for a, z in zip(st_, en_):
    if a + 1 >= n or z + 1 >= n: continue
    gr.append((TO[z + 1] / TO[a + 1] - 1, h[a]))
gr = np.array(gr)
tr = gr[:, 0]
print(f"trades {len(tr)}, per yr {len(tr)/yrs:.0f}; hit rate (TQQQ fill-to-fill > 0) {np.mean(tr>0):.3f}; mean gross {tr.mean()*1e4:.1f} bp; median {np.median(tr)*1e4:.1f} bp")
print(f"mean net of 1bp x2 TQQQ + 1bp x2 BIL: {(tr.mean()-4e-4)*1e4:.1f} bp; t-stat {tr.mean()/tr.std()*np.sqrt(len(tr)):.2f}")
# next-60m hit rate after an entry signal
