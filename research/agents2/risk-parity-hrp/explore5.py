"""Exploration 5 (clean engine, all signals lagged one session).

Re-tests the vol-target brake, vol windows, stop destinations and drawdown
throttle after fixing the look-ahead found in explore4.
"""
from __future__ import annotations

import numpy as np

from engine import Signals, load_panel, run_window, fmt

START10, START5 = "2017-01-03", "2021-10-25"


def main():
    ts, opens, closes = load_panel()
    s = Signals(ts, opens, closes)
    print("sessions", s.d, "risk-on", s.risk_on.mean(), "stop events", int(np.sum(np.diff(np.r_[0, s.stopped.astype(int)]) == 1)))

    def go(label, wt, dest="bil", slip=1.0, slip5=None):
        w = s.weights(wt, dest)
        m10, _ = run_window(s, w, START10, slip)
        m5, _ = run_window(s, w, START5, slip)
        extra = ""
        if slip5 is not None:
            a, _ = run_window(s, w, START10, slip5)
            b, _ = run_window(s, w, START5, slip5)
            extra = f"|| {slip5:.0f}bp {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f}"
        print(fmt(label, m10, m5, extra), flush=True)

    one = np.ones(s.d)
    print("\n--- reference ---")
    go("winner 100TQ stop->BIL", one, "bil", 1.0, 5.0)
    for dest in ("qqq", "half"):
        go(f"stop->{dest}", one, dest, 1.0, 5.0)

    print("\n--- vol-target brake (inverse-vol w/ target), stop->BIL ---")
    v20 = s.vol(20)
    print("mean TQQQ vol20 %.2f" % np.nanmean(v20[:, 1]))
    for tv in (0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55):
        wt = np.clip(tv / v20[:, 1], 0, 1)
        go(f"tv={tv:.2f} mWt{np.nanmean(wt):.2f}", wt, "bil", 1.0, 5.0)

    print("\n--- window sensitivity ---")
    for tv in (0.70, 0.65):
        for win in (10, 20, 40, 60):
            v = s.vol(win)
            wt = np.clip(tv / v[:, 1], 0, 1)
            go(f"tv={tv:.2f} win={win}", wt, "bil", 1.0, 5.0)

    print("\n--- drawdown throttle, stop->BIL ---")
    for hin in (126, 252):
        dd = s.drawdown(hin)
        for thr, wtc in ((0.05, 0.7), (0.08, 0.7), (0.08, 0.5), (0.10, 0.5), (0.15, 0.3)):
            wt = np.where(dd < -thr, wtc, 1.0)
            go(f"hi{hin} dd<{-thr:.0%} wT{wtc}", wt, "bil", 1.0, 5.0)


if __name__ == "__main__":
    main()
