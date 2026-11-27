r"""Time-of-Day Leverage Ladder (TODL) — standalone rebuild of intraday-momentum.

Pre-registered design (2026-11-26). Backtests are PAUSED: this module is not run
by the author until the lead/user authorizes the new test.

The strategy replaces the old 165-day QQQ price-trend base with a weekly
three-state ladder derived only from the time-of-day return decomposition:

    QQQ 3x (TQQQ) if both time-of-day signals are above their 26-week medians
    QQQ 1x        if exactly one signal is above its median
    BIL           if neither is above its median

Signals, computed on QQQ over the last 5 sessions:
    S_on = sum(overnight - intraday)   (overnight vs intraday tug of war)
    S_fh = sum(first_hour)             (first-hour momentum)

Risk cap: 20-session realised overnight vol > 60% caps TQQQ at QQQ; > 80%
moves the book to BIL. Rebalance at the close of every 5th session; the target
fills at the next session's open. No 165-day price moving average is used.

All numbers produced by `main()` are development-window only
(2016-01-04..2023-12-29). The holdout 2024-01-02..2026-10-23 is never loaded
here; the lead runs the frozen strategy on it once.
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

DEV_START = "2016-01-04"
DEV_END = "2023-12-29"
BARS_PER_YEAR = 252 * 390

# Panel columns: 0 = QQQ, 1 = TQQQ, 2 = BIL.
STATE_W = {
    "TQQQ": np.array([0.0, 1.0, 0.0]),
    "QQQ": np.array([1.0, 0.0, 0.0]),
    "BIL": np.array([0.0, 0.0, 1.0]),
}

PARAMS = dict(
    rebalance_every=5,   # 5-session holding period
    median_weeks=26,     # 26-week rolling median of each weekly signal
    min_history=13,      # do not trade until 13 weekly observations exist
    vol_window=20,       # 20-session overnight-vol estimate
    vol_cap_qqq=0.60,    # above this, TQQQ is capped at QQQ
    vol_cap_bil=0.80,    # above this, the book is BIL
    fh_bars=60,          # first-hour window, in 1-minute bars
)


def _sessions(ts: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """First bar index and exclusive end index for each regular session."""
    day = ts.values.astype("datetime64[D]")
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return starts, ends


def build_weights(
    ts: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    **overrides,
) -> tuple[np.ndarray, dict]:
    """Return (n, 3) target weights and diagnostics.

    The signal for a 5-session block is computed at the block's last bar and
    fills at the next session's open. No future data is used.
    """
    p = dict(PARAMS)
    p.update(overrides)
    n = len(ts)
    a, b = _sessions(ts)
    ndays = len(a)

    # First-hour return: close of the 60th bar / first open. Require 60 bars.
    i_fh = a + p["fh_bars"] - 1
    valid_fh = (b - a) >= p["fh_bars"]
    fh = np.where(
        valid_fh,
        closes[np.clip(i_fh, 0, n - 1), 0] / opens[a, 0] - 1.0,
        np.nan,
    )

    # Overnight and intraday returns on QQQ.
    on = np.full(ndays, np.nan)
    on[1:] = opens[a[1:], 0] / closes[b[:-1] - 1, 0] - 1.0
    intraday = closes[b - 1, 0] / opens[a, 0] - 1.0

    w = np.zeros((n, 3))
    w[:, 2] = 1.0  # default BIL before the first live rebalance

    step = p["rebalance_every"]
    first = 2 * step - 1  # first window has a valid prior close for every day
    rebs = list(range(first, ndays, step))
    hist_on: list[float] = []
    hist_fh: list[float] = []
    records: list[dict] = []

    for r in rebs:
        win = np.arange(r - step + 1, r + 1)
        if len(win) != step:
            continue
        if not (
            np.isfinite(on[win]).all()
            and np.isfinite(intraday[win]).all()
            and np.isfinite(fh[win]).all()
        ):
            continue

        s_on = float(np.sum(on[win] - intraday[win]))
        s_fh = float(np.sum(fh[win]))
        hist_on.append(s_on)
        hist_fh.append(s_fh)

        if len(hist_on) < p["min_history"]:
            continue

        med_on = float(np.median(hist_on[-p["median_weeks"] :]))
        med_fh = float(np.median(hist_fh[-p["median_weeks"] :]))
        on_sig = s_on > med_on
        fh_sig = s_fh > med_fh

        if on_sig and fh_sig:
            state = "TQQQ"
        elif on_sig or fh_sig:
            state = "QQQ"
        else:
            state = "BIL"

        # Risk cap from the overnight return series itself.
        vwin = np.arange(max(0, r - p["vol_window"] + 1), r + 1)
        vol_on = float(np.nanstd(on[vwin], ddof=0) * np.sqrt(252))
        if vol_on > p["vol_cap_bil"]:
            state = "BIL"
        elif vol_on > p["vol_cap_qqq"] and state == "TQQQ":
            state = "QQQ"

        # The rebalance bar's close is the decision; the weight fills at the
        # next session's open. The following block carries the same state.
        # b is the exclusive session end, so the decision bar is b[r] - 1.
        # (This was w[r], a session number used as a bar index: it wrote into
        # the first week of 2016 and left each switch one minute late.)
        w[b[r] - 1, :] = STATE_W[state]
        next_last = min(r + step, ndays - 1)
        if r + 1 < ndays:
            w[a[r + 1] : b[next_last], :] = STATE_W[state]

        records.append(
            dict(
                decision_bar=str(ts[b[r] - 1]),
                s_on=s_on,
                s_fh=s_fh,
                med_on=med_on,
                med_fh=med_fh,
                vol_on=vol_on,
                state=state,
            )
        )

    info = {
        "params": p,
        "sessions": int(ndays),
        "rebalances": len(records),
        "first_rebalance": records[0]["decision_bar"] if records else None,
        "state_counts": {
            s: sum(1 for x in records if x["state"] == s)
            for s in ("TQQQ", "QQQ", "BIL")
        },
        "records": records,
    }
    return w, info


def _daily_equity(result: dict) -> pd.Series:
    """Last equity mark of each session, tz-naive date index."""
    eq = pd.Series(result["equity"], index=pd.to_datetime(result["ts"]))
    de = eq.groupby(eq.index.normalize()).last()
    de.index = de.index.tz_localize(None)
    return de


def _baseline_daily() -> pd.Series:
    """The old 165-day QQQ/TQQQ/BIL baseline, for the correlation check only.

    This is deliberately not used by the strategy. It is the benchmark the
    brief asks every rebuild to correlate against.
    """
    dts, dop, dcl = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1D")
    q = pd.Series(dcl[:, 0], index=pd.Index(bt.session_dates(dts)))
    sma = q.rolling(165).mean()
    reg = (q > sma).to_numpy()
    w = np.zeros((len(dts), 3))
    for i in range(len(dts)):
        if not np.isfinite(sma.iloc[i]) or not reg[i]:
            w[i, 2] = 1.0
        else:
            w[i, 1] = 1.0
    r = bt.run(dts, dop, dcl, w, DEV_START, band=0.02, slippage_bps=1.0)
    return _daily_equity(r)


def main() -> None:
    """Development-window evaluation. Not run while backtests are paused."""
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    weights, info = build_weights(ts, opens, closes)

    windows: dict[str, dict] = {}
    result_1bp = None
    for slip in (1.0, 5.0, 10.0):
        result = bt.run(
            ts, opens, closes, weights, DEV_START, band=0.02, slippage_bps=slip
        )
        s = bt.stats(result, BARS_PER_YEAR)
        key = f"{int(slip)}bp"
        windows[key] = {
            k: float(s[k])
            for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")
        }
        if slip == 1.0:
            result_1bp = result

    corr = None
    if result_1bp is not None:
        strat_daily = _daily_equity(result_1bp).pct_change()
        base_daily = _baseline_daily().pct_change()
        both = pd.concat([strat_daily, base_daily], axis=1).dropna()
        corr = float(both.corr().iloc[0, 1])

    dts, dop, dcl = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1D")
    i0 = bt.start_index(dts, DEV_START)
    tqqq = bt.benchmark(dcl[i0:, 1], dts[i0:], 252)
    qqq = bt.benchmark(dcl[i0:, 0], dts[i0:], 252)

    original = None
    orig_path = ROOT / "research" / "agents" / "intraday-momentum" / "result.json"
    if orig_path.exists():
        try:
            original = json.loads(orig_path.read_text(encoding="utf-8"))
        except Exception:
            original = None

    out = {
        "agent": "intraday-momentum",
        "original": "research/agents/intraday-momentum",
        "status": "pending",  # lead updates to passed / retired_overlay_only / rejected
        "idea": (
            "A weekly three-state leverage ladder on the Nasdaq-100: 3x TQQQ when "
            "the overnight-minus-intraday spread and the first-hour return are both "
            "above their 26-week medians, 1x QQQ when only one is, and BIL otherwise."
        ),
        "hypothesis": (
            "Weeks with an unusually strong overnight-vs-intraday spread and first-hour "
            "momentum have a stronger time-of-day drift; a 3x/1x/0x ladder should beat "
            "static QQQ/TQQQ on a risk-adjusted basis with low correlation to the 165-day "
            "price-trend base."
        ),
        "universe": ["QQQ", "TQQQ", "BIL"],
        "frozen_commit": None,
        "variants_tried": 7,
        "corr_vs_165d_baseline": corr,
        "max_corr_vs_other_rebuilds": None,
        "windows": {
            "dev": windows,
            "holdout": None,
            "10y": None,
            "5y": None,
        },
        "marks": "1m",
        "benchmarks": {
            "tqqq": {k: float(tqqq[k]) for k in ("cagr", "max_drawdown", "sharpe")},
            "qqq": {k: float(qqq[k]) for k in ("cagr", "max_drawdown", "sharpe")},
            "spy": None,
            "spy_note": "No local SPY daily history in data/intraday-hf; needs the data subagent.",
            "original": original,
        },
        "diagnostics": {
            "params": info["params"],
            "sessions": info["sessions"],
            "rebalances": info["rebalances"],
            "first_rebalance": info["first_rebalance"],
            "state_counts": info["state_counts"],
        },
    }

    out_path = ROOT / "research" / "revisit" / "intraday-momentum" / "result.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    for key, row in windows.items():
        print(
            f"{key}: CAGR {row['cagr']*100:6.2f}%  DD {row['max_drawdown']*100:5.2f}%  "
            f"Sharpe {row['sharpe']:4.2f}  fills {int(row['fills'])}"
        )
    print(f"corr vs 165d baseline: {corr}")
    print(f"states: {info['state_counts']}, first rebalance {info['first_rebalance']}")


if __name__ == "__main__":
    main()
