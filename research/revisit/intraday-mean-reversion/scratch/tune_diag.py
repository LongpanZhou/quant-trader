"""Tune-brief Step 1/2 diagnostics. DEV ONLY (panel ends 2023-12-29).

Run from repo root:
    python research/revisit/intraday-mean-reversion/scratch/tune_diag.py
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("imr", HERE.parent / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt

DEV0, DEV1 = S.DEV_START, S.DEV_END
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
assert ts[-1].date() <= pd.Timestamp(DEV1).date()
out = {}

w, info = S.build_weights(ts, o, c)
F = S.session_features(ts, c)
first, last, nd = F["first"], F["last"], F["nd"]
sdate = F["d"][first]                       # per-SESSION date (correct)
i0, i1 = S.window_bounds(ts, DEV0, DEV1)
k0 = int(np.searchsorted(first, i0, side="right") - 1)  # session of i0 (2016-01-04)

# ---------------- Step 1 checks ----------------
ev = np.zeros(nd, bool)
ev[1:] = F["dmin"][1:] <= -0.03
held = np.flatnonzero(np.r_[False, ev[:-1]])
held_dev = held[held > k0]
out["events_dev_trigger"] = int(ev[k0:].sum())           # trigger sessions 2016-01-04..2023-12-29
out["held_sessions_dev"] = int(len(held_dev))
out["info_event_dates_first5_buggy"] = info["event_dates"][:5]
out["event_dates_first5_correct"] = [str(sdate[k]) for k in np.flatnonzero(ev)[:5]]

# weight validity
out["weights_finite"] = bool(np.isfinite(w).all())
out["weights_min"] = float(w.min())
out["rowsum_max"] = float(w.sum(1).max())
# position never held into the last bar of a session (held weight known at bar b-1 is 0)
out["held_at_second_last_bar"] = int((w[last - 1, :2] > 0).sum())
# every held session: weight on its first..b-2 bars == 1, set at prior session's last bar
bad = 0
for k in held_dev:
    a, b = first[k], last[k]
    if not (w[last[k - 1], 1] == 1 and (w[a:b - 1, 1] == 1).all() and w[b - 1, 1] == 0):
        bad += 1
out["held_session_shape_errors"] = bad
# half days and short sessions
lens = last - first + 1
out["session_len_counts_dev"] = {str(int(L)): int(n) for L, n in zip(*np.unique(lens[k0:], return_counts=True)) if L != 390}

# ---------------- headline reproduction ----------------
def run(wm, slip=1.0):
    r = bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1], wm[i0:i1 + 1], band=0.02, slippage_bps=slip)
    return r, bt.stats(r, S.BARS_1M)

res = {}
for slip in (0.0, 1.0, 5.0, 10.0):
    r, s = run(w, slip)
    res[slip] = (r, s)
    out[f"dev_{slip:.0f}bp"] = {k: round(float(s[k]), 4) for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
r1, s1 = res[1.0]

# ---------------- exposure ----------------
held_pos = np.r_[0, w[i0:i1, 1]]  # position during bar j is target of bar j-1
out["frac_minutes_TQQQ"] = round(float((held_pos > 0).mean()), 4)
out["frac_minutes_BIL"] = round(float((np.r_[1, w[i0:i1, 2]] > 0).mean()), 4)
out["frac_minutes_QQQ"] = 0.0
out["frac_minutes_short"] = 0.0
out["avg_gross_leverage"] = round(float(3 * held_pos.mean()), 4)
out["frac_sessions_held"] = round(len(held_dev) / (nd - k0 - 1), 4)

# ---------------- leverage-matched static mix ----------------
e = float(held_pos.mean())
def static_mix(frac):
    wm = np.zeros_like(w)
    wm[:, 1] = frac
    wm[:, 2] = 1 - frac
    # force a daily rebalance: band is 2% of equity; small mixes rarely cross it, so
    # also run with band=0 at each session's last bar via a tiny weight jitter is not
    # needed — report both band=0.02 and band=0.0.
    return wm
mix = static_mix(e)
rm, sm = run(mix)
rm0 = bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1], mix[i0:i1 + 1], band=0.0, slippage_bps=1.0)
sm0 = bt.stats(rm0, S.BARS_1M)
out["lev_matched_frac_tqqq"] = round(e, 4)
out["lev_matched_static"] = {"band2": [round(sm["cagr"], 4), round(sm["max_drawdown"], 4), round(sm["sharpe"], 3)],
                             "band0": [round(sm0["cagr"], 4), round(sm0["max_drawdown"], 4), round(sm0["sharpe"], 3)]}
# intraday-only static mix: e/0.95 TQQQ every session intraday (same "never overnight" shape)
wi = np.zeros_like(w); wi[:, 2] = 1.0
frac_i = min(1.0, e / ((lens - 1) / lens).mean())
for k in range(nd):
    a, b = first[k], last[k]
    if k > 0:
        wi[last[k - 1], 1] = frac_i
    wi[a:b - 1, 1] = frac_i
    wi[b - 1, 1] = 0.0
wi[-1, 1] = 0
wi[:, 2] = 1 - wi[:, 1]
ri, si = run(wi)
out["lev_matched_intraday_every_session"] = [round(si["cagr"], 4), round(si["max_drawdown"], 4), round(si["sharpe"], 3)]

# ---------------- per-year ----------------
eq = pd.Series(r1["equity"], index=ts[i0:i1 + 1])
tq = pd.Series(c[i0:i1 + 1, 1], index=ts[i0:i1 + 1])
qq = pd.Series(c[i0:i1 + 1, 0], index=ts[i0:i1 + 1])
eqy = eq.groupby(eq.index.year).last(); tqy = tq.groupby(tq.index.year).last(); qqy = qq.groupby(qq.index.year).last()
prev = [eq.iloc[0], tq.iloc[0], qq.iloc[0]]
yr = {}
for y in eqy.index:
    yr[int(y)] = {"strat": round(eqy[y] / prev[0] - 1, 4), "tqqq": round(tqy[y] / prev[1] - 1, 4),
                  "qqq": round(qqy[y] / prev[2] - 1, 4),
                  "events": int(sum(1 for k in held_dev if sdate[k].year == y))}
    prev = [eqy[y], tqy[y], qqy[y]]
out["per_year"] = yr

# ---------------- where the gap comes from (TQQQ log return decomposition) -------------
lt = np.log(c[:, 1])
on, intra_held, intra_un, last_bar = 0.0, 0.0, 0.0, 0.0
held_set = set(held_dev.tolist())
for k in range(k0 + 1, nd):
    a, b = first[k], last[k]
    on += np.log(o[a, 1]) - lt[last[k - 1]]            # overnight gap
    body = np.log(o[b, 1]) - np.log(o[a, 1])           # open -> open of 15:59 bar
    lb = lt[b] - np.log(o[b, 1])                       # final bar
    last_bar += lb
    if k in held_set:
        intra_held += body
    else:
        intra_un += body
yrs = s1["years"]
out["tqqq_logret_per_yr"] = {"overnight": round(on / yrs, 4), "intraday_held": round(intra_held / yrs, 4),
                            "intraday_not_held": round(intra_un / yrs, 4), "final_bar": round(last_bar / yrs, 4),
                            "total": round((on + intra_held + intra_un + last_bar) / yrs, 4)}
# missed up-days: TQQQ daily return on unheld sessions in top decile
dret = np.array([c[last[k], 1] / c[last[k - 1], 1] - 1 for k in range(k0 + 1, nd)])
ks = np.arange(k0 + 1, nd)
top = dret >= np.quantile(dret, 0.9)
out["top_decile_tqqq_days"] = int(top.sum())
out["top_decile_days_held"] = int(sum(1 for k in ks[top] if k in held_set))

# ---------------- event stats ----------------
evr = []
for k in held_dev:
    a, b = first[k], last[k]
    evr.append((str(sdate[k - 1]), float(o[b, 1] / o[a, 1] - 1)))  # traded leg: open -> 15:59 open
rets = np.array([x[1] for x in evr])
allr = np.array([o[last[k], 1] / o[first[k], 1] - 1 for k in range(k0 + 1, nd)])
out["event_n"] = int(len(rets))
out["event_mean"] = round(float(rets.mean()), 5)
out["event_median"] = round(float(np.median(rets)), 5)
out["event_hit"] = round(float((rets > 0).mean()), 4)
out["uncond_mean"] = round(float(allr.mean()), 5)
# cluster bootstrap with correct dates (gap > 7 calendar days)
boot = S.cluster_bootstrap(evr)
out["cluster_bootstrap_fixed"] = {k: boot[k] for k in ("n_events", "n_clusters", "mean", "p_mean_le_0", "ci95")}
# excess over unconditional
boot2 = S.cluster_bootstrap([(d, r - allr.mean()) for d, r in evr])
out["cluster_bootstrap_excess_p"] = boot2["p_mean_le_0"]
# placebo: random sessions, same count, one-session hold
rng = np.random.default_rng(11)
pm = np.array([rng.choice(allr, size=len(rets), replace=False).mean() for _ in range(5000)])
out["placebo_p_random_mean_ge_event"] = float((pm >= rets.mean()).mean())
# by sub-period
sub = {}
for lab, y0, y1 in (("2016-19", 2016, 2019), ("2020-21", 2020, 2021), ("2022-23", 2022, 2023)):
    m = np.array([y0 <= sdate[k].year <= y1 for k in held_dev])
    sub[lab] = {"n": int(m.sum()), "mean": round(float(rets[m].mean()), 5), "hit": round(float((rets[m] > 0).mean()), 3)}
out["event_subperiods"] = sub
# largest cluster removed
evd = pd.to_datetime([x[0] for x in evr])
m20 = ~((evd >= "2020-02-20") & (evd <= "2020-04-30"))
out["event_mean_ex_2020spring"] = round(float(rets[m20].mean()), 5)
out["event_dates"] = [x[0] for x in evr]

# ---------------- 165d correlation ----------------
base_w = S.correlation_baseline_weights(ts, c)
rb, sb = run(base_w)
a1, a2 = S.daily_returns(r1), S.daily_returns(rb)
j = a1.index.intersection(a2.index)
out["corr_165d"] = round(float(np.corrcoef(a1.loc[j], a2.loc[j])[0, 1]), 4)
out["base_165d_dev"] = [round(sb["cagr"], 4), round(sb["max_drawdown"], 4)]
out["tqqq_dev"] = bt.benchmark(c[i0:i1 + 1, 1], ts[i0:i1 + 1], S.BARS_1M)["cagr"]

# ---------------- preliminary 17.12% vs 11.31%: overnight on consecutive events ----------
cons = sum(1 for k in held_dev if (k + 1) in held_set)
out["consecutive_held_pairs"] = int(cons)

json.dump(out, open(HERE / "tune_diag.json", "w", newline="\n", encoding="utf-8"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "event_dates"}, indent=1, default=str))
