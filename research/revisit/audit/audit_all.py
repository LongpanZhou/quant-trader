"""Audit every revisit strategy and test it on ten years of 1-minute bars.

    python research/revisit/audit/audit_all.py            # all 26
    python research/revisit/audit/audit_all.py --only a,b  # some
    python research/revisit/audit/audit_all.py --skip-run  # re-check cached captures

For each strategy (see worker.py for how the headline is captured):

  engine      the headline weights replayed through bt.simulate (compiled) and
              bt.simulate_python (reference loop) give the same equity, and
              the replay reproduces result.json's dev 1bp CAGR / drawdown
  settings    band 2%, slippage 1 bp, start equity 100k on the headline call
  bars        the simulation runs on 1-minute bars (median step 60 s) whose
              timestamps are exactly the bt.panel 1-minute panel
  prices      the opens/closes fed to the engine are the real QQQ/TQQQ/BIL
              1-minute prices (no synthetic or shifted columns)
  weights     finite, non-negative, total <= 100% (no hidden leverage)
  look-ahead  rebuilding the strategy with data through 2026-10-23 leaves
              every weight on the dev window (2016-01-04 .. 2023-12-29)
              unchanged: nothing before a date depends on data after it
  10y / 5y    the full-data weights run 2017-01-03 / 2021-10-25 -> 2026-10-23
              on 1-minute bars at 1, 5 and 10 bp

Writes research/revisit/audit/audit.json and audit/report.md.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "research" / "revisit"
AUD = HERE / "audit"
CACHE = AUD / "cache"
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
from run_all import RUNS, load_timings  # noqa: E402

BARS = 252 * 390
SYMS = ("QQQ", "TQQQ", "BIL")
PANEL_START, PANEL_END = "2016-01-04", "2026-10-23"
DEV_END_TS = pd.Timestamp("2023-12-30", tz="America/New_York")
WINDOWS = {"10y": "2017-01-03", "5y": "2021-10-25"}
SLIPS = (1.0, 5.0, 10.0)

# Cut-test results that need a human reading, each checked in the code:
CUT_ARTIFACTS = {
    "opening-range-breakout": (
        "cut2 differences (10:18-10:31) come from entry_cutoff_bars=30 counted back from the "
        "last bar in the data: with data stopping at 10:41 the run thinks the session ends "
        "there. Live, the session end (15:59) is known from the clock, so this is not "
        "look-ahead."),
}


def run_workers(slugs, mode, jobs):
    timings = load_timings()
    slugs = sorted(slugs, key=lambda s: -timings.get(s, 1e9))
    threads = str(max(1, (os.cpu_count() or 1) // jobs))
    env = {**os.environ, "BT_THREADS": threads, "PYTHONIOENCODING": "utf-8"}
    (AUD / "logs").mkdir(parents=True, exist_ok=True)

    def one(slug):
        for attempt in (1, 2):
            log = AUD / "logs" / f"{slug}-{mode}.log"
            with log.open("w", encoding="utf-8") as fh:
                rc = subprocess.run([sys.executable, str(AUD / "worker.py"), slug, mode],
                                    cwd=ROOT, env=env, stdout=fh,
                                    stderr=subprocess.STDOUT).returncode
            if rc == 0:
                break
        return slug, rc, attempt

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = [pool.submit(one, s) for s in slugs]
        for i, f in enumerate(as_completed(futs), 1):
            slug, rc, attempt = f.result()
            note = "" if attempt == 1 else f" (attempt {attempt})"
            print(f"  [{i:2d}/{len(slugs)}] {mode:4s} {slug:28s} "
                  f"{'ok' if rc == 0 else f'FAILED rc={rc}'}{note}", flush=True)
    print(f"  {mode}: {time.perf_counter() - t0:.0f}s", flush=True)


def load_capture(slug, mode):
    meta_p = CACHE / f"{slug}-{mode}.json"
    if not meta_p.exists():
        return None, None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if not meta.get("found"):
        return meta, None
    z = np.load(CACHE / f"{slug}-{mode}.npz")
    ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True)).tz_convert("America/New_York")
    return meta, (ts, z["opens"], z["closes"], z["weights"])


def to_minutes(ts_c, w_c, ts1):
    """Hold a coarse-bar weight on every minute until the next coarse bar.

    A coarse weight set at bar t's close is filled at bar t+1's open; on the
    minute panel it is assigned to the last minute inside bar t, so the minute
    engine fills it at the first minute of bar t+1: the same fill time.
    """
    pos = np.searchsorted(ts_c.asi8, ts1.asi8, side="right") - 1  # coarse bar containing minute
    nxt = np.r_[pos[1:], pos[-1] + 1]
    src = np.where(nxt != pos, pos, pos - 1)
    w = np.empty((len(ts1), w_c.shape[1]))
    ok = src >= 0
    w[ok] = w_c[src[ok]]
    w[~ok] = (0.0, 0.0, 1.0)
    return w


def check(slug, P):
    ts1, op1, cl1 = P
    out = {"slug": slug, "issues": [], "notes": []}
    issues, notes = out["issues"], out["notes"]
    dmeta, dev = load_capture(slug, "dev")
    fmeta, full = load_capture(slug, "full")
    res = json.loads((HERE / slug / "result.json").read_text(encoding="utf-8"))
    out["status"] = res.get("status")
    stored = res["windows"]["dev"]["1bp"]
    if dev is None:
        issues.append(f"dev headline not captured ({(dmeta or {}).get('error')})")
        return out
    ts, op, cl, w = dev
    kw = dmeta["kw"]

    # settings
    out["settings"] = kw
    if abs(kw["band"] - 0.02) > 1e-12 or abs(kw["slippage_bps"] - 1.0) > 1e-12:
        issues.append(f"headline run uses band {kw['band']} / slippage {kw['slippage_bps']} bp")
    if abs(kw["start_equity"] - bt.START_EQUITY) > 1e-6:
        notes.append(f"start equity {kw['start_equity']}")

    # bars
    step = float(np.median(np.diff(ts.asi8))) / 1e9
    out["bar_seconds"] = step
    sub = ts1[(ts1 >= ts[0]) & (ts1 <= ts[-1])]
    minute = step == 60.0 and len(sub) == len(ts) and np.array_equal(sub.asi8, ts.asi8)
    out["native_1m"] = bool(minute)
    if not minute:
        notes.append(f"simulated on {step/60:g}-minute bars; re-marked on 1-minute bars below")

    # prices: each column must be one real symbol's open/close on those bars
    cols = []
    if minute:
        i0 = int(np.searchsorted(ts1.asi8, ts.asi8[0]))
        ro, rc = op1[i0:i0 + len(ts)], cl1[i0:i0 + len(ts)]
        for j in range(w.shape[1]):
            hit = [s for s in range(3) if np.allclose(op[:, j], ro[:, s], rtol=1e-12, atol=0)
                   and np.allclose(cl[:, j], rc[:, s], rtol=1e-12, atol=0)]
            cols.append(SYMS[hit[0]] if hit else None)
    else:
        sel = pd.DatetimeIndex(ts)
        ref = bt.panel(SYMS, PANEL_START, PANEL_END, f"{int(step // 60)}min"
                       if step < 86400 else "1D")
        idx = ref[0].get_indexer(sel)
        if (idx < 0).any():
            issues.append(f"{(idx < 0).sum()} coarse bars not in the bt.panel grid")
        else:
            for j in range(w.shape[1]):
                hit = [s for s in range(3)
                       if np.allclose(op[:, j], ref[1][idx, s], rtol=1e-12, atol=0)
                       and np.allclose(cl[:, j], ref[2][idx, s], rtol=1e-12, atol=0)]
                cols.append(SYMS[hit[0]] if hit else None)
    out["columns"] = [c or "synthetic" for c in cols]
    real = [c for c in cols if c]
    if len(set(real)) != len(real):
        issues.append(f"duplicate price columns {cols}")
    syn = [j for j, c in enumerate(cols) if c is None]
    if syn:
        # Synthetic short legs (inverse series built from real prices) reset
        # every session, so a position held across a close would book a fake
        # jump. The weight on each session's last bar (filled at the next
        # open) must therefore be zero.
        day = ts.tz_convert("America/New_York").normalize().asi8
        last_bar = np.r_[day[1:] != day[:-1], True]
        held = (w[last_bar][:, syn] > 1e-12).any(axis=1).sum()
        notes.append(f"synthetic short column(s) {syn}; held overnight on {int(held)} sessions")
        if held:
            issues.append(f"synthetic short held overnight on {int(held)} sessions")

    # weights
    wsum = w.sum(axis=1)
    if not np.isfinite(w).all():
        issues.append("non-finite weights")
    if (w < -1e-12).any():
        issues.append(f"negative weights on {int((w < -1e-12).any(axis=1).sum())} bars")
    if (wsum > 1 + 1e-9).any():
        issues.append(f"weights sum above 100% on {int((wsum > 1 + 1e-9).sum())} bars "
                      f"(max {wsum.max():.3f})")
    out["exposure"] = {s: float(w[:, j].mean()) for j, s in enumerate(cols) if s}

    # engine: compiled vs reference loop, and reproduces result.json
    a = bt.simulate(ts, op, cl, w, band=kw["band"], slippage_bps=kw["slippage_bps"],
                    start_equity=kw["start_equity"])
    b = bt.simulate_python(ts, op, cl, w, band=kw["band"], slippage_bps=kw["slippage_bps"],
                           start_equity=kw["start_equity"])
    rel = float(np.max(np.abs(a["equity"] / b["equity"] - 1)))
    out["engine_maxrel"] = rel
    if rel > 1e-9 or abs(a["fills"] - b["fills"]) > 1:
        issues.append(f"compiled engine differs from reference (maxrel {rel:.2e}, "
                      f"fills {a['fills']} vs {b['fills']})")
    elif a["fills"] != b["fills"]:
        notes.append(f"engines agree on equity (maxrel {rel:.1e}); fill count {a['fills']} vs "
                     f"{b['fills']} from a zero-size trade at a float tie")
    s = bt.stats(a, BARS)
    out["dev_repro"] = {"cagr": s["cagr"], "stored": stored["cagr"]}
    if abs(s["cagr"] - stored["cagr"]) > 1e-6 or abs(s["max_drawdown"] - stored["max_drawdown"]) > 1e-6:
        issues.append("replay does not reproduce result.json dev numbers")
    if ts[-1] < pd.Timestamp("2023-12-29 15:00", tz="America/New_York"):
        notes.append(f"dev run ends {ts[-1]:%Y-%m-%d %H:%M}, before the 2023-12-29 session")

    # intraday cut tests: same-session look-ahead
    out["cuts"] = {}
    for cut in ("cut1", "cut2"):
        cmeta, cap = load_capture(slug, cut)
        if cap is None:
            issues.append(f"{cut}: truncated run not captured ({(cmeta or {}).get('error')}, "
                          f"best overlap {(cmeta or {}).get('match_score')})")
            continue
        cts, _, _, cw = cap
        m = len(cts)
        diff = ~np.all(np.isclose(cw[:m], w[:m], rtol=0, atol=1e-12), axis=1)
        tail_only = not diff[:max(m - 2, 0)].any()
        out["cuts"][cut] = {"end": f"{cts[-1]:%Y-%m-%d %H:%M}", "bars": int(m),
                            "diff_bars": int(diff.sum()), "clean": bool(tail_only)}
        if not tail_only and slug in CUT_ARTIFACTS:
            notes.append(f"{cut}: {CUT_ARTIFACTS[slug]}")
        elif not tail_only:
            bad = np.flatnonzero(diff[:m - 2])
            issues.append(f"LOOK-AHEAD ({cut}, data to {cts[-1]:%Y-%m-%d %H:%M}): {len(bad)} earlier "
                          f"bars change, first {cts[bad[0]]:%Y-%m-%d %H:%M}, last {cts[bad[-1]]:%Y-%m-%d %H:%M}")
        elif diff.any():
            notes.append(f"{cut}: only the last {int(diff.sum())} bar(s) before the cut differ (end-of-data)")

    # Strategies whose main() cannot run on truncated data are cut-tested by
    # calling their weight builder directly (cut_direct.py).
    direct = [r for r in DIRECT if r["slug"] == slug]
    if direct:
        res_ok = all(v["diff_before_last2"] == 0 for r in direct for v in r["result"].values())
        cuts = sorted({r["cut"] for r in direct})
        out["cuts_direct"] = direct
        issues[:] = [i for i in issues if not i.startswith(("cut1:", "cut2:", "LOOK-AHEAD (cut"))]
        if res_ok:
            notes.append(f"cut-tested directly (cut_direct.py) at {', '.join(cuts)}: all weights "
                         "before each cut identical")
        else:
            issues.append("LOOK-AHEAD in direct cut test (see cut_direct.json)")

    # look-ahead + full
    if full is None:
        issues.append(f"full-data headline not captured ({(fmeta or {}).get('error')}, "
                      f"best overlap {(fmeta or {}).get('match_score')})")
        return out
    fts, fop, fcl, fw = full
    n = len(ts)
    same = np.all(np.isclose(fw[:n], w, rtol=0, atol=1e-12), axis=1)
    # The final dev bar's weight would fill at the next session's open, which
    # the dev run does not have, so it never trades: exclude it.
    same[-1] = True
    px_same = (np.allclose(fop[:n], op, rtol=1e-12, atol=0)
               and np.allclose(fcl[:n], cl, rtol=1e-12, atol=0))
    if not px_same:
        issues.append("LOOK-AHEAD: engine prices on the dev window change when 2024-2026 data is added")
    out["lookahead_identical_share"] = float(same.mean())
    if not same.all():
        bad = np.flatnonzero(~same)
        issues.append(f"LOOK-AHEAD: {len(bad)} dev bars change when 2024-2026 data is added "
                      f"(first {fts[bad[0]]:%Y-%m-%d %H:%M}, last {fts[bad[-1]]:%Y-%m-%d %H:%M})")
    out["full_end"] = f"{fts[-1]:%Y-%m-%d %H:%M}"
    if fts[-1] < pd.Timestamp("2026-10-22", tz="America/New_York"):
        issues.append(f"full run stops at {fts[-1]:%Y-%m-%d}")
    fwsum = fw.sum(axis=1)
    if not np.isfinite(fw).all() or (fw < -1e-12).any() or (fwsum > 1 + 1e-9).any():
        issues.append("full-data weights invalid (non-finite, negative or > 100%)")
    tail = fw[n:]
    out["post_dev_exposure"] = float(1 - tail[:, 2].mean()) if fw.shape[1] == 3 else None
    if len(tail) and np.all(tail == tail[0]):
        notes.append(f"no position changes after 2023 (constant weights {tail[0].round(3).tolist()})")

    # 10y / 5y on 1-minute bars: replay the full-data capture (its own price
    # columns, so synthetic legs are included); coarse captures are re-marked.
    if minute:
        rts, rop, rcl, rw = fts, fop, fcl, fw
        j0 = int(np.searchsorted(ts1.asi8, fts.asi8[0]))
        sub1 = ts1[j0:j0 + len(fts)]
        if len(sub1) != len(fts) or not np.array_equal(sub1.asi8, fts.asi8):
            issues.append("full run timestamps are not the 1-minute panel")
        else:
            for j, c in enumerate(cols):
                if c and not (np.allclose(fop[:, j], op1[j0:j0 + len(fts), SYMS.index(c)], rtol=1e-12, atol=0)
                              and np.allclose(fcl[:, j], cl1[j0:j0 + len(fts), SYMS.index(c)], rtol=1e-12, atol=0)):
                    issues.append(f"full run column {j} is not real {c} prices after 2023")
        if fts[0].date() > pd.Timestamp(WINDOWS["10y"]).date():
            issues.append(f"full run starts {fts[0]:%Y-%m-%d}, after the 10y start")
    else:
        rts, rop, rcl, rw = ts1, op1, cl1, to_minutes(fts, fw, ts1)
    out["windows"] = {}
    for label, start in WINDOWS.items():
        rs = [bt.run(rts, rop, rcl, rw, start, band=0.02, slippage_bps=sl) for sl in SLIPS]
        out["windows"][label] = {
            f"{int(sl)}bp": {k: float(v) for k, v in bt.stats(r, BARS).items()
                             if k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover", "exposure")}
            for sl, r in zip(SLIPS, rs)}
    return out


DIRECT = []


def main():
    global DIRECT
    p_direct = AUD / "cut_direct.json"
    DIRECT = json.loads(p_direct.read_text(encoding="utf-8")) if p_direct.exists() else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    ap.add_argument("--skip-run", action="store_true")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    slugs = [s for s in RUNS if not only or s in only]

    if not args.skip_run:
        print("capturing dev headlines", flush=True)
        run_workers(slugs, "dev", args.jobs)
        print("re-running on full 2016-2026 data", flush=True)
        run_workers(slugs, "full", args.jobs)
        for cut in ("cut1", "cut2"):
            print(f"re-running with data cut intraday ({cut})", flush=True)
            run_workers(slugs, cut, args.jobs)

    P = bt.panel(SYMS, PANEL_START, PANEL_END, "1min", warmup_days=0)
    print(f"1-minute panel {len(P[0]):,} bars {P[0][0]:%Y-%m-%d} .. {P[0][-1]:%Y-%m-%d}")
    bench = {}
    for label, start in WINDOWS.items():
        j = bt.start_index(P[0], start)
        bench[label] = {sym: bt.benchmark(P[2][j:, c], P[0][j:], BARS)
                        for c, sym in ((0, "QQQ"), (1, "TQQQ"))}
    results = []
    for slug in slugs:
        try:
            r = check(slug, P)
        except Exception as e:
            r = {"slug": slug, "issues": [f"audit crashed: {type(e).__name__}: {e}"], "notes": []}
        results.append(r)
        ten = (r.get("windows") or {}).get("10y", {}).get("1bp")
        print(f"{slug:28s} {'OK ' if not r['issues'] else 'ISSUE'} "
              f"{'' if not ten else f'10y CAGR {ten['cagr']*100:6.2f}%  DD {ten['max_drawdown']*100:5.1f}%'}",
              flush=True)
        for i in r["issues"]:
            print("    !", i)
        for i in r["notes"]:
            print("    -", i)

    payload = {"generated": str(pd.Timestamp.now().date()),
               "panel": [f"{P[0][0]:%Y-%m-%d}", f"{P[0][-1]:%Y-%m-%d}"],
               "benchmarks": {k: {s: {m: float(v[m]) for m in ("cagr", "max_drawdown", "sharpe")}
                                  for s, v in b.items()} for k, b in bench.items()},
               "strategies": results}
    if only:
        old = AUD / "audit.json"
        if old.exists():
            prev = {r["slug"]: r for r in json.loads(old.read_text(encoding="utf-8"))["strategies"]}
            prev.update({r["slug"]: r for r in results})
            payload["strategies"] = [prev[s] for s in RUNS if s in prev]
    (AUD / "audit.json").write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    write_report(payload)
    bad = [r["slug"] for r in payload["strategies"] if r["issues"]]
    print(f"\n{len(payload['strategies']) - len(bad)} clean, {len(bad)} with issues"
          + (f": {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


def write_report(p):
    L = ["# Revisit audit: all strategies, 1-minute bars, 2016-2026", "",
         f"Generated {p['generated']} by `research/revisit/audit/audit_all.py`. "
         f"Panel {p['panel'][0]} .. {p['panel'][1]}; 10y = 2017-01-03 ->, 5y = 2021-10-25 ->.",
         "Every run: next-bar-open fills, 2% band, 1 bp slippage (5/10 bp in audit.json).", "",
         "| strategy | status | bars | look-ahead | 10y CAGR | 10y DD | 5y CAGR | 5y DD | issues |",
         "|---|---|---|---|---:|---:|---:|---:|---|"]
    rows = []
    for r in p["strategies"]:
        w = r.get("windows") or {}
        t, f = w.get("10y", {}).get("1bp"), w.get("5y", {}).get("1bp")
        la = r.get("lookahead_identical_share")
        rows.append((t["cagr"] if t else -9, "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["slug"], r.get("status") or "", "1m" if r.get("native_1m") else
            (f"{r.get('bar_seconds', 0)/60:g}m -> 1m" if r.get("bar_seconds") else "?"),
            "clean" if la == 1.0 else ("?" if la is None else f"{(1-la)*100:.2f}% bars differ"),
            f"{t['cagr']*100:.2f}%" if t else "", f"{t['max_drawdown']*100:.1f}%" if t else "",
            f"{f['cagr']*100:.2f}%" if f else "", f"{f['max_drawdown']*100:.1f}%" if f else "",
            "; ".join(r["issues"]) or "none")))
    L += [row for _, row in sorted(rows, key=lambda x: -x[0])]
    L += ["", "Benchmarks (1-minute marks):", ""]
    for k, b in p["benchmarks"].items():
        for s, v in b.items():
            L.append(f"- {k} {s} buy & hold: CAGR {v['cagr']*100:.2f}%, DD {v['max_drawdown']*100:.1f}%")
    notes = [(r["slug"], n) for r in p["strategies"] for n in r.get("notes", [])]
    if notes:
        L += ["", "Notes:", ""] + [f"- {s}: {n}" for s, n in notes]
    (AUD / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
