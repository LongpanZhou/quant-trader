"""Cache/staleness checks and clean dev-window metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402

out = {}

# 1. what is inside the vol strategy's dev_panel cache?
z = np.load(W.ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "dev_panel.npz")
ts_c = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)).tz_convert("America/New_York")
out["vol_dev_panel_cache"] = {
    "file": str(W.ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "dev_panel.npz"),
    "bars": int(len(ts_c)),
    "first": str(ts_c[0]),
    "last": str(ts_c[-1]),
    "declared_dev_end": "2023-12-29",
    "is_full_panel": bool(ts_c[-1].year == 2026),
    "size_bytes": int((W.ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "dev_panel.npz").stat().st_size),
}
print("cache", json.dumps(out["vol_dev_panel_cache"], indent=1))

# 2. clean dev window: truncate the panel physically and rebuild the vol weights
ts, o, h, l, c = W.load_panel()
i_end = int(ts.searchsorted(pd.Timestamp("2023-12-30", tz="America/New_York")))
ts_d, o_d, h_d, l_d, c_d = ts[:i_end], o[:i_end], h[:i_end], l[:i_end], c[:i_end]
mod_v, w_d, info_d, atr_d, first_d, last_d = W.load_vol(ts_d, o_d, h_d, l_d, c_d)
r_d = bt.run(ts_d, o_d, c_d, w_d, "2016-01-04", band=0.02, slippage_bps=1.0)
m_d = W.metrics(W.daily_equity(r_d))
s_d = W.minute_metrics(r_d)
out["vol_clean_dev"] = {"daily": m_d, "minute": s_d, "events": info_d["events"]}
print("clean dev", json.dumps(out["vol_clean_dev"], indent=1))

# 3. compare weights on the common dev window (causality check)
z = np.load(W.CACHE / "vol-scaled-crash-stop-full.npz")
ts_f = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)).tz_convert("America/New_York")
w_f = z["weights"]
j = min(len(ts_d), len(ts_f))
out["vol_dev_vs_full_weights"] = {
    "common_bars": int(j),
    "max_abs_diff": float(np.abs(w_d[:j] - w_f[:j]).max()),
    "n_diff_bars": int(np.sum(np.abs(w_d[:j] - w_f[:j]).max(axis=1) > 1e-12)),
}
print("weights", out["vol_dev_vs_full_weights"])

# 4. 10y / 5y numbers from the full weights, minute marks (audit convention)
for label, start in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
    r = bt.run(ts, o, c, w_f, start, band=0.02, slippage_bps=1.0)
    out[f"vol_{label}_minute"] = W.minute_metrics(r)
    out[f"vol_{label}_daily"] = W.metrics(W.daily_equity(r))
print("10y", out["vol_10y_minute"])
print("5y", out["vol_5y_minute"])

# 5. ratio froth 10y/5y from its full weights
mod_r, w_r, _ = W.load_ratio_froth(ts, o, c)
for label, start in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
    r = bt.run(ts, o, c, w_r, start, band=0.02, slippage_bps=1.0)
    out[f"ratio_{label}_minute"] = W.minute_metrics(r)
    out[f"ratio_{label}_daily"] = W.metrics(W.daily_equity(r))
print("ratio 10y", out["ratio_10y_minute"])

# 6. compare agents2 result.json's 10y/5y to our fresh run
old = json.loads((W.ROOT / "research" / "agents2" / "ratio-pairs" / "result.json").read_text())
out["ratio_agents2_result"] = {
    "10y": old["windows"]["10y"],
    "5y": old["windows"]["5y"],
}
volres = json.loads((W.ROOT / "research" / "revisit" / "vol-scaled-crash-stop" / "result.json").read_text())
out["vol_result_json_dev"] = volres["windows"]["dev"]["1bp"]
out["vol_result_json_dev_matches_full_window"] = bool(
    abs(volres["windows"]["dev"]["1bp"]["cagr"] - W.minute_metrics(
        bt.run(ts, o, c, w_f, "2016-01-04", band=0.02, slippage_bps=1.0))["cagr"]) < 1e-9)
print("vol result dev matches full:", out["vol_result_json_dev_matches_full_window"])

W.save_json("winners_staleness.json", out)
