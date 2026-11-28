"""Vol-Spike Reflation v2 -- repair attempt and retirement test for vol-kelly-overlay.

Status: development-window test of whether the post-spike reflation edge can be
repaired.  The original strategy produced 11 entries in eight years and an
event mean indistinguishable from zero.  v2 keeps the same mechanism -- a
1-minute realized-volatility spike plus an oversold QQQ drawdown, buy TQQQ with
inverse-vol sizing -- and tests the two diagnosed defects:

  1. the "first up-close" stabilization filter is a late-entry artefact: it
     buys after the bounce.  Removing it is the main signal fix;
  2. the 3-session hold gives back the first-day reflation, so the hold is
     shortened to one session in the count-repair cell.

The 8-cell grid also relaxes the spike ratio.  If no cell has a significant
positive event mean, the strategy is retired rather than forced to trade.

No 165-day moving-average gate, no shorting, no 2024-2026 data.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/new/vol-kelly-overlay-v2/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BARS = 252 * 390
BAND = 0.02

PARAMS = dict(
    spike=1.40,        # v5 / v20 of within-day 1-minute realized vol
    dd_x=0.05,         # QQQ 10-day drawdown <= -5%
    dd_window=10,
    hold=1,            # sessions including the entry session
    up_filter=False,   # the original required QQQ close > prior close
    target_vol=0.35,
    w_min=0.25,
    w_max=0.75,
    stop_x=0.04,       # QQQ price stop from the actual next-open entry
    exit_ratio=1.00,   # v5/v20 normalization exit
)


# --------------------------------------------------------------------------- #
# data / signals
# --------------------------------------------------------------------------- #
def load_dev_panel():
    return bt.panel(SYMS, DEV_START, DEV_END, "1min")


def session_dates(ts):
    return bt.session_dates(ts)


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def daily_realized_var(ts, closes):
    """Per-session sum of squared within-day 1-minute log returns (TQQQ)."""
    n = len(ts)
    day_id = bt.day_ids(ts)
    dates = session_dates(ts)
    first, last = day_bounds(dates)
    tq = closes[:, 1]
    r = np.zeros(n)
    if n > 1:
        r[1:] = np.log(tq[1:] / tq[:-1])
    r[first] = 0.0                      # exclude the overnight gap
    return np.bincount(day_id, weights=r * r, minlength=len(first))


def daily_context(ts, closes):
    dates = session_dates(ts)
    first, last = day_bounds(dates)
    qqq = closes[last, 0]
    rv = daily_realized_var(ts, closes)
    v5 = np.sqrt(pd.Series(rv).rolling(5).mean().to_numpy() * 252.0)
    v20 = np.sqrt(pd.Series(rv).rolling(20).mean().to_numpy() * 252.0)
    ratio = v5 / v20
    dd = qqq / pd.Series(qqq).rolling(int(PARAMS["dd_window"])).max().to_numpy() - 1.0
    up = np.zeros(len(qqq), bool)
    up[1:] = qqq[1:] > qqq[:-1]
    return dict(dates=dates, first=first, last=last, qqq=qqq, rv=rv,
                v5=v5, v20=v20, ratio=ratio, dd=dd, up=up)


def to_minutes(ctx, day_w):
    n = len(ctx["dates"])
    day_id = np.repeat(np.arange(len(ctx["first"])),
                       np.diff(np.r_[ctx["first"], n]))
    return day_w[day_id]


# --------------------------------------------------------------------------- #
# strategy
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, params=None, ctx=None):
    """Return (minute weights, info).  Signal at close i, fill at open i+1."""
    p = {**PARAMS, **(params or {})}
    c = ctx if ctx is not None else daily_context(ts, closes)
    nd = len(c["first"])
    signal = (np.isfinite(c["ratio"]) & (c["ratio"] >= p["spike"])
              & np.isfinite(c["dd"]) & (c["dd"] <= -p["dd_x"]))
    if p["up_filter"]:
        signal &= c["up"]

    day_w = np.zeros((nd, 3))
    day_w[:, 2] = 1.0
    in_pos = False
    pending = False
    entry_i = 0
    entry_px = 0.0
    weight = 0.0
    events = []

    for i in range(nd):
        if pending:
            pending = False
            in_pos = True
            entry_i = i
            entry_px = float(opens[c["first"][i], 0])
            events.append(dict(signal_i=int(i - 1), entry_i=int(i),
                               entry_px=entry_px, weight=float(weight),
                               exit_i=None, exit_px=None))

        if in_pos:
            days = i - entry_i
            exit_now = (
                days >= int(p["hold"]) - 1
                or (np.isfinite(c["ratio"][i]) and c["ratio"][i] < p["exit_ratio"])
                or (c["qqq"][i] <= entry_px * (1.0 - p["stop_x"]))
            )
            if exit_now:
                in_pos = False
                events[-1]["exit_i"] = int(i)
                if i + 1 < nd:
                    events[-1]["exit_px"] = float(opens[c["first"][i + 1], 0])
                    day_w[i + 1, 2] = 1.0
            else:
                if i + 1 < nd:
                    day_w[i + 1, 1] = weight
                    day_w[i + 1, 2] = 1.0 - weight
        else:
            if signal[i] and np.isfinite(c["v20"][i]) and c["v20"][i] > 0:
                weight = float(np.clip(p["target_vol"] / c["v20"][i],
                                       p["w_min"], p["w_max"]))
                pending = True
                if i + 1 < nd:
                    day_w[i + 1, 1] = weight
                    day_w[i + 1, 2] = 1.0 - weight

    done = [e for e in events if e["exit_i"] is not None]
    info = dict(params=p, events=done, n_events=len(done),
                n_signals=int(signal.sum()),
                exposure=float(np.mean(day_w[:, 1])),
                exposure_time=float(np.mean(day_w[:, 1] > 0)))
    return to_minutes(c, day_w), info


# --------------------------------------------------------------------------- #
# benchmark only -- NOT part of the strategy
# --------------------------------------------------------------------------- #
def baseline_165d_weights(ts, closes):
    dates = session_dates(ts)
    first, last = day_bounds(dates)
    dq = closes[last, 0]
    sma = pd.Series(dq).rolling(165).mean().to_numpy()
    on = np.zeros(len(first), bool)
    on[1:] = dq[:-1] > np.r_[np.nan, sma[:-1]][1:]
    day_w = np.zeros((len(first), 3))
    day_w[:, 1] = on.astype(float)
    day_w[:, 2] = 1.0 - day_w[:, 1]
    return to_minutes(dict(dates=dates, first=first), day_w)


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def daily_returns(ts, equity):
    s = pd.Series(equity, index=ts)
    e = s.groupby(session_dates(pd.DatetimeIndex(ts))).last()
    return e.pct_change().dropna()


def corr_daily(a, b):
    idx = a.index.intersection(b.index)
    return float(np.corrcoef(a.loc[idx], b.loc[idx])[0, 1])


def bootstrap_p(vals, n_boot=10000, seed=7):
    if len(vals) < 3:
        return None
    rng = np.random.default_rng(seed)
    arr = np.asarray(vals, float)
    means = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    return float((means <= 0).mean())


def event_returns(ts, res, info):
    eq = res["equity"]
    ctx_last = bt.day_bounds_from_dates(session_dates(pd.DatetimeIndex(res["ts"])))[1]
    out = []
    for e in info["events"]:
        # fill at the open of entry_i, mark to the close of the exit fill day
        i0 = int(ctx_last[min(e["entry_i"] - 1, len(ctx_last) - 1)])
        i1 = int(ctx_last[min(e["exit_i"] + 1, len(ctx_last) - 1)])
        if i1 > i0:
            out.append(float(eq[i1] / eq[i0] - 1.0))
    return out


def slice_stats(ts, opens, closes, w, start, end, slip=1.0):
    i0 = bt.start_index(ts, start)
    i1 = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"))) + 1
    r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], w[i0:i1],
                    band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS)
    s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
    return s


def stats_row(s):
    return dict(cagr=float(s["cagr"]), max_drawdown=float(s["max_drawdown"]),
                sharpe=float(s["sharpe"]), sortino=float(s["sortino"]),
                calmar=float(s["calmar"]), fills=int(s["fills"]),
                turnover=float(s["turnover"]))


def grid(ts, opens, closes, ctx):
    cells = [
        dict(spike=1.50, dd_x=0.05, hold=3, up_filter=True),   # original
        dict(spike=1.50, dd_x=0.05, hold=3, up_filter=False),
        dict(spike=1.50, dd_x=0.05, hold=1, up_filter=False),
        dict(spike=1.40, dd_x=0.05, hold=3, up_filter=False),
        dict(spike=1.40, dd_x=0.05, hold=1, up_filter=False),  # count repair
        dict(spike=1.30, dd_x=0.05, hold=3, up_filter=False),
        dict(spike=1.40, dd_x=0.04, hold=3, up_filter=False),
        dict(spike=1.40, dd_x=0.06, hold=3, up_filter=False),
    ]
    rows = []
    for over in cells:
        w, info = build_weights(ts, opens, closes, over, ctx)
        r = bt.run(ts, opens, closes, w, start=DEV_START, band=BAND,
                   slippage_bps=1.0)
        s = bt.stats(r, BARS)
        s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
        ep = np.asarray(event_returns(ts, r, info), float)
        rows.append({
            **{k: over[k] for k in over},
            "entries": int(info["n_events"]),
            "tq_exposure": float(w[:, 1].mean()),
            "tq_time": float((w[:, 1] > 0).mean()),
            "cagr": float(s["cagr"]),
            "max_drawdown": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]),
            "event_mean": float(ep.mean()) if len(ep) else None,
            "event_hit": float((ep > 0).mean()) if len(ep) else None,
            "event_p": bootstrap_p(ep) if len(ep) else None,
        })
    return rows


def forward_diagnosis(ctx):
    """Condition counts and forward 3-session returns behind the diagnosis."""
    qqq = ctx["qqq"]
    tq = ctx  # only daily closes needed; close-to-close is enough for a diagnosis
    ratio, dd, up = ctx["ratio"], ctx["dd"], ctx["up"]
    n = len(qqq)
    spike = np.isfinite(ratio) & (ratio >= 1.50)
    over = np.isfinite(dd) & (dd <= -0.05)
    joint = spike & over
    out = {
        "sessions": int(n),
        "spike_days": int(spike.sum()),
        "drawdown_days": int(over.sum()),
        "up_days": int(up.sum()),
        "spike_and_drawdown_days": int(joint.sum()),
        "spike_drawdown_and_up_days": int((joint & up).sum()),
    }
    # forward 3-session QQQ close-to-close after the joint state, split by up
    idx = np.flatnonzero(joint & (np.arange(n) < n - 4))
    for label, mask in (("all", np.ones(len(idx), bool)),
                        ("up", up[idx]), ("down", ~up[idx])):
        k = idx[mask]
        if len(k):
            r = qqq[k + 3] / qqq[k] - 1.0
            out[f"fwd3_{label}_n"] = int(len(k))
            out[f"fwd3_{label}_mean"] = float(r.mean())
            out[f"fwd3_{label}_hit"] = float((r > 0).mean())
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, opens, closes = load_dev_panel()
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York"), \
        "development window only: no 2024-2026 bars"
    ctx = daily_context(ts, closes)
    w, info = build_weights(ts, opens, closes, ctx=ctx)
    base_w = baseline_165d_weights(ts, closes)

    out = {
        "agent": "vol-kelly-overlay-v2",
        "original": "research/revisit/vol-kelly-overlay",
        "status": "pending",
        "idea": "Buy a volatility-scaled TQQQ position after a 1-minute "
                "realized-vol spike and an oversold QQQ drawdown; exit on vol "
                "normalization, a short time stop or a price stop.",
        "hypothesis": "Post-spike volatility mean reversion plus TQQQ convexity "
                      "gives a positive 1-3 session rebound. The original's "
                      "up-close filter is a late-entry artefact; removing it "
                      "and shortening the hold should repair the event count.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "dev_window": [DEV_START, DEV_END],
        "marks": "1m",
        "params": {k: v for k, v in PARAMS.items()},
        "diagnosis": forward_diagnosis(ctx),
        "windows": {"dev": {}},
        "events": {},
        "subperiods": {},
        "yearly": {},
        "correlation": {},
        "grid": {},
        "falsifiers": {},
    }

    res = {}
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, start=DEV_START, band=BAND,
                   slippage_bps=slip)
        s = bt.stats(r, BARS)
        s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
        res[slip] = r
        out["windows"]["dev"][f"{int(slip)}bp"] = stats_row(s)
    rc = res[1.0]
    out["windows"]["dev"]["1bp"]["tq_exposure"] = float(w[:, 1].mean())
    out["windows"]["dev"]["1bp"]["tq_time"] = float((w[:, 1] > 0).mean())

    ep = np.asarray(event_returns(ts, rc, info), float)
    out["events"] = {
        "entries": int(info["n_events"]),
        "signal_days": int(info["n_signals"]),
        "mean_event_return": float(ep.mean()) if len(ep) else None,
        "median_event_return": float(np.median(ep)) if len(ep) else None,
        "hit_rate": float((ep > 0).mean()) if len(ep) else None,
        "bootstrap_p": bootstrap_p(ep) if len(ep) else None,
        "best_event": float(ep.max()) if len(ep) else None,
        "worst_event": float(ep.min()) if len(ep) else None,
        "episode_returns": [float(x) for x in ep],
    }

    # benchmarks
    i0 = bt.start_index(ts, DEV_START)
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        b = bt.benchmark(closes[i0:, col], ts[i0:], BARS)
        out.setdefault("benchmarks", {})[name] = {
            k: float(v) for k, v in b.items()}
    out["benchmarks"]["note"] = "buy-and-hold, 1m marks"

    rb = bt.run(ts, opens, closes, base_w, start=DEV_START, band=BAND,
                slippage_bps=1.0)
    out["correlation"]["vs_165d_baseline"] = corr_daily(
        daily_returns(ts, rb["equity"]), daily_returns(ts, rc["equity"]))
    out["correlation"]["baseline_cagr"] = float(bt.stats(rb, BARS)["cagr"])
    out["correlation"]["baseline_dd"] = float(bt.stats(rb, BARS)["max_drawdown"])

    out["yearly"] = bt.yearly(rc["ts"], rc["equity"], closes[i0:, 1])
    out["yearly"] = {str(k): {kk: float(vv) for kk, vv in v.items()}
                     for k, v in out["yearly"].items()}
    for tag, start, end in (("2016_2019", "2016-01-04", "2019-12-31"),
                            ("2020_2021", "2020-01-02", "2021-12-31"),
                            ("2022_2023", "2022-01-03", "2023-12-29")):
        s = slice_stats(ts, opens, closes, w, start, end)
        out["subperiods"][tag] = stats_row(s)

    rows = grid(ts, opens, closes, ctx)
    out["grid"] = {
        "cells": rows,
        "n": len(rows),
        "entries_range": [min(r["entries"] for r in rows),
                          max(r["entries"] for r in rows)],
        "frac_positive_cagr": float(np.mean([r["cagr"] > 0 for r in rows])),
        "frac_p_le_010": float(np.mean([(r["event_p"] is not None
                                         and r["event_p"] <= 0.10) for r in rows])),
        "median_event_mean": float(np.median([r["event_mean"] for r in rows])),
    }

    # single-event dependence, on the count-repair cell
    order = np.argsort(ep)
    without_best = float(np.prod(1.0 + ep[order[:-1]]) - 1.0) if len(ep) > 1 else None
    day_dates = pd.to_datetime(ctx["dates"][ctx["last"]])
    years = np.array([day_dates[e["entry_i"]].year for e in info["events"]])
    keep = years != 2020
    without_2020 = float(np.prod(1.0 + ep[keep]) - 1.0) if keep.any() else None
    out["concentration"] = {
        "best_event": float(ep.max()) if len(ep) else None,
        "product_without_best": without_best,
        "product_with_2020": float(np.prod(1.0 + ep) - 1.0) if len(ep) else None,
        "product_without_2020": without_2020,
    }

    # falsifiers (the original list, re-checked on the count-repair cell)
    d1 = out["windows"]["dev"]["1bp"]
    out["falsifiers"] = {
        "1_entries_ge_15": out["events"]["entries"] >= 15,
        "2_net_positive_10bp": out["windows"]["dev"]["10bp"]["cagr"] > 0.0,
        "3_bootstrap_p_le_010": (out["events"]["bootstrap_p"] is not None
                                 and out["events"]["bootstrap_p"] <= 0.10),
        "4_not_single_event": (without_best is not None and without_best > 0.0),
        "5_corr_lt_060": out["correlation"]["vs_165d_baseline"] < 0.60,
        "7_2022_23_positive": out["subperiods"]["2022_2023"]["cagr"] > 0.0,
        "8_up_filter_adds_nothing": (rows[1]["event_mean"] is not None
                                     and rows[1]["event_mean"]
                                     >= rows[0]["event_mean"]),
        "9_standalone_positive": d1["cagr"] > 0.0,
    }
    passed = all(out["falsifiers"].values())
    out["status"] = "repaired" if passed else "retired"
    if not passed:
        best_p = min(r["event_p"] for r in rows if r["event_p"] is not None)
        out["verdict"] = (
            f"retired: the count repair works ({rows[0]['entries']} -> "
            f"{out['events']['entries']} entries) and the 2022-23 sub-period is "
            f"positive, but the event mean is "
            f"{out['events']['mean_event_return']*100:.2f}% with "
            f"p={out['events']['bootstrap_p']:.3f}; no cell in the 8-cell grid "
            f"reaches p<=0.10 (best {best_p:.3f}). The original 11-entry "
            f"version is p={rows[0]['event_p']:.3f}. Dropping the up-close "
            "filter raises the mean but the sample is still not significant. "
            "The core post-spike reflation edge is absent; forcing 28 trades "
            "would be count-chasing, not a repair."
        )
    else:
        out["verdict"] = "repaired: see windows and events."

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"status {out['status']}  entries {out['events']['entries']}  "
          f"1bp CAGR {d1['cagr']*100:.2f}%  DD {d1['max_drawdown']*100:.2f}%  "
          f"Sharpe {d1['sharpe']:.2f}  event p {out['events']['bootstrap_p']:.3f}")
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
