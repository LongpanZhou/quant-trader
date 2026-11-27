r"""Late-rally risk-off overlay (letf-rebalance-flow), final strategy.

Promoted from scratch/final_metrics.py so the leaderboard number comes from a
runnable strategy file instead of a hand-typed entry.

Rules
-----
Base: the round-1 winner (165d QQQ SMA regime, 100% TQQQ risk-on / BIL risk-off,
4% minute stop armed when QQQ's first minute < MA20 * 1.01), built by
scratch/lib.base_winner_weights.

Overlay: on a *risk-off* session, if QQQ's 14:59 close is more than TH (1.5%) above
the prior session's close, hold 100% TQQQ from the 15:00 open to the 15:58 bar,
then return to BIL. Weights set at bar i fill at bar i+1's open (research/bt.py),
so the signal uses only the 14:59 close and earlier.

Caveat: TH was chosen from a sweep (scratch/eval.py) on the same 2017-2026 sample,
and the edge rests on ~96 events.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/agents2/letf-rebalance-flow/strategy.py
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
sys.path.insert(0, str(HERE / "scratch"))
import bt  # noqa: E402
import lib  # noqa: E402

TH = 0.015
M1459, M1558 = 329, 388  # minutes after 09:30
WINDOWS = {"10y": "2017-01-03", "5y": "2021-10-25"}
BARS = 252 * 390


def build_weights(ts, opens, closes):
    wd = lib.winner_daily(ts, opens, closes)
    n_sess = len(wd["dates"])
    starts, ends, mins = wd["starts"], wd["ends"], wd["mins"]
    base = lib.base_winner_weights(ts, wd)
    prev_c = pd.Series(wd["qclose"]).shift(1).to_numpy()
    p1459 = lib.session_series(closes[:, 0], wd["sess"], mins, n_sess, M1459)
    events = (~wd["risk_on"]) & (p1459 / prev_c - 1.0 > TH)

    w = base.copy()
    for k in np.flatnonzero(events):
        a, b = starts[k], ends[k]
        if b <= a:
            continue
        m = mins[a:b]
        sel = (m >= M1459) & (m < M1558)
        w[a:b][sel, 1] = 1.0
        w[a:b][sel, 2] = 0.0
        hit = np.flatnonzero(m == M1558)
        if len(hit):
            w[a + hit[0], 1:] = (0.0, 1.0)
            w[b - 1, 1:] = (0.0, 1.0)
    return w, base, events, wd["dates"]


def main():
    ts, opens, closes = lib.load_panel()
    w, base, events, dates = build_weights(ts, opens, closes)
    out = {
        "agent": "letf-rebalance-flow",
        "strategy": "winner + hold TQQQ 15:00-15:58 on risk-off days when QQQ 14:59 > prior close * (1+1.5%)",
        "parameters": {"threshold": TH},
        "events_since_2017": int(events[dates >= pd.Timestamp("2017-01-03", tz=dates.tz)].sum()),
        "windows": {},
        "winner_reference": {},
    }
    for label, start in WINDOWS.items():
        i = bt.start_index(ts, start)
        for key, ww in (("windows", w), ("winner_reference", base)):
            r = bt.run(ts, opens, closes, ww, start, band=0.02, slippage_bps=1.0)
            out[key][label] = {"1bp": bt.stats(r, BARS)}
        out["windows"][label]["tqqq"] = bt.benchmark(closes[i:, 1], ts[i:], BARS)
        s = out["windows"][label]["1bp"]
        print(f"{label}: CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  fills {s['fills']}")
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
