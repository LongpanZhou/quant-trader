"""Idea (b) implementation test: 5-minute ratio-deviation fade as an overlay."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    n = len(ts)
    hold, risk_on_day, _, _ = L.winner_state(ts, opens, closes)

    day_id = np.repeat(np.arange(nd), np.diff(np.r_[first, n]))
    bar = np.arange(n) - first[day_id]
    prev_c = np.r_[np.nan, closes[last, 0][:-1]][day_id]
    prev_t = np.r_[np.nan, closes[last, 1][:-1]][day_id]
    dev = np.log(closes[:, 1] / prev_t) - 3.0 * np.log(closes[:, 0] / prev_c)

    ext = d["ext200"].shift(1).to_numpy()
    froth_day = np.nan_to_num(ext, nan=-9) > 0.18

    def base_weights(froth):
        tgt = np.zeros((nd, 3))
        tgt[risk_on_day & ~froth, 1] = 1
        tgt[risk_on_day & froth, 0] = 1
        tgt[~risk_on_day, 2] = 1
        return L.weights_from_daily(ts, tgt, first, last, stopped=~hold)

    wb = base_weights(froth_day)
    r = L.metrics(ts, opens, closes, wb)
    print("base froth-QQQ:", f"{r['cagr']*100:.2f}/{r['max_drawdown']*100:.2f}  fills {r['fills']}")

    for thr_bp, H in ((60, 5), (60, 15), (100, 5), (100, 15), (150, 10)):
        d5 = np.full(n, np.nan)
        d5[5:] = dev[5:] - dev[:-5]
        active = (bar >= 5) & np.isfinite(d5)
        pos = np.flatnonzero(active & (d5 > thr_bp / 1e4))
        neg = np.flatnonzero(active & (d5 < -thr_bp / 1e4))
        w = wb.copy()
        # positive deviation: TQQQ rich -> QQQ for H bars if holding TQQQ
        for i in pos:
            j = min(i + H, first[day_id[i]] + 389)
            if w[i, 1] > 0 and hold[i + 1:j + 2].all():
                w[i + 1:j + 2, :] = (1.0, 0.0, 0.0)
        # negative deviation: TQQQ cheap -> TQQQ for H bars if holding QQQ on a froth day
        for i in neg:
            j = min(i + H, first[day_id[i]] + 389)
            if w[i, 0] > 0 and hold[i + 1:j + 2].all():
                w[i + 1:j + 2, :] = (0.0, 1.0, 0.0)
        r2 = L.metrics(ts, opens, closes, w)
        print(f"fade {thr_bp:3d}bp H={H:2d}: {r2['cagr']*100:6.2f}/{r2['max_drawdown']*100:5.2f}  "
              f"fills {r2['fills']:6d}  events {len(pos)+len(neg)}")


if __name__ == "__main__":
    main()
