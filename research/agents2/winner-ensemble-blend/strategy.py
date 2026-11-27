"""Winner + round-1 ensemble: causal inverse-volatility blend (round 2, agent 11).

Blend
-----
Three round-1 sleeves, all long-only QQQ/TQQQ/BIL with next-bar-open fills:

  winner    daily QQQ 165d SMA regime + armed 4% minute stop   (agent 1)
  ensemble  trend + 20d vol budget + 1m crash vote             (agent 8)
  momentum  overnight drift + first-hour QQQ momentum          (agent 4)

At every bar the capital is split in proportion to the inverse of each sleeve's
trailing 20-day realised volatility (daily equity returns, shifted one day),
clipped to [0.15, 0.65] and renormalised.  The sleeve weights are then averaged
with those allocations.  Everything is causal: the allocation for day d uses
sleeve returns through day d-1, and the blended target set at bar i fills at
open i+1.

Variants reported
-----------------
  IV3  primary: inverse-vol winner / ensemble / momentum (20d, clip .15/.65)
  IV2  aggressive: inverse-vol winner / momentum (20d, clip .30/.70)
  WE75 low-turnover: fixed 75% winner / 25% ensemble

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/winner-ensemble-blend/strategy.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BPY = 252 * 390
BAND = 0.02
SLIPS = (0.0, 1.0, 2.0, 5.0, 10.0)
IV_LB, IV_LO, IV_HI = 20, 0.15, 0.65
IV2_LO, IV2_HI = 0.30, 0.70


# --------------------------------------------------------------------------- #
# simulator: thin wrapper over bt.simulate (compiled core)
# --------------------------------------------------------------------------- #
def fast_sim(ts, opens, closes, w, slippage_bps=1.0, band=BAND,
             start_equity=100_000.0):
    """Delegates to bt.simulate (compiled Rust core, exact for any weights)."""
    r = bt.simulate(ts, opens, closes, w, band=band, slippage_bps=slippage_bps,
                    start_equity=start_equity)
    r.pop("cash")
    return r


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def daily_series(ts, x):
    s = pd.Series(x, index=ts)
    d = s.groupby(s.index.date).last()
    return pd.DatetimeIndex(pd.to_datetime(d.index)), d.to_numpy(float)


def inverse_vol_alloc(ts, eq_list, lookback, lo, hi):
    """Causal inverse-vol weights per sleeve, one value per calendar day.

    A daily return series is indexed by its *end* date; shift(1) in date space
    means day d's allocation uses returns through day d-1 only.
    """
    cols = []
    dts = None
    for eq in eq_list:
        dts, de = daily_series(ts, eq)
        r = pd.Series(np.diff(de) / de[:-1], index=dts[1:])
        cols.append(r.rolling(lookback).std().shift(1))
    V = pd.concat(cols, axis=1)
    inv = 1.0 / V
    W = inv.div(inv.sum(axis=1), axis=0)
    W = W.where(np.isfinite(W), 1.0 / len(eq_list)).to_numpy()
    for _ in range(20):
        W = np.clip(W, lo, hi)
        W = W / W.sum(axis=1, keepdims=True)
    df = pd.DataFrame(W, index=pd.Index(dts[1:].date))
    dvals = pd.Series(ts.date).to_numpy()
    mapped = df.reindex(pd.Index(dvals)).to_numpy().copy()
    bad = ~np.isfinite(mapped).all(axis=1)
    mapped[bad] = 1.0 / len(eq_list)
    return mapped


def metrics(eq, tsx):
    rets = np.diff(eq) / eq[:-1]
    years = (tsx[-1] - tsx[0]).total_seconds() / (365.25 * 86400)
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0),
        "total_return": float(eq[-1] / eq[0] - 1.0),
        "max_drawdown": float(-(eq / np.maximum.accumulate(eq) - 1.0).min()),
        "volatility": float(np.std(rets) * np.sqrt(BPY)),
        "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(BPY)),
        "ending_equity": float(eq[-1]),
        "years": float(years),
    }


def cagr_dd(v, i, j):
    x = v[i:j]
    years = (j - i) / 252.0
    return (float((x[-1] / x[0]) ** (1.0 / years) - 1.0),
            float(-(x / np.maximum.accumulate(x) - 1.0).min()))


def rolling_counts(dts, deq, dtq, dw):
    ret = dd = retw = ddw = both = n = 0
    for s in pd.date_range("2017-01-03", "2023-10-01", freq="QS"):
        i = int(dts.searchsorted(s))
        j = int(dts.searchsorted(s + pd.DateOffset(years=3)))
        if i >= j or j > len(dts) or j - i < 500:
            continue
        cs, ds = cagr_dd(deq, i, j)
        cb, db = cagr_dd(dtq, i, j)
        cw, dwd = cagr_dd(dw, i, j)
        n += 1
        ret += cs > cb
        dd += ds < db
        retw += cs > cw
        ddw += ds < dwd
        both += (cs > cw) and (ds < dwd)
    return {"n": n, "ret_gt_tqqq": ret, "dd_lt_tqqq": dd,
            "ret_gt_winner": retw, "dd_lt_winner": ddw, "both_gt_winner": both}


def yearly(ts, eq, tqqq):
    out = {}
    eqs = pd.Series(eq, index=pd.DatetimeIndex(ts))
    tqs = pd.Series(tqqq, index=pd.DatetimeIndex(ts))
    for y in sorted(set(eqs.index.year)):
        e = eqs[eqs.index.year == y]
        t = tqs[tqs.index.year == y]
        if len(e) < 2:
            continue
        out[int(y)] = {"strategy": float(e.iloc[-1] / e.iloc[0] - 1.0),
                       "tqqq": float(t.iloc[-1] / t.iloc[0] - 1.0)}
    return out


def dd_episode(ts, eq):
    dd = eq / np.maximum.accumulate(eq) - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(eq[: j + 1]))
    return {"max_drawdown": float(-dd[j]), "peak": str(ts[p])[:19],
            "trough": str(ts[j])[:19]}


def main():
    t0 = time.time()
    cache = HERE / "panel_cache.npz"
    if cache.exists():
        d = np.load(cache)
        ts = pd.DatetimeIndex(pd.to_datetime(d["ts"], utc=True)
                              .tz_convert("America/New_York"))
        opens, closes = d["opens"], d["closes"]
    else:
        ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    print(f"panel {len(ts):,} bars  {ts[0]} .. {ts[-1]}  ({time.time()-t0:.0f}s)", flush=True)

    winners = load_module(
        "winner", ROOT / "research/agents/daily-regime-minute-entry/strategy.py")
    ens = load_module(
        "ensemble", ROOT / "research/agents/ensemble-signals/strategy.py")
    mom = load_module(
        "momentum", ROOT / "research/agents/intraday-momentum/strategy.py")

    w_win, diag = winners.build_weights(ts, opens.astype(float), closes.astype(float))
    w_ens = ens.build_weights(ts, opens.astype(float), closes.astype(float))
    w_mom, mom_diag = mom.build_weights(ts, opens.astype(float), closes.astype(float))
    print(f"sleeves built ({time.time()-t0:.0f}s); winner stop events "
          f"{diag['stop_events']}", flush=True)

    eq_win = fast_sim(ts, opens, closes, w_win)["equity"]
    eq_ens = fast_sim(ts, opens, closes, w_ens)["equity"]
    eq_mom = fast_sim(ts, opens, closes, w_mom)["equity"]

    a3 = inverse_vol_alloc(ts, [eq_win, eq_ens, eq_mom], IV_LB, IV_LO, IV_HI)
    w_iv3 = (a3[:, 0:1] * w_win + a3[:, 1:2] * w_ens + a3[:, 2:3] * w_mom)
    a2 = inverse_vol_alloc(ts, [eq_win, eq_mom], IV_LB, IV2_LO, IV2_HI)
    w_iv2 = a2[:, 0:1] * w_win + a2[:, 1:2] * w_mom
    w_we75 = 0.75 * w_win + 0.25 * w_ens

    # causality check: truncating inputs does not change earlier allocations
    cut = bt.start_index(ts, "2022-01-03")
    eqt = {k: fast_sim(ts[:cut], opens[:cut], closes[:cut], w[:cut])["equity"]
           for k, w in (("w", w_win), ("e", w_ens), ("m", w_mom))}
    a3c = inverse_vol_alloc(ts[:cut], [eqt["w"], eqt["e"], eqt["m"]],
                            IV_LB, IV_LO, IV_HI)
    causal_diff = float(np.max(np.abs(a3c - a3[:cut])))

    # small neighbouring-parameter check for the allocation (1 bp only)
    plateau = {}
    for lb in (10, 15, 20, 30, 40, 60):
        for tag, lo, hi in (("IV3", IV_LO, IV_HI), ("IV2", IV2_LO, IV2_HI)):
            aa = inverse_vol_alloc(ts, ([eq_win, eq_ens, eq_mom] if tag == "IV3"
                                        else [eq_win, eq_mom]), lb, lo, hi)
            ww = (aa[:, 0:1] * w_win + aa[:, 1:2] * w_ens + aa[:, 2:3] * w_mom
                  if tag == "IV3" else aa[:, 0:1] * w_win + aa[:, 1:2] * w_mom)
            row = {}
            for lab in ("10y", "5y"):
                j0 = bt.start_index(ts, START10 if lab == "10y" else START5)
                f = fast_sim(ts[j0:], opens[j0:], closes[j0:], ww[j0:], 1.0)
                m = metrics(f["equity"], ts[j0:])
                row[lab] = [round(m["cagr"], 4), round(m["max_drawdown"], 4)]
            plateau[f"{tag}_lb{lb}"] = row
    for tag, lo, hi in (("c10_70", 0.10, 0.70), ("c20_60", 0.20, 0.60),
                        ("c25_55", 0.25, 0.55)):
        aa = inverse_vol_alloc(ts, [eq_win, eq_ens, eq_mom], IV_LB, lo, hi)
        ww = aa[:, 0:1] * w_win + aa[:, 1:2] * w_ens + aa[:, 2:3] * w_mom
        row = {}
        for lab in ("10y", "5y"):
            j0 = bt.start_index(ts, START10 if lab == "10y" else START5)
            f = fast_sim(ts[j0:], opens[j0:], closes[j0:], ww[j0:], 1.0)
            m = metrics(f["equity"], ts[j0:])
            row[lab] = [round(m["cagr"], 4), round(m["max_drawdown"], 4)]
        plateau[f"IV3_{tag}"] = row

    blends = {"IV3": w_iv3, "IV2": w_iv2, "WE75": w_we75}
    bench_w = {"winner": w_win, "ensemble": w_ens, "momentum": w_mom}

    out = {
        "agent": "round2-agent11-winner-ensemble-blend",
        "generated": time.strftime("%Y-%m-%d"),
        "primary": "WE75",
        "rules": {
            "sleeves": {
                "winner": "QQQ 165d SMA regime + armed 4% intraday stop, 100% TQQQ/BIL",
                "ensemble": "trend + 20d vol budget + 1m crash vote, 100% TQQQ/BIL",
                "momentum": "overnight drift + first-hour QQQ momentum, 100% TQQQ/BIL",
            },
            "allocation": (
                f"inverse trailing {IV_LB}d realised vol of each sleeve's standalone "
                f"daily equity (shifted 1 day), clipped [{IV_LO},{IV_HI}], renormalised"
            ),
            "blend": "portfolio target = sum(alloc_j * sleeve_j target weights)",
            "fills": "next bar open, 2% band, long-only, weights sum to 1",
        },
        "parameters": {"iv_lookback": IV_LB, "iv_clip": [IV_LO, IV_HI],
                       "iv2_clip": [IV2_LO, IV2_HI], "band": BAND},
        "alloc_means": {
            "IV3_winner_ensemble_momentum": [float(x) for x in a3.mean(axis=0)],
            "IV2_winner_momentum": [float(x) for x in a2.mean(axis=0)],
        },
        "causality_max_alloc_diff": causal_diff,
        "allocation_plateau_1bp": plateau,
        "windows": {},
        "benchmarks": {},
    }

    i0 = {"10y": bt.start_index(ts, START10), "5y": bt.start_index(ts, START5)}
    tsx = {k: ts[v:] for k, v in i0.items()}

    for name, w in {**blends, **bench_w}.items():
        out["windows"][name] = {}
        print(f"\n{name}", flush=True)
        for lab in ("10y", "5y"):
            j0 = i0[lab]
            block = {}
            for slip in SLIPS:
                f = fast_sim(tsx[lab], opens[j0:], closes[j0:], w[j0:],
                             slippage_bps=slip)
                m = metrics(f["equity"], tsx[lab])
                m["fills"] = f["fills"]
                m["turnover"] = float(f["turnover"])
                m["mean_risky_weight"] = float((w[j0:, 0] + w[j0:, 1]).mean())
                block[f"{slip:g}bp"] = m
                if slip == 1.0:
                    block["yearly"] = yearly(tsx[lab], f["equity"], closes[j0:, 1])
                    block["dd_episode"] = dd_episode(tsx[lab], f["equity"])
                    dts, deq = daily_series(tsx[lab], f["equity"])
                    _, dtq = daily_series(tsx[lab], closes[j0:, 1])
                    winr = fast_sim(tsx[lab], opens[j0:], closes[j0:],
                                    w_win[j0:])["equity"]
                    _, dw = daily_series(tsx[lab], winr)
                    block["rolling_3y"] = rolling_counts(dts, deq, dtq, dw)
                    out["windows"][name][lab] = block
            a = block["1bp"]
            print(f"  {lab}  1bp CAGR {a['cagr']*100:6.2f}%  DD {a['max_drawdown']*100:5.2f}%  "
                  f"Sharpe {a['sharpe']:4.2f}  fills {a['fills']}  "
                  f"5bp {block['5bp']['cagr']*100:6.2f}/{block['5bp']['max_drawdown']*100:5.2f}  "
                  f"10bp {block['10bp']['cagr']*100:6.2f}/{block['10bp']['max_drawdown']*100:5.2f}",
                  flush=True)
    out["benchmarks"] = {
        "tqqq": {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
                 "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}},
        "winner_published": {"10y": {"1bp": [0.5880, 0.4456], "5bp": [0.5460, 0.4708],
                                     "10bp": [0.4950, 0.5006]},
                             "5y": {"1bp": [0.4988, 0.3349], "5bp": [0.4589, 0.3413],
                                    "10bp": [0.4105, 0.3493]}},
    }

    # pass/fail
    pf = {}
    tq = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
    for name in ("IV3", "IV2", "WE75"):
        pf[name] = {}
        for lab in ("10y", "5y"):
            b = out["windows"][name][lab]
            a1 = b["1bp"]
            cw, dw = out["windows"]["winner"][lab]["1bp"]["cagr"], \
                out["windows"]["winner"][lab]["1bp"]["max_drawdown"]
            pf[name][lab] = {
                "cagr_1bp": a1["cagr"], "dd_1bp": a1["max_drawdown"],
                "beats_tqqq_1bp": bool(a1["cagr"] > tq[lab][0] and a1["max_drawdown"] < tq[lab][1]),
                "beats_tqqq_5bp": bool(b["5bp"]["cagr"] > tq[lab][0]
                                       and b["5bp"]["max_drawdown"] < tq[lab][1]),
                "beats_tqqq_10bp": bool(b["10bp"]["cagr"] > tq[lab][0]
                                        and b["10bp"]["max_drawdown"] < tq[lab][1]),
                "cagr_vs_winner_pp": (a1["cagr"] - cw) * 100,
                "dd_vs_winner_pp": (a1["max_drawdown"] - dw) * 100,
                "strict_dominance_1bp": bool(a1["cagr"] > cw
                                             and a1["max_drawdown"] < dw),
                "criterion2_1bp": bool(a1["max_drawdown"] < dw
                                       and a1["cagr"] > cw - 0.02),
            }
    out["pass_fail"] = pf

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {HERE/'result.json'}  ({time.time()-t0:.0f}s)")
    print(json.dumps({k: {w: {kk: (round(vv, 4) if isinstance(vv, float) else vv)
                              for kk, vv in d.items() if kk in
                              ('cagr_1bp', 'dd_1bp', 'strict_dominance_1bp',
                               'criterion2_1bp', 'beats_tqqq_10bp')}
                          for w, d in v.items()} for k, v in pf.items()}, indent=1))


if __name__ == "__main__":
    main()
