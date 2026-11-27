"""Step 2 diagnosis of the frozen (post index-fix) TODL. Dev only."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from common import *  # noqa

ts, o, c = panel()
a, b = S._sessions(ts)
w, info = S.build_weights(ts, o, c)
i0 = bt.start_index(ts, DEV_START)
out = {}

# exposure (minute share of weight in each column)
held = w[i0:]
out["exposure_minutes"] = {"QQQ": float((held[:, 0] > 0.5).mean()), "TQQQ": float((held[:, 1] > 0.5).mean()),
                           "BIL": float((held[:, 2] > 0.5).mean()), "short": 0.0}
lev = float((held[:, 0] + 3 * held[:, 1]).mean())
out["avg_gross_leverage"] = lev

res = {s: run(w, s) for s in (1.0, 5.0, 10.0)}
out["strategy"] = {f"{int(s)}bp": stats(r) for s, r in res.items()}
out["corr"] = corr_base(res[1.0])
out["years"] = float((ts[-1] - ts[i0]).days / 365.25)
out["trades_per_year"] = out["strategy"]["1bp"]["fills"] / out["years"]
out["turnover_per_year"] = out["strategy"]["1bp"]["turnover"] / out["years"]

# leverage-matched static mixes, rebalanced at each session close
def static(wq, wt):
    m = np.zeros_like(w)
    m[:, 0] = wq; m[:, 1] = wt; m[:, 2] = 1 - wq - wt
    return m
mixes = {"TQQQ_lev_matched": static(0.0, lev / 3), "QQQ_100": static(1.0, 0.0),
         "TQQQ_100": static(0.0, 1.0)}
# same-exposure mix: same time-average of QQQ and TQQQ weights
mixes["same_avg_weights"] = static(float(held[:, 0].mean()), float(held[:, 1].mean()))
mr = dict(zip(mixes, run_many(list(mixes.values()))))
out["static"] = {k: {**stats(r), "corr": corr_base(r)} for k, r in mr.items()}

# per-year
de = daily_eq(res[1.0]); dq = daily_eq(mr["QQQ_100"]); dt = daily_eq(mr["TQQQ_100"]); dm = daily_eq(mr["TQQQ_lev_matched"])
yr = {}
for y in range(2016, 2024):
    def yret(d):
        x = d[str(y)]; p = d[:str(y - 1)]
        st = p.iloc[-1] if len(p) else x.iloc[0]
        return float(x.iloc[-1] / st - 1)
    yr[y] = {"strat": yret(de), "tqqq": yret(dt), "qqq": yret(dq), "lev_matched": yret(dm)}
out["per_year"] = yr

# per-day attribution by state
day_state = pd.Series(np.where(w[b - 1, 1] > 0.5, "TQQQ", np.where(w[b - 1, 0] > 0.5, "QQQ", "BIL")),
                      index=pd.to_datetime(ts[a].date))
# state held DURING day d = weight at end of day d-1 (fills at d open) - use start-of-day weight a[d]+? weight at a[d] is target after fill
held_state = pd.Series(np.where(w[a, 1] > 0.5, "TQQQ", np.where(w[a, 0] > 0.5, "QQQ", "BIL")),
                       index=pd.to_datetime(ts[a].date))
qr = dq.pct_change(); tr = dt.pct_change(); sr = de.pct_change()
df = pd.DataFrame({"state": held_state, "q": qr, "t": tr, "s": sr}).dropna()
att = {}
for st_, g in df.groupby("state"):
    att[st_] = {"days": int(len(g)), "mean_qqq_bp": float(g.q.mean() * 1e4), "mean_strat_bp": float(g.s.mean() * 1e4),
                "sum_log_qqq": float(np.log1p(g.q).sum()), "sum_log_tqqq": float(np.log1p(g.t).sum()),
                "sum_log_strat": float(np.log1p(g.s).sum()),
                "qqq_up_days": int((g.q > 0).sum())}
out["by_state_days"] = att
# missed rallies: QQQ's best 20 days, which state were we in
best = df.q.nlargest(20); worst = df.q.nsmallest(20)
out["best20_states"] = df.loc[best.index, "state"].value_counts().to_dict()
out["worst20_states"] = df.loc[worst.index, "state"].value_counts().to_dict()

# event-level: forward 5-session QQQ return from next open to block end, by state and by signal
recs = info["records"]
bar_to_sess = {str(ts[b[k] - 1]): k for k in range(len(a))}
rows = []
for rc in recs:
    r = bar_to_sess[rc["decision_bar"]]
    e = min(r + 5, len(a) - 1)
    if r + 1 >= len(a):
        continue
    fq = c[b[e] - 1, 0] / o[a[r + 1], 0] - 1
    ft = c[b[e] - 1, 1] / o[a[r + 1], 1] - 1
    rows.append(dict(r=r, state=rc["state"], on=rc["s_on"] > rc["med_on"], fh=rc["s_fh"] > rc["med_fh"],
                     vol=rc["vol_on"], fq=fq, ft=ft, date=rc["decision_bar"][:10]))
ev = pd.DataFrame(rows)
out["n_rebalances"] = len(ev)
out["state_changes"] = int((ev.state != ev.state.shift()).sum() - 1)
out["vol_cap_fires"] = {"above_0.60": int((ev.vol > 0.6).sum()), "above_0.80": int((ev.vol > 0.8).sum()),
                        "vol_on_median": float(ev.vol.median()), "vol_on_max": float(ev.vol.max())}
def grp(col):
    g = ev.groupby(col).fq
    return {str(k): {"n": int(v.size), "mean_fwd5_qqq_bp": float(v.mean() * 1e4), "hit": float((v > 0).mean())} for k, v in g}
out["fwd_by_state"] = grp("state")
out["fwd_by_on_signal"] = grp("on")
out["fwd_by_fh_signal"] = grp("fh")
# per sub-period signal spreads
sp = {}
for lab, (y0, y1) in {"2016-19": ("2016", "2019"), "2020-21": ("2020", "2021"), "2022-23": ("2022", "2023")}.items():
    x = ev[(ev.date >= y0) & (ev.date <= y1 + "-12-31")]
    sp[lab] = {"on_spread_bp": float((x[x.on].fq.mean() - x[~x.on].fq.mean()) * 1e4),
               "fh_spread_bp": float((x[x.fh].fq.mean() - x[~x.fh].fq.mean()) * 1e4),
               "tqqq_minus_qqq_state_bp": float((x[x.state == "TQQQ"].fq.mean() - x[x.state == "QQQ"].fq.mean()) * 1e4),
               "n": int(len(x))}
out["signal_spread_by_subperiod"] = sp
# permutation p-values: shuffle signal labels
rng = np.random.default_rng(0)
def perm(mask, y, n=5000):
    obs = y[mask].mean() - y[~mask].mean()
    cnt = 0
    for _ in range(n):
        m = rng.permutation(mask)
        cnt += (y[m].mean() - y[~m].mean()) >= obs
    return float(obs * 1e4), float((cnt + 1) / (n + 1))
y = ev.fq.to_numpy()
out["perm_on"] = perm(ev.on.to_numpy(), y)
out["perm_fh"] = perm(ev.fh.to_numpy(), y)
out["perm_tqqq_vs_rest"] = perm((ev.state == "TQQQ").to_numpy(), y)
out["perm_bil_vs_rest_lower"] = perm((ev.state != "BIL").to_numpy(), y)
# hit rate per state
out["subperiod_cagr"] = sub_cagr(res[1.0])
out["subperiod_cagr_qqq"] = sub_cagr(mr["QQQ_100"])
out["subperiod_cagr_tqqq"] = sub_cagr(mr["TQQQ_100"])
ev.to_csv(HERE / "events.csv", index=False)
with open(HERE / "diag.json", "w", newline="\n", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
