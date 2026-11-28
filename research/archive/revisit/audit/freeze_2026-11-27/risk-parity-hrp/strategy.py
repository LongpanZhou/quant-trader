"""Volatility-State Risk Parity (VSRP) — rebuild of `risk-parity-hrp`.

STATUS: rejected on dev (corr 0.78 with the 165-day base; see DIAGNOSIS.md).
Tune 2026-11-27 fixed two reporting bugs (event study, spike count); the
weights are unchanged.

What it is
----------
A long-only allocation across QQQ, TQQQ and BIL in which the risk model owns the
whole position:

1. Composition: equal-risk-contribution (inverse-vol) weights on QQQ/TQQQ,
   clipped to [10%, 50%] TQQQ. Typical 75/25, sleeve vol ~34%.
2. Risk budget: 35% of equity at neutral, tilted by the *volatility term
   structure* (20-day vs 120-day realised vol) and damped when the 120-day vol
   is itself in a persistent high-vol regime. Transient stress raises the
   budget; persistent stress does not.
3. Risk controls: forecast-vol cap (18%), own-equity drawdown brake with
   hysteresis, long-only, gross <= 1.

No price moving average, no 165-day gate, no 4% stop, no reused weight code.
The 165-day baseline appears only in `baseline_weights()` for the correlation
report required by the brief.

Timing
------
Every daily input for session k uses data through the close of session k-1.
`weights[i] = tgt[k]` for every minute of session k; the last minute of session
k-1 also carries tgt[k] so `bt.simulate` fills at session k's open.

Run (only after authorisation):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/risk-parity-hrp/strategy.py            # dev only
    python research/revisit/risk-parity-hrp/strategy.py --controls # + robustness
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
BARS = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")

P = dict(
    short_win=20,
    long_win=120,
    comp_win=60,
    slope_scale=0.35,
    persist_scale=0.50,
    persist_damp=0.70,
    smooth=5,
    base_budget=0.35,
    tilt_strength=0.20,
    vol_cap=0.18,
    dd_half=-0.12,
    dd_floor=-0.20,
    dd_release_half=-0.06,
    dd_release_floor=-0.14,
    band=0.02,
    rho=0.9995,
    min_periods=60,
    b_min=0.03,
    b_max=0.60,
)


# --------------------------------------------------------------------------- #
# data / sessions
# --------------------------------------------------------------------------- #
def load_panel():
    return bt.panel(SYMS, DEV_START, DEV_END, "1min")


def session_arrays(ts, opens, closes):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    assert first[0] == 0, "panel must start on a session open"
    dcl = closes[last]
    dop = opens[first]
    d = len(first)
    rets = np.full((d, 3), np.nan)
    rets[1:] = dcl[1:] / dcl[:-1] - 1.0
    return dict(ts=ts, dates=dates, first=first, last=last, dcl=dcl, dop=dop,
                d=d, rets=rets, n=len(ts))


def lag(x):
    out = np.full_like(np.asarray(x, dtype=float), np.nan)
    out[1:] = np.asarray(x, dtype=float)[:-1]
    return out


def roll_vol(rets, win, minp):
    v = pd.DataFrame(rets).rolling(win, min_periods=minp).std().to_numpy() * np.sqrt(252.0)
    return v


# --------------------------------------------------------------------------- #
# daily state (all arrays indexed by session and already lagged)
# --------------------------------------------------------------------------- #
def daily_state(sa, p=P):
    rets, d = sa["rets"], sa["d"]
    v_s = roll_vol(rets, p["short_win"], max(10, p["short_win"] // 2))
    v_l = roll_vol(rets, p["long_win"], p["min_periods"])
    v_c = roll_vol(rets, p["comp_win"], p["min_periods"])

    # --- volatility state, computed through the close of session j ---
    with np.errstate(divide="ignore", invalid="ignore"):
        slope_j = np.log(v_s[:, 0] / v_l[:, 0])
    med = pd.Series(v_l[:, 0]).rolling(756, min_periods=p["min_periods"]).median().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        persist_j = np.clip((v_l[:, 0] / med - 1.0) / p["persist_scale"], 0.0, 1.0)
    tilt_raw_j = np.clip(slope_j / p["slope_scale"], -1.0, 1.0) * (1.0 - p["persist_damp"] * persist_j)
    tilt_j = pd.Series(tilt_raw_j).rolling(p["smooth"], min_periods=1).mean().to_numpy()

    # --- ERC composition through the close of session j ---
    with np.errstate(divide="ignore", invalid="ignore"):
        wT_j = np.clip(v_c[:, 0] / (v_c[:, 0] + v_c[:, 1]), 0.10, 0.50)
    wQ_j = 1.0 - wT_j
    sQ, sT = v_c[:, 0], v_c[:, 1]
    sv_j = np.sqrt((wQ_j * sQ) ** 2 + (wT_j * sT) ** 2
                   + 2.0 * wQ_j * wT_j * sQ * sT * p["rho"])

    return dict(
        tilt=lag(tilt_j), wT=lag(wT_j), wQ=lag(wQ_j), sleeve_vol=lag(sv_j),
        slope=lag(slope_j), persist=lag(persist_j),
        v20=lag(v_s[:, 0]), v120=lag(v_l[:, 0]),
    )


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(ts, opens, closes, p=P, brake=True, tilt_override=None):
    """Return (minute weights, info). All signals lagged one session."""
    sa = session_arrays(ts, opens, closes)
    st = daily_state(sa, p)
    d = sa["d"]
    dcl, dop = sa["dcl"], sa["dop"]
    tilt = st["tilt"] if tilt_override is None else np.asarray(tilt_override, float)

    tgt = np.zeros((d, 3))
    tgt[:, 2] = 1.0                      # flat / BIL before warm-up
    eq = np.ones(d)
    peak = np.ones(d)
    budgets = np.zeros(d)
    states = np.zeros(d, dtype=int)
    state = 0
    mult = {0: 1.0, 1: 0.5, 2: 0.2}

    for k in range(1, d):
        dd = eq[k - 1] / peak[k - 1] - 1.0
        if brake:
            if dd <= p["dd_floor"]:
                state = 2
            elif dd <= p["dd_half"] and state == 0:
                state = 1
            elif state == 2 and dd >= p["dd_release_floor"]:
                state = 1
            elif state == 1 and dd >= p["dd_release_half"]:
                state = 0
        states[k] = state

        wT, wQ, sv, ti = st["wT"][k], st["wQ"][k], st["sleeve_vol"][k], tilt[k]
        if not np.isfinite([wT, wQ, sv, ti]).all():
            b = 0.0
            wT = 0.0
            wQ = 0.0
        else:
            b0 = p["base_budget"] + p["tilt_strength"] * ti
            b1 = min(b0, p["vol_cap"] / sv) if sv > 0 else b0
            b = float(np.clip(b1 * mult[state], p["b_min"], p["b_max"]))
        tgt[k, 0] = b * wQ
        tgt[k, 1] = b * wT
        tgt[k, 2] = 1.0 - b
        budgets[k] = b

        # own-equity recursion for the brake signal (daily close marks, no costs)
        r_on = float(np.nansum(tgt[k - 1] * (dop[k] / dcl[k - 1] - 1.0)))
        eq_open = eq[k - 1] * (1.0 + r_on)
        r_id = float(np.nansum(tgt[k] * (dcl[k] / dop[k] - 1.0)))
        eq[k] = eq_open * (1.0 + r_id)
        peak[k] = max(peak[k - 1], eq[k])

    w = expand_to_minutes(sa, tgt)
    info = dict(
        mean_budget=float(np.mean(budgets[1:])),
        median_budget=float(np.median(budgets[1:])),
        mean_wT=float(np.nanmean(st["wT"][1:])),
        mean_wQ=float(np.nanmean(st["wQ"][1:])),
        mean_sleeve_vol=float(np.nanmean(st["sleeve_vol"][1:])),
        brake_days={str(s): int(np.sum(states == s)) for s in (0, 1, 2)},
        flat_days=int(np.sum(budgets < 0.01)),
        tilt_mean=float(np.nanmean(tilt[1:])),
        tilt_std=float(np.nanstd(tilt[1:])),
        # Tune 2026-11-27: astype(int) so only rising edges count. np.diff on a
        # bool array is XOR, which counted falling edges too (16 -> 8 episodes).
        spike_events=int(np.sum(np.diff(np.r_[False, (st["slope"] > 0.5)
                                              & (st["persist"] < 0.3)].astype(int)) == 1)),
    )
    return w, info


def expand_to_minutes(sa, tgt):
    """tgt[k] is held during session k; fills at session k's open."""
    d, n = sa["d"], sa["n"]
    day = np.repeat(np.arange(d), np.diff(np.r_[sa["first"], n]))
    is_last = np.zeros(n, dtype=bool)
    is_last[sa["last"]] = True
    src = np.minimum(day + is_last.astype(int), d - 1)
    return tgt[src]


def baseline_weights(sa):
    """165-day QQQ SMA baseline. COMPARISON ONLY — never an input."""
    q = sa["dcl"][:, 0]
    sma = pd.Series(q).rolling(165).mean().to_numpy()
    prev = lag(sma)
    on = np.zeros(sa["d"], dtype=bool)
    on[1:] = q[:-1] > prev[1:]
    tgt = np.zeros((sa["d"], 3))
    tgt[on, 1] = 1.0
    tgt[~on, 2] = 1.0
    return expand_to_minutes(sa, tgt)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def daily_returns(ts, eq):
    s = pd.Series(eq, index=ts)
    e = s.groupby(s.index.date).last().to_numpy()
    return np.diff(e) / e[:-1]


def daily_equity(ts, eq):
    s = pd.Series(eq, index=ts)
    return s.groupby(s.index.date).last().to_numpy()


def run_one(ts, opens, closes, w, slip, start=DEV_START, band=0.02):
    r = bt.run(ts, opens, closes, w, start, band=band, slippage_bps=slip)
    return bt.stats(r, BARS), r


def corr_vs_base(ts, opens, closes, w, slip=1.0):
    sa = session_arrays(ts, opens, closes)
    wb = baseline_weights(sa)
    _, rb = run_one(ts, opens, closes, wb, 0.0, band=0.0)
    _, r = run_one(ts, opens, closes, w, slip)
    a = daily_returns(r["ts"], r["equity"])
    b = daily_returns(rb["ts"], rb["equity"])
    n = min(len(a), len(b))
    return float(np.corrcoef(a[-n:], b[-n:])[0, 1]), rb


def slice_stats(ts, eq, start, end):
    s = pd.Series(eq, index=ts)
    m = (s.index >= pd.Timestamp(start, tz="America/New_York")) & \
        (s.index <= pd.Timestamp(end, tz="America/New_York"))
    e = s[m].to_numpy()
    t = s.index[m]
    if len(e) < 2:
        return dict(cagr=0.0, max_drawdown=0.0)
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(e)
    return dict(cagr=float((e[-1] / e[0]) ** (1 / years) - 1) if years > 0 else 0.0,
                max_drawdown=float(-(e / peak - 1).min()))


def benchmark_stats(ts, close, start=DEV_START):
    i = bt.start_index(ts, start)
    return bt.benchmark(close[i:], ts[i:], BARS)


# --------------------------------------------------------------------------- #
# required controls
# --------------------------------------------------------------------------- #
def _variant(ts, opens, closes, p, brake=True, tilt_override=None, slip=1.0):
    w, info = build_weights(ts, opens, closes, p, brake=brake, tilt_override=tilt_override)
    s, _ = run_one(ts, opens, closes, w, slip)
    return s, info, w


def controls(ts, opens, closes, base_w, base_stats, out):
    sa = session_arrays(ts, opens, closes)
    st = daily_state(sa, P)
    ctrl = {}

    # 1. ablations
    abl = {}
    for name, kw in (
        ("constant_35pct", dict(brake=False, tilt_override=np.zeros(sa["d"]))),
        ("tilt_no_persist_damp", dict(
            brake=True,
            tilt_override=pd.Series(np.clip(st["slope"] / P["slope_scale"], -1, 1))
            .rolling(P["smooth"], min_periods=1).mean().to_numpy())),
        ("brake_off", dict(brake=False, tilt_override=None)),
    ):
        s, info, _ = _variant(ts, opens, closes, P, **kw)
        abl[name] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                         mean_budget=info["mean_budget"])
    ctrl["ablations"] = abl

    # 2. placebo: sign-flipped and seeded random tilt with the same moments
    rng = np.random.default_rng(20261126)
    ti = st["tilt"].copy()
    valid = np.isfinite(ti)
    z = (ti[valid] - ti[valid].mean()) / ti[valid].std()
    rand = np.full(sa["d"], np.nan)
    rand[valid] = rng.permutation(z) * ti[valid].std() + ti[valid].mean()
    plc = {}
    for name, ov in (("sign_flipped", -ti), ("random_shuffle", rand)):
        s, info, wp = _variant(ts, opens, closes, P, brake=True, tilt_override=ov)
        plc[name] = dict(cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                         corr=corr_vs_base(ts, opens, closes, wp, 1.0)[0])
    ctrl["placebo"] = plc

    # 3. neighbourhood (+/- one step around the primary)
    neigh = []
    steps = {
        "tilt_strength": (0.15, 0.20, 0.25),
        "slope_scale": (0.30, 0.35, 0.40),
        "base_budget": (0.30, 0.35, 0.40),
        "vol_cap": (0.16, 0.18, 0.20),
    }
    for key, vals in steps.items():
        for v in vals:
            p = dict(P)
            p[key] = v
            s, info, _ = _variant(ts, opens, closes, p)
            neigh.append(dict(param=key, value=v, cagr=s["cagr"],
                              dd=s["max_drawdown"], sharpe=s["sharpe"],
                              mean_budget=info["mean_budget"]))
    ctrl["neighbourhood"] = neigh

    # 4. sub-periods
    _, r = run_one(ts, opens, closes, base_w, 1.0)
    ctrl["subperiods"] = {
        "2016_2019": slice_stats(ts, r["equity"], DEV_START, "2019-12-31"),
        "2020_2021": slice_stats(ts, r["equity"], "2020-01-01", "2021-12-31"),
        "2022_2023": slice_stats(ts, r["equity"], "2022-01-01", DEV_END),
    }

    # 5. event study: transient spikes and forward 20-day sleeve return
    wT = st["wT"]
    wQ = st["wQ"]
    # Tune 2026-11-27: wT/wQ are NaN during warm-up, which made the whole sleeve
    # curve NaN and the event study silently report 0 events. Warm-up is now
    # flat; fwd[k] starts at the close of k-1 (when session k's state is known);
    # one observation per episode (its first day), not per overlapping day.
    sleeve = np.full(sa["d"], np.nan)
    sleeve[0] = 1.0
    for k in range(1, sa["d"]):
        r = wT[k] * (sa["dcl"][k, 1] / sa["dcl"][k - 1, 1] - 1) + \
            wQ[k] * (sa["dcl"][k, 0] / sa["dcl"][k - 1, 0] - 1)
        sleeve[k] = sleeve[k - 1] * (1 + (r if np.isfinite(r) else 0.0))
    fwd = np.full(sa["d"], np.nan)
    for k in range(1, sa["d"] - 19):
        fwd[k] = sleeve[k + 19] / sleeve[k - 1] - 1
    fwd[~np.isfinite(st["slope"])] = np.nan
    ev_day = np.isfinite(fwd) & (st["slope"] > 0.5) & (st["persist"] < 0.3)
    ev = np.diff(np.r_[False, ev_day].astype(int)) == 1
    ctrl["event_study"] = dict(
        n_events=int(ev.sum()),
        event_mean_fwd20=float(np.nanmean(fwd[ev])) if ev.any() else None,
        unconditional_mean_fwd20=float(np.nanmean(fwd)),
    )
    if ev.sum() >= 3:
        pool = fwd[np.isfinite(fwd) & ~ev_day]
        obs = float(np.nanmean(fwd[ev]))
        n = int(ev.sum())
        sims = np.array([np.mean(rng.choice(pool, size=n, replace=False)) for _ in range(5000)])
        ctrl["event_study"]["permutation_p"] = float((sims >= obs).mean())

    out["controls"] = ctrl


def _tgt_from_w(sa, s, ts, opens, closes):
    """Deprecated helper. Kept only so old pickles/imports do not break."""
    return np.zeros((sa["d"], 3))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(with_controls=False):
    ts, opens, closes = load_panel()
    sa = session_arrays(ts, opens, closes)
    w, info = build_weights(ts, opens, closes)

    out = {
        "agent": "risk-parity-hrp",
        "original": "research/agents2/risk-parity-hrp",
        "status": "rejected",   # dev corr 0.78 >= 0.60 and placebo beats the tilt (DIAGNOSIS.md)
        "idea": "Equal-risk QQQ/TQQQ composition with a risk budget that rises after "
                "transient volatility spikes and is damped in persistent high-vol regimes.",
        "hypothesis": "The conditional Sharpe ratio of the equity factor rises after a "
                      "transient vol spike and not in a persistent high-vol regime.",
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 12,
        "corr_vs_165d_baseline": None,
        "max_corr_vs_other_rebuilds": None,
        "windows": {},
        "marks": "1m",
        "benchmarks": {},
        "info": info,
        "notes": [
            "dev only; holdout 2024-2026 not inspected",
            "10y/5y windows overlap the holdout and are left to the lead",
        ],
    }

    corr, rb = corr_vs_base(ts, opens, closes, w, 1.0)
    out["corr_vs_165d_baseline"] = corr

    for slip in (1.0, 5.0, 10.0):
        s, r = run_one(ts, opens, closes, w, slip)
        out["windows"].setdefault("dev", {})[f"{slip:.0f}bp"] = dict(
            cagr=float(s["cagr"]), max_drawdown=float(s["max_drawdown"]),
            sharpe=float(s["sharpe"]), fills=int(s["fills"]),
            turnover=float(s["turnover"]), exposure=float(s["exposure"]),
        )
    # benchmarks on dev
    for sym, j in (("qqq", 0), ("tqqq", 1), ("bil", 2)):
        b = benchmark_stats(ts, closes[:, j])
        out["benchmarks"][sym] = dict(cagr=b["cagr"], max_drawdown=b["max_drawdown"],
                                      sharpe=b["sharpe"])
    bb = slice_stats(rb["ts"], rb["equity"], DEV_START, DEV_END)
    out["benchmarks"]["base_165d"] = bb
    out["windows"]["holdout"] = {"1bp": None, "5bp": None, "10bp": None}
    out["windows"]["10y"] = {"1bp": None, "5bp": None}
    out["windows"]["5y"] = {"1bp": None, "5bp": None}

    if with_controls:
        controls(ts, opens, closes, w, out["windows"]["dev"]["1bp"], out)

    with open(HERE / "result.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("status", "corr_vs_165d_baseline")}, indent=2))


if __name__ == "__main__":
    main(with_controls="--controls" in sys.argv)
