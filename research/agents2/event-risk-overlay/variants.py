"""Event-overlay variants on the round-1 winner."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import cal  # noqa: E402
from explore import load_panel, baseline, START10, START5, BARS_PER_YEAR  # noqa: E402

# event sets (ex-ante)
EV = {
    "fomc": set(cal.FOMC_DATES),
    "cpi": set(cal.CPI_DATES),
    "nfp": set(cal.NFP_DATES),
    "opex": set(cal.opex_dates(2016, 2027)),
    "preh": set(cal.pre_holiday_dates(2016, 2027)),
}


def overlay(ts, w_base, meta, events, asset="bil", frac=0.0, overnight=False,
            weak_only=False, intraday_only_fomc=False):
    """Return new weights with TQQQ exposure replaced on `events` days.

    frac   : TQQQ fraction kept (0 = all out, 0.5 = half).
    asset  : where the released exposure goes ('bil' or 'qqq').
    overnight: also be flat from the prior session's 15:59 print.
    weak_only: act only when QQQ's close 2 sessions back is below its 20-day SMA.
    """
    w = w_base.copy()
    dates = meta["dates"][meta["first"]]
    first, last = meta["first"], meta["last"]
    dclose, ma20 = meta["dclose"], meta["ma20"]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    n_out = 0
    for k, d in enumerate(dates):
        if d not in events:
            continue
        if weak_only:
            prev = k - 1
            if prev < 0 or not np.isfinite(ma20_prev[prev]) or not (dclose[prev] < ma20_prev[prev]):
                continue
        f, l = first[k], last[k]
        if l - f < 5:
            continue
        if intraday_only_fomc:
            # de-risk 13:30 -> 15:30 only (covers 14:00 statement + presser)
            mins = np.array([t.hour * 60 + t.minute for t in ts[f:l + 1]])
            lo = np.searchsorted(mins, 13 * 60 + 30)
            hi = np.searchsorted(mins, 15 * 60 + 30)
            s, e = f + max(lo - 1, 0), f + hi
        else:
            s = (last[k - 1] - 1) if overnight and k > 0 else f
            e = l - 1
        if e <= s:
            continue
        hold = w[s:e, 1].copy()
        w[s:e, 1] = hold * frac
        if asset == "qqq":
            w[s:e, 0] = hold * (1.0 - frac)
        w[s:e, 2] = 1.0 - w[s:e, 1] - w[s:e, 0]
        n_out += 1
    return w, n_out


def metrics(ts, opens, closes, w, start, slip=1.0):
    r = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    s["bench"] = bt.benchmark(closes[i:, 1], ts[i:], BARS_PER_YEAR)
    s["yearly"] = bt.yearly(ts[i:], r["equity"], closes[i:, 1])
    peak = np.maximum.accumulate(r["equity"])
    dd = r["equity"] / peak - 1.0
    j = int(np.argmin(dd))
    p = int(np.argmax(r["equity"][: j + 1]))
    s["dd_peak"] = str(ts[i:][p].date())
    s["dd_trough"] = str(ts[i:][j].date())
    s["equity"] = r["equity"]
    s["ts"] = ts[i:]
    return s


def show(label, s10, s5):
    print(f"{label:46s} 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.2f}  "
          f"5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.2f}  "
          f"fills {s10['fills']:4d}  DD {s10['dd_peak']}->{s10['dd_trough']}")


def main():
    ts, opens, highs, lows, closes, vols = load_panel()
    w0, meta = baseline(ts, opens, closes)
    b10, b5 = metrics(ts, opens, closes, w0, START10), metrics(ts, opens, closes, w0, START5)
    show("baseline winner", b10, b5)

    all_ev = EV["fomc"] | EV["cpi"] | EV["nfp"]
    tests = [
        ("opex bil", dict(events=EV["opex"], asset="bil", frac=0.0)),
        ("opex qqq", dict(events=EV["opex"], asset="qqq", frac=0.0)),
        ("opex half qqq", dict(events=EV["opex"], asset="qqq", frac=0.5)),
        ("opex half tqqq", dict(events=EV["opex"], asset="qqq", frac=0.0)),
        ("opex bil overnight", dict(events=EV["opex"], asset="bil", frac=0.0, overnight=True)),
        ("opex bil weak-only", dict(events=EV["opex"], asset="bil", frac=0.0, weak_only=True)),
        ("fomc bil full day", dict(events=EV["fomc"], asset="bil", frac=0.0)),
        ("fomc qqq 13:30-15:30", dict(events=EV["fomc"], asset="qqq", frac=0.0, intraday_only_fomc=True)),
        ("cpi bil full day", dict(events=EV["cpi"], asset="bil", frac=0.0)),
        ("nfp bil full day", dict(events=EV["nfp"], asset="bil", frac=0.0)),
        ("preh bil full day", dict(events=EV["preh"], asset="bil", frac=0.0)),
        ("all macro (fomc+cpi+nfp) qqq", dict(events=all_ev, asset="qqq", frac=0.0)),
        ("ALL 5 events qqq (control)", dict(events=all_ev | EV["opex"] | EV["preh"], asset="qqq", frac=0.0)),
    ]
    for label, kw in tests:
        w, n = overlay(ts, w0, meta, **kw)
        s10 = metrics(ts, opens, closes, w, START10)
        s5 = metrics(ts, opens, closes, w, START5)
        show(f"{label} (n={n})", s10, s5)

    print("\n--- cost sensitivity for the candidates ---")
    for label, kw in [("opex bil", dict(events=EV["opex"], asset="bil", frac=0.0)),
                      ("opex qqq", dict(events=EV["opex"], asset="qqq", frac=0.0)),
                      ("opex half qqq", dict(events=EV["opex"], asset="qqq", frac=0.5))]:
        w, _ = overlay(ts, w0, meta, **kw)
        for slip in (5.0, 10.0):
            s10 = metrics(ts, opens, closes, w, START10, slip)
            s5 = metrics(ts, opens, closes, w, START5, slip)
            show(f"{label} @{slip:.0f}bp", s10, s5)


if __name__ == "__main__":
    main()
