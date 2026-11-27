"""Exploration: baseline reproduction + event-day statistics.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/event-risk-overlay/explore.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt  # noqa: E402
import cal  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N, MA_FAST, STOP, ARM_BUF = 165, 20, 0.04, 0.01
BARS_PER_YEAR = 252 * 390
CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"


def load_panel():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
    return ts, z["opens"], z["highs"], z["lows"], z["closes"], z["vols"]


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def baseline(ts, opens, closes, sma_n=SMA_N, ma_fast=MA_FAST, stop=STOP, arm_buf=ARM_BUF):
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))

    hold = np.zeros(n, bool)
    stops = []
    risk_on_days = np.zeros(len(first), bool)
    armed_days = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        on = bool(k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k])
        risk_on_days[k] = on
        if not on:
            continue
        arm = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1.0 + arm_buf))
        armed_days[k] = arm
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if arm and state and tqqq_close[i] < base * (1.0 - stop):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    meta = dict(dates=dates, first=first, last=last, dclose=dclose, sma=sma, ma20=ma20,
                risk_on=risk_on_days, armed=armed_days, day_id=day_id, stops=stops,
                hold=hold)
    return w, meta


def event_study(meta, opens, closes):
    first, last = meta["first"], meta["last"]
    dates = meta["dates"][first]
    d = pd.DataFrame({"date": dates})
    d["qqq_c"] = closes[last, 0]
    d["tqqq_c"] = closes[last, 1]
    d["qqq_o"] = opens[first, 0]
    d["tqqq_o"] = opens[first, 1]
    d["risk_on"] = meta["risk_on"]
    d["ma20"] = meta["ma20"]
    for c in ("qqq", "tqqq"):
        d[f"{c}_c2c"] = d[f"{c}_c"].pct_change()
        d[f"{c}_o2c"] = d[f"{c}_c"] / d[f"{c}_o"] - 1.0
        d[f"{c}_c2o"] = d[f"{c}_o"] / d[f"{c}_c"].shift(1) - 1.0
    d["weak"] = d["qqq_c"] < d["ma20"]

    fomc = set(cal.FOMC_DATES)
    cpi = set(cal.CPI_DATES)
    nfp = set(cal.NFP_DATES)
    opex = set(cal.opex_dates(2016, 2026))
    preh = set(cal.pre_holiday_dates(2016, 2026))
    d["fomc"] = d["date"].isin(fomc)
    d["cpi"] = d["date"].isin(cpi)
    d["nfp"] = d["date"].isin(nfp)
    d["opex"] = d["date"].isin(opex)
    d["preh"] = d["date"].isin(preh)
    d["any"] = d[["fomc", "cpi", "nfp", "opex", "preh"]].any(axis=1)
    return d


def summarize(d, mask_base, label):
    sub = d[mask_base]
    rows = []
    for col in ("fomc", "cpi", "nfp", "opex", "preh", "any"):
        a = sub.loc[sub[col], "tqqq_c2c"].dropna()
        b = sub.loc[~sub[col], "tqqq_c2c"].dropna()
        rows.append(dict(
            event=col, n=len(a),
            mean_bp=a.mean() * 1e4, med_bp=a.median() * 1e4,
            sd_bp=a.std() * 1e4, pct_neg=(a < 0).mean(),
            base_mean_bp=b.mean() * 1e4,
            t=(a.mean() - b.mean()) / (a.std() / np.sqrt(len(a))),
            qqq_mean_bp=sub.loc[sub[col], "qqq_c2c"].mean() * 1e4,
        ))
    out = pd.DataFrame(rows)
    print(f"\n=== {label}  (n sessions {len(sub)}) ===")
    print(out.to_string(index=False, float_format=lambda x: f"{x:7.2f}"))


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    print("bars", len(ts), "first", ts[0], "last", ts[-1])
    w, meta = baseline(ts, opens, closes)
    print("stop events", len(meta["stops"]), "risk-on sessions", int(meta["risk_on"].sum()))

    for start in (START10, START5):
        r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS_PER_YEAR)
        print(f"baseline {start}: CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  "
              f"Sharpe {s['sharpe']:.2f} fills {s['fills']}")

    d = event_study(meta, opens, closes)
    d = d[d["date"] >= pd.Timestamp(START10).date()].copy()
    print("\ncounts:", {c: int(d[c].sum()) for c in ("fomc", "cpi", "nfp", "opex", "preh", "any")})
    summarize(d, d["risk_on"], "risk-on sessions only")
    summarize(d, d["risk_on"] & d["weak"], "risk-on & QQQ<MA20 (weak)")
    summarize(d, d["risk_on"] & ~d["weak"], "risk-on & QQQ>=MA20 (strong)")

    # overlap structure
    print("\nevent-day overlap (risk-on days):")
    dd = d[d["risk_on"]]
    print("  any-event share of risk-on sessions: %.1f%%" % (100 * dd["any"].mean()))
    print("  weekday distribution of FOMC:", dd.loc[dd["fomc"], "date"].map(lambda x: x.strftime("%a")).value_counts().to_dict())
    print("\nopex sample:", sorted(opex_s) if (opex_s := [str(x) for x in cal.opex_dates(2017, 2017)]) else None)
    print("pre-holiday 2024:", [str(x) for x in cal.pre_holiday_dates(2024, 2024)])
    print("nyse holidays 2024:", sorted(str(x) for x in cal.nyse_holidays(2024)))


if __name__ == "__main__":
    main()
