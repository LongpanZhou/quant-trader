"""Phase-tranched versions (average of the 5 rebalance phases) + static mixes + random placebo. Dev only."""
import numpy as np, json
from common import *  # noqa
from vlib import build
ts, o, c = panel()
cfg = {
 "V0 frozen": dict(),
 "V1 sp-only BIL/QQQ": dict(legs=(("sp", 1),), ladder=("BIL", "QQQ")),
 "V1b sp-only BIL/TQQQ": dict(legs=(("sp", 1),), ladder=("BIL", "TQQQ")),
 "V2 sp+ fh-": dict(legs=(("sp", 1), ("fh", -1))),
 "V3 fh- BIL/TQQQ": dict(legs=(("fh", -1),), ladder=("BIL", "TQQQ")),
 "V3b fh- BIL/QQQ": dict(legs=(("fh", -1),), ladder=("BIL", "QQQ")),
 "P ret5- BIL/TQQQ": dict(legs=(("ret5", -1),), ladder=("BIL", "TQQQ")),
}
def tranched(kw):
    acc = None; sts = []
    for off in range(5):
        w, s = build(ts, o, c, offset=off, **kw)
        acc = w if acc is None else acc + w
        sts += s
    return acc / 5, sts
ws = {}; meta = {}
for k, kw in cfg.items():
    ws["T5 " + k], st = tranched(kw)
    meta["T5 " + k] = {s_: st.count(s_) / len(st) for s_ in set(st)}
def static(wq, wt):
    m = np.zeros((len(ts), 3)); m[:, 0] = wq; m[:, 1] = wt; m[:, 2] = 1 - wq - wt; return m
ws["static TQQQ50/BIL50"] = static(0, 0.5)
ws["static QQQ50/BIL50"] = static(0.5, 0)
out = {}
keys = list(ws)
for slip in (1.0, 5.0, 10.0):
    rs = run_many([ws[k] for k in keys], slip)
    for k, r in zip(keys, rs):
        s = stats(r); d = out.setdefault(k, {})
        d[f"{int(slip)}bp"] = [round(s["cagr"]*100, 2), round(s["max_drawdown"]*100, 2), round(s["sharpe"], 2), int(s["fills"])]
        if slip == 1.0:
            d["corr"] = round(corr_base(r), 3); d["sub"] = [round(v*100, 1) for v in sub_cagr(r).values()]
            d["avg_lev"] = round(float((ws[k][:, 0] + 3 * ws[k][:, 1]).mean()), 3)
for k, d in out.items():
    print(f"{k:28s} {d}  {meta.get(k, '')}")
# random placebo for V3 (single phase) and for the tranched V3: random states, same TQQQ frequency
rng = np.random.default_rng(42)
_, st3 = build(ts, o, c, **cfg["V3 fh- BIL/TQQQ"])
pt = np.mean([s == "TQQQ" for s in st3])
pl = []
for batch in range(10):
    wl = []
    for j in range(20):
        acc = 0
        for off in range(5):
            n_ = len(build(ts, o, c, offset=off, **cfg["V3 fh- BIL/TQQQ"])[1]) if batch == 0 and j == 0 else None
            break
        sts = list(np.where(rng.random(len(st3)) < pt, "TQQQ", "BIL"))
        wl.append(build(ts, o, c, states_override=sts, **cfg["V3 fh- BIL/TQQQ"])[0])
    for r in run_many(wl, 1.0):
        s = stats(r); pl.append((s["cagr"], s["max_drawdown"], s["sharpe"]))
pl = np.array(pl)
v3 = out.get("T5 V3 fh- BIL/TQQQ")
res = {"placebo_n": len(pl), "tqqq_freq": float(pt),
       "cagr_pct": np.percentile(pl[:, 0]*100, [5, 50, 95]).round(2).tolist(),
       "dd_pct": np.percentile(pl[:, 1]*100, [5, 50, 95]).round(2).tolist(),
       "sharpe_pct": np.percentile(pl[:, 2], [5, 50, 95]).round(2).tolist()}
for name, val in (("single-phase V3 cagr 48.53", 0.4853), ("phase-avg V3", None)):
    pass
res["share_placebo_cagr_ge_48.53"] = float((pl[:, 0] >= 0.4853).mean())
res["share_placebo_cagr_ge_T5V3"] = float((pl[:, 0] * 100 >= out["T5 V3 fh- BIL/TQQQ"]["1bp"][0]).mean())
res["share_placebo_sharpe_ge_T5V3"] = float((pl[:, 2] >= out["T5 V3 fh- BIL/TQQQ"]["1bp"][2]).mean())
print(res)
out["placebo_V3"] = res
with open(HERE / "sweep3.json", "w", newline="\n", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
