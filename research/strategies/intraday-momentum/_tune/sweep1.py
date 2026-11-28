import numpy as np, json
from common import *  # noqa
from vlib import build
ts, o, c = panel()
w0, _ = S.build_weights(ts, o, c)
wv, _ = build(ts, o, c)
print("V0 reproduces strategy:", np.array_equal(w0, wv))
V = {
 "V0 frozen sp+ fh+ 0/1/3x": dict(),
 "V1 sp only, BIL/QQQ": dict(legs=(("sp", 1),), ladder=("BIL", "QQQ")),
 "V1b sp only, BIL/TQQQ": dict(legs=(("sp", 1),), ladder=("BIL", "TQQQ")),
 "V2 sp+ fh- 0/1/3x": dict(legs=(("sp", 1), ("fh", -1))),
 "V3 fh- only, BIL/TQQQ": dict(legs=(("fh", -1),), ladder=("BIL", "TQQQ")),
 "V3b fh- only, BIL/QQQ": dict(legs=(("fh", -1),), ladder=("BIL", "QQQ")),
 "V4 idr- only, BIL/TQQQ": dict(legs=(("idr", -1),), ladder=("BIL", "TQQQ")),
 "P ret5- only, BIL/TQQQ (plain reversal comparator)": dict(legs=(("ret5", -1),), ladder=("BIL", "TQQQ")),
 "V0x frozen, median excl current": dict(incl=False),
}
ws = {}; sts = {}
for k, kw in V.items():
    ws[k], sts[k] = build(ts, o, c, **kw)
out = {}
for slip in (1.0, 5.0, 10.0):
    rs = run_many(list(ws.values()), slip)
    for k, r in zip(ws, rs):
        s = stats(r); d = out.setdefault(k, {})
        d[f"{int(slip)}bp"] = (round(s["cagr"]*100, 2), round(s["max_drawdown"]*100, 2), round(s["sharpe"], 2), int(s["fills"]))
        if slip == 1.0:
            d["corr"] = round(corr_base(r), 3)
            d["sub"] = {k2: round(v*100, 1) for k2, v in sub_cagr(r).items()}
            d["states"] = {s_: sts[k].count(s_) for s_ in set(sts[k])}
for k, d in out.items():
    print(k); print("   ", d)
with open(HERE / "sweep1.json", "w", newline="\n", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
