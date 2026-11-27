"""Engine v2: correct regime mapping + stop overlays that block same-day re-entry."""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS_PER_YEAR = 252 * 78
CACHE = Path(__file__).with_name("panel5.pkl")


def load_panel(rule: str = "5min"):
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, rule)
    qqq = c[:, 0]
    date = pd.Series(ts.date)
    bars = date.groupby(date).cumcount().to_numpy()
    last_bar = int(bars.max())

    raw = bt.load_1m("QQQ").set_index("ts")
    if rule == "5min":
        agg = raw.resample("5min", origin="start_day").agg(
            {"volume": "sum", "high": "max", "low": "min"})
        agg = agg.reindex(ts)
        vol = np.nan_to_num(agg["volume"].to_numpy())
        hi = agg["high"].to_numpy()
        lo = agg["low"].to_numpy()
    else:
        vol, hi, lo = raw["volume"].to_numpy(), raw["high"].to_numpy(), raw["low"].to_numpy()

    d = pd.DataFrame({"d": date, "pv": qqq * vol, "v": vol, "tp": (hi + lo + qqq) / 3.0})
    cs = d.groupby("d")[["pv", "v"]].cumsum()
    twap = d.groupby("d")["tp"].cumsum() / (d.groupby("d").cumcount() + 1)
    vwap = cs["pv"].to_numpy() / cs["v"].to_numpy()
    dev_vwap = qqq / vwap - 1.0
    dev_twap = qqq / twap.to_numpy() - 1.0

    def rsi(k):
        dd = np.diff(qqq, prepend=qqq[0])
        au = pd.Series(np.where(dd > 0, dd, 0.0)).ewm(alpha=1 / k, adjust=False).mean().to_numpy()
        ad = pd.Series(np.where(dd < 0, -dd, 0.0)).ewm(alpha=1 / k, adjust=False).mean().to_numpy()
        return 100 * au / np.where(au + ad > 0, au + ad, np.nan)

    s = pd.Series(qqq)
    m20 = s.rolling(20).mean().to_numpy()
    sd20 = s.rolling(20).std(ddof=0).to_numpy()
    z20 = (qqq - m20) / np.where(sd20 > 0, sd20, np.nan)

    tsd, _, cd = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1D")
    qd = cd[:, 0]
    dd = pd.DataFrame({"c": qd}, index=pd.Index([t.date() for t in tsd]))
    sma = dd["c"].rolling(165).mean()
    reg = (dd["c"] > sma).astype(float)
    dlist = date.to_numpy()
    reg_today = np.array([reg.to_dict().get(x, 0.0) for x in dlist], dtype=float)
    reg_prev = np.array([reg.shift(1).to_dict().get(x, 0.0) for x in dlist], dtype=float)
    # weight that will be executed at the NEXT bar's open
    reg_next = np.where(bars == last_bar, reg_today, reg_prev)

    # previous daily closes
    lastq = pd.Series(qqq).groupby(dlist).last()
    lastt = pd.Series(c[:, 1]).groupby(dlist).last()
    qpc = np.array([lastq.shift(1).to_dict().get(x, np.nan) for x in dlist])
    tpc = np.array([lastt.shift(1).to_dict().get(x, np.nan) for x in dlist])
    dopen = pd.Series(qqq).groupby(dlist).transform("first").to_numpy()

    feats = dict(date=dlist, bars=bars, last_bar=last_bar, rsi2=rsi(2), rsi5=rsi(5), z20=z20,
                 dev_vwap=dev_vwap, dev_twap=dev_twap, regime=reg_next, regime_prev=reg_prev,
                 regime_today=reg_today, qqq=qqq, tqqq=c[:, 1], vol=vol, qpc=qpc, tpc=tpc, dopen=dopen)
    return ts, o, c, feats


def load_cached():
    if CACHE.exists():
        return pickle.loads(CACHE.read_bytes())
    ts, o, c, feats = load_panel("5min")
    CACHE.write_bytes(pickle.dumps((ts, o, c, feats)))
    return ts, o, c, feats


def make_weights(feats, o, n, p):
    date, bars, last_bar = feats["date"], feats["bars"], feats["last_bar"]
    rsi2, rsi5, z20 = feats["rsi2"], feats["rsi5"], feats["z20"]
    dev = feats["dev_vwap"]
    reg = feats["regime"]
    qqq, tqqq = feats["qqq"], feats["tqqq"]
    qpc, tpc = feats["qpc"], feats["tpc"]
    dopen = feats["dopen"]

    if p["signal"] == "rsi2":
        ent, ext = rsi2 < p["entry"], rsi2 > p["exit"]
    elif p["signal"] == "rsi5":
        ent, ext = rsi5 < p["entry"], rsi5 > p["exit"]
    elif p["signal"] == "boll":
        ent, ext = z20 < p["entry"], z20 > p["exit"]
    elif p["signal"] == "vwap":
        ent, ext = dev < p["entry"], dev > p["exit"]
    else:
        ent = np.zeros(n, bool)
        ext = np.zeros(n, bool)

    w = np.zeros((n, 3))
    pos = 0.0          # current weight in TQQQ (0..1)
    entry_px = np.nan
    held = 0
    blocked = None     # date blocked by a stop
    peak_px = np.nan
    max_held = p.get("max_bars", 10 ** 9)
    stop_pnl = p.get("stop_pnl", np.inf)      # on TQQQ position P&L
    trail = p.get("trail", np.inf)            # on TQQQ giveback from peak
    stop_prev = p.get("stop_prev", np.inf)    # on QQQ move from prior close
    eod = p.get("eod_flat", False)
    base = p.get("base", 0.0)
    risk_off_w = p.get("risk_off_w", 0.0)
    reentry = p.get("reentry", None)          # rsi2 threshold to re-enter same day after stop

    for i in range(n - 1):
        d = date[i]
        nb = i + 1
        in_reg = reg[i] > 0.5
        # ---------------- flat / entry decisions
        if pos <= 0:
            target = 0.0
            if in_reg:
                if blocked == d and not (reentry is not None and rsi2[i] < reentry):
                    target = 0.0
                elif eod and bars[i] >= last_bar - 1:
                    target = 0.0
                elif base > 0:
                    target = 1.0
                elif ent[i]:
                    target = 1.0
                elif reentry is not None and rsi2[i] < reentry:
                    target = 1.0
            if target > 0 and pos <= 0:
                pos = target
                entry_px = tqqq[nb]
                peak_px = entry_px
                held = 1
            w[i, 0] = 0.0
            w[i, 1] = target
            w[i, 2] = 1.0 - target
            continue

        # ---------------- in position
        pnl = tqqq[i] / entry_px - 1.0 if np.isfinite(entry_px) else 0.0
        peak_px = max(peak_px, tqqq[i]) if np.isfinite(peak_px) else tqqq[i]
        giveback = tqqq[i] / peak_px - 1.0
        move_prev = qqq[i] / qpc[i] - 1.0 if np.isfinite(qpc[i]) else 0.0
        at_eod = eod and bars[i] >= last_bar - 1
        hit = (pnl <= -stop_pnl) or (giveback <= -trail) or (move_prev <= -stop_prev) or (held >= max_held)
        do_exit = hit or ext[i] or at_eod or (not in_reg)
        if do_exit:
            if hit:
                blocked = d
            w[i, 1] = risk_off_w
            w[i, 2] = 1.0 - risk_off_w
            pos = risk_off_w
            if risk_off_w <= 0:
                entry_px, peak_px, held = np.nan, np.nan, 0
            else:
                entry_px, peak_px, held = tqqq[nb], tqqq[nb], 1
        else:
            w[i, 1] = pos
            w[i, 2] = 1.0 - pos
            held += 1
    w[-1] = (0.0, 0.0, 1.0)
    return w


def run_one(ts, o, c, feats, p, slip=1.0, label="", verbose=True):
    w = make_weights(feats, o, len(ts), p)
    out = {}
    for start, key in ((START10, "10y"), (START5, "5y")):
        res = bt.run(ts, o, c, w, start, band=0.0, slippage_bps=slip)
        s = bt.stats(res, BARS_PER_YEAR)
        i0 = bt.start_index(ts, start)
        b = bt.benchmark(c[i0:, 1], ts[i0:], 252)
        out[key] = dict(stats=s, bench=b, res=res)
        if verbose:
            print(f"  {key} {slip:.0f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
                  f"Sharpe {s['sharpe']:4.2f} fills {s['fills']:5d} turn {s['turnover']:7.0f}x")
    return out, w
