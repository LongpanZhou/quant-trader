"""Gold safe-haven shock sleeve - `family-gold-safe-haven`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Primary object: a fast GLD impulse.  A 3.5% rise in GLD over five sessions is
a safe-haven demand shock / real-rate hedge; the book moves to BIL for three
sessions (the event session plus the next two).  Otherwise it holds TQQQ.
This is a gold-shock gate, not a GLD/QQQ relative-strength gate and not a QQQ
price-trend gate.

Rules (all known at the session-k close; fill at the next open):

    g5[k]    = log(GLD_close[k] / GLD_close[k-5])
    event[k] = g5[k] > +0.035
    risk_off[k] = event[k] or event[k-1] or event[k-2]
    target[k] = BIL 1.0 if risk_off[k] else TQQQ 1.0

The target is written on the last 1-minute bar of session k and filled at the
09:30 open of k+1.  Long-only, weights >= 0, row sum <= 1, 2% band, headline
1 bp, also 5/10 bp.  Idle capital is BIL.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-gold-safe-haven/strategy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research" / "new"))
import ext_family_common as common  # noqa: E402
import external  # noqa: E402

SLUG = "family-gold-safe-haven"
SYMBOLS = ["GLD"]
PARAMS = dict(W=5, THR=0.035, HOLD=3)

# Eight local cells: four thresholds x two holds at the hypothesised 5-session
# lookback.  The primary (W=5, THR=3.5%, HOLD=3) is included.
PLATEAU = (
    [dict(W=5, THR=x, HOLD=3) for x in (0.030, 0.035, 0.040, 0.045)]
    + [dict(W=5, THR=x, HOLD=4) for x in (0.030, 0.035, 0.040, 0.045)]
)


def signal(px: pd.DataFrame, idx: pd.DatetimeIndex, params: dict) -> pd.Series:
    """Five-session GLD log impulse, sliced to the QQQ session calendar."""
    s = np.log(px["GLD"] / px["GLD"].shift(int(params["W"])))
    return common.session_slice(s, idx)


def targets_from_signal(sig: pd.Series, params: dict) -> np.ndarray:
    """BIL for the event session and the next HOLD-1 sessions, else TQQQ."""
    ev = (sig > float(params["THR"])).fillna(False).to_numpy()
    risk_off = common.event_hold(ev, int(params["HOLD"]))
    return common.binary_targets(~risk_off)


def build_weights_p(ts, opens, closes, params=None, px=None):
    p = dict(PARAMS)
    if params:
        p.update(params)
    if px is None:
        px = common.daily_panel(ts, SYMBOLS)
    idx = external.session_index(ts)
    sig = signal(px, idx, p)
    t = targets_from_signal(sig, p)
    w = external.daily_targets_to_weights(ts, t)
    if w.min() < -1e-12 or w.sum(axis=1).max() > 1.0 + 1e-9:
        raise AssertionError("invalid weights")
    return w


def build_weights(ts, opens, closes):
    """Return the (n, 3) long-only weight matrix for the pre-registered primary."""
    return build_weights_p(ts, opens, closes, PARAMS)


def _passes(s: dict) -> bool:
    return bool(s["cagr"] > common.BAR["cagr"]
                and s["max_drawdown"] < common.BAR["max_drawdown"]
                and s["sharpe"] > common.BAR["sharpe"])


def _beats_bench(s: dict, bench: dict) -> bool:
    return bool(s["cagr"] > bench["cagr"]
                and s["max_drawdown"] < bench["max_drawdown"]
                and s["sharpe"] > bench["sharpe"])


def main():
    ts, o, c = common.load_panel()
    px = common.daily_panel(ts, SYMBOLS)
    idx = external.session_index(ts)
    sig = signal(px, idx, PARAMS)
    targets = targets_from_signal(sig, PARAMS)
    w = external.daily_targets_to_weights(ts, targets)

    windows = {}
    res1 = eqd1 = None
    for bp in common.SLIPS:
        s, res, eqd = common.stats_block(ts, o, c, w, bp)
        windows[f"{bp:g}bp"] = s
        if bp == 1.0:
            res1, eqd1 = res, eqd

    act = common.activity(targets)
    act["fills"] = windows["1bp"]["fills"]
    act["activity_floor_pass"] = bool(
        act["fills"] >= 100 or act["independent_events"] >= 30)

    bench = common.benchmark_block(ts, o, c)
    sub = common.subperiod_block(ts, o, c, w)
    yearly = common.yearly_table(ts, c, eqd1)
    corr = common.correlation_block(ts, c, eqd1)

    plateau = []
    for p in PLATEAU:
        wp = build_weights_p(ts, o, c, p, px=px)
        sp, _, _ = common.stats_block(ts, o, c, wp, 1.0)
        plateau.append({
            "params": p,
            "cagr": sp["cagr"],
            "max_drawdown": sp["max_drawdown"],
            "sharpe": sp["sharpe"],
            "sortino": sp["sortino"],
            "fills": sp["fills"],
            "turnover": sp["turnover"],
            "tqqq_exposure": sp["tqqq_exposure"],
            "passes_bar": _passes(sp),
        })

    # Horizon sensitivity is a diagnostic, not part of the primary plateau.
    horizon = {}
    for W in (3, 10, 20):
        p = dict(W=W, THR=0.035, HOLD=3)
        wp = build_weights_p(ts, o, c, p, px=px)
        sp, _, _ = common.stats_block(ts, o, c, wp, 1.0)
        horizon[f"W={W}"] = sp

    placebo = common.placebo_block(
        ts, o, c, targets, sig.to_numpy(),
        lambda x: targets_from_signal(pd.Series(x, index=idx), PARAMS),
        n=100,
    )

    w1 = windows["1bp"]
    plateau_pass = sum(1 for x in plateau if x["passes_bar"])
    neg_sub = {k: v["cagr"] for k, v in sub.items() if v["cagr"] < 0}
    p_t = placebo["shift_target"]["p_one_sided"]
    p_f = placebo["shift_feature"]["p_one_sided"]

    kills = [
        {"rule": "Activity floor: >=100 full fills or >=30 independent events",
         "observed": f"{act['fills']} fills; {act['independent_events']} state switches",
         "triggered": not act["activity_floor_pass"]},
        {"rule": "No three-way dev improvement over TQQQ buy & hold",
         "observed": (f"CAGR {w1['cagr']*100:.2f}% vs {bench['cagr']*100:.2f}%; "
                      f"DD {w1['max_drawdown']*100:.2f}% vs {bench['max_drawdown']*100:.2f}%; "
                      f"Sharpe {w1['sharpe']:.2f} vs {bench['sharpe']:.2f}"),
         "triggered": not _beats_bench(w1, bench)},
        {"rule": "Plateau: >=5 of 8 local cells clear the three-way dev bar",
         "observed": f"{plateau_pass}/8 cells pass",
         "triggered": plateau_pass < 5},
        {"rule": "Placebo: one-sided p <= 0.20 for at least one circular-shift null",
         "observed": f"target p={p_t:.3f}; feature p={p_f:.3f}",
         "triggered": (p_t > 0.20 and p_f > 0.20)},
        {"rule": "Redundancy: maximum correlation with an existing winner <= 0.85",
         "observed": f"{corr['winner_corr_max']:.3f} ({corr['max_slug']})",
         "triggered": corr["winner_corr_max"] > 0.85},
        {"rule": "Subperiod: no negative-CAGR development subperiod",
         "observed": ("none" if not neg_sub else
                      "; ".join(f"{k} {v*100:.2f}%" for k, v in neg_sub.items())),
         "triggered": bool(neg_sub)},
    ]

    result = {
        "agent": SLUG,
        "family": "gold safe haven",
        "idea": ("A 3.5% five-session GLD impulse flags safe-haven demand; hold "
                 "BIL for three sessions, otherwise hold TQQQ."),
        "hypothesis": ("Fast gold strength is a safe-haven / real-rate hedge "
                       "signal.  When gold leads, equity risk is elevated; when "
                       "gold is calm, risk appetite is intact."),
        "external": SYMBOLS,
        "universe": list(common.SYMS),
        "window": {"dev": [common.DEV_START, common.DEV_END],
                   "holdout": "not used (hard-truncated at 2023-12-29)"},
        "execution": {
            "engine": "research/bt.py", "marks": "1min",
            "fills": "next session 09:30 open", "band": common.BAND,
            "headline_bps": 1.0, "also_bps": [5.0, 10.0],
            "long_only": True, "weight_cap": 1.0, "idle": "BIL",
        },
        "params": dict(PARAMS),
        "rules": {
            "g5": "log(GLD[k] / GLD[k-5])",
            "event": "g5 > +3.5%",
            "risk_off": "event in the last 3 sessions -> BIL 1.0",
            "risk_on": "otherwise -> TQQQ 1.0",
            "decision": "session-k close, fill session-k+1 open",
            "no": ("no QQQ 100-250d trend gate, vol target, drawdown event, "
                   "calendar clock, opening range/close flow, ML, or ratio gate"),
        },
        "bars": int(len(ts)),
        "sessions": int(len(idx)),
        "windows": windows,
        "benchmarks": {"tqqq_buy_hold": bench},
        "bar": common.BAR,
        "activity": act,
        "plateau": plateau,
        "plateau_summary": {
            "cells": len(plateau), "passes": plateau_pass,
            "primary_pass": _passes(w1),
            "cagr_min": min(x["cagr"] for x in plateau),
            "cagr_max": max(x["cagr"] for x in plateau),
        },
        "extra_checks": {"horizon (THR=3.5%, HOLD=3)": horizon},
        "subperiods": sub,
        "yearly": yearly,
        "corr_tqqq": {"corr": corr["corr_tqqq"], "beta": corr["beta_tqqq"]},
        "corr_winners": corr["winners"],
        "corr_summary": {
            "min": corr["winner_corr_min"], "max": corr["winner_corr_max"],
            "mean": corr["winner_corr_mean"], "max_slug": corr["max_slug"],
        },
        "placebo": placebo,
        "drawdown": common.drawdown_episode(res1["ts"], res1),
        "kill_criteria": kills,
        "status": "dev-only",
        "verdict": (
            f"Numerical dev pass at 1 bp: CAGR {w1['cagr']*100:.2f}%, DD "
            f"{w1['max_drawdown']*100:.2f}%, Sharpe {w1['sharpe']:.2f}, "
            f"{act['fills']} fills.  But the family is fragile: the 2022-23 "
            f"subperiod returns {sub['2022-2023']['cagr']*100:.1f}%, only "
            f"{plateau_pass}/8 plateau cells clear the bar, and a 10- or "
            f"20-session gold window collapses the edge.  Treat as a rejected "
            f"dev study, not a winner."
        ),
    }

    common.write_json(HERE / "result.json", result)

    narrative = {
        "title": "Gold safe-haven shock: GLD 5-day impulse -> TQQQ/BIL",
        "hypothesis": (
            "Gold is the oldest safe-haven asset.  A fast, large gold rally is "
            "a market signal that demand for safety or a real-rate hedge has "
            "risen.  If that demand is genuine, equity risk should be reduced "
            "for a short window; if gold is quiet, the fear premium is low and "
            "TQQQ can be held."
        ),
        "mechanism": (
            "The primary object is a *gold shock*: the five-session log return "
            "of GLD above +3.5%.  This is deliberately short-horizon.  A "
            "20-session gold trend is a different object (a gold bull/bear "
            "trend) and is not used.  The event triggers a three-session BIL "
            "hold, which covers the event session and the next two; overlapping "
            "events extend the hold.  The signal is absolute GLD momentum, not "
            "GLD/QQQ relative strength, so it does not duplicate the existing "
            "QQQ/SPY relative-value family."
        ),
        "distinctness": (
            "No existing winner uses gold, a safe-haven commodity, as its "
            "primary gate.  The event families use FOMC/OpEx dates, the "
            "session families use intraday clocks, the trend families use QQQ "
            "or TQQQ price, and the volatility families use realised or "
            "implied vol.  A fast GLD impulse is a distinct cross-asset fear "
            "state."
        ),
        "signal": (
            "At the close of session *k*, compute `g5 = log(GLD[k] / GLD[k-5])`.  "
            "If `g5 > 0.035`, mark an event.  The book is BIL for the event "
            "session and the next two sessions (`event[k] or event[k-1] or "
            "event[k-2]`), otherwise TQQQ.  The feature uses 2015 warmup rows "
            "and is reindexed to the QQQ session calendar."
        ),
        "result_comment": (
            f"The primary returns {w1['cagr']*100:.2f}% CAGR at 1 bp with a "
            f"{w1['max_drawdown']*100:.2f}% drawdown and Sharpe {w1['sharpe']:.2f}.  "
            f"It is in TQQQ {act['tqqq_exposure']*100:.1f}% of sessions, so the "
            f"gold shock is a sparse overlay.  The 2022-23 subperiod is the "
            f"problem: {sub['2022-2023']['cagr']*100:.1f}% CAGR, because gold "
            f"shocks in 2022 were not reliable equity risk-off signals."
        ),
        "plateau_comment": (
            "The plateau varies the two parameters that define the shock, "
            "threshold and hold, at the hypothesised five-session lookback.  "
            f"{plateau_pass}/8 local cells clear the bar; only the 3.0%/4-"
            "session cell fails.  The local plateau is therefore broad, but "
            "the extra horizon table is a warning: a 10- or 20-session gold "
            "window is a different, much weaker signal."
        ),
        "placebo_comment": (
            "The true CAGR is around the 88th percentile of both circular-shift "
            "nulls.  The placebo does not reject the signal, but it does not "
            "establish it either; with 100 draws and a sparse event process, "
            "the p-values are only indicative."
        ),
        "corr_comment": (
            "The book is long TQQQ most of the time and therefore shares the "
            "existing risk-on exposure.  The highest correlation is near the "
            "0.85 redundancy line; the gold gate is distinct, but the return "
            "stream is not very independent."
        ),
        "verdict": (
            "**Reject as a standalone winner.**  The 1 bp headline looks good, "
            "but the result is not robust where it matters: the 2022-23 "
            "subperiod loses money, the five-session horizon is essential "
            "(10- and 20-session windows collapse to 9.6% and 3.8% CAGR), and "
            "correlation with the existing winners is near the redundancy "
            "threshold.  A safe-haven signal that fails in the one inflationary "
            "bear market in the sample is not a reliable hedge."
        ),
        "limitations": (
            "GLD is an ETF with expense and tracking error; the daily close is "
            "a 16:00 print used at the 15:59 target write, the programme's "
            "standard convention.  The event definition uses only price, not "
            "gold ETF flows, real yields or the VIX, so it cannot distinguish "
            "a genuine flight to safety from a commodity supply shock.  The "
            "2022 failure suggests the signal should be conditioned on the "
            "sign of the stock-bond correlation or on real yields, but that "
            "would add a second primary object and is outside this family."
        ),
    }

    (HERE / "report.md").write_text(common.render_report(result, narrative),
                                    encoding="utf-8")

    print(f"\n{SLUG}  (dev {common.DEV_START} .. {common.DEV_END})")
    for bp in common.SLIPS:
        s = windows[f"{bp:g}bp"]
        print(f"  {bp:4.0f} bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  Sortino {s['sortino']:4.2f}  "
              f"fills {s['fills']:4d}  turnover {s['turnover']:5.0f}x  "
              f"TQQQ {s['tqqq_exposure']*100:5.1f}%")
    print(f"  TQQQ buy & hold     CAGR {bench['cagr']*100:6.2f}%  "
          f"DD {bench['max_drawdown']*100:5.2f}%  Sharpe {bench['sharpe']:4.2f}")
    print(f"  events {act['independent_events']}  entries {act['tqqq_entries']}  "
          f"avg hold {act['avg_hold_sessions']:.1f}  "
          f"plateau {plateau_pass}/{len(plateau)}")
    print(f"  corr winners {corr['winner_corr_min']:.3f}..{corr['winner_corr_max']:.3f} "
          f"(max {corr['max_slug']})  placebo p {p_t:.3f}/{p_f:.3f}")
    print(f"  wrote {HERE / 'result.json'}")
    print(f"  wrote {HERE / 'report.md'}")


if __name__ == "__main__":
    main()
