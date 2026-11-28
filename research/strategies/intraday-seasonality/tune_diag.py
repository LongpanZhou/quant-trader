"""Tuning diagnostics for intraday-seasonality (2026-11-27). DEV WINDOW ONLY.

Loads the panel with end=2023-12-29; nothing after the dev window is loaded,
computed or printed.

    python research/strategies/intraday-seasonality/tune_diag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
import bt  # noqa: E402

DEV = S.WINDOWS["dev"]
BPY = S.BARS_PER_YEAR
OUT = HERE / "tune_diag.json"

ts, O, C = bt.panel(("QQQ", "TQQQ", "BIL"), DEV[0], DEV[1], "1min")
assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
n = len(ts)
dates = bt.session_dates(ts)
first, last = S.day_bounds(dates)
ns = len(first)
mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
day_id = np.repeat(np.arange(ns), np.diff(np.r_[first, n]))
years = np.array([d.year for d in dates[first]])
BAR = {}


def bar(hh, mm):
    if (hh, mm) not in BAR:
        BAR[(hh, mm)] = S.exact_bar(ts, first, last, hh, mm)
    return BAR[(hh, mm)]


q_open = O[first, 0]
q_prev_close = np.r_[np.nan, C[last, 0][:-1]]
gap = q_open / q_prev_close - 1.0


def q_at(sig_bar):
    return np.where(sig_bar >= 0, C[np.maximum(sig_bar, 0), 0], np.nan) / q_open - 1.0


# ------------------------------------------------------------------ fast clone
def weights(fire, sig_bar, exit_hm=(15, 0), hold=1, stop=None, size=None,
            exit_next_open=False):
    """Same mechanics as strategy.build_weights, for an arbitrary fire mask.

    Entry: weight set on sig_bar (fills next bar). Exit: weight set on the
    exit_hm bar of session k+hold (fills the following minute); if missing,
    the last bar of that session (fills next session open).
    """
    w = np.zeros(n)
    ex_bar = bar(*exit_hm)
    ev = []
    for k in np.flatnonzero(fire):
        if k + hold >= ns:
            continue
        ew = int(sig_bar[k])
        if ew < 0 or ew + 1 > last[k] or ew <= 0:
            continue
        epx = O[ew + 1, 1]
        if exit_next_open:
            xw = int(last[k + hold - 1])
        else:
            e = ex_bar[k + hold]
            xw = int(e) if e >= 0 else int(last[k + hold])
        xw = max(xw, ew)
        if stop is not None:
            j0, j1 = ew + 1, min(xw, int(last[k + hold]))
            hit = np.flatnonzero(C[j0:j1 + 1, 1] < epx * (1 - stop))
            if len(hit):
                xw = j0 + int(hit[0])
        s = 1.0 if size is None else float(size[k])
        w[ew:xw] = np.maximum(w[ew:xw], s)
        ev.append((k, ew, xw, epx, s))
    W = np.zeros((n, 3))
    W[:, 1] = np.clip(w, 0, 1)
    W[:, 2] = 1 - W[:, 1]
    return W, ev


def sim(W, slip=1.0, win=DEV):
    return S.simulate_window(ts, O, C, W, win, slip)


def m(W, slip=1.0, win=DEV):
    return S.metrics(sim(W, slip, win))


def ev_rets(ev):
    return np.array([O[xw + 1, 1] / epx - 1.0 for (_, _, xw, epx, s) in ev if xw + 1 < n])


def boot_p(r, seed=11, B=10_000):
    rng = np.random.default_rng(seed)
    b = rng.choice(r, size=(B, len(r)), replace=True).mean(axis=1)
    return float((b <= 0).mean())


def subs(W):
    return {k: m(W, 1.0, v) for k, v in S.SUBPERIODS.items()}


# ------------------------------------------------------------------ base
res = {}
i1558 = bar(15, 58)
qd = q_at(i1558)
ok = np.isfinite(qd) & (mins[first] == 570)
fire0 = ok & (qd <= -0.01)
W0, ev0 = weights(fire0, i1558)
Wref, info = S.build_weights(ts, O, C, **S.BASE)
assert np.array_equal(W0, Wref), "fast clone does not reproduce build_weights"
i0, j0 = S.window_slice(ts, *DEV)
wb = S.baseline_weights(ts, C)
rb = sim(wb)
r0 = sim(W0)
base_m = {f"{s:.0f}bp": m(W0, s) for s in (0, 1, 5, 10)}
res["base"] = base_m
res["corr_base"] = S.corr_vs(r0, rb)

# exposure
res["exposure"] = {"tqqq": float(W0[i0:j0, 1].mean()), "bil": float(W0[i0:j0, 2].mean()),
                   "qqq": 0.0, "short": 0.0,
                   "gross_leverage": float(3 * W0[i0:j0, 1].mean())}
e = res["exposure"]["tqqq"]

# leverage-matched static mix, rebalanced daily (daily close-to-close)
dcl = C[last]                       # session closes QQQ, TQQQ, BIL
dr = dcl[1:] / dcl[:-1] - 1
mix = e * dr[:, 1] + (1 - e) * dr[:, 2]
yrs = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)
eqm = np.r_[1, np.cumprod(1 + mix)]
res["static_mix"] = {"tqqq_weight": e, "cagr": float(eqm[-1] ** (1 / yrs) - 1),
                     "max_drawdown": float(-(eqm / np.maximum.accumulate(eqm) - 1).min()),
                     "sharpe": float(mix.mean() / mix.std() * np.sqrt(252))}
# same thing through bt with a 2% band (rebalances only when drift > band)
Wm = np.zeros((n, 3)); Wm[:, 1] = e; Wm[:, 2] = 1 - e
res["static_mix_bt"] = m(Wm)

# per-year
eq0 = r0["equity"]; tsw = r0["ts"]
yr = {}
for y in range(2016, 2024):
    msk = np.asarray(tsw.year == y)
    a = eq0[msk]; q = C[i0:j0, 0][msk]; t3 = C[i0:j0, 1][msk]
    # year return from the previous year-end mark
    idx = np.flatnonzero(msk)
    p = idx[0] - 1 if idx[0] > 0 else idx[0]
    yr[y] = {"strategy": float(a[-1] / eq0[p] - 1), "tqqq": float(t3[-1] / C[i0 + p, 1] - 1),
             "qqq": float(q[-1] / C[i0 + p, 0] - 1), "mix": None}
for y in range(2016, 2024):
    msk = years[1:] == y
    yr[y]["mix"] = float(np.prod(1 + mix[msk]) - 1)
res["per_year"] = yr

# where the gap comes from: TQQQ log return held vs missed
lr = np.log(C[1:, 1] / C[:-1, 1])          # close[i-1] -> close[i]
pos = W0[:-2, 1]                            # target on i-1 filled at open i: held for
pos = np.r_[0.0, pos]                       # the open[i]->close[i] part; approximate
held = pos[: len(lr)] > 0                   # whole close->close by position at bar i
lr_w = lr[i0:j0 - 1]; held_w = held[i0:j0 - 1]
res["tqqq_logret_split"] = {"total": float(lr_w.sum()), "held": float(lr_w[held_w].sum()),
                            "missed": float(lr_w[~held_w].sum())}
# daily view: TQQQ daily close-close return, attribute to day held overnight+
tq_d = dr[:, 1]
held_day = np.zeros(ns, bool)
for (k, ew, xw, epx, s) in ev0:
    held_day[k + 1] = True                  # session after the signal
hd = held_day[1:]
order = np.argsort(tq_d)[::-1]
res["top_days"] = {"top20_tqqq_up_days_held": int(hd[order[:20]].sum()),
                   "top50_held": int(hd[order[:50]].sum()),
                   "bottom20_down_days_held": int(hd[order[-20:]].sum()),
                   "frac_days_held": float(hd.mean())}
# mean TQQQ next-session return (close->close) after signal vs all days
res["tqqq_cc_after_signal_bp"] = float(tq_d[hd].mean() * 1e4)
res["tqqq_cc_all_bp"] = float(tq_d.mean() * 1e4)

# costs
r_ev = ev_rets(ev0)
res["events"] = {"n": int(len(r_ev)), "per_year": float(len(r_ev) / yrs),
                 "mean_bp": float(r_ev.mean() * 1e4), "median_bp": float(np.median(r_ev) * 1e4),
                 "hit": float((r_ev > 0).mean()),
                 "t": float(r_ev.mean() / r_ev.std(ddof=1) * np.sqrt(len(r_ev))),
                 "boot_p": boot_p(r_ev),
                 "worst5_bp": [float(x * 1e4) for x in np.sort(r_ev)[:5]],
                 "best5_bp": [float(x * 1e4) for x in np.sort(r_ev)[-5:]]}
res["fills_per_year"] = base_m["1bp"]["fills"] / yrs
res["cost_drag"] = {k: base_m["0bp"]["cagr"] - v["cagr"] for k, v in base_m.items()}

# per-event by year
evy = {}
for y in range(2016, 2024):
    rr = np.array([O[xw + 1, 1] / epx - 1 for (k, _, xw, epx, _) in ev0 if years[k] == y])
    evy[y] = {"n": int(len(rr)), "mean_bp": float(rr.mean() * 1e4) if len(rr) else None,
              "hit": float((rr > 0).mean()) if len(rr) else None}
res["events_by_year"] = evy

# ------------------------------------------------------------------ placebos
def summary(W, ev=None):
    r = sim(W)
    out = {**{k: m(W)[k] for k in ("cagr", "max_drawdown", "sharpe")},
           "corr_base": S.corr_vs(r, rb), "tqqq_exposure": float(W[i0:j0, 1].mean())}
    if ev is not None:
        rr = ev_rets(ev)
        out.update(n=int(len(rr)), mean_bp=float(rr.mean() * 1e4) if len(rr) else None,
                   hit=float((rr > 0).mean()) if len(rr) else None)
    return out


pl = {}
Wu, evu = weights(ok & (qd >= 0.01), i1558); pl["P1_upday"] = summary(Wu, evu)
Wg, evg = weights(ok & (gap <= -0.01), i1558); pl["P4_gap_select"] = summary(Wg, evg)
rng = np.random.default_rng(7)
frac = fire0.mean()
rnd = []
for _ in range(100):
    f = ok & (rng.random(ns) < frac)
    W, ev = weights(f, i1558)
    rnd.append(summary(W, ev))
pl["P2_random"] = {"n_draws": 100,
                   "sharpe_pct": [float(np.percentile([x["sharpe"] for x in rnd], p)) for p in (5, 50, 95)],
                   "cagr_pct": [float(np.percentile([x["cagr"] for x in rnd], p)) for p in (5, 50, 95)],
                   "frac_sharpe_ge_base": float(np.mean([x["sharpe"] >= base_m["1bp"]["sharpe"] for x in rnd])),
                   "frac_mean_ge_base": float(np.mean([x["mean_bp"] >= res["events"]["mean_bp"] for x in rnd]))}
shp = []
for _ in range(100):
    f = np.zeros(ns, bool)
    for y in np.unique(years):
        idx = np.flatnonzero((years == y) & ok)
        kk = int(fire0[years == y].sum())
        f[rng.choice(idx, kk, replace=False)] = True
    W, ev = weights(f, i1558)
    shp.append(summary(W, ev))
pl["P3_shuffled_in_year"] = {"sharpe_pct": [float(np.percentile([x["sharpe"] for x in shp], p)) for p in (5, 50, 95)],
                             "frac_sharpe_ge_base": float(np.mean([x["sharpe"] >= base_m["1bp"]["sharpe"] for x in shp]))}
# intraday-only decline (gap filter) vs gap-led
Wgf, evgf = weights(fire0 & (np.abs(gap) <= 0.005), i1558); pl["gapfilter_abs_le_0.5pct"] = summary(Wgf, evgf)
res["placebos"] = pl

# ------------------------------------------------------------------ variants (one-at-a-time around base)
var = {}
count = 0


def run_variant(name, W, ev):
    global count
    count += 1
    s = summary(W, ev)
    s["5bp_cagr"] = m(W, 5)["cagr"]
    s["10bp_cagr"] = m(W, 10)["cagr"]
    s["subs_cagr"] = {k: v["cagr"] for k, v in subs(W).items()}
    s["subs_sharpe"] = {k: v["sharpe"] for k, v in subs(W).items()}
    var[name] = s


for thr in (-0.005, -0.0075, -0.01, -0.0125, -0.015, -0.02):
    W, ev = weights(ok & (qd <= thr), i1558); run_variant(f"thr={thr}", W, ev)
for up in (-0.025, -0.03):
    W, ev = weights(fire0 & (qd >= up), i1558); run_variant(f"upper={up}", W, ev)
W, ev = weights(fire0 & (np.abs(gap) <= 0.005), i1558); run_variant("gap<=0.5%", W, ev)
# entry 15:30 open (signal on the 15:29 close)
i1529 = bar(15, 29); q29 = q_at(i1529)
W, ev = weights(ok & np.isfinite(q29) & (q29 <= -0.01), i1529); run_variant("entry=15:30", W, ev)
W, ev = weights(fire0, i1558, exit_next_open=True); run_variant("exit=next_open", W, ev)
for hh, mm in ((10, 0), (12, 0), (14, 0), (15, 30), (15, 58)):
    W, ev = weights(fire0, i1558, exit_hm=(hh, mm)); run_variant(f"exit=next_{hh:02d}{mm:02d}", W, ev)
W, ev = weights(fire0, i1558, stop=0.05); run_variant("stop=5%", W, ev)
for h in (2, 3):
    W, ev = weights(fire0, i1558, hold=h); run_variant(f"hold={h}", W, ev)
W, ev = weights(fire0, i1558, size=np.clip(np.abs(qd) / 0.02, 0.5, 1.0)); run_variant("size=scaled", W, ev)
res["variants"] = var
res["variants_tried"] = count

# idle-time fill diagnostic: QQQ when not in TQQQ
def idle_qqq(W, exclude=None):
    W2 = np.zeros_like(W)
    W2[:, 1] = W[:, 1]
    q = 1 - W[:, 1]
    if exclude is not None:
        q = q * (~exclude)
    W2[:, 0] = q
    W2[:, 2] = 1 - W2[:, 0] - W2[:, 1]
    return W2


idle = {"QQQ_idle": summary(idle_qqq(W0))}
res["idle_fill"] = idle

with open(OUT, "w", newline="\n", encoding="utf-8") as fh:
    json.dump(res, fh, indent=2, default=float)
print(json.dumps(res, indent=1, default=float))
