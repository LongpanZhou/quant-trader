"""Minute drawdown/stop overlay on the 165-day QQQ -> TQQQ trend.

Primary variant (v1)
--------------------
Daily regime:  hold TQQQ while QQQ's daily close is above its 165-day SMA.
Minute stop:   the 165-day SMA can be written as a threshold T_t on today's
               close: close_t > SMA165_t  <=>  close_t > mean(close_{t-164..t-1}).
               If QQQ trades at or below 0.995 * T_t intraday, sell TQQQ at the
               next minute's open and move to BIL.
Re-entry:      after a stop, buy TQQQ again only when TQQQ trades at a new
               10-day high (vs the prior 10 daily closes) while the daily
               regime is bullish.  This avoids buying the first weak bounce.
Regime exit:   if QQQ closes below its 165-day SMA, go to BIL at the next open
               (same as the daily baseline).

Alternative variants
--------------------
v2  same intraday stop, but stay in BIL until the daily regime resets
    (QQQ goes below and then back above its 165-day SMA).  Negative control.
v3  15% trailing stop from the TQQQ position peak, re-entry on a QQQ 20-day
    high.  Classic trailing stop, parameter-sensitive.
v4  smooth volatility control: TQQQ weight = min(1, 0.55 / vol20(TQQQ)),
    with the same 165-day regime filter.  Robust alternative.

All signals use data through bar i only; weights are filled at bar i+1's open
by research/bt.py.  Long-only, weights sum to <= 1.

Revision note (2026-11-26)
--------------------------
`thr_d` is already `rolling(164).mean().shift(1)`, so `thr_d[d]` is the mean of
closes d-164..d-1 and is known before day d opens.  The corrected code maps it
with `same_day(thr_d)`.  An earlier revision used `per_bar(thr_d)`, which added
a second day of lag and inflated V1 from 43.27%/45.23% (10y) and 29.46%/42.96%
(5y) to 46.89%/45.32% and 32.40%/42.96%.  The old 46.89% numbers are withdrawn;
all current results use `same_day`.

Run:
    cd C:\\Users\\27175\\Desktop\\quant-trader-research
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents/drawdown-stop-overlay/strategy.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"
BARS_PER_YEAR = 252 * 390


def build_panels():
    tsm, om, cm = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
    qqq_d, tq_d = cd[:, 0], cd[:, 1]

    sma165 = pd.Series(qqq_d).rolling(165).mean().to_numpy()
    regime_d = np.zeros(len(tsd), dtype=bool)
    ok = np.isfinite(sma165)
    regime_d[ok] = qqq_d[ok] > sma165[ok]

    # Threshold on today's close: close > rolling164_mean_shifted1 <-> close > SMA165.
    thr_d = pd.Series(qqq_d).rolling(164).mean().shift(1).to_numpy()
    hi10t_d = pd.Series(tq_d).rolling(10).max().to_numpy()
    hi20q_d = pd.Series(qqq_d).rolling(20).max().to_numpy()
    vol20_d = pd.Series(tq_d).pct_change().rolling(20).std().to_numpy() * np.sqrt(252)

    mdates = pd.DatetimeIndex(tsm).tz_convert("America/New_York").normalize().tz_localize(None)
    ddates = pd.DatetimeIndex(tsd).tz_localize(None).normalize()
    day_idx = np.searchsorted(ddates, mdates)
    is_last = np.r_[day_idx[1:] != day_idx[:-1], True]
    prev = day_idx - 1
    valid = prev >= 0

    def per_bar(arr):
        out = np.full(len(tsm), np.nan)
        out[valid] = arr[prev[valid]]
        return out

    def same_day(arr):
        # For arrays already built only from earlier sessions (e.g. thr_d is
        # shifted by one), so day d's value is known before day d opens.
        return arr[day_idx]

    return dict(
        tsm=tsm, om=om, cm=cm, tsd=tsd, cd=cd,
        qqq_m=cm[:, 0], tq_m=cm[:, 1],
        day_idx=day_idx, is_last=is_last, regime_d=regime_d,
        # thr_d is already shifted by one session: same_day gives today's exact
        # SMA threshold, known before the open. per_bar would add a second day
        # of lag and inflate the backtest.
        thr_m=same_day(thr_d), hi10t_m=per_bar(hi10t_d),
        hi20q_m=per_bar(hi20q_d), vol20_d=vol20_d,
    )


def regime_at(P, i: int) -> bool:
    """Daily regime known at bar i: at 15:59 use today's close, else yesterday's."""
    d = P["day_idx"][i]
    if P["is_last"][i]:
        return bool(P["regime_d"][d])
    return bool(d >= 1 and P["regime_d"][d - 1])


def weights_threshold_stop(P, buf: float = 0.005, sticky: bool = False) -> np.ndarray:
    n = len(P["tsm"])
    w = np.zeros((n, 3))
    pos = 0
    stopped = False
    qqq, tq = P["qqq_m"], P["tq_m"]
    thr, hi10t = P["thr_m"], P["hi10t_m"]
    for i in range(n - 1):
        if not regime_at(P, i) or not np.isfinite(thr[i]):
            tgt = 0
            stopped = False
        elif pos == 1:
            if qqq[i] <= thr[i] * (1.0 - buf):
                stopped = True
                tgt = 0
            else:
                tgt = 1
        else:
            if not stopped:
                tgt = 1
            elif sticky:
                tgt = 0
            elif tq[i] >= hi10t[i]:
                stopped = False
                tgt = 1
            else:
                tgt = 0
        w[i, 1] = float(tgt)
        w[i, 2] = 1.0 - tgt
        pos = tgt
    return w


def weights_peak_stop(P, stop: float = 0.15) -> np.ndarray:
    n = len(P["tsm"])
    w = np.zeros((n, 3))
    pos = 0
    stopped = False
    peak = 0.0
    tq, qqq, hi20q = P["tq_m"], P["qqq_m"], P["hi20q_m"]
    for i in range(n - 1):
        if not regime_at(P, i):
            tgt = 0
            stopped = False
        elif pos == 1:
            if tq[i] <= peak * (1.0 - stop):
                stopped = True
                tgt = 0
            else:
                tgt = 1
        else:
            if not stopped:
                tgt = 1
                peak = tq[i]
            elif qqq[i] >= hi20q[i]:
                stopped = False
                tgt = 1
                peak = tq[i]
            else:
                tgt = 0
        w[i, 1] = float(tgt)
        w[i, 2] = 1.0 - tgt
        pos = tgt
        if pos == 1:
            peak = max(peak, tq[i])
    return w


def weights_vol_target(P, target: float = 0.55) -> np.ndarray:
    n = len(P["tsm"])
    d = P["day_idx"]
    vol = P["vol20_d"]
    wt_d = np.clip(target / vol, 0.0, 1.0)
    wt_d = np.where(P["regime_d"], wt_d, 0.0)
    wt_d = np.nan_to_num(wt_d)
    w = np.zeros((n, 3))
    for i in range(n - 1):
        day = d[i]
        if P["is_last"][i]:
            tgt = wt_d[day]           # set at today's close, fills next open
        else:
            tgt = wt_d[day - 1] if day >= 1 else 0.0
        w[i, 1] = tgt
        w[i, 2] = 1.0 - tgt
    return w


def weights_baseline(P) -> np.ndarray:
    n = len(P["tsm"])
    w = np.zeros((n, 3))
    for i in range(n - 1):
        regime = regime_at(P, i)
        w[i, 1] = 1.0 if regime else 0.0
        w[i, 2] = 0.0 if regime else 1.0
    return w


def evaluate(P, w, start: str, slippage_bps: float):
    r = bt.run(P["tsm"], P["om"], P["cm"], w, start, band=0.02, slippage_bps=slippage_bps)
    s = bt.stats(r, BARS_PER_YEAR)
    df = pd.DataFrame({"ts": r["ts"], "eq": r["equity"]})
    daily_close = df.groupby(df.ts.dt.date)["eq"].last()
    s["daily_close_dd"] = float(-(daily_close / daily_close.cummax() - 1.0).min())
    eq = r["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    s["dd_date"] = str(r["ts"][int(np.argmin(dd))])
    i0 = bt.start_index(P["tsm"], start)
    s["yearly"] = {
        int(y): {
            "strategy": round(float(v["strategy"]), 4),
            "tqqq": round(float(v["benchmark"]), 4),
        }
        for y, v in bt.yearly(r["ts"], eq, P["cm"][i0:, 1]).items()
    }
    # per-year max drawdown within the year (strategy)
    s["yearly_dd"] = {}
    for y in sorted(set(r["ts"].year)):
        mask = r["ts"].year == y
        e = eq[mask]
        pk = np.maximum.accumulate(e)
        s["yearly_dd"][int(y)] = round(float(-(e / pk - 1.0).min()), 4)
    return s, r


def main() -> None:
    P = build_panels()

    variants = {
        "baseline": weights_baseline(P),
        "v1_threshold_stop_10dhigh": weights_threshold_stop(P, 0.005, sticky=False),
        "v2_threshold_stop_sticky": weights_threshold_stop(P, 0.005, sticky=True),
        "v3_peak_stop_15_qqq20high": weights_peak_stop(P, 0.15),
        "v4_vol_target_55": weights_vol_target(P, 0.55),
    }

    out = {}
    for name, w in variants.items():
        out[name] = {}
        for start in (START10, START5):
            out[name][start] = {}
            for slip in (1.0, 5.0):
                s, _ = evaluate(P, w, start, slip)
                out[name][start][f"{slip:g}bp"] = s
            print(f"\n{name} | {start}")
            s = out[name][start]["1bp"]
            s5 = out[name][start]["5bp"]
            print(
                f"  1bp CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
                f"dailyDD {s['daily_close_dd']*100:5.2f}%  Sharpe {s['sharpe']:.3f}  "
                f"Sortino {s['sortino']:.3f}  vol {s['volatility']*100:.1f}%  "
                f"fills {s['fills']}  turnover {s['turnover']:.0f}x  "
                f"end ${s['ending_equity']:,.0f}  DDdate {s['dd_date'][:10]}"
            )
            print(
                f"  5bp CAGR {s5['cagr']*100:6.2f}%  DD {s5['max_drawdown']*100:5.2f}%  "
                f"Sharpe {s5['sharpe']:.3f}  fills {s5['fills']}"
            )
            print(
                "  yearly "
                + " ".join(
                    f"{y}:{v['strategy']*100:.1f}/{v['tqqq']*100:.1f}"
                    for y, v in s["yearly"].items()
                )
            )

    # Benchmarks: daily TQQQ, same windows.
    bench = {}
    for start in (START10, START5):
        i = bt.start_index(P["tsd"], start)
        bench[start] = bt.benchmark(P["cd"][i:, 1], P["tsd"][i:], 252)

    meta = {
        "data": "local adjusted 1-minute QQQ/TQQQ/BIL, regular session 09:30-16:00 ET",
        "window_10y": [START10, END],
        "window_5y": [START5, END],
        "fills": "next bar open, 2% band, long-only",
        "costs_bps": [1.0, 5.0],
        "benchmark_tqqq_daily": {
            k: {kk: float(vv) for kk, vv in v.items()} for k, v in bench.items()
        },
        "readme_benchmark_targets": {
            "10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
            "5y": {"cagr": 0.1347, "max_drawdown": 0.8168},
        },
        "note": "The harness 5y benchmark from the 2021-10-25 close is 13.88%; the "
        "README's 13.47% target is consistent with a pre-window (2021-10-22) "
        "starting price. Both are reported; pass/fail uses the stricter 13.47% "
        "target.",
    }

    targets = {START10: (0.3928, 0.8168), START5: (0.1347, 0.8168)}
    pass_fail = {}
    for name in variants:
        pass_fail[name] = {}
        for start, (target_cagr, target_dd) in targets.items():
            s1 = out[name][start]["1bp"]
            s5 = out[name][start]["5bp"]
            pass_fail[name][start] = {
                "target_cagr": target_cagr,
                "target_max_dd": target_dd,
                "pass_1bp": bool(
                    s1["cagr"] > target_cagr and s1["max_drawdown"] < target_dd
                ),
                "pass_5bp": bool(
                    s5["cagr"] > target_cagr and s5["max_drawdown"] < target_dd
                ),
            }

    result = {"meta": meta, "pass_fail": pass_fail, "variants": out}
    with open(HERE / "result.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"\nwrote {HERE / 'result.json'}")


if __name__ == "__main__":
    main()
