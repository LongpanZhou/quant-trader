"""Event-level decomposition of the weekly signals (dev only). Forward = next open -> close 5 sessions later."""
import numpy as np, pandas as pd
from common import *  # noqa
ts, o, c = panel()
a, b = S._sessions(ts)
nd = len(a)
q0 = o[a, 0]; q1 = c[b - 1, 0]
on = np.full(nd, np.nan); on[1:] = q0[1:] / q1[:-1] - 1
idr = q1 / q0 - 1
fh = c[a + 59, 0] / q0 - 1
rest = q1 / c[a + 59, 0] - 1  # 10:30 -> close
rebs = np.arange(9, nd - 1, 5)
rows = []
for r in rebs:
    win = slice(r - 4, r + 1)
    e = min(r + 5, nd - 1)
    rows.append(dict(r=r, year=ts[a[r]].year, on=on[win].sum(), idr=idr[win].sum(), fh=fh[win].sum(),
                     rest=rest[win].sum(), sp=(on[win] - idr[win]).sum(),
                     ret5=q1[r] / q1[r - 5] - 1, fq=c[b[e] - 1, 0] / o[a[r + 1], 0] - 1))
ev = pd.DataFrame(rows)
# rolling-median rank vs trailing 26 incl current (as in strategy), min 13
def above(x, n=26, incl=True):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        h = x[max(0, i - n + 1): i + 1] if incl else x[max(0, i - n): i]
        if len(h) >= 13:
            out[i] = x[i] > np.median(h)
    return out
per = {"16-19": (2016, 2019), "20-21": (2020, 2021), "22-23": (2022, 2023)}
print(f"{'signal':10s} {'all':>8s} " + " ".join(f"{k:>8s}" for k in per) + "   (fwd5 bp: above-median minus below)")
for col in ["sp", "on", "idr", "fh", "rest", "ret5"]:
    m = above(ev[col].to_numpy())
    ok = ~np.isnan(m); x = ev[ok].copy(); x["m"] = m[ok] > 0.5
    def spr(z): return (z[z.m].fq.mean() - z[~z.m].fq.mean()) * 1e4
    print(f"{col:10s} {spr(x):8.1f} " + " ".join(f"{spr(x[(x.year>=y0)&(x.year<=y1)]):8.1f}" for y0, y1 in per.values()))
print("raw corr of signal with fwd5:")
print(ev[["sp", "on", "idr", "fh", "rest", "ret5", "fq"]].corr()["fq"].round(3).to_dict())
