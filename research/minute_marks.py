r"""Re-mark coarse-bar strategies on the 1-minute panel so drawdowns compare like with like.

Most agents trade and mark equity on 1-minute bars. A few decide on daily or
5-minute bars and so only mark equity at those closes, which hides intraday
troughs (the daily 165d baseline's 5y drawdown is 36.9% on daily marks but 42.2%
on minute marks). This script takes each such strategy's own coarse weights,
holds them on the 1-minute panel exactly as the coarse simulation would, and
re-runs research/bt.py with the usual 2% band and 1 bp.

Mapping: coarse weights w[k] are set at coarse bar k's close and fill at the
next coarse bar's open. On minutes, the weight at the last minute of bar k is
w[k], and every other minute of bar k carries w[k-1]. With next-bar-open fills
that reproduces the coarse fill times exactly; only the equity marks (and band
drift checks) become per-minute.

Writes research/minute_marked.json, which export_web_compare.py uses for the
leaderboard instead of the coarse-marked numbers.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/minute_marks.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

OUT = ROOT / "research" / "minute_marked.json"
SYMS = ("QQQ", "TQQQ", "BIL")
START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_1M = 252 * 390


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "research" / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_BUCKET_CACHE: dict = {}


def _minute_buckets(ts1: pd.DatetimeIndex, rule: str) -> pd.DatetimeIndex:
    key = (id(ts1), rule)
    cached = _BUCKET_CACHE.get(key)
    if cached is not None:
        return cached
    buckets = ts1.normalize() if rule == "1D" else ts1.floor(rule)
    _BUCKET_CACHE.clear()
    _BUCKET_CACHE[key] = buckets
    return buckets


_SRC_CACHE: dict = {}


def _minute_source(ts_coarse, ts1: pd.DatetimeIndex, rule: str):
    """Coarse row held by each minute (-1 = before the first coarse fill).

    Sweeps call `to_minutes` hundreds of times with the same calendars, so the
    mapping is cached by the coarse timestamps' values and the minute index.
    """
    coarse_i8 = np.asarray(pd.DatetimeIndex(ts_coarse).asi8)
    key = (rule, id(ts1), len(ts1), str(getattr(ts_coarse, "tz", None)),
           len(coarse_i8), hash(coarse_i8.tobytes()))
    hit = _SRC_CACHE.get(key)
    if hit is not None and hit[0] is ts1:
        return hit[1], hit[2]
    if rule == "1D":
        bucket1 = _minute_buckets(ts1, rule)
        coarse = pd.DatetimeIndex(ts_coarse).normalize()
    else:
        bucket1 = _minute_buckets(ts1, rule)
        coarse = pd.DatetimeIndex(ts_coarse)
    k = coarse.get_indexer(bucket1)
    if (k < 0).any():
        raise ValueError(f"{(k < 0).sum()} minutes have no {rule} bar")
    last = np.r_[k[1:] != k[:-1], True]
    src = np.where(last, k, k - 1)
    before = src < 0
    src = np.where(before, 0, src)
    before = before if before.any() else None
    _SRC_CACHE.clear()
    _SRC_CACHE[key] = (ts1, src, before)
    return src, before


def to_minutes(ts_coarse: pd.DatetimeIndex, w_coarse: np.ndarray, ts1: pd.DatetimeIndex,
               rule: str) -> np.ndarray:
    """Hold coarse weights on minutes with the same fill times as the coarse run."""
    src, before = _minute_source(ts_coarse, ts1, rule)
    w = np.asarray(w_coarse, dtype=float).take(src, axis=0)
    if before is not None:
        w[before] = (0.0, 0.0, 1.0)
    return w


def score(ts1, o1, c1, w1) -> dict:
    out = {}
    for label, start in (("10y", START10), ("5y", START5)):
        r = bt.run(ts1, o1, c1, w1, start, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS_1M)
        out[label] = {"cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
                      "sharpe": float(s["sharpe"]), "fills": int(s["fills"])}
    return out


def coarse_score(ts, o, c, w, bars) -> dict:
    out = {}
    for label, start in (("10y", START10), ("5y", START5)):
        s = bt.stats(bt.run(ts, o, c, w, start, band=0.02, slippage_bps=1.0), bars)
        out[label] = {"cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"])}
    return out


def main():
    ts1, o1, c1 = bt.panel(SYMS, START10, END, "1min")
    tsd, od, cd = bt.panel(SYMS, START10, END, "1D")
    ts5, o5, c5 = bt.panel(SYMS, START10, END, "5min")
    coarse = {}

    ml = load("mlc_daily", "agents/ml-classifier/strategy.py")
    w_ml, *_ = ml.build_strategy(ts5, o5, c5, tsd, od, cd)
    coarse["ml-classifier"] = (tsd, od, cd, w_ml, "1D", 252)

    vk = load("volkelly", "agents/vol-kelly-overlay/strategy.py")
    tsv, ov, cv = vk.daily_panel()
    w_vk, _ = vk.build_weights(tsv, cv, vk.tqqq_rv(tsv))
    coarse["vol-kelly-overlay"] = (tsv, ov, cv, w_vk, "1D", 252)

    # The README daily 165d SMA baseline (same rule ml-classifier uses as its base).
    q = cd[:, 0]
    on = q > pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    w_base = np.zeros((len(tsd), 3))
    w_base[:, 1] = on
    w_base[:, 2] = 1.0 - on
    coarse["benchmark-daily"] = (tsd, od, cd, w_base, "1D", 252)

    dc = load("donchian", "agents/donchian-breakout/strategy.py")
    p = dc.load_panel("5min")
    w_dc = dc.donchian_weights(*p, dc.PRIMARY_N)
    coarse["donchian-breakout"] = (p[0], p[1], p[2], w_dc, "5min", 252 * 78)

    imr = load("imr", "agents/intraday-mean-reversion/strategy.py")
    imr.RULE = "5min"
    ts_m, o_m, c_m, w_m, _ = imr.build("5min", 0.03, 165)
    coarse["intraday-mean-reversion"] = (ts_m, o_m, c_m, w_m, "5min", 252 * 78)

    result = {"note": __doc__.split("\n\n")[1].replace("\n", " "), "agents": {}}
    for slug, (ts, o, c, w, rule, bars) in coarse.items():
        w1 = to_minutes(ts, w, ts1, rule)
        row = {"rule": rule, "coarse": coarse_score(ts, o, c, w, bars),
               "minute": score(ts1, o1, c1, w1)}
        result["agents"][slug] = row
        cm, mm = row["coarse"], row["minute"]
        print(f"{slug:26s} {rule:>4s}  10y {cm['10y']['cagr']*100:6.2f}/{cm['10y']['max_drawdown']*100:5.2f}"
              f" -> {mm['10y']['cagr']*100:6.2f}/{mm['10y']['max_drawdown']*100:5.2f}"
              f"   5y {cm['5y']['cagr']*100:6.2f}/{cm['5y']['max_drawdown']*100:5.2f}"
              f" -> {mm['5y']['cagr']*100:6.2f}/{mm['5y']['max_drawdown']*100:5.2f}", flush=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
