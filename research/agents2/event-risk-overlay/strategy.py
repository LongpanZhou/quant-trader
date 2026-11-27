"""Event-risk overlay on the round-1 winner (daily 165-SMA regime + 4% stop).

Base strategy (round-1 winner, unchanged)
----------------------------------------
  risk_on   = QQQ close[d-1] > 165-day SMA of QQQ closes (through d-1)
  if not risk_on: hold BIL
  else: hold TQQQ, but if QQQ's 09:30 print < MA20 * 1.01 (armed) and TQQQ
        closes 4% below the session open, sell at the next minute's open and
        stay in BIL for the rest of the day and the night.

Overlay (this study)
--------------------
  On an ex-ante event session, keep the overnight TQQQ position but replace
  the *intraday* leg from 09:31 to 15:59 with the de-risk asset, then buy
  TQQQ back on the 15:59 print.  Events are pure calendar objects (see cal.py).

  Variants
    V1 opex_flat_bil    OpEx day -> BIL intraday            (primary)
    V2 opex_qqq         OpEx day -> QQQ intraday
    V3 opex_fomc_flat   OpEx + scheduled FOMC day -> BIL
    V4 all_events_qqq   FOMC+CPI+NFP+OpEx+pre-holiday -> QQQ  (control)

No look-ahead: every event date is a calendar object published in advance, and
the overlay decision for session d is taken at the 09:30 bar of d using only
prices at/before that bar.  Fills are at the next bar's open.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/event-risk-overlay/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
from cal import (CPI_DATES, FOMC_DATES, NFP_DATES, opex_dates,  # noqa: E402
                 pre_holiday_dates)

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
SMA_N, MA_FAST, STOP, ARM_BUF = 165, 20, 0.04, 0.01
BARS_PER_YEAR = 252 * 390

EVENTS = {
    "fomc": set(FOMC_DATES),
    "cpi": set(CPI_DATES),
    "nfp": set(NFP_DATES),
    "opex": set(opex_dates(2016, 2027)),
    "preh": set(pre_holiday_dates(2016, 2027)),
}
EVENTS["all"] = set().union(*[EVENTS[k] for k in ("fomc", "cpi", "nfp", "opex", "preh")])

VARIANTS = {
    "opex_flat_bil": {"events": ("opex",), "asset": "bil", "frac": 0.0},
    "opex_qqq": {"events": ("opex",), "asset": "qqq", "frac": 0.0},
    "opex_half_bil": {"events": ("opex",), "asset": "bil", "frac": 0.5},
    "opex_fomc_flat": {"events": ("opex", "fomc"), "asset": "bil", "frac": 0.0},
    "all_events_qqq": {"events": ("all",), "asset": "qqq", "frac": 0.0},
}


# ---------------------------------------------------------------------------
def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def build_base(ts, opens, closes):
    """Round-1 winner weights + per-session metadata."""
    dates = np.array([t.date() for t in ts])
    first, last = day_bounds(dates)
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]

    hold = np.zeros(n, bool)
    stops = []
    risk_on = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        on = bool(k > 0 and np.isfinite(sma_prev[k]) and dclose[k - 1] > sma_prev[k])
        risk_on[k] = on
        if not on:
            continue
        armed = bool(np.isfinite(ma20_prev[k]) and qqq_close[f] < ma20_prev[k] * (1.0 + ARM_BUF))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1.0 - STOP):
                state = False
                stops.append((str(dates[f]), str(ts[i].time())))
            hold[i] = state

    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    meta = dict(dates=dates, first=first, last=last, dclose=dclose, sma=sma,
                ma20=ma20, risk_on=risk_on, stops=stops)
    return w, meta


def apply_overlay(w_base, meta, events, asset="bil", frac=0.0):
    """Replace the intraday TQQQ leg on event sessions.

    weights[i] is filled at open(i+1), so setting weights[first]=0 sells on the
    09:31 open and weights[last-1]=1 buys back on the 15:59 open.  The position
    is therefore unchanged over the night, which is where TQQQ's drift lives.
    """
    w = w_base.copy()
    dates, first, last = meta["dates"], meta["first"], meta["last"]
    n_days = 0
    for k, d in enumerate(dates[first]):
        if d not in events:
            continue
        f, l = first[k], last[k]
        if l - f < 5:
            continue
        hold = w[f:l - 1, 1].copy()
        w[f:l - 1, 1] = hold * frac
        w[f:l - 1, 0] = hold * (1.0 - frac) if asset == "qqq" else 0.0
        w[f:l - 1, 2] = 1.0 - w[f:l - 1, 1] - w[f:l - 1, 0]
        n_days += 1
    return w, n_days


def window(ts, opens, closes, w, start, slip):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    eq = np.asarray(r["equity"], dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(eq[: j + 1]))
    deq = pd.Series(eq, index=ts[i:]).groupby(ts[i:].date).last()
    return {
        "start": start, "end": END,
        "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
        "max_drawdown_daily": float(-(deq / deq.cummax() - 1).min()),
        "sharpe": float(s["sharpe"]), "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]), "exposure": float(s["exposure"]),
        "fills": int(s["fills"]), "turnover": float(s["turnover"]),
        "ending_equity": float(s["ending_equity"]),
        "dd_peak": str(ts[i:][p].date()), "dd_trough": str(ts[i:][j].date()),
        "equity": eq, "ts": ts[i:],
        "yearly": {str(k): v for k, v in bt.yearly(ts[i:], eq, closes[i:, 1]).items()},
        "peak_idx": p,
    }


def yearly_of(res):
    return {k: v["strategy"] for k, v in res["yearly"].items()}


def rolling3(res, years=3):
    deq = pd.Series(res["equity"], index=res["ts"]).groupby(res["ts"].date).last()
    end = deq.index[-1]
    start = deq.index[0]
    out = []
    while True:
        stop = (pd.Timestamp(start) + pd.DateOffset(years=years)).date()
        if stop > end:
            break
        w = deq[(deq.index >= start) & (deq.index < stop)]
        if len(w) > 200:
            yrs = (pd.Timestamp(w.index[-1]) - pd.Timestamp(w.index[0])).days / 365.25
            out.append({"start": str(start),
                        "cagr": float((w.iloc[-1] / w.iloc[0]) ** (1 / yrs) - 1.0),
                        "max_drawdown": float(-(w / w.cummax() - 1).min())})
        start = (pd.Timestamp(start) + pd.DateOffset(months=3)).date()
    return out


def event_study(ts, opens, closes, meta):
    """Descriptive: mean overnight / intraday returns by event family."""
    dates, first, last = meta["dates"], meta["first"], meta["last"]
    n = len(first)
    rows = []
    for k in range(1, n):
        f, l = first[k], last[k]
        rows.append({
            "date": dates[first[k]], "risk_on": bool(meta["risk_on"][k]),
            "t_c2c": closes[l, 1] / closes[last[k - 1], 1] - 1.0,
            "t_c2o": opens[f, 1] / closes[last[k - 1], 1] - 1.0,
            "t_o2c": closes[l, 1] / opens[f, 1] - 1.0,
            "q_o2c": closes[l, 0] / opens[f, 0] - 1.0,
        })
    d = pd.DataFrame(rows)
    d = d[d["date"] >= pd.Timestamp(START10).date()].reset_index(drop=True)
    out = {}
    ro = d[d["risk_on"]]
    for name in ("fomc", "cpi", "nfp", "opex", "preh"):
        m = ro["date"].isin(EVENTS[name]).to_numpy()
        g = np.log1p(ro.loc[m, "q_o2c"].to_numpy()) - np.log1p(ro.loc[m, "t_o2c"].to_numpy())
        out[name] = {
            "n_risk_on": int(m.sum()),
            "tqqq_c2c_bp": float(ro.loc[m, "t_c2c"].mean() * 1e4),
            "tqqq_c2o_bp": float(ro.loc[m, "t_c2o"].mean() * 1e4),
            "tqqq_o2c_bp": float(ro.loc[m, "t_o2c"].mean() * 1e4),
            "qqq_o2c_bp": float(ro.loc[m, "q_o2c"].mean() * 1e4),
            "swap_gain_bp": float(g.mean() * 1e4),
            "swap_gain_t": float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))),
            "swap_hit_rate": float((g > 0).mean()),
            "non_event_o2c_bp": float(ro.loc[~m, "t_o2c"].mean() * 1e4),
        }
    out["_n_sessions"] = int(len(d))
    out["_n_risk_on"] = int(ro.shape[0])
    out["_years"] = float((d["date"].iloc[-1] - d["date"].iloc[0]).days / 365.25)
    return out


# ---------------------------------------------------------------------------
def main():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    w0, meta = build_base(ts, opens, closes)
    print(f"bars {len(ts)}  sessions {len(meta['first'])}  stops {len(meta['stops'])}")

    out = {
        "agent": "event-risk-overlay",
        "strategy": {
            "base": "QQQ 165-day SMA regime, 100% TQQQ risk-on / BIL risk-off, "
                    "4% intraday stop armed when QQQ 09:30 < MA20*1.01",
            "overlay": "on ex-ante event sessions keep the overnight TQQQ leg and "
                       "hold the de-risk asset from the 09:31 open to the 15:59 open",
            "calendar_source": "Fed FOMC calendars; BLS CPI/Employment-Situation release "
                               "schedules (archived bls.gov pages); OpEx = 3rd Friday "
                               "(holiday-shifted); pre-holiday = last session before a "
                               "NYSE full-day holiday",
            "event_days_risk_on_10y": {k: int(sum(1 for d, on in zip(meta["dates"][meta["first"]], meta["risk_on"])
                                                  if on and d in EVENTS[k]))
                                       for k in ("fomc", "cpi", "nfp", "opex", "preh", "all")},
            "fills": "next bar open", "band": 0.02,
        },
        "event_study": event_study(ts, opens, closes, meta),
        "variants": {},
        "baseline": {},
    }

    weights = {"baseline": w0}
    for name, cfg in VARIANTS.items():
        ev = set().union(*[EVENTS[k] for k in cfg["events"]])
        w, nd = apply_overlay(w0, meta, ev, asset=cfg["asset"], frac=cfg["frac"])
        weights[name] = w
        out["variants"][name] = {"config": {"events": list(cfg["events"]), "asset": cfg["asset"],
                                            "frac": cfg["frac"]}, "sessions_overlaid": nd}

    for name, w in weights.items():
        store = out["baseline"] if name == "baseline" else out["variants"][name]
        store["costs"] = {}
        for slip in (1.0, 5.0, 10.0):
            tag = f"{slip:.0f}bp"
            r10 = window(ts, opens, closes, w, START10, slip)
            r5 = window(ts, opens, closes, w, START5, slip)
            store["costs"][tag] = {
                "10y": {k: r10[k] for k in ("start", "end", "cagr", "max_drawdown",
                                            "max_drawdown_daily", "sharpe", "sortino",
                                            "volatility", "exposure", "fills", "turnover",
                                            "ending_equity", "dd_peak", "dd_trough")},
                "5y": {k: r5[k] for k in ("start", "end", "cagr", "max_drawdown",
                                          "max_drawdown_daily", "sharpe", "sortino",
                                          "volatility", "exposure", "fills", "turnover",
                                          "ending_equity", "dd_peak", "dd_trough")},
            }
            if slip == 1.0:
                store["yearly"] = yearly_of(r10)
                store["yearly_bench_tqqq"] = {k: v["benchmark"] for k, v in r10["yearly"].items()}
                store["yearly_5y"] = yearly_of(r5)
                store["rolling3y"] = rolling3(r10)
                store["_r10"] = r10
                store["_r5"] = r5
        print(f"  {name:16s} 1bp 10y {store['costs']['1bp']['10y']['cagr']*100:6.2f}/"
              f"{store['costs']['1bp']['10y']['max_drawdown']*100:5.2f}  5y "
              f"{store['costs']['1bp']['5y']['cagr']*100:6.2f}/"
              f"{store['costs']['1bp']['5y']['max_drawdown']*100:5.2f}")

    # pass / fail vs the winner
    b = out["baseline"]["costs"]
    tq = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
          "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}

    # Drawdown attribution: the winner's max-DD episode is measured from a
    # specific intraday peak.  Compare each variant's drawdown from *that same
    # peak moment*, so the comparison is not distorted by the variant simply
    # owning a higher equity peak on a different day.
    for wl in ("10y", "5y"):
        bp = out["baseline"]["_r10" if wl == "10y" else "_r5"]["peak_idx"]
        for name in out["variants"]:
            eq = out["variants"][name]["_r10" if wl == "10y" else "_r5"]["equity"]
            out["variants"][name][f"dd_from_winner_peak_{wl}"] = float(1.0 - eq[bp:].min() / eq[bp])
        out["baseline"][f"dd_from_winner_peak_{wl}"] = float(
            1.0 - out["baseline"]["_r10" if wl == "10y" else "_r5"]["equity"][bp:].min()
            / out["baseline"]["_r10" if wl == "10y" else "_r5"]["equity"][bp])
    for name in out["variants"]:
        v = out["variants"][name]["costs"]
        out["variants"][name]["pass"] = {}
        for wl in ("10y", "5y"):
            for cost in ("1bp", "5bp", "10bp"):
                s = v[cost][wl]
                bw = b[cost][wl]
                out["variants"][name]["pass"][f"{wl}_{cost}"] = {
                    "beats_winner_cagr": bool(s["cagr"] > bw["cagr"]),
                    "lower_dd_than_winner": bool(s["max_drawdown"] < bw["max_drawdown"]),
                    "cagr_diff_pp": float((s["cagr"] - bw["cagr"]) * 100),
                    "dd_diff_pp": float((s["max_drawdown"] - bw["max_drawdown"]) * 100),
                    "strict_dominance": bool(s["cagr"] > bw["cagr"] and s["max_drawdown"] < bw["max_drawdown"]),
                    "beats_tqqq": bool(s["cagr"] > tq[wl]["cagr"] and s["max_drawdown"] < tq[wl]["max_drawdown"]),
                }

    # rolling-3y consistency vs baseline
    base_r3 = out["baseline"]["rolling3y"]
    for name in out["variants"]:
        r3 = out["variants"][name]["rolling3y"]
        wins = sum(1 for a, c in zip(base_r3, r3) if c["cagr"] > a["cagr"] and c["max_drawdown"] < a["max_drawdown"])
        out["variants"][name]["rolling3y_wins_both"] = int(wins)
        out["variants"][name]["rolling3y_n"] = len(r3)
    out["baseline"]["rolling3y_wins_both"] = 0
    out["baseline"]["rolling3y_n"] = len(base_r3)

    for store in [out["baseline"]] + list(out["variants"].values()):
        store.pop("_r10", None)
        store.pop("_r5", None)

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
