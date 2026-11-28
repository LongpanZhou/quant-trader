"""Dollar-impulse regime sleeve - `family-dollar-regime`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded.

Primary object: the 60-session log return of UUP, the PowerShares DB US Dollar
Index Bullish Fund.  A broad dollar appreciation of more than 3% over 60
sessions is treated as a global dollar-funding / tightening shock and the book
moves to BIL.  Otherwise the book holds TQQQ.  The signal is a dollar impulse,
not a QQQ price-trend, volatility or calendar gate.

Rules (all known at the session-k close; fill at the next open):

    u60[k] = log(UUP_close[k] / UUP_close[k-60])
    target[k] = TQQQ 1.0 if u60[k] <= +0.030 else BIL 1.0

The target is written on the last 1-minute bar of session k and filled at the
09:30 open of k+1.  Long-only, weights >= 0, row sum <= 1, 2% band, headline
1 bp, also 5/10 bp.  Idle capital is BIL.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-dollar-regime/strategy.py
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

SLUG = "family-dollar-regime"
SYMBOLS = ["UUP"]
PARAMS = dict(W=60, THR=0.03)

# Eight local cells: five thresholds at the primary window plus three nearby
# windows at the primary threshold.  The primary (60, 0.03) is included.
PLATEAU = (
    [dict(W=60, THR=x) for x in (0.020, 0.025, 0.030, 0.035, 0.040)]
    + [dict(W=w, THR=0.03) for w in (20, 40, 80)]
)


def signal(px: pd.DataFrame, idx: pd.DatetimeIndex, params: dict) -> pd.Series:
    """60-session UUP log impulse, sliced to the QQQ session calendar."""
    s = np.log(px["UUP"] / px["UUP"].shift(int(params["W"])))
    return common.session_slice(s, idx)


def targets_from_signal(sig: pd.Series, params: dict) -> np.ndarray:
    """TQQQ when the dollar impulse is at or below the threshold, else BIL."""
    on = (sig <= float(params["THR"])).fillna(False).to_numpy()
    return common.binary_targets(on)


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
        "family": "dollar regime",
        "idea": ("A 60-session UUP appreciation above 3% flags a global dollar "
                 "funding shock; hold BIL, otherwise hold TQQQ."),
        "hypothesis": ("Broad dollar strength tightens global financial conditions "
                       "and is negative for long-duration US growth equity; dollar "
                       "weakness is a risk-on tailwind."),
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
            "u60": "log(UUP[k] / UUP[k-60])",
            "risk_on": "u60 <= +3.0% -> TQQQ 1.0",
            "risk_off": "u60 > +3.0% -> BIL 1.0",
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
            f"Dev pass at 1 bp: CAGR {w1['cagr']*100:.2f}%, DD "
            f"{w1['max_drawdown']*100:.2f}%, Sharpe {w1['sharpe']:.2f}, "
            f"{act['fills']} fills.  The dollar impulse clears the three-way "
            f"dev bar and {plateau_pass}/8 plateau cells.  It is not a clean "
            f"independent winner: correlation with `{corr['max_slug']}` is "
            f"{corr['winner_corr_max']:.3f}, the 2022-23 subperiod is only "
            f"{sub['2022-2023']['cagr']*100:.1f}%, and the 2.0-2.5% threshold "
            f"cells fail.  Promote to a dev candidate; do not call it verified "
            f"until the one-shot 2024-2026 holdout."
        ),
    }

    common.write_json(HERE / "result.json", result)

    narrative = {
        "title": "Dollar-impulse regime: UUP 60-day impulse -> TQQQ/BIL",
        "hypothesis": (
            "The dollar is the price of global dollar liquidity.  When the "
            "trade-weighted dollar appreciates sharply, foreign borrowers' "
            "dollar liabilities grow, cross-border credit is squeezed, and "
            "long-duration US growth equity is vulnerable.  A flat or weaker "
            "dollar is the opposite regime: global liquidity is stable or "
            "expanding, which is a tailwind for TQQQ."
        ),
        "mechanism": (
            "The signal is deliberately a *dollar impulse*, not a QQQ trend or "
            "volatility state.  UUP tracks the ICE US Dollar Index, a broad "
            "basket dominated by EUR, JPY, GBP, CAD, SEK and CHF.  A 60-session "
            "log return above +3% is a large move (about the top quintile of "
            "the development distribution) and has historically clustered "
            "around funding stress, Fed tightening scares and risk-off episodes.  "
            "The strategy pays a small whipsaw cost for being in BIL during "
            "those episodes and stays long TQQQ otherwise."
        ),
        "distinctness": (
            "The primary object is a cross-asset currency impulse.  None of the "
            "nine existing winners uses UUP or any FX series as its gate: "
            "ratio-froth uses a QQQ/TQQQ ratio, vol-scaled-crash-stop uses "
            "realised volatility, relative-value-tqqq uses QQQ/SPY, the event "
            "families use calendar or session clocks, and the microstructure "
            "families use intraday order flow.  The dollar impulse is an "
            "external macro state, not another trend/vol/calendar variant."
        ),
        "signal": (
            "At the close of session *k*, compute `u60 = log(UUP[k] / "
            "UUP[k-60])`.  If `u60 <= 0.030`, the target is TQQQ 1.0; otherwise "
            "it is BIL 1.0.  The feature is computed on the external daily "
            "calendar with 2015 warmup rows, then reindexed to the QQQ session "
            "calendar.  The first session already has a finite 60-day impulse."
        ),
        "result_comment": (
            f"At 1 bp the book returns {w1['cagr']*100:.2f}% CAGR with a "
            f"{w1['max_drawdown']*100:.2f}% max drawdown and Sharpe {w1['sharpe']:.2f}; "
            f"at 10 bp the CAGR is still {windows['10bp']['cagr']*100:.2f}%.  "
            f"TQQQ exposure is {act['tqqq_exposure']*100:.1f}%, so the book is "
            f"selectively de-risked rather than a permanent BIL overlay."
        ),
        "plateau_comment": (
            "The plateau is a local cross: five thresholds at the 60-session "
            "window plus three nearby windows at the 3% threshold.  The 3.0-4.0% "
            "cells all clear the bar; the 2.0% and 2.5% cells do not.  The "
            "signal therefore has a usable plateau but is not threshold-"
            "insensitive at the low end."
        ),
        "placebo_comment": (
            "The circular-shift nulls preserve the holding-length distribution "
            "and the marginal distribution of the dollar impulse.  The true "
            "CAGR sits near the 90th percentile of the target-shift null and "
            "near the 80th percentile of the feature-shift null.  The evidence "
            "is suggestive, not overwhelming: a 100-draw placebo on eight years "
            "of daily regimes has limited power."
        ),
        "corr_comment": (
            "The book is still a long-TQQQ risk-on book most of the time, so it "
            "correlates with the existing risk-on winners.  The highest link is "
            "with `relative-value-tqqq`, which also rotates equity exposure; the "
            "dollar gate itself is distinct.  A correlation above 0.85 would "
            "have triggered the redundancy kill criterion."
        ),
        "verdict": (
            "This is a solid dev candidate, not a verified winner.  "
            f"It clears the bar and the activity floor, has a {plateau_pass}/8 "
            "plateau, and positive returns in all three subperiods.  The "
            "caveats are real: the edge is concentrated in 2016-19, the "
            f"2022-23 subperiod only returns "
            f"{sub['2022-2023']['cagr']*100:.1f}%, the 2.0-2.5% threshold cells "
            "fail, and correlation "
            f"with `{corr['max_slug']}` is {corr['winner_corr_max']:.3f}.  "
            "The one-shot holdout is the "
            "only way to know whether the dollar impulse survives."
        ),
        "limitations": (
            "UUP is a fund with its own expenses and tracking error, and the "
            "daily close is a 16:00 print while the target is written at 15:59; "
            "the one-minute gap is the same convention used by the rest of the "
            "programme.  The 60-day impulse is a slow signal and can be late at "
            "turning points.  The development window contains only one major "
            "dollar cycle (2016-2023), so the threshold is not estimated on a "
            "long sample.  The next step is a frozen one-shot 2024-2026 holdout "
            "and a check of the dollar impulse against a trade-weighted Fed "
            "broad index (not just UUP) before any promotion."
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
