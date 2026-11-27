"""Build result.json for the intraday-mean-reversion agent."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import strategy as S  # noqa: E402

RULE = "5min"
S.RULE = RULE
ts, o, c, feats = S.prepare(RULE)
n = len(ts)

w, stops = S.make_weights(feats, n, 0.03)
out = {
    "agent": "intraday-mean-reversion",
    "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "data": {
        "symbols": ["QQQ", "TQQQ", "BIL"],
        "source": "data/intraday-hf adjusted 1-minute bars, regular session only",
        "decision_bars": "5-minute (1-minute control reported)",
        "warmup": "500 calendar days (data starts 2016-01-04)",
        "no_lookahead": "signal at bar i uses data through bar i; fill at open i+1",
    },
    "rules": {
        "regime": "QQQ close > 165-day SMA of QQQ closes -> long TQQQ, else BIL; evaluated at the 15:59 close, executed at the next 09:30 open",
        "stop": "while long TQQQ: if QQQ <= -3.0% vs previous daily close at any 5-minute close, sell to BIL at the next 5-minute open and stay in BIL for the rest of the session",
        "reentry": "next session 09:30 open if the regime is still on (post-capitulation mean-reversion re-entry)",
        "exit": "no other exits; overnight exposure held while the regime is on",
        "costs": "1bp slippage on traded notional (primary), 5/10/20bp sensitivity",
    },
    "windows": {},
    "yearly": {},
    "cost_sensitivity": {},
    "parameter_grid": [],
    "walk_forward": [],
    "ablations": {},
    "event_study": {},
}

for start, key in ((S.START10, "10y"), (S.START5, "5y")):
    s, b, res, i0 = S.metrics(ts, o, c, w, start, 1.0)
    dm = S.daily_marked(res)
    out["windows"][key] = {
        "start": start, "end": S.END,
        "cagr": round(float(s["cagr"]), 6),
        "max_drawdown_5m_marked": round(float(s["max_drawdown"]), 6),
        "sharpe_5m": round(float(s["sharpe"]), 4),
        "sortino_5m": round(float(s["sortino"]), 4),
        "volatility_5m": round(float(s["volatility"]), 6),
        "cagr_daily_marked": round(float(dm["cagr"]), 6),
        "max_drawdown_daily_marked": round(float(dm["max_drawdown"]), 6),
        "sharpe_daily": round(float(dm["sharpe"]), 4),
        "fills": int(s["fills"]),
        "turnover_x_start_equity": round(float(s["turnover"]), 1),
        "ending_equity": round(float(s["ending_equity"]), 2),
        "years": round(float(s["years"]), 3),
        "bench_cagr": round(float(b["cagr"]), 6),
        "bench_max_drawdown_5m_marked": round(float(b["max_drawdown"]), 6),
        "bench_sharpe": round(float(b["sharpe"]), 4),
        "bench_max_drawdown_daily": 0.8168,
    }
    if key == "10y":
        out["yearly"] = S.yearly_table(res, c[i0:, 1])

for slip in (0.0, 1.0, 5.0, 10.0, 20.0):
    row = {}
    for start, key in ((S.START10, "10y"), (S.START5, "5y")):
        s, b, _, _ = S.metrics(ts, o, c, w, start, slip)
        row[key] = {"cagr": round(float(s["cagr"]), 6),
                    "max_drawdown_5m_marked": round(float(s["max_drawdown"]), 6),
                    "sharpe": round(float(s["sharpe"]), 4)}
    out["cost_sensitivity"][f"{slip:.0f}bp"] = row

# parameter grid (stop sweep, including no-stop baseline)
for stop in (0.010, 0.015, 0.020, 0.0225, 0.025, 0.0275, 0.030, 0.0325, 0.035, 0.040, 0.050, 1.0):
    wg, ns = S.make_weights(feats, n, stop)
    row = {"stop": stop, "stop_events": int(ns)}
    for slip in (1.0, 5.0):
        for start, key in ((S.START10, "10y"), (S.START5, "5y")):
            s, b, _, _ = S.metrics(ts, o, c, wg, start, slip)
            row[f"{key}_{slip:.0f}bp"] = {
                "cagr": round(float(s["cagr"]), 6),
                "max_drawdown_5m_marked": round(float(s["max_drawdown"]), 6),
                "sharpe": round(float(s["sharpe"]), 4),
            }
    out["parameter_grid"].append(row)

# walk-forward
dates_arr = np.array([d for d in ts.date])
for a, bnd in (("2017-01-03", "2019-12-31"), ("2020-01-01", "2022-12-31"), ("2023-01-01", "2026-10-23")):
    i0 = max(0, int(np.searchsorted(dates_arr, pd.Timestamp(a).date(), "left")) - 1)
    i1 = int(np.searchsorted(dates_arr, pd.Timestamp(bnd).date(), "right")) - 1
    res = S.bt.simulate(ts[i0:i1 + 1], o[i0:i1 + 1], c[i0:i1 + 1], w[i0:i1 + 1],
                        band=0.0, slippage_bps=1.0)
    st = S.bt.stats(res, S.BARS_PER_YEAR[RULE])
    bm = S.bt.benchmark(c[i0:i1 + 1, 1], ts[i0:i1 + 1], S.BARS_PER_YEAR[RULE])
    out["walk_forward"].append({
        "start": a, "end": bnd,
        "strategy_cagr": round(float(st["cagr"]), 6),
        "strategy_max_drawdown": round(float(st["max_drawdown"]), 6),
        "strategy_sharpe": round(float(st["sharpe"]), 4),
        "tqqq_cagr": round(float(bm["cagr"]), 6),
        "tqqq_max_drawdown": round(float(bm["max_drawdown"]), 6),
    })

# ablations
def stats_for(stop, slip=1.0, key="10y"):
    start = S.START10 if key == "10y" else S.START5
    ww, _ = S.make_weights(feats, n, stop)
    s, b, _, _ = S.metrics(ts, o, c, ww, start, slip)
    return {"cagr": round(float(s["cagr"]), 6), "max_drawdown": round(float(s["max_drawdown"]), 6),
            "sharpe": round(float(s["sharpe"]), 4), "fills": int(s["fills"])}

out["ablations"] = {
    "no_stop_daily_regime_only_10y": stats_for(1.0, 1.0, "10y"),
    "no_stop_daily_regime_only_5y": stats_for(1.0, 1.0, "5y"),
    "stop_3pct_10y": stats_for(0.03, 1.0, "10y"),
    "stop_3pct_5y": stats_for(0.03, 1.0, "5y"),
}

# event study
date, bars, qqq, qpc = feats["dlist"], feats["bars"], feats["qqq"], feats["qpc"]
stop_idx = [i for i in range(1, n - 1) if w[i, 1] == 0 and w[i - 1, 1] == 1
            and np.isfinite(qpc[i]) and qqq[i] / qpc[i] - 1 <= -0.03]
ev = []
for i in stop_idx:
    j = max(k for k in range(i, n) if date[k] == date[i])
    if j + 1 >= n:
        continue
    k0 = j + 1
    k1 = max(k for k in range(k0, min(k0 + 100, n)) if date[k] == date[k0])
    ev.append({"date": str(date[i]),
               "rest_of_session": float(c[j, 1] / o[i + 1, 1] - 1.0),
               "overnight_gap": float(o[k0, 1] / c[j, 1] - 1.0),
               "next_session_open_close": float(c[k1, 1] / o[k0, 1] - 1.0),
               "hold_from_exit_to_next_open": float(o[k0, 1] / o[i + 1, 1] - 1.0)})
e = pd.DataFrame(ev)
out["event_study"] = {
    "n_events": int(len(e)),
    "mean_qqq_drawdown_at_trigger": round(float(np.mean([qqq[i] / qpc[i] - 1.0 for i in stop_idx])), 6),
    "mean_rest_of_session": round(float(e["rest_of_session"].mean()), 6),
    "mean_overnight_gap_avoided": round(float(e["overnight_gap"].mean()), 6),
    "mean_next_session_open_close_captured": round(float(e["next_session_open_close"].mean()), 6),
    "mean_stop_minus_hold": round(float(-e["hold_from_exit_to_next_open"].mean()), 6),
    "stop_minus_hold_t_stat": round(float(-e["hold_from_exit_to_next_open"].mean()
                                          / e["hold_from_exit_to_next_open"].std()
                                          * np.sqrt(len(e))), 2),
}

# verdict vs TQQQ
v10 = out["windows"]["10y"]
v5 = out["windows"]["5y"]
out["verdict"] = {
    "benchmark_10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
    "benchmark_5y": {"cagr": 0.1347, "max_drawdown": 0.8168},
    "pass_10y": bool(v10["cagr"] > 0.3928 and v10["max_drawdown_5m_marked"] < 0.8168),
    "pass_5y": bool(v5["cagr"] > 0.1347 and v5["max_drawdown_5m_marked"] < 0.8168),
    "beats_daily_baseline_10y": bool(v10["cagr"] > 0.4531 and v10["max_drawdown_5m_marked"] < 0.5871),
    "beats_daily_baseline_5y": bool(v5["cagr"] > 0.3461 and v5["max_drawdown_5m_marked"] < 0.3686),
}
out["verdict"]["pass"] = out["verdict"]["pass_10y"] and out["verdict"]["pass_5y"]

path = HERE.parent / "result.json"
path.write_text(json.dumps(out, indent=2))
print("wrote", path)
print(json.dumps(out["windows"], indent=2))
print(json.dumps(out["event_study"], indent=2))
print(json.dumps(out["verdict"], indent=2))
