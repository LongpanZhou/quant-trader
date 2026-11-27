"""Volatility-Shock Recovery (VSR) -- standalone rebuild of dynamic-leverage-throttle.

DESIGN / PRE-REGISTERED CODE.  Backtests are paused (2026-11-26): do not run
this file until the lead authorises the new test.  No result.json has been
produced for this version.

Idea
----
The old strategy was inverse-volatility sizing bolted onto the shared 165-day
QQQ SMA regime and the round-1 4% minute stop.  Here volatility owns the whole
position.  The strategy is episodic:

  * a volatility shock (v20 >= 1.25 * v60),
  * with the shock decaying (v5 <= 0.85 * v20),
  * and the market in a drawdown (-35% <= QQQ 252-day drawdown <= -8%),

is the state in which forced deleveraging is ending.  Buy TQQQ at the next
open, sized by w = min(0.75, 0.30 / v20), and hold for weeks until volatility
normalises, the market recovers, volatility re-accelerates, or a time stop.
BIL otherwise.

There is no 165-day moving-average gate in the strategy.  The only use of the
165-day baseline is the benchmark/correlation function at the bottom, which is
never called by build_weights().

Run (only after authorisation):
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/revisit/dynamic-leverage-throttle/strategy.py
"""
from __future__ import annotations

import itertools
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
BARS = 252 * 390

PARAMS = dict(
    shock_mult=1.25,     # v20 >= shock_mult * v60
    decay_ratio=0.85,    # v5 <= decay_ratio * v20
    dd_entry=-0.08,      # QQQ 252d drawdown at or below this
    dd_crash=-0.35,      # ... but not below this
    target_vol=0.30,     # inverse-vol target
    max_weight=0.75,
    dd_exit=-0.03,       # exit when recovered to within 3% of the high
    vol_norm=1.05,       # exit when v20 <= vol_norm * v60
    reaccel=1.10,        # exit when v5 >= reaccel * v20
    use_reaccel=False,   # tuning 2026-11-27: re-acceleration exit dropped (see DIAGNOSIS.md)
    dd_stop=-0.40,       # catastrophe exit
    time_stop=60,        # sessions
    cooldown=5,          # sessions after an exit
    resize_every=5,      # sessions
    band=0.02,
    use_shock=True,
    use_decay=True,
    use_dd=True,
    always_on=False,     # ablation: stripped continuous vol target
    warmup_daily=True,   # tuning fix: pre-2016 daily history for indicators
)


# --------------------------------------------------------------------------- #
# data / indicators
# --------------------------------------------------------------------------- #
def load_dev_panel():
    return bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")


_DATES_CACHE: dict = {}


def session_dates(ts: pd.DatetimeIndex) -> np.ndarray:
    """`bt.session_dates(ts)`, computed once per panel.

    The per-element conversion takes seconds on a 1-minute panel and the
    sweeps call it hundreds of times on the same timestamps.
    """
    i8 = ts.asi8
    key = (len(i8), int(i8[0]) if len(i8) else 0, int(i8[-1]) if len(i8) else 0,
           int(i8[::997].sum()) if len(i8) else 0, str(ts.tz))
    d = _DATES_CACHE.get(key)
    if d is None:
        d = bt.session_dates(ts)
        _DATES_CACHE.clear()
        _DATES_CACHE[key] = d
    return d


def day_bounds(dates):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def prev(a):
    return np.r_[np.nan, a[:-1]]


_PRE_CACHE: dict = {}


def daily_prehistory(first_date):
    """Adjusted daily QQQ/TQQQ closes strictly before the panel's first session.

    Tuning fix (2026-11-27): the 1-minute archive starts on 2016-01-04, so
    without this the 60-day vol and the 252-day high were undefined until
    2016-05-25 and the Jan-Feb 2016 drawdown could never be traded.  The daily
    Yahoo files (2015-01-02 on) are on the same adjusted basis as the minute
    bars (bt.load_1m scales minutes by adjclose/close).  Only dates before the
    first minute session are used, so this adds no information about any
    session in the panel.
    """
    key = str(first_date)
    if key in _PRE_CACHE:
        return _PRE_CACHE[key]
    out = []
    for sym in ("QQQ", "TQQQ"):
        df = pd.read_parquet(bt.DATA_DIR / f"{sym}-1d-yahoo.parquet")
        d = pd.to_datetime(df["date"])
        d = d.dt.tz_localize(None) if d.dt.tz is not None else d
        df = df.assign(_d=d.dt.date).sort_values("_d")
        df = df[df["_d"] < first_date]
        out.append(df.set_index("_d")["adjclose"])
    pre = pd.concat(out, axis=1, join="inner").dropna()
    res = (pre.iloc[:, 0].to_numpy(float), pre.iloc[:, 1].to_numpy(float))
    _PRE_CACHE.clear()
    _PRE_CACHE[key] = res
    return res


def daily_signals(ts, closes, warmup_daily=True):
    """Daily closes and causal indicators through each session's close."""
    dates = session_dates(ts)
    first, last = day_bounds(dates)
    dq, dt = closes[last, 0], closes[last, 1]
    npre = 0
    if warmup_daily and len(first):
        pq, pt = daily_prehistory(dates[first[0]])
        npre = len(pq)
        dq_all, dt_all = np.r_[pq, dq], np.r_[pt, dt]
    else:
        dq_all, dt_all = dq, dt
    rt = np.r_[np.nan, np.log(dt_all[1:] / dt_all[:-1])]

    def annvol(r, n):
        return pd.Series(r).rolling(n).std().to_numpy()[npre:] * np.sqrt(252)

    v5 = annvol(rt, 5)
    v20 = annvol(rt, 20)
    v60 = annvol(rt, 60)
    hi252 = pd.Series(dq_all).rolling(252, min_periods=100).max().to_numpy()[npre:]
    dd252 = dq / hi252 - 1.0
    return dict(dates=dates, first=first, last=last, dq=dq, dt=dt,
                v5=v5, v20=v20, v60=v60, dd252=dd252, n_prehistory=npre)


def size_for(v20, p):
    if not np.isfinite(v20) or v20 <= 0:
        return 0.0
    return float(min(p["max_weight"], p["target_vol"] / v20))


def entry_ok(k, sig, p):
    v5, v20, v60 = sig["v5"][k], sig["v20"][k], sig["v60"][k]
    dd = sig["dd252"][k]
    if not (np.isfinite(v5) and np.isfinite(v20) and np.isfinite(v60)
            and np.isfinite(dd)):
        return False
    if p["use_shock"] and not (v20 >= p["shock_mult"] * v60):
        return False
    if p["use_decay"] and not (v5 <= p["decay_ratio"] * v20):
        return False
    if p["use_dd"] and not (p["dd_crash"] <= dd <= p["dd_entry"]):
        return False
    return True


def exit_reason(k, entry_k, sig, p):
    v5, v20, v60 = sig["v5"][k], sig["v20"][k], sig["v60"][k]
    dd = sig["dd252"][k]
    if np.isfinite(v20) and np.isfinite(v60) and v20 <= p["vol_norm"] * v60:
        return "vol_normalised"
    if (p["use_reaccel"] and np.isfinite(v5) and np.isfinite(v20)
            and v5 >= p["reaccel"] * v20):
        return "vol_reaccelerating"
    if np.isfinite(dd) and dd >= p["dd_exit"]:
        return "recovered"
    if np.isfinite(dd) and dd <= p["dd_stop"]:
        return "catastrophe_stop"
    if (k - entry_k) >= p["time_stop"]:
        return "time_stop"
    return None


def to_minutes(sig, day_w):
    n = len(sig["dates"])
    day_id = np.repeat(np.arange(len(sig["first"])),
                       np.diff(np.r_[sig["first"], n]))
    return day_w[day_id]


# --------------------------------------------------------------------------- #
# strategy
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, params=None):
    """Return (minute weights, info).  Signal at close k, fill at k+1 open."""
    p = {**PARAMS, **(params or {})}
    sig = daily_signals(ts, closes, p["warmup_daily"])
    nd = len(sig["first"])
    day_w = np.zeros((nd, 3))
    day_w[:, 2] = 1.0
    info = dict(entries=[], exits=[], params=p, always_on=p["always_on"])

    if p["always_on"]:
        for k in range(nd):
            w = size_for(sig["v20"][k], p)
            day_w[k, 1] = w
            day_w[k, 2] = 1.0 - w
        info["exposure"] = float(np.mean(day_w[:, 1]))
        return to_minutes(sig, day_w), info

    holding = False
    entry_k = -1
    current_w = 0.0
    cooldown_until = -1

    for k in range(nd):
        # events at the close of session k affect session k+1
        if holding:
            reason = exit_reason(k, entry_k, sig, p)
            if reason is not None:
                if k + 1 < nd:
                    day_w[k + 1, 1] = 0.0
                    day_w[k + 1, 2] = 1.0
                info["exits"].append({
                    "session": int(k + 1),
                    "date": str(sig["dates"][sig["first"][k]]),
                    "reason": reason,
                    "held": int(k - entry_k),
                })
                holding = False
                current_w = 0.0
                cooldown_until = k + p["cooldown"]
            elif (k - entry_k) % p["resize_every"] == 0:
                current_w = size_for(sig["v20"][k], p)
        elif k >= cooldown_until and entry_ok(k, sig, p):
            holding = True
            entry_k = k
            current_w = size_for(sig["v20"][k], p)
            info["entries"].append({
                "session": int(k + 1),
                "date": str(sig["dates"][sig["first"][k]]),
                "dd252": float(sig["dd252"][k]),
                "v20": float(sig["v20"][k]),
                "weight": float(current_w),
            })

        if k + 1 < nd:
            day_w[k + 1, 1] = current_w if holding else 0.0
            day_w[k + 1, 2] = 1.0 - day_w[k + 1, 1]

    # close an open episode for reporting only
    if holding:
        info["open_at_end"] = True
        info["exits"].append({
            "session": int(nd), "date": str(sig["dates"][-1]),
            "reason": "end_of_sample", "held": int(nd - 1 - entry_k),
        })

    info["entry_count"] = len(info["entries"])
    info["exposure"] = float(np.mean(day_w[:, 1]))
    held = [e["held"] for e in info["exits"]
            if e["reason"] != "end_of_sample"]
    info["median_hold"] = float(np.median(held)) if held else 0.0
    return to_minutes(sig, day_w), info


# --------------------------------------------------------------------------- #
# benchmark only -- NOT part of the strategy
# --------------------------------------------------------------------------- #
def baseline_165d_weights(ts, closes):
    """The old shared base, used only to measure correlation and as benchmark."""
    dates = session_dates(ts)
    first, last = day_bounds(dates)
    dq = closes[last, 0]
    sma = pd.Series(dq).rolling(165).mean().to_numpy()
    on = np.zeros(len(first), bool)
    on[1:] = dq[:-1] > prev(sma)[1:]
    day_w = np.zeros((len(first), 3))
    day_w[:, 1] = on.astype(float)
    day_w[:, 2] = 1.0 - day_w[:, 1]
    sig = dict(dates=dates, first=first)
    return to_minutes(sig, day_w)


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def daily_returns(ts, equity):
    s = pd.Series(equity, index=ts)
    e = s.groupby(session_dates(pd.DatetimeIndex(ts))).last()
    return e.pct_change().dropna()


def corr_daily(a, b):
    idx = a.index.intersection(b.index)
    return float(np.corrcoef(a.loc[idx], b.loc[idx])[0, 1])


def run_chunked(ts, opens, closes, mats, start, slip, chunk=12):
    out = []
    for i in range(0, len(mats), chunk):
        out.extend(bt.run_many(ts, opens, closes, mats[i:i + chunk],
                               start=start, band=PARAMS["band"],
                               slippage_bps=slip))
    return out


def metrics(res, ts, opens, closes, start, slip):
    r = bt.run(ts, opens, closes, res, start, band=PARAMS["band"],
               slippage_bps=slip)
    s = bt.stats(r, BARS)
    s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
    return r, s


def slice_stats(ts, opens, closes, w, start, end, slip=1.0):
    i0 = bt.start_index(ts, start)
    i1 = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"))) + 1
    r = bt.simulate(ts[i0:i1], opens[i0:i1], closes[i0:i1], w[i0:i1],
                    band=PARAMS["band"], slippage_bps=slip)
    s = bt.stats(r, BARS)
    s["calmar"] = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
    return s


def episode_returns(res, info, last):
    eq = res["equity"]
    pairs = []
    ei = 0
    for ex in info["exits"]:
        if ei >= len(info["entries"]):
            break
        en = info["entries"][ei]
        i0 = 0 if en["session"] <= 0 else int(last[min(en["session"] - 1, len(last) - 1)])
        i1 = int(last[min(ex["session"] - 1, len(last) - 1)])
        if i1 > i0:
            pairs.append(float(eq[i1] / eq[i0] - 1.0))
        ei += 1
    return pairs


def bootstrap_p(ep, n_boot=10000, seed=7):
    if len(ep) < 5:
        return None
    rng = np.random.default_rng(seed)
    a = np.asarray(ep, float)
    means = rng.choice(a, size=(n_boot, len(a)), replace=True).mean(axis=1)
    return float((means <= 0).mean())


def neighbourhood(ts, opens, closes, base_daily, p0, grid):
    """3x3x3x3x3 grid; returns rows with CAGR/DD/Calmar/corr at 1 bp."""
    keys = list(grid)
    mats = []
    meta = []
    for vals in itertools.product(*(grid[k] for k in keys)):
        pp = {**p0, **dict(zip(keys, vals))}
        w, _ = build_weights(ts, opens, closes, pp)
        mats.append(w)
        meta.append(dict(zip(keys, vals)))
    res = run_chunked(ts, opens, closes, mats, DEV_START, 1.0)
    rows = []
    for pp, r in zip(meta, res):
        s = bt.stats(r, BARS)
        cal = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
        rows.append({**pp,
                     "cagr": float(s["cagr"]),
                     "max_drawdown": float(s["max_drawdown"]),
                     "calmar": float(cal),
                     "corr": corr_daily(base_daily, daily_returns(ts, r["equity"])),
                     "fills": int(s["fills"])})
    return rows


def other_rebuild_corr(ts, my_daily):
    """Optional: correlate with sibling rebuilds that saved daily_returns.parquet."""
    best = None
    for d in sorted((ROOT / "research" / "revisit").iterdir()):
        if not d.is_dir() or d.name == HERE.name:
            continue
        f = d / "daily_returns.parquet"
        if not f.exists():
            continue
        try:
            df = pd.read_parquet(f)
            s = pd.Series(df["ret"].to_numpy(),
                          index=pd.to_datetime(df["date"]))
            c = corr_daily(my_daily, s)
            best = c if best is None else max(best, c)
        except Exception:
            continue
    return best


# --------------------------------------------------------------------------- #
# main (not run while backtests are paused)
# --------------------------------------------------------------------------- #
def spy_daily_benchmark():
    """SPY buy-and-hold, daily marks only (SOURCE.md restricts it to benchmark)."""
    p = ROOT / "data" / "round3" / "yahoo" / "SPY-1d-yahoo.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    d = df[(df["date"] >= pd.Timestamp(DEV_START))
           & (df["date"] <= pd.Timestamp(DEV_END))].sort_values("date")
    if len(d) < 2:
        return None
    b = bt.benchmark(d["adjclose"].to_numpy(), pd.DatetimeIndex(d["date"]), 252)
    out = {k: float(v) for k, v in b.items()}
    out["marks"] = "daily"
    return out


def main():
    if "--authorised" not in sys.argv:
        raise SystemExit(
            "Backtests are paused (2026-11-26). Re-run with --authorised only "
            "after the lead/user authorises the new test."
        )
    ts, opens, closes = load_dev_panel()
    w, info = build_weights(ts, opens, closes)
    base_w = baseline_165d_weights(ts, closes)

    out = {
        "agent": "dynamic-leverage-throttle",
        "original": "research/agents2/dynamic-leverage-throttle",
        "status": "pending",
        "idea": "Volatility-shock recovery: buy TQQQ when a realised-vol shock "
                "is decaying inside a market drawdown, sized inversely to vol.",
        "hypothesis": "Post-shock volatility decay marks the end of forced "
                      "deleveraging; inverse-vol TQQQ captures the recovery "
                      "with low correlation to the 165-day trend base.",
        "universe": ["QQQ (signal)", "TQQQ (instrument)", "BIL (cash)"],
        "frozen_commit": None,
        "variants_tried": 0,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": {},
            "holdout": {"note": "not run; reserved for the lead, single run"},
            "10y": {"note": "not run; would overlap the holdout"},
            "5y": {"note": "not run; would overlap the holdout"},
        },
        "marks": "1m",
        "benchmarks": {},
        "events": {},
        "subperiods": {},
        "yearly": {},
        "neighbourhood": {},
        "ablations": {},
    }

    # headline dev windows at 1/5/10 bp
    res = run_chunked(ts, opens, closes, [w, base_w], DEV_START, 1.0)
    rb, sb = res[0], res[1]
    base_daily = daily_returns(ts, sb["equity"])
    for slip in (1.0, 5.0, 10.0):
        rc, sc = metrics(w, ts, opens, closes, DEV_START, slip)
        if slip == 1.0:
            rc1 = rc
        _, sbp = metrics(base_w, ts, opens, closes, DEV_START, slip)
        out["windows"]["dev"][f"{int(slip)}bp"] = {
            "cagr": float(sc["cagr"]),
            "max_drawdown": float(sc["max_drawdown"]),
            "sharpe": float(sc["sharpe"]),
            "sortino": float(sc["sortino"]),
            "calmar": float(sc["calmar"]),
            "fills": int(sc["fills"]),
            "turnover": float(sc["turnover"]),
            "baseline_cagr": float(sbp["cagr"]),
            "baseline_dd": float(sbp["max_drawdown"]),
            "baseline_calmar": float(sbp["calmar"]),
        }
    out["corr_vs_165d_baseline"] = corr_daily(
        base_daily, daily_returns(ts, rc1["equity"]))
    out["max_corr_vs_other_rebuilds"] = other_rebuild_corr(
        ts, daily_returns(ts, rc1["equity"]))

    # benchmarks
    i0 = bt.start_index(ts, DEV_START)
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        b = bt.benchmark(closes[i0:, col], ts[i0:], BARS)
        out["benchmarks"][name] = {k: float(v) for k, v in b.items()}
    out["benchmarks"]["spy"] = spy_daily_benchmark()
    orig_path = ROOT / "research" / "agents2" / "dynamic-leverage-throttle" / "result.json"
    if orig_path.exists():
        orig = json.loads(orig_path.read_text())
        out["benchmarks"]["original"] = {
            "note": "original result.json; 10y/5y overlap the holdout",
            "windows": orig.get("windows", {}),
        }

    # events / holding period / bootstrap
    last = day_bounds(session_dates(ts))[1]
    ep = episode_returns(rc1, info, last)
    out["events"] = {
        "entries": int(info["entry_count"]),
        "exits": int(len([e for e in info["exits"] if e["reason"] != "end_of_sample"])),
        "median_hold_sessions": float(info["median_hold"]),
        "episode_returns": [float(x) for x in ep],
        "bootstrap_p_mean_le_zero": bootstrap_p(ep),
    }

    # yearly and sub-periods
    out["yearly"] = bt.yearly(rc1["ts"], rc1["equity"], closes[i0:, 1])
    out["yearly"] = {str(k): {kk: float(vv) for kk, vv in v.items()}
                     for k, v in out["yearly"].items()}
    for tag, start, end in (("2016_2019", "2016-01-04", "2019-12-31"),
                            ("2020_2021", "2020-01-02", "2021-12-31"),
                            ("2022_2023", "2022-01-03", "2023-12-29")):
        sc = slice_stats(ts, opens, closes, w, start, end)
        sbp = slice_stats(ts, opens, closes, base_w, start, end)
        out["subperiods"][tag] = {
            "cagr": float(sc["cagr"]), "max_drawdown": float(sc["max_drawdown"]),
            "calmar": float(sc["calmar"]),
            "baseline_cagr": float(sbp["cagr"]),
            "baseline_dd": float(sbp["max_drawdown"]),
        }

    # ablation variants
    ablations = {
        "primary": {},
        "no_decay": {"use_decay": False},
        "no_shock": {"use_shock": False},
        "no_drawdown": {"use_dd": False},
        "always_on_vt": {"always_on": True},
    }
    mats, names = [], []
    for name, over in ablations.items():
        ww, _ = build_weights(ts, opens, closes, {**PARAMS, **over})
        mats.append(ww)
        names.append(name)
    for name, r in zip(names, run_chunked(ts, opens, closes, mats, DEV_START, 1.0)):
        s = bt.stats(r, BARS)
        cal = s["cagr"] / s["max_drawdown"] if s["max_drawdown"] > 0 else 0.0
        out["ablations"][name] = {
            "cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
            "calmar": float(cal),
            "corr": corr_daily(base_daily, daily_returns(ts, r["equity"])),
        }

    # pre-registered 3x3x3x3x3 neighbourhood
    grid = {
        "shock_mult": [1.15, 1.25, 1.35],
        "decay_ratio": [0.80, 0.85, 0.90],
        "dd_entry": [-0.06, -0.08, -0.10],
        "target_vol": [0.25, 0.30, 0.35],
        "time_stop": [40, 60, 80],
    }
    rows = neighbourhood(ts, opens, closes, base_daily, PARAMS, grid)
    out["neighbourhood"] = {
        "grid": grid,
        "n": len(rows),
        "rows": rows,
        "frac_corr_below_060": float(np.mean([r["corr"] < 0.60 for r in rows])),
        "frac_positive_cagr": float(np.mean([r["cagr"] > 0 for r in rows])),
        "median_calmar": float(np.median([r["calmar"] for r in rows])),
    }
    out["variants_tried"] = len(rows) + len(ablations) - 1

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"dev candidate 1bp: CAGR {out['windows']['dev']['1bp']['cagr']*100:.2f}%  "
          f"DD {out['windows']['dev']['1bp']['max_drawdown']*100:.2f}%  "
          f"Calmar {out['windows']['dev']['1bp']['calmar']:.2f}  "
          f"corr {out['corr_vs_165d_baseline']:.3f}  "
          f"entries {out['events']['entries']}")
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
