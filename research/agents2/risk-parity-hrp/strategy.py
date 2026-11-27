"""Risk-parity / HRP overlay on the QQQ 165-day regime + 4% minute stop.

Final strategy (RP-half)
------------------------
1. Regime (daily, lagged): QQQ close > 165-day SMA of QQQ closes -> risk-on
   for the next session; otherwise 100% BIL.
2. Risk-on sessions hold 100% TQQQ by default (including overnight).
3. Intraday stop (unchanged from the round-1 winner): on a session that is
   *armed* (QQQ's first minute below its 20-day SMA x 1.01), if TQQQ trades 4%
   below the session open, the TQQQ sleeve is liquidated at the next minute's
   open. Unlike the winner, the proceeds are split 50/50 between QQQ and BIL
   (the "risk-parity" de-risking: half the stopped risk stays in the equity
   factor at 1x, half goes to cash). The position is held for the rest of the
   session and the following night; the next session restarts at the daily
   target if the regime is still on.

Reference variants computed here
--------------------------------
* `winner`      : stop proceeds 100% to BIL (the round-1 bar).
* `voltarget70` : inverse-vol / vol-target brake, w_TQQQ = min(1, 0.70/sigma_T),
                  remainder QQQ, stop proceeds to BIL. All inputs lagged.
* HRP and plain inverse-vol *unconstrained* across QQQ/TQQQ/BIL are reported
  as average weights only: they are degenerate (see report.md).

No look-ahead: every daily signal at session k uses closes through k-1. Fills
are at the next bar's open; slippage is charged on traded notional.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/risk-parity-hrp/strategy.py
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
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
SMA_N, MA20, STOP, ARM = 165, 20, 0.04, 0.01
# Round-1 winner reference (README / daily-regime-minute-entry).
WINNER = {"10y": {"cagr": 0.5880, "max_drawdown": 0.4456,
                  "5bp": (0.5460, 0.4708), "10bp": (0.4950, 0.5006)},
          "5y": {"cagr": 0.4988, "max_drawdown": 0.3349,
                 "5bp": (0.4589, 0.3413), "10bp": (0.4105, 0.3493)}}
TQQQ_BH = {"10y": {"cagr": 0.3928, "max_drawdown": 0.8168},
           "5y": {"cagr": 0.1347, "max_drawdown": 0.8168}}


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_panel():
    cache = HERE / "panel_1m.npz"
    if cache.exists():
        z = np.load(cache)
        ts = pd.DatetimeIndex(z["ts"], tz="UTC").tz_convert("America/New_York")
        return ts, z["opens"], z["closes"]
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    np.savez_compressed(cache, ts=ts.values.astype("datetime64[ns]"),
                        opens=opens, closes=closes)
    return ts, opens, closes


def lag(x):
    out = np.empty_like(x)
    out[0] = np.nan
    out[1:] = x[:-1]
    return out


class Signals:
    def __init__(self, ts, opens, closes):
        self.ts, self.opens, self.closes = ts, opens, closes
        dates = np.array([t.date() for t in ts])
        self.dates = dates
        first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        last = np.r_[first[1:] - 1, len(ts) - 1]
        self.first, self.last = first, last
        self.n, self.d = len(ts), len(first)
        self.dcl = closes[last]                 # (d,3) session closes
        q = self.dcl[:, 0]
        sma = pd.Series(q).rolling(SMA_N).mean().to_numpy()
        ma20 = pd.Series(q).rolling(MA20).mean().to_numpy()
        self.risk_on = np.zeros(self.d, bool)
        self.risk_on[1:] = q[:-1] > lag(sma)[1:]
        ma20_prev = lag(ma20)
        self.armed = np.zeros(self.d, bool)
        for k in range(1, self.d):
            if self.risk_on[k] and np.isfinite(ma20_prev[k]):
                self.armed[k] = (closes[first[k], 0] < ma20_prev[k] * (1.0 + ARM))
        # minute-level stop state
        self.stopped = np.zeros(self.n, bool)
        self.stop_events = 0
        for k in range(self.d):
            if not self.armed[k]:
                continue
            f, l = first[k], last[k]
            base = opens[f, 1]
            dead = False
            for i in range(f, l + 1):
                if not dead and closes[i, 1] < base * (1.0 - STOP):
                    dead = True
                    self.stop_events += 1
                self.stopped[i] = dead
        self.day_id = np.repeat(np.arange(self.d), np.diff(np.r_[first, self.n]))
        self.rets = np.diff(self.dcl, axis=0) / self.dcl[:-1]

    def vol(self, win):
        v = pd.DataFrame(self.rets).rolling(win).std().to_numpy() * np.sqrt(252)
        v = np.vstack([np.full((1, 3), np.nan), v])
        return lag(v)

    def weights(self, wt_tqqq, dest="bil"):
        w = np.zeros((self.n, 3))
        on = self.risk_on[self.day_id]
        tq = np.nan_to_num(wt_tqqq, nan=1.0)[self.day_id]
        dead = self.stopped
        live = on & ~dead
        w[:, 1] = np.where(live, tq, 0.0)
        wq = np.where(on, 1.0 - tq, 0.0)
        w[:, 2] = np.where(on, 0.0, 1.0)
        if dest == "bil":
            w[:, 2] += np.where(on & dead, tq, 0.0)
        elif dest == "half":
            wq = wq + np.where(on & dead, 0.5 * tq, 0.0)
            w[:, 2] += np.where(on & dead, 0.5 * tq, 0.0)
        else:
            raise ValueError(dest)
        w[:, 0] = wq
        return w


# --------------------------------------------------------------------------
# reference risk models (weights only; the unconstrained versions are
# degenerate on this asset set and are not backtested)
# --------------------------------------------------------------------------
def hrp_weights(cov):
    """Lopez de Prado (2016) HRP, single linkage, recursive bisection."""
    k = cov.shape[0]
    sd = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sd, sd)
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, None))
    cl = {i: [i] for i in range(k)}
    tree = {i: ("leaf", i) for i in range(k)}
    dist_c = {(i, j): dist[i, j] for i in range(k) for j in range(i + 1, k)}
    active = list(range(k))
    nxt = k
    while len(active) > 1:
        _, a, b = min(((dist_c[(min(x, y), max(x, y))], x, y)
                       for i, x in enumerate(active) for y in active[i + 1:]),
                      key=lambda t: t[0])
        cl[nxt] = cl[a] + cl[b]
        for c in active:
            if c in (a, b):
                continue
            da = min(dist[i, j] for i in cl[a] for j in cl[c])
            db = min(dist[i, j] for i in cl[b] for j in cl[c])
            dist_c[(min(nxt, c), max(nxt, c))] = min(da, db)
        tree[nxt] = ("node", a, b)
        active = [c for c in active if c not in (a, b)] + [nxt]
        nxt += 1
    root = active[0]

    def order(node):
        return [tree[node][1]] if tree[node][0] == "leaf" else order(tree[node][1]) + order(tree[node][2])

    def cvar(members):
        idx = np.array(members)
        sub = cov[np.ix_(idx, idx)]
        iv = 1.0 / np.diag(sub)
        iv = iv / iv.sum()
        return float(iv @ sub @ iv)

    def alloc(members):
        if len(members) == 1:
            return {members[0]: 1.0}
        h = len(members) // 2
        left, right = members[:h], members[h:]
        al = (1.0 / cvar(left)) / (1.0 / cvar(left) + 1.0 / cvar(right))
        out = {}
        for m, a in ((left, al), (right, 1.0 - al)):
            for i, w in alloc(m).items():
                out[i] = out.get(i, 0.0) + a * w
        return out

    w = np.zeros(k)
    for i, v in alloc(order(root)).items():
        w[i] = v
    return w


def risk_model_weights(sig):
    """Average unconstrained HRP / inverse-vol weights (diagnostic only)."""
    rets = sig.rets
    hrp, iv = [], []
    for k in range(60, sig.d):
        win = rets[k - 60:k]
        cov = np.cov(win, rowvar=False)
        hrp.append(hrp_weights(cov))
        s = np.sqrt(np.diag(cov))
        iv.append((1 / s) / (1 / s).sum())
    hrp = np.array(hrp)
    iv = np.array(iv)
    on = sig.risk_on[60:]
    out = {"hrp_all": hrp.mean(0).tolist(), "iv_all": iv.mean(0).tolist(),
           "hrp_risk_on": hrp[on].mean(0).tolist(),
           "iv_risk_on": iv[on].mean(0).tolist(),
           "qqq_tqqq_corr_60d_avg": float(np.mean(
               [np.corrcoef(w[:, 0], w[:, 1])[0, 1] for w in
                (rets[k - 60:k] for k in range(60, sig.d))]))}
    return out


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def window_stats(sig, w, start, slip):
    r = bt.run(sig.ts, sig.opens, sig.closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    i = bt.start_index(sig.ts, start)
    # daily-mark drawdown
    eq = pd.Series(r["equity"], index=sig.ts[i:])
    deq = eq.groupby(eq.index.date).last().to_numpy()
    peak = np.maximum.accumulate(deq)
    s["dd_daily"] = float(-(deq / peak - 1.0).min())
    bench = bt.benchmark(sig.closes[i:, 1], sig.ts[i:], BARS)
    return s, r, bench


def rolling3y(sig, eq_strategy, eq_winner, start):
    """Quarterly-spaced 3-year windows from session-end equity."""
    # eq_strategy / eq_winner come from bt.run(..., start) and already begin at i0.
    i0 = bt.start_index(sig.ts, start)
    day = sig.dates[i0:]
    assert len(eq_strategy) == len(day) == len(eq_winner)

    def session_last(x):
        return pd.Series(np.asarray(x, float)).groupby(day).last().to_numpy()

    eq = session_last(eq_strategy)
    ew = session_last(eq_winner)
    tq = session_last(sig.closes[i0:, 1])
    dd = np.unique(day)
    n = len(eq)
    span = 756
    rows = []
    for s in range(0, n - span, 63):
        e = eq[s:s + span + 1]
        w = ew[s:s + span + 1]
        t = tq[s:s + span + 1]
        def cagr(x):
            return (x[-1] / x[0]) ** (252.0 / span) - 1.0
        def mdd(x):
            p = np.maximum.accumulate(x)
            return float(-(x / p - 1.0).min())
        rows.append({
            "start": str(dd[s]), "end": str(dd[s + span]),
            "cagr": cagr(e), "dd": mdd(e),
            "winner_cagr": cagr(w), "winner_dd": mdd(w),
            "tqqq_cagr": cagr(t), "tqqq_dd": mdd(t),
        })
    return rows


def summarize_rolling(rows):
    n = len(rows)
    return {
        "n_windows": n,
        "lower_dd_than_winner": int(sum(r["dd"] < r["winner_dd"] for r in rows)),
        "higher_cagr_than_winner": int(sum(r["cagr"] > r["winner_cagr"] for r in rows)),
        "beat_winner_both": int(sum(r["cagr"] > r["winner_cagr"] and r["dd"] < r["winner_dd"] for r in rows)),
        "lower_dd_than_tqqq": int(sum(r["dd"] < r["tqqq_dd"] for r in rows)),
        "higher_cagr_than_tqqq": int(sum(r["cagr"] > r["tqqq_cagr"] for r in rows)),
        "beat_tqqq_both": int(sum(r["cagr"] > r["tqqq_cagr"] and r["dd"] < r["tqqq_dd"] for r in rows)),
        "median_cagr": float(np.median([r["cagr"] for r in rows])),
        "median_dd": float(np.median([r["dd"] for r in rows])),
        "worst_dd": float(max(r["dd"] for r in rows)),
    }


def pack(s, bench):
    return {
        "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
        "max_drawdown_daily_marks": s["dd_daily"],
        "sharpe": s["sharpe"], "sortino": s["sortino"],
        "volatility": s["volatility"], "calmar": s["cagr"] / s["max_drawdown"],
        "fills": s["fills"], "turnover": s["turnover"],
        "exposure": s["exposure"], "ending_equity": s["ending_equity"],
        "benchmark_tqqq_bh": bench,
    }


def main():
    ts, opens, closes = load_panel()
    sig = Signals(ts, opens, closes)
    ones = np.ones(sig.d)
    vol70 = np.clip(0.70 / sig.vol(20)[:, 1], 0.0, 1.0)

    print(f"signals: {sig.d} sessions, risk-on {sig.risk_on.mean()*100:.1f}%, "
          f"stop events {sig.stop_events}", flush=True)

    out = {
        "agent": "risk-parity-hrp",
        "strategy": "RP-half: 165d QQQ regime, 100% TQQQ, 4% minute stop, "
                    "stopped sleeve 50% QQQ / 50% BIL",
        "signals": {"sessions": sig.d, "risk_on_frac": float(sig.risk_on.mean()),
                    "stop_events": int(sig.stop_events)},
        "windows": {}, "winner_1bp": {}, "voltarget_1bp": {},
        "cost_sensitivity": {}, "yearly": {}, "rolling3y_10y": {},
        "risk_models": {},
    }

    # --- final strategy, three cost levels ---
    w_half = sig.weights(ones, "half")
    for label, start in (("10y", START10), ("5y", START5)):
        out["cost_sensitivity"][label] = {}
        for slip in (1.0, 5.0, 10.0):
            s, r, b = window_stats(sig, w_half, start, slip)
            out["cost_sensitivity"][label][f"{slip:.0f}bp"] = pack(s, b)
            if slip == 1.0:
                out["windows"][label] = pack(s, b)
                tsl = sig.ts[bt.start_index(sig.ts, start):]
                eqv = r["equity"]
                ddv = eqv / np.maximum.accumulate(eqv) - 1.0
                j = int(np.argmin(ddv))
                p = int(np.argmax(eqv[:j + 1]))
                out["windows"][label]["dd_peak_ts"] = str(tsl[p])
                out["windows"][label]["dd_trough_ts"] = str(tsl[j])
                out["yearly"][label] = {str(k): v for k, v in bt.yearly(
                    tsl, eqv, sig.closes[bt.start_index(sig.ts, start):, 1]).items()}
                if label == "10y":
                    eq_half = r["equity"]
            print(f"RP-half {label} {slip:.0f}bp: CAGR {s['cagr']*100:.2f}% "
                  f"DD {s['max_drawdown']*100:.2f}% Sharpe {s['sharpe']:.2f} "
                  f"fills {s['fills']}", flush=True)

    # --- winner reference (1 bp) ---
    w_win = sig.weights(ones, "bil")
    eq_win = None
    for label, start in (("10y", START10), ("5y", START5)):
        s, r, b = window_stats(sig, w_win, start, 1.0)
        out["winner_1bp"][label] = pack(s, b)
        out["yearly"][label + "_winner"] = {str(k): v for k, v in bt.yearly(sig.ts[bt.start_index(sig.ts, start):], r["equity"], sig.closes[bt.start_index(sig.ts, start):, 1]).items()}
        if label == "10y":
            eq_win = r["equity"]
        print(f"winner {label} 1bp: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.2f}%", flush=True)

    # --- vol-target / inverse-vol brake (1 bp), clean lagged signals ---
    w_vt = sig.weights(vol70, "bil")
    for label, start in (("10y", START10), ("5y", START5)):
        s, r, b = window_stats(sig, w_vt, start, 1.0)
        out["voltarget_1bp"][label] = pack(s, b)
        print(f"voltarget70 {label} 1bp: CAGR {s['cagr']*100:.2f}% "
              f"DD {s['max_drawdown']*100:.2f}%", flush=True)

    # --- rolling 3y ---
    rows = rolling3y(sig, eq_half, eq_win, START10)
    out["rolling3y_10y"] = {"rows": rows, "summary": summarize_rolling(rows)}
    print("rolling 3y windows:", out["rolling3y_10y"]["summary"], flush=True)

    # --- risk model diagnostics (no backtest) ---
    out["risk_models"] = risk_model_weights(sig)
    print("risk models:", out["risk_models"], flush=True)

    # --- pass/fail ---
    def pf(key):
        a, b = out["windows"]["10y"], out["windows"]["5y"]
        wa, wb = WINNER["10y"], WINNER["5y"]
        return {
            "vs_tqqq_10y": bool(a["cagr"] > TQQQ_BH["10y"]["cagr"] and a["max_drawdown"] < TQQQ_BH["10y"]["max_drawdown"]),
            "vs_tqqq_5y": bool(b["cagr"] > TQQQ_BH["5y"]["cagr"] and b["max_drawdown"] < TQQQ_BH["5y"]["max_drawdown"]),
            "vs_winner_10y_cagr_within_2pp": bool(a["cagr"] > wa["cagr"] - 0.02),
            "vs_winner_10y_lower_dd": bool(a["max_drawdown"] < wa["max_drawdown"]),
            "vs_winner_5y_cagr_within_2pp": bool(b["cagr"] > wb["cagr"] - 0.02),
            "vs_winner_5y_lower_dd": bool(b["max_drawdown"] < wb["max_drawdown"]),
            "strict_dominance": bool(a["cagr"] > wa["cagr"] and a["max_drawdown"] < wa["max_drawdown"] and
                                     b["cagr"] > wb["cagr"] and b["max_drawdown"] < wb["max_drawdown"]),
        }
    out["pass_fail"] = pf("windows")
    out["not_run"] = ["10bp winner (README reference used instead)",
                      "HRP/inverse-vol unconstrained backtest (degenerate weights, diagnostic only)"]

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json", flush=True)


if __name__ == "__main__":
    main()
