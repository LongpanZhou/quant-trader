"""Rebuild both winners from current code on 2016-01-04..2026-10-23 and
compare with the published curves_full files.  Read-only: nothing is written
outside audit/.
"""
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

CURVES = W.ROOT / "research" / "revisit" / "curves_full"


def curve_cmp(name, daily):
    pub = json.loads((CURVES / f"{name}.json").read_text())
    p = pd.Series(pub["values"], index=pd.to_datetime(pub["dates"]))
    p = p / p.iloc[0] * 100.0
    d = daily / daily.iloc[0] * 100.0
    j = pd.concat([d.rename("fresh"), p.rename("pub")], axis=1)
    both = j.dropna()
    rel = (both["fresh"] / both["pub"] - 1.0)
    return {
        "published_days": int(len(p)),
        "fresh_days": int(len(d)),
        "published_range": [str(p.index[0].date()), str(p.index[-1].date())],
        "fresh_range": [str(d.index[0].date()), str(d.index[-1].date())],
        "same_dates": bool(len(j) == len(both) and len(d) == len(p)),
        "max_abs_rel_diff": float(rel.abs().max()) if len(rel) else None,
        "mean_abs_rel_diff": float(rel.abs().mean()) if len(rel) else None,
        "max_abs_diff_index": str(rel.abs().idxmax().date()) if len(rel) else None,
        "published_last": float(p.iloc[-1]),
        "fresh_last": float(d.iloc[-1]),
        "published_stats": W.metrics(p),
        "fresh_stats": W.metrics(d),
    }


def main():
    ts, o, h, l, c = W.load_panel()
    print("panel", len(ts), ts[0], ts[-1])
    out = {}

    # ---------------- ratio froth (old agents2 base + overlay) ----------------
    mod_r, w_r, diag_r = W.load_ratio_froth(ts, o, c)
    r_r = bt.run(ts, o, c, w_r, W.START, band=0.02, slippage_bps=1.0)
    d_r = W.daily_equity(r_r)
    out["ratio_froth"] = {
        "diag": diag_r,
        "daily_metrics": W.metrics(d_r),
        "minute": W.minute_metrics(r_r),
        "exposure": W.exposure(w_r, ts),
        "curve": curve_cmp("ratio-froth", d_r),
        "yearly": W.yearly_returns_eoy(d_r),
    }
    print("ratio", out["ratio_froth"]["daily_metrics"])
    print("ratio curve", out["ratio_froth"]["curve"]["max_abs_rel_diff"])

    # ---------------- vol-scaled crash stop ----------------
    mod_v, w_v, info_v, atr, first, last = W.load_vol(ts, o, h, l, c)
    r_v = bt.run(ts, o, c, w_v, W.START, band=0.02, slippage_bps=1.0)
    d_v = W.daily_equity(r_v)
    out["vol_scaled"] = {
        "info": info_v,
        "atr_finite_sessions": int(np.isfinite(atr).sum()),
        "daily_metrics": W.metrics(d_v),
        "minute": W.minute_metrics(r_v),
        "exposure": W.exposure(w_v, ts),
        "curve": curve_cmp("vol-scaled-crash-stop", d_v),
        "yearly": W.yearly_returns_eoy(d_v),
    }
    print("vol", out["vol_scaled"]["daily_metrics"])
    print("vol curve", out["vol_scaled"]["curve"]["max_abs_rel_diff"])

    # compare with the already-cached full weights from the earlier audit
    z = np.load(W.CACHE / "vol-scaled-crash-stop-full.npz")
    ts_c = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)).tz_convert("America/New_York")
    w_c = z["weights"]
    same = (len(ts_c) == len(ts) and np.array_equal(ts_c.asi8, ts.asi8)
            and np.allclose(w_c, w_v, atol=1e-12))
    out["vol_scaled"]["matches_cached_audit_weights"] = bool(same)
    if not same and len(ts_c) == len(ts):
        out["vol_scaled"]["cached_weight_maxdiff"] = float(np.abs(w_c - w_v).max())
    print("vol cached weights match", same)

    # ---------------- benchmarks ----------------
    dates = bt.session_dates(ts)
    _, last_b = bt.day_bounds_from_dates(dates)
    idx = pd.to_datetime(dates[last_b])
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        s = pd.Series(c[last_b, col], index=idx)
        out[f"bench_{name}"] = {
            "daily_metrics": W.metrics(s),
            "yearly": W.yearly_returns_eoy(s),
        }
        print(name, out[f"bench_{name}"]["daily_metrics"]["cagr"],
              out[f"bench_{name}"]["daily_metrics"]["max_drawdown"])

    # daily return correlations / betas
    for nm, d in (("ratio_froth", d_r), ("vol_scaled", d_v)):
        sr = W.daily_returns(d)
        block = {}
        for b in ("tqqq", "qqq"):
            bd = pd.Series(c[last_b, 1 if b == "tqqq" else 0], index=idx)
            br = W.daily_returns(bd)
            block[b] = {**W.beta_corr(sr, br), **W.updown_capture(sr, br)}
        out[nm]["beta"] = block
        print(nm, "beta", {k: round(v["beta"], 3) for k, v in block.items()},
              "corr", {k: round(v["corr"], 3) for k, v in block.items()})

    W.save_json("winners_rebuild.json", out)


if __name__ == "__main__":
    main()
