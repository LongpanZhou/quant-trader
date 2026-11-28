import numpy as np, pandas as pd
from common import *

ts, O, C, H, L, dates, first, last = load()
w, info = S.build_weights(ts, O, C, H, L)
ev = pd.DataFrame(info["events"])
print("events total", len(ev), "first", ev.date.min(), "last", ev.date.max())
ev_dev = ev[(ev.date >= DEV0) & (ev.date <= DEV1)]
print("events in dev", len(ev_dev))
print(ev.to_string())

sig = info["signal"]; sd = sig[(sig.date >= pd.Timestamp(DEV0).date()) & (sig.date <= pd.Timestamp(DEV1).date())]
print("funnel (dev sessions):", len(sd))
m = np.ones(len(sd), bool)
for col in ["band", "weak", "stress", "gap_open", "confirm"]:
    m &= sd[col].to_numpy(bool); print(f"  & {col}: {m.sum()}   (alone: {sd[col].sum()})")

# missing-minute check: f+30 must be 10:00, f+31 10:01
bad = [(str(dates[f]), str(ts[f+30].time())) for f, l in zip(first, last) if f + 31 <= l and (ts[f+30].hour, ts[f+30].minute) != (10, 0)]
print("sessions where f+30 != 10:00:", len(bad), bad[:20])
bad0 = [str(dates[f]) for f in first if (ts[f].hour, ts[f].minute) != (9, 30)]
print("sessions not starting 09:30:", len(bad0), bad0[:10])

# lookahead in the skip rule: entry<=target uses bar f+31 open
i0, i1 = dev_slice(ts)
wd = w[i0:i1]
print("minutes short frac", (wd[:, 3] > 0).mean(), "avg short gross", wd[:, 3].mean(), "BIL avg", wd[:, 2].mean())
print("avg size when short", wd[wd[:, 3] > 0, 3].mean())

res = {}
for slip in (1, 5, 10):
    r, s = sim(ts, O, C, w, slip); res[slip] = (r, s)
    print(f"{slip}bp cagr {s['cagr']:.4%} dd {s['max_drawdown']:.4%} sharpe {s['sharpe']:.3f} fills {s['fills']}")
wb = np.zeros_like(w); wb[:, 2] = 1
rb, sb = sim(ts, O, C, wb, 1); print("all-BIL cagr", sb["cagr"])
# excess over BIL
rs = res[1][0]
excess = rs["equity"][-1] / rb["equity"][-1]
print("terminal excess over BIL", excess - 1)

# leverage-matched static: avg gross g in short QQQ; TQQQ mix at g/3
g = wd[:, 3].mean()
for lab, col, frac in (("TQQQ static g/3", 1, g / 3), ("QQQ static g", 0, g), ("short-QQQ static (always) g", None, g)):
    ww = np.zeros_like(w); ww[:, 2] = 1 - frac
    if col is not None:
        ww[:, col] = frac
        r, s = sim(ts, O, C, ww, 1); print(lab, f"{frac:.5f}", f"cagr {s['cagr']:.4%} dd {s['max_drawdown']:.4%}")

# per-year
tq = pd.Series(C[i0:i1, 1], index=ts[i0:i1]); qq = pd.Series(C[i0:i1, 0], index=ts[i0:i1])
eq = pd.Series(rs["equity"], index=rs["ts"]); eb = pd.Series(rb["equity"], index=rb["ts"])
yr = lambda s: s.groupby(s.index.year).last() / s.groupby(s.index.year).first().shift(0) - 1
def yret(s):
    g = s.groupby(s.index.year); lastv = g.last(); prev = lastv.shift(1); prev.iloc[0] = g.first().iloc[0]
    return lastv / prev - 1
tab = pd.DataFrame({"strat": yret(eq), "BIL": yret(eb), "TQQQ": yret(tq), "QQQ": yret(qq)})
tab["events"] = ev_dev.groupby(pd.to_datetime(ev_dev.date).dt.year).size()
print(tab.to_string(float_format=lambda x: f"{x:.4f}"))

# correlation vs baseline
wbase = baseline_165(ts, C, first, last)
rbase, sbase = sim(ts, O, C, wbase, 1)
print("baseline cagr", sbase["cagr"], "dd", sbase["max_drawdown"])
d1, d2 = daily(rs), daily(rbase)
print("corr vs 165d baseline", d1.corr(d2.reindex(d1.index)))
print("corr vs QQQ daily", d1.corr(qq.groupby(qq.index.date).last().pct_change().reindex(d1.index)))

# events: per-event pnl, gross gain in $ terms
ev_dev = ev_dev.assign(net1=ev_dev.gross_ret + ev_dev.borrow_ret - 2e-4)
print(ev_dev[["gross_ret", "net1", "size", "hold_min"]].describe())
print("contribution of events (sum size*net1)", (ev_dev["size"] * ev_dev.net1).sum())
