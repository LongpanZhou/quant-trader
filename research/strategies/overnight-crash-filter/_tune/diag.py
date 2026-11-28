"""Step 2 diagnosis of the frozen strategy (dev only)."""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from common import SLUG, bt, panel, load_strategy, stats, daily_rets, sub_cagr, BARS, DEV_START

path = sys.argv[1] if len(sys.argv) > 1 else None
mod = load_strategy(path)
ts, o, c = panel()
w, info = mod.build_weights(ts, o, c)
n = len(ts)
out = {"info": info}

# ---- headline at costs
res = {}
for bp in (0, 1, 5, 10):
    r = bt.simulate(ts, o, c, w, band=0.02, slippage_bps=bp)
    res[bp] = r
    out[f"{bp}bp"] = stats(r)
eq1 = res[1]["equity"]

# ---- exposure (held position during bar i is w[i-1])
held = np.vstack([np.zeros((1, 3)), w[:-1]])
out["frac_bars_tqqq"] = float((held[:, 1] > 0).mean())
out["frac_bars_qqq"] = float((held[:, 0] > 0).mean())
out["frac_bars_bil"] = float((held[:, 2] > 0).mean())
out["avg_gross_lev_per_bar"] = float((3 * held[:, 1] + held[:, 0]).mean())
# calendar-time weighting: the bar before a session gap carries the overnight hours
tsn = ts.as_unit("ns").asi8
dt = np.diff(np.r_[tsn, tsn[-1] + 60_000_000_000]) / 6e10  # minutes until next bar
out["avg_gross_lev_calendar"] = float(((3 * held[:, 1] + held[:, 0]) * dt).sum() / dt.sum())
out["frac_calendar_tqqq"] = float(((held[:, 1] > 0) * dt).sum() / dt.sum())
out["frac_calendar_qqq"] = float(((held[:, 0] > 0) * dt).sum() / dt.sum())

# ---- block returns per session
s = mod.build_signals(ts, o, c)
first, last, nd = s["first"], s["last"], s["nd"]
tq_o, qq_o = o[:, 1], o[:, 0]
night = np.full(nd, np.nan)        # TQQQ 15:59 open -> next 09:30 open
night[:-1] = tq_o[first[1:]] / tq_o[last[:-1]] - 1
dayq = qq_o[last] / qq_o[np.minimum(first + 1, last)] - 1   # QQQ 09:31 open -> 15:59 open
dayt = tq_o[last] / tq_o[first] - 1                         # TQQQ 09:30 open -> 15:59 open
nightw = w[last - 1, 1]
dayw = w[first, 0]                 # weight set at the 09:30 bar close
on_n = nightw > 0
on_d = dayw > 0
years = np.array([d.year for d in s["dates"][first]])


def tstat(x):
    x = x[np.isfinite(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


rng = np.random.default_rng(0)


def boot_p(x, pool, reps=5000):
    """P(mean of random same-size draw from pool >= mean(x))."""
    x = x[np.isfinite(x)]
    pool = pool[np.isfinite(pool)]
    m = x.mean()
    draws = rng.choice(pool, size=(reps, len(x))).mean(axis=1)
    return float((draws >= m).mean())


vn = np.isfinite(night)
up = s["r_day"] > 0
ev = {}
ev["night_events"] = int(on_n.sum())
ev["night_mean_bp_on"] = float(np.nanmean(night[on_n]) * 1e4)
ev["night_hit_on"] = float((night[on_n & vn] > 0).mean())
ev["night_mean_bp_all"] = float(np.nanmean(night) * 1e4)
ev["night_mean_bp_after_up"] = float(np.nanmean(night[up]) * 1e4)
ev["night_mean_bp_after_down"] = float(np.nanmean(night[~up]) * 1e4)
a, b = night[up & vn], night[~up & vn]
ev["F1_t_up_minus_down"] = float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
ev["night_boot_p_vs_all_nights"] = boot_p(night[on_n], night)
neg = s["gap"] < 0
vd = np.isfinite(dayq)
ev["day_events"] = int(on_d.sum())
ev["day_mean_bp_on"] = float(np.nanmean(dayq[on_d]) * 1e4)
ev["day_hit_on"] = float((dayq[on_d] > 0).mean())
ev["day_mean_bp_all"] = float(np.nanmean(dayq) * 1e4)
ev["day_mean_bp_neg_gap"] = float(np.nanmean(dayq[neg]) * 1e4)
ev["day_mean_bp_pos_gap"] = float(np.nanmean(dayq[~neg & np.isfinite(s["gap"])]) * 1e4)
a, b = dayq[neg & vd], dayq[~neg & vd & np.isfinite(s["gap"])]
ev["F2_t_neg_minus_pos"] = float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
ev["day_t_on"] = tstat(dayq[on_d])
ev["day_boot_p_vs_all_days"] = boot_p(dayq[on_d], dayq)
out["events"] = ev

# ---- gross contribution by leg (0 bp, simple sum of weighted returns)
out["sum_logret_night_leg"] = float(np.nansum(np.log1p(nightw * night)))
out["sum_logret_day_leg"] = float(np.nansum(np.log1p(dayw * dayq)))
out["tqqq_sum_log_night"] = float(np.nansum(np.log1p(night)))
out["tqqq_sum_log_day"] = float(np.nansum(np.log1p(dayt)))
# missed nights: up-day nights skipped (signal off) and their TQQQ return
out["tqqq_sum_log_night_skipped"] = float(np.nansum(np.log1p(night[~on_n])))
out["tqqq_sum_log_night_taken"] = float(np.nansum(np.log1p(night[on_n])))

# ---- per year
yr = {}
eqs = pd.Series(eq1, index=ts)
for y in sorted(set(ts.year)):
    m = ts.year == y
    e = eq1[m]
    yr[int(y)] = {"strat": float(e[-1] / e[0] - 1),
                  "tqqq": float(c[m, 1][-1] / c[m, 1][0] - 1),
                  "qqq": float(c[m, 0][-1] / c[m, 0][0] - 1),
                  "night_leg_log": float(np.nansum(np.log1p(nightw * night)[years == y])),
                  "day_leg_log": float(np.nansum(np.log1p(dayw * dayq)[years == y]))}
out["yearly"] = yr

# ---- costs
yrs = out["1bp"]
nyrs = (ts[-1] - ts[0]).days / 365.25
out["fills_per_year"] = out["1bp"]["fills"] / nyrs
out["roundtrips_per_year"] = (int(on_n.sum()) + int(on_d.sum())) / nyrs
out["traded_notional_x_equity_per_year"] = float(
    (np.abs(np.diff(np.vstack([np.zeros((1, 3)), w]), axis=0)).sum() / nyrs))
out["cost_drag_cagr_pts"] = {bp: out["0bp"]["cagr"] - out[f"{bp}bp"]["cagr"] for bp in (1, 5, 10)}

# ---- leverage-matched static mixes
statics = {}
for x in (0.1, 0.15, out["avg_gross_lev_calendar"] / 3, out["avg_gross_lev_per_bar"] / 3, 0.3):
    ws = np.zeros((n, 3)); ws[:, 1] = x
    r = bt.simulate(ts, o, c, ws, band=0.02, slippage_bps=1)
    statics[f"{x:.3f}"] = stats(r)
out["static_tqqq_cash"] = statics
# vol-matched
target_vol = out["1bp"]["volatility"]
ws = np.zeros((n, 3)); ws[:, 1] = 1.0
vt = stats(bt.simulate(ts, o, c, ws, band=0.02, slippage_bps=1))["volatility"]
x = target_vol / vt
ws[:, 1] = x
out["static_vol_matched"] = {"x": x} | stats(bt.simulate(ts, o, c, ws, band=0.02, slippage_bps=1))

# ---- correlation with 165d baseline
bw = mod._benchmark_correlation_weights(ts, o, c)
rb = bt.simulate(ts, o, c, bw, band=0.02, slippage_bps=1)
out["corr_165d"] = float(daily_rets(ts, eq1).corr(daily_rets(ts, rb["equity"])))
out["baseline"] = stats(rb)
out["sub"] = sub_cagr(ts, eq1)

print(json.dumps(out, indent=1, default=float))
