"""Step 3: variants, neighbourhood, sub-periods, placebo (dev only)."""
import json
from common import *

ts, o, c = load()
uniq, sess, starts, ends = sessions(ts)
sig = S.load_daily_signal()
dates = pd.DatetimeIndex(sig.index); z = sig["z"].to_numpy()
bw = baseline_w(ts)
bdr = daily_ret(ts, bt.run(ts, o, c, bw, DEV0, 0.02, 1)["equity"])
N_VAR = 0
rows = []


def renew_weights(z, hold, ze):
    """Variant R: a new signal while holding restarts the hold clock."""
    n = len(z); w = np.zeros((n, 3)); w[:, 2] = 1; rem = 0
    for t in range(n):
        fire = np.isfinite(z[t]) and z[t] < ze
        if fire:
            rem = hold
        if rem > 0:
            w[t] = (0, 1, 0); rem -= 1
    return w


def evaluate(name, wd_daily, risk=1, idle=2, extra=None):
    global N_VAR
    N_VAR += 1
    wd_ = wd_daily.copy()
    if risk != 1 or idle != 2:
        on = wd_[:, 1] > 0
        wd_[:] = 0; wd_[on, risk] = 1; wd_[~on, idle] = 1
    w = S.to_minutes(ts, wd_, dates)
    r = bt.run(ts, o, c, w, DEV0, 0.02, 1)
    s = st(r); dr = daily_ret(ts, r["equity"])
    expo = w[bt.start_index(ts, DEV0):, risk].mean()
    row = {"name": name, "cagr": float(s["cagr"]), "dd": s["max_drawdown"], "sharpe": s["sharpe"],
           "expo": float(expo), "corr": float(dr.corr(bdr)),
           "s1619": sub_cagr(ts, r["equity"], 2016, 2019), "s2021": sub_cagr(ts, r["equity"], 2020, 2021),
           "s2223": sub_cagr(ts, r["equity"], 2022, 2023)}
    if extra: row.update(extra)
    rows.append(row)
    print(f"{name:28s} CAGR {row['cagr']:6.2%} DD {row['dd']:6.1%} Sh {row['sharpe']:.2f} expo {expo:.2f} "
          f"corr {row['corr']:.2f} | 16-19 {row['s1619']:6.1%} 20-21 {row['s2021']:6.1%} 22-23 {row['s2223']:6.1%}")
    return row, w


print("== neighbourhood: z x hold (TQQQ/BIL, base rule) ==")
for ze in (-0.75, -1.0, -1.25, -1.5, -1.75):
    for h in (1, 2, 3, 5):
        evaluate(f"z{ze} h{h}", S.daily_weights(z, hold=h, z_entry=ze))
print("== z-window neighbours (z -1.25, h3) ==")
for win in (10, 40, 60):
    sd = sig["rel"].rolling(win).std().shift(1); zz = (sig["rel"] / sd).to_numpy()
    evaluate(f"win{win}", S.daily_weights(zz, hold=3, z_entry=-1.25))
print("== structural variants ==")
evaluate("QQQ risk asset (beta test)", S.daily_weights(z), risk=0)
evaluate("renew hold on new signal", renew_weights(z, 3, -1.25))
evaluate("idle in QQQ, TQQQ on signal", S.daily_weights(z), risk=1, idle=0)
evaluate("absolute QQQ z (not relative)", S.daily_weights(
    (sig["qqq"].pct_change() / sig["qqq"].pct_change().rolling(20).std().shift(1)).to_numpy()))
evaluate("stop -10% (pre-registered)", None if False else S.daily_weights(z), extra=None) if False else None
# pre-registered stop variant via build_weights
N_VAR += 1
w, _ = S.build_weights(ts, o, c, stop=-0.10)
r = bt.run(ts, o, c, w, DEV0, 0.02, 1); s = st(r)
print(f"{'stop -10%':28s} CAGR {s['cagr']:6.2%} DD {s['max_drawdown']:6.1%} Sh {s['sharpe']:.2f} corr {daily_ret(ts, r['equity']).corr(bdr):.2f}")
rows.append({"name": "stop -10%", "cagr": float(s["cagr"]), "dd": s["max_drawdown"], "sharpe": s["sharpe"]})

print("== placebo: random 3-session entries, same count (150), 200 draws ==")
rng = np.random.default_rng(42)
dev_idx = np.flatnonzero((dates >= DEV0) & (dates <= DEV1))
base_wd = S.daily_weights(z)
n_ent = int((np.diff(np.r_[0, base_wd[dev_idx, 1]]) > 0).sum())
pc = []; psh = []
for k in range(200):
    zz = np.full(len(z), np.nan)
    pick = rng.choice(dev_idx[:-4], size=int(n_ent * 1.33), replace=False)  # ~37 lost to overlap, like the real signal
    zz[pick] = -9
    wd_ = S.daily_weights(zz)
    w = S.to_minutes(ts, wd_, dates)
    s = st(bt.run(ts, o, c, w, DEV0, 0.02, 1)); pc.append(s["cagr"]); psh.append(s["sharpe"])
pc = np.array(pc); psh = np.array(psh)
real = rows[[r_["name"] for r_ in rows].index("z-1.25 h3")]
print(f"placebo CAGR mean {pc.mean():.2%} [5%,95%] {np.percentile(pc,5):.2%} {np.percentile(pc,95):.2%}; "
      f"P(placebo >= real CAGR) {np.mean(pc >= real['cagr']):.3f}; Sharpe mean {psh.mean():.2f}, P(>= real) {np.mean(psh >= real['sharpe']):.3f}")
print("variants tried:", N_VAR)
json.dump({"rows": rows, "placebo_cagr": pc.tolist(), "placebo_sharpe": psh.tolist(), "variants": N_VAR},
          open(HERE / "step3_results.json", "w", newline="\n", encoding="utf-8"), indent=1, default=float)
