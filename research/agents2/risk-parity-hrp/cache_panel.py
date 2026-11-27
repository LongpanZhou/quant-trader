"""Load the 1m panel once and cache it inside this agent's folder."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
START, END = "2017-01-03", "2026-10-23"


def main() -> None:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    np.savez_compressed(
        HERE / "panel_1m.npz",
        ts=ts.values.astype("datetime64[ns]"),
        opens=opens,
        closes=closes,
    )
    print("bars", len(ts), "from", ts[0], "to", ts[-1])
    print("saved", HERE / "panel_1m.npz")


if __name__ == "__main__":
    main()
