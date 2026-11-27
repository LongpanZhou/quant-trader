"""Dynamic leverage throttle on the winner: 30% TQQQ core + 70% 65%-vol-target.

Rules
-----
1. Regime (daily, no look-ahead): if QQQ's prior close is above its 165-day SMA,
   the session is risk-on; otherwise 100% BIL.
2. Size (risk-on): let v20 be the 20-day realised volatility of TQQQ daily
   close-to-close log returns (annualised, through the prior close).  Target
   volatility is 65%.  The TQQQ weight is
       w_t = 0.30 + 0.70 * min(1, 0.65 / v20)
   i.e. a permanent 30% TQQQ core plus a 70%-weighted inverse-vol satellite.
   The remainder is BIL.  There is no leverage above 100% TQQQ.
3. Stop (the winner's minute overlay): on a risk-on day, arm a 4% stop from the
   session open only when QQQ's first-minute close is below its prior 20-day
   SMA times 1.01.  If armed and TQQQ closes 4% below the session open, sell
   the whole book at the next minute's open and stay in BIL for the rest of the
   session.  Re-enter next session at the open if the regime is still on.
4. All daily weights are set from data through the prior close and fill at the
   next bar's open (09:31 for the first bar of the day).  Long only, weights
   sum to <= 1.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/agents2/dynamic-leverage-throttle/strategy.py
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
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
# Winner's stop / regime.
SMA_N, MA_FAST, ARM_BUF, STOP = 165, 20, 0.01, 0.04
# Throttle.
VOL_N, TARGET, CORE = 20, 0.65, 0.30
BAND = 0.02


def load_panel():
    # bt.panel caches on disk keyed by the parquet mtimes, at full float64
    # precision; the old local float32 panel.npz never invalidated.
    return bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")


def prev(a):
    return np.r_[np.nan, a[:-1]]


def build_signals(ts, opens, closes):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    dq, dt = closes[last, 0], closes[last, 1]
    ma20 = pd.Series(dq).rolling(MA_FAST).mean().to_numpy()
    sma = pd.Series(dq).rolling(SMA_N).mean().to_numpy()
    risk_on = np.zeros(len(first), bool)
    risk_on[1:] = dq[:-1] > prev(sma)[1:]
    armed = closes[first, 0] < prev(ma20) * (1.0 + ARM_BUF)
    ret = np.r_[np.nan, np.log(dt[1:] / dt[:-1])]
    vol20 = prev(pd.Series(ret).rolling(VOL_N).std().to_numpy() * np.sqrt(252))
    vol30 = prev(pd.Series(ret).rolling(30).std().to_numpy() * np.sqrt(252))
    dd60 = prev((dq / pd.Series(dq).rolling(60).max() - 1.0).to_numpy())
    trend = prev(dq / sma - 1.0)
    mu60 = prev(pd.Series(ret).rolling(60).mean().to_numpy())
    var60 = prev(pd.Series(ret).rolling(60).var().to_numpy())
    return dict(dates=dates, first=first, last=last, dq=dq, dt=dt,
                risk_on=risk_on, armed=armed, vol20=vol20, vol30=vol30,
                dd60=dd60, trend=trend, mu60=mu60, var60=var60)


def build_weights(sig, ts, opens, closes, day_tq, day_qq=None):
    """Minute weights from per-session TQQQ/QQQ targets, with the winner stop."""
    first, last = sig["first"], sig["last"]
    risk_on = sig["risk_on"]
    if day_qq is None:
        day_qq = np.zeros(len(first))
    tq = np.where(risk_on, np.clip(day_tq, 0.0, 1.0), 0.0)
    qq = np.where(risk_on, np.clip(day_qq, 0.0, 1.0), 0.0)
    tot = tq + qq
    over = tot > 1.0
    if over.any():
        tq[over] /= tot[over]
        qq[over] /= tot[over]
    qc, tc = closes[:, 0], closes[:, 1]
    w = np.zeros((len(ts), 3))
    for k in range(len(first)):
        f, l = first[k], last[k]
        wt, wq = tq[k], qq[k]
        if wt <= 0 and wq <= 0:
            w[f:l + 1, 2] = 1.0
            continue
        if not sig["armed"][k]:
            w[f:l + 1, 0] = wq
            w[f:l + 1, 1] = wt
            w[f:l + 1, 2] = 1.0 - wt - wq
            continue
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if state and tc[i] < base * (1.0 - STOP):
                state = False
            if state:
                w[i, 0] = wq
                w[i, 1] = wt
                w[i, 2] = 1.0 - wt - wq
            else:
                w[i, 2] = 1.0
    return w


def throttle(sig, target=TARGET, core=CORE, vol=None):
    v = sig["vol20"] if vol is None else vol
    return core + (1.0 - core) * np.minimum(1.0, target / v)


def run_window(w, ts, opens, closes, start, slip):
    r = bt.run(ts, opens, closes, w, start, band=BAND, slippage_bps=slip)
    s = bt.stats(r, BARS)
    s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
    eq = pd.Series(r["equity"], index=r["ts"])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["max_drawdown_daily_marks"] = float(-(deq / peak - 1.0).min())
    i0 = bt.start_index(ts, start)
    s["bench_tqqq"] = bt.benchmark(closes[i0:, 1], ts[i0:], BARS)
    return r, s


def yearly_rows(ts, equity, bench, start):
    i0 = bt.start_index(ts, start)
    y = bt.yearly(ts[i0:], equity, bench[i0:])
    return {int(k): {"strategy": float(v["strategy"]),
                     "benchmark": float(v["benchmark"])} for k, v in y.items()}


def main():
    ts, opens, closes = load_panel()
    sig = build_signals(ts, opens, closes)
    cand = build_weights(sig, ts, opens, closes, throttle(sig))
    win = build_weights(sig, ts, opens, closes, np.ones(len(sig["first"])))

    out = {
        "agent": "dynamic-leverage-throttle",
        "strategy": "30% TQQQ core + 70% 65%-vol-target TQQQ, BIL residual, "
                    "with the winner's armed 4% minute stop",
        "params": {"sma": SMA_N, "ma_arm": MA_FAST, "arm_buf": ARM_BUF,
                   "stop": STOP, "vol_n": VOL_N, "target_vol": TARGET,
                   "core": CORE, "band": BAND,
                   "instrument": "TQQQ / QQQ / BIL", "long_only": True},
        "windows": {},
        "cost_sensitivity": {},
        "yearly": {},
        "rolling_3y": {},
        "variants_1bp": {},
        "half_periods": {},
        "causality": {},
    }

    for tag, start in (("10y", START10), ("5y", START5)):
        rec = {}
        for slip in (1.0, 5.0, 10.0):
            rc, sc = run_window(cand, ts, opens, closes, start, slip)
            rw, sw = run_window(win, ts, opens, closes, start, slip)
            rec[f"{int(slip)}bp"] = {
                "candidate": {k: float(v) for k, v in sc.items()
                              if not isinstance(v, dict)},
                "winner": {k: float(v) for k, v in sw.items()
                           if not isinstance(v, dict)},
                "tqqq": {k: float(v) for k, v in sc["bench_tqqq"].items()},
            }
        out["windows"][tag] = rec
        out["yearly"][tag] = {
            "candidate": yearly_rows(ts, rc["equity"], closes[:, 1], start),
            "winner": yearly_rows(ts, rw["equity"], closes[:, 1], start),
        }

    # Rolling 3-year windows, quarterly starts 2017-04 .. 2023-10.
    starts = [pd.Timestamp(y, m, 1) for y in range(2017, 2024)
              for m in (1, 4, 7, 10)
              if pd.Timestamp("2017-04-01") <= pd.Timestamp(y, m, 1)
              <= pd.Timestamp("2023-10-01")]
    roll = []
    for s in starts:
        i0 = int(ts.searchsorted(s.tz_localize("America/New_York")))
        e = s + pd.DateOffset(years=3)
        i1 = int(ts.searchsorted(e.tz_localize("America/New_York")))
        b = bt.benchmark(closes[i0:i1, 1], ts[i0:i1], BARS)
        entry = {"start": str(s.date()), "end": str(e.date()),
                 "tqqq": {"cagr": float(b["cagr"]),
                          "max_drawdown": float(b["max_drawdown"])}}
        for name, w in (("candidate", cand), ("winner", win)):
            r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], w[i0:i1],
                            band=BAND, slippage_bps=1.0)
            st = bt.stats(r, BARS)
            entry[name] = {"cagr": float(st["cagr"]),
                           "max_drawdown": float(st["max_drawdown"]),
                           "calmar": float(st["cagr"] / st["max_drawdown"])}
        roll.append(entry)
    out["rolling_3y"]["windows"] = roll

    def count(fn):
        return int(sum(1 for e in roll if fn(e)))

    out["rolling_3y"]["counts"] = {
        "n": len(roll),
        "candidate_ret_gt_tqqq": count(lambda e: e["candidate"]["cagr"] > e["tqqq"]["cagr"]),
        "candidate_dd_lt_tqqq": count(lambda e: e["candidate"]["max_drawdown"] < e["tqqq"]["max_drawdown"]),
        "winner_ret_gt_tqqq": count(lambda e: e["winner"]["cagr"] > e["tqqq"]["cagr"]),
        "winner_dd_lt_tqqq": count(lambda e: e["winner"]["max_drawdown"] < e["tqqq"]["max_drawdown"]),
        "candidate_ret_gt_winner": count(lambda e: e["candidate"]["cagr"] > e["winner"]["cagr"]),
        "candidate_dd_lt_winner": count(lambda e: e["candidate"]["max_drawdown"] < e["winner"]["max_drawdown"]),
        "candidate_both_gt_winner": count(
            lambda e: e["candidate"]["cagr"] > e["winner"]["cagr"]
            and e["candidate"]["max_drawdown"] < e["winner"]["max_drawdown"]),
        "candidate_calmar_gt_winner": count(
            lambda e: e["candidate"]["calmar"] > e["winner"]["calmar"]),
    }

    # Variant table (1 bp) - mandated neighbours and negative controls.
    n = len(sig["first"])
    variants = {
        "vol_target_45": throttle(sig, 0.45, 0.0),
        "vol_target_55": throttle(sig, 0.55, 0.0),
        "vol_target_65": throttle(sig, 0.65, 0.0),
        "vol_target_80": throttle(sig, 0.80, 0.0),
        "vol65_core20": throttle(sig, 0.65, 0.20),
        "vol65_core30_PRIMARY": throttle(sig, 0.65, 0.30),
        "vol65_core40": throttle(sig, 0.65, 0.40),
        "vol65_core30_vol30": throttle(sig, 0.65, 0.30, sig["vol30"]),
        "drawdown60_k0.5": np.clip(1.0 - 0.5 * np.maximum(-sig["dd60"], 0.0), 0.25, 1.0),
        "trend_band4_floor50": np.clip(0.5 + 0.5 * sig["trend"] / 0.04, 0.5, 1.0),
        "kelly60_half": np.clip(0.5 * np.maximum(sig["mu60"], 0.0) / sig["var60"], 0.0, 1.0),
        "winner_100pct": np.ones(n),
    }
    for name, wt in variants.items():
        w = build_weights(sig, ts, opens, closes, wt)
        row = {}
        for tag, start in (("10y", START10), ("5y", START5)):
            _, s = run_window(w, ts, opens, closes, start, 1.0)
            row[tag] = {k: float(s[k]) for k in
                        ("cagr", "max_drawdown", "calmar", "sharpe", "fills",
                         "turnover", "exposure")}
        out["variants_1bp"][name] = row
        print(f"{name:24s} 10y {row['10y']['cagr']*100:6.2f}/{row['10y']['max_drawdown']*100:5.2f}"
              f" 5y {row['5y']['cagr']*100:6.2f}/{row['5y']['max_drawdown']*100:5.2f}",
              flush=True)

    # Half periods.
    for tag, start, end in (("2017_2021", "2017-01-03", "2021-12-31"),
                            ("2022_2026", "2022-01-03", "2026-10-23")):
        i0 = int(ts.searchsorted(pd.Timestamp(start, tz="America/New_York")))
        i1 = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"))) + 1
        rec = {}
        for name, w in (("candidate", cand), ("winner", win)):
            r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], w[i0:i1],
                            band=BAND, slippage_bps=1.0)
            s = bt.stats(r, BARS)
            rec[name] = {"cagr": float(s["cagr"]),
                         "max_drawdown": float(s["max_drawdown"]),
                         "calmar": float(s["cagr"] / s["max_drawdown"])}
        out["half_periods"][tag] = rec

    # Causality: truncate at a session boundary and compare prior weights.
    j = int(np.searchsorted(sig["dates"], pd.Timestamp("2022-01-03").date()))
    ts_t, op_t, cl_t = ts[:j], opens[:j], closes[:j]
    sig_t = build_signals(ts_t, op_t, cl_t)
    cand_t = build_weights(sig_t, ts_t, op_t, cl_t, throttle(sig_t))
    out["causality"] = {
        "truncation": "2022-01-03",
        "prior_weights_identical": bool(np.array_equal(cand[:j], cand_t)),
        "max_abs_diff": float(np.max(np.abs(cand[:j] - cand_t))) if j else 0.0,
    }

    # Pass/fail.
    w10 = out["windows"]["10y"]["1bp"]
    w5 = out["windows"]["5y"]["1bp"]
    for tag in ("10y", "5y"):
        c = out["windows"][tag]["1bp"]["candidate"]
        w = out["windows"][tag]["1bp"]["winner"]
        t = out["windows"][tag]["1bp"]["tqqq"]
        out["windows"][tag]["pass"] = {
            "cagr_gt_tqqq": bool(c["cagr"] > t["cagr"]),
            "dd_lt_tqqq": bool(c["max_drawdown"] < t["max_drawdown"]),
            "cagr_within_2pp_winner": bool(c["cagr"] > w["cagr"] - 0.02),
            "dd_lt_winner": bool(c["max_drawdown"] < w["max_drawdown"]),
            "strict_dominance": bool(c["cagr"] > w["cagr"]
                                     and c["max_drawdown"] < w["max_drawdown"]),
            "calmar_gt_winner": bool(c["calmar"] > w["calmar"]),
        }
    out["pass_criterion2_both"] = bool(
        out["windows"]["10y"]["pass"]["cagr_within_2pp_winner"]
        and out["windows"]["10y"]["pass"]["dd_lt_winner"]
        and out["windows"]["5y"]["pass"]["cagr_within_2pp_winner"]
        and out["windows"]["5y"]["pass"]["dd_lt_winner"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2))

    for tag in ("10y", "5y"):
        c = out["windows"][tag]["1bp"]["candidate"]
        c5 = out["windows"][tag]["5bp"]["candidate"]
        c10 = out["windows"][tag]["10bp"]["candidate"]
        w = out["windows"][tag]["1bp"]["winner"]
        t = out["windows"][tag]["1bp"]["tqqq"]
        print(f"\n{tag}  candidate 1bp {c['cagr']*100:6.2f}/{c['max_drawdown']*100:5.2f} "
              f"Cal {c['calmar']:.2f} Sh {c['sharpe']:.2f} fills {c['fills']:.0f}")
        print(f"      winner    1bp {w['cagr']*100:6.2f}/{w['max_drawdown']*100:5.2f} "
              f"Cal {w['calmar']:.2f} Sh {w['sharpe']:.2f}")
        print(f"      TQQQ      1bp {t['cagr']*100:6.2f}/{t['max_drawdown']*100:5.2f}")
        print(f"      candidate 5bp {c5['cagr']*100:6.2f}/{c5['max_drawdown']*100:5.2f} "
              f"Cal {c5['calmar']:.2f} | 10bp {c10['cagr']*100:6.2f}/{c10['max_drawdown']*100:5.2f}")
        print("      pass " + json.dumps(out["windows"][tag]["pass"]))
    print("\nrolling counts", json.dumps(out["rolling_3y"]["counts"]))
    print("causality", out["causality"])
    print("criterion2 both windows:", out["pass_criterion2_both"])
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
