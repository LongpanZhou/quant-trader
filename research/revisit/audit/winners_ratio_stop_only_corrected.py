"""Corrected ratio stop-only control and patch it into winners_attrib.json."""
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


def main():
    ts, o, h, l, c = W.load_panel()
    mod, w_full, _ = W.load_ratio_froth(ts, o, c)
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    qqq_close, tqqq_close = c[:, 0], c[:, 1]
    dc = qqq_close[last]
    ma20 = pd.Series(dc).rolling(mod.MA_FAST).mean().to_numpy()
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    hold = np.ones(len(ts), bool)
    armed_days = 0
    stop_days = 0
    for k, (f, ll) in enumerate(zip(first, last)):
        if k == 0 or not (ma20_prev[k] == ma20_prev[k]):
            continue
        if not (qqq_close[f] < ma20_prev[k] * (1 + mod.ARM_BUF)):
            continue
        armed_days += 1
        base = o[f, 1]
        idx = np.flatnonzero(tqqq_close[f:ll + 1] < base * (1 - mod.STOP))
        if len(idx):
            stop_days += 1
            hold[f + int(idx[0]):ll + 1] = False
    w = np.zeros((len(ts), 3))
    w[hold, 1] = 1.0
    w[~hold, 2] = 1.0
    r = bt.run(ts, o, c, w, W.START, band=0.02, slippage_bps=1.0)
    d = W.daily_equity(r)
    idx = pd.to_datetime(dates[last])
    tq = pd.Series(c[last, 1], index=idx).pct_change()
    qq = pd.Series(c[last, 0], index=idx).pct_change()
    out = {"daily": W.metrics(d), "minute": W.minute_metrics(r),
           "exposure": W.exposure(w, ts),
           "beta_tqqq": W.beta_corr(W.daily_returns(d), tq),
           "beta_qqq": W.beta_corr(W.daily_returns(d), qq),
           "yearly": W.yearly_returns_eoy(d),
           "armed_days": armed_days, "stop_days": stop_days}
    print(json.dumps(out, indent=1, default=float))
    W.save_json("winners_ratio_stop_only_corrected.json",
                {"stop_only_corrected": out})

    # patch the attribution JSON so the table values have one source of truth
    path = HERE / "winners_attrib.json"
    doc = json.loads(path.read_text())
    old = doc["ratio"].get("stop_only", {})
    out["note"] = ("Corrected: the first pass put BIL on non-armed days. "
                   "This version holds TQQQ by default and applies the 4% stop "
                   "only on armed days.")
    doc["ratio"]["stop_only"] = out
    path.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    print("patched", path)


if __name__ == "__main__":
    main()
