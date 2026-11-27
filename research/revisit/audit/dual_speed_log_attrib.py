"""Log-return attribution: overnight gap vs intraday, current vs pre-tune cash."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit" / "audit"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "revisit" / "dual-speed-regime"))
import bt  # noqa: E402
import strategy as S  # noqa: E402

TZ = "America/New_York"
START, FULL_END = "2016-01-04", "2026-10-23"

ts, o, c = bt.panel(S.SYMS, START, FULL_END, "1min", warmup_days=500)
idx = pd.DatetimeIndex(ts)
is_0930 = np.asarray((idx.hour == 9) & (idx.minute == 30))
years = (ts[-1] - ts[0]).total_seconds() / (365.25 * 86400)

out = {}
for name, kw in (("current", dict()),
                 ("pretune_cash", dict(overnight=False, idle="cash")),
                 ("pretune_bil", dict(overnight=False, idle="bil"))):
    w, info = S.build_weights(ts, o, c, **kw)
    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
    eq, cash = r["equity"], r["cash"]
    # For cash-idle variants eq-cash is the TQQQ value.  For BIL it also
    # contains BIL; approximate the open value with the same dollar exposure
    # (BIL's overnight move is ~0, so this is accurate to a few bp).
    Vt = eq - cash
    gap = np.zeros(len(ts))
    for i in range(1, len(ts)):
        gap[i] = Vt[i - 1] * (o[i, 1] / c[i - 1, 1] - 1.0)
    on_gap = np.where(is_0930, gap, 0.0)
    ret_total = np.zeros(len(ts))
    ret_total[1:] = eq[1:] / eq[:-1] - 1.0
    ret_on = on_gap / eq
    ret_intra = (eq - np.r_[eq[0], eq[:-1]] - on_gap) / np.r_[eq[0], eq[:-1]]
    # avoid division by zero at i=0
    ret_on[0] = 0.0
    ret_intra[0] = 0.0
    log_total = float(np.log1p(ret_total[1:]).sum())
    log_on = float(np.log1p(ret_on[1:]).sum())
    log_intra = float(np.log1p(ret_intra[1:]).sum())
    out[name] = {
        "log_total": log_total,
        "log_on_0930": log_on,
        "log_intra": log_intra,
        "on_share": log_on / log_total if log_total else None,
        "cagr_total": float(np.exp(log_total / years) - 1.0),
        "cagr_on_only": float(np.exp(log_on / years) - 1.0),
        "cagr_intra_only": float(np.exp(log_intra / years) - 1.0),
        "years": years,
        "eq_end": float(eq[-1]),
        "gap_0930_dollars": float(on_gap.sum()),
        "n_0930_gap_positive": int((on_gap > 0).sum()),
        "n_0930_gap_negative": int((on_gap < 0).sum()),
    }

(HERE / "dual_speed_log_attrib.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
