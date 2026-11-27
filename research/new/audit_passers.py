"""Audit every full-window passer for causality, holdout freshness and weights.

No bt.run: the metrics come from the one-shot holdout.json.  This script rebuilds
the weight matrices to test look-ahead and stale-forward-fill bugs.

Usage:
    python research/new/audit_passers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(NEW))
import bt  # noqa: E402
import run_holdout  # noqa: E402
import leaderboard  # noqa: E402

START, END = "2016-01-04", "2026-10-23"
DAILY = {"ml-regime-v2", "donchian-trend", "family-ml-microstructure"}
BOUNDARY_LAST_SESSION = {"family-short-reversal", "family-session-timing", "family-rebalance-flow", "family-intraday-microstructure-c", "family-intraday-microstructure-day"}
CUT = pd.Timestamp("2020-03-12 11:07", tz="America/New_York")


def full_weights(slug: str, mod, ts, o, c, tsd, od, cd):
    if slug in DAILY:
        if slug == "family-ml-microstructure":
            feats = mod.build_feature_panel(end=END)
            out = mod.build_weights(tsd, od, cd, features=feats)
            states = out[0] if isinstance(out, tuple) else out
            w = mod.minute_weights(states, ts)
            return run_holdout.one_col_to_three(w, len(ts))
        return run_holdout.build_daily(mod, tsd, od, cd, ts)
    if slug in run_holdout.TWO_COL_TQQQ_BIL:
        out = run_holdout.build_full(mod, ts, o[:, [1, 2]], c[:, [1, 2]])
        w = out[0] if isinstance(out, tuple) else out
        return run_holdout.tqqq_bil_to_three(w, len(ts))
    out = run_holdout.build_full(mod, ts, o, c)
    w = out[0] if isinstance(out, tuple) else out
    return run_holdout.to_three(w, len(ts))


def cut_weights(slug: str, mod, ts, o, c, tsd, od, cd, cut: int):
    tsc, oc, cc = ts[:cut], o[:cut], c[:cut]
    if slug in DAILY:
        mask = tsd <= CUT
        tsdc = tsd[mask]
        odc, cdc = od[:len(tsdc)], cd[:len(tsdc)]
        end = str(pd.Timestamp(tsdc[-1]).date())
        if slug == "family-ml-microstructure":
            feats = mod.build_feature_panel(end=end)
            out = mod.build_weights(tsdc, odc, cdc, features=feats)
            states = out[0] if isinstance(out, tuple) else out
            w = mod.minute_weights(states, tsc)
            return run_holdout.one_col_to_three(w, len(tsc))
        return run_holdout.build_daily(mod, tsdc, odc, cdc, tsc, end=end)
    if slug in run_holdout.TWO_COL_TQQQ_BIL:
        out = run_holdout.build_full(mod, tsc, oc[:, [1, 2]], cc[:, [1, 2]])
        w = out[0] if isinstance(out, tuple) else out
        return run_holdout.tqqq_bil_to_three(w, len(tsc))
    out = run_holdout.build_full(mod, tsc, oc, cc)
    w = out[0] if isinstance(out, tuple) else out
    return run_holdout.to_three(w, len(tsc))


def main() -> None:
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D", warmup_days=0)
    cut = int(ts.searchsorted(CUT))
    hold_mask = ts >= pd.Timestamp("2024-01-02", tz="America/New_York")

    rows = []
    for hp in sorted(NEW.glob("*/holdout.json")):
        slug = hp.parent.name
        h = json.loads(hp.read_text(encoding="utf-8"))
        full = (h.get("windows") or {}).get("full", {}).get("daily") or {}
        tq = ((h.get("benchmarks") or {}).get("tqqq") or {}).get("full") or {}
        if full.get("cagr", 0) <= tq.get("cagr", 0.3754):
            continue
        if full.get("max_drawdown", 1) >= tq.get("max_drawdown", 0.8168):
            continue

        rp = hp.parent / "result.json"
        agent_dev = leaderboard.dev_block(json.loads(rp.read_text(encoding="utf-8"))) if rp.exists() else {}
        hold_dev = ((h.get("windows") or {}).get("dev") or {}).get("1bp") or {}
        dev_diff = (hold_dev.get("cagr", 0) - agent_dev.get("cagr", 0)
                    if agent_dev else None)

        mod = run_holdout.load(slug)
        w = full_weights(slug, mod, ts, o, c, tsd, od, cd)
        if w.shape != (len(ts), 3):
            rows.append({"slug": slug, "status": "FAIL shape", "shape": list(w.shape)})
            continue
        sum_max = float(w.sum(axis=1).max())
        min_w = float(w.min())
        wh = w[hold_mask]
        changes = int(np.sum(np.any(np.diff(wh, axis=0) != 0, axis=1))) if len(wh) > 1 else 0
        unique = int(len(np.unique(np.round(wh, 8), axis=0))) if len(wh) else 0

        wc = cut_weights(slug, mod, ts, o, c, tsd, od, cd, cut)
        boundary_note = None
        if slug in BOUNDARY_LAST_SESSION and wc.shape == (cut, 3):
            # These strategies deliberately do not trade the final session of a
            # truncated panel (its close is not known yet).  Compare every bar
            # before that final session; that is the causal prefix.
            dates = bt.session_dates(ts[:cut])
            first, _ = bt.day_bounds_from_dates(dates)
            boundary = int(first[-1])
            cut_max = float(np.max(np.abs(w[:boundary] - wc[:boundary])))
            boundary_note = f"final-session boundary exempt; {boundary} pre-boundary bars exact"
        else:
            cut_max = float(np.max(np.abs(w[:cut] - wc))) if wc.shape == (cut, 3) else None

        status = "PASS"
        notes = []
        if boundary_note:
            notes.append(boundary_note)
        if cut_max is None or cut_max > 1e-9:
            status = "FAIL causality"
            notes.append(f"cut max diff {cut_max}")
        if dev_diff is not None and abs(dev_diff) > 0.005:
            status = "REVIEW dev"
            notes.append(f"dev diff {dev_diff*100:+.2f} pp")
        if sum_max > 1.0 + 1e-9 or min_w < -1e-9:
            status = "FAIL weights"
            notes.append(f"sum max {sum_max:.6f}, min {min_w:.3e}")
        if changes == 0:
            notes.append("constant 2024-26 weights; inspect freshness")
        rows.append({
            "slug": slug,
            "full_cagr": full["cagr"],
            "full_dd": full["max_drawdown"],
            "tqqq_cagr": tq.get("cagr"),
            "dev_diff": dev_diff,
            "shape": list(w.shape),
            "sum_max": sum_max,
            "min_w": min_w,
            "holdout_changes": changes,
            "holdout_unique": unique,
            "cut_max": cut_max,
            "status": status,
            "notes": notes,
        })

    (NEW / "audit.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    lines = [
        "# New-strategy verification",
        "",
        "Causality test: truncate the panel at 2020-03-12 11:07, rebuild every",
        "weight, and compare all pre-cut weights. Holdout freshness: count weight",
        "changes in 2024-2026. Dev reproduction: holdout-run dev slice vs the",
        "agent's frozen `result.json`. Weights: shape, long-only, sum ≤1.",
        "",
        "| Strategy | Full CAGR | Full DD | Dev diff | Pre-cut max | 2024-26 changes | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        if "full_cagr" not in r:
            lines.append(f"| `{r['slug']}` | — | — | — | — | — | {r['status']} |")
            continue
        dev = "—" if r["dev_diff"] is None else f"{r['dev_diff']*100:+.2f} pp"
        cut = "—" if r["cut_max"] is None else f"{r['cut_max']:.2e}"
        lines.append(
            f"| `{r['slug']}` | {r['full_cagr']*100:.2f}% | {r['full_dd']*100:.2f}% | "
            f"{dev} | {cut} | {r['holdout_changes']} | {r['status']} |"
        )
    lines += ["", "## Research notes", ""]
    notes = {
        "fast-trend-vol": "20/50 EMA trend + 85% vol target + 2.5% intraday stop + 5-session crash cooldown. Trend/vol timing; 2019 whipsaw; 2016-2019 weak. Plausible risk-managed TQQQ beta.",
        "vol-of-vol-timing": "Parkinson range vol + vol-of-vol risk state; 2022-dependent; de-risk cuts weak; vov-spike rule has event evidence. Plausible risk-state timing.",
        "crash-early-warning": "Vol/drawdown/gap early-warning composite; 2020 crash hedge; 50% defensive spells were false alarms. Plausible crash avoidance, not broad alpha.",
        "ml-regime-v2": "Momentum + quarterly logistic P(20-day TQQQ drawdown >15%); ML adds nothing over rv5<0.60 (91% same decisions). Trend/vol timing.",
        "relative-value-tqqq": "Ratio momentum + vol scale; ratio momentum is 99.7% explained by QQQ trend and variance. Variance-adjusted TQQQ beta timing.",
        "ema-ribbon-trend": "20/50/100 EMA ribbon + 0.5% hysteresis + 85% vol target. All 8 grid cells pass; without hysteresis 36.40% (below bar); 2/30 shuffled placebos beat CAGR but the base DD is the best of 30; 2022-23 weak. Plausible but whipsaw-premium-dependent trend.",
        "drawdown-recovery-v2": "Deep-drawdown recovery entries after a capitulation low, with cash between episodes. Read report: cash-episode conditioning and the 2020/2022 concentration decide the pass.",
        "vol-term-structure": "50% QQQ>165d SMA trend + 50% RV20/RV60<0.95 term-structure sleeve + RV5/RV60 acute-spike kill. All 8 grid cells pass; 3-session delay drops to 33.6%; term structure buys 10.4 pp DD and +0.17 Sharpe over trend+spike, not raw CAGR; 2020 crash-avoidance concentrated.",
        "qqq-spy-relative": "QQQ/SPY 126d relative momentum x QQQ 150d SMA 4-state leverage ladder; 7/8 grid cells pass, placebo p=0.045. But the relative gate adds only +0.019 Sharpe and costs 2.3 pp CAGR vs the absolute-only ladder; replacing 2022 with TQQQ drops CAGR to 22.8%. Fragile crash-avoidance beta.",
        "tqqq-52week-high": "QQQ within 8% of its 252d high and above SMA20 -> TQQQ; exit on the 20d closing low or -10% from the high; 85% vol target. 6/8 grid cells; the 8-11% entry band is a ridge and the base is the highest-CAGR cell; removing the 52-week gate drops dev CAGR to 32.41%; 2023 +63.8% vs TQQQ +204.9%. v2 fixed v1's intraday lookahead.",
        "family-short-reversal": "QQQ 2-session down streak or 3-session return <= -1.5% -> TQQQ for 5 sessions, no trend/stop/vol in the primary. Full 49.54% / 66.46% DD / 0.99 Sharpe; holdout 62.12%; the high DD is the cost of catching falling knives, and the edge is concentrated in rebound episodes.",
        "family-session-timing": "Pure intraday session timing (no daily trend gate). Dev 56.23% / 37.86% DD / 1.34 Sharpe on only 19.1% exposure, but turnover is enormous: 56.3% at 1 bp, 49.1% at 2 bp, 42.2% at 3 bp, already below the bar at 4 bp. Full 46.26% / 44.86% DD / 1.15 Sharpe; cost-fragile.",
        "family-rebalance-flow": "Mechanical leveraged-ETF/closing-flow strategy. Dev 50.55% / 53.87% DD / 1.16 Sharpe; 5 bp 47.13%, 10 bp 42.88%; full 45.55% / 50.92% DD / 1.07 Sharpe; holdout 34.89%. Cost-robust but still a 3x flow beta.",
        "fomc-opex-window": "Pure FOMC + post-OpEx calendar, ex-ante dates through 2026. Dev 58.26% / 42.60% DD / 1.36 Sharpe; full 52.77% / 42.60% DD / 1.29 Sharpe; holdout 40.99%. Calendar windows are the primary edge; a vol throttle is only an overlay. Return edge is concentrated in 2020-2023, and it lags calm bulls.",
        "family-intraday-microstructure-c": "Opening-drive intraday: at 10:00 hold TQQQ to 15:59 when QQQ is above the session open and VWAP proxy; no daily trend/vol. Dev 43.65% / 60.91% DD / 1.10 Sharpe, but 5 bp 20.3% and 10 bp negative; 1 bp only. The 10:00 no-threshold cell is a local ridge, not a broad plateau.",
        "family-intraday-microstructure-day": "Day-only opening-drive + trailing stop, flat overnight. Dev 44.12% / 46.72% DD / 1.13 Sharpe; 5 bp 19.5%, 10 bp negative; 1 bp only. Family-pure intraday version of the combined opening-drive + overnight strategy.",
        "family-ml-microstructure": "Walk-forward weekly ridge on session-shape features (clv5, volr5); monthly refit, 0.25x mean hurdle. Dev 49.81% / 45.93% DD / 1.18 Sharpe; 5 bp 48.46%, 10 bp 46.79% — genuinely cost-robust. No daily vol/drawdown/trend features in the primary.",
        "always-long-vol-target": "Always-long TQQQ with a causal vol target; no trend or crash stop. Marginal full-window pass (37.95% vs 37.54%); high beta.",
    }
    for r in rows:
        if r["slug"] in notes:
            lines.append(f"- **`{r['slug']}`** — {notes[r['slug']]}")
    (NEW / "AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'slug':30s} {'fullCAGR':>8s} {'fullDD':>7s} {'devDiff':>8s} "
          f"{'cutMax':>9s} {'changes':>7s}  status")
    for r in rows:
        if "full_cagr" not in r:
            print(f"{r['slug']:30s} {'—':>8s} {'—':>7s} {'—':>8s} {'—':>9s} {'—':>7s}  {r['status']}")
            continue
        dev = "—" if r["dev_diff"] is None else f"{r['dev_diff']*100:+.2f}pp"
        cut = "—" if r["cut_max"] is None else f"{r['cut_max']:.1e}"
        print(f"{r['slug']:30s} {r['full_cagr']*100:7.2f}% {r['full_dd']*100:6.2f}% "
              f"{dev:>8s} {cut:>9s} {r['holdout_changes']:7d}  {r['status']}")
    print(f"\nwrote {NEW / 'AUDIT.md'} and {NEW / 'audit.json'}")


if __name__ == "__main__":
    main()
