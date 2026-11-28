"""Revisit: `time-of-day` rebuilt as a conditional closing-pressure carry.

NOT YET RUN.  This file is the frozen specification; `python strategy.py` is
deliberately not executed until the lead authorises the test.

The strategy
------------
Universe: TQQQ (long, 3x QQQ) and cash.
Clock   : one decision per session at 15:58 ET.
           - entry at the open of the session's LAST 1-minute bar (~15:59)
           - exit  at the open of the next session's 32nd bar (~10:01)
           - flat otherwise -> holding period about 17 hours
Signal  : (1) closing pressure = QQQ log return over the last ``close_window``
              minutes of the session, measured *before* the entry;
          (2) risk state = the block's own realised volatility.
Gate    : hold only when the closing block moved against the sign we want
          (``close_sign``, default -1 = "the close was sold"), the move is at
          least ``close_min_z`` typical closing moves, and the block's realised
          vol is within ``vol_mult`` of its 60-session median.
Size    : ``min(1, vol_target / realised_vol)`` while the gate is on, else 0.

No 100-250 day moving average of QQQ/TQQQ/SPY/NDX is used anywhere.  The only
regime inputs are the closing 30 minutes and the strategy's own completed block
returns.  All of them are strictly causal:

  * a block entered on session k ends at ~10:01 of session k+1, so at 15:58 of
    session k the newest completed block is k-1;
  * ``c30`` on session k uses closes up to bar (last-1) of session k, and the
    entry fills at the open of the last bar, so it cannot see the fill price;
  * the magnitude reference is the median of |c30| over the previous 20
    sessions only.

Development window 2016-01-04 .. 2023-12-29.  The holdout is never loaded while
parameters are chosen: ``load(DEV_END)`` is the only panel call used for
development.  ``windows.10y`` and ``windows.5y`` in result.json are filled once,
after the freeze, from a separate panel that overlaps the holdout.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS_1M = 252 * 390

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
FULL_END = "2026-10-23"
T10, T5 = "2017-01-03", "2021-10-25"
DEV_ONLY = os.environ.get("REVISIT_DEV_ONLY") == "1"
SUBS = (("2016-01-04", "2019-12-31", "2016-19"),
        ("2020-01-02", "2021-12-31", "2020-21"),
        ("2022-01-03", "2023-12-29", "2022-23"))

SYMS = ("QQQ", "TQQQ", "BIL")
COL = {"QQQ": 0, "TQQQ": 1, "BIL": 2}

EXIT_BAR = 31          # exit fills at the open of the session's 32nd bar (~10:01)


# --------------------------------------------------------------------------- #
# panel and session plumbing
# --------------------------------------------------------------------------- #
def load(panel_end: str = DEV_END):
    return bt.panel(SYMS, DEV_START, panel_end, "1min", warmup_days=0)


def session_bounds(ts: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    _, starts, ends = bt.day_bounds(ts)
    return starts, ends


def block_log_returns(op: np.ndarray, starts: np.ndarray, ends: np.ndarray,
                      sym: str = "TQQQ") -> np.ndarray:
    """r[k] = log(exit open / entry open) for the block entered on session k."""
    c = COL[sym]
    ns = len(starts)
    r = np.full(ns, np.nan)
    for k in range(ns - 1):
        j = min(starts[k + 1] + EXIT_BAR, ends[k + 1])
        entry, exitp = op[ends[k], c], op[j, c]
        if entry > 0 and exitp > 0:
            r[k] = np.log(exitp / entry)
    return r


# --------------------------------------------------------------------------- #
# specification
# --------------------------------------------------------------------------- #
@dataclass
class Params:
    use_close: bool = True        # apply the closing-pressure condition
    close_sign: int = -1          # -1: hold after a sold close; +1: momentum branch
    close_window: int = 30        # minutes in the closing block
    close_min_z: float = 0.5      # |c30| must be >= this multiple of typical
    close_ref: int = 20           # sessions in the |c30| median

    use_gate: bool = True         # apply the block-vol regime
    vol_look: int = 10            # sessions in the block-vol estimate
    ref_look: int = 60            # sessions in the median reference
    vol_mult: float = 1.5         # gate off when vol > vol_mult * median

    vol_target: float = 0.40      # annualised block-vol target; 0 disables sizing
    size_floor: float = 0.0

    idle: str = "cash"            # "cash" | "bil"

    def tag(self) -> str:
        return (f"close{int(self.use_close)}{self.close_sign}"
                f"w{self.close_window}z{self.close_min_z}"
                f"_gate{int(self.use_gate)}v{self.vol_look}"
                f"m{self.vol_mult}_t{self.vol_target}_{self.idle}")


# --------------------------------------------------------------------------- #
# causal signals
# --------------------------------------------------------------------------- #
_SIGNAL_CACHE: dict = {}


def clock_signals(ts, opens, closes, p: Params) -> dict:
    """Closing block return, its normaliser, block vol state.  All causal.

    Only four parameters enter the signals, and the variants, placebo and
    neighbourhood reuse them, so results are memoised per panel and those
    parameters.  The arrays are shared and must be treated as read-only.
    """
    key = (id(ts), id(opens), id(closes), p.close_window, p.close_ref,
           p.vol_look, p.ref_look)
    hit = _SIGNAL_CACHE.get(key)
    if hit is not None and hit[0] is ts and hit[1] is opens and hit[2] is closes:
        return dict(hit[3])
    sig = _clock_signals(ts, opens, closes, p)
    if len(_SIGNAL_CACHE) >= 32:
        _SIGNAL_CACHE.clear()
    _SIGNAL_CACHE[key] = (ts, opens, closes, sig)
    return dict(sig)


def _clock_signals(ts, opens, closes, p: Params) -> dict:
    starts, ends = session_bounds(ts)
    ns = len(starts)
    qc = closes[:, COL["QQQ"]]

    c30 = np.full(ns, np.nan)
    for k in range(ns):
        i1 = ends[k]
        j = max(starts[k], i1 - p.close_window)
        a, b = qc[j], qc[i1 - 1]      # close of bar (last-window) .. close of 15:58
        if a > 0 and b > 0:
            c30[k] = float(np.log(b / a))

    absref = np.full(ns, np.nan)
    for k in range(ns):
        lo = k - p.close_ref
        if lo < 0:
            continue
        w = np.abs(c30[lo:k])
        w = w[np.isfinite(w)]
        if w.size >= max(5, p.close_ref // 2):
            absref[k] = float(np.median(w))

    r = block_log_returns(opens, starts, ends, "TQQQ")
    vol = np.full(ns, np.nan)
    for k in range(ns):
        lo = k - p.vol_look
        if lo < 0:
            continue
        w = r[lo:k]
        if np.isfinite(w).all() and w.size > 2:
            vol[k] = float(np.std(w, ddof=1) * np.sqrt(252.0))
    ref = np.full(ns, np.nan)
    for k in range(ns):
        lo = k - p.ref_look
        if lo < 0:
            continue
        w = vol[lo:k]
        w = w[np.isfinite(w)]
        if w.size >= max(10, p.ref_look // 3):
            ref[k] = float(np.median(w))

    return {"c30": c30, "absref": absref, "r": r, "vol": vol, "ref": ref,
            "starts": starts, "ends": ends}


def block_sizes(sig: dict, p: Params) -> tuple[np.ndarray, dict]:
    ns = len(sig["c30"])
    size = np.zeros(ns)
    fail = {"warmup": 0, "close_sign": 0, "close_small": 0, "vol_gate": 0}
    for k in range(ns):
        c30, absref = sig["c30"][k], sig["absref"][k]
        v, m = sig["vol"][k], sig["ref"][k]
        if p.use_close:
            if not (np.isfinite(c30) and np.isfinite(absref)) or absref <= 0:
                fail["warmup"] += 1
                continue
            if p.close_sign > 0 and not (c30 > 0):
                fail["close_sign"] += 1
                continue
            if p.close_sign < 0 and not (c30 < 0):
                fail["close_sign"] += 1
                continue
            if abs(c30) < p.close_min_z * absref:
                fail["close_small"] += 1
                continue
        if p.use_gate:
            if not (np.isfinite(v) and np.isfinite(m)) or v > p.vol_mult * m:
                fail["vol_gate"] += 1
                continue
        s = 1.0
        if p.vol_target > 0:
            if not np.isfinite(v):
                fail["warmup"] += 1
                continue
            s = min(1.0, p.vol_target / max(v, 1e-6))
        size[k] = max(p.size_floor, s)
    info = {"active_sessions": int((size > 0).sum()), "mean_size": float(size.mean()),
            "mean_size_when_active": float(size[size > 0].mean()) if (size > 0).any() else 0.0,
            "reject_reasons": fail}
    return size, info


def weights_from_size(ts, starts, ends, size, p: Params) -> np.ndarray:
    """Targets are set on a few bars per session and held until the next one."""
    ns, n = len(starts), len(ts)
    idle = (0.0, 0.0, 1.0) if p.idle == "bil" else (0.0, 0.0, 0.0)
    marks = {}                                     # bar -> row; later writes win
    for k in range(ns):
        if k > 0 and size[k - 1] > 0:
            j = min(starts[k] + EXIT_BAR, ends[k])
            marks[(j - 1) % n] = idle              # exit at ~10:01
        s = size[k]
        if s > 0:
            marks[(ends[k] - 1) % n] = (0.0, s, 0.0)   # entry at ~15:59
        else:
            marks[(ends[k] - 1) % n] = idle
    return _hold_rows(marks, n)


def _hold_rows(marks: dict, n: int) -> np.ndarray:
    """Forward-fill the marked rows over n bars, zeros before the first one.

    Same result as filling an (n, 3) NaN array at the marks and running
    `pd.DataFrame(rows).ffill().fillna(0.0).to_numpy()`.
    """
    out = np.zeros((n, 3))
    if not marks:
        return out
    idx = np.fromiter(sorted(marks), dtype=np.int64, count=len(marks))
    vals = np.array([marks[i] for i in idx.tolist()], dtype=float)
    out[idx[0]:] = np.repeat(vals, np.diff(np.r_[idx, n]), axis=0)
    return out


def build_weights(ts, opens, closes, params: Params, sym: str = "TQQQ"
                  ) -> tuple[np.ndarray, dict]:
    """Target weights and diagnostics for the block strategy."""
    sig = clock_signals(ts, opens, closes, params)
    size, info = block_sizes(sig, params)
    w = weights_from_size(ts, sig["starts"], sig["ends"], size, params)
    info.update({"params": asdict(params), "sessions": int(len(sig["starts"])),
                 "exit_bar": EXIT_BAR, "entry": "open of the session's last bar"})
    return w, info


# --------------------------------------------------------------------------- #
# reference base (correlation only -- not part of the strategy)
# --------------------------------------------------------------------------- #
def baseline_weights(ts, closes, sma: int = 165) -> np.ndarray:
    """Original shared base: TQQQ when QQQ close > SMA165, else BIL.

    Used only to measure F6 (daily-return correlation with the old base).  It is
    never combined with, called by, or mixed into the strategy weights.
    """
    sess = pd.DatetimeIndex(sorted(set(ts.date)))
    dcl = pd.Series(closes[:, 0], index=ts).groupby(ts.date).last()
    dcl.index = pd.to_datetime(dcl.index)
    sig = (dcl > dcl.rolling(sma).mean()).fillna(False).reindex(sess).to_numpy()
    starts, ends = session_bounds(ts)
    rows = np.full((len(ts), 3), np.nan)
    for k in range(len(ends)):
        rows[ends[k]] = [0.0, 1.0, 0.0] if sig[k] else [0.0, 0.0, 1.0]
    return pd.DataFrame(rows).ffill().fillna(0.0).to_numpy()


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def slice_idx(ts, lo, hi):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    # Include the whole `hi` session.  A bare 00:00 timestamp drops the final
    # 09:30-15:59 bars and makes the curve end one session early.
    end = pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)
    j = int(ts.searchsorted(end, side="left"))
    return i, j


def run_window(w, ts, op, cl, lo, hi, slip):
    i, j = slice_idx(ts, lo, hi)
    res = bt.simulate(ts[i:j], op[i:j], cl[i:j], w[i:j], band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_returns(res):
    """Session-close returns (same as grouping the minute equity by date)."""
    dates, _, last = bt.day_bounds(res["ts"])
    eq = pd.Series(np.asarray(res["equity"])[last], index=pd.Index(dates[last]))
    return eq.pct_change().dropna()


def pack(s: dict) -> dict:
    return {"cagr": s["cagr"], "max_drawdown": s["max_drawdown"], "sharpe": s["sharpe"],
            "sortino": s["sortino"], "volatility": s["volatility"],
            "fills": s["fills"], "turnover": s["turnover"],
            "exposure": s["exposure"], "ending_equity": s["ending_equity"]}


def conditional_test(sig: dict, ts) -> dict:
    """F1: mean block return after a sold close vs a bought close (dev only)."""
    starts, ends = sig["starts"], sig["ends"]
    keep = (pd.DatetimeIndex(pd.to_datetime(sorted(set(ts.date)))) >= pd.Timestamp(DEV_START)) \
        & (pd.DatetimeIndex(pd.to_datetime(sorted(set(ts.date)))) <= pd.Timestamp(DEV_END))
    r, c30 = sig["r"], sig["c30"]
    m = np.isfinite(r) & np.isfinite(c30) & keep
    neg, pos = r[m & (c30 < 0)], r[m & (c30 >= 0)]
    if neg.size < 30 or pos.size < 30:
        return {"n_neg": int(neg.size), "n_pos": int(pos.size)}
    se = np.sqrt(neg.var(ddof=1) / neg.size + pos.var(ddof=1) / pos.size)
    diff = float(neg.mean() - pos.mean())
    return {"n_neg": int(neg.size), "n_pos": int(pos.size),
            "mean_bp_after_sold_close": float(neg.mean() * 1e4),
            "mean_bp_after_bought_close": float(pos.mean() * 1e4),
            "diff_bp": float(diff * 1e4),
            "t_stat": float(diff / se) if se > 0 else None,
            "hit_rate_neg": float((neg > 0).mean()),
            "hit_rate_pos": float((pos > 0).mean())}


def placebo(w, ts, op, cl, sig, p: Params, n_draws: int = 200, seed: int = 7) -> dict:
    """F5: shuffle which nights are active, keeping the same count and sizes."""
    size_real, _ = block_sizes(sig, p)
    active = np.flatnonzero(size_real > 0)
    if active.size == 0:
        return {"n_draws": 0}
    sizes = size_real[active]
    rng = np.random.default_rng(seed)
    cagrs = []
    res, st = run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
    real = st["cagr"]
    # Same draws as run_window() one at a time, simulated in parallel batches.
    i, j = slice_idx(ts, DEV_START, DEV_END)
    batch = []
    for d in range(n_draws):
        perm = rng.permutation(size_real.size)
        s = np.zeros_like(size_real)
        s[perm[:active.size]] = sizes
        batch.append(weights_from_size(ts, sig["starts"], sig["ends"], s, p)[i:j])
        if len(batch) == 12 or d == n_draws - 1:
            for r in bt.simulate_many(ts[i:j], op[i:j], cl[i:j], batch,
                                      band=0.02, slippage_bps=1.0):
                cagrs.append(bt.stats(r, BARS_1M)["cagr"])
            batch = []
    cagrs = np.array(cagrs)
    return {"n_draws": n_draws, "real_cagr": float(real),
            "placebo_mean": float(cagrs.mean()), "placebo_p95": float(np.percentile(cagrs, 95)),
            "p_value": float((cagrs >= real).mean())}


def freeze_hash(params: Params) -> str:
    payload = (HERE / "strategy.py").read_bytes() + json.dumps(asdict(params),
                                                               sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def decide(out_variants: dict, corr: dict, f1: dict, f5: dict,
           tqqq_dev_cagr: float) -> tuple[str, dict]:
    """Apply the pre-registered falsifiers.  Status is computed, never typed in."""
    v0 = out_variants["V0_unconditional"]["dev_1bp"]["cagr"]
    v1 = out_variants["V1_close_only"]["dev_1bp"]["cagr"]
    v3 = out_variants["V3_full"]["dev_1bp"]
    sub0 = out_variants["V0_unconditional"]["sub_periods_1bp"]
    sub1 = out_variants["V1_close_only"]["sub_periods_1bp"]

    f1_ok = bool(f1.get("diff_bp", 0.0) >= 5.0 and (f1.get("t_stat") or 0.0) >= 1.5)
    f2_ok = bool(v1 > v0)
    f3_ok = bool(v3["max_drawdown"] <= 0.45 and v3["sharpe"] >= 0.70)
    f4_ok = bool(sum(sub1[t]["cagr"] > sub0[t]["cagr"] for t in sub1) >= 2)
    f5_ok = bool(f5.get("p_value", 1.0) < 0.10)
    f6_ok = bool(corr["V3_full"] < 0.60)
    f7_ok = bool(out_variants["V3_full"]["dev_5bp"]["cagr"] > tqqq_dev_cagr)
    checks = {"F1_sign_and_size": f1_ok, "F2_conditioning_beats_unconditional": f2_ok,
              "F3_risk": f3_ok, "F4_subperiods": f4_ok, "F5_placebo": f5_ok,
              "F6_independence": f6_ok, "F7_cost_5bp": f7_ok,
              "V4_opposite_sign_cagr": out_variants["V4_momentum_sign"]["dev_1bp"]["cagr"],
              "V0_cagr": v0, "V1_cagr": v1}

    if not (f3_ok and f6_ok):
        status = "rejected"
    elif not f2_ok:
        status = "retired_overlay_only"
    elif f1_ok and f3_ok and f4_ok and f5_ok and f6_ok and f7_ok:
        status = "passed"
    elif f1_ok and f3_ok and f4_ok and f5_ok and f6_ok:
        status = "fragile"
    else:
        status = "rejected"
    return status, checks


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    ts, op, cl = load(DEV_END)
    print(f"dev panel {len(ts):,} bars, {len(np.unique(ts.date))} sessions, "
          f"{ts[0].date()} .. {ts[-1].date()}")

    base = baseline_weights(ts, cl)
    bres, bs = run_window(base, ts, op, cl, DEV_START, DEV_END, 1.0)
    bdr = daily_returns(bres)
    print(f"165d baseline dev: CAGR {bs['cagr']*100:.2f}% DD {bs['max_drawdown']*100:.2f}%")

    variants = {
        "V0_unconditional": Params(use_close=False, use_gate=False, vol_target=0.0),
        "V1_close_only": Params(use_close=True, use_gate=False, vol_target=0.0),
        "V2_gate_only": Params(use_close=False, use_gate=True, vol_target=0.0),
        "V3_full": Params(),
        "V4_momentum_sign": Params(close_sign=+1),
        "V5_full_bil": Params(idle="bil"),
    }

    out_variants: dict[str, dict] = {}
    corr: dict[str, float] = {}
    for name, p in variants.items():
        w, info = build_weights(ts, op, cl, p)
        rec = {"params": asdict(p), "info": info}
        for slip in (1.0, 5.0, 10.0):
            res, s = run_window(w, ts, op, cl, DEV_START, DEV_END, slip)
            rec[f"dev_{int(slip)}bp"] = pack(s)
            if slip == 1.0:
                corr[name] = float(daily_returns(res).corr(bdr))
                sub = {}
                for lo, hi, tag in SUBS:
                    _, ss = run_window(w, ts, op, cl, lo, hi, 1.0)
                    sub[tag] = {"cagr": ss["cagr"], "max_drawdown": ss["max_drawdown"],
                                "sharpe": ss["sharpe"]}
                rec["sub_periods_1bp"] = sub
        rec["corr_vs_165d_baseline"] = corr[name]
        out_variants[name] = rec
        d = rec["dev_1bp"]
        print(f"{name:20s} 1bp CAGR {d['cagr']*100:6.2f}% DD {d['max_drawdown']*100:5.2f}% "
              f"sh {d['sharpe']:4.2f} fills {d['fills']:5d} corr {corr[name]:.2f} "
              f"active {info['active_sessions']}")

    # F1 and F5 on the frozen full variant
    p3 = variants["V3_full"]
    sig = clock_signals(ts, op, cl, p3)
    w3 = build_weights(ts, op, cl, p3)[0]
    f1 = conditional_test(sig, ts)
    print("F1 conditional test:", f1)
    f5 = placebo(w3, ts, op, cl, sig, p3)
    print("F5 placebo:", f5)

    # parameter neighbourhood (+-1 step), V3 as the centre
    grid = {}
    for key, values in (("vol_look", (5, 10, 20)), ("ref_look", (40, 60, 90)),
                        ("vol_mult", (1.25, 1.5, 2.0)), ("close_window", (20, 30, 45)),
                        ("close_min_z", (0.0, 0.5, 1.0)), ("vol_target", (0.30, 0.40, 0.50))):
        row = {}
        for v in values:
            pp = Params(**{**asdict(p3), key: v})
            w, _ = build_weights(ts, op, cl, pp)
            _, s = run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
            row[str(v)] = {"cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                           "sharpe": s["sharpe"]}
        grid[key] = row
    print("neighbourhood:", {k: {kk: round(vv["cagr"] * 100, 1) for kk, vv in v.items()}
                             for k, v in grid.items()})

    # ---- freeze, then dev only unless the lead explicitly runs the full sample ---- #
    frozen = freeze_hash(p3)
    windows = {"dev": {}, "holdout": {}, "10y": {}, "5y": {}}
    tqqq = {}
    qqq = {}
    if DEV_ONLY:
        ts2, op2, cl2 = load(DEV_END)
        w_warm = build_weights(ts2, op2, cl2, p3)[0]
        for slip in (1.0, 5.0, 10.0):
            _, s = run_window(w_warm, ts2, op2, cl2, DEV_START, DEV_END, slip)
            windows["dev"][f"{int(slip)}bp"] = pack(s)
        i, j = slice_idx(ts2, DEV_START, DEV_END)
        tqqq["dev"] = bt.benchmark(cl2[i:j, 1], ts2[i:j], BARS_1M)
        tqqq["dev"]["symbol"] = "TQQQ"
        qqq["dev"] = bt.benchmark(cl2[i:j, 0], ts2[i:j], BARS_1M)
    else:
        ts2, op2, cl2 = load(FULL_END)
        w_warm = build_weights(ts2, op2, cl2, p3)[0]
        for slip in (1.0, 5.0, 10.0):
            _, s = run_window(w_warm, ts2, op2, cl2, DEV_START, DEV_END, slip)
            windows["dev"][f"{int(slip)}bp"] = pack(s)
        for tag, lo, hi in (("10y", T10, FULL_END), ("5y", T5, FULL_END)):
            for slip in (1.0, 5.0):
                _, s = run_window(w_warm, ts2, op2, cl2, lo, hi, slip)
                windows[tag][f"{int(slip)}bp"] = pack(s)
        for tag, lo, hi in (("dev", DEV_START, DEV_END), ("10y", T10, FULL_END), ("5y", T5, FULL_END)):
            i, j = slice_idx(ts2, lo, hi)
            tqqq[tag] = bt.benchmark(cl2[i:j, 1], ts2[i:j], BARS_1M)
            tqqq[tag]["symbol"] = "TQQQ"
        i, j = slice_idx(ts2, DEV_START, DEV_END)
        qqq["dev"] = bt.benchmark(cl2[i:j, 0], ts2[i:j], BARS_1M)

    status, checks = decide(out_variants, corr, f1, f5, tqqq["dev"]["cagr"])

    result = {
        "agent": "time-of-day",
        "original": "research/agents/time-of-day",
        "status": status,
        "idea": "The overnight+first-30m block pays because it settles the previous "
                "session's closing pressure, so it should be held selectively after "
                "a sold close rather than every night.",
        "hypothesis": "Block return is decreasing in the last-30-minute QQQ return; "
                      "conditioning plus a self-referential vol gate beats holding "
                      "every night.",
        "universe": ["TQQQ", "BIL (idle variant only)", "cash"],
        "frozen_commit": frozen,
        "variants_tried": len(variants),
        "corr_vs_165d_baseline": corr["V3_full"],
        "max_corr_vs_other_rebuilds": None,
        "windows": windows,
        "marks": "1m",
        "benchmarks": {"tqqq": tqqq, "qqq": qqq, "spy": None,
                       "original": {"note": "original result.json is on 2017-2026 / "
                                            "2021-2026 windows, 10y 49.23%/42.66%, "
                                            "5y 28.89%/34.54% at 1bp"}},
        "diagnostics": {"falsifiers": checks, "f1_conditional": f1, "f5_placebo": f5,
                        "neighbourhood": grid, "baseline_dev": pack(bs)},
    }
    (HERE / "result.json").write_text(json.dumps(result, indent=2, default=float))
    print("wrote result.json")


if __name__ == "__main__":
    main()
