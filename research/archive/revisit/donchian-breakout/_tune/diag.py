"""Step 1/2 diagnostics for the ORIGINAL (pre-tune) rebuild. Dev window only."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import (HERE, DEV_START, BARS, bt, to_minutes, load_mod, panel1, daily,
                    stats, corr_base)

S = load_mod(HERE.parent / "_before_tune" / "strategy.py", "dal_before")
out = {}

ts5, o5, c5, qh, ql, qc, tc, atr_q, atr_t = S.load_5m()
i5 = bt.start_index(ts5, DEV_START)
# warm-up check: load_5m filters 1m data to >= DEV_START, then bfills the 500-day warmup
out["warmup_bars_before_dev"] = int(i5)
out["warmup_bars_constant"] = bool(np.all(qc[:i5] == qc[i5])) if i5 else None
w5, info = S.build_weights(ts5, qh, ql, qc, tc, atr_q, atr_t)
st = np.where(w5[:, 0] == 1, 2, np.where(w5[:, 1] > 0, 3, 0))[i5:]
out["state_frac_dev"] = {"BIL(A<=1)": float((st == 0).mean()), "QQQ(A=2)": float((st == 2).mean()),
                         "TQQQ(A=3)": float((st == 3).mean())}
tw = w5[i5:, 1][st == 3]
out["tqqq_weight_when_A3"] = {"mean": float(tw.mean()), "p10": float(np.percentile(tw, 10)),
                              "p50": float(np.median(tw)), "p90": float(np.percentile(tw, 90))}
# state changes / episode lengths in 5-min bars
chg = np.flatnonzero(np.diff(st) != 0)
out["state_changes_dev"] = int(len(chg))
out["state_changes_per_year"] = float(len(chg) / 8.0)
ep = np.diff(np.r_[0, chg + 1, len(st)])
out["median_episode_5m_bars"] = float(np.median(ep))

ts1, o1, c1 = panel1()
w1 = to_minutes(ts5, w5, ts1, "5min")
i1 = bt.start_index(ts1, DEV_START)
wd = w1[i1:]
out["minute_exposure"] = {"QQQ": float((wd[:, 0] > 0).mean()), "TQQQ": float((wd[:, 1] > 0).mean()),
                          "BIL_only": float((wd[:, 2] == 1).mean()), "short": 0.0}
lev = wd[:, 0] + 3 * wd[:, 1]
out["avg_gross_leverage"] = float(lev.mean())

res = {}
runs = {}
for bps in (0, 1, 5, 10):
    r = bt.run(ts1, o1, c1, w1, DEV_START, 0.02, bps)
    res[f"{bps}bp"] = stats(r)
    runs[bps] = r
out["cost"] = res
yrs = res["1bp"]["fills"] and bt.stats(runs[1], BARS)["years"]
out["fills_per_year"] = res["1bp"]["fills"] / yrs
out["corr_vs_165d"] = corr_base(runs[1])

# leverage-matched static mix: TQQQ at avg_gross/3, rest BIL (2% band, i.e. ~daily drift rebal)
L = out["avg_gross_leverage"] / 3
ws = np.zeros_like(w1)
ws[:, 1] = L
ws[:, 2] = 1 - L
rs = bt.run(ts1, o1, c1, ws, DEV_START, 0.02, 1)
out["static_mix"] = {"tqqq_w": L, **stats(rs)}
# exposure-matched QQQ mix with the same time-in-market as QQQ-or-TQQQ
# per-year table
eq = daily(runs[1])
eq0 = daily(runs[0])
qd = pd.Series(c1[:, 0], index=ts1).resample("1D").last().dropna()
td = pd.Series(c1[:, 1], index=ts1).resample("1D").last().dropna()
sd = daily(rs)
yt = {}
for y in range(2016, 2024):
    def yr(s):
        prev = s[:str(y - 1)]
        cur = s[str(y)]
        p0 = prev.iloc[-1] if len(prev) and y > 2016 else cur.iloc[0]
        return float(cur.iloc[-1] / p0 - 1)
    yt[y] = {"strat_1bp": yr(eq), "strat_0bp": yr(eq0), "static_mix": yr(sd), "TQQQ": yr(td),
             "QQQ": yr(qd)}
out["per_year"] = yt

# gap decomposition on the 1-min grid (gross, 0 bp): log-return attribution by held state
lr = np.diff(np.log(c1[i1:]), axis=0)                    # per-minute log returns per asset
held = wd[:-1]                                           # weight held into the next minute (approx)
contrib_q = (held[:, 0] * lr[:, 0]).sum()
contrib_t = (held[:, 1] * lr[:, 1]).sum()
contrib_b = (held[:, 2] * lr[:, 2]).sum()
tq_total = lr[:, 1].sum()
tq_when_out = lr[:, 1][held[:, 1] == 0].sum()
tq_when_in = lr[:, 1][held[:, 1] > 0].sum()
q_when_bil = lr[:, 0][held[:, 2] == 1].sum()
q_when_q = lr[:, 0][held[:, 0] > 0].sum()
q_when_t = lr[:, 0][held[:, 1] > 0].sum()
out["attribution_logpts"] = {
    "TQQQ_total": float(tq_total), "TQQQ_while_strategy_not_in_TQQQ": float(tq_when_out),
    "TQQQ_while_in_TQQQ": float(tq_when_in),
    "QQQ_while_BIL": float(q_when_bil), "QQQ_while_QQQ": float(q_when_q),
    "QQQ_while_TQQQ": float(q_when_t),
    "strategy_QQQ_leg": float(contrib_q), "strategy_TQQQ_leg": float(contrib_t),
    "strategy_BIL_leg": float(contrib_b),
    "cost_drag_1bp_logpts": float(np.log(res["0bp"]["cagr"] + 1) * 8 - np.log(res["1bp"]["cagr"] + 1) * 8),
}
# overnight vs intraday QQQ split per state (decision at last bar of the day)
date = pd.DatetimeIndex(ts1[i1:]).date
last = np.r_[date[1:] != date[:-1], True][:-1]
out["overnight_QQQ_logpts_by_state"] = {
    "BIL": float(lr[last & (held[:, 2] == 1), 0].sum()),
    "QQQ": float(lr[last & (held[:, 0] > 0), 0].sum()),
    "TQQQ": float(lr[last & (held[:, 1] > 0), 0].sum()),
}
out["intraday_QQQ_logpts_by_state"] = {
    "BIL": float(lr[~last & (held[:, 2] == 1), 0].sum()),
    "QQQ": float(lr[~last & (held[:, 0] > 0), 0].sum()),
    "TQQQ": float(lr[~last & (held[:, 1] > 0), 0].sum()),
}
out["minutes_frac_by_state"] = {"BIL": float((held[:, 2] == 1).mean()), "QQQ": float((held[:, 0] > 0).mean()),
                                "TQQQ": float((held[:, 1] > 0).mean())}

# core signal events: each entry into A>=2 (risk-on episode). Return of QQQ over the episode,
# entry at next 5m open, exit at the next 5m open after leaving A>=2.
on = (st >= 2).astype(int)
ent = np.flatnonzero(np.diff(np.r_[0, on]) == 1)
ex = np.flatnonzero(np.diff(np.r_[on, 0]) == -1)
qo = o5[i5:, 0]
rets = []
for a, b in zip(ent, ex):
    if b + 2 < len(qo):
        rets.append(qo[b + 2] / qo[a + 1] - 1)   # fill at open a+1, exit fill at open b+2
rets = np.array(rets)
out["events_riskon"] = {"n": int(len(rets)), "per_year": float(len(rets) / 8), "hit_rate": float((rets > 0).mean()),
                        "mean_bp": float(rets.mean() * 1e4), "median_bp": float(np.median(rets) * 1e4),
                        "sum_logpts": float(np.log1p(rets).sum()),
                        "t_stat": float(rets.mean() / rets.std(ddof=1) * np.sqrt(len(rets)))}
# per-bar forward QQQ return conditional on state, vs unconditional (signal content per bar)
fr = qo[1:] / qo[:-1] - 1
fr = np.r_[fr[1:], np.nan, np.nan][:len(st)]  # return from open i+1 to open i+2 (held after decision i)
m = np.isfinite(fr)
out["fwd5m_bp_by_state"] = {k: float(np.nanmean(fr[m & (st == v)]) * 1e4) for k, v in
                            (("BIL", 0), ("QQQ", 2), ("TQQQ", 3))}
out["fwd5m_bp_all"] = float(np.nanmean(fr[m]) * 1e4)
(HERE / "diag_before.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
print(json.dumps(out, indent=2, default=float))
