"""Emit the markdown tables used in report.md from result.json + the sweep
json files. Run after strategy.py.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/report_numbers.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "result.json").read_text())
V = R["variants"]
W = "winner_fixed4_bil"


def pct(x, n=2):
    return f"{x*100:.{n}f}"


def table_headline():
    print("### Headline (1 bp)\n")
    print("| Window | Winner CAGR | Winner DD | ATR CAGR | ATR DD | Δ CAGR | Δ DD |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for lab in ("10y", "5y"):
        a, b = V[W]["windows"][lab], V["atr70_cap4_bil"]["windows"][lab]
        print(f"| {lab} | {pct(a['cagr'])}% | {pct(a['dd'])}% | {pct(b['cagr'])}% | "
              f"{pct(b['dd'])}% | {pct(b['cagr']-a['cagr'],2)}pp | {pct(b['dd']-a['dd'],2)}pp |")


def table_costs():
    print("\n### Cost sensitivity (CAGR / max DD)\n")
    print("| Variant | Costs | 10y CAGR | 10y DD | 5y CAGR | 5y DD |")
    print("|---|---|---:|---:|---:|---:|")
    for name in ("winner_fixed4_bil", "atr70_cap4_bil", "atr055_cap4_bil",
                 "atr085_cap4_bil", "atr070_cap6_bil", "fixed4_partial50",
                 "atr70_cap4_partial50"):
        v = V[name]
        for cost, label in ((None, "1 bp"), ("5bp", "5 bp"), ("10bp", "10 bp")):
            if cost is None:
                c = {lab: v["windows"][lab] for lab in ("10y", "5y")}
            else:
                c = {lab: v["costs"][lab][cost] for lab in ("10y", "5y")}
            print(f"| {name} | {label} | {pct(c['10y']['cagr'])}% | {pct(c['10y']['dd'])}% | "
                  f"{pct(c['5y']['cagr'])}% | {pct(c['5y']['dd'])}% |")


def table_yearly():
    print("\n### Yearly returns (1 bp)\n")
    print("| Year | ATR stop | Winner | TQQQ |")
    print("|---|---:|---:|---:|")
    for y in sorted(V[W]["windows"]["10y"]["yearly"]):
        a = V["atr70_cap4_bil"]["windows"]["10y"]["yearly"][y]["strategy"]
        w = V[W]["windows"]["10y"]["yearly"][y]["strategy"]
        b = V[W]["windows"]["10y"]["yearly"][y]["benchmark"]
        print(f"| {y} | {pct(a)}% | {pct(w)}% | {pct(b)}% |")
    # 2021 stub + 2026 stub of the 5y window
    print("\n5y-window stub years:")
    for y in ("2021", "2026"):
        a = V["atr70_cap4_bil"]["windows"]["5y"]["yearly"][y]["strategy"]
        w = V[W]["windows"]["5y"]["yearly"][y]["strategy"]
        b = V[W]["windows"]["5y"]["yearly"][y]["benchmark"]
        print(f"  {y}: ATR {pct(a)}%  winner {pct(w)}%  TQQQ {pct(b)}%")


def table_rolling():
    print("\n### Rolling 3-year windows (quarterly starts, 756 trading days)\n")
    print("| Variant | Window | n | CAGR>TQQQ | DD<TQQQ | both>TQQQ | CAGR>winner | DD<winner | both>winner | median CAGR edge | median DD edge |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("atr055_cap4_bil", "atr70_cap4_bil", "atr085_cap4_bil",
                 "atr070_cap6_bil", "fixed4_partial50", "atr70_cap4_partial50"):
        s = V[name].get("rolling3y_summary")
        if not s:
            continue
        for lab in ("10y", "5y"):
            x = s[lab]
            print(f"| {name} | {lab} | {x['windows']} | {x['beat_tqqq_cagr']} | "
                  f"{x['beat_tqqq_dd']} | {x['beat_both_tqqq']} | {x['beat_winner_cagr']} | "
                  f"{x['beat_winner_dd']} | {x['beat_winner_both']} | "
                  f"{pct(x['median_cagr_edge'])}pp | {pct(x['median_dd_edge'])}pp |")


def table_windows_best_worst():
    print("\n### Rolling 3y worst windows for the headline\n")
    rw = V["atr70_cap4_bil"]["rolling3y"]["10y"]
    rwin = V[W]["rolling3y"]["10y"]
    rows = sorted(zip(rw, rwin), key=lambda z: z[0]["cagr"] - z[1]["cagr"])
    print("| start | ATR CAGR | ATR DD | winner CAGR | winner DD | TQQQ CAGR | TQQQ DD |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for a, w in rows[:3] + rows[-3:]:
        print(f"| {a['start']} | {pct(a['cagr'])}% | {pct(a['dd'])}% | {pct(w['cagr'])}% | "
              f"{pct(w['dd'])}% | {pct(a['bench_cagr'])}% | {pct(a['bench_dd'])}% |")


def table_surface():
    print("\n### Parameter surface (10y / 5y, 1 bp)\n")
    print("| Stop distance | 10y CAGR | 10y DD | 5y CAGR | 5y DD | stops | fills |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name in ("atr055_cap4_bil", "atr70_cap4_bil", "atr085_cap4_bil",
                 "atr070_cap6_bil", "fixed4_partial50", "atr70_cap4_partial50",
                 "winner_fixed4_bil"):
        v = V[name]
        lab = name
        print(f"| {lab} | {pct(v['windows']['10y']['cagr'])}% | {pct(v['windows']['10y']['dd'])}% | "
              f"{pct(v['windows']['5y']['cagr'])}% | {pct(v['windows']['5y']['dd'])}% | "
              f"{v['stops']} | {v['windows']['10y']['fills']} |")


def subperiods():
    print("\n### Sub-period returns (compounded yearly, 1 bp)\n")
    groups = {"2017-2019": ("2017", "2018", "2019"), "2020-2022": ("2020", "2021", "2022"),
              "2023-2026": ("2023", "2024", "2025", "2026")}
    print("| Period | ATR | Winner | TQQQ |")
    print("|---|---:|---:|---:|")
    for label, yrs in groups.items():
        vals = []
        for name in ("atr70_cap4_bil", W):
            y = V[name]["windows"]["10y"]["yearly"]
            prod = 1.0
            for yy in yrs:
                prod *= 1 + y[yy]["strategy"]
            vals.append(prod - 1)
        prod = 1.0
        for yy in yrs:
            prod *= 1 + V[W]["windows"]["10y"]["yearly"][yy]["benchmark"]
        print(f"| {label} | {pct(vals[0])}% | {pct(vals[1])}% | {pct(prod-1)}% |")


def pass_flags():
    print("\n### Pass/fail\n")
    for name, p in R["pass_vs_winner"].items():
        print(f"{name}: strict {p['strict_dominance']}  dd/2pp {p['lower_dd_within_2pp']}  "
              f"vs TQQQ {R['pass_vs_tqqq'][name]}")


def extras():
    print("\n### Extras")
    print("diagnostics:", json.dumps(R["diagnostics"])[:400])
    for name in ("atr70_cap4_bil", "winner_fixed4_bil"):
        for lab in ("10y", "5y"):
            w = V[name]["windows"][lab]
            print(f"{name} {lab}: sharpe {w['sharpe']:.2f} sortino {w['sortino']:.2f} "
                  f"vol {pct(w['vol'])}% turnover {w['turnover']:.0f}x "
                  f"tqqq_time {pct(w['tqqq_time'],1)}% dd {w['dd_peak']} -> {w['dd_trough']}")


if __name__ == "__main__":
    table_headline()
    table_costs()
    table_yearly()
    table_rolling()
    table_windows_best_worst()
    table_surface()
    subperiods()
    pass_flags()
    extras()
