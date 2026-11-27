r"""Risk-managed TQQQ/QQQ/BIL overlay on the QQQ 165-day SMA regime.

Rules
-----
1. Regime (daily close, no look-ahead):
   risk-on when QQQ close > 165-day SMA of QQQ close, else 100% BIL.
2. Volatility ladder (risk-on only): 20-day realized volatility of TQQQ,
   annualized from 1-minute within-day log returns (sum of squares per day,
   then a 20-day average).  At vol <= 65% hold 100% TQQQ; between 65% and
   95% linearly shift the risky sleeve into QQQ; at vol >= 95% hold QQQ.
3. Crash throttle: if QQQ is >= 6% below its trailing 20-day high AND TQQQ
   5-day realized vol >= 55%, scale the whole risky sleeve by 0.95 (5% to
   BIL).  This is a mild, same-day de-risking, not a stop that locks out.
4. All weights are set from the close of day i and filled at the open of
   day i+1.  Long only, weights sum to <= 1.

Run from the repo root:
    $env:PYTHONPATH = "C:/Users/27175/AppData/Local/Temp/opencode/pylibs"
    python research/agents/vol-kelly-overlay/strategy.py
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
START = "2017-01-03"
END = "2026-10-23"
W5 = "2021-10-25"
SYMS = ("QQQ", "TQQQ", "BIL")

# Round, economically motivated parameters; see report.md for sensitivity.
SMA_N = 165
VOL_N = 20
VOL_LO = 0.65
VOL_HI = 0.95
DD_N = 20
DD_X = 0.06
DD_VOL_X = 0.55
DD_CUT = 0.05
BAND = 0.02


def daily_panel():
    ts, opens, closes = bt.panel(SYMS, START, END, "1D")
    op = np.column_stack([opens[:, 0], opens[:, 1], opens[:, 2]])
    cl = np.column_stack([closes[:, 0], closes[:, 1], closes[:, 2]])
    return ts, op, cl


def tqqq_rv(ts: pd.DatetimeIndex) -> np.ndarray:
    """Per-day 1-minute realized variance of TQQQ, aligned to `ts`."""
    cache = HERE / "rv1m.parquet"
    if cache.exists():
        rv = pd.read_parquet(cache)
        series = rv["TQQQ"]
    else:
        df = bt.load_1m("TQQQ").sort_values("ts")
        prev = df.groupby("date")["close"].shift(1)
        r = np.log(df["close"] / prev)
        r = r.where(np.isfinite(r), 0.0)
        series = (r * r).groupby(df["date"]).sum()
    idx = pd.to_datetime(series.index)
    if idx.tz is None:
        idx = idx.tz_localize("America/New_York")
    else:
        idx = idx.tz_convert("America/New_York")
    series.index = idx
    series = series.reindex(pd.DatetimeIndex(ts).normalize()).ffill()
    return series.to_numpy()


def build_weights(ts, cl, rv):
    qqq = cl[:, 0]
    sma = pd.Series(qqq).rolling(SMA_N).mean().to_numpy()
    state = (qqq > sma).astype(float)
    state[:SMA_N] = 0.0

    vol20 = np.sqrt(pd.Series(rv).rolling(VOL_N).mean().to_numpy() * 252.0)
    vol5 = np.sqrt(pd.Series(rv).rolling(5).mean().to_numpy() * 252.0)
    share = np.clip((vol20 - VOL_LO) / (VOL_HI - VOL_LO), 0.0, 1.0)
    share = np.where(np.isfinite(share), share, 1.0)

    ddq = (pd.Series(qqq) / pd.Series(qqq).rolling(DD_N).max() - 1.0).to_numpy()
    cut = (ddq <= -DD_X) & (vol5 >= DD_VOL_X) & np.isfinite(vol5)
    scale = np.where(cut, 1.0 - DD_CUT, 1.0)

    w = np.zeros((len(qqq), 3))
    on = state > 0
    w[on, 0] = scale[on] * share[on]          # QQQ
    w[on, 1] = scale[on] * (1.0 - share[on])  # TQQQ
    w[on, 2] = 1.0 - scale[on]                # BIL
    w[~on, 2] = 1.0
    return w, dict(state=state, vol20=vol20, vol5=vol5, share=share,
                    cut=cut, sma=sma)


def baseline_weights(state):
    w = np.zeros((len(state), 3))
    w[:, 1] = state
    w[:, 2] = 1.0 - state
    return w


def binary_weights(diag):
    """Alternative: 100% TQQQ below 70% vol, 100% QQQ above, same cut."""
    state = diag["state"]
    vol20 = diag["vol20"]
    cut = diag["cut"]
    scale = np.where(cut, 1.0 - DD_CUT, 1.0)
    hi = np.isfinite(vol20) & (vol20 >= 0.70)
    on = state > 0
    w = np.zeros((len(state), 3))
    w[on & ~hi, 1] = scale[on & ~hi]
    w[on & hi, 0] = scale[on & hi]
    w[on, 2] = 1.0 - scale[on]
    w[~on, 2] = 1.0
    return w


def run_window(d, w, start, end, slip):
    ts, op, cl = d
    i0 = bt.start_index(ts, start)
    i1 = int(ts.searchsorted(pd.Timestamp(end, tz="America/New_York"))) + 1
    res = bt.simulate(ts[i0:i1], op[i0:i1], cl[i0:i1], w[i0:i1],
                      band=BAND, slippage_bps=slip)
    return bt.stats(res, 252)


def run(d, w, start, slip):
    ts, op, cl = d
    res = bt.run(ts, op, cl, w, start=start, band=BAND, slippage_bps=slip)
    s = bt.stats(res, 252)
    i0 = bt.start_index(ts, start)
    b = bt.benchmark(cl[i0:, 1], ts[i0:], 252)
    return res, s, b


def main():
    ts, op, cl = daily_panel()
    rv = tqqq_rv(ts)
    w, diag = build_weights(ts, cl, rv)
    base = baseline_weights(diag["state"])
    d = (ts, op, cl)

    out = {
        "strategy": "vol-kelly-overlay",
        "description": "QQQ 165d SMA regime with a 1m-RV TQQQ->QQQ volatility "
                       "ladder and a mild crash throttle.",
        "params": dict(sma= SMA_N, vol_n=VOL_N, vol_lo=VOL_LO, vol_hi=VOL_HI,
                       dd_n=DD_N, dd_x=DD_X, dd_vol_x=DD_VOL_X, cut=DD_CUT,
                       band=BAND, slippage_bps_primary=1.0,
                       slippage_bps_sensitivity=5.0),
        "windows": {},
    }

    for tag, start in (("10y", START), ("5y", W5)):
        rec = {}
        for slip in (1.0, 5.0):
            res, s, b = run(d, w, start, slip)
            rb, sb, bb = run(d, base, start, slip)
            rec[f"{int(slip)}bp"] = {
                "candidate": {k: float(v) for k, v in s.items()},
                "baseline": {k: float(v) for k, v in sb.items()},
                "tqqq": {k: float(v) for k, v in b.items()},
            }
            if slip == 1.0:
                i0 = bt.start_index(ts, start)
                yy = bt.yearly(res["ts"], res["equity"], cl[i0:, 1])
                rec["yearly"] = {
                    int(y): {"strategy": float(v["strategy"]),
                             "tqqq": float(v["benchmark"])}
                    for y, v in yy.items()
                }
                rec["yearly_baseline"] = {
                    int(y): float(v["strategy"])
                    for y, v in bt.yearly(rb["ts"], rb["equity"],
                                          cl[i0:, 1]).items()
                }
        out["windows"][tag] = rec

    # Alternative binary 70% QQQ switch (same crash throttle).
    wb = binary_weights(diag)
    out["alternative_binary_70"] = {}
    for tag, start in (("10y", START), ("5y", W5)):
        rec = {}
        for slip in (1.0, 5.0):
            res, s, b = run(d, wb, start, slip)
            rec[f"{int(slip)}bp"] = {
                "candidate": {k: float(v) for k, v in s.items()},
                "tqqq": {k: float(v) for k, v in b.items()},
            }
        out["alternative_binary_70"][tag] = rec

    # Half-period stability of the primary.
    out["half_periods"] = {}
    for tag, start, end in (("2017_2021", "2017-01-03", "2021-12-31"),
                            ("2022_2026", "2022-01-03", "2026-10-23")):
        out["half_periods"][tag] = {
            "candidate": {k: float(v) for k, v in
                          run_window(d, w, start, end, 1.0).items()},
            "baseline": {k: float(v) for k, v in
                         run_window(d, base, start, end, 1.0).items()},
        }

    # Comparisons / pass-fail vs the stated benchmarks.
    for tag, base_cagr, base_dd in (("10y", 0.4531, 0.5871),
                                    ("5y", 0.3461, 0.3686)):
        c = out["windows"][tag]["1bp"]["candidate"]
        t = out["windows"][tag]["1bp"]["tqqq"]
        out["windows"][tag]["vs_tqqq"] = {
            "cagr_delta": c["cagr"] - t["cagr"],
            "dd_delta": c["max_drawdown"] - t["max_drawdown"],
            "pass": bool(c["cagr"] > t["cagr"]
                         and c["max_drawdown"] < t["max_drawdown"]),
        }
        out["windows"][tag]["vs_daily_baseline"] = {
            "cagr_delta_vs_quoted": c["cagr"] - base_cagr,
            "dd_delta_vs_quoted": c["max_drawdown"] - base_dd,
            "pass": bool(c["cagr"] > base_cagr
                         and c["max_drawdown"] < base_dd),
        }

    (HERE / "result.json").write_text(json.dumps(out, indent=2))

    # Console summary.
    for tag in ("10y", "5y"):
        c = out["windows"][tag]["1bp"]["candidate"]
        c5 = out["windows"][tag]["5bp"]["candidate"]
        t = out["windows"][tag]["1bp"]["tqqq"]
        b = out["windows"][tag]["1bp"]["baseline"]
        print(f"\n{tag}  candidate   CAGR {c['cagr']*100:6.2f}%  "
              f"DD {c['max_drawdown']*100:5.2f}%  Sharpe {c['sharpe']:.2f}  "
              f"fills {c['fills']:.0f}  turnover {c['turnover']:.1f}x")
        print(f"      at 5bp     CAGR {c5['cagr']*100:6.2f}%  "
              f"DD {c5['max_drawdown']*100:5.2f}%  Sharpe {c5['sharpe']:.2f}")
        print(f"      baseline    CAGR {b['cagr']*100:6.2f}%  "
              f"DD {b['max_drawdown']*100:5.2f}%  Sharpe {b['sharpe']:.2f}")
        print(f"      TQQQ        CAGR {t['cagr']*100:6.2f}%  "
              f"DD {t['max_drawdown']*100:5.2f}%  Sharpe {t['sharpe']:.2f}")
        print(f"      pass vs TQQQ {out['windows'][tag]['vs_tqqq']['pass']}  "
              f"pass vs baseline {out['windows'][tag]['vs_daily_baseline']['pass']}")
        print("      yearly: " + "  ".join(
            f"{y}:{v['strategy']*100:.1f}/{v['tqqq']*100:.1f}"
            for y, v in out["windows"][tag]["yearly"].items()))
    print(f"\nwrote {HERE / 'result.json'}")


if __name__ == "__main__":
    main()
