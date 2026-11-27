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

captured = []
orig_run, orig_sim, orig_many = bt.run, bt.simulate, bt.run_many


def run(*a, **k):
    r = orig_run(*a, **k)
    captured.append(r)
    return r


def sim(*a, **k):
    r = orig_sim(*a, **k)
    captured.append(r)
    return r


def many(*a, **k):
    rs = orig_many(*a, **k)
    captured.extend(rs)
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
for r in captured:
    try:
        s = bt.stats(r, 252 * 390)
    except Exception:
        continue
    if (abs(s["cagr"] - stored["cagr"]) < 1e-6
            and abs(s["max_drawdown"] - stored["max_drawdown"]) < 1e-6):
        match = r
        break

if match is None:
    print("NO MATCH", slug, "captured", len(captured))
    raise SystemExit(2)

eq = pd.Series(match["equity"], index=pd.DatetimeIndex(match["ts"]))
daily = eq.groupby(eq.index.date).last()
daily = daily / daily.iloc[0] * 100.0
payload = {
    "slug": slug,
    "dates": [str(d) for d in daily.index],
    "values": [float(v) for v in daily.to_numpy()],
}
out.write_text(json.dumps(payload), encoding="utf-8")
print("WROTE", out, len(daily), "days", "last", round(float(daily.iloc[-1]), 1))
