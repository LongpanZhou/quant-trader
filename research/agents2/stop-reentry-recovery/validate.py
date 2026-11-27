"""Validate the round-1 winner reproduction, then screen re-entry families."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

w, d = S.base_weights(A, reg, ma20)
print("base stop bars:", len(d["stop_bars"]))
for start in (S.START10, S.START5):
    s = S.metrics(ts, o, c, w, start, 1.0)
    S.line(f"BASE {start[:4]}", s)

# control: regime only
w0 = np.zeros((len(ts), 3)); w0[:, 1] = reg.astype(float); w0[:, 2] = 1 - w0[:, 1]
for start in (S.START10, S.START5):
    s = S.metrics(ts, o, c, w0, start, 1.0)
    S.line(f"CONTROL {start[:4]}", s)
