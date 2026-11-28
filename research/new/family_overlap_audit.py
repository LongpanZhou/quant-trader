"""Audit all 20 new families against all nine existing winners.

Return-based: daily-return correlation and OLS alpha after the existing winner.
Signal-based: session-level TQQQ risk-on overlap (Jaccard) where weights can be
rebuilt from the local strategy modules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "research" / "new"
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
import run_holdout as R  # noqa: E402

NEW_SLUGS = [
    "family-close-location", "family-volume-skew", "family-vol-of-volume",
    "family-change-point", "family-hurst-persistence", "family-tqqq-decay",
    "family-realized-skew", "family-beta-rotation", "family-sector-rotation",
    "family-breadth", "family-crypto-risk-appetite", "family-rates-volatility",
    "family-energy-rotation", "family-oil-shock", "family-style-rotation",
    "family-yen-carry", "family-lowvol-rotation", "family-homebuilder-rotation",
    "family-financials-rotation", "family-retail-rotation",
]
EXISTING = [
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "fomc-opex-window", "family-session-timing", "family-short-reversal",
    "family-rebalance-flow", "family-intraday-microstructure-day",
    "family-ml-microstructure",
]


def curves():
    d = json.loads((ROOT / "web/public/data/compare/all.json").read_text(encoding="utf-8"))
    out = {}
    for s in d["series"]:
        v = pd.Series(s["values"], index=pd.to_datetime(d["dates"]))
        out[s["id"]] = v
    return out


def reg(y, x):
    df = pd.concat([y, x], axis=1, join="inner").dropna()
    r = df.iloc[:, 0].pct_change().dropna()
    m = df.iloc[:, 1].pct_change().reindex(r.index)
    X = np.column_stack([np.ones(len(r)), m.to_numpy()])
    b = np.linalg.lstsq(X, r.to_numpy(), rcond=None)[0]
    e = r.to_numpy() - X @ b
    s2 = e @ e / max(1, len(r) - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    return (float(b[0]), float(b[0] / np.sqrt(cov[0, 0])),
            float(np.corrcoef(r, m)[0, 1]), int(len(r)))


def daily_state(slug, ts, o, c):
    try:
        mod = R.load(slug)
        out = R.build_full(mod, ts, o, c)
        w = out[0] if isinstance(out, tuple) else out
        w = np.asarray(w, dtype=float)
        if w.shape[1] == 2:
            w = R.tqqq_bil_to_three(w, len(ts))
        if w.shape != (len(ts), 3):
            return None
        _, first, last = bt.day_bounds(ts)
        return w[last, 1] > 0.5
    except Exception as exc:
        print(f"weight skip {slug}: {exc}")
        return None


def main():
    cs = curves()
    rows = []
    for slug in NEW_SLUGS:
        best_corr = (-1, "")
        best_alpha = (-1, "")
        for ex in EXISTING:
            a, at, corr, n = reg(cs[slug], cs[ex])
            if abs(corr) > best_corr[0]:
                best_corr = (abs(corr), ex)
            if abs(a) > best_alpha[0]:
                best_alpha = (abs(a), ex)
            rows.append({"new": slug, "existing": ex, "alpha": a,
                         "alpha_t": at, "corr": corr, "n": n})

    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min", warmup_days=0)
    states = {}
    for slug in NEW_SLUGS + EXISTING:
        st = daily_state(slug, ts, o, c)
        if st is not None:
            states[slug] = st
    overlaps = []
    for slug in NEW_SLUGS:
        best = (-1, "")
        for ex in EXISTING:
            if slug not in states or ex not in states:
                continue
            a, b = states[slug], states[ex]
            j = float(np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum()))
            if j > best[0]:
                best = (j, ex)
        overlaps.append({"new": slug, "max_jaccard": best[0], "against": best[1]})

    summary = []
    for slug in NEW_SLUGS:
        rr = [r for r in rows if r["new"] == slug]
        ov = next(x for x in overlaps if x["new"] == slug)
        maxc = max(rr, key=lambda r: abs(r["corr"]))
        maxa = max(rr, key=lambda r: abs(r["alpha"]))
        summary.append({
            "new": slug, "max_corr": maxc["corr"], "corr_against": maxc["existing"],
            "max_alpha": maxa["alpha"] * 252.0, "alpha_t": maxa["alpha_t"],
            "alpha_against": maxa["existing"],
            "max_jaccard": ov["max_jaccard"], "overlap_against": ov["against"],
        })

    (NEW / "FAMILY_OVERLAP_AUDIT.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    lines = ["# Family overlap audit", "",
             "| New | Max corr | Against | Max alpha/yr | Alpha t | Jaccard | Against |",
             "|---|---:|---|---:|---:|---:|---|"]
    for s in sorted(summary, key=lambda x: -abs(x["max_corr"])):
        lines.append(f"| `{s['new']}` | {s['max_corr']:.2f} | `{s['corr_against']}` | "
                     f"{s['max_alpha']*100:+.2f}% | {s['alpha_t']:.2f} | "
                     f"{s['max_jaccard']:.2f} | `{s['overlap_against']}` |")
    (NEW / "FAMILY_OVERLAP_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s in summary:
        print(f"{s['new']:36s} corr {s['max_corr']:5.2f} {s['corr_against']:28s} "
              f"alpha {s['max_alpha']*100:6.2f}% t {s['alpha_t']:5.2f} "
              f"jaccard {s['max_jaccard']:5.2f}")


if __name__ == "__main__":
    main()
