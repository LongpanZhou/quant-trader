"""Final evaluation + result.json for the stop re-entry / recovery study."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import srlib as S  # noqa: E402

A = S.arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
o, c = A["o"], A["c"]
reg, ma20 = S.regime(ts, c[:, 0], first, last)
vwap = S.session_vwap(A["h"], A["l"], A["c"], A["v"], first, last)
ema5 = S.session_ema(c, first, last, 5, 9)
ema5b = S.session_ema(c, first, last, 5, 20)
ema15 = S.session_ema(c, first, last, 15, 9)

COMBO = dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5,
             next_day_tight=0.02)
VARIANTS = {
    "base": dict(mode="base"),
    "tight_only": dict(mode="base", next_day_tight=0.02),
    "block_only": dict(mode="nextday", block_next_on_weak_close=True, block_frac=0.5),
    "combo": COMBO,
    "combo_entry": dict(COMBO, tight_anchor="entry"),
    "combo_nochain": dict(COMBO, tight_chain=False),
}
W, D = {}, {}
for name, kw in VARIANTS.items():
    W[name], D[name] = S.make_weights(A, reg, ma20, vwap, ema5, ema5b, ema15, **kw)


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, pd.Timestamp):
        return str(x)
    return x


def window(w, start, slip):
    s = S.metrics(ts, o, c, w, start, slip)
    t0 = S.bt.start_index(ts, start)
    share = float(np.mean(w[t0:, 1]))
    day_share = {}
    for v in (1.0, 0.5, 0.0):
        day_share[f"{v:.1f}"] = float(np.mean(w[first, 1] == v))
    return dict(
        cagr=float(s["cagr"]), total_return=float(s["total_return"]),
        max_drawdown=float(s["max_drawdown"]),
        max_drawdown_daily_marks=float(s["max_drawdown_daily_marks"]),
        sharpe=float(s["sharpe"]), sortino=float(s["sortino"]), volatility=float(s["volatility"]),
        fills=int(s["fills"]), turnover=float(s["turnover"]), exposure=float(s["exposure"]),
        ending_equity=float(s["ending_equity"]),
        dd_peak=str(s["dd_peak_ts"]), dd_trough=str(s["dd_trough_ts"]),
        tqqq_weight=share, day_share=day_share,
        benchmark=s["bench"], yearly={str(k): v for k, v in s["yearly"].items()},
        eq=s["eq"],
    )


out = {"agent": "stop-reentry-recovery", "date": "2026-11-25",
       "data": "local adjusted 1m QQQ/TQQQ/BIL, regular session, 2017-01-03..2026-10-23",
       "cost_convention": "one-way slippage on traded notional; next-bar-open fills",
       "variants": {}, "costs": {}, "rolling": {}, "subperiods": {},
       "attribution": {}, "bootstrap": {}, "grid": {}, "same_day": {}, "overnight": {}}

print("=" * 110)
print("VARIANTS (1 bp)")
for name in VARIANTS:
    out["variants"][name] = {"10y": window(W[name], S.START10, 1.0),
                             "5y": window(W[name], S.START5, 1.0)}
    a, b = out["variants"][name]["10y"], out["variants"][name]["5y"]
    print(f"{name:14s} 10y {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} | "
          f"5y {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} | "
          f"fills {a['fills']:4d} | tqqq_w {a['tqqq_weight']*100:5.1f}%")

print("=" * 110)
print("COSTS")
for slip in (5.0, 10.0):
    key = f"{slip:.0f}bp"
    out["costs"][key] = {}
    for name in ("base", "combo", "combo_entry"):
        out["costs"][key][name] = {"10y": window(W[name], S.START10, slip),
                                    "5y": window(W[name], S.START5, slip)}
        a = out["costs"][key][name]["10y"]; b = out["costs"][key][name]["5y"]
        print(f"{name:12s} {key:4s} 10y {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} | "
              f"5y {b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f}")

print("=" * 110)
print("SUB-PERIODS (1 bp)")
for a_, z_ in (("2017-01-03", "2019-12-31 23:59"), ("2020-01-02", "2022-12-30 23:59"),
               ("2023-01-03", "2026-10-23 23:59"), ("2017-01-03", "2021-12-31 23:59"),
               ("2022-01-03", "2026-10-23 23:59")):
    row = {}
    for name in ("base", "combo"):
        ser = out["variants"][name]["10y"]["eq"].loc[a_:z_]
        yrs_ = (ser.index[-1] - ser.index[0]).total_seconds() / (365.25 * 86400)
        row[name] = dict(cagr=float((ser.iloc[-1] / ser.iloc[0]) ** (1 / yrs_) - 1),
                         dd=float(-(ser / ser.cummax() - 1).min()))
    out["subperiods"][f"{a_[:4]}-{z_[:4]}"] = row
    print(f"  {a_[:4]}-{z_[:4]}  base {row['base']['cagr']*100:6.2f}/{row['base']['dd']*100:5.2f}  "
          f"combo {row['combo']['cagr']*100:6.2f}/{row['combo']['dd']*100:5.2f}")

# ------------------------------------------------------------------ monthly + rolling
base_eq = out["variants"]["base"]["10y"]["eq"].groupby(lambda x: x.date()).last()
cand_eq = out["variants"]["combo"]["10y"]["eq"].groupby(lambda x: x.date()).last()
i0 = S.bt.start_index(ts, S.START10)
bench_d = pd.Series(c[:, 1][i0:], index=ts[i0:]).groupby(lambda x: x.date()).last()
for ser in (base_eq, cand_eq, bench_d):
    ser.index = pd.to_datetime(ser.index)
roll = S.rolling3(cand_eq, bench_d, base_eq)
out["rolling"] = dict(windows=roll,
                      n=len(roll),
                      beats_tqqq=int(sum(r["beats_bench"] for r in roll)),
                      beats_winner=int(sum(r["beats_winner"] for r in roll)),
                      median_cagr=float(np.median([r["cagr"] for r in roll])),
                      median_dd=float(np.median([r["dd"] for r in roll])),
                      median_winner_cagr=float(np.median([r["winner_cagr"] for r in roll])),
                      median_winner_dd=float(np.median([r["winner_dd"] for r in roll])),
                      median_tqqq_cagr=float(np.median([r["bench_cagr"] for r in roll])),
                      median_tqqq_dd=float(np.median([r["bench_dd"] for r in roll])))
print("=" * 110)
print(f"ROLLING 3Y: {len(roll)} windows; beats TQQQ {out['rolling']['beats_tqqq']}, "
      f"beats winner {out['rolling']['beats_winner']}; "
      f"median CAGR {out['rolling']['median_cagr']*100:.2f}% vs "
      f"{out['rolling']['median_winner_cagr']*100:.2f}% / "
      f"{out['rolling']['median_tqqq_cagr']*100:.2f}%")

# monthly
for name, ser in (("base", base_eq), ("combo", cand_eq)):
    m = ser.resample("ME").last().pct_change().dropna()
    out["variants"][name]["monthly"] = dict(
        positive_share=float((m > 0).mean()), mean=float(m.mean()), median=float(m.median()),
        worst=[[str(k.date()), float(v)] for k, v in m.sort_values().head(5).items()],
        best=[[str(k.date()), float(v)] for k, v in m.sort_values().tail(5).items()])
    print(f"{name} monthly: +{ (m>0).mean()*100:.1f}%  mean {m.mean()*100:+.2f}%  "
          f"worst {out['variants'][name]['monthly']['worst'][0]}")

# ------------------------------------------------------------------ attribution
base_d = base_eq.pct_change().dropna()
cand_d = cand_eq.pct_change().dropna()
idx = base_d.index.intersection(cand_d.index)
diff = np.log1p(cand_d.loc[idx]) - np.log1p(base_d.loc[idx])
blocked = set(pd.to_datetime([str(d) for d in D["combo"]["blocked_dates"]]).date)
tight = set(pd.to_datetime([str(d) for d in D["combo"]["tight_dates"]]).date)
tightstop = set(pd.to_datetime([str(d) for d in D["combo"]["tight_stop_dates"]]).date)
base_stop = set(A["dates"][i] for i in D["base"]["stops"])
rows = []
for d, v in diff.items():
    rows.append(dict(date=str(d.date()), logdiff=float(v),
                     blocked=d.date() in blocked, tight=d.date() in tight,
                     tight_stop=d.date() in tightstop, base_stop=d.date() in base_stop))
att = pd.DataFrame(rows)
att["year"] = att["date"].str[:4]
out["attribution"] = dict(
    total_logdiff=float(att["logdiff"].sum()),
    by_year={str(k): float(v) for k, v in att.groupby("year")["logdiff"].sum().items()},
    top_pos=att.sort_values("logdiff", ascending=False).head(15).drop(columns=["year"]).to_dict("records"),
    top_neg=att.sort_values("logdiff").head(15).drop(columns=["year"]).to_dict("records"),
    blocked_days=int(len(blocked)), tight_days=int(len(tight)), tight_stops=int(len(tightstop)),
)
print("=" * 110)
print("ATTRIBUTION (sum of daily log diff, pp):")
print({k: round(v * 100, 2) for k, v in out["attribution"]["by_year"].items()})
print("top + days:")
for r in out["attribution"]["top_pos"][:8]:
    print(f"  {r['date']} {r['logdiff']*100:+6.2f}pp  blocked={r['blocked']} tight={r['tight']} "
          f"tightstop={r['tight_stop']}")
print("top - days:")
for r in out["attribution"]["top_neg"][:8]:
    print(f"  {r['date']} {r['logdiff']*100:+6.2f}pp  blocked={r['blocked']} tight={r['tight']} "
          f"tightstop={r['tight_stop']}")

# ------------------------------------------------------------------ bootstrap monthly
m_base = base_eq.resample("ME").last().pct_change().dropna()
m_cand = cand_eq.resample("ME").last().pct_change().dropna()
mi = m_base.index.intersection(m_cand.index)
ld = np.log1p(m_cand.loc[mi]) - np.log1p(m_base.loc[mi])
rng = np.random.default_rng(7)
n = len(ld)
draws = rng.choice(ld.to_numpy(), size=(5000, n), replace=True).sum(axis=1)
yrs_ = n / 12.0
ann = np.expm1(draws / yrs_)
out["bootstrap"] = dict(n_months=int(n), mean_monthly_logdiff=float(ld.mean()),
                        t_stat=float(ld.mean() / (ld.std(ddof=1) / np.sqrt(n))),
                        ann_diff_p05=float(np.percentile(ann, 5)),
                        ann_diff_p50=float(np.percentile(ann, 50)),
                        ann_diff_p95=float(np.percentile(ann, 95)),
                        prob_positive=float((ann > 0).mean()))
print("=" * 110)
print(f"BOOTSTRAP: monthly logdiff {ld.mean()*100:+.3f}%/mo  t={out['bootstrap']['t_stat']:.2f}  "
      f"annualized diff p05/p50/p95 = {out['bootstrap']['ann_diff_p05']*100:+.2f} / "
      f"{out['bootstrap']['ann_diff_p50']*100:+.2f} / {out['bootstrap']['ann_diff_p95']*100:+.2f} pp  "
      f"P(>0)={out['bootstrap']['prob_positive']*100:.1f}%")

# ------------------------------------------------------------------ load prior screens
for key, fn in (("grid", "sweep5.json"), ("same_day", "sweep1.json")):
    p = HERE / fn
    if p.exists():
        out[key] = json.loads(p.read_text())

# pass/fail
tq = {"10y": {"cagr": 0.3928, "dd": 0.8168}, "5y": {"cagr": 0.1347, "dd": 0.8168}}
b10, b5 = out["variants"]["base"]["10y"], out["variants"]["base"]["5y"]
q10, q5 = out["variants"]["combo"]["10y"], out["variants"]["combo"]["5y"]
out["pass"] = {
    "vs_tqqq": {"10y": bool(q10["cagr"] > tq["10y"]["cagr"] and q10["max_drawdown"] < tq["10y"]["dd"]),
                "5y": bool(q5["cagr"] > tq["5y"]["cagr"] and q5["max_drawdown"] < tq["5y"]["dd"])},
    "strict_dominance_vs_winner": {
        "10y": bool(q10["cagr"] > b10["cagr"] and q10["max_drawdown"] < b10["max_drawdown"]),
        "5y": bool(q5["cagr"] > b5["cagr"] and q5["max_drawdown"] < b5["max_drawdown"])},
    "lower_dd_within_2pp": {
        "10y": bool(q10["max_drawdown"] < b10["max_drawdown"] and q10["cagr"] > b10["cagr"] - 0.02),
        "5y": bool(q5["max_drawdown"] < b5["max_drawdown"] and q5["cagr"] > b5["cagr"] - 0.02)},
}
print("=" * 110)
print("PASS:", json.dumps(out["pass"], indent=1))

# drop equity series before writing
for grp in ("variants", "costs"):
    for name in out[grp]:
        for lab in ("10y", "5y"):
            if lab in out[grp][name]:
                out[grp][name][lab].pop("eq", None)
        if "10y" in out[grp][name] and "5y" in out[grp][name]:
            pass
for key in out["costs"]:
    for name in out["costs"][key]:
        for lab in ("10y", "5y"):
            out["costs"][key][name][lab].pop("eq", None)

(HERE / "result.json").write_text(json.dumps(clean(out), indent=2))
print("\nwrote result.json")
