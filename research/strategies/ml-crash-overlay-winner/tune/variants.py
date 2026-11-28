"""Step 3 variant grid (dev window only). Every variant tried is written to
tune/variants.json, so the count in DIAGNOSIS.md is the length of that file.

Families (state map from the model's risk rank, same min-hold/crash-exit rule):
  A  "q_tqqq"  : widen the TQQQ (low predicted decay) bucket  rank<qt->TQQQ, <qb->QQQ, else BIL
  B  "mid2x"   : middle bucket held as 50% QQQ + 50% TQQQ (2x) instead of QQQ
  V  "vol"     : family A driven by a plain rv20 rank instead of the model (does the ML add anything?)
"""
import json, itertools
from common import *

p = probs()
rank_ml = rank_of(p)
rk_vol = rank_of(F["rv20"].to_numpy()).copy(); rk_vol[dts.year == 2016] = np.nan

ROWS = {"QQQ": [1, 0, 0], "TQQQ": [0, 1, 0], "BIL": [0, 0, 1], "2x": [0.5, 0.5, 0]}


def weights(rank, qt, qb, mh, mid="QQQ"):
    _, state = S.state_weights(rank, qt, qb, mh)
    w = np.zeros((len(state), 3))
    w[state == 1] = ROWS["TQQQ"]; w[state == 0] = ROWS[mid]; w[state == 2] = ROWS["BIL"]
    return w


specs = []
for qt, qb, mh in itertools.product((0.15, 0.30, 0.45, 0.60), (0.65, 0.70, 0.75, 0.80), (3, 5, 10)):
    if qt < qb:
        specs.append(("A", qt, qb, mh, "QQQ"))
for qt, qb, mh in itertools.product((0.15, 0.30), (0.65, 0.70, 0.75), (5,)):
    specs.append(("B", qt, qb, mh, "2x"))
for qt, qb, mh in itertools.product((0.15, 0.30, 0.45, 0.60), (0.65, 0.70, 0.75, 0.80), (5,)):
    if qt < qb:
        specs.append(("V", qt, qb, mh, "QQQ"))

rows = []
B = 24
for a in range(0, len(specs), B):
    batch = specs[a:a + B]
    ws = [weights((rk_vol if f == "V" else rank_ml), qt, qb, mh, mid)
          for f, qt, qb, mh, mid in batch]
    rr = run_many(ws)
    for (f, qt, qb, mh, mid), w, r in zip(batch, ws, rr):
        s = st(r)
        row = {"family": f, "q_tqqq": qt, "q_bil": qb, "min_hold": mh, "mid": mid,
               "cagr": s["cagr"], "dd": s["max_drawdown"], "sharpe": s["sharpe"], "fills": s["fills"],
               "corr": corr_base(r), "subs": subs(r)}
        rows.append(row)
    print(a + len(batch), "/", len(specs), flush=True)
with open(HERE / "tune" / "variants.json", "w", newline="\n", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1)
for r in rows:
    sb = " ".join(f"{v['cagr']*100:6.1f}" for v in r["subs"].values())
    print(f"{r['family']} qt={r['q_tqqq']:.2f} qb={r['q_bil']:.2f} mh={r['min_hold']:2d} {r['mid']:4s} "
          f"CAGR {r['cagr']*100:6.2f} DD {r['dd']*100:5.1f} Sh {r['sharpe']:.2f} corr {r['corr']:.2f} subs {sb}")
