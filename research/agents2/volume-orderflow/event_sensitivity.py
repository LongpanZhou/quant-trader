"""Step 21: how much of the edge is one event?  Re-enable single skipped stops."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from strategy import build_weights  # noqa: E402


def main():
    D = engine.Data()
    w, ev = build_weights(D)
    base, _ = engine.winner_weights(D)
    b = engine.evaluate(D, base, "winner")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}
    engine.evaluate(D, w, "final")

    # stop days present in the winner but absent in the final rule
    def stop_days(w):
        out = {}
        h = w[:, 1]
        for d in range(D.nd):
            f, l = int(D.first[d]), int(D.last[d])
            seg = h[f:l + 1]
            if seg[0] > 0 and (seg == 0).any():
                j = int(np.argmax(seg == 0))
                out[str(D.dates[f])] = (d, j)
        return out

    sf, sb = stop_days(w), stop_days(base)
    only_winner = sorted(set(sb) - set(sf))
    only_final = sorted(set(sf) - set(sb))
    print(f"\nstops only in the round-1 winner: {len(only_winner)}")
    print("  ", ", ".join(only_winner))
    print(f"stops only in the final rule: {len(only_final)}")
    print("  ", ", ".join(only_final))

    print("\n-- re-enabling individual skipped stops (5y window sensitivity)")
    for day in only_winner:
        if day < "2021-10-01":
            continue
        d, j = sb[day]
        w2 = w.copy()
        f, l = int(D.first[d]), int(D.last[d])
        w2[f + j:l + 1, 1] = 0.0
        w2[f + j:l + 1, 2] = 1.0
        r = engine.evaluate(D, w2)
        print(f"  restore {day}: 10y {r['10y']['cagr']*100:5.2f}/"
              f"{r['10y']['max_drawdown']*100:5.2f} | 5y "
              f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f}")

    print("\n-- adding the 2026-06-24 stop back (exact fill from the winner)")
    if "2026-06-24" in sb:
        d, j = sb["2026-06-24"]
        w2 = w.copy()
        f, l = int(D.first[d]), int(D.last[d])
        w2[f + j:l + 1, 1] = 0.0
        w2[f + j:l + 1, 2] = 1.0
        r = engine.evaluate(D, w2, "restore 2026-06-24")

    print("\n-- stop counts inside the 5y window")
    for name, ww in (("winner", base), ("final", w)):
        sd = stop_days(ww)
        n5 = sum(1 for x in sd if x >= "2021-10-25")
        print(f"  {name}: {n5} stops")


if __name__ == "__main__":
    main()
