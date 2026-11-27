"""Final analysis for the overnight / first-hour + crash-filter agent.

Writes result.json with every number quoted in report.md.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402
import check_sim as cs  # noqa: E402

OUT = HERE / "result.json"
BARS = lab.BARS_PER_YEAR


def dd_info(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd)); i = int(np.argmax(eq[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10], "dd": float(-dd[j])}


def full_metrics(ts, o, c, w, costs=(0.0, 1.0, 5.0, 10.0)):
    out = {}
    for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
        i = lab.bt.start_index(ts, start)
        out[tag] = {"start": start, "end": lab.END, "costs": {}}
        for slip in costs:
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=slip)
            s = lab.stats(r)
            rec = {
                "cagr": float(s["cagr"]),
                "max_drawdown": float(s["max_drawdown"]),
                "max_drawdown_daily_marks": float(lab.dd_daily(ts[i:], r["equity"])),
                "sharpe": float(s["sharpe"]),
                "sortino": float(s["sortino"]),
                "volatility": float(s["volatility"]),
                "fills": int(s["fills"]),
                "turnover": float(s["turnover"]),
                "exposure": float(s["exposure"]),
                "ending_equity": float(s["ending_equity"]),
                "total_return": float(s["total_return"]),
            }
            if slip == 1.0:
                rec["dd_window"] = dd_info(ts[i:], r["equity"])
                rec["yearly"] = {str(k): {"strategy": float(v["strategy"]),
                                          "benchmark": float(v["benchmark"])}
                                 for k, v in lab.yearly(ts[i:], r["equity"], c[i:, 1]).items()}
                rec["rolling3y"] = lab.rolling3(ts[i:], r["equity"], c[i:, 1])
            out[tag]["costs"][f"{slip:.0f}bp"] = rec
        b = lab.bt.benchmark(c[i:, 1], ts[i:], BARS)
        out[tag]["benchmark_tqqq"] = {k: float(b[k]) for k in
                                      ("cagr", "max_drawdown", "sharpe", "volatility")}
    return out


def swing_stats(ts, eq):
    """Rolling 3y: how often does the strategy beat TQQQ / the winner."""
    return None


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g0 = d.gate(band=0.0)
    g1 = d.gate(band=0.01)
    g2 = d.gate(band=0.02)

    variants = {}
    variants["winner_ref"] = cs.winner_weights(ts, o, c)
    # ---- primary: first-hour gate + vol crash filter + 4% stop -----------
    variants["R_primary"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, signal_thr=-0.005)
    # ---- alternatives / ablations ----------------------------------------
    variants["R0_thr0_band0"] = lab.build_weights(
        d, base="signal", m=60, gate=g0, vol_max=0.35, stop=0.04, signal_thr=0.0)
    variants["R_alt_vol32"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, vol_max=0.32, stop=0.04, signal_thr=-0.005)
    variants["R_alt_thr25"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, signal_thr=-0.0025)
    variants["R_no_volfilter"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, stop=0.04, signal_thr=-0.005)
    variants["R_base_nostop_novol"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, signal_thr=-0.005)
    variants["R_no_stop"] = lab.build_weights(
        d, base="signal", m=60, gate=g2, vol_max=0.35, signal_thr=-0.005)
    variants["R_m30"] = lab.build_weights(
        d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04, signal_thr=-0.005)
    # ---- pure overnight family -------------------------------------------
    variants["P1_overnight"] = lab.build_weights(
        d, base="overnight", gate=g2, vol_max=0.35)
    variants["P1_overnight_nofilter"] = lab.build_weights(d, base="overnight", gate=g2)
    variants["P2_morning30"] = lab.build_weights(
        d, base="morning", m=30, gate=g2, vol_pct_max=0.95)
    variants["P2_morning30_nofilter"] = lab.build_weights(
        d, base="morning", m=30, gate=g2)
    # ---- gate / do-nothing references ------------------------------------
    variants["ctrl_regime_only"] = lab.build_weights(d, base="full", gate=g0)

    res = {}
    for name, w in variants.items():
        print(f"computing {name} ...")
        res[name] = full_metrics(ts, o, c, w)

    # ---- swing / filter diagnostics -------------------------------------
    vol = d.vol(20, 0)
    i10 = int(np.searchsorted(d.ddates, np.datetime64(lab.START10)))
    yr = np.array([x.year for x in d.ddates])
    skips = {}
    for y in sorted(set(yr[i10:])):
        m = (yr == y) & (np.arange(d.nd) >= i10)
        skips[str(int(y))] = {
            "regime_on_days": int((g2 & m).sum()),
            "vol_skipped_days": int(((vol > 0.35) & g2 & m).sum()),
        }
    # regime flat episodes (band 2%)
    flat = []
    in_flat = False
    for k in range(i10, d.nd):
        if not g2[k] and not in_flat:
            start = d.ddates[k]; in_flat = True
        elif g2[k] and in_flat:
            flat.append([str(start), str(d.ddates[k - 1])]); in_flat = False
    if in_flat:
        flat.append([str(start), str(d.ddates[-1])])

    # rolling 3y head-to-head vs winner
    r_win = lab.run_window(ts, o, c, variants["winner_ref"], lab.START10, band=0.02, slippage_bps=1.0)
    r_pr = lab.run_window(ts, o, c, variants["R_primary"], lab.START10, band=0.02, slippage_bps=1.0)
    i10b = lab.bt.start_index(ts, lab.START10)
    roll_w = lab.rolling3(ts[i10b:], r_win["equity"], c[i10b:, 1])
    roll_p = lab.rolling3(ts[i10b:], r_pr["equity"], c[i10b:, 1])
    h2h = [{"start": a["start"], "primary_cagr": a["cagr"], "winner_cagr": b["cagr"],
            "primary_dd": a["dd"], "winner_dd": b["dd"],
            "primary_beats_winner_cagr": bool(a["cagr"] > b["cagr"]),
            "primary_lower_dd": bool(a["dd"] < b["dd"])}
           for a, b in zip(roll_p, roll_w)]

    out = {
        "agent": "overnight-crash-filter",
        "generated": "2026-11-25",
        "data": {"source": "data/intraday-hf (adjusted 1-minute QQQ/TQQQ/BIL)",
                 "first_bar": str(ts[0]), "last_bar": str(ts[-1]),
                 "bars": int(len(ts)), "sessions": int(d.nd),
                 "windows": {"10y": [lab.START10, lab.END], "5y": [lab.START5, lab.END]}},
        "primary": {
            "name": "first-hour gated TQQQ, 165d regime (2% band), 20d vol crash filter, 4% stop",
            "rules": {
                "regime": "QQQ close > 165d SMA*1.02 -> ON; < SMA*0.98 -> OFF; else hold state (signal at prior close)",
                "overnight": "TQQQ from 15:59 open to 10:30 open next session when regime ON",
                "crash_filter": "skip the overnight entry when QQQ 20d realised vol (through prior close) > 35% annualised",
                "afternoon": "hold TQQQ from 10:30 to 15:59 iff QQQ first-hour return (09:30->10:29) >= -0.5%",
                "stop": "while long, exit at next-minute open if TQQQ < session open*0.96 (rest of day, re-enter at 15:59)",
                "risk_off": "100% BIL",
                "fills": "next bar open", "band": 0.02,
            },
            "metrics": res["R_primary"],
        },
        "variants": {k: v for k, v in res.items() if k != "R_primary"},
        "diagnostics": {
            "vol_filter_skips_by_year": skips,
            "regime_flat_episodes": flat,
            "regime_on_days_10y": int(g2[i10:].sum()),
            "sessions_10y": int(d.nd - i10),
        },
        "rolling3y_primary_vs_winner": h2h,
        "references": {
            "winner_readme": lab.WINNER,
            "tqqq_bh_readme": lab.TQQQ_BH,
            "daily_baseline_readme": lab.DAILY_BASE,
            "time_of_day_v2_round1": lab.TOD_V2,
        },
    }
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print("wrote", OUT)

    # ---- console summary -------------------------------------------------
    for name in variants:
        r = res[name]
        print(f"{name:28s}", end="")
        for tag in ("10y", "5y"):
            for k in ("1bp", "5bp", "10bp"):
                m = r[tag]["costs"][k]
                print(f" {tag}{k} {m['cagr']*100:6.2f}/{m['max_drawdown']*100:5.2f}", end="")
            print(" |", end="")
        print()


if __name__ == "__main__":
    main()
