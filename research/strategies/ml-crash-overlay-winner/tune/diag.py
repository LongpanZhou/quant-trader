"""Step 2 diagnosis of the shipped strategy (dev window only).
Usage: python diag.py [tag]   writes tune/diag_<tag>.json (default tag 'before')."""
import json
from common import *

tag = sys.argv[1] if len(sys.argv) > 1 else "before"
w1, wd, state, p, y, rank, decay, info = S.build_weights(ts1, o1, c1, tsd, od, cd)
dev = np.asarray(dts >= pd.Timestamp(S.DEV_START))
out = {}
rs = {s: run(wd, s) for s in (1.0, 5.0, 10.0)}
r = rs[1.0]; s = st(r)
out["headline"] = {f"{int(k)}bp": {m: st(v)[m] for m in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
                   for k, v in rs.items()}
out["corr_base"] = corr_base(r)
qb = st(run(onehot(np.zeros(len(tsd), int))))
out["qqq_bh_sharpe_dd"] = (qb["sharpe"], qb["max_drawdown"])

# exposure on minutes, gross leverage
wm = minutes(wd)[bt.start_index(ts1, S.DEV_START):]
share = {"QQQ": float(wm[:, 0].mean()), "TQQQ": float(wm[:, 1].mean()), "BIL": float(wm[:, 2].mean())}
out["minute_share"] = share
lev = share["QQQ"] + 3 * share["TQQQ"]; out["avg_gross_leverage"] = lev


def const(v):
    return np.tile(np.array(v, float), (len(tsd), 1))


mixes = {"TQQQ L/3 + BIL": [0, lev / 3, 1 - lev / 3],
         "state-share mix": [share["QQQ"], share["TQQQ"], share["BIL"]],
         "QQQ L + BIL": [min(lev, 1), 0, 1 - min(lev, 1)],
         "QQQ 100%": [1, 0, 0], "TQQQ 100%": [0, 1, 0]}
out["static"] = {}
for k, v in mixes.items():
    rr = run(const(v)); ss = st(rr)
    out["static"][k] = {"w": v, "cagr": ss["cagr"], "dd": ss["max_drawdown"], "sharpe": ss["sharpe"],
                        "corr": corr_base(rr)}

# per-year
eq = daily_ret(r)
yr = {}
for Y in range(2016, 2024):
    m = eq.index.year == Y
    idx = np.flatnonzero(dts.year == Y); prev = idx[0] - 1
    q0 = od[idx[0], 0] if prev < 0 else cd[prev, 0]
    t0 = od[idx[0], 1] if prev < 0 else cd[prev, 1]
    yr[Y] = {"strategy": float(np.prod(1 + eq[m]) - 1), "TQQQ": float(cd[idx[-1], 1] / t0 - 1),
             "QQQ": float(cd[idx[-1], 0] / q0 - 1),
             "QQQ%": float((state[idx] == 0).mean()), "TQQQ%": float((state[idx] == 1).mean()),
             "BIL%": float((state[idx] == 2).mean())}
out["per_year"] = yr

# attribution by the state held into each day (close-to-close)
held = np.r_[2, state[:-1]]
dq = np.r_[np.nan, cd[1:, 0] / cd[:-1, 0] - 1]
dtq = np.r_[np.nan, cd[1:, 1] / cd[:-1, 1] - 1]
sr = eq.reindex(dts).to_numpy()
att = {}
for k, nm in ((0, "QQQ"), (1, "TQQQ"), (2, "BIL")):
    m = (held == k) & np.isfinite(sr) & np.isfinite(dtq)
    att[nm] = {"days": int(m.sum()), "sum_log_strategy": float(np.log1p(sr[m]).sum()),
               "sum_log_TQQQ": float(np.log1p(dtq[m]).sum()), "sum_log_QQQ": float(np.log1p(dq[m]).sum()),
               "TQQQ_ann_in_state": float(np.expm1(np.log1p(dtq[m]).mean() * 252)),
               "QQQ_ann_in_state": float(np.expm1(np.log1p(dq[m]).mean() * 252)),
               "QQQ_daily_vol_ann": float(np.std(dq[m]) * np.sqrt(252))}
out["attribution"] = att
ok = np.isfinite(dtq) & np.isfinite(sr)
top = np.argsort(-np.where(ok, dtq, -9))[:40]; bot = np.argsort(np.where(ok, dtq, 9))[:40]
out["best40_TQQQ_days_held"] = {nm: int((held[top] == k).sum()) for k, nm in ((0, "QQQ"), (1, "TQQQ"), (2, "BIL"))}
out["worst40_TQQQ_days_held"] = {nm: int((held[bot] == k).sum()) for k, nm in ((0, "QQQ"), (1, "TQQQ"), (2, "BIL"))}

# costs
out["fills_per_year"] = s["fills"] / s["years"]
out["switches_per_year"] = info["n_switches"] / s["years"]
out["turnover_per_year"] = s["turnover"] / s["years"]
out["cost_drag_cagr"] = {"1to5bp": out["headline"]["1bp"]["cagr"] - out["headline"]["5bp"]["cagr"],
                         "1to10bp": out["headline"]["1bp"]["cagr"] - out["headline"]["10bp"]["cagr"]}

# episodes / events
ep = []; cur = state[0]; a = 0
for i in range(1, len(state) + 1):
    if i == len(state) or state[i] != cur:
        ep.append((int(cur), a, i - 1))
        if i < len(state):
            cur = state[i]; a = i
ev = {}
for k, nm in ((1, "TQQQ"), (2, "BIL"), (0, "QQQ")):
    E = [(a, b) for kk, a, b in ep if kk == k and a + 1 < len(od)]
    rq = [od[min(b + 1, len(od) - 1), 0] / od[a + 1, 0] - 1 for a, b in E]
    rt = [od[min(b + 1, len(od) - 1), 1] / od[a + 1, 1] - 1 for a, b in E]
    if k == 1:
        hit = [t > 3 * q for q, t in zip(rq, rt)]          # leverage was favourable
        hit2 = [t > q for q, t in zip(rq, rt)]             # TQQQ beat QQQ
    elif k == 2:
        hit = [q < 0 for q in rq]; hit2 = hit               # QQQ fell while out
    else:
        hit = [q > 0 for q in rq]; hit2 = hit
    ev[nm] = {"episodes": len(E), "mean_len": float(np.mean([b - a + 1 for a, b in E])),
              "mean_QQQ_ret": float(np.mean(rq)), "hit": float(np.mean(hit)), "hit2": float(np.mean(hit2))}
out["episodes"] = ev

rng = np.random.default_rng(0)


def shift_test(k1, k2, B=2000):
    m = (dts.year >= 2017) & np.isfinite(decay)
    d = decay[m]; s_ = state[m]
    obs = d[s_ == k1].mean() - d[s_ == k2].mean()
    n = len(d); cnt = 0; tot = 0
    for _ in range(B):
        sh = np.roll(s_, rng.integers(20, n - 20))
        if not ((sh == k1).any() and (sh == k2).any()):
            continue
        tot += 1
        diff = d[sh == k1].mean() - d[sh == k2].mean()
        cnt += (diff >= obs) if obs > 0 else (diff <= obs)
    return {"obs": float(obs), "p_one_sided": float((cnt + 1) / (tot + 1))}


out["decay_separation"] = {"TQQQ_minus_QQQ": shift_test(1, 0), "BIL_minus_QQQ": shift_test(2, 0)}
out["auc_by_year"] = info["auc_by_year"]
m = dev & np.isfinite(p) & np.isfinite(y)
pos, neg = p[m][y[m] == 1], p[m][y[m] == 0]
out["auc_pooled"] = float((pos[:, None] > neg[None, :]).mean())

# vol-only comparator with the same map (ML vs simple realised vol)
out["vol_only"] = {}
for nm in ("rv5", "rv20", "range20"):
    rk = rank_of(F[nm].to_numpy()).copy(); rk[dts.year == 2016] = np.nan
    wv, _ = S.state_weights(rk)
    rr = run(wv); ss = st(rr)
    m2 = (dts.year >= 2017) & np.isfinite(p) & np.isfinite(F[nm].to_numpy())
    out["vol_only"][nm] = {"cagr": ss["cagr"], "dd": ss["max_drawdown"], "sharpe": ss["sharpe"], "corr": corr_base(rr),
                           "spearman_p": float(pd.Series(p[m2]).rank().corr(pd.Series(F[nm].to_numpy()[m2]).rank()))}

# placebo: 300 circular shifts of the 2017-2023 state path
idx = np.flatnonzero(dts.year >= 2017)
wl = []
for b in range(300):
    s2 = state.copy(); s2[idx] = np.roll(state[idx], rng.integers(20, len(idx) - 20)); wl.append(onehot(s2))
res = []
for a in range(0, 300, 30):
    res += [st(x)["sharpe"] for x in run_many(wl[a:a + 30])]
res = np.array(res)
out["placebo_shift"] = {"strategy_sharpe": s["sharpe"], "p95": float(np.percentile(res, 95)),
                        "median": float(np.median(res)), "p_value": float((np.sum(res >= s["sharpe"]) + 1) / 301)}
out["subperiods"] = subs(r)
with open(HERE / "tune" / f"diag_{tag}.json", "w", newline="\n", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
