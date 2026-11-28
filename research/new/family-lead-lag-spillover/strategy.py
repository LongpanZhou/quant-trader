"""Cross-market lead-lag spillover: SPY's intraday move -> QQQ's next session.

DEVELOPMENT WINDOW ONLY (2016-01-04 .. 2023-12-29).  The 2024-2026 holdout is
never loaded for evaluation; the SPY daily file is truncated at 2023-12-29
immediately after reading.

Mechanism
---------
SPY and QQQ share a common market factor.  A broad cash-session selloff in SPY
is partly liquidity/positioning flow.  If QQQ has not already priced the same
flow (SPY underperforms its rolling beta to QQQ), the next QQQ session tends to
bounce.  The signal is SPY's *intraday* return, open-to-close, so the overnight
gap (which is not tradable with next-open fills) is excluded.

Rules (all known at the 16:00 close of session d; fills at the next open)
--------------------------------------------------------------------------
    s_id[d] = SPY adjclose[d] / (SPY open[d] * adjclose[d]/close[d]) - 1
    z[d]    = s_id[d] / stdev(s_id[d-20..d-1], ddof=1)
    event   = z[d] <= -0.50
    entry   = TQQQ at the open of session d+1
    exit    = TQQQ at the 15:59 open of session d+1 (one-session clock)
    idle    = BIL

A run of consecutive events keeps the position open; `hold=2` extends the exit
to the close of d+2.  The primary uses hold=1, so chaining is irrelevant.

No 100-250 day moving-average gate, no volatility targeting, no drawdown or
capitulation state, no calendar window, no opening-range or close-flow signal,
no ML, and no QQQ/SPY ratio-momentum gate.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-lead-lag-spillover/strategy.py
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
SYMBOLS = ("QQQ", "TQQQ", "BIL")
CQ, CT, CB = 0, 1, 2
BARS_PER_YEAR = 252 * 390
BAND = 0.02

# Pre-registered primary, fixed before the grid was run.
PARAMS = dict(
    signal="spy_intraday",   # spy_intraday | spy_cc | qqq_intraday | residual
    vol_window=20,
    thr=0.50,
    hold=1,
    chain=True,
    confirm=None,            # None | "resid_neg"
    exit_mode="close",       # close = 15:59 open; next_open = next 09:30
    idle="bil",              # bil | cash
)

BARS_PER_YEAR_DAILY = 252.0
START_EQUITY = bt.START_EQUITY


# --------------------------------------------------------------------------- #
# daily features
# --------------------------------------------------------------------------- #
def _daily(symbol: str, path: Path) -> pd.DataFrame:
    d = pd.read_parquet(path)
    d["date"] = pd.to_datetime(d["date"])
    d = d[d["date"] <= pd.Timestamp(DEV_END)].copy()
    d["fac"] = d["adjclose"] / d["close"]
    d["o_adj"] = d["open"] * d["fac"]
    d["c_adj"] = d["adjclose"]
    return d[["date", "o_adj", "c_adj"]]


def _rolling_beta_resid(y: np.ndarray, x: np.ndarray, window: int = 60):
    n = len(y)
    res = np.full(n, np.nan)
    beta = np.full(n, np.nan)
    for i in range(window + 2, n):
        yy, xx = y[i - window:i], x[i - window:i]
        if not (np.isfinite(yy).all() and np.isfinite(xx).all()):
            continue
        X = np.column_stack([np.ones(window), xx])
        b = np.linalg.lstsq(X, yy, rcond=None)[0]
        beta[i] = b[1]
        res[i] = y[i] - (b[0] + b[1] * x[i])
    return res, beta


def _z(v: pd.Series, window: int) -> np.ndarray:
    return (v / v.rolling(window).std(ddof=1).shift(1)).to_numpy()


def daily_features(ts) -> dict:
    """One row per QQQ session.  All rolling inputs use data through d-1."""
    dates, first, last = bt.day_bounds(ts)
    sdates = pd.to_datetime(dates[first])
    nd = len(first)

    spy = _daily("SPY", ROOT / "data/round3/yahoo/SPY-1d-yahoo.parquet")
    qqq = _daily("QQQ", ROOT / "data/intraday-hf/QQQ-1d-yahoo.parquet")
    spy = spy.set_index("date").reindex(sdates)
    qqq = qqq.set_index("date").reindex(sdates)
    if spy["c_adj"].isna().any() or qqq["c_adj"].isna().any():
        missing = sdates[spy["c_adj"].isna() | qqq["c_adj"].isna()]
        raise RuntimeError(f"daily alignment missing {len(missing)} sessions: {missing[:5]}")

    s_id = spy["c_adj"] / spy["o_adj"] - 1.0
    s_cc = spy["c_adj"].pct_change()
    q_id = qqq["c_adj"] / qqq["o_adj"] - 1.0
    q_cc = qqq["c_adj"].pct_change()

    z_id = _z(s_id, 20)
    z_cc = _z(s_cc, 20)
    zq_id = _z(q_id, 20)

    res_id, beta_id = _rolling_beta_resid(s_id.to_numpy(), q_id.to_numpy(), 60)
    rez = pd.Series(res_id)
    rz_id = (rez / rez.rolling(60).std(ddof=1).shift(1)).to_numpy()

    feats = dict(
        dates=sdates, first=first, last=last, nd=nd,
        s_id=s_id.to_numpy(), s_cc=s_cc.to_numpy(),
        q_id=q_id.to_numpy(), q_cc=q_cc.to_numpy(),
        z_id=z_id, z_cc=z_cc, zq_id=zq_id,
        res_id=res_id, beta_id=beta_id, rz_id=rz_id,
    )
    feats["z_id_extra"] = _z(s_id, 60)
    return feats


# --------------------------------------------------------------------------- #
# signal -> held sessions -> weights
# --------------------------------------------------------------------------- #
def event_mask(f: dict, p: dict) -> np.ndarray:
    name = p["signal"]
    if name == "spy_intraday":
        vw = int(p.get("vol_window", 20))
        sig = f["z_id"] if vw == 20 else _z(pd.Series(f["s_id"]), vw)
    elif name == "spy_cc":
        sig = f["z_cc"]
    elif name == "qqq_intraday":
        sig = f["zq_id"]
    elif name == "residual":
        sig = f["rz_id"]
    elif name == "spy_intraday_stale":
        z = f["z_id"].copy()
        sig = np.r_[np.nan, z[:-1]]
    else:
        raise ValueError(name)
    m = np.isfinite(sig) & (sig < -float(p["thr"]))
    if p.get("confirm") == "resid_neg":
        m &= np.isfinite(f["res_id"]) & (f["res_id"] < 0)
    return m


def held_from_mask(mask: np.ndarray, hold: int, nd: int, chain: bool = True):
    intervals: list[tuple[int, int]] = []
    end = -1
    for i in range(nd):
        if not mask[i]:
            continue
        if chain and i <= end:
            a, _ = intervals[-1]
            end = max(end, i + hold)
            intervals[-1] = (a, end)
        elif i > end:
            end = i + hold
            intervals.append((i + 1, end))
    held = np.zeros(nd, dtype=bool)
    for a, b in intervals:
        held[a:min(b + 1, nd)] = True
    return held, intervals


def weights_from_held(ts, f: dict, held: np.ndarray, exit_mode: str = "close",
                      idle: str = "bil"):
    n = len(ts)
    nd, first, last = f["nd"], f["first"], f["last"]
    w = np.zeros((n, 3))
    if idle == "bil":
        w[:, CB] = 1.0
    elif idle != "cash":
        raise ValueError(idle)
    for s in range(nd):
        if not held[s]:
            continue
        ent = first[s] - 1 if s > 0 else first[s]
        nxt_held = s + 1 < nd and held[s + 1]
        if exit_mode == "close":
            stop = last[s] - 1          # bars ent .. last-1
            w[ent:stop, CT] = 1.0
            if idle == "bil":
                w[ent:stop, CB] = 0.0
            if nxt_held:
                # stay in TQQQ across the overnight instead of paying a
                # sell/buy round trip at 15:59 and the next 09:30
                w[last[s] - 1, CT] = 1.0
                if idle == "bil":
                    w[last[s] - 1, CB] = 0.0
            else:
                w[last[s] - 1, CT] = 0.0
                if idle == "bil":
                    w[last[s] - 1, CB] = 1.0
        elif exit_mode == "next_open":
            stop = last[s] + 1          # hold through 15:59, sell at next 09:30
            w[ent:stop, CT] = 1.0
            if idle == "bil":
                w[ent:stop, CB] = 0.0
            if not nxt_held:
                w[last[s], CT] = 0.0
                if idle == "bil":
                    w[last[s], CB] = 1.0
        else:
            raise ValueError(exit_mode)
    return w


def build_weights(ts, opens, closes, features: dict | None = None, **overrides):
    """Required entry point: (n,3) long-only weights, rows sum to <= 1.

    A target written on bar i is filled at bar i+1's open by `bt`.
    """
    w, _ = _build(ts, opens, closes, features, **overrides)
    return w


def _build(ts, opens, closes, features: dict | None = None, **overrides):
    p = dict(PARAMS)
    p.update({k: v for k, v in overrides.items() if v is not None})
    f = features if features is not None else daily_features(ts)
    mask = event_mask(f, p)
    held, intervals = held_from_mask(mask, int(p["hold"]), f["nd"], bool(p["chain"]))
    w = weights_from_held(ts, f, held, p["exit_mode"], p.get("idle", "bil"))
    return w, dict(mask=mask, held=held, intervals=intervals, params=p)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def daily_equity(result: dict) -> pd.Series:
    s = bt.daily_last(result["equity"], result["ts"])
    return s.dropna()


def daily_stats(daily: pd.Series) -> dict:
    eq = daily.to_numpy()
    ret = np.diff(eq) / eq[:-1]
    years = len(ret) / BARS_PER_YEAR_DAILY
    peak = np.maximum.accumulate(eq)
    vol = ret.std(ddof=0)
    down = np.minimum(ret, 0.0)
    dstd = np.sqrt(np.mean(down ** 2))
    return dict(
        cagr=float((eq[-1] / eq[0]) ** (1 / years) - 1),
        max_drawdown=float(-(eq / peak - 1).min()),
        sharpe=float(ret.mean() / vol * np.sqrt(BARS_PER_YEAR_DAILY)) if vol > 0 else 0.0,
        sortino=float(ret.mean() / dstd * np.sqrt(BARS_PER_YEAR_DAILY)) if dstd > 0 else 0.0,
        volatility=float(vol * np.sqrt(BARS_PER_YEAR_DAILY)),
        years=float(years),
        ending_equity=float(eq[-1]),
    )


def slice_daily(daily: pd.Series, start: str, end: str) -> pd.Series:
    return daily[(daily.index >= pd.Timestamp(start)) & (daily.index <= pd.Timestamp(end))]


def summarize(run: dict, w: np.ndarray, meta: dict) -> dict:
    s = bt.stats(run, BARS_PER_YEAR)
    daily = daily_equity(run)
    ds = daily_stats(daily)
    s["daily_sharpe"] = ds["sharpe"]
    s["daily_sortino"] = ds["sortino"]
    s["daily_volatility"] = ds["volatility"]
    i0 = bt.start_index(run["ts"], DEV_START)
    tq = float(np.mean(w[i0:, CT]))
    s["tqqq_exposure"] = tq
    s["bil_exposure"] = float(np.mean(w[i0:, CB]))
    s["entries"] = int(len(meta["intervals"]))
    s["held_sessions"] = int(meta["held"].sum())
    s["avg_hold_sessions"] = (float(meta["held"].sum() / len(meta["intervals"]))
                              if meta["intervals"] else 0.0)
    s["open_at_end"] = bool(meta["intervals"]
                            and meta["intervals"][-1][1] >= len(meta["held"]) - 1)
    s["exits"] = int(s["entries"] - int(s["open_at_end"]))
    s["signal_days"] = int(meta["mask"].sum())
    return s


def run_case(ts, o, c, f, bps=1.0, **overrides):
    w, meta = _build(ts, o, c, features=f, **overrides)
    run = bt.run(ts, o, c, w, start=DEV_START, band=BAND, slippage_bps=bps)
    return run, w, meta


# --------------------------------------------------------------------------- #
# benchmarks / placebo / correlation
# --------------------------------------------------------------------------- #
def benchmark_weights(ts, col: int) -> np.ndarray:
    w = np.zeros((len(ts), 3))
    w[:, col] = 1.0
    return w


def shifted_features(f: dict, k: int) -> dict:
    out = dict(f)
    z = np.nan_to_num(f["z_id"], nan=0.0)
    out["z_id"] = np.roll(z, k)
    return out


def load_curve(name: str) -> pd.Series:
    d = json.load(open(ROOT / "research/new/curves" / f"{name}.json"))
    dates = pd.to_datetime(d["dates"])
    vals = np.asarray(d["values"], float)
    keep = dates <= pd.Timestamp(DEV_END)          # hard truncation: dev only
    dates, vals = dates[keep], vals[keep]
    return pd.Series(np.diff(vals) / vals[:-1], index=dates[1:])


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


def correlations(daily: pd.Series) -> dict:
    ret = daily.pct_change().dropna()
    out = {}
    for name in WINNERS:
        try:
            c = load_curve(name)
        except Exception as exc:  # pragma: no cover
            out[name] = {"error": str(exc)}
            continue
        j = ret.index.intersection(c.index)
        if len(j) < 100:
            out[name] = {"error": f"only {len(j)} overlapping days"}
            continue
        out[name] = {"pearson": float(ret.loc[j].corr(c.loc[j])), "n": int(len(j))}
    return out


def random_event_placebo(f, p, n_draw=1000, seed=7, bps=2.0):
    """Cheap daily-return placebo: same number of held sessions, random dates."""
    rng = np.random.default_rng(seed)
    tq = f["tq_ses"]
    nd = f["nd"]
    mask = event_mask(f, p)
    held, _ = held_from_mask(mask, int(p["hold"]), nd, bool(p["chain"]))
    held = held.astype(float)
    n_held = int(held.sum())
    dates = f["dates"]
    idx = np.arange(1, nd)  # session 0 has no prior close
    real = _daily_pos_sharpe(held, tq, bps)
    draws = np.empty(n_draw)
    for j in range(n_draw):
        pos = np.zeros(nd)
        pos[rng.choice(idx, size=n_held, replace=False)] = 1.0
        draws[j] = _daily_pos_sharpe(pos, tq, bps)
    return dict(
        n_draws=int(n_draw), n_held=int(n_held),
        real_sharpe=float(real),
        placebo_mean=float(draws.mean()),
        placebo_p05=float(np.quantile(draws, 0.05)),
        placebo_p95=float(np.quantile(draws, 0.95)),
        p_value=float((1 + (draws >= real).sum()) / (1 + n_draw)),
        percentile=float((draws < real).mean()),
    )


def _daily_pos_sharpe(pos: np.ndarray, r: np.ndarray, bps: float) -> float:
    n = len(pos)
    e = np.empty(n)
    e[0] = 1.0
    for s in range(n - 1):
        prev = pos[s - 1] if s > 0 else 0.0
        cost = abs(pos[s] - prev) * bps / 1e4
        e[s + 1] = e[s] * (1 + pos[s] * r[s] - cost)
    ret = e[1:] / e[:-1] - 1
    sd = ret.std(ddof=0)
    return float(ret.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ts, o, c = bt.panel(SYMBOLS, DEV_START, DEV_END, "1min", warmup_days=0)
    f = daily_features(ts)
    # daily open->close returns used only by the cheap placebo
    f["tq_ses"] = c[f["last"], CT] / o[f["first"], CT] - 1.0
    f["q_ses"] = c[f["last"], CQ] / o[f["first"], CQ] - 1.0

    # ---------------- primary, three cost levels ----------------
    dev = {}
    daily = {}
    for bps in (0.0, 1.0, 5.0, 10.0):
        run, w, meta = run_case(ts, o, c, f, bps=bps)
        s = summarize(run, w, meta)
        dev[f"{bps:g}bp"] = s
        daily[f"{bps:g}bp"] = daily_equity(run)
    run1, w1, meta1 = run_case(ts, o, c, f, bps=1.0)
    daily1 = daily_equity(run1)

    # ---------------- benchmarks ----------------
    bm = {}
    for name, col in (("tqqq", CT), ("qqq", CQ)):
        bw = benchmark_weights(ts, col)
        br = bt.run(ts, o, c, bw, start=DEV_START, band=BAND, slippage_bps=1.0)
        bs = bt.stats(br, BARS_PER_YEAR)
        bs["daily_sharpe"] = daily_stats(daily_equity(br))["sharpe"]
        bm[name] = bs

    # ---------------- yearly / subperiods ----------------
    btw = benchmark_weights(ts, CT)
    btr = bt.run(ts, o, c, btw, start=DEV_START, band=BAND, slippage_bps=1.0)
    btd = daily_equity(btr)
    yearly = {}
    for y in range(2016, 2024):
        d = slice_daily(daily1, f"{y}-01-01", f"{y}-12-31")
        db = slice_daily(btd, f"{y}-01-01", f"{y}-12-31")
        if len(d) > 2:
            yearly[str(y)] = {
                "strategy": float(d.iloc[-1] / d.iloc[0] - 1),
                "tqqq": float(db.iloc[-1] / db.iloc[0] - 1) if len(db) > 2 else np.nan,
            }

    subperiods = {}
    for label, a, b in (("2016_2019", "2016-01-01", "2019-12-31"),
                        ("2020_2021", "2020-01-01", "2021-12-31"),
                        ("2022_2023", "2022-01-01", "2023-12-31")):
        d = slice_daily(daily1, a, b)
        st = daily_stats(d)
        subperiods[label] = {k: st[k] for k in
                             ("cagr", "max_drawdown", "sharpe", "volatility",
                              "sortino", "ending_equity")}

    # ---------------- parameter plateau ----------------
    grid = []
    for sig in ("spy_intraday", "spy_cc", "qqq_intraday"):
        for thr in (0.25, 0.50, 0.75, 1.00):
            for hold in (1, 2):
                r, w, m = run_case(ts, o, c, f, bps=1.0, signal=sig, thr=thr, hold=hold)
                st = summarize(r, w, m)
                grid.append(dict(signal=sig, thr=thr, hold=hold,
                                 cagr=st["cagr"], max_drawdown=st["max_drawdown"],
                                 sharpe=st["sharpe"], daily_sharpe=st["daily_sharpe"],
                                 volatility=st["volatility"], fills=st["fills"],
                                 turnover=st["turnover"], entries=st["entries"],
                                 tqqq_exposure=st["tqqq_exposure"]))

    neighbours = []
    for thr in (0.40, 0.45, 0.50, 0.55, 0.60):
        for hold in (1, 2):
            r, w, m = run_case(ts, o, c, f, bps=1.0, thr=thr, hold=hold)
            st = summarize(r, w, m)
            neighbours.append(dict(thr=thr, hold=hold, cagr=st["cagr"],
                                   max_drawdown=st["max_drawdown"],
                                   sharpe=st["sharpe"], fills=st["fills"],
                                   entries=st["entries"],
                                   tqqq_exposure=st["tqqq_exposure"]))
    for vw in (10, 20, 40, 60):
        r, w, m = run_case(ts, o, c, f, bps=1.0, vol_window=vw)
        st = summarize(r, w, m)
        neighbours.append(dict(thr=0.50, hold=1, vol_window=vw, cagr=st["cagr"],
                               max_drawdown=st["max_drawdown"], sharpe=st["sharpe"],
                               fills=st["fills"], entries=st["entries"],
                               tqqq_exposure=st["tqqq_exposure"]))

    # ---------------- controls / falsifiers ----------------
    controls = {}
    control_specs = {
        "qqq_own_intraday": dict(signal="qqq_intraday", thr=0.50, hold=1),
        "spy_close_to_close": dict(signal="spy_cc", thr=0.50, hold=1),
        "spy_residual": dict(signal="residual", thr=0.50, hold=1),
        "spy_intraday_resid_confirm": dict(signal="spy_intraday", thr=0.50,
                                           hold=1, confirm="resid_neg"),
        "stale_one_session": dict(signal="spy_intraday_stale", thr=0.50, hold=1),
        "exit_next_open": dict(signal="spy_intraday", thr=0.50, hold=1,
                               exit_mode="next_open"),
        "hold_two_sessions": dict(signal="spy_intraday", thr=0.50, hold=2),
        "no_deadband": dict(signal="spy_intraday", thr=0.0, hold=1),
        "cash_idle": dict(signal="spy_intraday", thr=0.50, hold=1, idle="cash"),
    }
    for name, spec in control_specs.items():
        r, w, m = run_case(ts, o, c, f, bps=1.0, **spec)
        st = summarize(r, w, m)
        controls[name] = {k: st[k] for k in
                          ("cagr", "max_drawdown", "sharpe", "daily_sharpe",
                           "volatility", "fills", "turnover", "entries",
                           "tqqq_exposure")}

    # ---------------- signal diagnostics ----------------
    base = event_mask(f, dict(PARAMS))
    # next-session TQQQ return (open->close of d+1)
    fwd_t = np.r_[f["tq_ses"][1:], np.nan]
    fwd_q = np.r_[f["q_ses"][1:], np.nan]
    sig_stats = {
        "n_signal_days": int(base.sum()),
        "unconditional_next_tqqq_bp": float(np.nanmean(fwd_t) * 1e4),
        "signal_next_tqqq_bp": float(np.nanmean(fwd_t[base]) * 1e4),
        "signal_next_qqq_bp": float(np.nanmean(fwd_q[base]) * 1e4),
        "signal_day_tqqq_bp": float(np.nanmean(f["tq_ses"][base]) * 1e4),
        "resid_neg_next_tqqq_bp": float(np.nanmean(fwd_t[base & (f["res_id"] < 0)]) * 1e4),
        "resid_pos_next_tqqq_bp": float(np.nanmean(fwd_t[base & (f["res_id"] > 0)]) * 1e4),
        "mean_beta_id": float(np.nanmean(f["beta_id"])),
    }

    # ---------------- placebo: exact bt circular shift ----------------
    shifts = [13, 17, 23, 31, 37, 43, 53, 61, 71, 79, 89, 101,
              109, 127, 139, 149, 163, 173, 191, 211, 233, 251, 307, 401]
    real_sharpe = dev["1bp"]["sharpe"]
    real_cagr = dev["1bp"]["cagr"]
    placebo = []
    for k in shifts:
        fk = shifted_features(f, k)
        r, w, m = run_case(ts, o, c, fk, bps=1.0)
        st = bt.stats(r, BARS_PER_YEAR)
        placebo.append(dict(shift=int(k), cagr=float(st["cagr"]),
                            sharpe=float(st["sharpe"]),
                            max_drawdown=float(st["max_drawdown"])))
    psh = np.array([p["sharpe"] for p in placebo])
    pcg = np.array([p["cagr"] for p in placebo])
    placebo_shift = dict(
        n_draws=len(shifts), real_sharpe=float(real_sharpe),
        real_cagr=float(real_cagr),
        placebo_sharpe_mean=float(psh.mean()),
        placebo_sharpe_max=float(psh.max()),
        placebo_cagr_mean=float(pcg.mean()),
        placebo_cagr_max=float(pcg.max()),
        p_value_sharpe=float((1 + (psh >= real_sharpe).sum()) / (1 + len(psh))),
        draws=placebo,
    )

    placebo_rand = random_event_placebo(f, dict(PARAMS), n_draw=1000)

    # ---------------- correlations ----------------
    corr = correlations(daily1)
    bret = btd.pct_change().dropna()
    ret1 = daily1.pct_change().dropna()
    j = ret1.index.intersection(bret.index)
    corr["tqqq_buy_hold"] = {"pearson": float(ret1.loc[j].corr(bret.loc[j])),
                             "n": int(len(j))}

    # drawdown window of the primary
    eqv = daily1.to_numpy()
    peakv = np.maximum.accumulate(eqv)
    ddv = eqv / peakv - 1.0
    it = int(ddv.argmin())
    ip = int(np.argmax(eqv[:it + 1]))
    dd_window = {"peak": str(daily1.index[ip].date()),
                 "trough": str(daily1.index[it].date()),
                 "dd": float(-ddv[it])}

    # full stats for the variants that matter to the verdict
    variants = {}
    variant_specs = {
        "hold_two_sessions": dict(signal="spy_intraday", thr=0.50, hold=2),
        "exit_next_open": dict(signal="spy_intraday", thr=0.50, hold=1,
                               exit_mode="next_open"),
        "cash_idle": dict(signal="spy_intraday", thr=0.50, hold=1, idle="cash"),
        "qqq_own_intraday": dict(signal="qqq_intraday", thr=0.50, hold=1),
        "spy_residual": dict(signal="residual", thr=0.50, hold=1),
    }
    short_rev = load_curve("family-short-reversal")
    for name, spec in variant_specs.items():
        vd = {}
        d1 = None
        for bps in (1.0, 5.0, 10.0):
            r, w, m = run_case(ts, o, c, f, bps=bps, **spec)
            st = summarize(r, w, m)
            vd[f"{bps:g}bp"] = {k: st[k] for k in
                                ("cagr", "max_drawdown", "sharpe", "sortino",
                                 "daily_sharpe", "volatility", "fills", "turnover",
                                 "ending_equity", "entries", "avg_hold_sessions",
                                 "tqqq_exposure")}
            if bps == 1.0:
                d1 = daily_equity(r)
        vd["subperiods"] = {}
        for label, a, b in (("2016_2019", "2016-01-01", "2019-12-31"),
                            ("2020_2021", "2020-01-01", "2021-12-31"),
                            ("2022_2023", "2022-01-01", "2023-12-31")):
            ds = daily_stats(slice_daily(d1, a, b))
            vd["subperiods"][label] = {k: ds[k] for k in
                                       ("cagr", "max_drawdown", "sharpe")}
        rr = d1.pct_change().dropna()
        jj = rr.index.intersection(short_rev.index)
        vd["corr_short_reversal"] = float(rr.loc[jj].corr(short_rev.loc[jj]))
        vd["clears_brief_bar"] = bool(
            vd["1bp"]["cagr"] >= 0.3672 and vd["1bp"]["max_drawdown"] <= 0.8229
            and vd["1bp"]["sharpe"] >= 0.82)
        variants[name] = vd

    # ---------------- assemble ----------------
    out = {
        "agent": "family-lead-lag-spillover",
        "family": "cross-market spillover / lead-lag",
        "window": {"dev": [DEV_START, DEV_END], "holdout": "not loaded"},
        "idea": ("SPY's cash-session move is a cleaner read on the common market "
                 "factor than QQQ's own move.  A half-sigma SPY intraday decline "
                 "is followed by a next-session QQQ/TQQQ bounce; hold one session, "
                 "BIL otherwise."),
        "hypothesis": ("SPY's prior-session return contains information about "
                       "QQQ's next-session return beyond QQQ's own past return.  "
                       "The orthogonalised residual should carry the edge if the "
                       "effect is a genuine cross-market spillover rather than "
                       "common-factor reversal."),
        "rules": {
            "signal": ("SPY intraday total return, open-to-close, standardised by "
                       "its trailing 20-session stdev through d-1"),
            "event": "z <= -0.50",
            "entry": "TQQQ at the open of session d+1",
            "exit": "TQQQ at the 15:59 open of session d+1",
            "idle": "BIL",
            "decision_clock": ("16:00 ET close of session d.  SPY and QQQ close at "
                               "the same time; fills are next session's 09:30 open. "
                               "No same-day information is used after 16:00."),
            "alignment": ("SPY daily dates are inner-joined to the QQQ 1-minute "
                          "session calendar; all 2,012 dev sessions have a SPY row. "
                          "Daily SPY open is multiplied by adjclose/close so the "
                          "overnight/intraday split is dividend-consistent."),
        },
        "execution": {
            "engine": "research/bt.py", "marks": "1min", "fills": "next open",
            "band": BAND, "headline_bps": 1.0, "also_bps": [5.0, 10.0],
            "long_only": True, "weight_cap": 1.0,
        },
        "params": dict(PARAMS),
        "dev": dev,
        "benchmark_tqqq": bm["tqqq"],
        "benchmark_qqq": bm["qqq"],
        "brief_tqqq_bar": {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82},
        "yearly": yearly,
        "subperiods": subperiods,
        "grid": grid,
        "neighbours": neighbours,
        "controls": controls,
        "variants": variants,
        "dd_window": dd_window,
        "signal_stats": sig_stats,
        "placebo_shift": placebo_shift,
        "placebo_random_events": placebo_rand,
        "correlations": corr,
        "kill_criteria": {
            "activity": ">= 100 fills",
            "sharpe": ">= 0.82 at 1bp",
            "cagr": ">= 20% at 1bp",
            "cost": "positive CAGR at 10bp",
            "stability": "no negative subperiod CAGR; 2022-2023 daily Sharpe > 0.2",
            "placebo": "shift p-value <= 0.10",
            "novelty": ("orthogonalised residual must predict the tradable "
                        "next-session QQQ open-to-close return with t <= -1.5, "
                        "and must not be matched by QQQ's own signal"),
        },
        "status": "completed",
    }

    # verdict fields are filled after the numbers are known (see report.md)
    D = out["dev"]["1bp"]
    out["verdict"] = {
        "clears_brief_cagr": bool(D["cagr"] >= 0.3672),
        "clears_brief_sharpe": bool(D["sharpe"] >= 0.82),
        "clears_brief_drawdown": bool(D["max_drawdown"] <= 0.8229),
        "clears_brief_bar_all_three": bool(D["cagr"] >= 0.3672
                                           and D["max_drawdown"] <= 0.8229
                                           and D["sharpe"] >= 0.82),
        "variants_clearing_bar": [k for k, v in variants.items()
                                  if v["clears_brief_bar"]],
        "fills": int(D["fills"]),
        "daily_sharpe": float(D["daily_sharpe"]),
        "novelty": ("FAILED: QQQ's own intraday signal is at least as good "
                    "(Sharpe %.3f vs %.3f) and the orthogonalised residual is "
                    "not significant.  This is common-factor short-term "
                    "reversal, not an incremental cross-market spillover."
                    % (variants["qqq_own_intraday"]["1bp"]["sharpe"], D["sharpe"])),
        "note": ("The pre-registered one-session intraday clock misses the "
                 "36.72% CAGR bar.  The two-session and next-open variants "
                 "clear it, but mostly by adding exposure/overnight drift, not "
                 "by strengthening the spillover.  See report.md."),
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float),
                                      encoding="utf-8")
    print(json.dumps({k: out["dev"]["1bp"][k] for k in
                      ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
                       "fills", "turnover", "ending_equity", "tqqq_exposure",
                       "entries", "avg_hold_sessions")}, indent=2))
    print("bench tqqq", {k: round(bm["tqqq"][k], 4) for k in
                         ("cagr", "max_drawdown", "sharpe", "volatility")})
    print("wrote", HERE / "result.json")


def build_holdout_weights(ts, opens, closes):
    """Authorized full-panel adapter: extend the daily SPY/QQQ load to 2026."""
    global DEV_END
    old = DEV_END
    DEV_END = "2026-10-23"
    try:
        return build_weights(ts, opens, closes)
    finally:
        DEV_END = old


if __name__ == "__main__":
    main()
