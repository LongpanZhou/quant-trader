"""Event-level sweep (dev only): relax filters of the gap-fill short and measure per-event edge."""
import itertools, json
import numpy as np, pandas as pd
from common import *

ts, O, C, H, L, dates, first, last = load()
o, c = O[:, 0], C[:, 0]
dc = c[last]; prior = np.r_[np.nan, dc[:-1]]
gap = o[first] / prior - 1
mod = np.array([t.hour * 60 + t.minute for t in ts])
dd = pd.to_datetime(pd.Series(dates[first]))
indev = ((dd >= DEV0) & (dd <= DEV1)).to_numpy()
yr = dd.dt.year.to_numpy()

def feats(ma):
    sma = pd.Series(dc).rolling(ma).mean().to_numpy(); smap = np.r_[np.nan, sma[:-1]]
    ret5 = pd.Series(dc).pct_change(5).shift(1).to_numpy()
    return (prior < smap) & (ret5 < 0)
vol20 = pd.Series(dc).pct_change().rolling(20).std(ddof=0).shift(1).to_numpy() * np.sqrt(252)
vmed = pd.Series(vol20).rolling(252, min_periods=60).median().to_numpy()
# signal bar by clock (10:00) where available; fall back to f+30
sigbar = np.array([f + 30 for f in first])
valid = sigbar + 1 < last
orh = np.array([H[f:f + 30].max() for f in first])

def run(gap_lo=0.001, gap_hi=0.0075, ma=10, weak_on=True, stress=1.0, confirm=0.0, conf_on=True,
        floor=0.002, cap=0.015, tstop=690, slip=1.0, entry_shift=0, side=1):
    weak = feats(ma) if weak_on else np.ones(len(first), bool)
    st = vol20 > vmed * stress if stress is not None else np.ones(len(first), bool)
    band = (gap >= gap_lo) & (gap <= gap_hi)
    sb = sigbar + entry_shift
    c10 = c[np.minimum(sb, len(c) - 1)]
    r30 = c10 / o[first] - 1
    conf = (r30 < confirm) if conf_on else np.ones(len(first), bool)
    sig = band & weak & st & (c10 > prior) & conf & valid & indev & np.isfinite(vol20) & np.isfinite(vmed)
    out = []
    for k in np.flatnonzero(sig):
        f, l = first[k], last[k]; e = sb[k] + 1
        if e >= l: continue
        ent = o[e]; tgt = prior[k]
        stop = min(max(orh[k], ent * (1 + floor)), ent * (1 + cap))
        x = l - 1; why = "eod"
        for i in range(e, l):
            if H[i] >= stop: x, why = i, "stop"; break
            if L[i] <= tgt: x, why = i, "target"; break
            if mod[i] >= tstop: x, why = i, "time"; break
        px = o[min(x + 1, l)]
        out.append((k, -(px / ent - 1) - 2 * slip / 1e4, why))
    return out

def summ(ev, nboot=4000, seed=0):
    if not ev: return dict(n=0)
    p = np.array([e[1] for e in ev]); ks = np.array([e[0] for e in ev]); n = len(p)
    rng = np.random.default_rng(seed)
    boot = rng.choice(p, size=(nboot, n)).mean(1)
    sub = {}
    for nm, a, b in (("16-19", 2016, 2019), ("20-21", 2020, 2021), ("22-23", 2022, 2023)):
        m = (yr[ks] >= a) & (yr[ks] <= b); sub[nm] = (int(m.sum()), float(p[m].mean() * 1e4) if m.any() else np.nan)
    return dict(n=n, mean_bp=p.mean() * 1e4, t=p.mean() / p.std(ddof=1) * np.sqrt(n) if n > 2 else np.nan,
                win=(p > 0).mean(), p=(boot <= 0).mean(), sub=sub)

if __name__ == "__main__":
    rows = []
    def rep(name, **kw):
        s = summ(run(**kw)); rows.append((name, s))
        sub = " ".join(f"{k}:{v[0]}/{v[1]:+.1f}" for k, v in s.get("sub", {}).items())
        print(f"{name:38s} n={s['n']:4d} mean={s.get('mean_bp', 0):+6.2f}bp t={s.get('t', 0):+5.2f} win={s.get('win', 0):.2f} p={s.get('p', 1):.3f} | {sub}")
    rep("primary")
    rep("no stress", stress=None)
    rep("no weak", weak_on=False)
    rep("no weak no stress", weak_on=False, stress=None)
    rep("no weak no stress no confirm", weak_on=False, stress=None, conf_on=False)
    rep("no confirm (placebo)", conf_on=False)
    rep("weak5", ma=5); rep("weak20", ma=20)
    rep("stress1.25", stress=1.25)
    rep("gap 0.05-0.6", gap_lo=0.0005, gap_hi=0.006); rep("gap 0.15-0.9", gap_lo=0.0015, gap_hi=0.009)
    rep("all-filters-off gap 0.1-1.5", weak_on=False, stress=None, gap_hi=0.015)
    rep("all-off tstop 12:00", weak_on=False, stress=None, tstop=720)
    rep("all-off tstop 15:58(eod)", weak_on=False, stress=None, tstop=2000)
    rep("all-off at 5bp", weak_on=False, stress=None, slip=5)
    rep("primary 5bp", slip=5)
