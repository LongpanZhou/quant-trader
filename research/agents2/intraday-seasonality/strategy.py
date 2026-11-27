"""Final evaluation for the intraday-seasonality agent.

Strategy (the winner plus the one overlay that survived):
  * round-1 winner: QQQ 165-day SMA regime, 100% TQQQ risk-on / 100% BIL
    risk-off, 4% intraday stop from the session open armed when QQQ's first
    minute is below its 20-day SMA x 1.01, out for the rest of the day and the
    night after a stop.
  * overlay: at 15:00 ET on a risk-on session, if QQQ is more than 1.0% below
    its session open, move TQQQ to BIL at the 15:01 open and buy back at the
    15:30 open.  Otherwise nothing changes.

Writes result.json and prints every table used in report.md.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/strategy.py
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
import lib  # noqa: E402

OUT = Path(__file__).resolve().parent
START10, START5, END = lib.START10, lib.START5, lib.END
IS_END = "2022-01-01"
THR = -0.010
CARVE = ((15, 0), (15, 30))

WINNER = {"10y": {"cagr": 0.5880, "dd": 0.4456},
          "5y": {"cagr": 0.4988, "dd": 0.3349}}
WINNER_5 = {"10y": {"cagr": 0.5460, "dd": 0.4708},
            "5y": {"cagr": 0.4589, "dd": 0.3413}}
WINNER_10 = {"10y": {"cagr": 0.4950, "dd": 0.5006},
             "5y": {"cagr": 0.4105, "dd": 0.3493}}
TQQQ = {"10y": {"cagr": 0.3928, "dd": 0.8168},
        "5y": {"cagr": 0.1347, "dd": 0.8168}}


def build(ts, opens, closes, cal, w_base, thr=THR, carve=CARVE):
    i0 = lib.time_index(ts, cal["first"], cal["last"], *carve[0])
    sig = closes[i0, 0] / opens[cal["first"], 0] - 1.0
    mask = sig < thr
    w = lib.carve(w_base, cal, carve[0], carve[1], ts, mask)
    return w, mask, sig


def metrics(r, ts, start, end=None):
    s = lib.window(r, ts, start, end)
    return {k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                              "volatility", "total_return", "ending_equity")}


def main():
    ts, opens, closes = lib.load_panel()
    cal = lib.calendar(ts)
    first, last = cal["first"], cal["last"]
    w_base, base_diag = lib.build_base(ts, opens, closes)
    w_fin, mask, sig = build(ts, opens, closes, cal, w_base)

    out = {
        "agent": "intraday-seasonality",
        "strategy": {
            "base": "round-1 winner: QQQ 165d SMA regime + 4% intraday stop armed below MA20*1.01",
            "overlay": ("on risk-on sessions where QQQ at 15:00 is more than 1.0% below the "
                        "session open, hold BIL from the 15:01 open to the 15:30 open"),
            "fills": "next bar open",
            "threshold": THR,
            "carve": "15:00 weight -> 15:29 restore (out 15:01..15:30)",
        },
        "base_diagnostics": {"days": base_diag["days"], "stop_events": base_diag["stop_events"]},
        "overlay_diagnostics": {"signal_days": int(mask.sum())},
        "windows": {}, "base_windows": {}, "tqqq": {},
        "cost": {}, "yearly": {}, "rolling3": {}, "subperiods": {},
        "neighbours": {}, "walkforward": {}, "families": {},
    }

    # ---------------------------------------------------------- headline
    r_fin = lib.simulate(ts, opens, closes, w_fin, 1.0)
    r_base = lib.simulate(ts, opens, closes, w_base, 1.0)
    for label, start in (("10y", START10), ("5y", START5)):
        out["windows"][label] = metrics(r_fin, ts, start)
        out["base_windows"][label] = metrics(r_base, ts, start)
        i = bt.start_index(ts, start)
        out["tqqq"][label] = bt.benchmark(closes[i:, 1], ts[i:], lib.BARS_PER_YEAR)

    print("=== headline, 1 bp ===")
    for label in ("10y", "5y"):
        f, b = out["windows"][label], out["base_windows"][label]
        print(f"  {label}: final {f['cagr']*100:6.2f}/{f['max_drawdown']*100:5.2f}  "
              f"base {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f}  "
              f"fills {r_fin['fills']}  end ${f['ending_equity']:,.0f}")

    # ------------------------------------------------ effective events
    i1500 = lib.time_index(ts, first, last, *CARVE[0])
    i1530 = lib.time_index(ts, first, last, *CARVE[1])
    held = w_base[i1500, 1] > 0.5
    blk = opens[i1530, 1] / opens[i1500 + 1, 1] - 1.0
    ex = mask & held & np.isfinite(blk)
    gain = -blk[ex]
    out["overlay_diagnostics"] = {
        "signal_days": int(mask.sum()),
        "executed_sessions": int(ex.sum()),
        "preempted_by_stop_or_regime": int((mask & ~held).sum()),
        "mean_gain_bp": float(gain.mean() * 1e4),
        "median_gain_bp": float(np.median(gain) * 1e4),
        "t_stat": float(gain.mean() / (gain.std(ddof=1) / np.sqrt(len(gain)))),
        "win_rate": float(np.mean(gain > 0)),
        "per_year": int(round(ex.sum() / 9.8)),
    }
    print(f"\noverlay: {mask.sum()} signal days, {ex.sum()} executed "
          f"(~{ex.sum()/9.8:.0f}/yr), mean gain {gain.mean()*1e4:.2f}bp "
          f"t={out['overlay_diagnostics']['t_stat']:.2f} win {np.mean(gain>0)*100:.1f}%")

    # ---------------------------------------------------------- costs
    print("\n=== cost sensitivity ===")
    for slip in (0.0, 1.0, 5.0, 10.0):
        r = lib.simulate(ts, opens, closes, w_fin, slip)
        row = {}
        for label, start in (("10y", START10), ("5y", START5)):
            row[label] = metrics(r, ts, start)
            print(f"  {slip:2.0f}bp {label}: {row[label]['cagr']*100:6.2f}% / "
                  f"{row[label]['max_drawdown']*100:5.2f}%  sharpe {row[label]['sharpe']:.2f}")
        out["cost"][f"{slip:.0f}bp"] = row

    # ---------------------------------------------------------- yearly
    print("\n=== yearly ===")
    i10 = bt.start_index(ts, START10)
    bench = closes[i10:, 1]
    yearly = {}
    for lab, e in (("final", r_fin["equity"]), ("base", r_base["equity"])):
        yearly[lab] = lib.yearly_table(ts, e, START10)
    ty = {}
    t = ts[i10:]
    for y in sorted(set(t.year)):
        m = t.year == y
        if m.sum() > 1:
            ty[int(y)] = float(bench[m][-1] / bench[m][0] - 1)
    for y in sorted(yearly["final"]):
        print(f"  {y}: final {yearly['final'][y]*100:7.2f}%  base {yearly['base'][y]*100:7.2f}%  "
              f"TQQQ {ty.get(y, float('nan'))*100:7.2f}%")
    out["yearly"] = {"final": yearly["final"], "base": yearly["base"], "tqqq": ty}

    # ---------------------------------------------------------- sub-periods
    print("\n=== sub-periods (1bp) ===")
    for name, a, b in (("2017-2019", "2017-01-03", "2020-01-01"),
                       ("2020-2022", "2020-01-01", "2023-01-01"),
                       ("2023-2026", "2023-01-01", None),
                       ("IS 2017-2021", "2017-01-03", IS_END),
                       ("OOS 2022-2026", IS_END, None)):
        f = metrics(r_fin, ts, a, b)
        bb = metrics(r_base, ts, a, b)
        out["subperiods"][name] = {"final": f, "base": bb}
        print(f"  {name:15s} final {f['cagr']*100:6.2f}%/{f['max_drawdown']*100:5.2f}%   "
              f"base {bb['cagr']*100:6.2f}%/{bb['max_drawdown']*100:5.2f}%")

    # ---------------------------------------------------------- rolling 3y
    print("\n=== rolling 3-year windows (quarterly starts) ===")
    starts = pd.date_range("2017-01-03", "2023-10-23", freq="QS", tz="America/New_York")
    ro_f = lib.rolling3(ts, r_fin["equity"], starts)
    ro_b = lib.rolling3(ts, r_base["equity"], starts)
    ro_t = lib.rolling3(ts, closes[i10:, 1], starts) if False else None
    # benchmark on the same grid
    ro_t = []
    for s, f, b in zip(starts, ro_f, ro_b):
        j0 = int(np.searchsorted(ts, s))
        j1 = int(np.searchsorted(ts, s + pd.DateOffset(months=36)))
        if j1 > len(ts) or j1 <= j0 + 100:
            continue
        e = bench[j0 - i10:j1 - i10]
        yrs = (ts[j1 - 1] - ts[j0]).total_seconds() / (365.25 * 86400)
        peak = np.maximum.accumulate(e)
        ro_t.append({"start": str(s.date()),
                     "cagr": float((e[-1] / e[0]) ** (1 / yrs) - 1),
                     "dd": float(-(e / peak - 1).min())})
    ro_t = [x for x in ro_t if any(x["start"] == y["start"] for y in ro_f)]
    beat_base = sum(1 for f, b in zip(ro_f, ro_b) if f["cagr"] > b["cagr"])
    beat_tqqq = sum(1 for f, tq in zip(ro_f, ro_t) if f["cagr"] > tq["cagr"])
    lower_dd_base = sum(1 for f, b in zip(ro_f, ro_b) if f["dd"] < b["dd"])
    lower_dd_tqqq = sum(1 for f, tq in zip(ro_f, ro_t) if f["dd"] < tq["dd"])
    print(f"  {len(ro_f)} windows; beats base CAGR {beat_base}, lower DD {lower_dd_base}; "
          f"beats TQQQ CAGR {beat_tqqq}, lower DD {lower_dd_tqqq}")
    for f, b, tq in zip(ro_f, ro_b, ro_t):
        print(f"    {f['start']}  final {f['cagr']*100:6.1f}/{f['dd']*100:5.1f}  "
              f"base {b['cagr']*100:6.1f}/{b['dd']*100:5.1f}  TQQQ {tq['cagr']*100:6.1f}/{tq['dd']*100:5.1f}")
    out["rolling3"] = {"windows": ro_f, "base": ro_b, "tqqq": ro_t,
                       "n": len(ro_f), "beat_base_cagr": beat_base,
                       "lower_dd_than_base": lower_dd_base,
                       "beat_tqqq_cagr": beat_tqqq, "lower_dd_than_tqqq": lower_dd_tqqq}

    # ---------------------------------------------------------- neighbours
    print("\n=== neighbours: threshold x window (1bp) ===")
    for carve, cname in ((((15, 0), (15, 30)), "15:00-15:30"),
                         (((15, 0), (15, 59)), "15:00-15:59"),
                         (((15, 30), (15, 59)), "15:30-15:59")):
        for thr in (0.0, -0.005, -0.0075, -0.010, -0.0125, -0.015, -0.020):
            w, m, _ = build(ts, opens, closes, cal, w_base, thr, carve)
            r = lib.simulate(ts, opens, closes, w, 1.0)
            row = {"thr": thr, "events": int(m.sum()), "fills": r["fills"]}
            for label, start, end in (("10y", START10, None), ("5y", START5, None),
                                      ("IS", START10, IS_END), ("OOS", IS_END, None)):
                s = lib.window(r, ts, start, end)
                row[f"{label}_cagr"] = s["cagr"]
                row[f"{label}_dd"] = s["max_drawdown"]
            out["neighbours"][f"{cname} thr{thr:.4f}"] = row
            print(f"  {cname} thr{thr*100:6.2f}% "
                  f"events {row['events']:4d}  10y {row['10y_cagr']*100:6.2f}/{row['10y_dd']*100:5.2f}  "
                  f"5y {row['5y_cagr']*100:6.2f}/{row['5y_dd']*100:5.2f}  "
                  f"IS {row['IS_cagr']*100:6.2f}  OOS {row['OOS_cagr']*100:6.2f}")

    # ---------------------------------------------------------- walk-forward
    print("\n=== walk-forward threshold selection ===")
    years = cal["year"]
    dyear = np.array([t.year for t in ts])
    lasty = {y: int(np.flatnonzero(dyear == y)[-1]) for y in range(2017, 2027)}
    firsty = {y: int(np.flatnonzero(dyear == y)[0]) for y in range(2017, 2027)}
    variants = {}
    for thr in (0.0, -0.0025, -0.005, -0.0075, -0.010, -0.0125, -0.015, -0.020):
        w, _, _ = build(ts, opens, closes, cal, w_base, thr, CARVE)
        variants[thr] = lib.simulate(ts, opens, closes, w, 1.0)["equity"]

    def yret(e, y):
        a, b = firsty[y], lasty[y]
        return e[b] / e[a - 1] - 1.0

    wf, base_c = 1.0, 1.0
    wf_rows = []
    for y in range(2019, 2027):
        prior = range(2017, y)
        score = {}
        for thr, e in variants.items():
            g = 1.0
            for yy in prior:
                g *= 1 + yret(e, yy)
            score[thr] = g ** (1 / len(list(prior))) - 1
        best = max(score, key=score.get)
        r = yret(variants[best], y)
        wf *= 1 + r
        base_c *= 1 + yret(r_base["equity"], y)
        wf_rows.append({"year": y, "thr": best, "ret": r,
                        "base": yret(r_base["equity"], y), "is_score": score[best]})
        print(f"  {y}: pick {best*100:6.2f}% -> {r*100:7.2f}%  base {yret(r_base['equity'],y)*100:7.2f}%")
    n = len(wf_rows)
    out["walkforward"] = {"rows": wf_rows,
                          "cagr": wf ** (1 / n) - 1, "base_cagr": base_c ** (1 / n) - 1,
                          "excess": (wf / base_c) ** (1 / n) - 1}
    print(f"  WF {2019}-2026 {out['walkforward']['cagr']*100:.2f}% vs base "
          f"{out['walkforward']['base_cagr']*100:.2f}%  excess {out['walkforward']['excess']*100:+.2f}pp")

    # ---------------------------------------------------------- other families
    print("\n=== other families tested (1bp, 10y/5y CAGR-DD) ===")
    fam = {}
    i0931 = lib.time_index(ts, first, last, 9, 31)
    i0935 = lib.time_index(ts, first, last, 9, 35)
    q_open = opens[first, 0]
    prev_c = np.r_[np.nan, closes[last, 0][:-1]]
    gap = q_open / prev_c - 1.0
    for name, mk in (("opening5 gap<-1.5%", gap < -0.015),
                     ("opening5 gap>+1.5%", gap > 0.015)):
        w = lib.carve(w_base, cal, (9, 31), (9, 35), ts, mk)
        fam[name] = {**ev_dict(ts, opens, closes, w), "events": int(mk.sum())}

    # lunch: 12:00-14:00 on OpEx week and after a big morning move
    i1200 = lib.time_index(ts, first, last, 12, 0)
    q_morning = closes[i1200, 0] / q_open - 1.0
    for name, mk in (("lunch opex week", cal["opex"]),
                     ("lunch morning>+1.5%", q_morning > 0.015),
                     ("lunch morning<-1.5%", q_morning < -0.015)):
        w = lib.carve(w_base, cal, (12, 0), (14, 0), ts, mk)
        fam[name] = {**ev_dict(ts, opens, closes, w), "events": int(mk.sum())}

    # day-of-week: no-stop and carve variants
    for name, mk in (("last30 wednesdays", cal["dow"] == 2),
                     ("last30 opex week", cal["opex"]),
                     ("last30 pre-holiday", cal["pre_hol"])):
        w = lib.carve(w_base, cal, (15, 0), (15, 30), ts, mk)
        fam[name] = {**ev_dict(ts, opens, closes, w), "events": int(mk.sum())}

    # stop gating by calendar (zero extra turnover)
    for name, gate in (("no stop on opex week", ~cal["opex"]),
                       ("no stop on pre-holiday", ~cal["pre_hol"]),
                       ("no stop on post-holiday", ~cal["post_hol"]),
                       ("no stop on fridays", cal["dow"] != 4)):
        w, _ = lib.build_base(ts, opens, closes, armed_mask=gate)
        fam[name] = {**ev_dict(ts, opens, closes, w), "events": int((~gate).sum())}

    for name, d in fam.items():
        print(f"  {name:28s} 10y {d['10y_cagr']*100:6.2f}/{d['10y_dd']*100:5.2f}  "
              f"5y {d['5y_cagr']*100:6.2f}/{d['5y_dd']*100:5.2f}  events {d['events']}")
    out["families"] = fam

    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))

    # ---------------------------------------------------------- harness check
    print("\n=== independent harness check (bt.simulate, 1bp, 10y) ===")
    ref = bt.run(ts, opens, closes, w_fin, START10, band=0.02, slippage_bps=1.0)
    s = bt.stats(ref, lib.BARS_PER_YEAR)
    print(f"  bt.simulate CAGR {s['cagr']*100:.4f}%  DD {s['max_drawdown']*100:.4f}%  "
          f"end ${s['ending_equity']:,.2f}  fills {s['fills']}")
    out["verification"] = {
        "bt_simulate_10y_cagr": s["cagr"], "bt_simulate_10y_dd": s["max_drawdown"],
        "bt_simulate_fills": s["fills"],
        "fast_sim_10y_cagr": out["windows"]["10y"]["cagr"],
        "fast_sim_10y_dd": out["windows"]["10y"]["max_drawdown"],
    }
    (OUT / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nwrote", OUT / "result.json")


def ev_dict(ts, opens, closes, w):
    r = lib.simulate(ts, opens, closes, w, 1.0)
    d = {}
    for label, start in (("10y", START10), ("5y", START5)):
        s = lib.window(r, ts, start)
        d[f"{label}_cagr"] = s["cagr"]
        d[f"{label}_dd"] = s["max_drawdown"]
    d["fills"] = r["fills"]
    return d


if __name__ == "__main__":
    main()
