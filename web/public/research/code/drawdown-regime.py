"""Drawdown-based regime overlay on the round-1 winner (TQQQ / QQQ / BIL).

Base strategy (round-1 winner, reproduced exactly)
--------------------------------------------------
1. QQQ daily close > 165-day SMA  -> risk-on for the next session.
2. Risk-on: hold 100% TQQQ, including overnight.
3. Intraday stop, only when armed (QQQ's first-minute price < 20-day SMA
   through the prior close, times 1.01): if TQQQ trades 4% below the session
   open, sell at the next minute's open and hold BIL for the rest of the day
   and the following night. Re-enter next session if the regime is still on.

Drawdown overlay (this agent)
-----------------------------
dd(t) = QQQ_close(t-1) / max(QQQ_close, t-252 .. t-1) - 1

The drawdown is known before the open (it uses closes through t-1 only), so it
can be applied to session t with no look-ahead.  Variants tested:

  dd05_bil / dd10_bil / dd15_bil
      full exit to BIL while dd <= -5% / -10% / -15%; re-enter when the
      drawdown recovers to -2% / -5% / -10%.
  dd05_half / dd10_half
      the same but only half the book moves to BIL.
  uw120_bil
      full exit to BIL after 120 sessions underwater (no new 52-week high).
  dd08_qqq
      de-lever from TQQQ (beta 3) to QQQ (beta 1) while dd <= -8%.
  dd08_stop2
      keep TQQQ, but halve the minute stop from 4% to 2% while dd <= -8%.
  dd08_stop2_75
      dd08_stop2 with 25% of the book in BIL while dd <= -8%.

All fills are at the next bar's open; slippage is charged on traded notional;
weights are long-only and sum to <= 1.  The core `research/bt.py` is imported
only for stats/benchmark helpers and is never modified.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/drawdown-regime/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ddlib as L
import fastsim

OUT = HERE


# ------------------------------------------------------------------ builds
def cond_stop(ts, opens, closes, dctx, dd_thr, stop2, base_stop=0.04, scale2=1.0):
    """Winner stop, tighter (and optionally smaller) while dd <= -dd_thr."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    nstops = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        deep = dctx["dd_prev"][k] <= -dd_thr
        stop = stop2 if deep else base_stop
        sc = scale2 if deep else 1.0
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
                nstops += 1
            hold[i] = sc if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w, nstops


def delever(ts, opens, closes, dctx, exit_thr, reenter_thr, qqq_frac=1.0):
    """Hold QQQ instead of TQQQ while the drawdown is deeper than exit_thr."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold_t = np.zeros(n)
    hold_q = np.zeros(n)
    blocked = False
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            blocked = False
            continue
        if blocked:
            if dctx["dd_prev"][k] >= -reenter_thr:
                blocked = False
        elif dctx["dd_prev"][k] <= -exit_thr:
            blocked = True
        if blocked:
            hold_q[f:l + 1] = qqq_frac
            continue
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * 0.96:
                on = False
            hold_t[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 0] = hold_q
    w[:, 1] = hold_t
    w[:, 2] = 1 - hold_q - hold_t
    return w


def build_variants(ts, opens, closes, dctx):
    n = dctx["n"]
    v = {}
    v["winner"] = dict(
        rules="165d SMA QQQ regime + 4% minute stop armed by QQQ<MA20*1.01",
        w=L.render(ts, opens, closes, dctx, np.ones(n))[0])
    for name, thr, rec, sc in (
        ("dd05_bil", 0.05, 0.02, 0.0),
        ("dd10_bil", 0.10, 0.05, 0.0),
        ("dd15_bil", 0.15, 0.10, 0.0),
        ("dd05_half", 0.05, 0.02, 0.5),
        ("dd10_half", 0.10, 0.05, 0.5),
    ):
        v[name] = dict(
            rules=f"winner + {'BIL' if sc == 0 else 'half BIL'} while QQQ <= "
                  f"-{thr:.0%} below 52w high; re-enter at -{rec:.0%}",
            w=L.render(ts, opens, closes, dctx, L.dd_state(dctx, thr, rec, scale=sc))[0])
    v["uw120_bil"] = dict(
        rules="winner + full BIL while underwater sessions since 52w high >= 120",
        w=L.render(ts, opens, closes, dctx,
                   L.dd_state(dctx, 120, 10, scale=0.0, kind="uw"))[0])
    v["dd08_qqq"] = dict(
        rules="winner but 100% QQQ while QQQ <= -8% below 52w high; re-enter at -4%",
        w=delever(ts, opens, closes, dctx, 0.08, 0.04))
    w6, st6 = cond_stop(ts, opens, closes, dctx, 0.08, 0.02)
    v["dd08_stop2"] = dict(
        rules="winner but 2% minute stop (instead of 4%) while QQQ <= -8% below 52w high",
        w=w6, stop_events=st6)
    w7, _ = cond_stop(ts, opens, closes, dctx, 0.08, 0.02, scale2=0.75)
    v["dd08_stop2_75"] = dict(
        rules="dd08_stop2 plus 25% BIL while QQQ <= -8% below 52w high",
        w=w7, stop_events=st6)
    return v


# ----------------------------------------------------------------- metrics
def metrics(ts, opens, closes, w, bp, idx):
    out = {}
    for start, j in ((L.START10, idx["j10"]), (L.START5, idx["j5"])):
        r = fastsim.simulate(ts[j:], opens[j:], closes[j:], w[j:], band=0.02,
                             slippage_bps=bp)
        s = L.bt.stats(r, L.BARS_PER_YEAR)
        eq = r["equity"]
        peak = np.maximum.accumulate(eq)
        k = int(np.argmin(eq / peak - 1))
        p = int(np.argmax(eq[: k + 1]))
        s["dd_peak"] = str(r["ts"][p])
        s["dd_trough"] = str(r["ts"][k])
        s["bench"] = L.bt.benchmark(closes[j:, 1], ts[j:], L.BARS_PER_YEAR)
        s["yearly"] = {str(y): val for y, val in
                       L.bt.yearly(ts[j:], eq, closes[j:, 1]).items()}
        yarr = idx["y10"] if start == L.START10 else idx["y5"]
        ydd = {}
        for y in np.unique(yarr):
            e = eq[yarr == y]
            ydd[str(int(y))] = float(-(e / np.maximum.accumulate(e) - 1).min())
        s["yearly_dd"] = ydd
        out[start] = s
    return out


def forward_table(dctx, closes):
    first, last = dctx["first"], dctx["last"]
    tq, qq = closes[last, 1], closes[last, 0]
    dd, reg = dctx["dd_prev"], dctx["reg"]
    rows = []
    for name, lo, hi in (("0..-3%", 0.0, -0.03), ("-3..-5%", -0.03, -0.05),
                         ("-5..-8%", -0.05, -0.08), ("-8..-12%", -0.08, -0.12),
                         ("-12..-20%", -0.12, -0.20), ("<=-20%", -0.20, -1.0)):
        m = reg & (dd <= lo) & (dd > hi)
        idx = np.flatnonzero(m)
        r5 = np.array([tq[k + 5] / tq[k] - 1 for k in idx if k + 5 < len(tq)])
        r20 = np.array([tq[k + 20] / tq[k] - 1 for k in idx if k + 20 < len(tq)])
        q20 = np.array([qq[k + 20] / qq[k] - 1 for k in idx if k + 20 < len(qq)])
        rows.append(dict(bucket=name, n=int(len(idx)),
                         fwd5=float(r5.mean()), fwd5_hit=float((r5 > 0).mean()),
                         fwd20=float(r20.mean()), fwd20_hit=float((r20 > 0).mean()),
                         qqq20=float(q20.mean())))
    return rows


def block_bootstrap_p(d, block=20, n_boot=4000, seed=7):
    rng = np.random.default_rng(seed)
    d = np.asarray(d)
    n = len(d)
    nb = int(np.ceil(n / block))
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n - block, size=nb)
        sample = np.concatenate([d[s:s + block] for s in starts])[:n]
        means[b] = sample.mean()
    return float((means <= 0).mean()), float(means.std())


def check_no_lookahead(dctx):
    """Assert that dd_prev and reg at session k use only closes through k-1."""
    dc = dctx["dclose"]
    k = len(dc) - 1
    hi = dc[max(0, k - 252):k].max()
    assert abs(dctx["dd_prev"][k] - (dc[k - 1] / hi - 1)) < 1e-12
    sma_prev = dc[max(0, k - 165):k].mean()
    assert dctx["reg"][k] == (dc[k - 1] > sma_prev)
    return True


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)
    assert check_no_lookahead(dctx)
    j10 = L.bt.start_index(ts, L.START10)
    j5 = L.bt.start_index(ts, L.START5)
    idx = {"j10": j10, "j5": j5,
           "y10": np.array([t.year for t in ts[j10:]]),
           "y5": np.array([t.year for t in ts[j5:]])}
    print(f"panel {len(ts):,} bars, {dctx['n']} sessions "
          f"({dctx['dates'][0]} .. {dctx['dates'][-1]})", flush=True)

    variants = build_variants(ts, opens, closes, dctx)

    # significance of the best variant vs the winner (daily log-return diff)
    ea = pd.Series(fastsim.simulate(ts[j10:], opens[j10:], closes[j10:],
                                    variants["winner"]["w"][j10:], band=0.02,
                                    slippage_bps=1.0)["equity"], index=ts[j10:])
    eb = pd.Series(fastsim.simulate(ts[j10:], opens[j10:], closes[j10:],
                                    variants["dd08_stop2"]["w"][j10:], band=0.02,
                                    slippage_bps=1.0)["equity"], index=ts[j10:])
    da = np.log(ea).groupby([x.date() for x in ea.index]).last().diff().dropna()
    db = np.log(eb).groupby([x.date() for x in eb.index]).last().diff().dropna()
    d = (db - da).to_numpy()
    pval, boot_sd = block_bootstrap_p(d)

    res = {
        "agent": "drawdown-regime",
        "date": "2026-11-25",
        "data": {"symbols": ["QQQ", "TQQQ", "BIL"], "frequency": "1min",
                 "source": "data/intraday-hf (local adjusted)",
                 "warmup_start": str(dctx["dates"][0]),
                 "test_end": str(dctx["dates"][-1]),
                 "sessions": int(dctx["n"])},
        "definition": {
            "dd": "QQQ close(t-1) / max(QQQ close, t-252..t-1) - 1; known before the open",
            "regime": "QQQ close(t-1) > 165-day SMA of QQQ closes",
            "stop": "TQQQ 4% below session open when armed (QQQ first minute < MA20*1.01); fill next minute open; out rest of day + night",
            "fills": "next bar open", "band": 0.02,
            "no_lookahead_check": "passed",
        },
        "significance": {
            "variant": "dd08_stop2",
            "daily_log_diff_sum_pp": float(d.sum() * 100),
            "mean_bp_per_day": float(d.mean() * 1e4),
            "block_bootstrap_sd_bp": float(boot_sd * 1e4),
            "p_value_one_sided": pval, "block_days": 20,
        },
        "forward_returns": forward_table(dctx, closes),
        "variants": {},
    }

    for name, v in variants.items():
        entry = {"rules": v["rules"], "costs": {}}
        if "stop_events" in v:
            entry["stop_events"] = int(v["stop_events"])
        for bp in (1.0, 5.0, 10.0):
            m = metrics(ts, opens, closes, v["w"], bp, idx)
            if bp == 1.0:
                yearly = {k: {"strategy": val["strategy"], "benchmark": val["benchmark"]}
                          for k, val in m[L.START10]["yearly"].items()}
                yearly_dd = m[L.START10]["yearly_dd"]
            entry["costs"][f"{bp:.0f}bp"] = {
                "10y": {k: m[L.START10][k] for k in
                        ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
                         "fills", "turnover", "ending_equity", "dd_peak", "dd_trough")},
                "5y": {k: m[L.START5][k] for k in
                       ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
                        "fills", "turnover", "ending_equity", "dd_peak", "dd_trough")},
            }
        entry["yearly"] = yearly
        entry["yearly_dd"] = yearly_dd
        if name in ("winner", "dd10_bil", "dd05_bil", "dd08_stop2", "dd08_stop2_75"):
            r3 = L.rolling3y(ts, opens, closes, v["w"])
            entry["rolling3y"] = {
                "n": len(r3),
                "beat_tqqq_cagr_and_dd": int(sum(
                    1 for x in r3 if x["cagr"] > x["bcagr"] and x["dd"] < x["bdd"])),
                "median_cagr": float(np.median([x["cagr"] for x in r3])),
                "worst_dd": float(max(x["dd"] for x in r3)),
                "windows": r3,
            }
        res["variants"][name] = entry
        c = entry["costs"]["1bp"]
        print(f"{name:16s} 10y {c['10y']['cagr']*100:6.2f}/{c['10y']['max_drawdown']*100:5.2f}"
              f"  5y {c['5y']['cagr']*100:6.2f}/{c['5y']['max_drawdown']*100:5.2f}",
              flush=True)

    res["tqqq_buy_hold"] = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
                            "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}
    res["winner_reference"] = {
        "10y": {"cagr": 0.5880, "max_drawdown": 0.4456},
        "5y": {"cagr": 0.4988, "max_drawdown": 0.3349},
        "5bp": {"10y": [0.5460, 0.4708], "5y": [0.4589, 0.3413]},
        "10bp": {"10y": [0.4950, 0.5006], "5y": [0.4105, 0.3493]},
    }

    for name, e in res["variants"].items():
        flags = {}
        for bp in ("1bp", "5bp", "10bp"):
            c = e["costs"][bp]
            w = res["variants"]["winner"]["costs"][bp]
            flags[bp] = {
                "beat_tqqq": bool(c["10y"]["cagr"] > 0.3928
                                  and c["10y"]["max_drawdown"] < 0.8168
                                  and c["5y"]["cagr"] > 0.1347
                                  and c["5y"]["max_drawdown"] < 0.8168),
                "strict_dominance_vs_winner": bool(
                    c["10y"]["cagr"] > w["10y"]["cagr"]
                    and c["10y"]["max_drawdown"] < w["10y"]["max_drawdown"]
                    and c["5y"]["cagr"] > w["5y"]["cagr"]
                    and c["5y"]["max_drawdown"] < w["5y"]["max_drawdown"]),
                "lower_dd_and_cagr_within_2pp": bool(
                    c["10y"]["max_drawdown"] < w["10y"]["max_drawdown"]
                    and c["5y"]["max_drawdown"] < w["5y"]["max_drawdown"]
                    and c["10y"]["cagr"] > w["10y"]["cagr"] - 0.02
                    and c["5y"]["cagr"] > w["5y"]["cagr"] - 0.02),
                "surface": "vs winner at the same cost",
            }
        e["pass"] = flags

    (OUT / "result.json").write_text(json.dumps(res, indent=2, default=float))
    print("wrote", OUT / "result.json")


if __name__ == "__main__":
    main()
