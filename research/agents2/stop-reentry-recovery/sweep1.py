"""Screen same-day / overnight re-entry families against the round-1 winner."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, first, last = A["ts"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

V = {
    "base": dict(mode="base"),
    "vwap_c1": dict(mode="vwap", confirm=1),
    "vwap_c1_t2": dict(mode="vwap", confirm=1, tight=0.02),
    "vwap_c1_t3": dict(mode="vwap", confirm=1, tight=0.03),
    "vwap_c3_t2": dict(mode="vwap", confirm=3, tight=0.02),
    "vwap_c2_b5_t2": dict(mode="vwap", confirm=2, buffer=0.0005, tight=0.02),
    "vwap_c1_t2_win": dict(mode="vwap", confirm=1, tight=0.02, t_start=30, t_end=330),
    "vwap_failstop": dict(mode="vwap", confirm=1, vwap_fail=0.001),
    "vwap_c1_t2_half": dict(mode="vwap", confirm=1, tight=0.02, size=0.5),
    "ema5_c1": dict(mode="ema5", confirm=1),
    "ema5_c1_t2": dict(mode="ema5", confirm=1, tight=0.02),
    "ema5_c3_t2": dict(mode="ema5", confirm=3, tight=0.02),
    "ema5s20_c1_t2": dict(mode="ema5", ema_line="ema5b", confirm=1, tight=0.02),
    "ema15_c1": dict(mode="ema15", confirm=1),
    "ema15_c1_t2": dict(mode="ema15", confirm=1, tight=0.02),
    "ema15_c3_t2": dict(mode="ema15", confirm=3, tight=0.02),
    "ema15_c1_t2_half": dict(mode="ema15", confirm=1, tight=0.02, size=0.5),
    "qqqma_c1_t2": dict(mode="qqqma", confirm=1, tight=0.02),
    "qqqma_c1": dict(mode="qqqma", confirm=1),
    "overnight_stop": dict(mode="overnight", overnight_cond="stoplevel"),
    "overnight_vwap": dict(mode="overnight", overnight_cond="vwap"),
    "overnight_open": dict(mode="overnight", overnight_cond="open"),
    "overnight_vwap_half": dict(mode="overnight", overnight_cond="vwap", size=0.5),
    "nextday_blockweak": dict(mode="nextday", block_next_on_weak_close=True),
}

res = {}
t0 = time.time()
for name, kw in V.items():
    w, d = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)
    row = dict(reentries=len(d["reentries"]), second_stops=len(d["second_stops"]),
               overnight=d["overnight"], blocked=d["blocked_days"])
    for lab, start in (("10y", S.START10), ("5y", S.START5)):
        s = S.metrics(ts, o, c, w, start, 1.0)
        row[lab] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                        fills=s["fills"], turnover=s["turnover"])
    res[name] = row
    print(f"{name:22s} re={row['reentries']:3d} ss={row['second_stops']:3d} ov={row['overnight']:2d} | "
          f"10y {row['10y']['cagr']*100:6.2f}/{row['10y']['dd']*100:5.2f} | "
          f"5y {row['5y']['cagr']*100:6.2f}/{row['5y']['dd']*100:5.2f} | fills {row['10y']['fills']:5d}")

(HERE / "sweep1.json").write_text(json.dumps(res, indent=2))
print(f"\n{time.time()-t0:.1f}s")
