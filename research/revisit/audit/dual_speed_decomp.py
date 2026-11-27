"""Exact P&L attribution and correlation checks for the dual-speed audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit" / "audit"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "revisit" / "dual-speed-regime"))
import bt  # noqa: E402
import strategy as S  # noqa: E402

TZ = "America/New_York"
START, FULL_END = "2016-01-04", "2026-10-23"


def stats(r):
    s = bt.stats(r, S.BPY)
    return {k: float(s[k]) for k in
            ("cagr", "max_drawdown", "sharpe", "volatility", "fills",
             "turnover", "exposure", "ending_equity", "years")}


def daily_ret(r):
    eq = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
    return eq.groupby(eq.index.date).last().pct_change().dropna()


ts, o, c = bt.panel(S.SYMS, START, FULL_END, "1min", warmup_days=500)
w, info = S.build_weights(ts, o, c)
r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
eq, cash = r["equity"], r["cash"]

# Current variant holds only TQQQ + cash, so TQQQ value at each close is exact.
Vt = eq - cash
gap = np.zeros(len(ts))
intra = np.zeros(len(ts))
cost = np.zeros(len(ts))
for i in range(1, len(ts)):
    gap[i] = Vt[i - 1] * (o[i, 1] / c[i - 1, 1] - 1.0)
    vclose = eq[i] - cash[i]
    vafter = vclose * o[i, 1] / c[i, 1]
    intra[i] = vclose - vafter
    cost[i] = gap[i] + intra[i] - (eq[i] - eq[i - 1])

idx = pd.DatetimeIndex(ts)
hour = idx.hour.to_numpy()
minute = idx.minute.to_numpy()
tod = np.where((hour == 9) & (minute == 30), "09:30_gap+minute",
       np.where((hour >= 10) & ((hour < 15) | ((hour == 15) & (minute <= 29))),
                "10:30-15:29", "15:30-15:59"))

out = {
    "gross_pnl": float(gap.sum() + intra.sum()),
    "net_pnl": float(eq[-1] - eq[0]),
    "total_cost": float(cost.sum()),
    "gap_pnl": float(gap.sum()),
    "intra_pnl": float(intra.sum()),
    "gap_share_of_gross": float(gap.sum() / (gap.sum() + intra.sum())),
    "intra_share_of_gross": float(intra.sum() / (gap.sum() + intra.sum())),
    "by_time_of_day": {},
    "by_year": {},
}
for label in ("09:30_gap+minute", "10:30-15:29", "15:30-15:59"):
    m = tod == label
    out["by_time_of_day"][label] = {
        "gap_pnl": float(gap[m].sum()),
        "intra_pnl": float(intra[m].sum()),
        "total": float(gap[m].sum() + intra[m].sum()),
        "minutes": int(m.sum()),
    }
for y in range(2016, 2027):
    m = idx.year == y
    if not m.any():
        continue
    out["by_year"][str(y)] = {
        "gap_pnl": float(gap[m].sum()),
        "intra_pnl": float(intra[m].sum()),
        "net_equity_change": float(eq[m][-1] - eq[m][0]),
    }

# First-hour exposure: how many minutes in 09:31..10:29 carry a nonzero weight?
first_hour = (hour == 9) & (minute >= 31) | ((hour == 10) & (minute <= 29))
out["first_hour_0931_1029"] = {
    "minutes": int(first_hour.sum()),
    "minutes_nonzero_weight": int((w[first_hour, 1] > 0).sum()),
    "max_weight": float(w[first_hour, 1].max()),
}

# Overnight gap: held vs not held, and the conditional TQQQ return.
dates, first, last, day_id = S.day_index(ts)
on_held, on_flat = [], []
for k in range(1, len(first)):
    f, pl = first[k], last[k - 1]
    if last[k] - f + 1 < 300 or pl - first[k - 1] + 1 < 300:
        continue
    ret = o[f, 1] / c[pl, 1] - 1.0
    (on_held if w[pl - 1, 1] > 0 else on_flat).append(ret)
out["overnight_conditional"] = {
    "n_held": len(on_held), "n_flat": len(on_flat),
    "mean_ret_held": float(np.mean(on_held)), "mean_ret_flat": float(np.mean(on_flat)),
    "sum_log_held": float(np.log1p(on_held).sum()),
    "sum_log_flat": float(np.log1p(on_flat).sum()),
    "avg_weight_held": float(np.mean([w[last[k - 1] - 1, 1] for k in range(1, len(first))
                                      if last[k] - first[k] + 1 >= 300
                                      and w[last[k - 1] - 1, 1] > 0])) if on_held else 0.0,
}

# Daily-return correlations.
sr = daily_ret(r)
tq = pd.Series(c[:, 1], index=pd.DatetimeIndex(ts))
tqd = tq.groupby(tq.index.date).last().pct_change().dropna()
qq = pd.Series(c[:, 0], index=pd.DatetimeIndex(ts))
qqd = qq.groupby(qq.index.date).last().pct_change().dropna()
j = pd.concat([sr, tqd, qqd], axis=1, join="inner").dropna()
j.columns = ["strat", "tqqq", "qqq"]
out["corr_daily"] = {
    "n": int(len(j)),
    "vs_tqqq": float(j["strat"].corr(j["tqqq"])),
    "vs_qqq": float(j["strat"].corr(j["qqq"])),
    "active_days": int((j["strat"] != 0).sum()),
    "vs_tqqq_active": float(j[j["strat"] != 0]["strat"].corr(j[j["strat"] != 0]["tqqq"])),
}

# Holdout windows: current vs pre-tune.
w_pre, _ = S.build_weights(ts, o, c, overnight=False, idle="bil")
r_pre = bt.run(ts, o, c, w_pre, START, band=0.02, slippage_bps=1.0)


def slice_stats(run, a, z):
    i = bt.start_index(run["ts"], a)
    j = int(np.searchsorted(pd.DatetimeIndex(run["ts"]), pd.Timestamp(z, tz=TZ)))
    rr = {k: (np.asarray(v)[i:j] if isinstance(v, (list, np.ndarray)) else v)
          for k, v in run.items()}
    rr["ts"] = pd.DatetimeIndex(run["ts"])[i:j]
    return stats(rr)


out["windows"] = {
    "current": {
        "dev": slice_stats(r, START, "2023-12-30"),
        "holdout_2024_2026": slice_stats(r, "2024-01-02", "2026-10-24"),
        "full": stats(r),
    },
    "pretune_intraday_bil": {
        "dev": slice_stats(r_pre, START, "2023-12-30"),
        "holdout_2024_2026": slice_stats(r_pre, "2024-01-02", "2026-10-24"),
        "full": stats(r_pre),
    },
}

# Yearly returns, current and pre-tune, for the 2024-2026 holdout.
yr = {}
for y in range(2016, 2027):
    m = idx.year == y
    if not m.any():
        continue
    yr[str(y)] = {
        "current": float(r["equity"][m][-1] / r["equity"][m][0] - 1.0),
        "pretune": float(r_pre["equity"][m][-1] / r_pre["equity"][m][0] - 1.0),
        "tqqq": float(c[m, 1][-1] / c[m, 1][0] - 1.0),
    }
out["yearly"] = yr

(HERE / "dual_speed_decomp.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1)[:12000])
