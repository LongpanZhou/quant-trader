"""LETF overshoot recovery v2 — repair of `stop-reentry-recovery`.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded or inspected.

Original failure
----------------
The old signal required a 1 pp underperformance of TQQQ versus 3x QQQ.  The
intraday tracking residual has a 0.121 pp standard deviation, so that is an
~8-sigma condition: 3 days in 8 years, 1 event, 5 fills.  It also has no
forward edge (forward excess returns after those days are negative).

Repair
------
Keep the "large downside overshoot" idea, but normalize the drop by TQQQ's own
trailing 20-session volatility instead of the tiny QQQ tracking residual:

    r_t   = TQQQ_close[d] / TQQQ_open[d] - 1
    sd20  = std(r_t[d-20 .. d-1])
    z     = r_t / max(sd20, 0.005)
    event = (r_t <= -5.0%) AND (z <= -2.0)

Primary execution: buy 100% TQQQ at the next session's 09:31 open, sell at the
same session's 15:59 open (one-session hold), otherwise BIL.  The original
3-session 50%->100% scale-in with a 4% daily-close stop is grid cell 8.

The 165-day QQQ SMA appears only as a benchmark/correlation reference, never as
a gate.  No old weight matrix or old `build_weights` is imported.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/stop-reentry-recovery-v2/strategy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
BPY = 252 * 390

PARAMS = dict(drop=0.050, z_max=-2.0, z_n=20, hold=1, size=1.0,
              stop=0.0, daily_stop=True, addon=False, size1=1.0)

GRID = [
    ("1 primary 5.0%/2.0", dict(drop=0.050, z_max=-2.0, hold=1, size=1.0,
                                stop=0.0, addon=False)),
    ("2 drop 4.0%", dict(drop=0.040, z_max=-2.0, hold=1, size=1.0,
                         stop=0.0, addon=False)),
    ("3 drop 4.5%", dict(drop=0.045, z_max=-2.0, hold=1, size=1.0,
                         stop=0.0, addon=False)),
    ("4 drop 6.0%", dict(drop=0.060, z_max=-2.0, hold=1, size=1.0,
                         stop=0.0, addon=False)),
    ("5 z -1.75", dict(drop=0.050, z_max=-1.75, hold=1, size=1.0,
                       stop=0.0, addon=False)),
    ("6 z -2.25", dict(drop=0.050, z_max=-2.25, hold=1, size=1.0,
                       stop=0.0, addon=False)),
    ("7 half size", dict(drop=0.050, z_max=-2.0, hold=1, size=0.5,
                         stop=0.0, addon=False)),
    ("8 original structure", dict(drop=0.050, z_max=-2.0, hold=3, size=0.5,
                                  size1=1.0, stop=0.04, addon=True)),
]


# ---------------------------------------------------------------------------
# daily features / signal
# ---------------------------------------------------------------------------
def daily_features(ts, op, cl, z_n=20):
    dates, first, last = bt.day_bounds(ts)
    do = op[first]
    dc = cl[last]
    r_t = dc[:, 1] / do[:, 1] - 1.0
    r_q = dc[:, 0] / do[:, 0] - 1.0
    sd = pd.Series(r_t).rolling(z_n).std(ddof=0).shift(1).to_numpy()
    z = r_t / np.maximum(sd, 0.005)
    return dict(dates=dates, first=first, last=last, do=do, dc=dc,
                r_t=r_t, r_q=r_q, sd=sd, z=z,
                session_dates=np.array([d for d in dates[first]]))


def signal_mask(f, drop, z_max):
    finite = np.isfinite(f["z"])
    return finite & (f["r_t"] <= -drop) & (f["z"] <= z_max)


def component_counts(f, excess=0.01):
    """Original and repaired component counts, for the diagnosis table."""
    r_t, r_q, z = f["r_t"], f["r_q"], f["z"]
    excess_ret = r_t - 3.0 * r_q
    finite = np.isfinite(excess_ret) & np.isfinite(z)
    return dict(
        sessions=int(len(r_t)),
        old_drop_3pct=int(np.nansum(r_t <= -0.03)),
        old_excess_1pp=int(np.nansum(excess_ret <= -excess)),
        old_conjunction=int(np.nansum((r_t <= -0.03) & (excess_ret <= -excess))),
        new_z_2sigma=int(np.nansum(z <= -2.0)),
        new_drop_5pct=int(np.nansum(r_t <= -0.05)),
        new_conjunction=int(np.nansum(finite & (r_t <= -0.05) & (z <= -2.0))),
        excess_std_pp=float(np.nanstd(excess_ret) * 100),
    )


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def build_weights(ts, op, cl, params=None, mask=None):
    """Return (weights (n,3), info).  weights[i] fills at bar i+1's open."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    f = daily_features(ts, op, cl, int(p["z_n"]))
    nd, first, last = len(f["first"]), f["first"], f["last"]
    sig = signal_mask(f, p["drop"], p["z_max"])
    if mask is not None:
        sig = np.asarray(mask, bool) & np.isfinite(f["z"])

    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    pos = 0.0
    entry_day = -1
    hold_until = -1
    entry_px = np.nan
    addon_done = True
    stopped = False
    pending = False
    entries, stops, addons, signal_days = [], [], [], []

    for k in range(nd):
        f0, z0 = int(first[k]), int(last[k])
        m = z0 - f0 + 1

        # entry decided at the previous close, filled at this session's f0+1
        if pending and pos == 0.0:
            pos = float(p["size"])
            entry_day = k
            hold_until = k + int(p["hold"]) - 1
            entry_px = float(op[min(f0 + 1, z0), 1])
            addon_done = not bool(p["addon"])
            stopped = False
            pending = False
            entries.append(str(f["session_dates"][k]))

        # add-on at the 09:31 of the second session if the entry day closed up
        if pos > 0 and k == entry_day + 1 and not addon_done:
            addon_done = True
            if f["dc"][k - 1, 1] > f["do"][k - 1, 1]:
                pos = float(p["size1"])
                addons.append(str(f["session_dates"][k]))

        block = np.full(m, pos)

        # optional stop.  A minute-close stop is available, but the primary
        # uses no stop; cell 8 uses a daily-close stop.
        if p["stop"] > 0 and p["hold"] > 1:
            if p["daily_stop"]:
                if pos > 0 and k >= entry_day and f["dc"][k, 1] < entry_px * (1.0 - p["stop"]):
                    block[-1] = 0.0
                    pos = 0.0
                    stopped = True
                    stops.append(str(f["session_dates"][k]))
            else:
                start = 1 if k == entry_day else 0
                for j in range(start, m):
                    if pos > 0 and cl[f0 + j, 1] < entry_px * (1.0 - p["stop"]):
                        block[j:] = 0.0
                        pos = 0.0
                        stopped = True
                        stops.append(str(f["session_dates"][k]))
                        break

        # scheduled exit at the close of the last hold session
        if (not stopped) and pos > 0 and k == hold_until:
            block[-2:] = 0.0
            pos = 0.0

        w[f0:z0 + 1, 1] = block
        w[f0:z0 + 1, 2] = 1.0 - block

        # queue the next event only when flat and the current event is finished
        if sig[k] and pos == 0.0 and k >= hold_until:
            pending = True
        if sig[k]:
            signal_days.append(str(f["session_dates"][k]))

    info = dict(
        params={k: (bool(v) if isinstance(v, (bool, np.bool_)) else
                    (int(v) if isinstance(v, (int, np.integer)) else float(v)))
                for k, v in p.items()},
        signal_days=sorted(set(signal_days)),
        entries=len(entries),
        entry_dates=entries,
        stops=len(stops),
        stop_dates=stops,
        addons=len(addons),
        addon_dates=addons,
    )
    return w, info


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------
def dev_slice(ts, start=DEV_START, end=DEV_END):
    i = bt.start_index(ts, start)
    end_ts = pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
    j = int(ts.searchsorted(end_ts, side="left"))
    return slice(i, j)


def run_metrics(ts, op, cl, w, start=DEV_START, end=DEV_END, slip=1.0):
    s = dev_slice(ts, start, end)
    r = bt.simulate(ts[s], op[s], cl[s], w[s], band=0.02, slippage_bps=slip)
    st = bt.stats(r, BPY)
    st["tqqq_exposure"] = float(np.mean(w[s][:, 1]))
    return r, st


def daily_returns(result):
    eq = pd.Series(result["equity"], index=result["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def subperiods(ts, op, cl, w):
    out = {}
    for label, a, b in (("2016-2019", "2016-01-04", "2019-12-31"),
                        ("2020-2021", "2020-01-02", "2021-12-31"),
                        ("2022-2023", "2022-01-03", "2023-12-29")):
        _, s = run_metrics(ts, op, cl, w, a, b, 1.0)
        out[label] = {k: float(s[k]) for k in
                      ("cagr", "max_drawdown", "sharpe", "volatility",
                       "tqqq_exposure", "fills", "turnover")}
    return out


def event_study(f, sig, hold):
    """Forward TQQQ return from the next open to the close of d+hold."""
    idx = np.flatnonzero(sig)
    r, e = [], []
    for d in idx:
        if d + hold >= len(f["r_t"]):
            continue
        entry = f["do"][d + 1, 1]
        exit_ = f["dc"][d + hold, 1]
        r.append(exit_ / entry - 1.0)
        e.append((exit_ / entry - 1.0)
                 - 3.0 * (f["dc"][d + hold, 0] / f["do"][d + 1, 0] - 1.0))
    r = np.asarray(r)
    e = np.asarray(e)
    if len(r) < 3:
        return dict(n=int(len(r)))
    t = float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))) if r.std(ddof=1) > 0 else None
    rng = np.random.default_rng(7)
    boot = rng.choice(r, (20000, len(r)), replace=True).mean(axis=1)
    order = np.argsort(r)
    return dict(
        n=int(len(r)), mean=float(r.mean()), median=float(np.median(r)),
        win=float((r > 0).mean()), t=t, std=float(r.std(ddof=1)),
        bootstrap_p=float((boot <= 0).mean()),
        ci95_low=float(np.quantile(boot, 0.025)),
        ci95_high=float(np.quantile(boot, 0.975)),
        min=float(r.min()), max=float(r.max()),
        mean_ex_top5=float(r[order[:-5]].mean()) if len(r) > 5 else None,
        t_ex_top5=(float(r[order[:-5]].mean() / r[order[:-5]].std(ddof=1)
                          * np.sqrt(len(r) - 5))
                   if len(r) > 5 and r[order[:-5]].std(ddof=1) > 0 else None),
        excess_mean=float(e.mean()),
        excess_mean_pp=float(e.mean() * 100.0),
    )


def event_study_by_year(f, sig, hold):
    out = {}
    sd = f["session_dates"]
    idx = np.flatnonzero(sig)
    for d in idx:
        if d + hold >= len(f["r_t"]):
            continue
        yr = int(sd[d].year)
        r = f["dc"][d + hold, 1] / f["do"][d + 1, 1] - 1.0
        out.setdefault(yr, []).append(float(r))
    return {int(y): {"n": len(v), "mean": float(np.mean(v)),
                     "win": float(np.mean(np.asarray(v) > 0))}
            for y, v in sorted(out.items())}


def benchmark_weights(ts, cl, n=165):
    """165-day QQQ SMA baseline — benchmark/correlation only, never a gate."""
    dates, first, last = bt.day_bounds(ts)
    qc = cl[last, 0]
    sma = pd.Series(qc).rolling(n).mean().to_numpy()
    reg = np.zeros(len(first), bool)
    reg[1:] = qc[:-1] > sma[:-1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    w = np.zeros((len(ts), 3))
    w[:, 1] = reg[day_id].astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def placebo(ts, op, cl, f, sig, n_draws=200, seed=11):
    """Random same-size event sets, same hold/size, same costs."""
    n_sig = int(sig.sum())
    if n_sig < 1:
        return None
    nd = len(f["first"])
    hold = int(PARAMS["hold"])
    eligible = np.array([k for k in range(int(PARAMS["z_n"]) + 1, nd - hold - 1)
                         if str(f["session_dates"][k]) >= DEV_START])
    rng = np.random.default_rng(seed)
    cagrs, dds = [], []
    for _ in range(n_draws):
        pick = rng.choice(eligible, n_sig, replace=False)
        m = np.zeros(nd, bool)
        m[pick] = True
        wg, _ = build_weights(ts, op, cl, dict(PARAMS), mask=m)
        _, s = run_metrics(ts, op, cl, wg, DEV_START, DEV_END, 1.0)
        cagrs.append(float(s["cagr"]))
        dds.append(float(s["max_drawdown"]))
    cagrs = np.asarray(cagrs)
    real, _ = run_metrics(ts, op, cl,
                          build_weights(ts, op, cl, dict(PARAMS))[0],
                          DEV_START, DEV_END, 1.0)
    real_cagr = float(bt.stats(real, BPY)["cagr"])
    return dict(
        n_draws=int(n_draws), real_cagr=real_cagr,
        placebo_mean=float(np.mean(cagrs)), placebo_std=float(np.std(cagrs, ddof=1)),
        placebo_p95=float(np.quantile(cagrs, 0.95)),
        placebo_max=float(np.max(cagrs)),
        percentile=float((cagrs < real_cagr).mean()),
        p_value=float((cagrs >= real_cagr).mean()),
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ts, op, cl = bt.panel(SYMS, DEV_START, DEV_END, "1min")
    assert str(ts[-1].date()) <= DEV_END, "holdout data leaked into the panel"
    f = daily_features(ts, op, cl, PARAMS["z_n"])
    sd = f["session_dates"]
    dev_sessions = np.array([str(d) >= DEV_START for d in sd])

    sig = signal_mask(f, PARAMS["drop"], PARAMS["z_max"])
    sig_dev = sig & dev_sessions
    w, info = build_weights(ts, op, cl, dict(PARAMS))

    comp = component_counts(f)
    comp["old_events"] = 1
    comp["old_entries"] = 1
    comp["old_fills"] = 5

    s = dev_slice(ts)
    exp_dev = float(np.mean(w[s][:, 1]))
    long_sessions = int(sum(np.any(w[int(f["first"][k]):int(f["last"][k]) + 1, 1] > 0)
                            for k in range(len(f["first"])) if dev_sessions[k]))
    entries_dev = [d for d in info["entry_dates"] if d >= DEV_START]
    stops_dev = [d for d in info["stop_dates"] if d >= DEV_START]

    out = {
        "agent": "stop-reentry-recovery-v2",
        "original": "research/revisit/stop-reentry-recovery",
        "status": "pending",
        "idea": "Buy TQQQ after a volatility-normalized downside overshoot "
                "(TQQQ intraday <= -5% and <= -2 trailing-20d sigma), exit at "
                "the same session's close, otherwise BIL.",
        "hypothesis": "A large TQQQ down day that is unusual relative to its own "
                      "recent volatility is a forced-selling overshoot; the next "
                      "session's open-to-close return is positive.",
        "why_changed": "The original 1pp TQQQ-vs-3xQQQ underperformance filter is "
                       "an ~8-sigma event (residual sigma 0.121pp): 3 days, 1 event, "
                       "5 fills in 8 years, with no positive forward excess return. "
                       "The repair keeps the overshoot idea but normalizes the drop "
                       "by TQQQ's own trailing volatility.",
        "universe": ["TQQQ (long)", "BIL (cash)", "QQQ (signal only)"],
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "params": PARAMS,
        "diagnostics": {
            "component_counts": comp,
            "events": int(sig_dev.sum()),
            "entries": len(entries_dev),
            "stops": len(stops_dev),
            "addons": int(info["addons"]),
            "tqqq_exposure": exp_dev,
            "sessions_long": long_sessions,
            "signal_dates": [d for d in info["signal_days"]
                             if d >= DEV_START],
            "entry_dates": entries_dev,
            "stop_dates": stops_dev,
        },
        "event_study": {
            "h1": event_study(f, sig_dev, 1),
            "h3": event_study(f, sig_dev, 3),
            "h5": event_study(f, sig_dev, 5),
            "by_year_h1": event_study_by_year(f, sig_dev, 1),
        },
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "subperiods": {},
        "yearly": {},
        "grid": [],
        "benchmarks": {},
        "corr_vs_165d_baseline": None,
        "placebo": None,
        "verdict": None,
    }

    # cost ladder
    r1 = None
    for slip, tag in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r, st = run_metrics(ts, op, cl, w, DEV_START, DEV_END, slip)
        out["windows"]["dev"][tag] = {
            "cagr": float(st["cagr"]), "max_drawdown": float(st["max_drawdown"]),
            "sharpe": float(st["sharpe"]), "sortino": float(st["sortino"]),
            "volatility": float(st["volatility"]), "fills": int(st["fills"]),
            "turnover": float(st["turnover"]), "ending_equity": float(st["ending_equity"]),
            "tqqq_exposure": float(st["tqqq_exposure"]),
        }
        if slip == 1.0:
            r1 = r

    out["subperiods"] = subperiods(ts, op, cl, w)
    i = bt.start_index(ts, DEV_START)
    out["yearly"] = {int(k): {"strategy": float(v["strategy"]),
                              "benchmark": float(v["benchmark"])}
                     for k, v in bt.yearly(ts[i:], r1["equity"], cl[i:, 1]).items()}

    # benchmarks
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        b = bt.benchmark(cl[i:, col], ts[i:], BPY)
        out["benchmarks"][name] = {k: float(b[k]) for k in
                                   ("cagr", "max_drawdown", "volatility", "sharpe")}
    bw = benchmark_weights(ts, cl)
    rb, sb = run_metrics(ts, op, cl, bw, DEV_START, DEV_END, 1.0)
    out["benchmarks"]["baseline_165d"] = {
        "cagr": float(sb["cagr"]), "max_drawdown": float(sb["max_drawdown"]),
        "sharpe": float(sb["sharpe"]), "volatility": float(sb["volatility"]),
    }
    sr = daily_returns(r1)
    br = daily_returns(rb)
    j = sr.index.intersection(br.index)
    out["corr_vs_165d_baseline"] = float(np.corrcoef(sr.loc[j], br.loc[j])[0, 1])

    # pre-registered grid (1bp)
    for name, pp in GRID:
        wg, gi = build_weights(ts, op, cl, pp)
        _, sg = run_metrics(ts, op, cl, wg, DEV_START, DEV_END, 1.0)
        sg_dev = np.mean(wg[s][:, 1])
        out["grid"].append({
            "name": name, "params": {k: pp[k] for k in pp},
            "signals": len([d for d in gi["signal_days"] if d >= DEV_START]),
            "entries": len([d for d in gi["entry_dates"] if d >= DEV_START]),
            "stops": len([d for d in gi["stop_dates"] if d >= DEV_START]),
            "tqqq_exposure": float(sg_dev),
            "cagr": float(sg["cagr"]), "max_drawdown": float(sg["max_drawdown"]),
            "sharpe": float(sg["sharpe"]), "fills": int(sg["fills"]),
        })

    out["placebo"] = placebo(ts, op, cl, f, sig_dev, n_draws=200)

    # verdict
    dev1 = out["windows"]["dev"]["1bp"]
    h1 = out["event_study"]["h1"]
    bil = out["benchmarks"]["bil"]["cagr"]
    base_dd = out["benchmarks"]["baseline_165d"]["max_drawdown"]
    sub = out["subperiods"]
    neg = sum(1 for v in sub.values() if v["cagr"] <= 0)
    checks = {
        "enough_entries": out["diagnostics"]["entries"] >= 20,
        "forward_edge": h1["mean"] > 0 and h1["bootstrap_p"] <= 0.10,
        "not_top5": (h1.get("mean_ex_top5") or 0) > 0,
        "beats_bil_10bp": out["windows"]["dev"]["10bp"]["cagr"] > bil,
        "dd_below_baseline": dev1["max_drawdown"] < base_dd,
        "subperiods_not_two_negative": neg < 2,
        "placebo_95": out["placebo"]["percentile"] >= 0.95,
    }
    out["verdict"] = {"checks": checks, "n_checks_passed": int(sum(checks.values())),
                      "status": "passed_dev" if all(checks.values()) else "retired"}
    out["status"] = out["verdict"]["status"]
    out["status_note"] = (
        "Development-only event repair. Low TQQQ exposure (~2.8%) by design; "
        "the CAGR is not a broad equity beta. The relative TQQQ-vs-3xQQQ "
        "overshoot is falsified; the surviving claim is a volatility-normalized "
        "downside reversal."
    )

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"signals {out['diagnostics']['events']}  entries {out['diagnostics']['entries']}  "
          f"stops {out['diagnostics']['stops']}  exposure {exp_dev*100:.2f}%")
    for tag in ("1bp", "5bp", "10bp"):
        d = out["windows"]["dev"][tag]
        print(f"  {tag:4s} CAGR {d['cagr']*100:6.2f}%  DD {d['max_drawdown']*100:5.2f}%  "
              f"Sharpe {d['sharpe']:4.2f}  fills {d['fills']:3d}")
    print(f"  h1 mean {h1['mean']*100:+.3f}%  t {h1['t']:.2f}  p {h1['bootstrap_p']:.4f}  "
          f"placebo percentile {out['placebo']['percentile']*100:.1f}%")
    print(f"  subperiods: " + "  ".join(f"{k} {v['cagr']*100:+.1f}%" for k, v in sub.items()))
    print("  entry dates:", ", ".join(out["diagnostics"]["entry_dates"]))
    print("  verdict:", out["verdict"])
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
