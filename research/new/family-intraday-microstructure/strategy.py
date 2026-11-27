"""Intraday microstructure: opening-drive continuation + weak-close overnight reversal.

Development window only: 2016-01-04 .. 2023-12-29.  No 2024+ data is loaded.

Signals (all causal, minute bars only):
  day sleeve A: at 09:34, gap = open(09:30)/prev close - 1 > +0.25% and
                r5 = close(09:34)/open(09:30) - 1 > 0  -> buy 09:35 open.
  day sleeve B: at 09:59, r30 = close(09:59)/open(09:30) - 1 > +0.50%
                -> buy 10:00 open.
  day exit:     close-based trailing stop, 8% below the highest close since
                entry; exit at the next bar's open.  Otherwise exit at the
                15:59 open (flat overnight).
  night sleeve: at 15:58, if the session return close(15:58)/open(09:30)-1
                < -1.0%, buy at the 15:59 open and hold to the next 09:31 open.

The flat asset is BIL in the headline; a cash-flat variant is also reported
because the BIL leg doubles the fill count.  Weights are long-only, sum <= 1.
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

START = "2016-01-04"
END = "2023-12-29"
BARS_PER_YEAR = 390 * 252
BASE_TRAIL = 0.08
BASE_NIGHT = -0.010
BASE_GAP = 0.0025
BASE_R30 = 0.005


def _sessions(ts, o, c):
    """Per-session features from the 1-minute panel.  Column 0 is TQQQ."""
    dates, first, last = bt.day_bounds(ts)
    out = []
    prev_close = None
    for i in range(len(first)):
        a, b = int(first[i]), int(last[i])
        f = {
            "date": dates[a],
            "a": a,
            "b": b,
            "n": b - a + 1,
            "gap": np.nan,
            "r5": np.nan,
            "r30": np.nan,
            "dayret": np.nan,
        }
        if b - a >= 2:
            f["dayret"] = float(c[b - 1, 0] / o[a, 0] - 1.0)
        if prev_close is not None and prev_close > 0:
            f["gap"] = float(o[a, 0] / prev_close - 1.0)
        if b - a >= 5:
            f["r5"] = float(c[a + 4, 0] / o[a, 0] - 1.0)
        if b - a >= 30:
            f["r30"] = float(c[a + 29, 0] / o[a, 0] - 1.0)
        out.append(f)
        prev_close = float(c[b, 0])
    return out


def _flags(feats, night_th, gap_th, r30_th):
    night = np.array(
        [bool(np.isfinite(f["dayret"]) and f["dayret"] < night_th) for f in feats],
        dtype=bool,
    )
    gap = np.array(
        [
            bool(
                np.isfinite(f["gap"])
                and np.isfinite(f["r5"])
                and f["gap"] > gap_th
                and f["r5"] > 0.0
            )
            for f in feats
        ],
        dtype=bool,
    )
    r30 = np.array(
        [
            bool(np.isfinite(f["r30"]) and f["r30"] > r30_th)
            for f in feats
        ],
        dtype=bool,
    )
    return night, gap, r30


def _weights(ts, o, c, feats, night, gap, r30, trail, bil):
    """Build the weight matrix from precomputed session flags."""
    n = len(ts)
    w = np.zeros((n, 2), dtype=float)
    if bil:
        w[:, 1] = 1.0
    prev_night = False
    for i, f in enumerate(feats):
        a, b = f["a"], f["b"]
        if f["n"] < 35:
            # short/half session: only the overnight exit is possible
            if prev_night:
                w[a, 0] = 1.0
                w[a, 1] = 0.0
            else:
                w[a, 0] = 0.0
                if bil:
                    w[a, 1] = 1.0
            prev_night = bool(night[i])
            w[b, 0] = 1.0 if prev_night else 0.0
            if bil:
                w[b, 1] = 0.0 if prev_night else 1.0
            continue

        # morning: carry the prior night through the 09:30 bar, then flat
        if prev_night:
            w[a, 0] = 1.0
            w[a, 1] = 0.0
        else:
            w[a, 0] = 0.0
            if bil:
                w[a, 1] = 1.0
        w[a + 1 : b, 0] = 0.0
        if bil:
            w[a + 1 : b, 1] = 1.0

        # day entry
        e = None
        if gap[i]:
            e = a + 5
        elif r30[i]:
            e = a + 30
        if e is not None and e < b - 1:
            entry = float(o[e, 0])
            peak = entry
            exit_j = b - 1
            for j in range(e, b):
                if c[j, 0] <= peak * (1.0 - trail):
                    exit_j = j
                    break
                if c[j, 0] > peak:
                    peak = float(c[j, 0])
            end = min(exit_j + 1, b)
            w[e:end, 0] = 1.0
            if bil:
                w[e:end, 1] = 0.0

        # night entry at the last bar
        if night[i]:
            w[b, 0] = 1.0
            if bil:
                w[b, 1] = 0.0
        else:
            w[b, 0] = 0.0
            if bil:
                w[b, 1] = 1.0
        prev_night = bool(night[i])
    return w


def build_weights(ts, o, c, night_th=BASE_NIGHT, gap_th=BASE_GAP,
                  r30_th=BASE_R30, trail=BASE_TRAIL, bil=True):
    """Required entry point.  o/c are the TQQQ/BIL columns (2 columns)."""
    feats = _sessions(ts, o, c)
    night, gap, r30 = _flags(feats, night_th, gap_th, r30_th)
    return _weights(ts, o, c, feats, night, gap, r30, trail, bil)


def _run(ts, o, c, w, bps):
    return bt.run(ts, o, c, w, start=START, band=0.02, slippage_bps=bps)


def _summary(result, ts, o, c):
    s = bt.stats(result, BARS_PER_YEAR)
    i = bt.start_index(ts, START)
    b = bt.benchmark(c[i:, 0], ts[i:], BARS_PER_YEAR)
    eq = result["equity"]
    rets = np.diff(eq) / eq[:-1]
    tq = np.diff(c[i:, 0]) / c[i:, 0][:-1]
    s["corr_tqqq"] = float(np.corrcoef(rets, tq)[0, 1])
    s["benchmark"] = b
    return s


def _yearly(result):
    eq = result["equity"]
    t = result["ts"]
    out = {}
    for y in range(2016, 2024):
        m = t.year == y
        e = eq[m]
        if len(e) > 1:
            out[int(y)] = float(e[-1] / e[0] - 1.0)
    return out


def _ex_year_cagr(result, year):
    eq = result["equity"]
    t = result["ts"]
    rets = np.diff(eq) / eq[:-1]
    m = t[1:].year != year
    x = rets[m]
    years = len(x) / BARS_PER_YEAR
    return float(np.prod(1.0 + x) ** (1.0 / years) - 1.0)


def _cut_tests(result):
    eq = result["equity"]
    t = result["ts"]
    rets = np.diff(eq) / eq[:-1]
    years = len(rets) / BARS_PER_YEAR
    out = {
        "ex2018_cagr": _ex_year_cagr(result, 2018),
        "ex2020_cagr": _ex_year_cagr(result, 2020),
        "ex2022_cagr": _ex_year_cagr(result, 2022),
    }
    # remove the best N days (compounded from the remaining daily returns)
    for n in (5, 10, 20):
        keep = np.ones(len(rets), dtype=bool)
        idx = np.argsort(rets)[-n:]
        keep[idx] = False
        x = rets[keep]
        yr = len(x) / BARS_PER_YEAR
        out[f"ex_best_{n}_days_cagr"] = float(np.prod(1.0 + x) ** (1.0 / yr) - 1.0)
    return out


GRID = [
    ("base", dict(night_th=BASE_NIGHT, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.08)),
    ("trail6", dict(night_th=BASE_NIGHT, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.06)),
    ("trail10", dict(night_th=BASE_NIGHT, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.10)),
    ("trail4", dict(night_th=BASE_NIGHT, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.04)),
    ("night_dr15", dict(night_th=-0.015, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.08)),
    ("night_dr05", dict(night_th=-0.005, gap_th=BASE_GAP, r30_th=BASE_R30, trail=0.08)),
    ("gap0", dict(night_th=BASE_NIGHT, gap_th=0.0, r30_th=BASE_R30, trail=0.08)),
    ("r30_065", dict(night_th=BASE_NIGHT, gap_th=BASE_GAP, r30_th=0.0065, trail=0.08)),
]


def main():
    ts, O, C = bt.panel(("QQQ", "TQQQ", "BIL"), start=START, end=END,
                        rule="1min", warmup_days=60)
    o, c = O[:, [1, 2]], C[:, [1, 2]]  # TQQQ, BIL
    _, first, _ = bt.day_bounds(ts)
    print(f"bars {len(ts):,}  sessions {len(first):,}  "
          f"{ts[0]} .. {ts[-1]}")

    feats = _sessions(ts, o, c)
    night, gap, r30 = _flags(feats, BASE_NIGHT, BASE_GAP, BASE_R30)
    print(f"signal counts: night {night.sum()}  gap {gap.sum()}  r30 {r30.sum()}  "
          f"union {int((gap | r30).sum())}")

    results = {}
    base_runs = {}
    for bil in (True, False):
        w = _weights(ts, o, c, feats, night, gap, r30, BASE_TRAIL, bil)
        label = "BIL" if bil else "cash"
        print(f"\n--- headline, flat={label} ---")
        for bps in (1.0, 5.0, 10.0):
            r = _run(ts, o, c, w, bps)
            s = _summary(r, ts, o, c)
            print(f"  {bps:4.1f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
                  f"Sharpe {s['sharpe']:5.2f}  exposure {s['exposure']*100:5.1f}%  "
                  f"fills {s['fills']:,}  corr {s['corr_tqqq']:.2f}")
            results[f"{label}_{int(bps)}bp"] = {
                k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                for k, v in s.items()
                if k != "benchmark"
            }
            results[f"{label}_{int(bps)}bp"]["benchmark"] = {
                k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                for k, v in s["benchmark"].items()
            }
            if bps == 1.0:
                base_runs[label] = r
                results[f"{label}_yearly"] = _yearly(r)
                results[f"{label}_cuts"] = _cut_tests(r)

    # grid
    print("\n--- pre-registered 8-cell grid ---")
    grid_rows = []
    for name, p in GRID:
        w = build_weights(ts, o, c, bil=True, **p)
        s1 = _summary(_run(ts, o, c, w, 1.0), ts, o, c)
        s5 = _summary(_run(ts, o, c, w, 5.0), ts, o, c)
        wc = build_weights(ts, o, c, bil=False, **p)
        c1 = _summary(_run(ts, o, c, wc, 1.0), ts, o, c)
        c5 = _summary(_run(ts, o, c, wc, 5.0), ts, o, c)
        row = {
            "cell": name,
            "params": p,
            "bil_1bp": {k: float(s1[k]) for k in ("cagr", "max_drawdown", "sharpe", "exposure", "fills")},
            "bil_5bp": {k: float(s5[k]) for k in ("cagr", "max_drawdown", "sharpe", "exposure", "fills")},
            "cash_1bp": {k: float(c1[k]) for k in ("cagr", "max_drawdown", "sharpe", "exposure", "fills")},
            "cash_5bp": {k: float(c5[k]) for k in ("cagr", "max_drawdown", "sharpe", "exposure", "fills")},
        }
        grid_rows.append(row)
        print(f"  {name:11s} BIL 1bp {s1['cagr']*100:6.2f}% / {s1['max_drawdown']*100:5.2f}% / {s1['sharpe']:4.2f}"
              f"   BIL 5bp {s5['cagr']*100:6.2f}%   cash 5bp {c5['cagr']*100:6.2f}% / {c5['max_drawdown']*100:5.2f}%")
    results["grid"] = grid_rows

    # placebo: shuffle the three signal flags independently, same counts.
    print("\n--- placebo: 200 shuffles of session flags, base mechanics, cash 1bp ---")
    rng = np.random.default_rng(20261127)
    base_cash = _summary(_run(ts, o, c, build_weights(ts, o, c, bil=False), 1.0), ts, o, c)
    placebo = []
    for _ in range(200):
        nf = rng.permutation(night)
        gf = rng.permutation(gap)
        rf = rng.permutation(r30)
        wp = _weights(ts, o, c, feats, nf, gf, rf, BASE_TRAIL, False)
        placebo.append(float(_summary(_run(ts, o, c, wp, 1.0), ts, o, c)["cagr"]))
    placebo = np.array(placebo)
    pct = float((placebo < base_cash["cagr"]).mean())
    print(f"  base {base_cash['cagr']*100:.2f}%  placebo mean {placebo.mean()*100:.2f}%  "
          f"p5 {np.percentile(placebo,5)*100:.2f}%  p95 {np.percentile(placebo,95)*100:.2f}%  "
          f"base percentile {pct*100:.1f}%")
    results["placebo"] = {
        "n": 200,
        "base_cash_1bp_cagr": float(base_cash["cagr"]),
        "mean": float(placebo.mean()),
        "p5": float(np.percentile(placebo, 5)),
        "p95": float(np.percentile(placebo, 95)),
        "max": float(placebo.max()),
        "base_percentile": pct,
    }

    # save
    results["meta"] = {
        "start": START,
        "end": END,
        "strategy": "opening-drive continuation + weak-close overnight reversal",
        "family": "intraday-microstructure",
        "base_params": {
            "night_th": BASE_NIGHT,
            "gap_th": BASE_GAP,
            "r30_th": BASE_R30,
            "trail": BASE_TRAIL,
        },
        "notes": "BIL is the headline flat asset; cash variant shown because BIL "
                 "doubles fills.  No 2024+ data loaded.",
    }
    out = Path(__file__).resolve().parent / "result.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
