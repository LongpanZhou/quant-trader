"""Direct look-ahead cut test for strategies whose main() cannot run on
truncated data (their reporting code needs the whole dev window).

    python research/revisit/audit/cut_direct.py <slug> <cut>      # one cut
    python research/revisit/audit/cut_direct.py all                # every case

Builds the headline weights twice with the strategy's own code: once on the
normal dev data and once with every data source truncated at `cut` (see
worker.install_cut). Every weight before the cut must be identical; the last
two bars before the cut may differ (end-of-data handling).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import worker  # noqa: E402
from worker import bt, CACHE  # noqa: E402

SYMS = ("QQQ", "TQQQ", "BIL")
D0, D1 = "2016-01-04", "2023-12-29"


def load(slug):
    path = worker.HERE / slug / "strategy.py"
    spec = importlib.util.spec_from_file_location("cut_" + slug.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def time_of_day(mod):
    ts, op, cl = mod.load(mod.DEV_END)
    return ts, {"V3_full": mod.build_weights(ts, op, cl, mod.Params())[0],
                "V5_full_bil": mod.build_weights(ts, op, cl, mod.Params(idle="bil"))[0]}


def intraday_mean_reversion(mod):
    ts, o, c = bt.panel(SYMS, mod.DEV_START, mod.DEV_END, "1min")
    return ts, {"headline": mod.build_weights(ts, o, c, threshold=0.03, asset=1)[0]}


def winner_ensemble_blend(mod):
    ts, o, c = bt.panel(SYMS, mod.DEV_START, mod.DEV_END, "1min")
    return ts, {"headline": mod.build_weights(ts, o, c)[0]}


def drawdown_regime(mod):
    ts, o, c = bt.panel(SYMS, mod.DEV_START, mod.DEV_END, "1min", warmup_days=500)
    return ts, {"headline": mod.build_weights(ts, o, c)[0]}


BUILDERS = {
    "time-of-day": time_of_day,
    "intraday-mean-reversion": intraday_mean_reversion,
    "winner-ensemble-blend": winner_ensemble_blend,
    "drawdown-regime": drawdown_regime,
}
# Intraday cuts, plus session-boundary cuts for daily-decision strategies
# that need a complete daily bar for every session they see.
CASES = [(s, c) for s in BUILDERS for c in ("2020-03-12 11:07", "2022-09-13 10:41")
         if s != "drawdown-regime"] + [
    ("drawdown-regime", "2020-03-12 00:00"), ("drawdown-regime", "2022-09-13 00:00"),
    ("winner-ensemble-blend", "2020-03-12 00:00"), ("winner-ensemble-blend", "2022-09-13 00:00"),
]


def one(slug, cut):
    fn = BUILDERS[slug]
    out = {}
    tag = cut.replace(" ", "_").replace(":", "")
    ref = CACHE / f"direct-{slug}-ref.npz"
    if cut == "ref":
        ts, ws = fn(load(slug))
        np.savez(ref, ts=ts.as_unit("ns").asi8, **ws)
        print(json.dumps({"slug": slug, "ref": len(ts)}))
        return 0
    worker.install_cut(cut, slug + "-direct")
    try:
        ts, ws = fn(load(slug))
    finally:
        import shutil
        shutil.rmtree(bt.CACHE_DIR, ignore_errors=True)
    z = np.load(ref)
    n = len(ts)
    assert np.array_equal(z["ts"][:n], ts.as_unit("ns").asi8), "timestamps differ"
    for name, w in ws.items():
        diff = ~np.all(np.isclose(w, z[name][:n], rtol=0, atol=1e-12), axis=1)
        early = diff[:max(n - 2, 0)]
        out[name] = {"bars": n, "end": str(ts[-1]), "diff_total": int(diff.sum()),
                     "diff_before_last2": int(early.sum()),
                     "first_diff": str(ts[np.flatnonzero(early)[0]]) if early.any() else None}
    print(json.dumps({"slug": slug, "cut": cut, "result": out}))
    return 0


def main():
    if sys.argv[1] != "all":
        return one(sys.argv[1], sys.argv[2])
    env_cmd = [sys.executable, __file__]
    results = []
    for slug in BUILDERS:
        subprocess.run(env_cmd + [slug, "ref"], check=True, capture_output=True)
    procs = [(s, c, subprocess.Popen(env_cmd + [s, c], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True))
             for s, c in CASES]
    bad = 0
    for s, c, p in procs:
        txt = p.communicate()[0]
        line = [l for l in txt.splitlines() if l.startswith("{")]
        if p.returncode or not line:
            print(f"{s:26s} {c}  ERROR\n{txt[-800:]}")
            bad += 1
            continue
        r = json.loads(line[-1])
        results.append(r)
        for name, v in r["result"].items():
            ok = v["diff_before_last2"] == 0
            bad += not ok
            print(f"{s:26s} {c}  {name:12s} {'PASS' if ok else 'FAIL'}  "
                  f"{v['bars']:,} bars, {v['diff_total']} differ at the end"
                  + ("" if ok else f", first earlier diff {v['first_diff']}"))
    (HERE / "cut_direct.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
