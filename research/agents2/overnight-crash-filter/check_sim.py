"""Validate the fast simulator against bt.simulate and reproduce references."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

sys.path.insert(0, str(lab.ROOT / "research"))
import bt  # noqa: E402


def winner_weights(ts, opens, closes, stop=0.04, arm_buf=0.01, ma_fast=20):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    n = len(ts)
    qc, tc = closes[:, 0], closes[:, 1]
    dclose = qc[last]
    sma = pd.Series(dclose).rolling(165).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        k = int(day_id[f])
        if k == 0:
            continue
        if not (sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]):
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and qc[f] < ma20_prev[k] * (1 + arm_buf))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tc[i] < base * (1 - stop):
                state = False
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    days = lab.Days(ts, o, c)
    print(f"panel {ts[0]} .. {ts[-1]}  bars {len(ts):,}  days {days.nd}")

    # ---- validation: fast_sim vs bt.simulate on four weight sets ----
    test = {
        "bh": np.tile(np.array([[0.0, 1.0, 0.0]]), (len(ts), 1)),
        "overnight": lab.build_weights(days, base="overnight", m=0),
        "first30": lab.build_weights(days, base="morning", m=30),
        "winner": winner_weights(ts, o, c),
    }
    for name, w in test.items():
        for slip in (1.0, 5.0):
            i = bt.start_index(ts, lab.START10)
            r1 = bt.simulate(ts[i:], o[i:], c[i:], w[i:], band=0.02, slippage_bps=slip)
            r2 = lab.fast_sim(ts[i:], o[i:], c[i:], w[i:], band=0.02, slippage_bps=slip)
            dm = np.nanmax(np.abs(r1["equity"] - r2["equity"]) / r1["equity"])
            print(f"  {name:10s} {slip:4.1f}bp  max rel eq diff {dm:.2e}  "
                  f"fills {r1['fills']} vs {r2['fills']}  "
                  f"CAGR {bt.stats(r1, lab.BARS_PER_YEAR)['cagr']*100:.2f} vs "
                  f"{bt.stats(r2, lab.BARS_PER_YEAR)['cagr']*100:.2f}")

    # ---- reference strategies ----
    for name, w in test.items():
        if name == "bh":
            continue
        for start in (lab.START10, lab.START5):
            for slip in (1.0, 5.0, 10.0):
                s, _ = lab.summarize(ts, o, c, w, start, slip, f"{name} {start[:4]} {slip:.0f}bp")


if __name__ == "__main__":
    main()
