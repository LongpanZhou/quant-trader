"""One-shot 2016-2026 holdout for a `research/new/<slug>` strategy.

The strategy is frozen after its development result.  This script loads the full
1-minute panel, calls `build_weights(ts, opens, closes)` once, runs the shared
engine, and reports development, holdout, full-window, 10y and 5y metrics plus
the full daily curve.  It must not be used to tune the strategy.

Usage:
    python research/new/run_holdout.py relative-value-tqqq
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
CURVES = NEW / "curves"
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START, DEV_END, END = "2016-01-04", "2023-12-29", "2026-10-23"
TEN, FIVE = "2017-01-03", "2021-10-25"


def load(slug: str):
    path = NEW / slug / "strategy.py"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    spec = importlib.util.spec_from_file_location("new_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def to_three(w, n: int) -> np.ndarray:
    """Normalise a public build_weights result to the 3-asset panel.

    Some agents build a 2-asset (QQQ, TQQQ) strategy with cash idle.  The shared
    engine panel is QQQ/TQQQ/BIL; pad BIL with zero so the unallocated fraction
    remains cash, matching the strategy's stated idle return.
    """
    w = np.asarray(w, dtype=float)
    if w.shape == (n, 3):
        return w
    if w.shape == (n, 2):
        out = np.zeros((n, 3))
        out[:, :2] = w
        return out
    raise ValueError(f"build_weights returned {w.shape}, expected {(n, 3)} or {(n, 2)}")


TWO_COL_TQQQ_BIL = {"family-intraday-microstructure", "family-intraday-microstructure-day"}
ONE_COL_TQQQ = {"family-ml-microstructure"}


def one_col_to_three(w, n: int) -> np.ndarray:
    """Map a 1-D TQQQ weight vector to the shared QQQ/TQQQ/BIL columns."""
    w = np.asarray(w, dtype=float).reshape(-1)
    if len(w) != n:
        raise ValueError(f"expected {n} TQQQ weights, got {len(w)}")
    out = np.zeros((n, 3))
    out[:, 1] = np.clip(w, 0.0, 1.0)
    out[:, 2] = 1.0 - out[:, 1]
    return out


def tqqq_bil_to_three(w, n: int) -> np.ndarray:
    """Map a (TQQQ, BIL) weight matrix to the shared QQQ/TQQQ/BIL columns."""
    w = np.asarray(w, dtype=float)
    if w.shape != (n, 2):
        raise ValueError(f"expected {(n, 2)} TQQQ/BIL weights, got {w.shape}")
    out = np.zeros((n, 3))
    out[:, 1] = w[:, 0]
    out[:, 2] = w[:, 1]
    return out


def build_full(mod, ts, o, c):
    """Call build_weights, lifting a dev-only panel guard for the holdout.

    Several agents hard-code a guard that raises if the panel extends past
    2023-12-29.  The lead's holdout run is the authorization to lift it; the
    strategy's signal, parameters and weight logic are unchanged.

    A strategy may provide `build_holdout_weights(ts, o, c)` when its public
    `build_weights` needs an explicit data-window adapter (e.g. full-panel
    bars).  The hook is optional and leaves every other strategy untouched.
    """
    if hasattr(mod, "build_holdout_weights"):
        return mod.build_holdout_weights(ts, o, c)
    try:
        return mod.build_weights(ts, o, c)
    except (ValueError, RuntimeError, AssertionError) as exc:
        msg = str(exc).lower()
        if ("development window" not in msg and "past the development" not in msg
                and "holdout" not in msg):
            raise
        if hasattr(mod, "END"):
            mod.END = END
        if hasattr(mod, "DEV_END"):
            mod.DEV_END = pd.Timestamp(END)
        return mod.build_weights(ts, o, c)


def expand_daily_weights(wd, tsd: pd.DatetimeIndex, ts1: pd.DatetimeIndex) -> np.ndarray:
    """Expand daily target weights to the minute panel.

    `wd[k]` is set at the close of session k and held during session k+1,
    matching `bt.simulate`'s next-open convention.
    """
    wd = np.asarray(wd, dtype=float)
    if wd.ndim != 2 or wd.shape[1] != 3 or len(wd) != len(tsd):
        raise ValueError(f"daily weights {wd.shape} do not match {len(tsd)} sessions")
    dates_d = bt.session_dates(tsd)
    dates_m_bar = bt.session_dates(ts1)
    first, last = bt.day_bounds_from_dates(dates_m_bar)
    dates_m = dates_m_bar[first]
    counts = last - first + 1
    idx = np.searchsorted(dates_d, dates_m)
    if (idx >= len(dates_d)).any() or not np.array_equal(dates_d[idx], dates_m):
        raise RuntimeError("daily and minute session calendars do not align")
    target = np.zeros_like(wd)
    target[1:] = wd[:-1]
    return np.repeat(target[idx], counts, axis=0)


def build_daily(mod, tsd, od, cd, ts1, end: str = END) -> np.ndarray:
    """Build daily weights (or states) and map them onto the minute panel."""
    import inspect

    kw = {}
    if "end" in inspect.signature(mod.build_weights).parameters:
        kw["end"] = end
    out = mod.build_weights(tsd, od, cd, **kw)
    states = out[0] if isinstance(out, tuple) else out
    if np.asarray(states).ndim == 2 and np.asarray(states).shape[1] == 3:
        return expand_daily_weights(states, tsd, ts1)
    return to_three(mod.minute_weights(states, tsd, ts1), len(ts1))


def minute_stats(r: dict, lo: str, hi: str) -> dict:
    """Window metrics from the full-run result and its per-fill log.

    Fills and turnover are sliced from ``r["fills_log"]`` (requires
    ``bt.run(..., fill_log=True)``).  ``turnover`` is the sum of the fill
    notionals in ``[lo, hi + 1 day)`` divided by the window's starting equity
    (the first marked equity in the window), not by the full-run start
    equity.  The keys ``traded_notional`` and ``turnover_start_equity`` expose
    the numerator and denominator used.
    """
    ts = pd.DatetimeIndex(r["ts"])
    a = pd.Timestamp(lo, tz="America/New_York")
    b = pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)
    mask = (ts >= a) & (ts <= b)
    rr = {k: (np.asarray(v)[mask]
              if isinstance(v, (list, np.ndarray)) and k != "fills_log" else v)
          for k, v in r.items()}
    rr["ts"] = ts[mask]
    s = bt.stats(rr, 252 * 390)
    out = {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "sortino",
                                    "volatility", "fills", "turnover", "exposure",
                                    "ending_equity") if k in s}
    if "fills_log" not in r:
        raise ValueError("minute_stats requires a fill log: "
                         "call bt.run(..., fill_log=True)")
    fills = [x for x in r["fills_log"] if a <= pd.Timestamp(x["ts"]) < b]
    traded = float(sum(float(x["notional"]) for x in fills))
    start_eq = float(rr["equity"][0])
    out["fills"] = int(len(fills))
    out["turnover"] = traded / start_eq if start_eq > 0 else 0.0
    out["traded_notional"] = traded
    out["turnover_start_equity"] = start_eq
    out["turnover_denominator"] = "window_start_equity"
    return out


def daily_stats(daily: pd.Series, lo: str, hi: str) -> dict:
    s = daily[(daily.index >= pd.Timestamp(lo)) & (daily.index <= pd.Timestamp(hi))]
    if len(s) < 2:
        return {}
    eq = s.to_numpy(dtype=float)
    years = (s.index[-1] - s.index[0]).days / 365.25
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "max_drawdown": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
        "start": str(s.index[0].date()),
        "end": str(s.index[-1].date()),
        "days": int(len(s)),
    }


def daily_curve(equity: np.ndarray, ts: pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(equity, index=ts)
    daily = s.groupby(s.index.date).last()
    daily.index = pd.to_datetime(daily.index)
    return daily / daily.iloc[0] * 100.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--daily", action="store_true",
                    help="strategy builds daily weights; expand with minute_weights")
    args = ap.parse_args()
    slug = args.slug

    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    mod = load(slug)
    if slug == "cross-asset-momentum":
        # This strategy carries an explicit dev-only guard in daily_frame().
        # The lead's authorized holdout lifts that guard to the full panel end;
        # no signal, parameter or weight logic is changed.
        mod.DEV_END = pd.Timestamp(END)
    if args.daily:
        tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1D", warmup_days=0)
        if slug == "family-ml-microstructure":
            feats = mod.build_feature_panel(end=END)
            out = mod.build_weights(tsd, od, cd, features=feats)
            states = out[0] if isinstance(out, tuple) else out
            w = mod.minute_weights(states, ts)
            if slug in ONE_COL_TQQQ:
                w = one_col_to_three(w, len(ts))
        else:
            w = build_daily(mod, tsd, od, cd, ts)
    elif slug in TWO_COL_TQQQ_BIL:
        out = build_full(mod, ts, o[:, [1, 2]], c[:, [1, 2]])
        raw = out[0] if isinstance(out, tuple) else out
        w = tqqq_bil_to_three(raw, len(ts))
    else:
        out = build_full(mod, ts, o, c)
        w = out[0] if isinstance(out, tuple) else out
    w = np.asarray(w, dtype=float)
    w = to_three(w, len(ts))
    if w.shape != (len(ts), 3):
        raise SystemExit(f"{slug}: build_weights returned {w.shape}, expected {(len(ts), 3)}")

    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0, fill_log=True)
    eq = pd.Series(r["equity"], index=pd.DatetimeIndex(r["ts"]))
    daily = daily_curve(r["equity"], pd.DatetimeIndex(r["ts"]))

    def bench(col: int) -> pd.Series:
        s = pd.Series(c[:, col], index=pd.DatetimeIndex(ts))
        d = s.groupby(s.index.date).last()
        d.index = pd.to_datetime(d.index)
        return d / d.iloc[0] * 100.0

    tqqq, qqq = bench(1), bench(0)
    windows = {
        "dev": (START, DEV_END),
        "holdout": ("2024-01-02", END),
        "full": (START, END),
        "10y": (TEN, END),
        "5y": (FIVE, END),
    }
    result = {
        "slug": slug,
        "generated": pd.Timestamp.now(tz="UTC").isoformat(),
        "windows": {},
        "daily_curve": {
            "dates": [str(d.date()) for d in daily.index],
            "values": [float(v) for v in daily.to_numpy()],
        },
        "benchmarks": {
            sym: {
                "dev": daily_stats(curve, START, DEV_END),
                "holdout": daily_stats(curve, "2024-01-02", END),
                "full": daily_stats(curve, START, END),
                "10y": daily_stats(curve, TEN, END),
                "5y": daily_stats(curve, FIVE, END),
            }
            for sym, curve in (("tqqq", tqqq), ("qqq", qqq))
        },
    }
    for name, (lo, hi) in windows.items():
        result["windows"][name] = {
            "1bp": minute_stats(r, lo, hi),
            "daily": daily_stats(daily, lo, hi),
        }

    path = NEW / slug / "holdout.json"
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    CURVES.mkdir(parents=True, exist_ok=True)
    (CURVES / f"{slug}.json").write_text(json.dumps({
        "slug": slug,
        "dates": result["daily_curve"]["dates"],
        "values": result["daily_curve"]["values"],
    }), encoding="utf-8")

    dev = result["windows"]["dev"]["1bp"]
    hold = result["windows"]["holdout"]["1bp"]
    full = result["windows"]["full"]["1bp"]
    print(f"{slug}")
    print(f"  dev     {dev['cagr']*100:6.2f}% CAGR {dev['max_drawdown']*100:6.2f}% DD "
          f"{dev['sharpe']:5.2f} Sharpe  fills {dev['fills']}  "
          f"turnover {dev['turnover']:.2f}x")
    print(f"  holdout {hold['cagr']*100:6.2f}% CAGR {hold['max_drawdown']*100:6.2f}% DD "
          f"{hold['sharpe']:5.2f} Sharpe  fills {hold['fills']}  "
          f"turnover {hold['turnover']:.2f}x")
    print(f"  full    {full['cagr']*100:6.2f}% CAGR {full['max_drawdown']*100:6.2f}% DD "
          f"{full['sharpe']:5.2f} Sharpe  fills {full['fills']}  "
          f"turnover {full['turnover']:.2f}x")
    print(f"  wrote {path}")


if __name__ == "__main__":
    main()
