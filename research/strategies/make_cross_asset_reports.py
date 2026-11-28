"""Generate report.md for the four reserve cross-asset families from result.json.

Run from the repo root after the strategies:
    python research/strategies/make_cross_asset_reports.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import cross_asset as ca  # noqa: E402
import bt  # noqa: E402

SLUGS = [
    "family-rates-volatility",
    "family-international-relative",
    "family-small-cap-relative",
    "family-copper-gold",
]

TITLES = {
    "family-rates-volatility": "MOVE rates-volatility regime",
    "family-international-relative": "EEM/QQQ international relative leadership",
    "family-small-cap-relative": "IWM/QQQ small-cap relative leadership",
    "family-copper-gold": "CPER/GLD copper-gold relative momentum",
}

NARRATIVE = {
    "family-rates-volatility": """
The MOVE level is the strongest of the four reserve signals. The primary holds
TQQQ only when rates volatility is below its own one-year median and sits in
BIL otherwise. Over 2016-2023 it compounds at **{cagr}** with a **{dd}**
maximum drawdown, versus TQQQ's {tq_cagr} / {tq_dd}. It survives 10 bp
({cagr10}), the circular-shift placebo is beaten by none of the 60 draws, and
the static 48/52 TQQQ/BIL blend at the strategy's own average weights only
makes {static_cagr}. The timing is doing the work.

The weakness is the plateau's 126-session window: those four cells are weaker
than the 252-session cells, and three of the four fail. The 20-session change
is a genuinely worse object: it loses roughly 10 pp of
CAGR after next-open execution and fails at every cost. So the family is a
**level** strategy, not a rates-momentum strategy. The five passing cells are
enough for the house 5/8 plateau rule, but the result is not uniformly robust.

2016 and 2022 are the negative years ({y2016} and {y2022}). The 2016 rate
scare produced repeated MOVE spikes while the equity market recovered, so the
binary BIL rung whipsawed; 2022 was a sustained rates-vol bear market that the
signal caught late. The three subperiods are all positive, and the worst
drawdown is 38.3% rather than TQQQ's 82.3%, so the family is a credible
low-drawdown reserve rather than a return-maximising one.
""",
    "family-international-relative": """
The 60-session EEM/QQQ spread is the strongest headline of the four:
**{cagr}** CAGR with **{dd}** drawdown at 1 bp, and it still clears the bar at
10 bp ({cagr10}). All eight plateau cells pass, the placebo is beaten by none
of the 60 draws, and the static 49/51 QQQ/TQQQ blend only makes {static_cagr}.
The signal is not a repackaged average allocation.

The lookback is load-bearing. The 20-session ablation collapses to 24.5% with
83.9% drawdown: short-horizon EEM/QQQ moves are noise for this purpose. The
family is therefore a **slow macro** overlay, not a fast relative-strength
trade. The 8/8 plateau is a plateau in the normalisation window, threshold and
mapping, not in the lookback.

The two negative years are 2018 ({y2018}) and 2022 ({y2022}), both global
risk-off years. The 2022-2023 subperiod is still positive ({sub2223}) because
the 2023 recovery more than offsets the 2022 loss. Correlation to the existing
winners reaches 0.80 (`family-short-reversal`), so this is a high-beta cousin
of the TQQQ timing family, not an independent return stream.
""",
    "family-small-cap-relative": """
The small-cap family passes the headline test but fails the consistency test.
At 1 bp it makes **{cagr}** with a **{dd}** drawdown; all eight plateau cells
pass; the real result is at the 93rd percentile of the circular-shift placebo;
and the static 38/62 QQQ/TQQQ blend only makes {static_cagr}. But 2022 is
**{y2022}** and the 2022-2023 subperiod is **{sub2223}**. The IWM/QQQ spread stayed positive for much of
2022 because large-cap growth fell harder than small caps, so the strategy
stayed in TQQQ through the Nasdaq bear market. The signal is a risk-appetite
thermometer, not a crash detector.

Every plateau cell has a 75-79% drawdown. This is a levered Nasdaq beta
overlay with a small-cap tilt, not a defensive reserve. The 8/8 plateau is
therefore less impressive than it looks: the whole surface is high-return,
high-drawdown. Correlation to the existing winners reaches 0.83
(`family-rebalance-flow`), the highest of the four families.

The family is reported as a **negative result on the kill criteria** because
of the negative subperiod, even though the 1 bp headline clears the TQQQ bar.
A user who only cares about eight-year CAGR/DD could use it; a user who cares
about surviving 2022 should not.
""",
    "family-copper-gold": """
The copper/gold family is a clean negative. The primary makes **{cagr}** at
1 bp, below TQQQ's 36.72%, with a **{dd}** drawdown. None of the eight plateau
cells passes, the 10 bp result is {cagr10}, the placebo is only at the {pct}
percentile, the static 35/65 QQQ/TQQQ blend matches the strategy, and the
2022-2023 subperiod is negative ({sub2223}). Six of the nine kill criteria
trigger.

The best cell is the 126-session / -0.75 / binary variant at 33.55%, still
3.2 pp below the bar. The 20-session ablation is no better (29.8-35.7%). The
copper/gold ratio is a slow, noisy macro object; over 2016-2023 it does not
add usable timing information to a 3x Nasdaq sleeve. That is a useful
negative result: it closes off a plausible-sounding cross-asset idea rather
than hiding it in a parameter search.
""",
}


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%"


def f2(x):
    return f"{x:.2f}"


def f0(x):
    return f"{x:,.0f}"


def stats_row(label, s):
    return (f"| {label} | {pct(s['cagr'])} | {pct(s['max_drawdown'])} | "
            f"{f2(s['sharpe'])} | {f2(s['sortino'])} | {pct(s['volatility'])} | "
            f"{pct(s['exposure'])} | {s['fills']:,} | {f0(s['turnover'])}x |")


def main():
    ts, o, c = ca.load_panel()
    dates, _, last = bt.day_bounds(ts)
    idx = pd.DatetimeIndex(pd.to_datetime(dates[last])).tz_localize(None).normalize()
    tq = pd.Series(c[last, 1], index=idx)
    qq = pd.Series(c[last, 0], index=idx)
    tq_y = ca.yearly(tq)
    qq_y = ca.yearly(qq)
    tq_sub = ca.subperiods(tq)

    for slug in SLUGS:
        here = HERE / slug
        d = json.loads((here / "result.json").read_text(encoding="utf-8"))
        p = d["primary"]
        st = p["dev"]["1bp"]
        s5 = p["dev"]["5bp"]
        s10 = p["dev"]["10bp"]
        b = d["benchmarks"]
        lines = []
        add = lines.append

        add(f"# {TITLES[slug]} -- report")
        add("")
        add(f"**Slug:** `{slug}`  ")
        add(f"**Family:** `{d['family']}`  ")
        add(f"**Window:** {d['window']['dev'][0]} -> {d['window']['dev'][1]}, "
            f"development only. The 2024-2026 holdout was not loaded.  ")
        add("**Execution:** `research/bt.py`, 1-minute marks, next-open fills, "
            "2% band, long-only, weights >= 0, sum <= 1. Headline 1 bp; 5 bp and "
            "10 bp also reported.  ")
        add(f"**Primary:** {d['primary_object']}.  ")
        add(f"**Verdict:** `{d['verdict']}`  ")
        add("")
        tq_pass = (st["cagr"] > ca.TQQQ_BAR_CAGR
                   and st["max_drawdown"] < ca.TQQQ_BAR_DD)
        if slug == "family-small-cap-relative":
            lead = (f"**Verdict: `{d['verdict']}`.** The headline clears the TQQQ "
                    f"bar ({pct(st['cagr'])} vs 36.72% CAGR, "
                    f"{pct(st['max_drawdown'])} vs 82.29% max DD) but the "
                    f"2022-2023 subperiod is negative. The family is a high-beta "
                    f"Nasdaq overlay, not a defensive reserve.")
        elif tq_pass:
            lead = (f"**Verdict: `{d['verdict']}`.** The primary earns "
                    f"**{pct(st['cagr'])} CAGR / {pct(st['max_drawdown'])} max DD / "
                    f"{f2(st['sharpe'])} Sharpe** at 1 bp, above the published TQQQ "
                    f"bar (36.72% / 82.29% / 0.82) with a lower drawdown. It is a "
                    f"development-only result; 2024-2026 is untouched.")
        else:
            lead = (f"**Verdict: `{d['verdict']}`.** The primary earns "
                    f"**{pct(st['cagr'])} CAGR / {pct(st['max_drawdown'])} max DD / "
                    f"{f2(st['sharpe'])} Sharpe** at 1 bp, below the published TQQQ "
                    f"bar (36.72% / 82.29%). This is a negative result, reported in "
                    f"full; 2024-2026 is untouched.")
        add(lead)
        add("")
        add("---")
        add("")

        add("## 1. Headline")
        add("")
        add("| cost | CAGR | max DD | Sharpe | Sortino | vol | exposure | fills | turnover |")
        add("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        add(stats_row("**1 bp**", st))
        add(stats_row("5 bp", s5))
        add(stats_row("10 bp", s10))
        add("")
        add(f"The stated bar is TQQQ **36.72% CAGR / 82.29% max DD / 0.82 "
            f"Sharpe**. The local 1-minute benchmark is {pct(b['tqqq']['cagr'])} / "
            f"{pct(b['tqqq']['max_drawdown'])} / {f2(b['tqqq']['sharpe'])}. "
            f"Ending equity at 1 bp is **${st['ending_equity']:,.0f}** from $100,000. "
            f"There are **{p['events']:,}** distinct fill events.")
        add("")
        add(f"Average target weights: QQQ {pct(p['avg_weights'][0], 1)}, "
            f"TQQQ {pct(p['avg_weights'][1], 1)}, BIL {pct(p['avg_weights'][2], 1)}.")
        add("")

        add("## 2. Benchmarks")
        add("")
        add("| | CAGR | max DD | Sharpe | vol |")
        add("|---|---:|---:|---:|---:|")
        add(f"| primary 1 bp | {pct(st['cagr'])} | {pct(st['max_drawdown'])} | "
            f"{f2(st['sharpe'])} | {pct(st['volatility'])} |")
        add(f"| TQQQ | {pct(b['tqqq']['cagr'])} | {pct(b['tqqq']['max_drawdown'])} | "
            f"{f2(b['tqqq']['sharpe'])} | {pct(b['tqqq']['volatility'])} |")
        add(f"| QQQ | {pct(b['qqq']['cagr'])} | {pct(b['qqq']['max_drawdown'])} | "
            f"{f2(b['qqq']['sharpe'])} | {pct(b['qqq']['volatility'])} |")
        add("")

        add("## 3. Yearly returns")
        add("")
        add("| year | strategy | TQQQ | QQQ |")
        add("|---|---:|---:|---:|")
        for y, v in p["yearly"].items():
            add(f"| {y} | {pct(v, 1)} | {pct(tq_y.get(y, float('nan')), 1)} | "
                f"{pct(qq_y.get(y, float('nan')), 1)} |")
        add("")

        add("## 4. Subperiods")
        add("")
        add("| period | strategy CAGR | strategy DD | Sharpe | TQQQ CAGR | TQQQ DD |")
        add("|---|---:|---:|---:|---:|---:|")
        for name, v in p["subperiods"].items():
            t = tq_sub.get(name, {})
            add(f"| {name} | {pct(v['cagr'])} | {pct(v['max_drawdown'])} | "
                f"{f2(v['sharpe'])} | {pct(t.get('cagr', float('nan')))} | "
                f"{pct(t.get('max_drawdown', float('nan')))} |")
        add("")

        add("## 5. Eight-cell plateau")
        add("")
        add("| # | params | CAGR | max DD | Sharpe | fills | pass |")
        add("|---:|---|---:|---:|---:|---:|---|")
        for row in d["grid"]:
            s = row["1bp"]
            params = ", ".join(f"{k}={v}" for k, v in row["params"].items())
            add(f"| {row['cell']} | {params} | {pct(s['cagr'])} | "
                f"{pct(s['max_drawdown'])} | {f2(s['sharpe'])} | {s['fills']:,} | "
                f"{'yes' if row['pass'] else 'no'} |")
        add("")
        pl = d["plateau"]
        add(f"**{pl['pass_cells']} of {pl['cells']} cells pass** ({pct(pl['share'], 0)}). "
            f"The plateau rule requires at least 5 of 8.")
        add("")

        add("## 6. Ablations")
        add("")
        add("| params | CAGR | max DD | Sharpe | fills | pass |")
        add("|---|---:|---:|---:|---:|---|")
        for row in d.get("ablations", []):
            s = row["1bp"]
            params = ", ".join(f"{k}={v}" for k, v in row["params"].items())
            add(f"| {params} | {pct(s['cagr'])} | {pct(s['max_drawdown'])} | "
                f"{f2(s['sharpe'])} | {s['fills']:,} | "
                f"{'yes' if row['pass'] else 'no'} |")
        add("")

        add("## 7. Placebo")
        add("")
        plb = p["placebo"]
        add("Circular shifts of the daily target sequence preserve the allocation "
            "path and exposure but destroy its alignment with returns.")
        add("")
        add("| draws | CAGR p05 | CAGR p50 | CAGR p95 | CAGR max | real percentile | DD p50 |")
        add("|---:|---:|---:|---:|---:|---:|---:|")
        add(f"| {plb['n']} | {pct(plb['cagr_p05'])} | {pct(plb['cagr_p50'])} | "
            f"{pct(plb['cagr_p95'])} | {pct(plb['cagr_max'])} | "
            f"{pct(plb['cagr_percentile_of_real'], 0)} | {pct(plb['dd_p50'])} |")
        add("")
        add(f"Sharpe percentile of the real result: "
            f"{pct(plb['sharpe_percentile_of_real'], 0)}.")
        add("")

        add("## 8. Correlation to the nine winners")
        add("")
        add("| winner | correlation |")
        add("|---|---:|")
        for k, v in sorted(p["corr_winners"].items(), key=lambda kv: -kv[1]):
            add(f"| {k} | {v:.2f} |")
        add("")
        add(f"Range **{p['corr_range'][0]:.2f} .. {p['corr_range'][1]:.2f}**; "
            f"maximum is `{p['corr_max_name']}`. The duplicate threshold is 0.95.")
        add("")

        add("## 9. Static blend at the same average weights")
        add("")
        sb = p["static_blend_same_avg"]
        add("| | CAGR | max DD | Sharpe |")
        add("|---|---:|---:|---:|")
        add(f"| strategy 1 bp | {pct(st['cagr'])} | {pct(st['max_drawdown'])} | {f2(st['sharpe'])} |")
        add(f"| static average weights | {pct(sb['cagr'])} | {pct(sb['max_drawdown'])} | {f2(sb['sharpe'])} |")
        add("")

        add("## 10. Kill criteria -- verdict")
        add("")
        add("| # | criterion | triggered? |")
        add("|---:|---|---|")
        for i, (k, v) in enumerate(d["kill_checks"].items(), start=1):
            add(f"| {i} | `{k}` | {'**yes**' if v else 'no'} |")
        add("")
        add(f"**Verdict: `{d['verdict']}`.**")
        add("")

        add("## 11. Interpretation")
        add("")
        subs = p["subperiods"]
        sub2223 = subs.get("2022-2023", {}).get("cagr", float("nan"))
        add(NARRATIVE[slug].format(
            cagr=pct(st["cagr"]), dd=pct(st["max_drawdown"]),
            cagr10=pct(s10["cagr"]), static_cagr=pct(sb["cagr"]),
            tq_cagr=pct(b["tqqq"]["cagr"]), tq_dd=pct(b["tqqq"]["max_drawdown"]),
            y2016=pct(p["yearly"].get("2016", float("nan")), 1),
            y2018=pct(p["yearly"].get("2018", float("nan")), 1),
            y2022=pct(p["yearly"].get("2022", float("nan")), 1),
            sub2223=pct(sub2223, 1),
            pct=pct(plb["cagr_percentile_of_real"], 0),
        ).strip())
        add("")

        add("## 12. Causality and implementation")
        add("")
        cuts = d.get("cut_tests", [])
        for ct in cuts:
            add(f"- Truncating the panel at **{ct['cut']}** leaves "
                f"**{ct['bars_checked']:,}** prior weights identical "
                f"(`max_abs_weight_diff = {ct['max_abs_weight_diff']:.1e}`, "
                f"pass = {ct['pass']}).")
        add("- Signals use daily closes through session k; the target is written "
            "at k's 15:59 close and filled at k+1's 09:30 open.")
        add("- Signal legs are the external daily adjusted closes in "
            "`data/external/` (QQQ's leg is the local "
            "`QQQ-1d-yahoo.parquet`); execution prices are the local 1-minute "
            "QQQ/TQQQ/BIL panel.")
        add("- No same-day fill, no full-sample normalisation, no price-trend "
            "gate, no volatility targeting, no drawdown event, no calendar "
            "clock, no opening-range/close-flow, no ML and no relative-strength "
            "ratio gate.")
        add("- Long-only, weights 0/1 or a two-asset split, sum <= 1; BIL is the "
            "flat asset. The 2% band is the only rebalance dead-band.")
        add("")

        add("## 13. Caveats")
        add("")
        add("- Development-only: 2016-2023. The 2024-2026 holdout was physically "
            "excluded from every Parquet read.")
        add("- A separate process deposited `holdout.json` / `holdout_run.log` in "
            "this folder after the development run; this agent did not read or use "
            "them.")
        add("- The primary cell was chosen after daily-bar diagnostics on the "
            "same window; the 8-cell grid is a robustness probe, not a clean "
            "out-of-sample pre-registration.")
        add("- The 1-minute panel starts in 2016, so the sample cannot cover "
            "2000/2008.")
        add("- Costs are 1/5/10 bp on traded notional; the 2% band is fixed.")
        add("")

        (here / "report.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {here / 'report.md'}")


if __name__ == "__main__":
    main()
