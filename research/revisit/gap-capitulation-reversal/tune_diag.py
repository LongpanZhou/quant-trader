"""Tuning diagnostics (2026-11-27). DEV WINDOW ONLY (2016-01-04 -> 2023-12-29).

    python research/revisit/gap-capitulation-reversal/tune_diag.py [module]

`module` defaults to `strategy` (the current file); pass `_before_tune.strategy`
style paths via TUNE_MOD env to diagnose another version.  Writes
tune_diag_<tag>.json next to this file.  Never loads data after DEV_END.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402


def load_mod(path):
    spec = importlib.util.spec_from_file_location("gcr_" + Path(path).parent.name.replace("-", "_"), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def daily_eq(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last()


def trades(ts, o, c, w):
    """Contiguous runs of non-BIL weight.  Fill at next-bar open."""
    held = (w[:, 0] + w[:, 1]) > 0
    col = np.where(w[:, 1] > 0, 1, 0)
    out = []
    i, n = 0, len(ts)
    while i < n:
        if not held[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and held[j + 1] and col[j + 1] == col[i]:
            j += 1
        a = col[i]
        if i + 1 < n and j + 1 < n:
            ent, ex = o[i + 1, a], o[j + 1, a]
            out.append(dict(entry=str(ts[i + 1]), exit=str(ts[j + 1]),
                            asset="TQQQ" if a == 1 else "QQQ",
                            ret=float(ex / ent - 1.0), bars=int(j - i + 1)))
        i = j + 1
    return out


def main():
    os.environ.setdefault("BT_THREADS", "1")
    mod_path = os.environ.get("TUNE_MOD", str(HERE / "strategy.py"))
    tag = os.environ.get("TUNE_TAG", "current")
    S = load_mod(mod_path)
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    qlow, qvol = S.daily_extras(ts)
    w, info = S.build_weights(ts, o, c, qlow, qvol, S.PARAMS)
    i0 = bt.start_index(ts, S.DEV_START)
    tsd, od, cd, wd = ts[i0:], o[i0:], c[i0:], w[i0:]

    out = {"tag": tag}
    res = {}
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, o, c, w, S.DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, S.BARS_PER_YEAR)
        res[slip] = r
        out[f"{int(slip)}bp"] = {k: s[k] for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
    years = res[1.0]["ts"][-1] - res[1.0]["ts"][0]
    yrs = years.total_seconds() / (365.25 * 86400)
    out["trades_per_year"] = out["1bp"]["fills"] / yrs
    out["turnover_per_year"] = out["1bp"]["turnover"] / yrs
    out["cost_drag_1_to_10bp_pp"] = (out["1bp"]["cagr"] - out["10bp"]["cagr"]) * 100

    # exposure
    fq = float(np.mean(wd[:, 0] > 0)); ft = float(np.mean(wd[:, 1] > 0))
    fb = float(np.mean(wd[:, 2] > 0))
    gross = float(np.mean(wd[:, 0] + 3 * wd[:, 1]))
    out["exposure"] = dict(qqq=fq, tqqq=ft, bil=fb, synthetic_short=0.0, avg_gross_lev=gross)

    # daily series
    de = daily_eq(res[1.0]); sr = de.pct_change().dropna()
    def dclose(col):
        s = pd.Series(cd[:, col], index=tsd); return s.groupby(s.index.date).last()
    tq, qq, bil = dclose(1), dclose(0), dclose(2)
    rt, rq, rb = tq.pct_change().dropna(), qq.pct_change().dropna(), bil.pct_change().dropna()

    # leverage-matched static mixes, daily rebalance, no cost
    def mix(wt):
        r = wt * rt + (1 - wt) * rb
        eq = (1 + r).cumprod()
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        dd = float(-(eq / eq.cummax() - 1).min())
        return dict(w_tqqq=wt, cagr=float(cagr), max_dd_daily=dd,
                    sharpe=float(r.mean() / r.std() * np.sqrt(252)))
    out["lev_matched"] = {"gross/3": mix(gross / 3), "exposure_frac": mix(fq + ft),
                          "bil_only": mix(0.0)}

    # per-year
    py = {}
    for y in range(2016, 2024):
        m = [d.year == y for d in de.index]
        e = de[m]; prev = de[[d.year == y - 1 for d in de.index]]
        base = prev.iloc[-1] if len(prev) else 100000.0
        def yr(s):
            sm = s[[d.year == y for d in s.index]]; sp = s[[d.year == y - 1 for d in s.index]]
            b0 = sp.iloc[-1] if len(sp) else sm.iloc[0]
            return float(sm.iloc[-1] / b0 - 1)
        py[y] = dict(strategy=float(e.iloc[-1] / base - 1), tqqq=yr(tq), qqq=yr(qq), bil=yr(bil))
    out["per_year"] = py

    # sub-periods (CAGR, 1bp)
    sub = {}
    for a, b in (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"), ("2022-01-03", "2023-12-29")):
        s = de[(de.index >= pd.Timestamp(a).date()) & (de.index <= pd.Timestamp(b).date())]
        prev = de[de.index < pd.Timestamp(a).date()]
        s0 = prev.iloc[-1] if len(prev) else 100000.0
        y_ = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
        sub[f"{a[:4]}-{b[:4]}"] = float((s.iloc[-1] / s0) ** (1 / y_) - 1)
    out["subperiods_cagr"] = sub

    # where the gap comes from: TQQQ return on days held vs not
    held_day = pd.Series((wd[:, 0] + wd[:, 1]) > 0, index=tsd)
    held_day = held_day.groupby(held_day.index.date).any()
    hd = held_day.reindex(rt.index).fillna(False)
    out["gap"] = dict(
        days_held=int(hd.sum()), days_total=int(len(hd)),
        tqqq_logret_days_held=float(np.log1p(rt[hd]).sum()),
        tqqq_logret_days_out=float(np.log1p(rt[~hd]).sum()),
        tqqq_up_days_out=int(((rt > 0) & ~hd).sum()),
        strat_logret_days_held=float(np.log1p(sr.reindex(rt.index).fillna(0)[hd]).sum()),
        strat_logret_days_out=float(np.log1p(sr.reindex(rt.index).fillna(0)[~hd]).sum()),
    )

    tr = trades(tsd, od, cd, wd)
    rs = np.array([t["ret"] for t in tr])
    out["trades"] = dict(n=len(tr), hit=float((rs > 0).mean()) if len(rs) else None,
                         mean=float(rs.mean()) if len(rs) else None,
                         sum_ret=float(rs.sum()) if len(rs) else None,
                         by_asset={a: dict(n=int(sum(t["asset"] == a for t in tr)),
                                           mean=float(np.mean([t["ret"] for t in tr if t["asset"] == a]))
                                           if any(t["asset"] == a for t in tr) else None)
                                   for a in ("QQQ", "TQQQ")},
                         list=tr)
    out["info"] = {k: v for k, v in info.items() if k not in ("event_dates", "trade_dates")}
    out["event_dates"] = info["event_dates"]

    # correlation with 165d baseline
    bw = S.benchmark_weights(ts, c)
    rb_ = daily_eq(bt.run(ts, o, c, bw, S.DEV_START, 0.02, 1.0)).pct_change().dropna()
    j = sr.index.intersection(rb_.index)
    out["corr_165d"] = float(np.corrcoef(sr.loc[j], rb_.loc[j])[0, 1])

    p = HERE / f"tune_diag_{tag}.json"
    with open(p, "w", newline="\n", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    brief = {k: v for k, v in out.items() if k not in ("trades", "event_dates")}
    brief["trades"] = {k: v for k, v in out["trades"].items() if k != "list"}
    print(json.dumps(brief, indent=1, default=float))
    for t in tr:
        print(t)


if __name__ == "__main__":
    main()
