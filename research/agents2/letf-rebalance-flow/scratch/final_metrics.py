"""Final metrics for the chosen late-rally overlay. One run each: base and overlay."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, "research")
sys.path.insert(0, str(HERE / "scratch"))
import bt
import lib

TH = 0.015
ts, opens, closes = lib.load_panel()
wd = lib.winner_daily(ts, opens, closes)
n_sess = len(wd["dates"]); starts, ends = wd["starts"], wd["ends"]; mins = wd["mins"]
base = lib.base_winner_weights(ts, wd)
prev_c = pd.Series(wd["qclose"]).shift(1).to_numpy()
p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 329)
p1558 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, 388)
run60 = p1459 / prev_c - 1.0
late60 = p1558 / p1459 - 1.0
events = (~wd["risk_on"]) & (run60 > TH)

w = base.copy()
for k in np.where(events)[0]:
    a, b = starts[k], ends[k]
    if b <= a:
        continue
    m = mins[a:b]
    sel = (m >= 329) & (m < 388)
    w[a:b][sel, 1] = 1.0
    w[a:b][sel, 2] = 0.0
    ii = np.where(m == 388)[0]
    if len(ii):
        i0 = a + ii[0]
        w[i0, 1] = 0.0; w[i0, 2] = 1.0
        w[b - 1, 1] = 0.0; w[b - 1, 2] = 1.0

out = {}
eqs = {}
for label, ww in [("strategy", w), ("winner", base)]:
    r = bt.run(ts, opens, closes, ww, "2017-01-03", band=0.02, slippage_bps=1.0)
    eqs[label] = r["equity"]
    for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
        rr = bt.run(ts, opens, closes, ww, start, band=0.02, slippage_bps=1.0)
        out[f"{label}_{win}_1bp"] = bt.stats(rr, 252 * 390)

# TQQQ benchmark
for start, win in [("2017-01-03", "10y"), ("2021-10-25", "5y")]:
    i = bt.start_index(ts, start)
    out[f"tqqq_{win}"] = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)
    out[f"qqq_{win}"] = bt.benchmark(closes[i:, 0], ts[i:], 252 * 390)

# yearly
i0 = bt.start_index(ts, "2017-01-03")
for label in ["strategy", "winner"]:
    out[f"yearly_{label}"] = bt.yearly(ts[i0:], eqs[label], closes[i0:, 1])

# daily equity
def daily_eq(eq):
    full = np.full(len(ts), np.nan)
    full[i0:] = eq
    d, e = lib.daily_equity(ts, full)
    m = d >= pd.Timestamp("2017-01-03", tz="America/New_York")
    return d[m], e[m]
dts, seq = daily_eq(eqs["strategy"])
_, weq = daily_eq(eqs["winner"])
# tqqq daily close
tq_full = lib.daily_close(ts, closes, wd["sess"], mins, n_sess, 1)
tq_all = pd.Series(tq_full, index=wd["dates"])
tq = tq_all.reindex(dts).to_numpy()

# rolling 3y, quarterly starts 2017-04 .. 2023-10
def wstats(dates, e, a, b):
    m = (dates >= a) & (dates < b)
    x = e[m]
    if len(x) < 3:
        return None
    t = dates[m]
    yrs = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return dict(cagr=float((x[-1] / x[0]) ** (1 / yrs) - 1),
                dd=float(-(x / peak - 1).min()), start=str(t[0].date()), end=str(t[-1].date()))

roll = []
starts_q = pd.date_range("2017-04-01", "2023-10-01", freq="QS")
for q in starts_q:
    a = pd.Timestamp(q, tz="America/New_York")
    b = a + pd.DateOffset(years=3)
    ss = wstats(dts, seq, a, b); ww = wstats(dts, weq, a, b); tt = wstats(dts, tq, a, b)
    if ss and ww and tt:
        roll.append(dict(start=str(a.date()), strat=ss, winner=ww, tqqq=tt,
                         ret_gt_tqqq=ss["cagr"] > tt["cagr"], dd_lt_tqqq=ss["dd"] < tt["dd"],
                         ret_gt_winner=ss["cagr"] > ww["cagr"], dd_lt_winner=ss["dd"] < ww["dd"]))
out["rolling3y"] = roll
out["rolling3y_counts"] = dict(
    n=len(roll),
    ret_gt_tqqq=sum(r["ret_gt_tqqq"] for r in roll),
    dd_lt_tqqq=sum(r["dd_lt_tqqq"] for r in roll),
    both_tqqq=sum(r["ret_gt_tqqq"] and r["dd_lt_tqqq"] for r in roll),
    ret_gt_winner=sum(r["ret_gt_winner"] for r in roll),
    dd_lt_winner=sum(r["dd_lt_winner"] for r in roll),
    both_winner=sum(r["ret_gt_winner"] and r["dd_lt_winner"] for r in roll),
)

# sub-periods
sub = {}
for a, b, tag in [("2017-01-03", "2020-01-01", "2017-19"),
                  ("2020-01-01", "2023-01-01", "2020-22"),
                  ("2023-01-01", "2026-10-24", "2023-26")]:
    sub[tag] = dict(strategy=wstats(dts, seq, pd.Timestamp(a, tz="America/New_York"), pd.Timestamp(b, tz="America/New_York")),
                    winner=wstats(dts, weq, pd.Timestamp(a, tz="America/New_York"), pd.Timestamp(b, tz="America/New_York")))
    i = int(dts.searchsorted(pd.Timestamp(a, tz="America/New_York")))
    j = int(dts.searchsorted(pd.Timestamp(b, tz="America/New_York")))
    sub[tag]["tqqq"] = wstats(dts, tq, pd.Timestamp(a, tz="America/New_York"), pd.Timestamp(b, tz="America/New_York"))
out["subperiods"] = sub

# max DD dates (minute marks)
for label in ["strategy", "winner"]:
    e = eqs[label]
    peak = np.maximum.accumulate(e)
    dd = e / peak - 1
    i = int(np.argmin(dd))
    j = int(np.argmax(e[:i + 1]))
    out[f"{label}_maxdd_dates"] = [str(ts[j].date()), str(ts[i].date())]

# daily return correlation and incremental
sret = pd.Series(seq).pct_change()
wret = pd.Series(weq).pct_change()
out["corr_daily_strategy_winner"] = float(sret.corr(wret))
out["corr_incremental_winner"] = float((sret - wret).corr(wret))
out["incremental_ann_mean"] = float((sret - wret).mean() * 252)
out["incremental_ann_vol"] = float((sret - wret).std() * np.sqrt(252))
out["incremental_sharpe"] = float((sret - wret).mean() / (sret - wret).std() * np.sqrt(252))

# event stats (TQQQ 15:00->15:59 and overnight)
def stats(r):
    r = r.dropna()
    return dict(n=int(len(r)), mean_bp=float(r.mean() * 1e4), med_bp=float(r.median() * 1e4),
                hit=float((r > 0).mean()),
                t=float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 2 else None)

# use daily2 event frame components
t_o = lib.session_series(opens[:, 1], wd["sess"], mins, n_sess, 0)
t_c = lib.session_series(closes[:, 1], wd["sess"], mins, n_sess, 389)
t_o1500 = lib.session_series(opens[:, 1], wd["sess"], mins, n_sess, 330)
t_p1558 = lib.session_series(closes[:, 1], wd["sess"], mins, n_sess, 388)
late_t = pd.Series(t_p1558 / t_o1500 - 1)
next_open = np.full(n_sess, np.nan); next_open[:-1] = t_o[1:]
on = pd.Series(next_open / t_c - 1)
ev_df = pd.DataFrame({"date": wd["dates"], "event": events, "run": run60, "late": late_t, "on": on})
ev_df = ev_df[ev_df["date"] >= pd.Timestamp("2017-01-03", tz="America/New_York")]
out["event_stats"] = stats(ev_df.loc[ev_df.event, "late"])
out["event_stats_overnight"] = stats(ev_df.loc[ev_df.event, "on"])
out["event_counts_by_year"] = {int(y): int(g["event"].sum()) for y, g in ev_df.groupby(ev_df["date"].dt.year)}
# non-event risk-off days: late return
out["nonevent_riskoff_late"] = stats(ev_df.loc[~ev_df.event & (~wd["risk_on"][-len(ev_df):]), "late"])

# save daily equity for reference
pd.DataFrame({"date": dts, "strategy": seq, "winner": weq, "tqqq": tq}).to_pickle(HERE / "daily_equity.pkl")

def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o

with open(HERE / "metrics_tmp.json", "w") as f:
    json.dump(clean(out), f, indent=2)
print(json.dumps(clean({k: out[k] for k in ["strategy_10y_1bp", "strategy_5y_1bp", "winner_10y_1bp", "winner_5y_1bp",
                                            "tqqq_10y", "tqqq_5y", "rolling3y_counts", "corr_daily_strategy_winner",
                                            "corr_incremental_winner", "incremental_ann_mean", "incremental_ann_vol",
                                            "incremental_sharpe", "event_stats", "event_stats_overnight",
                                            "event_counts_by_year", "nonevent_riskoff_late",
                                            "strategy_maxdd_dates", "winner_maxdd_dates"]}), indent=2))
print("\nyearly strategy", {k: round(v["strategy"]*100, 2) for k, v in out["yearly_strategy"].items()})
print("yearly winner", {k: round(v["strategy"]*100, 2) for k, v in out["yearly_winner"].items()})
print("yearly tqqq", {k: round(v["benchmark"]*100, 2) for k, v in out["yearly_strategy"].items()})
print("\nsubperiods", json.dumps(clean(out["subperiods"]), indent=1))
