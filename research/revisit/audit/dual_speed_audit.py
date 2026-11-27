"""Causality / reproduction audit for research/revisit/dual-speed-regime.

Read-only with respect to the strategy: imports strategy.py, never edits it.
Writes dual_speed_audit.json and dual_speed_causal_curve.json in this dir.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit" / "audit"
STRAT = ROOT / "research" / "revisit" / "dual-speed-regime"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(STRAT))

import bt  # noqa: E402
import strategy as S  # noqa: E402

TZ = "America/New_York"
FULL_END = "2026-10-23"
DEV_END = "2023-12-29"
START = "2016-01-04"
BAND = 0.02

OUT = {}
T0 = time.perf_counter()


def log(*a):
    print(f"[{time.perf_counter() - T0:7.1f}s]", *a, flush=True)


def clean(x):
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def stat_block(r, bpy=S.BPY):
    s = bt.stats(r, bpy)
    keys = ("cagr", "total_return", "max_drawdown", "sharpe", "sortino",
            "volatility", "exposure", "fills", "turnover", "ending_equity", "years")
    return {k: float(s[k]) for k in keys}


def daily_curve(r):
    eq = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
    daily = eq.groupby(eq.index.date).last()
    return daily / daily.iloc[0] * 100.0


def daily_stats(r):
    """Daily-close CAGR / DD / Sharpe, 252 sessions."""
    d = daily_curve(r).to_numpy()
    rets = d[1:] / d[:-1] - 1.0
    yrs = len(d) / 252.0
    peak = np.maximum.accumulate(d)
    return {
        "cagr": float((d[-1] / d[0]) ** (1.0 / yrs) - 1.0),
        "max_drawdown": float(-(d / peak - 1.0).min()),
        "sharpe": float(np.mean(rets) / np.std(rets, ddof=0) * np.sqrt(252.0)),
        "volatility": float(np.std(rets, ddof=0) * np.sqrt(252.0)),
        "n_days": int(len(d)),
    }


def slice_run(ts, o, c, w, start=START, end_exclusive=None):
    i = bt.start_index(ts, start)
    if end_exclusive is None:
        j = len(ts)
    else:
        j = int(np.searchsorted(ts, pd.Timestamp(end_exclusive, tz=TZ)))
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=BAND, slippage_bps=1.0)


# --------------------------------------------------------------------------- #
# 1. development panel and reproduction
# --------------------------------------------------------------------------- #
log("loading development panel 2016-01-04..2023-12-29 (1min)")
ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
log(f"dev panel {len(ts):,} bars, {ts[0]} .. {ts[-1]}")

w_dev, info_dev = S.build_weights(ts, o, c)
r_dev = bt.run(ts, o, c, w_dev, S.DEV_START, band=BAND, slippage_bps=1.0)
stored = json.loads((STRAT / "result.json").read_text())["windows"]["dev"]["1bp"]

OUT["dev_current"] = {
    "stats": stat_block(r_dev),
    "daily_stats": daily_stats(r_dev),
    "info": clean(info_dev),
    "stored_result_json": {k: stored[k] for k in
                           ("cagr", "max_drawdown", "sharpe", "fills", "ending_equity")},
    "delta_vs_stored": {
        "cagr": stat_block(r_dev)["cagr"] - stored["cagr"],
        "max_drawdown": stat_block(r_dev)["max_drawdown"] - stored["max_drawdown"],
        "sharpe": stat_block(r_dev)["sharpe"] - stored["sharpe"],
        "fills": stat_block(r_dev)["fills"] - stored["fills"],
        "ending_equity": stat_block(r_dev)["ending_equity"] - stored["ending_equity"],
    },
}
log("DEV current  CAGR %.4f%%  DD %.4f%%  Sharpe %.4f  fills %d  end %.2f" % (
    100 * OUT["dev_current"]["stats"]["cagr"],
    100 * OUT["dev_current"]["stats"]["max_drawdown"],
    OUT["dev_current"]["stats"]["sharpe"],
    OUT["dev_current"]["stats"]["fills"],
    OUT["dev_current"]["stats"]["ending_equity"]))
log("DEV stored   CAGR %.4f%%  DD %.4f%%  Sharpe %.4f  fills %d  end %.2f" % (
    100 * stored["cagr"], 100 * stored["max_drawdown"], stored["sharpe"],
    stored["fills"], stored["ending_equity"]))

# pre-tune / intraday variants on the same panel
variant_specs = {
    "pretune_intraday_bil": dict(overnight=False, idle="bil"),
    "pretune_intraday_cash": dict(overnight=False, idle="cash"),
    "overnight_cash": dict(overnight=True, idle="cash"),
    "overnight_bil": dict(overnight=True, idle="bil"),
}
OUT["dev_variants"] = {}
dev_variant_weights = {}
for name, kw in variant_specs.items():
    w, inf = S.build_weights(ts, o, c, **kw)
    r = bt.run(ts, o, c, w, S.DEV_START, band=BAND, slippage_bps=1.0)
    OUT["dev_variants"][name] = {
        "kwargs": kw, "stats": stat_block(r), "daily_stats": daily_stats(r),
        "info": clean(inf),
    }
    dev_variant_weights[name] = w
    log("DEV %-24s CAGR %7.3f%%  DD %6.3f%%  Sharpe %.3f  fills %d" % (
        name, 100 * OUT["dev_variants"][name]["stats"]["cagr"],
        100 * OUT["dev_variants"][name]["stats"]["max_drawdown"],
        OUT["dev_variants"][name]["stats"]["sharpe"],
        OUT["dev_variants"][name]["stats"]["fills"]))

# published dev-only curve (captured 12:45) should be the current code
dev_curve_path = ROOT / "research" / "revisit" / "curves" / "dual-speed-regime.json"
if dev_curve_path.exists():
    dc = json.loads(dev_curve_path.read_text())
    dv = np.asarray(dc["values"], float)
    ours = daily_curve(r_dev).to_numpy()
    OUT["dev_curve_compare"] = {
        "file": str(dev_curve_path.relative_to(ROOT)),
        "n_dates_file": len(dc["dates"]), "n_dates_ours": len(ours),
        "max_abs_diff": float(np.max(np.abs(dv - ours))) if len(dv) == len(ours) else None,
        "last_file": float(dv[-1]), "last_ours": float(ours[-1]),
    }
    log("DEV curve compare max|diff| =", OUT["dev_curve_compare"]["max_abs_diff"])

# --------------------------------------------------------------------------- #
# 2. full causal panel (2016-01-04 .. 2026-10-23, warmup before 2016)
# --------------------------------------------------------------------------- #
log("loading FULL panel 2016-01-04..2026-10-23 (1min)")
ts_f, o_f, c_f = bt.panel(S.SYMS, START, FULL_END, "1min", warmup_days=500)
log(f"full panel {len(ts_f):,} bars, {ts_f[0]} .. {ts_f[-1]}")
w_full, info_full = S.build_weights(ts_f, o_f, c_f)
r_full = bt.run(ts_f, o_f, c_f, w_full, START, band=BAND, slippage_bps=1.0)
OUT["full_current"] = {
    "stats": stat_block(r_full), "daily_stats": daily_stats(r_full),
    "info": clean(info_full),
}
log("FULL current CAGR %.4f%%  DD %.4f%%  Sharpe %.4f  fills %d  end %.2f" % (
    100 * OUT["full_current"]["stats"]["cagr"],
    100 * OUT["full_current"]["stats"]["max_drawdown"],
    OUT["full_current"]["stats"]["sharpe"],
    OUT["full_current"]["stats"]["fills"],
    OUT["full_current"]["stats"]["ending_equity"]))

# dev slice of the *same* full-panel weight matrix
r_full_dev = slice_run(ts_f, o_f, c_f, w_full, START, "2023-12-30")
OUT["dev_from_full_panel"] = {
    "stats": stat_block(r_full_dev), "daily_stats": daily_stats(r_full_dev),
    "delta_vs_stored": {
        "cagr": stat_block(r_full_dev)["cagr"] - stored["cagr"],
        "max_drawdown": stat_block(r_full_dev)["max_drawdown"] - stored["max_drawdown"],
        "sharpe": stat_block(r_full_dev)["sharpe"] - stored["sharpe"],
        "ending_equity": stat_block(r_full_dev)["ending_equity"] - stored["ending_equity"],
    },
}
log("DEV slice of full-panel run CAGR %.4f%%  DD %.4f%%  Sharpe %.4f" % (
    100 * OUT["dev_from_full_panel"]["stats"]["cagr"],
    100 * OUT["dev_from_full_panel"]["stats"]["max_drawdown"],
    OUT["dev_from_full_panel"]["stats"]["sharpe"]))

# weight-prefix identity: dev panel vs full panel
n_dev = len(ts)
prefix = w_full[:n_dev]
OUT["weight_prefix_dev_vs_full"] = {
    "bars": int(n_dev),
    "max_abs_diff": float(np.max(np.abs(prefix - w_dev))),
    "n_diff_bars": int((np.abs(prefix - w_dev).max(axis=1) > 1e-12).sum()),
    "ts_last_compared": str(ts[n_dev - 1]),
}

# --------------------------------------------------------------------------- #
# 3. cut tests on the full panel
# --------------------------------------------------------------------------- #
def truncated_last_bar_end(ts_cut, c_cut):
    dates, first, last, day_id = S.day_index(ts_cut)
    ends, _, _ = S.bars_60m(c_cut[:, 0], first, last)
    return int(ends[-1])


OUT["cut_tests"] = {}
for label, cut in (("cut1_2020-03-12_11:07", "2020-03-12 11:07"),
                   ("cut2_2022-09-13_10:41", "2022-09-13 10:41")):
    cut_ts = pd.Timestamp(cut, tz=TZ)
    n_cut = int(np.searchsorted(ts_f, cut_ts))
    ts_c, o_c, c_c = ts_f[:n_cut], o_f[:n_cut], c_f[:n_cut]
    w_cut, info_cut = S.build_weights(ts_c, o_c, c_c)
    last_end = truncated_last_bar_end(ts_c, c_c)
    diff = np.abs(w_cut - w_full[:n_cut]).max(axis=1)
    diff_all_idx = np.flatnonzero(diff > 1e-12)
    diff_pre_idx = np.flatnonzero(diff[:last_end] > 1e-12)
    OUT["cut_tests"][label] = {
        "cut_ts": cut, "bars_in_truncated_panel": int(n_cut),
        "truncated_last_bar_end": str(ts_c[last_end]),
        "max_abs_diff_all_bars": float(diff.max()) if len(diff) else 0.0,
        "n_diff_bars_all": int(len(diff_all_idx)),
        "diff_bar_times_all": [str(ts_c[i]) for i in diff_all_idx[:5]],
        "bars_before_truncated_last_bar": int(last_end),
        "max_abs_diff_before_last_bar": float(diff[:last_end].max()) if last_end else 0.0,
        "n_diff_bars_before_last_bar": int(len(diff_pre_idx)),
        "clean_before_last_bar": bool(len(diff_pre_idx) == 0),
        "info_truncated": clean(info_cut),
    }
    log("CUT %s: diff before final partial bar = %.3g (%d bars); all-bar diff = %.3g (%d bars)" % (
        cut, OUT["cut_tests"][label]["max_abs_diff_before_last_bar"],
        OUT["cut_tests"][label]["n_diff_bars_before_last_bar"],
        OUT["cut_tests"][label]["max_abs_diff_all_bars"],
        OUT["cut_tests"][label]["n_diff_bars_all"]))

# --------------------------------------------------------------------------- #
# 4. pre-tune full curve: does it reproduce curves_full exactly?
# --------------------------------------------------------------------------- #
OUT["full_pretune"] = {}
for name in ("pretune_intraday_bil", "pretune_intraday_cash", "overnight_bil"):
    w, inf = S.build_weights(ts_f, o_f, c_f, **variant_specs[name])
    r = bt.run(ts_f, o_f, c_f, w, START, band=BAND, slippage_bps=1.0)
    OUT["full_pretune"][name] = {
        "stats": stat_block(r), "daily_stats": daily_stats(r), "info": clean(inf),
    }
    log("FULL %-24s CAGR %7.3f%%  DD %6.3f%%  Sharpe %.3f  fills %d" % (
        name, 100 * OUT["full_pretune"][name]["stats"]["cagr"],
        100 * OUT["full_pretune"][name]["stats"]["max_drawdown"],
        OUT["full_pretune"][name]["stats"]["sharpe"],
        OUT["full_pretune"][name]["stats"]["fills"]))
    if name == "pretune_intraday_bil":
        r_pre_full = r
        w_pre_full = w

curves_full_path = ROOT / "research" / "revisit" / "curves_full" / "dual-speed-regime.json"
if curves_full_path.exists():
    cf = json.loads(curves_full_path.read_text())
    fv = np.asarray(cf["values"], float)
    pre_daily = daily_curve(r_pre_full).to_numpy()
    cur_daily = daily_curve(r_full).to_numpy()
    same_len = len(fv) == len(pre_daily) == len(cur_daily)
    OUT["curves_full_compare"] = {
        "file": str(curves_full_path.relative_to(ROOT)),
        "n_dates": len(cf["dates"]), "dates_first": cf["dates"][0],
        "dates_last": cf["dates"][-1],
        "max_abs_diff_pretune_bil": float(np.max(np.abs(fv - pre_daily))) if same_len else None,
        "max_abs_diff_current": float(np.max(np.abs(fv - cur_daily))) if same_len else None,
        "last_curve": float(fv[-1]),
        "last_pretune_bil": float(pre_daily[-1]) if same_len else None,
        "last_current": float(cur_daily[-1]) if same_len else None,
        "metrics_file": cf.get("metrics", {}),
    }
    log("CURVES_FULL compare: pre-tune max|diff| =", OUT["curves_full_compare"]["max_abs_diff_pretune_bil"],
        " current max|diff| =", OUT["curves_full_compare"]["max_abs_diff_current"])

# --------------------------------------------------------------------------- #
# 5. yearly and overnight decomposition (current variant)
# --------------------------------------------------------------------------- #
years = sorted(set(ts_f.year))
yr = {}
for y in years:
    m = ts_f.year == y
    if m.sum() < 2:
        continue
    eq = r_full["equity"][m]
    b = c_f[m, 1]
    yr[int(y)] = {
        "strategy": float(eq[-1] / eq[0] - 1.0),
        "tqqq": float(b[-1] / b[0] - 1.0),
    }
OUT["yearly_current"] = yr

# Overnight vs intraday contribution of the current weights, approximate:
# shares held over the close->open gap are the target set at the previous bar
# (w[l_prev - 1]), exactly as bt.simulate executes fills.
dates, first, last, day_id = S.day_index(ts_f)
on_log, id_log, last30_log = 0.0, 0.0, 0.0
on_exposure, id_exposure = 0.0, 0.0
n_sess = 0
for k in range(1, len(first)):
    f, l = first[k], last[k]
    pf, pl = first[k - 1], last[k - 1]
    if l - f + 1 < 300 or pl - pf + 1 < 300:
        continue
    n_sess += 1
    on = np.log(o_f[f, 1] / c_f[pl, 1])
    # overnight position: weight at the last minute of the prior session is
    # executed at the prior close? bt fills w[pl-1] at open[pl]; shares then
    # ride close[pl] -> open[f].  Use w[pl-1].
    won = float(w_full[pl - 1, 1])
    on_log += won * on
    on_exposure += won
    # intraday 09:30 open -> 15:59 close, weight after the 09:30 fill is
    # w[f-1] (set on the prior session's last bar) for the first minute, then
    # the 09:30 bar's own weight from 10:30.  Approximate with the time-average
    # of w over the session.
    wid = float(np.mean(w_full[f:l + 1, 1]))
    id_log += wid * np.log(c_f[l, 1] / o_f[f, 1])
    id_exposure += wid
    # last 30 minutes 15:29 close -> 15:59 close
    if l - f + 1 == 390:
        last30_log += float(w_full[f + 359, 1]) * np.log(c_f[l, 1] / c_f[f + 359, 1])
OUT["decomposition_current"] = {
    "n_sessions": n_sess,
    "overnight_log_sum": float(on_log),
    "overnight_cagr_equiv": float(np.exp(on_log / (n_sess / 252.0)) - 1.0),
    "avg_overnight_weight_on_full_days": float(on_exposure / max(n_sess, 1)),
    "intraday_log_sum": float(id_log),
    "intraday_cagr_equiv": float(np.exp(id_log / (n_sess / 252.0)) - 1.0),
    "avg_intraday_weight": float(id_exposure / max(n_sess, 1)),
    "last30_log_sum": float(last30_log),
    "last30_cagr_equiv": float(np.exp(last30_log / (n_sess / 252.0)) - 1.0),
}

# average target weight at 15:59 by year (overnight bet frequency)
by_year = {}
for y in years:
    m = (ts_f.year == y) & (ts_f.hour == 15) & (ts_f.minute == 59)
    if m.sum():
        by_year[int(y)] = float(np.mean(w_full[m, 1]))
OUT["avg_1559_weight_by_year"] = by_year

# --------------------------------------------------------------------------- #
# 6. 2026-05-26 bad prints and half-days
# --------------------------------------------------------------------------- #
def ohlc_anomalies(symbol, day):
    df = bt.load_1m(symbol)
    m = df["date"] == pd.Timestamp(day).date()
    d = df.loc[m].copy()
    body_hi = d[["open", "close"]].max(axis=1)
    body_lo = d[["open", "close"]].min(axis=1)
    out = {
        "symbol": symbol, "day": day, "bars": int(len(d)),
        "first": str(d["ts"].iloc[0]) if len(d) else None,
        "last": str(d["ts"].iloc[-1]) if len(d) else None,
        "bad_high_gt_5pct_over_body": int((d["high"] > body_hi * 1.05).sum()),
        "bad_low_gt_5pct_under_body": int((d["low"] < body_lo * 0.95).sum()),
        "max_high_over_body": float((d["high"] / body_hi).max() - 1.0) if len(d) else None,
        "min_low_over_body": float((d["low"] / body_lo).min() - 1.0) if len(d) else None,
        "close_ret_min": float((d["close"].pct_change()).min()),
        "close_ret_max": float((d["close"].pct_change()).max()),
        "zero_or_neg": int((d[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
    }
    return out


OUT["bad_print_day"] = {
    sym: ohlc_anomalies(sym, "2026-05-26") for sym in ("QQQ", "TQQQ", "BIL")
}
d = pd.Timestamp("2026-05-26", tz=TZ).date()
m = np.array([x.date() == d for x in ts_f])
OUT["bad_print_day"]["strategy"] = {
    "bars_in_panel": int(m.sum()),
    "minutes_long": int((w_full[m, 1] > 0).sum()),
    "weight_sum": float(w_full[m, 1].sum()),
    "equity_day_return": float(r_full["equity"][m][-1] / r_full["equity"][m][0] - 1.0),
    "tqqq_day_return": float(c_f[m, 1][-1] / c_f[m, 1][0] - 1.0),
}
# 5-minute-bar anomaly view for TQQQ on that day (matching data_check.md)
t = bt.load_1m("TQQQ")
t = t[t["date"] == d].set_index("ts")
r5 = t.resample("5min", origin="start_day").agg(
    {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
body = r5[["open", "close"]].max(axis=1)
OUT["bad_print_day"]["tqqq_5m_worst"] = [
    {"ts": str(i), "open": float(r.open), "high": float(r.high), "low": float(r.low),
     "close": float(r.close), "high_over_body": float(r.high / body.loc[i] - 1.0),
     "low_under_body": float(r.low / body.loc[i] - 1.0)}
    for i, r in r5.sort_values("high", ascending=False).head(6).iterrows()
]

# half-day table: bar counts, last bar, current exposure that day
half = {}
for hd in sorted(bt.HALF_DAYS):
    if hd < ts_f[0].date() or hd > ts_f[-1].date():
        continue
    m = np.array([x.date() == hd for x in ts_f])
    if not m.any():
        continue
    idx = np.flatnonzero(m)
    half[str(hd)] = {
        "bars": int(m.sum()), "last_bar": str(ts_f[idx[-1]]),
        "avg_weight": float(w_full[idx, 1].mean()),
        "max_weight": float(w_full[idx, 1].max()),
    }
OUT["half_days"] = half
OUT["half_days_summary"] = {
    "n": len(half),
    "min_bars": min(v["bars"] for v in half.values()) if half else None,
    "max_bars": max(v["bars"] for v in half.values()) if half else None,
    "any_after_1300": any(v["last_bar"][11:16] > "13:00" for v in half.values()),
}

# --------------------------------------------------------------------------- #
# 7. save the causal full curve
# --------------------------------------------------------------------------- #
daily = daily_curve(r_full)
payload = {
    "slug": "dual-speed-regime",
    "variant": "current strategy.py defaults (OVERNIGHT=True, IDLE='cash')",
    "source": "research/revisit/dual-speed-regime/strategy.py",
    "band": BAND,
    "slippage_bps": 1.0,
    "marks": "1min",
    "causal": True,
    "dates": [str(x) for x in daily.index],
    "values": [float(v) for v in daily.to_numpy()],
    "metrics": {
        "dev_2016_2023": stat_block(r_full_dev),
        "full": stat_block(r_full),
        "10y": stat_block(slice_run(ts_f, o_f, c_f, w_full, "2017-01-03")),
        "5y": stat_block(slice_run(ts_f, o_f, c_f, w_full, "2021-10-25")),
    },
    "metrics_daily": {
        "dev_2016_2023": daily_stats(r_full_dev),
        "full": daily_stats(r_full),
    },
}
(HERE / "dual_speed_causal_curve.json").write_text(json.dumps(payload, indent=1))
OUT["causal_curve"] = {
    "path": str((HERE / "dual_speed_causal_curve.json").relative_to(ROOT)),
    "n_days": len(daily), "first_date": str(daily.index[0]),
    "last_date": str(daily.index[-1]), "last_value": float(daily.iloc[-1]),
}

(HERE / "dual_speed_audit.json").write_text(json.dumps(clean(OUT), indent=2))
log("wrote", HERE / "dual_speed_audit.json")
log("wrote", HERE / "dual_speed_causal_curve.json")
print(json.dumps(clean({
    "dev_current": OUT["dev_current"]["stats"],
    "dev_from_full": OUT["dev_from_full_panel"]["stats"],
    "full_current": OUT["full_current"]["stats"],
    "full_pretune": OUT["full_pretune"]["pretune_intraday_bil"]["stats"],
}), indent=2))
