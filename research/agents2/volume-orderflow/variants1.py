"""Step 5: volume-gated overnight exposure on top of the round-1 winner."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def overnight_gate(D, w, k=1.5, m=388, require_down=False, require_below_vwap=False):
    """Flat overnight after a high-relative-volume session.

    Decision at bar m (default 15:58) using cumulative same-time-of-day RVOL;
    the sale fills at open[m+1] (15:59) so the whole gap is avoided, and the
    position is re-established at the next session's open.
    """
    w = w.copy()
    n_ev = 0
    rv = D.rvol_cum_q[:, m]
    for d in range(D.nd - 1):
        if not D.reg[d]:
            continue
        if not np.isfinite(rv[d]) or rv[d] <= k:
            continue
        if require_down and not (D.tc[d] < D.to[d]):
            continue
        if require_below_vwap and not (np.isfinite(D.dev_q[d, m]) and D.dev_q[d, m] < 0):
            continue
        n_ev += 1
        l = D.last[d]
        if l - 1 <= D.first[d]:
            continue
        w[l - 1, 1] = 0.0
        w[l, 1] = float(D.reg[d + 1])   # buy back at the next open if still risk-on
        w[l - 1, 2] = 1.0 - w[l - 1, 1]
        w[l, 2] = 1.0 - w[l, 1]
    return w, n_ev


def main():
    D = engine.Data()
    base, stop_bar = engine.winner_weights(D)
    print(f"winner stops {int(stop_bar.sum())}")
    engine.evaluate(D, base, "winner (round-1)")
    ctrl = np.zeros((D.n, 3))
    ctrl[:, 1] = D.reg_bar
    ctrl[:, 2] = 1 - ctrl[:, 1]
    engine.evaluate(D, ctrl, "regime only, no stop")

    print("\n-- overnight RVOL gate on the winner")
    for k in (1.2, 1.5, 1.8, 2.0, 2.5, 3.0):
        w, nev = overnight_gate(D, base, k=k)
        engine.evaluate(D, w, f"gate rvol>{k:<4} (n={nev})")

    print("\n-- variants at k=1.5")
    for lab, kw in (("down days only", dict(require_down=True)),
                    ("below VWAP only", dict(require_below_vwap=True))):
        w, nev = overnight_gate(D, base, k=1.5, **kw)
        engine.evaluate(D, w, f"gate rvol>1.5, {lab} (n={nev})")

    print("\n-- decision at 15:00 (exit before the last hour)")
    for k in (1.5, 2.0, 2.5):
        w, nev = overnight_gate(D, base, k=k, m=300)
        engine.evaluate(D, w, f"gate rvol>15:00 {k} (n={nev})")


if __name__ == "__main__":
    main()
