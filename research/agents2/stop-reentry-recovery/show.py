import json

g = json.load(open("research/agents2/stop-reentry-recovery/sweep5.json"))
print("GRID")
for k, v in g.items():
    print(f"{v['frac']:.3f} {v['tight']:.3f}  {v['10y']['cagr']*100:6.2f}/{v['10y']['dd']*100:5.2f}  "
          f"{v['5y']['cagr']*100:6.2f}/{v['5y']['dd']*100:5.2f}  blk {v['blocked']} ts {v['tight_stops']}")

s = json.load(open("research/agents2/stop-reentry-recovery/result.json"))
print("\nDETAIL")
for n in ("base", "combo"):
    for lab in ("10y", "5y"):
        x = s["variants"][n][lab]
        print(n, lab, "sharpe", round(x["sharpe"], 3), "sortino", round(x["sortino"], 3),
              "vol", round(x["volatility"] * 100, 2), "turn", round(x["turnover"], 1),
              "end", round(x["ending_equity"]))
print("\nBOOTSTRAP", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s["bootstrap"].items()})
print("\nROLLING", {k: (round(v, 4) if isinstance(v, (int, float)) else v)
                    for k, v in s["rolling"].items() if k != "windows"})
print("\nATTR by year", {k: round(v * 100, 2) for k, v in s["attribution"]["by_year"].items()})
print("\nSUB", s["subperiods"])
