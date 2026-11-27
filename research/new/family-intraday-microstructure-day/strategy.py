"""Day-only opening-drive intraday microstructure (family-pure variant).

This is the day sleeve of the original intraday agent with the overnight
reversal disabled, so the book is flat from 15:59 to 09:30.  The input is the
shared panel sliced to (TQQQ, BIL) columns; the output is the same 2-column
shape.

The base helpers are inlined here so this library entry does not depend on the
deleted `research/new/family-intraday-microstructure/` candidate directory.
The signal mechanics, thresholds and `night_th=-1.0` no-overnight setting are
unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

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
        [bool(np.isfinite(f["r30"]) and f["r30"] > r30_th) for f in feats],
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


def build_weights(ts, o, c, night_th=-1.0, gap_th=BASE_GAP,
                  r30_th=BASE_R30, trail=BASE_TRAIL, bil=True):
    """Day sleeve only: no overnight position, no weak-close reversal."""
    feats = _sessions(ts, o, c)
    night, gap, r30 = _flags(feats, night_th, gap_th, r30_th)
    return _weights(ts, o, c, feats, night, gap, r30, trail, bil)
