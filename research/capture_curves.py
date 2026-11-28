import json
import os
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

slug = sys.argv[1]
flags = sys.argv[2:]
path = ROOT / "research" / "revisit" / slug / "strategy.py"
result_path = path.parent / "result.json"
previous_result = None
if result_path.exists():
    try:
        previous_result = json.loads(result_path.read_text())
    except Exception:
        previous_result = None
out = ROOT / "research" / "revisit" / "curves" / f"{slug}.json"
out.parent.mkdir(parents=True, exist_ok=True)

# Every engine call is recorded as (cagr, max_drawdown, daily curve) instead of
# keeping the whole result: a sweep makes hundreds of 1-minute results (~13 MB
# each), and only the one matching result.json is needed at the end.
captured = []
orig_run, orig_sim, orig_many = bt.run, bt.simulate, bt.run_many


_DAY_NS = 86_400 * 10**9
_SAFE_TOD_NS = 5 * 3600 * 10**9   # US/Eastern is UTC-4/-5


def daily_curve(r):
    """(session day numbers, last equity of each session), cheaply.

    Equal to `eq.groupby(eq.index.date).last()`: every bar at or after 05:00
    UTC lies on the same calendar day in New York and in UTC, so the local
    session date is the UTC day number of the timestamp.
    """
    i8 = np.asarray(pd.DatetimeIndex(r["ts"]).asi8)
    eq = np.asarray(r["equity"], dtype=float)
    key = (len(i8), int(i8[0]), int(i8[-1]), int(i8[::997].sum()))
    hit = _BOUNDS.get(key)
    if hit is None:
        day = i8 // _DAY_NS
        if ((i8 - day * _DAY_NS) >= _SAFE_TOD_NS).all():
            last = np.r_[np.flatnonzero(day[1:] != day[:-1]), len(day) - 1]
            hit = (day[last], last)
        else:
            hit = (None, None)
        if len(_BOUNDS) >= 8:
            _BOUNDS.clear()
        _BOUNDS[key] = hit
    days, last = hit
    if days is None:
        s = pd.Series(eq, index=pd.DatetimeIndex(r["ts"]))
        d = s.groupby(s.index.date).last()
        return (np.array([np.datetime64(x, "D").astype(np.int64) for x in d.index]),
                d.to_numpy(float))
    return days, eq[last]


_BOUNDS: dict = {}


def record(r):
    try:
        cagr, mdd = bt.cagr_and_drawdown(r)
        captured.append((cagr, mdd, daily_curve(r)))
    except Exception:
        pass  # not a usable equity result (the old matcher skipped these too)


def run(*a, **k):
    r = orig_run(*a, **k)
    record(r)
    return r


def sim(*a, **k):
    r = orig_sim(*a, **k)
    record(r)
    return r


def many(*a, **k):
    rs = orig_many(*a, **k)
    for r in rs:
        record(r)
    return rs


bt.run, bt.simulate, bt.run_many = run, sim, many
sys.argv = [str(path)] + flags
try:
    runpy.run_path(str(path), run_name="__main__")
except SystemExit as e:
    print("SystemExit", e)
except Exception as e:
    print("main error", type(e).__name__, e)

# The agent main writes a dev-only result.json.  Preserve the lead's
# already-computed holdout/10y/5y blocks instead of wiping them on every rerun.
if previous_result and result_path.exists():
    try:
        current = json.loads(result_path.read_text())
        prev_windows = previous_result.get("windows") or {}
        cur_windows = current.setdefault("windows", {})
        for key in ("holdout", "10y", "5y"):
            if not cur_windows.get(key) and prev_windows.get(key):
                cur_windows[key] = prev_windows[key]
        result_path.write_text(json.dumps(current, indent=2, default=float),
                               encoding="utf-8")
    except Exception as e:
        print("could not preserve holdout windows:", e)

stored = json.loads(result_path.read_text())["windows"]["dev"]["1bp"]
match = None
for cagr, mdd, curve in captured:
    if (abs(cagr - stored["cagr"]) < 1e-6
            and abs(mdd - stored["max_drawdown"]) < 1e-6):
        match = curve
        break

if match is None:
    print("NO MATCH", slug, "captured", len(captured))
    raise SystemExit(2)

days, values = match
values = values / values[0] * 100.0
payload = {
    "slug": slug,
    "dates": [str(d) for d in days.astype("datetime64[D]")],
    "values": [float(v) for v in values],
}
out.write_text(json.dumps(payload), encoding="utf-8")
print("WROTE", out, len(values), "days", "last", round(float(values[-1]), 1))
