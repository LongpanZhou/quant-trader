"""Drawdown-recovery TQQQ v2: two-speed circuit breaker.

Standalone strategy, development window only (2016-01-04 .. 2023-12-29).

Rules
-----
Signal: QQQ session close (15:59 print).  Position: TQQQ.  Idle: cash at 0%.
One decision per session at the close, filled at the next session's open by
the shared `research/bt.py` simulator (2% band, 1 bp headline).

    dd20 = q / max(q[-19..0]) - 1
    dd60 = q / max(q[-59..0]) - 1
    vr   = sigma10(lagged) / sigma60(lagged)       (annualised)

State machine, default LONG:
  LONG -> CASH when dd20 <= -8% or dd60 <= -12%  (a new drawdown).
  A position entered from a deep cash episode is instead stopped by
  dd20 <= -8% or an 8% drawdown from its own post-entry high, until the
  stale dd60 heals above -12%.
  CASH -> LONG when the cash episode was deep (dd60 reached -12%) and
  vr < 0.60 (volatility contraction), or when it was shallow and either
  vr < 0.60 or q > max(q[-10..-1]) (a 10-session high).

Indicator warmup uses QQQ daily closes from 2015-01-02..2015-12-31 only.
The 1-minute panel is physically sliced at 2023-12-29; no 2024+ bar is used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_1M = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
COL_Q, COL_T = 0, 1

# pre-registered centre
ARM_20 = 0.08
ARM_60 = 0.12
VOL_RATIO = 0.60
VOL_WIN = 10
VOL_LONG = 60
HI_N = 10
TRAIL = 0.08          # backstop for a recovery position; never binds in dev
DEEP_DD60 = 0.12
WARMUP_START = "2015-01-02"


# --------------------------------------------------------------------------- #
# panel and signals
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END):
    return bt.panel(SYMBOLS, start, end, "1min", warmup_days=0)


def _pre_closes(first_session_date) -> np.ndarray:
    """QQQ total-return daily closes strictly before the intraday archive."""
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    pre = daily[daily["date"] < first_session_date].sort_values("date")
    pre = pre[pre["date"] >= pd.Timestamp(WARMUP_START).date()]
    return pre["adjclose"].to_numpy(dtype=float)


def _rmax_excl(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).max().shift(1).to_numpy()


def _rmin_excl(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).min().shift(1).to_numpy()


def _rstd_lag(x: np.ndarray, n: int) -> np.ndarray:
    s = pd.Series(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()
    out = np.full(len(x), np.nan)
    out[1:] = s[:-1]
    return out


def session_signals(ts, closes):
    """Causal daily arrays aligned to the 2012 dev sessions."""
    dates, first, last = bt.day_bounds(ts)
    nd = len(first)
    q = np.asarray(closes, dtype=float)[last, COL_Q]
    pre = _pre_closes(dates[first][0])
    npre = len(pre)
    qa = np.r_[pre, q]
    r = np.full(len(qa), np.nan)
    r[1:] = np.log(qa[1:] / qa[:-1])
    v10 = _rstd_lag(r, VOL_WIN)[npre:] * np.sqrt(252.0)
    v60 = _rstd_lag(r, VOL_LONG)[npre:] * np.sqrt(252.0)
    return {
        "dates": dates, "first": first, "last": last, "nd": nd,
        "q": q,
        "dd20": (qa / _rmax_excl(qa, 20) - 1.0)[npre:],
        "dd60": (qa / _rmax_excl(qa, 60) - 1.0)[npre:],
        "hi5": _rmax_excl(qa, 5)[npre:],
        "hi10": _rmax_excl(qa, 10)[npre:],
        "hi20": _rmax_excl(qa, 20)[npre:],
        "lo10": _rmin_excl(qa, 10)[npre:],
        "v10": v10, "v60": v60,
        "vr": v10 / np.maximum(v60, 1e-12),
        "npre": npre,
    }


# --------------------------------------------------------------------------- #
# state machine
# --------------------------------------------------------------------------- #
def state_machine(sig: dict, arm_20: float = ARM_20, arm_60: float = ARM_60,
                  vol_ratio: float = VOL_RATIO, hi_n: int = HI_N,
                  trail: float = TRAIL, deep_dd60: float = DEEP_DD60,
                  deep_rule: str = "vol_only",
                  shallow_rule: str = "hi_or_vol",
                  start_long: bool = True, use_lo_exit: bool = False,
                  trail_only: bool = False):
    """Return per-session target weights and the round-trip episode list."""
    q = sig["q"]
    dd20, dd60 = sig["dd20"], sig["dd60"]
    hi = sig[f"hi{hi_n}"]
    lo = sig["lo10"] if use_lo_exit else None
    vr = sig["vr"]
    n = len(q)
    t = np.zeros(n)
    w = 1.0 if start_long else 0.0
    peak = q[0] if start_long else np.nan
    deep = False
    recovery = False
    eps: list[dict] = []
    if start_long:
        eps.append({"entry_i": 0, "entry_why": "initial"})
    for i in range(n):
        if not (np.isfinite(dd20[i]) and np.isfinite(dd60[i])
                and np.isfinite(vr[i])):
            t[i] = w
            continue
        if w > 0:
            peak = max(peak, q[i])
            lo_trig = lo is not None and np.isfinite(lo[i]) and q[i] < lo[i]
            if trail_only:
                exit_trig = q[i] / peak - 1.0 <= -trail or lo_trig
            elif recovery:
                exit_trig = (q[i] / peak - 1.0 <= -trail
                             or dd20[i] <= -arm_20 or lo_trig)
                if dd60[i] > -arm_60:
                    recovery = False
            else:
                exit_trig = dd20[i] <= -arm_20 or dd60[i] <= -arm_60 or lo_trig
            if exit_trig:
                w = 0.0
                deep = dd60[i] <= -arm_60
                if eps and "exit_i" not in eps[-1]:
                    eps[-1].update({
                        "exit_i": i,
                        "exit_why": ("lo10" if lo_trig else
                                     ("dd" if not trail_only else "trail")),
                        "deep": bool(deep),
                        "qret": float(q[i] / q[eps[-1]["entry_i"]] - 1.0),
                        "days": int(i - eps[-1]["entry_i"]),
                    })
        else:
            if dd60[i] <= -arm_60:
                deep = True
            vol_ok = vr[i] < vol_ratio
            hi_ok = np.isfinite(hi[i]) and q[i] > hi[i]
            if deep:
                trig = vol_ok if deep_rule == "vol_only" else (vol_ok or hi_ok)
            else:
                if shallow_rule == "hi_only":
                    trig = hi_ok
                elif shallow_rule == "vol_only":
                    trig = vol_ok
                else:
                    trig = hi_ok or vol_ok
            if trig:
                w = 1.0
                peak = q[i]
                recovery = deep
                deep = False
                eps.append({
                    "entry_i": i,
                    "entry_why": ("deep_vol" if recovery and vol_ok else
                                  ("deep_hi" if recovery else
                                   ("shallow_hi" if hi_ok and not vol_ok else "shallow_vol"))),
                    "entry_dd20": float(dd20[i]),
                    "entry_dd60": float(dd60[i]),
                    "entry_vr": float(vr[i]),
                })
        t[i] = w
    if eps and "exit_i" not in eps[-1]:
        eps[-1].update({
            "exit_i": n - 1, "exit_why": "open", "deep": bool(deep),
            "qret": float(q[-1] / q[eps[-1]["entry_i"]] - 1.0),
            "days": int(n - 1 - eps[-1]["entry_i"]),
        })
    return t, eps


def weights_from_daily(sig: dict, t: np.ndarray) -> np.ndarray:
    """Map one target per session to per-bar weights.

    `weights[i]` is set at the close of bar i and filled at the open of bar
    i+1.  The last bar of session k carries the new target t[k]; the rest of
    session k carries the previous target t[k-1].
    """
    first, last, nd = sig["first"], sig["last"], sig["nd"]
    n = int(last[-1]) + 1
    w1 = np.zeros(n)
    prev = 0.0
    for k in range(nd):
        f, l = int(first[k]), int(last[k])
        w1[f:l] = prev
        w1[l] = t[k]
        prev = t[k]
    w1[-1] = w1[-2]
    return w1


def build_weights(ts, opens, closes, arm_20: float = ARM_20,
                  arm_60: float = ARM_60, vol_ratio: float = VOL_RATIO,
                  hi_n: int = HI_N, trail: float = TRAIL,
                  deep_rule: str = "vol_only",
                  shallow_rule: str = "hi_or_vol",
                  start_long: bool = True, use_lo_exit: bool = False,
                  trail_only: bool = False,
                  return_episodes: bool = False):
    sig = session_signals(ts, closes)
    t, eps = state_machine(sig, arm_20, arm_60, vol_ratio, hi_n, trail,
                           DEEP_DD60, deep_rule, shallow_rule, start_long,
                           use_lo_exit, trail_only)
    w1 = weights_from_daily(sig, t)
    w = np.zeros((len(ts), 3))
    w[:, COL_T] = w1[:len(ts)]
    assert (w >= 0).all() and (w.sum(axis=1) <= 1.0 + 1e-9).all()
    if return_episodes:
        return w, eps, sig, t
    return w


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_weights(ts, o, c, w, start=DEV_START, slip=1.0):
    r = bt.run(ts, o, c, w, start, band=0.02, slippage_bps=slip)
    return r, bt.stats(r, BARS_1M)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(res["ts"].date).last().pct_change().dropna()


def dd_window(ts, equity):
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def subperiod(ts, equity, lo, hi):
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min()),
            "years": float(years)}


def calendar_year_cut(ts, equity, year: int) -> dict:
    s = pd.Series(equity, index=ts)
    d = s.groupby(ts.date).last()
    r = d.pct_change().dropna()
    r = r[np.array([x.year != year for x in r.index])]
    eq = np.cumprod(1.0 + r.to_numpy())
    years = len(r) / 252.0
    peak = np.maximum.accumulate(eq)
    return {"cagr": float(eq[-1] ** (1 / years) - 1),
            "max_drawdown": float(-(eq / peak - 1).min()),
            "years": float(years)}


def cash_attribution(sig, t, o, c):
    """Fill-to-fill cash periods and the TQQQ return that was avoided."""
    first, last, nd = sig["first"], sig["last"], sig["nd"]
    q = sig["q"]
    tq_open = np.array([o[int(first[i]), COL_T] for i in range(nd)])
    cash = []
    i = 0
    while i < nd:
        if t[i] == 0:
            j = i
            while j + 1 < nd and t[j + 1] == 0:
                j += 1
            if j + 2 < nd:
                tq_ret = tq_open[j + 2] / tq_open[i + 1] - 1.0
            else:
                tq_ret = tq_open[nd - 1] / tq_open[i + 1] - 1.0
            cash.append({
                "exit_signal": str(sig["dates"][first[i]])[:10],
                "reentry_signal": str(sig["dates"][first[j]])[:10],
                "days": int(j - i + 1),
                "qqq_return": float(q[min(j + 1, nd - 1)] / q[i] - 1.0),
                "tqqq_return": float(tq_ret),
                "log_tqqq": float(np.log1p(tq_ret)),
            })
            i = j + 1
        else:
            i += 1
    return cash


def episode_table(sig, eps, ts, o, c):
    """TQQQ next-open return of each round trip."""
    first, last, nd = sig["first"], sig["last"], sig["nd"]

    def next_open(k):
        if k + 1 < nd:
            return float(o[int(first[k + 1]), COL_T])
        return float(c[int(last[k]), COL_T])

    out = []
    for e in eps:
        i, j = int(e["entry_i"]), int(e["exit_i"])
        tq_in = next_open(i)
        tq_out = next_open(j)
        out.append({
            "entry": str(sig["dates"][first[i]])[:10],
            "exit": str(sig["dates"][first[j]])[:10],
            "days": int(e["days"]),
            "entry_why": e.get("entry_why"),
            "exit_why": e.get("exit_why"),
            "entry_dd20": e.get("entry_dd20"),
            "entry_dd60": e.get("entry_dd60"),
            "entry_vr": e.get("entry_vr"),
            "qqq_return": float(e["qret"]),
            "tqqq_return": float(tq_out / tq_in - 1.0),
        })
    return out


# --------------------------------------------------------------------------- #
# placebo
# --------------------------------------------------------------------------- #
def block_permute(t: np.ndarray, block: int, rng) -> np.ndarray:
    n = len(t)
    starts = list(range(0, n, block))
    blocks = [t[s:s + block] for s in starts]
    order = rng.permutation(len(blocks))
    return np.concatenate([blocks[i] for i in order])[:n]


def random_breaker(t: np.ndarray, rng) -> np.ndarray:
    """Keep the cash/equity labels but put them at random non-overlapping dates."""
    n = len(t)
    # cash runs from the real series
    runs = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and t[j + 1] == t[i]:
            j += 1
        if t[i] == 0:
            runs.append(j - i + 1)
        i = j + 1
    out = np.ones(n)
    total = sum(runs)
    if total == 0:
        return out
    # place the cash runs at random starts; retry to avoid overlap
    for length in runs:
        placed = False
        for _ in range(100):
            s = int(rng.integers(0, max(n - length, 1)))
            if out[s:s + length].all():
                out[s:s + length] = 0.0
                placed = True
                break
        if not placed:
            # fall back to a random contiguous block
            s = int(rng.integers(0, max(n - length, 1)))
            out[s:s + length] = 0.0
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = load_panel()
    sig = session_signals(ts, c)
    print(f"panel {len(ts):,} bars, {sig['nd']} sessions, "
          f"{sig['dates'][sig['first'][0]]} .. "
          f"{sig['dates'][sig['last'][-1]]}")
    print(f"pre-history {sig['npre']} QQQ closes (2015 only)")

    w, eps, sig, t = build_weights(ts, o, c, return_episodes=True)
    out = {
        "strategy": "drawdown-recovery-v2",
        "directory": "research/new/drawdown-recovery-v2",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1m",
                   "fills": "next open, 2% band", "idle": "cash at 0%"},
        "rules": {
            "arm_dd20": ARM_20, "arm_dd60": ARM_60,
            "vol_ratio": VOL_RATIO, "vol_window": VOL_WIN,
            "vol_long": VOL_LONG, "hi_window": HI_N,
            "trail": TRAIL, "deep_dd60": DEEP_DD60,
            "deep_rule": "vol contraction only",
            "shallow_rule": "10d high or vol contraction",
            "state": "long by default; cash after a new drawdown",
            "warmup": "QQQ daily closes 2015-01-02..2015-12-31",
        },
        "dev": {},
    }

    results = {}
    for slip in (1.0, 5.0, 10.0):
        res, s = run_weights(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:2.0f}bp  CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sharpe {s['sharpe']:4.2f}  "
              f"exp {s['exposure']*100:5.1f}%  fills {s['fills']:,}  "
              f"turnover {s['turnover']:.2f}x")

    res1, s1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    bench = bt.benchmark(c[i0:, COL_T], ts[i0:], BARS_1M)
    out["benchmark_tqqq"] = {k: float(v) for k, v in bench.items()}
    out["benchmark_tqqq"]["symbol"] = "TQQQ"
    out["benchmark_tqqq"]["bar_from_brief"] = {
        "cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}
    out["corr_daily_tqqq"] = float(
        daily_returns(res1).corr(
            daily_returns({"equity": c[i0:, COL_T], "ts": ts[i0:]})))

    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]),
                 "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"],
                              c[i0:, COL_T]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"],
                               "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"],
                               "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"],
                               "2022-01-03", "2023-12-29"),
    }
    out["exposure_by_year"] = {
        str(y): float(np.mean(
            ((res1["equity"] - res1["cash"]) / res1["equity"])[res1["ts"].year == y]))
        for y in sorted(set(res1["ts"].year))
    }

    # ---- pre-registered grid (8 cells) --------------------------------------
    grid_spec = [
        (0.07, 0.11, 0.60), (0.08, 0.12, 0.60), (0.09, 0.13, 0.60),
        (0.10, 0.15, 0.60), (0.08, 0.12, 0.55), (0.08, 0.12, 0.65),
        (0.07, 0.11, 0.65), (0.09, 0.13, 0.55),
    ]
    grid = []
    ws = []
    for a20, a60, vr in grid_spec:
        ws.append(build_weights(ts, o, c, arm_20=a20, arm_60=a60,
                                vol_ratio=vr))
    for (a20, a60, vr), wt in zip(grid_spec, ws):
        _, s = run_weights(ts, o, c, wt)
        grid.append({"arm_dd20": a20, "arm_dd60": a60, "vol_ratio": vr,
                     **pack(s)})
        print(f"grid {a20:.0%}/{a60:.0%} vol{vr:.2f}  "
              f"CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:4.2f}  exp {s['exposure']*100:5.1f}%")
    out["grid"] = grid

    # ---- neighbours (robustness, not used to choose the centre) -------------
    neigh_spec = [
        ("hi_window 5", {"hi_n": 5}),
        ("hi_window 20", {"hi_n": 20}),
        ("trail 6%", {"trail": 0.06}),
        ("trail 10%", {"trail": 0.10}),
        ("shallow vol-only", {"shallow_rule": "vol_only"}),
        ("shallow hi-only", {"shallow_rule": "hi_only"}),
        ("deep vol-or-hi", {"deep_rule": "vol_or_hi"}),
        ("start in cash", {"start_long": False}),
    ]
    neigh = []
    for name, kw in neigh_spec:
        wt = build_weights(ts, o, c, **kw)
        _, s = run_weights(ts, o, c, wt)
        neigh.append({"name": name, **pack(s)})
        print(f"neigh {name:20s} CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}  "
              f"exp {s['exposure']*100:5.1f}%")
    out["neighbours"] = neigh

    # ---- ablations ----------------------------------------------------------
    abl = []
    for name, kw in [
        ("10d-low exit added", {"use_lo_exit": True}),
        ("trailing-only exit", {"trail_only": True}),
        ("no deep/slow branch (all shallow)", {"deep_rule": "vol_or_hi"}),
    ]:
        wt = build_weights(ts, o, c, **kw)
        _, s = run_weights(ts, o, c, wt)
        abl.append({"name": name, **pack(s)})
        print(f"ablate {name:34s} CAGR {s['cagr']*100:6.2f}%  "
              f"DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:4.2f}  "
              f"exp {s['exposure']*100:5.1f}%")
    out["ablations"] = abl

    # ---- controls / attribution --------------------------------------------
    controls = {}
    const = float(np.mean(t))
    w_const = np.zeros((len(ts), 3))
    w_const[:, COL_T] = const
    _, s = run_weights(ts, o, c, w_const)
    controls["constant_exposure_same_mean"] = {**pack(s), "weight": const}

    w_bh = np.zeros((len(ts), 3))
    w_bh[:, COL_T] = 1.0
    _, s = run_weights(ts, o, c, w_bh)
    controls["tqqq_buy_hold_harness"] = pack(s)

    w_cash = np.zeros((len(ts), 3))
    _, s = run_weights(ts, o, c, w_cash)
    controls["all_cash"] = pack(s)
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:32s} CAGR {v['cagr']*100:6.2f}%  "
              f"DD {v['max_drawdown']*100:5.2f}%  Sh {v['sharpe']:4.2f}")

    # ---- episode table ------------------------------------------------------
    out["episodes"] = episode_table(sig, eps, ts, o, c)
    out["n_round_trips"] = len(out["episodes"])
    out["cash_fraction"] = float(1.0 - np.mean(t))
    out["deep_episodes"] = int(sum(
        1 for e in out["episodes"] if str(e.get("entry_why", "")).startswith("deep")))
    cash = cash_attribution(sig, t, o, c)
    out["cash_periods"] = cash
    out["n_cash_episodes"] = len(cash)
    out["cash_log_tqqq"] = float(sum(x["log_tqqq"] for x in cash))
    out["negative_cash_episodes"] = int(sum(
        1 for x in cash if x["tqqq_return"] < 0))
    out["avg_cash_days"] = float(np.mean([x["days"] for x in cash]))
    out["median_cash_days"] = float(np.median([x["days"] for x in cash]))
    out["strategy_log"] = float(np.log(res1["equity"][-1] / res1["equity"][0]))

    j18 = bt.start_index(ts, "2018-01-29")
    j18e = bt.start_index(ts, "2018-04-26")
    x18 = c[j18:j18e, COL_T]
    out["benchmark_dd_2018_window"] = float(
        -(x18 / np.maximum.accumulate(x18) - 1.0).min())

    # ---- placebo -----------------------------------------------------------
    rng = np.random.default_rng(20261127)
    real = s1["cagr"]
    block_cagrs = []
    for _ in range(80):
        tp = block_permute(t, 20, rng)
        wp = np.zeros((len(ts), 3))
        wp[:, COL_T] = weights_from_daily(sig, tp)
        _, sp = run_weights(ts, o, c, wp)
        block_cagrs.append(sp["cagr"])
    block_cagrs = np.array(block_cagrs)

    random_cagrs = []
    for _ in range(80):
        tp = random_breaker(t, rng)
        wp = np.zeros((len(ts), 3))
        wp[:, COL_T] = weights_from_daily(sig, tp)
        _, sp = run_weights(ts, o, c, wp)
        random_cagrs.append(sp["cagr"])
    random_cagrs = np.array(random_cagrs)

    out["placebo"] = {
        "real_cagr": float(real),
        "block_permutation_20d": {
            "n_draws": int(len(block_cagrs)),
            "mean": float(block_cagrs.mean()),
            "p95": float(np.percentile(block_cagrs, 95)),
            "p_value": float((block_cagrs >= real).mean()),
        },
        "random_circuit_breaker": {
            "n_draws": int(len(random_cagrs)),
            "mean": float(random_cagrs.mean()),
            "p95": float(np.percentile(random_cagrs, 95)),
            "p_value": float((random_cagrs >= real).mean()),
        },
    }
    print("placebo", {k: (v if not isinstance(v, dict) else
                         {kk: round(float(vv), 4) for kk, vv in v.items()})
                     for k, v in out["placebo"].items()})

    # ---- cut tests ---------------------------------------------------------
    cuts = {}
    for year in (2018, 2020, 2022, 2023):
        cuts[str(year)] = {
            "strategy": calendar_year_cut(res1["ts"], res1["equity"], year),
            "benchmark_ex_year": calendar_year_cut(ts[i0:], c[i0:, COL_T], year),
        }
    out["cut_tests"] = cuts
    for y, v in cuts.items():
        print(f"cut ex-{y}: strat {v['strategy']['cagr']*100:6.2f}% / "
              f"{v['strategy']['max_drawdown']*100:5.2f}%  "
              f"bench {v['benchmark_ex_year']['cagr']*100:6.2f}% / "
              f"{v['benchmark_ex_year']['max_drawdown']*100:5.2f}%")

    # ---- causality: truncation at 2022-01-03 -------------------------------
    j = bt.start_index(ts, "2022-01-03")
    j0 = int(sig["first"][np.searchsorted(sig["first"], j)])
    w_trunc = build_weights(ts[:j0], o[:j0], c[:j0])
    out["causality"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_trunc[:-1], w[:j0 - 1])),
    }
    print("causality", out["causality"])

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
