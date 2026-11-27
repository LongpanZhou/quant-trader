import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "a21", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py"
)
a21 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(a21)

ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1min")
w, _ = a21.build_weights(ts, op, cl)
cut = int(ts.searchsorted(__import__("pandas").Timestamp("2022-01-03", tz="America/New_York")))
w2, _ = a21.build_weights(ts[:cut], op[:cut], cl[:cut])
print("causal prior weights identical:", np.array_equal(w[:cut], w2))
print("row sums in [0,1]:", float(w.sum(axis=1).min()), float(w.sum(axis=1).max()))
