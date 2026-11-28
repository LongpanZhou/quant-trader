"""Placebo + bootstrap for the tuned strategy (2026-11-27). DEV ONLY.

Placebo: random event sessions, same count as the real events, run through
the SAME build_weights rules (asset switch, hold, stops) and the engine.
Bootstrap: trade-level realised returns (engine fills), mean <= 0.
"""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
os.environ.setdefault("BT_THREADS", "1")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S
import tune_diag as D
bt = S.bt


def main(n_draws=300):
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    qlow, qvol = S.daily_extras(ts)
    out = {}
    for tag, extra in (("tuned", {}), ("before_params", {"event_low_stop": True})):
        p = {**S.PARAMS, **extra}
        w, info = S.build_weights(ts, o, c, qlow, qvol, p)
        real = bt.stats(bt.run(ts, o, c, w, S.DEV_START, 0.02, 1.0), S.BARS_PER_YEAR)["cagr"]
        d = S.prepare_daily(ts, o, c, qlow, qvol)
        i0 = bt.start_index(ts, S.DEV_START)
        dev_days = np.flatnonzero(d["first"] >= i0)
        dev_days = dev_days[(dev_days >= 21) & (dev_days < d["nd"] - 1)]
        rng = np.random.default_rng(20261127)
        k = info["n_events"]
        cagrs = []
        for _ in range(n_draws):
            m = np.zeros(d["nd"], bool)
            m[rng.choice(dev_days, size=k, replace=False)] = True
            wp, _ = S.build_weights(ts, o, c, qlow, qvol, {**p, "_event_mask": m})
            cagrs.append(bt.stats(bt.run(ts, o, c, wp, S.DEV_START, 0.02, 1.0), S.BARS_PER_YEAR)["cagr"])
        cagrs = np.array(cagrs)
        tr = D.trades(ts[i0:], o[i0:], c[i0:], w[i0:])
        rs = np.array([t["ret"] for t in tr])
        bs = np.random.default_rng(7).choice(rs, size=(10000, len(rs))).mean(axis=1)
        out[tag] = dict(real_cagr=float(real), n_events=k, placebo_mean=float(cagrs.mean()),
                        placebo_p95=float(np.quantile(cagrs, 0.95)),
                        placebo_pctile_of_real=float((cagrs < real).mean()),
                        n_trades=len(rs), trade_hit=float((rs > 0).mean()), trade_mean=float(rs.mean()),
                        trade_bootstrap_p=float((bs <= 0).mean()))
        print(tag, json.dumps(out[tag]), flush=True)
    with open(HERE / "tune_placebo.json", "w", newline="\n", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
