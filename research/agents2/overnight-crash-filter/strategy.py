"""First-hour gated TQQQ with a 165-day regime, a 20-day volatility crash
filter and a 4% intraday stop.  Long-only, 1-minute execution, next-open fills.

Rules
-----
Universe: QQQ (signal), TQQQ (risk asset), BIL (risk-off asset).

1. Regime (daily, 2% hysteresis band).  Let S = 165-day SMA of QQQ daily
   closes through day d-1 and C = QQQ close of day d-1.  The state is ON if
   C > 1.02*S, OFF if C < 0.98*S, otherwise it keeps its previous value.
   The state for day d is therefore known at the previous close.

2. Overnight + first hour.  When the regime is ON, buy TQQQ at the 15:59
   open (decision on the 15:58 bar) and hold it through the next session's
   first hour, i.e. to the 10:30 open.

3. Crash filter.  Skip the overnight entry when QQQ's 20-day realised
   volatility of daily log returns (annualised, through the previous close)
   is above 35%.  While skipped the account holds BIL.

4. Afternoon.  At 10:29 compute the QQQ first-hour return
   r60 = QQQ(10:29) / QQQ(09:30) - 1.  If r60 >= -0.5% and the regime is ON,
   hold TQQQ from the 10:30 open to the 15:59 open; otherwise hold cash
   (risk-off days hold BIL).

5. Intraday stop.  While long TQQQ, if TQQQ trades 4% below the session open,
   sell at the next minute's open and stay out for the rest of the session.
   The overnight leg is re-entered at 15:59 if the regime is still ON.

6. Risk-off.  100% BIL.

Fills: a weight set at bar i is executed at the open of bar i+1.  Costs are
charged on traded notional (1 bp primary, 5 / 10 bp reported).

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/overnight-crash-filter/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

SMA_N = 165
BAND = 0.02
MORNING_MIN = 60          # hold the first hour past the open
VOL_WIN = 20
VOL_MAX = 0.35            # annualised QQQ 20d vol crash filter
STOP = 0.04
SIGNAL_THR = -0.005
BARS_PER_YEAR = 252 * 390
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"


def build_weights(ts, opens, closes):
    """Explicit implementation of rules 1-6 (positions -> harness weights)."""
    d = lab.Days(ts, opens, closes)
    qc, qo = closes[:, 0], opens[:, 0]
    tc = closes[:, 1]
    tq_o = opens[:, 1]

    # --- regime with hysteresis, using closes through the prior day ---------
    sma = pd.Series(d.dclose[:, 0]).rolling(SMA_N).mean().to_numpy()
    gate = np.zeros(d.nd, bool)
    state = False
    for k in range(1, d.nd):
        if not np.isfinite(sma[k - 1]):
            state = False
        elif d.dclose[k - 1, 0] > sma[k - 1] * (1 + BAND):
            state = True
        elif d.dclose[k - 1, 0] < sma[k - 1] * (1 - BAND):
            state = False
        gate[k] = state

    # --- 20d realised vol, through the prior close ------------------------
    vol = d.vol(VOL_WIN, 0, ann=True)

    p_t = np.zeros(len(ts))   # TQQQ position held during bar i
    p_b = np.zeros(len(ts))   # BIL position held during bar i
    for k in range(d.nd):
        f, l = d.first[k], d.last[k]
        g = bool(gate[k])
        overnight_ok = bool(gate[k])
        if np.isfinite(vol[k]) and vol[k] > VOL_MAX:
            overnight_ok = False
        # continuation of last night's trade: hold the first hour
        held = bool(k > 0 and gate[k - 1]
                    and not (np.isfinite(vol[k - 1]) and vol[k - 1] > VOL_MAX))
        exit_at = f + MORNING_MIN
        if held:
            # 4% stop from the session open inside the morning block
            base = tq_o[f]
            for i in range(f, min(exit_at, l + 1)):
                if tc[i] < base * (1.0 - STOP):
                    exit_at = i + 1
                    break
            p_t[f:min(exit_at, l + 1)] = 1.0
        # afternoon
        a_start = min(f + MORNING_MIN, l + 1)
        a_end = l
        if g and a_start < l:
            r60 = qc[a_start - 1] / qo[f] - 1.0
            if r60 >= SIGNAL_THR:
                base = tq_o[f]
                for i in range(a_start, l + 1):
                    if tc[i] < base * (1.0 - STOP):
                        a_end = i + 1
                        break
                p_t[a_start:a_end] = 1.0
        # risk-off asset
        if not g:
            p_b[(exit_at if held else f):l + 1] = 1.0
        # overnight entry at 15:59
        if overnight_ok:
            p_t[l] = 1.0
            p_b[l] = 0.0
        else:
            p_t[l] = 0.0
            p_b[l] = 1.0

    w = np.zeros((len(ts), 3))
    w[:-1, 1] = p_t[1:]
    w[:-1, 2] = p_b[1:]
    w[-1, 1] = p_t[-1]
    w[-1, 2] = p_b[-1]
    return w


def window(ts, opens, closes, w, start, slip):
    r = lab.run_window(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = lab.stats(r)
    i = bt.start_index(ts, start)
    b = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR)
    return s, b, r


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    w = build_weights(ts, o, c)

    # equivalence with the shared builder used for the research grids
    d = lab.Days(ts, o, c)
    w_ref = lab.build_weights(d, base="signal", m=MORNING_MIN, gate=d.gate(band=BAND),
                              vol_max=VOL_MAX, stop=STOP, signal_thr=SIGNAL_THR)
    assert np.array_equal(w, w_ref), "explicit rules diverge from lab.build_weights"
    print("weights match lab.build_weights exactly")

    out = {"strategy": "overnight-crash-filter / first-hour hybrid",
           "parameters": dict(sma=SMA_N, band=BAND, morning_min=MORNING_MIN,
                              vol_win=VOL_WIN, vol_max=VOL_MAX, stop=STOP,
                              signal_thr=SIGNAL_THR),
           "windows": {}}
    print(f"\n{'window':6s} {'cost':>5s} {'CAGR':>8s} {'maxDD':>7s} {'Sharpe':>7s} "
          f"{'vol':>7s} {'fills':>7s} {'end $':>14s}")
    for tag, start in (("10y", START10), ("5y", START5)):
        out["windows"][tag] = {}
        for slip in (0.0, 1.0, 5.0, 10.0):
            s, b, r = window(ts, o, c, w, start, slip)
            out["windows"][tag][f"{slip:.0f}bp"] = {
                "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                "sharpe": s["sharpe"], "volatility": s["volatility"],
                "fills": s["fills"], "turnover": s["turnover"],
                "ending_equity": s["ending_equity"],
            }
            print(f"{tag:6s} {slip:4.0f}bp {s['cagr']*100:7.2f}% {s['max_drawdown']*100:6.2f}% "
                  f"{s['sharpe']:7.2f} {s['volatility']*100:6.2f}% {s['fills']:7,d} "
                  f"${s['ending_equity']:13,.0f}")
    (HERE / "strategy_result.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nwrote", HERE / "strategy_result.json")


if __name__ == "__main__":
    main()
