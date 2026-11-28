"""Shared plumbing for the external cross-asset TQQQ/BIL families.

Development window only: 2016-01-04 .. 2023-12-29.  Every external series is
truncated at DEV_END before a feature is formed; the 2024-2026 rows are never
read into a feature or a result.

Timing contract
---------------
A feature for session k uses external daily closes through the close of
session k.  The target row is written on the last 1-minute bar of session k
and `bt` fills it at the 09:30 open of session k+1.  This is the same contract
as `research/external.daily_targets_to_weights`; no bar after session k is
used to form the target.

All helpers are deliberately boring so the four family strategies only contain
their signal logic, not four copies of the metrics code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import external  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2
BAND = 0.02
SLIPS = (1.0, 5.0, 10.0)
BPY_1M = 252 * 390
BPY_1D = 252

# Published TQQQ development bar used by the existing research programme.
BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}

WINNERS = [
    "ratio-froth",
    "vol-scaled-crash-stop",
    "relative-value-tqqq",
    "fomc-opex-window",
    "family-session-timing",
    "family-short-reversal",
    "family-rebalance-flow",
    "family-intraday-microstructure-day",
    "family-ml-microstructure",
]


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_panel():
    """1-minute QQQ/TQQQ/BIL panel, physically restricted to the dev window."""
    return bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=0)


def local_daily(symbol: str) -> pd.Series:
    """Local Yahoo daily adjusted close.

    The full series is returned; `daily_panel` only takes rows strictly before
    the passed panel's first session plus rows on that panel's session
    calendar, so a development panel cannot see a 2024+ value.
    """
    df = pd.read_parquet(bt.DATA_DIR / f"{symbol}-1d-yahoo.parquet")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    s = df.set_index("date")["adjclose"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def daily_panel(ts: pd.DatetimeIndex, symbols: list[str]) -> pd.DataFrame:
    """External daily closes plus a pre-panel warmup, aligned to sessions.

    The returned frame contains (a) external rows strictly before the first
    session of the *passed panel*, used only to warm up rolling features, and
    (b) one row per session of that panel.  No future row can enter: `live` is
    reindexed to the panel's session calendar and `hist` is strictly before
    its first session.  The caller decides the panel end.  `main()` passes the
    development panel (end 2023-12-29); a separate one-shot holdout can pass a
    longer panel, but this study never does.
    """
    idx = external.session_index(ts)
    ext_syms = [s for s in symbols if s != "QQQ"]

    live = external.align(ts, ext_syms) if ext_syms else pd.DataFrame(index=idx)
    hist = pd.DataFrame({s: external.load(s) for s in ext_syms}) if ext_syms else pd.DataFrame()

    if "QQQ" in symbols:
        q = local_daily("QQQ")
        if len(hist):
            hist["QQQ"] = q.reindex(hist.index).ffill()
        live["QQQ"] = q.reindex(idx).ffill()

    if len(hist):
        hist = hist.loc[hist.index < idx[0]]
        hist = hist.loc[hist.index >= idx[0] - pd.Timedelta(days=730)]
    out = pd.concat([hist, live]).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def session_slice(series: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """Feature computed on the warmup+session frame, sliced to sessions."""
    return series.reindex(idx).ffill()


def binary_targets(on: np.ndarray) -> np.ndarray:
    """Rows [QQQ, TQQQ, BIL] for a TQQQ/BIL switch."""
    on = np.asarray(on, dtype=float)
    t = np.zeros((len(on), 3), dtype=float)
    t[:, CT] = on
    t[:, CB] = 1.0 - on
    return t


def ternary_targets(state: np.ndarray) -> np.ndarray:
    """Rows [QQQ, TQQQ, BIL]; state 0=BIL, 1=TQQQ, 2=QQQ."""
    state = np.asarray(state, dtype=int)
    t = np.zeros((len(state), 3), dtype=float)
    t[:, CQ] = (state == 2)
    t[:, CT] = (state == 1)
    t[:, CB] = (state == 0)
    return t


def event_hold(ev: np.ndarray, hold: int) -> np.ndarray:
    """True for `hold` sessions starting at each True in `ev`."""
    ev = np.asarray(ev, dtype=bool)
    out = np.zeros(len(ev), dtype=bool)
    for i in np.flatnonzero(ev):
        out[i:i + int(hold)] = True
    return out


# --------------------------------------------------------------------------- #
# simulation and metrics
# --------------------------------------------------------------------------- #
def bounds(ts: pd.DatetimeIndex, lo: str = DEV_START, hi: str = DEV_END):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York")
                            + pd.Timedelta(days=1)))
    return i, j


def run_range(ts, o, c, w, lo=DEV_START, hi=DEV_END, bp=1.0, fill_log=False):
    i, j = bounds(ts, lo, hi)
    return bt.simulate(
        ts[i:j], o[i:j], c[i:j], w[i:j],
        band=BAND, slippage_bps=bp, start_equity=bt.START_EQUITY,
        fill_log=fill_log,
    )


def _daily_returns(res):
    eq = bt.daily_last(res["equity"], res["ts"])
    return eq, eq.pct_change().dropna()


def stats_block(ts, o, c, w, bp=1.0, lo=DEV_START, hi=DEV_END):
    i, j = bounds(ts, lo, hi)
    res = run_range(ts, o, c, w, lo, hi, bp)
    s = bt.stats(res, BPY_1M)
    eqd, r = _daily_returns(res)
    ww = np.asarray(w[i:j])
    out = {
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "exposure": float(s["exposure"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "ending_equity": float(s["ending_equity"]),
        "years": float(s["years"]),
        "daily_vol": float(r.std() * np.sqrt(BPY_1D)) if len(r) > 2 else None,
        "daily_sharpe": (float(r.mean() / r.std() * np.sqrt(BPY_1D))
                         if len(r) > 2 and r.std() > 0 else None),
        "tqqq_exposure": float(ww[:, CT].mean()),
        "bil_exposure": float(ww[:, CB].mean()),
        "qqq_exposure": float(ww[:, CQ].mean()),
        "days": int(len(eqd)),
        "start": str(eqd.index[0].date()),
        "end": str(eqd.index[-1].date()),
    }
    return out, res, eqd


def activity(targets: np.ndarray) -> dict:
    """Trade/state counts from a per-session target matrix."""
    t = np.asarray(targets)
    state = np.argmax(t, axis=1)
    is_t = state == CT
    switches = int(np.sum(state[1:] != state[:-1]))
    entries = int(is_t[0]) + int(np.sum((~is_t[:-1]) & is_t[1:]))
    exits = int(np.sum(is_t[:-1] & (~is_t[1:])))
    runs = []
    cur = 0
    for x in is_t:
        if x:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {
        "state_switches": switches,
        "tqqq_entries": entries,
        "tqqq_exits": exits,
        "tqqq_runs": len(runs),
        "tqqq_hold_sessions": int(is_t.sum()),
        "tqqq_exposure": float(is_t.mean()),
        "bil_exposure": float((state == CB).mean()),
        "qqq_exposure": float((state == CQ).mean()),
        "avg_hold_sessions": float(is_t.sum() / entries) if entries else None,
        "median_hold_sessions": float(np.median(runs)) if runs else None,
        "max_hold_sessions": int(max(runs)) if runs else None,
        "min_hold_sessions": int(min(runs)) if runs else None,
        "independent_events": switches,
    }


def subperiod_block(ts, o, c, w):
    out = {}
    for name, lo, hi in (
        ("2016-2019", "2016-01-04", "2019-12-31"),
        ("2020-2021", "2020-01-01", "2021-12-31"),
        ("2022-2023", "2022-01-01", "2023-12-29"),
    ):
        s, _, _ = stats_block(ts, o, c, w, 1.0, lo, hi)
        out[name] = s
    return out


def _tqqq_session_close(ts, c):
    dates, first, last = bt.day_bounds(ts)
    return pd.Series(c[last, CT], index=pd.to_datetime(dates[last]))


def yearly_table(ts, c, eqd):
    tq = _tqqq_session_close(ts, c)
    out = {}
    prev_e = prev_q = None
    for y in range(2016, 2024):
        e = eqd[eqd.index.year == y]
        q = tq[tq.index.year == y]
        if len(e) < 2 or len(q) < 2:
            continue
        base_e = prev_e if prev_e is not None else e.iloc[0]
        base_q = prev_q if prev_q is not None else q.iloc[0]
        out[str(y)] = {
            "strategy": float(e.iloc[-1] / base_e - 1.0),
            "tqqq": float(q.iloc[-1] / base_q - 1.0),
        }
        prev_e, prev_q = e.iloc[-1], q.iloc[-1]
    return out


def archive_daily_returns(slug: str) -> pd.Series:
    """Archived dev curve parsed only through DEV_END.

    The curve JSON also contains 2024-2026 values.  We locate the development
    cut from the date strings and read only the first `n` numeric values, so
    the holdout numbers are never converted to floats or used.
    """
    path = ROOT / "research" / "new" / "curves" / f"{slug}.json"
    text = path.read_text(encoding="utf-8")
    ds = text.index('"dates": [') + len('"dates": [')
    de = text.index("]", ds)
    dates = pd.to_datetime([x.strip().strip('"') for x in text[ds:de].split(",")])
    n = int((dates <= pd.Timestamp(DEV_END)).sum())
    vs = text.index('"values": [') + len('"values": [')
    vals = np.fromstring(text[vs:], sep=",", count=n)
    return pd.Series(vals, index=dates[:n]).pct_change()


def correlation_block(ts, c, eqd):
    tq = _tqqq_session_close(ts, c)
    r = eqd.pct_change().dropna()
    tqr = tq.pct_change()
    both = pd.DataFrame({"r": r, "tq": tqr}).dropna()
    out = {
        "corr_tqqq": float(both["r"].corr(both["tq"])),
        "beta_tqqq": float(np.cov(both["r"], both["tq"])[0, 1] / np.var(both["tq"])),
        "winners": {},
    }
    for slug in WINNERS:
        rr = archive_daily_returns(slug).dropna()
        idx = r.index.intersection(rr.index)
        out["winners"][slug] = {
            "corr": float(r.loc[idx].corr(rr.loc[idx])),
            "n": int(len(idx)),
        }
    vals = [v["corr"] for v in out["winners"].values()]
    out["winner_corr_min"] = float(min(vals))
    out["winner_corr_max"] = float(max(vals))
    out["winner_corr_mean"] = float(np.mean(vals))
    out["max_slug"] = max(out["winners"], key=lambda k: out["winners"][k]["corr"])
    return out


def placebo_block(ts, o, c, targets, feature, target_fn, n=100, seed=20261127):
    """Circular-shift nulls.

    shift_target preserves each holding length and the full exposure path but
    destroys alignment with returns.  shift_feature preserves the marginal
    distribution of the primary object but destroys its date alignment.
    """
    true_s, _, _ = stats_block(ts, o, c, external.daily_targets_to_weights(ts, targets), 1.0)
    true = true_s["cagr"]
    rng = np.random.default_rng(seed)
    nd = len(targets)

    def draw(kind):
        vals = []
        for k in rng.integers(40, nd - 40, n):
            k = int(k)
            if kind == "target":
                t = np.roll(targets, k, axis=0)
            else:
                t = target_fn(np.roll(feature, k))
            w = external.daily_targets_to_weights(ts, t)
            s, _, _ = stats_block(ts, o, c, w, 1.0)
            vals.append(s["cagr"])
        vals = np.asarray(vals)
        return {
            "n": int(len(vals)),
            "mean": float(vals.mean()),
            "median": float(np.median(vals)),
            "p5": float(np.percentile(vals, 5)),
            "p95": float(np.percentile(vals, 95)),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "true": float(true),
            "percentile": float((vals < true).mean()),
            "p_one_sided": float((np.sum(vals >= true) + 1) / (len(vals) + 1)),
        }

    return {"shift_target": draw("target"), "shift_feature": draw("feature")}


def benchmark_block(ts, o, c):
    w = np.tile([0.0, 1.0, 0.0], (len(ts), 1))
    r = bt.simulate(ts, o, c, w, band=BAND, slippage_bps=1.0,
                    start_equity=bt.START_EQUITY)
    s = bt.stats(r, BPY_1M)
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "fills", "turnover", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def drawdown_episode(ts, res):
    eq = res["equity"]
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    t = int(np.argmin(dd))
    p = int(np.argmax(eq[:t + 1]))
    rec = None
    if np.any(eq[t:] >= peak[p]):
        rec = str(pd.Timestamp(ts[t + int(np.argmax(eq[t:] >= peak[p]))]))
    return {
        "depth": float(-dd[t]),
        "peak": str(pd.Timestamp(ts[p])),
        "trough": str(pd.Timestamp(ts[t])),
        "recovery": rec,
    }


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    return obj


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(clean(obj), indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# report rendering
# --------------------------------------------------------------------------- #
def _p(x, n=2):
    return "—" if x is None else f"{x * 100:.{n}f}%"


def _f(x, n=2):
    return "—" if x is None else f"{x:.{n}f}"


def _i(x):
    return "—" if x is None else f"{int(x):,}"


def _stats_row(label, s):
    return (f"| {label} | {_p(s['cagr'])} | {_p(s['max_drawdown'])} | "
            f"{_f(s['sharpe'])} | {_f(s['sortino'])} | {_p(s['volatility'])} | "
            f"{_p(s['exposure'], 1)} | {_i(s['fills'])} | {_f(s['turnover'], 0)}x |")


def render_report(result: dict, narrative: dict) -> str:
    w1 = result["windows"]["1bp"]
    w5 = result["windows"]["5bp"]
    w10 = result["windows"]["10bp"]
    bench = result["benchmarks"]["tqqq_buy_hold"]
    bar = result["bar"]
    act = result["activity"]
    pl = result["plateau"]
    pl_pass = sum(1 for x in pl if x["passes_bar"])
    corr = result["corr_winners"]
    cs = result["corr_summary"]
    plc = result["placebo"]

    lines = []
    lines.append(f"# {narrative['title']}")
    lines.append("")
    lines.append(f"**Family:** `{result['family']}`  ")
    lines.append(f"**Slug:** `{result['agent']}`  ")
    lines.append(f"**Development window:** {result['window']['dev'][0]} .. "
                 f"{result['window']['dev'][1]}  ")
    lines.append("**Status:** dev-only; no 2024–2026 result was computed in this "
                 "study.  The development panel ends 2023-12-29.  `build_weights` "
                 "accepts a longer panel for a separate one-shot holdout, but no "
                 "such run is part of this report.")
    lines.append("")
    lines.append("## 1. Hypothesis")
    lines.append("")
    lines.append(narrative["hypothesis"])
    lines.append("")
    lines.append("### Mechanism")
    lines.append("")
    lines.append(narrative["mechanism"])
    lines.append("")
    lines.append("### Why this is a distinct family")
    lines.append("")
    lines.append(narrative["distinctness"])
    lines.append("")
    lines.append("## 2. Signal and execution")
    lines.append("")
    lines.append(f"**External series:** {', '.join(result['external'])}  ")
    lines.append(f"**Primary parameters:** `{result['params']}`")
    lines.append("")
    lines.append(narrative["signal"])
    lines.append("")
    lines.append("**Execution contract.** The target for session *k* is written on "
                 "the last 1-minute bar of session *k* and filled at the 09:30 open "
                 "of session *k+1*.  The external close of session *k* is the "
                 "latest daily print used; no bar after *k* enters the signal.  "
                 "Idle capital is BIL; the book is long-only, weights ≥ 0, row "
                 "sum ≤ 1, 2% rebalance band, headline 1 bp, also 5/10 bp.")
    lines.append("")
    lines.append("## 3. Development results")
    lines.append("")
    lines.append("### 3.1 Headline")
    lines.append("")
    lines.append("| Book | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(_stats_row("Primary, 1 bp", w1))
    lines.append(_stats_row("Primary, 5 bp", w5))
    lines.append(_stats_row("Primary, 10 bp", w10))
    lines.append(f"| TQQQ buy & hold | {_p(bench['cagr'])} | {_p(bench['max_drawdown'])} | "
                 f"{_f(bench['sharpe'])} | {_f(bench['sortino'])} | {_p(bench['volatility'])} | "
                 f"{_p(bench['exposure'], 1)} | {_i(bench['fills'])} | {_f(bench['turnover'], 0)}x |")
    lines.append(f"| Published dev bar | {_p(bar['cagr'])} | {_p(bar['max_drawdown'])} | "
                 f"{_f(bar['sharpe'])} | — | — | — | — | — |")
    lines.append("")
    lines.append(narrative["result_comment"])
    lines.append("")
    lines.append("### 3.2 Activity and exposure")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Full fills at 1 bp | {act['fills']} |")
    lines.append(f"| State switches / independent events | {act['state_switches']} |")
    lines.append(f"| TQQQ entries / exits | {act['tqqq_entries']} / {act['tqqq_exits']} |")
    lines.append(f"| TQQQ holding sessions | {act['tqqq_hold_sessions']} |")
    lines.append(f"| Median TQQQ run | {_f(act['median_hold_sessions'], 1)} sessions |")
    lines.append(f"| Max TQQQ run | {act['max_hold_sessions']} sessions |")
    lines.append(f"| TQQQ / BIL / QQQ exposure | {_p(act['tqqq_exposure'], 1)} / "
                 f"{_p(act['bil_exposure'], 1)} / {_p(act['qqq_exposure'], 1)} |")
    floor = act["fills"] >= 100 or act["state_switches"] >= 30
    lines.append(f"| Activity floor (≥100 fills or ≥30 events) | "
                 f"{'PASS' if floor else 'FAIL'} |")
    lines.append("")
    lines.append("### 3.3 Subperiods (1 bp)")
    lines.append("")
    lines.append("| Subperiod | CAGR | Max DD | Sharpe | Sortino | Fills | TQQQ exposure |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, s in result["subperiods"].items():
        lines.append(f"| {name} | {_p(s['cagr'])} | {_p(s['max_drawdown'])} | "
                     f"{_f(s['sharpe'])} | {_f(s['sortino'])} | {_i(s['fills'])} | "
                     f"{_p(s['tqqq_exposure'], 1)} |")
    lines.append("")
    lines.append("### 3.4 Yearly returns")
    lines.append("")
    lines.append("| Year | Strategy | TQQQ |")
    lines.append("|---|---:|---:|")
    for y, v in result["yearly"].items():
        lines.append(f"| {y} | {_p(v['strategy'])} | {_p(v['tqqq'])} |")
    lines.append("")
    lines.append("### 3.5 Worst drawdown")
    lines.append("")
    dd = result["drawdown"]
    lines.append(f"Depth **{_p(dd['depth'])}**, peak {dd['peak']}, trough "
                 f"{dd['trough']}, recovery {dd['recovery'] or 'not recovered in dev'}.")
    lines.append("")
    lines.append("## 4. Robustness")
    lines.append("")
    lines.append("### 4.1 Eight-cell plateau")
    lines.append("")
    lines.append("| Cell | CAGR | Max DD | Sharpe | Fills | TQQQ exposure | 3-way bar |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for x in pl:
        ps = ", ".join(f"{k}={v}" for k, v in x["params"].items())
        lines.append(f"| {ps} | {_p(x['cagr'])} | {_p(x['max_drawdown'])} | "
                     f"{_f(x['sharpe'])} | {_i(x['fills'])} | {_p(x['tqqq_exposure'], 1)} | "
                     f"{'PASS' if x['passes_bar'] else 'fail'} |")
    lines.append("")
    lines.append(f"**Plateau:** {pl_pass}/{len(pl)} cells clear the three-way dev bar "
                 f"(CAGR > {_p(bar['cagr'])}, DD < {_p(bar['max_drawdown'])}, "
                 f"Sharpe > {_f(bar['sharpe'])}).")
    lines.append("")
    lines.append(narrative["plateau_comment"])
    lines.append("")
    n_extra = 1 if result.get("extra_checks") else 0
    if n_extra:
        lines.append("### 4.2 Additional checks")
        lines.append("")
        for name, block in result["extra_checks"].items():
            lines.append(f"**{name}**")
            lines.append("")
            if isinstance(block, dict):
                lines.append("| Item | CAGR | Max DD | Sharpe | Fills |")
                lines.append("|---|---:|---:|---:|---:|")
                for k, v in block.items():
                    if isinstance(v, dict) and "cagr" in v:
                        lines.append(f"| {k} | {_p(v['cagr'])} | {_p(v['max_drawdown'])} | "
                                     f"{_f(v['sharpe'])} | {_i(v['fills'])} |")
            lines.append("")
            if narrative.get(f"extra_{name}"):
                lines.append(narrative[f"extra_{name}"])
                lines.append("")
    lines.append(f"### 4.{3 if n_extra else 2} Placebo / randomized signal dates")
    lines.append("")
    lines.append("| Null | Mean CAGR | Median | 5th pct | 95th pct | True | Percentile | One-sided p |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, label in (("shift_target", "Circular shift of target"),
                        ("shift_feature", "Circular shift of primary feature")):
        z = plc[name]
        lines.append(f"| {label} | {_p(z['mean'])} | {_p(z['median'])} | {_p(z['p5'])} | "
                     f"{_p(z['p95'])} | {_p(z['true'])} | {z['percentile']:.2f} | "
                     f"{z['p_one_sided']:.3f} |")
    lines.append("")
    lines.append(narrative["placebo_comment"])
    lines.append("")
    lines.append(f"### 4.{4 if n_extra else 3} Correlation with the nine existing winners")
    lines.append("")
    lines.append("| Winner | Correlation | n |")
    lines.append("|---|---:|---:|")
    for slug, v in sorted(corr.items(), key=lambda kv: -kv[1]["corr"]):
        lines.append(f"| `{slug}` | {v['corr']:.3f} | {v['n']} |")
    lines.append("")
    lines.append(f"Range **{cs['min']:.3f} .. {cs['max']:.3f}** (mean {cs['mean']:.3f}); "
                 f"highest with `{result['corr_summary']['max_slug']}`.  "
                 f"Correlation with TQQQ itself is **{result['corr_tqqq']['corr']:.3f}** "
                 f"(beta {result['corr_tqqq']['beta']:.2f}).")
    lines.append("")
    lines.append(narrative["corr_comment"])
    lines.append("")
    lines.append("## 5. Kill criteria")
    lines.append("")
    lines.append("| # | Criterion | Observed | Triggered |")
    lines.append("|---|---|---|---|")
    for i, k in enumerate(result["kill_criteria"], 1):
        lines.append(f"| {i} | {k['rule']} | {k['observed']} | "
                     f"{'YES' if k['triggered'] else 'no'} |")
    lines.append("")
    trig = [k for k in result["kill_criteria"] if k["triggered"]]
    lines.append(f"**{len(trig)} of {len(result['kill_criteria'])} kill criteria triggered.**")
    lines.append("")
    lines.append("## 6. Honest verdict")
    lines.append("")
    lines.append(narrative["verdict"])
    lines.append("")
    lines.append("## 7. Limitations and next steps")
    lines.append("")
    lines.append(narrative["limitations"])
    lines.append("")
    lines.append("## 8. Reproduction")
    lines.append("")
    lines.append("```powershell")
    lines.append('$env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"')
    lines.append('$env:BT_THREADS = "1"')
    lines.append(f"python research/new/{result['agent']}/strategy.py")
    lines.append("```")
    lines.append("")
    lines.append("The script rebuilds `result.json` and this report from the "
                 "development window only.")
    lines.append("")
    return "\n".join(lines)
