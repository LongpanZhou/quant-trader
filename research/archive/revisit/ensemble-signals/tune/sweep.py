"""Variant sweep, neighbourhoods, sub-periods, placebo. Dev only."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vstrat as V
bt, S = V.bt, V.S
ts, o, c = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
base_r = S._baseline_daily_returns(ts, o, c)
SUBS = {"16-19": ("2016-01-01", "2019-12-31"), "20-21": ("2020-01-01", "2021-12-31"), "22-23": ("2022-01-01", "2023-12-31")}


def dret(r):
    e = pd.Series(r["equity"], index=r["ts"]).resample("1D").last().dropna()
    return e.pct_change().dropna()


def evaluate(rows, slips=(1,)):
    ws = [V.build(ts, o, c, **kw)[0] for _, kw in rows]
    out = []
    res = {s: bt.run_many(ts, o, c, ws, S.DEV_START, band=0.02, slippage_bps=s, threads=1) for s in slips}
    for k, (name, kw) in enumerate(rows):
        r = res[slips[0]][k]; st = bt.stats(r, S.BARS_PER_YEAR); dr = dret(r)
        j = dr.index.intersection(base_r.index)
        row = {"name": name, "cagr": st["cagr"], "dd": st["max_drawdown"], "sharpe": st["sharpe"], "fills": st["fills"],
               "corr": float(np.corrcoef(dr.loc[j], base_r.loc[j])[0, 1])}
        eq = pd.Series(r["equity"], index=r["ts"])
        for sp, (a, b) in SUBS.items():
            e = eq[(eq.index >= pd.Timestamp(a, tz=eq.index.tz)) & (eq.index <= pd.Timestamp(b + " 23:59", tz=eq.index.tz))]
            yrs = (e.index[-1] - e.index[0]).total_seconds() / (365.25 * 86400)
            row["cagr_" + sp] = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
        for s in slips[1:]:
            row[f"cagr_{s}bp"] = bt.stats(res[s][k], S.BARS_PER_YEAR)["cagr"]
        out.append(row)
    return pd.DataFrame(out).set_index("name")


pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
which = sys.argv[1] if len(sys.argv) > 1 else "struct"
if which == "struct":
    rows = [("A0 as-is", {}),
            ("A1 warmup", dict(warmup=True)),
            ("A2 pct excl self", dict(pct_excl_self=True)),
            ("A3 warmup+excl", dict(warmup=True, pct_excl_self=True)),
            ("B1 recovery->QQQ", dict(recovery_asset="qqq")),
            ("B2 recovery->BIL", dict(recovery_asset="bil")),
            ("B3 TQQQ units fixed /3", dict(tqqq_units="tqqq")),
            ("B1w recovery->QQQ +warm", dict(recovery_asset="qqq", warmup=True)),
            ("B3w units fixed +warm", dict(tqqq_units="tqqq", warmup=True)),
            ("C1 normal TQQQ same exp", dict(recovery_asset="qqq", normal_asset="tqqq")),
            ("C2 normal TQQQ tgt .40", dict(recovery_asset="qqq", normal_asset="tqqq", qqq_vol_target=0.40)),
            ("C3 normal TQQQ tgt .60", dict(recovery_asset="qqq", normal_asset="tqqq", qqq_vol_target=0.60)),
            ]
    print(evaluate(rows, (1, 5, 10)).round(4).to_string())
elif which == "nbhd":
    base = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    grid = {"stress_pct": [0.7, 0.8, 0.9], "stress_slope": [0.0, 0.1, 0.2], "calm_pct": [0.2, 0.3, 0.4],
            "complacency_slope": [0.15, 0.25, 0.35], "min_hold": [3, 5, 10], "max_recovery": [10, 20, 30],
            "tqqq_vol_target": [0.25, 0.35, 0.45], "qqq_vol_target": [0.15, 0.20, 0.25], "vol_fast": [3, 5, 10], "vol_mid": [15, 20, 30]}
    skip = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
    rows = [("center", dict(base))]
    for k, vals in grid.items():
        if k in skip:
            continue
        for v in vals:
            if v == base.get(k, S.DEFAULTS[k]):
                continue
            d = dict(base); d[k] = v; rows.append((f"{k}={v}", d))
    print(evaluate(rows).round(4).to_string())
elif which == "placebo":
    base = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    rows = [("real", dict(base))] + [(f"plc{s}", dict(base, placebo_seed=s)) for s in range(40)]
    df = evaluate(rows)
    real = df.loc["real"]; pl = df.drop("real")
    print(real.round(4).to_dict())
    print("placebo cagr mean %.4f sd %.4f; share >= real %.3f; sharpe mean %.3f share>=real %.3f" % (
        pl.cagr.mean(), pl.cagr.std(), (pl.cagr >= real.cagr).mean(), pl.sharpe.mean(), (pl.sharpe >= real.sharpe).mean()))
