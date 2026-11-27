"""Diagnostics for the risk-off late-rally effect."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import lib

ts, opens, closes = lib.load_panel()
uniq, sess, mins = lib.session_info(ts)
n_sess = len(uniq)
wd = lib.winner_daily(ts, opens, closes)
starts, ends = wd["starts"], wd["ends"]

def ps(col, minute, asset=0):
    out = np.full(n_sess, np.nan)
    sel = mins == minute
    out[sess[sel]] = col[sel, asset]
    return out

prev_c = pd.Series(wd["qclose"]).shift(1).to_numpy()
# QQQ prices
q = {m: ps(closes, m, 0) for m in [329, 359, 388, 389, 300, 270, 240, 210, 180, 120, 60]}
# TQQQ
t = {m: ps(closes, m, 1) for m in [329, 359, 388, 389, 300, 270, 240, 210, 180, 120, 60]}
qo = {m: ps(opens, m, 0) for m in [330, 360, 390, 301, 271, 241, 211, 181, 121, 61]}
to = {m: ps(opens, m, 1) for m in [330, 360, 390, 301, 271, 241, 211, 181, 121, 61, 0]}

run = q[329] / prev_c - 1
test = pd.DataFrame({"date": uniq, "risk_on": wd["risk_on"], "run": run})
for m in q:
    test[f"q{m}"] = q[m]
    test[f"t{m}"] = t[m]
test["qo330"] = qo[330]; test["to330"] = to[330]
test["qo360"] = qo[360]; test["to360"] = to[360]
test["qo390"] = qo[390]; test["to390"] = to[390]
for m in [61, 121, 181, 211, 241, 271, 301, 331]:
    if m in qo:
        test[f"qo{m}"] = qo[m]
    if m in to:
        test[f"to{m}"] = to[m]

test["late60"] = test["t388"] / test["to330"] - 1
test["late30"] = test["t388"] / test["to360"] - 1
test["first30"] = test["t359"] / test["to330"] - 1
test["last30"] = test["t388"] / test["to360"] - 1
test["final_min"] = test["t389"] / test["t388"] - 1
test["day"] = test["t389"] / test["t388"].shift(1) - 1
# next session open: shift the 09:30 open back one session
next_open = np.full(n_sess, np.nan)
next_open[:-1] = to[0][1:]
test["on_next"] = next_open / test["t389"] - 1
test["prev_c"] = prev_c
test = test[test["date"] >= pd.Timestamp("2017-01-03", tz="America/New_York")].copy()

m = (~test["risk_on"]) & (test["run"] > 0.015)
sub = test[m]
print("risk-off run>1.5%:", len(sub))
for col in ["first30", "last30", "final_min", "late60", "on_next"]:
    r = sub[col].dropna()
    print(f"  {col:10s} mean {r.mean()*1e4:7.2f}bp  med {r.median()*1e4:7.2f}  hit {(r>0).mean():.2f}  t {r.mean()/(r.std(ddof=1)/np.sqrt(len(r))):.2f}")

print("\nAll risk-off up days by run bucket: first30/last30")
sub2 = test[~test["risk_on"]].copy()
sub2["bucket"] = pd.cut(sub2["run"]*100, [-99, -2, -1, 0, 1, 2, 3, 99])
for b, g in sub2.groupby("bucket", observed=True):
    print(f"  {str(b):12s} n={len(g):4d} first30 {g.first30.mean()*1e4:7.2f}bp last30 {g.last30.mean()*1e4:7.2f}bp "
          f"60m {g.late60.mean()*1e4:7.2f}bp on {g.on_next.mean()*1e4:7.2f}bp")

print("\nEntry-time falsification for risk-off run>1.5% (QQQ avg fwd return to 15:59)")
for entry_min, label in [(240, "13:00"), (270, "13:30"), (300, "14:00"), (329, "14:59")]:
    sig = test[f"q{entry_min}"] / test["prev_c"] - 1
    mask = (~test["risk_on"]) & (sig > 0.015)
    entry_open = test[f"to{entry_min + 1}"]
    r = (test["t388"] / entry_open - 1)[mask]
    hours = (388 - entry_min) / 60.0
    print(f"  entry {label}: n={mask.sum():3d}  TQQQ fwd mean {r.mean()*1e4:7.2f}bp  "
          f"per-hour {r.mean()*1e4/hours:6.2f}bp  hit {(r>0).mean():.2f}")

print("\nExtreme late-day reversal tests (final 30m after a weak prior 30m)")
test["r1500_1530"] = test["q359"] / test["qo330"] - 1
for rs in [True, False]:
    for th in [-0.005, -0.01, -0.015, -0.02]:
        mask = (test["risk_on"] == rs) & (test["r1500_1530"] < th)
        r = test.loc[mask, "last30"].dropna()
        print(f"  regime={rs} r1500_1530<{th*100:.1f}% n={len(r):3d} last30 {r.mean()*1e4:7.2f}bp hit {(r>0).mean():.2f}")

print("\nConditional overnight after risk-off moderate decline")
for lo, hi in [(-0.02, -0.01), (-0.01, -0.005), (-0.005, 0), (0, 0.005)]:
    mask = (~test["risk_on"]) & (test["run"] >= lo) & (test["run"] < hi)
    r = test.loc[mask, "on_next"].dropna()
    print(f"  run [{lo*100:.1f},{hi*100:.1f}) n={len(r):3d} overnight {r.mean()*1e4:7.2f}bp hit {(r>0).mean():.2f}")

test.to_pickle(HERE / "daily2.pkl")
print("\nsaved daily2.pkl")
