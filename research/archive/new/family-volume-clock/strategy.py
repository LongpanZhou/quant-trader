"""Volume-clock family: midday volume-acceleration state, overnight TQQQ.

Development window only (2016-01-04 .. 2023-12-29).

Mechanism
---------
The market clock is replaced by a volume clock only for the *state* decision:
at 13:00 ET we compare the last 30 minutes of QQQ volume with the same
30-minute window on each of the prior 20 sessions.  The ratio is a
same-time-of-day volume-acceleration state.

    accel_k = sum(vol[12:31..13:00], session k)
              ------------------------------------
              median over k-20..k-1 of the same 30-minute sum

A volume burst (accel above the exit threshold) marks urgent, information-
driven repricing; the overnight tail risk is elevated.  A volume drought
(accel below the enter threshold) marks the absence of urgent flow; the
residual overnight drift in TQQQ persists.  A hysteresis band between the two
thresholds is the neutral deadband: the prior state is kept.

Rules
-----
* Decision clock: close of the 13:00 ET bar (offset 210 from 09:30).
* Volume window: 12:31-13:00 ET (30 one-minute bars).
* Normalisation: median of the same 30-minute window over the prior 20
  sessions (strictly before session k).  No full-sample statistics.
* State machine:
      state 0 -> 1 if accel < 0.75
      state 1 -> 0 if accel > 0.85
      otherwise state unchanged (deadband).
* If state == 1: buy TQQQ at the 13:01 open, hold through the 15:59 close,
  sell at the next session's 09:30 open.  One overnight per entry.
* If state == 0: cash (0%).  The BIL-flat variant is reported separately;
  under the shared simulator its second leg doubles fills and is much more
  cost-sensitive.
* Long only, weights >= 0, row sum <= 1, 2% band, next-open fills.

The sign of the volume-weighted price move is tested as a secondary signal:
VWAP deviation at 13:00 (close / volume-weighted average price - 1).  It has
standalone predictive content, but combining it with the acceleration gate
lowers CAGR; the acceleration state is the primary driver.  See report.md.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-volume-clock/strategy.py
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

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2

# Pre-registered centre (frozen before the confirmatory grid).
DEC_MIN = 210      # 13:00 ET bar; signal known at its close
WIN_MIN = 30       # 12:31-13:00 ET
LOOK = 20          # prior-20 same-window median
ENTER = 0.75       # enter the overnight long below this acceleration
EXIT = 0.85        # exit the state above this acceleration
FLAT = "cash"      # headline; "BIL" variant is reported separately

WINNERS = [
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
]
EXTRA_CURVES = ["overnight-drift-filter"]


# --------------------------------------------------------------------------- #
# data / signal
# --------------------------------------------------------------------------- #
def load_panel(start: str = DEV_START, end: str = DEV_END, warmup_days: int = 60):
    """Dev panel plus aligned QQQ share volume."""
    ts, o, c = bt.panel(SYMBOLS, start, end, "1min", warmup_days=warmup_days)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)
    return ts, o, c, vol


def qqq_volume(ts: pd.DatetimeIndex) -> np.ndarray:
    """QQQ share volume aligned to an arbitrary panel index (holdout-safe)."""
    ts = pd.DatetimeIndex(ts)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    return np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)


def volume_acceleration(ts, vol, dec_min: int = DEC_MIN, win: int = WIN_MIN,
                        look: int = LOOK) -> np.ndarray:
    """Same-time-of-day 30-minute volume ratio, strictly causal.

    `accel[k]` uses session k's window ending at `dec_min` and the same window
    on sessions k-look .. k-1.  Sessions with a missing/short window or a zero
    median are NaN.
    """
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    w0 = dec_min - win + 1
    acc = np.full(n, np.nan)
    if w0 < 0:
        return acc
    for k in range(look, n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if dec_min >= m - 1:
            continue
        fk = int(first[k])
        cur = float(np.sum(vol[fk + w0: fk + dec_min + 1]))
        hist = [
            float(np.sum(vol[int(first[kk]) + w0: int(first[kk]) + dec_min + 1]))
            for kk in range(k - look, k)
        ]
        med = float(np.median(hist))
        if med > 0:
            acc[k] = cur / med
    return acc


def state_mask(accel: np.ndarray, enter: float, exit_: float,
               hysteresis: bool = True) -> np.ndarray:
    """Overnight-long state from the acceleration series."""
    n = len(accel)
    mask = np.zeros(n, dtype=bool)
    state = 0
    for k in range(n):
        a = accel[k]
        if not np.isfinite(a):
            state = 0
            continue
        if not hysteresis:
            state = 1 if a < enter else 0
        elif state == 0 and a < enter:
            state = 1
        elif state == 1 and a > exit_:
            state = 0
        mask[k] = bool(state)
    return mask


def weights_from_mask(ts, mask: np.ndarray, dec_min: int = DEC_MIN,
                      flat: str = FLAT):
    """Build the (n, 3) matrix: overnight TQQQ on mask days, else flat."""
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    w = np.zeros((len(ts), 3))
    traded = 0
    for k in range(n - 1):
        if not mask[k]:
            continue
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if dec_min >= m - 1:
            continue
        fk, lk = int(first[k]), int(last[k])
        w[fk + dec_min, CT] = 1.0          # fill at 13:01 open
        w[fk + dec_min + 1: lk + 1, CT] = 1.0
        w[lk, CT] = 0.0                    # fill at next session's open
        traded += 1
    w[-1] = w[-2]
    if flat == "BIL":
        w[:, CB] = 1.0 - w[:, CT]
    return w, traded


def build_weights(ts, opens, closes, dec_min: int = DEC_MIN, enter: float = ENTER,
                  exit_: float = EXIT, win: int = WIN_MIN, look: int = LOOK,
                  flat: str = FLAT, accel: np.ndarray | None = None,
                  hysteresis: bool = True, return_diag: bool = False):
    """Required public API.  Returns an (n, 3) long-only weight matrix.

    The function is generic over the panel range: if the lead calls it on the
    full 2016-2026 panel it uses only information available at each 13:00
    decision (prior 20 sessions), so it is holdout-safe.
    """
    ts = pd.DatetimeIndex(ts)
    opens = np.asarray(opens, dtype=float)
    closes = np.asarray(closes, dtype=float)
    if accel is None:
        vol = qqq_volume(ts)
        accel = volume_acceleration(ts, vol, dec_min, win, look)
    mask = state_mask(accel, enter, exit_, hysteresis=hysteresis)
    w, traded = weights_from_mask(ts, mask, dec_min, flat)
    if return_diag:
        return w, {"accel": accel, "mask": mask, "traded": traded}
    return w


def build_holdout_weights(ts, opens, closes):
    """Optional adapter: identical frozen logic on the full panel."""
    return build_weights(ts, opens, closes)


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def pack(s: dict) -> dict:
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover", "fills", "ending_equity", "years")
    return {k: (int(s[k]) if k == "fills" else float(s[k])) for k in keys}


def run_w(ts, o, c, w, slip: float = 1.0, fill_log: bool = False):
    r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip,
               fill_log=fill_log)
    return r, bt.stats(r, BPY)


def daily_returns(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=pd.to_datetime(res["ts"]))
    d = s.groupby(s.index.normalize()).last()
    d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
    return d.pct_change().dropna()


def daily_curve(res: dict) -> pd.Series:
    s = pd.Series(res["equity"], index=pd.to_datetime(res["ts"]))
    d = s.groupby(s.index.normalize()).last()
    d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
    return d


def daily_stats(res: dict) -> dict:
    d = daily_curve(res)
    eq = d.to_numpy()
    years = (d.index[-1] - d.index[0]).days / 365.25
    rets = np.diff(eq) / eq[:-1]
    peak = np.maximum.accumulate(eq)
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1),
        "max_drawdown": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std(ddof=0) * np.sqrt(252)),
        "volatility": float(rets.std(ddof=0) * np.sqrt(252)),
        "days": int(len(d)),
    }


def subperiod(ts, equity, lo: str, hi: str) -> dict | None:
    m = ((ts >= pd.Timestamp(lo, tz="America/New_York"))
         & (ts < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    x, tt = equity[m], ts[m]
    if len(x) < 2:
        return None
    years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(x)
    return {"cagr": float((x[-1] / x[0]) ** (1 / years) - 1),
            "max_drawdown": float(-(x / peak - 1).min())}


def dd_window(ts, equity) -> dict:
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1]))
    return {"peak": str(ts[i])[:10], "trough": str(ts[j])[:10],
            "dd": float(-dd[j])}


def alpha_beta_vs_tqqq(ts, c, res) -> dict:
    sr = daily_returns(res)
    tq = pd.Series(c[:, CT], index=pd.to_datetime(ts))
    tr = tq.groupby(tq.index.normalize()).last().pct_change().dropna()
    tr.index = pd.DatetimeIndex(tr.index).tz_localize(None).normalize()
    j = sr.index.intersection(tr.index)
    sr, tr = sr.loc[j], tr.loc[j]
    beta = float(np.cov(sr, tr, ddof=1)[0, 1] / np.var(tr, ddof=1))
    alpha = float(sr.mean() - beta * tr.mean())
    resid = sr.to_numpy() - alpha - beta * tr.to_numpy()
    se = float(np.std(resid, ddof=2) / np.sqrt(len(sr)))
    return {"beta": beta, "alpha_bp_day": alpha * 1e4,
            "alpha_ann": float((1 + alpha) ** 252 - 1),
            "t_alpha": float(alpha / se) if se > 0 else 0.0,
            "corr": float(sr.corr(tr)), "n": int(len(sr))}


def load_curve(slug: str) -> pd.Series | None:
    p = ROOT / "research" / "new" / "curves" / f"{slug}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    s = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s.pct_change().dropna()


def corr_table(res) -> dict:
    dr = daily_returns(res)
    out = {}
    for slug in WINNERS + EXTRA_CURVES:
        wr = load_curve(slug)
        if wr is None:
            continue
        j = dr.index.intersection(wr.index)
        out[slug] = {"corr": float(dr.loc[j].corr(wr.loc[j])), "n": int(len(j))}
    return out


def signal_diagnostics(accel, mask, ts, o, c) -> dict:
    """Overnight return split by acceleration state, plus vol controls."""
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    on = np.full(n, np.nan)
    rv = np.full(n, np.nan)
    rop = np.full(n, np.nan)
    vwd = np.full(n, np.nan)
    for k in range(LOOK, n - 1):
        if not np.isfinite(accel[k]):
            continue
        fk, lk = int(first[k]), int(last[k])
        m = min(lk - fk + 1, 390)
        if DEC_MIN >= m - 1:
            continue
        cl = c[fk:fk + m, 0]
        v = None  # volume not needed for these diagnostics except VWAP
        # VWAP (QQQ) over the session through the decision
        # reconstruct from closes only is impossible; pass volume separately
        fn = int(first[k + 1])
        on[k] = o[fn, 1] / c[lk, 1] - 1.0
        rr = np.diff(np.log(cl[:DEC_MIN + 1]))
        rv[k] = float(np.std(rr, ddof=0) * np.sqrt(390))
        rop[k] = cl[DEC_MIN] / o[fk, 0] - 1.0
    return {"overnight": on, "rv": rv, "r_open": rop}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c, vol = load_panel()
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    print(f"panel {len(ts):,} bars, {n} sessions, {ts[0].date()} .. {ts[-1].date()}")

    accel = volume_acceleration(ts, vol, DEC_MIN, WIN_MIN, LOOK)
    w, diag = build_weights(ts, o, c, accel=accel, return_diag=True)
    print(f"entries {diag['traded']}  accel finite {np.isfinite(accel).sum()}  "
          f"TQQQ bars {np.mean(w[:, CT] > 0)*100:.1f}%")

    out = {
        "strategy": "volume-clock-1300-acceleration-overnight",
        "directory": "research/new/family-volume-clock",
        "window": {"start": DEV_START, "end": DEV_END, "marks": "1min",
                   "fills": "next-minute open, 2% band",
                   "idle": "cash (0%); BIL variant reported separately"},
        "rules": {
            "decision_clock": "close of the 13:00 ET bar (offset 210 from 09:30)",
            "volume_window": "12:31-13:00 ET (30 one-minute QQQ bars)",
            "normalisation": "median of the same 30-minute window over the prior 20 sessions",
            "state": "enter overnight long if accel < 0.75; exit if accel > 0.85; "
                     "otherwise hold prior state (deadband)",
            "position": "100% TQQQ at the 13:01 open, hold through 15:59, "
                        "sell at the next 09:30 open; cash otherwise",
            "long_only": True,
            "no": "daily trend SMA, volatility targeting, drawdown/capitulation event, "
                  "calendar window, opening range, closing-auction/rebalance flow, ML classifier",
        },
        "centre": {"dec_min": DEC_MIN, "win_min": WIN_MIN, "look": LOOK,
                   "enter": ENTER, "exit": EXIT, "flat": FLAT},
        "dev": {},
    }

    results = {}
    for slip in (0.0, 1.0, 5.0, 10.0):
        res, s = run_w(ts, o, c, w, slip=slip)
        results[slip] = (res, s)
        if slip == 0.0:
            out["gross_0bp"] = pack(s)
        else:
            out["dev"][f"{int(slip)}bp"] = pack(s)
        print(f"centre {slip:4.1f}bp  CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  Sortino {s['sortino']:4.2f}  vol {s['volatility']*100:5.2f}%  "
              f"expo {s['exposure']*100:5.1f}%  fills {s['fills']:,}  turnover {s['turnover']:.0f}  "
              f"end ${s['ending_equity']:,.0f}")

    res1, s1 = results[1.0]
    i0 = bt.start_index(ts, DEV_START)
    out["benchmarks"] = {
        "tqqq": {k: float(v) for k, v in bt.benchmark(c[i0:, CT], ts[i0:], BPY).items()},
        "qqq": {k: float(v) for k, v in bt.benchmark(c[i0:, CQ], ts[i0:], BPY).items()},
        "bil": {k: float(v) for k, v in bt.benchmark(c[i0:, CB], ts[i0:], BPY).items()},
    }
    out["bar"] = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82,
                  "note": "TQQQ dev bar from the task brief (daily-close marks)"}
    out["bar_check"] = {
        "cagr_above": bool(s1["cagr"] > 0.3672),
        "dd_below": bool(s1["max_drawdown"] < 0.8229),
        "sharpe_above": bool(s1["sharpe"] > 0.82),
        "all_three": bool(s1["cagr"] > 0.3672 and s1["max_drawdown"] < 0.8229
                          and s1["sharpe"] > 0.82),
    }

    # BIL-flat variant
    out["bil_flat_variant"] = {}
    for slip in (1.0, 5.0, 10.0):
        wb, _ = build_weights(ts, o, c, accel=accel, flat="BIL", return_diag=True)
        _, sb = run_w(ts, o, c, wb, slip=slip)
        out["bil_flat_variant"][f"{int(slip)}bp"] = pack(sb)
        print(f"BIL flat {slip:4.1f}bp  CAGR {sb['cagr']*100:6.2f}%  DD {sb['max_drawdown']*100:5.2f}%  "
              f"Sharpe {sb['sharpe']:4.2f}  fills {sb['fills']:,}  turnover {sb['turnover']:.0f}")

    # daily-close metrics and subperiods
    out["daily_close"] = {k: v for k, v in daily_stats(res1).items()}
    out["subperiods"] = {
        "2016_2019": subperiod(res1["ts"], res1["equity"], "2016-01-04", "2019-12-31"),
        "2020_2021": subperiod(res1["ts"], res1["equity"], "2020-01-02", "2021-12-31"),
        "2022_2023": subperiod(res1["ts"], res1["equity"], "2022-01-03", "2023-12-29"),
    }
    out["yearly"] = {
        str(k): {"strategy": float(v["strategy"]), "benchmark": float(v["benchmark"])}
        for k, v in bt.yearly(res1["ts"], res1["equity"], c[i0:, CT]).items()
    }
    out["dd_window"] = dd_window(res1["ts"], res1["equity"])
    out["alpha_beta_tqqq"] = alpha_beta_vs_tqqq(ts, c, res1)
    out["corr_winners"] = corr_table(res1)

    # holding period / entries from the fill log
    rlog, _ = run_w(ts, o, c, w, slip=1.0, fill_log=True)
    log = rlog["fills_log"]
    buys = [x for x in log if x["side"] == "buy"]
    sells = [x for x in log if x["side"] == "sell"]
    holds = []
    bi = 0
    for s in sells:
        if bi < len(buys) and buys[bi]["ts"] <= s["ts"]:
            holds.append((s["ts"] - buys[bi]["ts"]).total_seconds() / 3600.0)
            bi += 1
    out["activity"] = {
        "fills": int(s1["fills"]), "buys": len(buys), "sells": len(sells),
        "entries": len(buys),
        "avg_hold_hours": float(np.mean(holds)) if holds else 0.0,
        "median_hold_hours": float(np.median(holds)) if holds else 0.0,
        "tqqq_bar_exposure": float(np.mean(w[:, CT] > 0)),
        "nights_per_year": float(len(buys) / s1["years"]),
        "turnover_1bp": float(s1["turnover"]),
    }
    print(f"activity: {len(buys)} entries, avg hold {out['activity']['avg_hold_hours']:.1f}h, "
          f"median {out['activity']['median_hold_hours']:.1f}h")

    # signal attribution: low vs high acceleration, vol controls
    sd = signal_diagnostics(accel, diag["mask"], ts, o, c)
    on = sd["overnight"]; rv = sd["rv"]; rop = sd["r_open"]
    valid = np.isfinite(on) & np.isfinite(accel) & np.isfinite(rv) & np.isfinite(rop)
    lo = valid & (accel < ENTER)
    hi = valid & (accel > EXIT)
    mid = valid & (accel >= ENTER) & (accel <= EXIT)

    def bucket(m):
        x = on[m]
        return {"n": int(len(x)), "mean_bp": float(x.mean() * 1e4),
                "median_bp": float(np.median(x) * 1e4),
                "t": float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 else 0.0,
                "win": float(np.mean(x > 0))}

    out["signal_attribution"] = {
        "low_accel": bucket(lo), "deadband": bucket(mid), "high_accel": bucket(hi),
        "low_minus_high_bp": float((on[lo].mean() - on[hi].mean()) * 1e4),
    }

    # OLS: overnight ~ 1 + low_accel + log(rv) + |r_open|
    y = on[valid]
    X = np.column_stack([np.ones(valid.sum()), (accel[valid] < ENTER).astype(float),
                         np.log(rv[valid]), np.abs(rop[valid])])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = float(resid @ resid / (len(y) - X.shape[1]))
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    out["signal_attribution"]["ols"] = {
        "dep_var": "overnight TQQQ close-to-next-open",
        "terms": ["const", "accel<0.75", "log_realised_vol", "abs_r_open"],
        "coef_bp": [float(b * 1e4) for b in beta],
        "t": [float(b / s) for b, s in zip(beta, se)],
        "n": int(len(y)),
    }
    print(f"low accel {out['signal_attribution']['low_accel']['mean_bp']:.1f}bp "
          f"(n={out['signal_attribution']['low_accel']['n']}) vs high "
          f"{out['signal_attribution']['high_accel']['mean_bp']:.1f}bp "
          f"(n={out['signal_attribution']['high_accel']['n']})")
    print(f"OLS accel<0.75 t={out['signal_attribution']['ols']['t'][1]:.2f}")

    # ---------------- pre-registered 8-cell plateau -------------------------
    grid_specs = [
        ("12:45 e0.75 x0.85", 195, 0.75, 0.85),
        ("13:00 e0.70 x0.80", 210, 0.70, 0.80),
        ("13:00 e0.75 x0.85 (centre)", 210, 0.75, 0.85),
        ("13:00 e0.75 x0.90", 210, 0.75, 0.90),
        ("13:00 e0.80 x0.90", 210, 0.80, 0.90),
        ("13:00 e0.80 x1.00", 210, 0.80, 1.00),
        ("13:15 e0.75 x0.85", 225, 0.75, 0.85),
        ("13:30 e0.75 x0.85", 240, 0.75, 0.85),
    ]
    acc_cache = {d: volume_acceleration(ts, vol, d, WIN_MIN, LOOK)
                 for d in sorted({x[1] for x in grid_specs})}
    grid = []
    for label, dec, ent, ext in grid_specs:
        wg, dg = build_weights(ts, o, c, dec_min=dec, enter=ent, exit_=ext,
                               accel=acc_cache[dec], return_diag=True)
        row = {"cell": label, "dec_min": dec, "enter": ent, "exit": ext,
               "entries": int(dg["traded"])}
        for slip in (1.0, 5.0):
            _, sg = run_w(ts, o, c, wg, slip=slip)
            row[f"{int(slip)}bp"] = pack(sg)
        grid.append(row)
        g1 = row["1bp"]; g5 = row["5bp"]
        print(f"grid {label:30s} 1bp {g1['cagr']*100:6.2f}%/{g1['max_drawdown']*100:5.1f}% "
              f"Sh {g1['sharpe']:4.2f}  5bp {g5['cagr']*100:6.2f}%  entries {row['entries']}")
    out["grid"] = grid

    # ---------------- broader neighbours ------------------------------------
    neigh = []
    for dec in (180, 195, 210, 225, 240):
        for ent, ext in ((0.70, 0.80), (0.75, 0.85), (0.80, 0.90), (0.75, 0.90)):
            a = acc_cache.get(dec)
            if a is None:
                a = volume_acceleration(ts, vol, dec, WIN_MIN, LOOK)
                acc_cache[dec] = a
            wn, dn = build_weights(ts, o, c, dec_min=dec, enter=ent, exit_=ext,
                                   accel=a, return_diag=True)
            _, sn = run_w(ts, o, c, wn, slip=1.0)
            neigh.append({"dec_min": dec, "enter": ent, "exit": ext,
                          "entries": int(dn["traded"]), **pack(sn)})
    out["neighbours"] = neigh

    # ---------------- controls ----------------------------------------------
    controls = {}
    # 1. all sessions, overnight, no signal
    wall = np.zeros((len(ts), 3))
    for k in range(n - 1):
        fk, lk = int(first[k]), int(last[k])
        wall[fk + DEC_MIN, CT] = 1.0
        wall[fk + DEC_MIN + 1: lk + 1, CT] = 1.0
        wall[lk, CT] = 0.0
    wall[-1] = wall[-2]
    _, s = run_w(ts, o, c, wall); controls["all_sessions_overnight"] = pack(s)
    # 2. static threshold, no hysteresis
    wst, _ = build_weights(ts, o, c, accel=accel, hysteresis=False,
                           return_diag=True)
    _, s = run_w(ts, o, c, wst); controls["static_accel_lt_0.75"] = pack(s)
    # 3. high-acceleration state only (the bad side)
    mask_hi = np.isfinite(accel) & (accel > EXIT)
    whi, _ = weights_from_mask(ts, mask_hi, DEC_MIN)
    _, s = run_w(ts, o, c, whi); controls["high_accel_only"] = pack(s)
    # 4. always long TQQQ
    wb = np.zeros((len(ts), 3)); wb[:, CT] = 1.0
    _, s = run_w(ts, o, c, wb); controls["buy_hold_tqqq"] = pack(s)
    # 5. VWAP sign only (no acceleration gate)
    vwd = np.full(n, np.nan)
    for k in range(LOOK, n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if DEC_MIN >= m - 1:
            continue
        fk = int(first[k]); cl = c[fk:fk + m, 0]; v = vol[fk:fk + m]
        vw = np.sum(v[:DEC_MIN + 1] * cl[:DEC_MIN + 1]) / max(v[:DEC_MIN + 1].sum(), 1)
        vwd[k] = cl[DEC_MIN] / vw - 1.0
    m_vwd = np.isfinite(vwd) & (vwd > -0.001)
    wv, _ = weights_from_mask(ts, m_vwd, DEC_MIN)
    _, s = run_w(ts, o, c, wv); controls["vwap_dev_gt_-10bp_only"] = pack(s)
    # 6. 13:00 r_open > -20bp only (price-only control)
    rop = np.full(n, np.nan)
    for k in range(LOOK, n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if DEC_MIN >= m - 1:
            continue
        fk = int(first[k])
        rop[k] = c[fk + DEC_MIN, 0] / o[fk, 0] - 1.0
    m_rop = np.isfinite(rop) & (rop > -0.002)
    wr, _ = weights_from_mask(ts, m_rop, DEC_MIN)
    _, s = run_w(ts, o, c, wr); controls["r_open_gt_-20bp_only"] = pack(s)
    # 7. acceleration + VWAP sign
    m_both = np.isfinite(accel) & np.isfinite(vwd) & (accel < ENTER) & (vwd > -0.001)
    wbo, _ = weights_from_mask(ts, m_both, DEC_MIN)
    _, s = run_w(ts, o, c, wbo); controls["accel_and_vwap_sign"] = pack(s)
    out["controls"] = controls
    for k, v in controls.items():
        print(f"control {k:34s} CAGR {v['cagr']*100:6.2f}% DD {v['max_drawdown']*100:5.1f}% "
              f"Sh {v['sharpe']:4.2f} fills {v['fills']:,}")

    # ---------------- causality / truncation --------------------------------
    j = bt.start_index(ts, "2022-01-03")
    vol_tr = vol[:j]
    a_tr = volume_acceleration(ts[:j], vol_tr, DEC_MIN, WIN_MIN, LOOK)
    w_tr = build_weights(ts[:j], o[:j], c[:j], accel=a_tr)
    out["causality_day_boundary"] = {
        "truncation_date": "2022-01-03",
        "prior_weights_unchanged": bool(np.allclose(w_tr[:j], w[:j])),
        "max_abs_diff": float(np.max(np.abs(w_tr[:j] - w[:j]))),
    }
    j2 = bt.start_index(ts, "2020-03-12 11:07")
    n_cmp = bt.start_index(ts, "2020-03-12")
    a_tr2 = volume_acceleration(ts[:j2], vol[:j2], DEC_MIN, WIN_MIN, LOOK)
    w_tr2 = build_weights(ts[:j2], o[:j2], c[:j2], accel=a_tr2)
    out["causality_intraday_cut"] = {
        "truncation_date": "2020-03-12 11:07",
        "prior_weights_unchanged": bool(np.allclose(w_tr2[:n_cmp], w[:n_cmp])),
        "max_abs_diff": float(np.max(np.abs(w_tr2[:n_cmp] - w[:n_cmp]))),
    }
    print("causality", out["causality_day_boundary"], out["causality_intraday_cut"])

    # ---------------- pass / kill summary -----------------------------------
    g = out["grid"]
    pos_grid = sum(1 for r in g if r["1bp"]["cagr"] > 0)
    out["kill_checks"] = {
        "activity_floor_100_fills": bool(s1["fills"] >= 100),
        "entries_ge_30": bool(len(buys) >= 30),
        "cagr_above_tqqq_bar": bool(s1["cagr"] > 0.3672),
        "sharpe_above_tqqq_bar": bool(s1["sharpe"] > 0.82),
        "dd_below_tqqq_bar": bool(s1["max_drawdown"] < 0.8229),
        "ten_bp_above_bil": bool(out["dev"]["10bp"]["cagr"] > out["benchmarks"]["bil"]["cagr"]),
        "all_subperiods_positive": bool(all(
            v is not None and v["cagr"] > 0 for v in out["subperiods"].values())),
        "grid_positive_cells": int(pos_grid),
        "grid_positive_at_least_6_of_8": bool(pos_grid >= 6),
        "volume_attribution_t_ge_2": bool(out["signal_attribution"]["ols"]["t"][1] >= 2.0),
    }
    out["pass"] = {
        "headline_clears_bar_at_1bp": out["bar_check"]["all_three"],
        "risk_adjusted_improvement": bool(
            s1["max_drawdown"] < 0.8229 and s1["sharpe"] > 0.82),
        "cagr_edge_over_bar_pp": float((s1["cagr"] - 0.3672) * 100),
        "note": "CAGR edge at 1bp is small; the durable improvement is drawdown "
                "and Sharpe. At 5bp the CAGR is below the TQQQ bar.",
    }

    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float),
                                      encoding="utf-8")
    print("wrote", HERE / "result.json")


if __name__ == "__main__":
    main()
