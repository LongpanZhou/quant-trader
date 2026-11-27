# Round 3 brief: open research

You are the **lead agent** for round 3 of this repo's strategy research. Read
this whole brief before doing anything. You will plan the round, spawn
subagents to do the research and the auditing, and fix anything the audits
find before reporting.

Repo: `C:\Users\27175\Desktop\quant-trader-research`
Python setup (PowerShell):

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
```

Do not use `python -I`; it ignores `PYTHONPATH`.

---

## 1. The goal

> Find strategies that earn a **higher CAGR than TQQQ buy-and-hold with a much
> lower maximum drawdown**, that keep working on data they were not tuned on,
> and that you can explain.

That is the whole mandate. There is **no required base strategy**, no
required structure, and no required asset. A strategy doesn't need a core
plus overlays. It can be anything: a single rule, a portfolio, a model, a
basket of stocks, an intraday system, a mix of several ideas.

## 2. Why this round is open

Rounds 1 and 2 (`research/agents/`, `research/agents2/`) were told to start
from one baseline: hold TQQQ when QQQ is above its 165-day average, otherwise
BIL. Every agent added an overlay to it. The result was 25 strategies that
behave like one, with an average daily-return correlation of about 0.86 and
near-identical equity curves.

This round removes that anchor. Don't start from that strategy or any other
previous answer. Start from the data and your own reasoning.

## 3. Ground rules

1. **No inherited code or positions.** Don't import, copy or call code from
   `research/agents/` or `research/agents2/`, and don't start from their
   weights. You may *read* their reports, mainly to avoid repeating known dead
   ends.
2. **Any idea is allowed, including one that resembles an old one,** as long
   as you reached it through your own analysis and can show why it works.
   Don't aim for a particular answer, and don't avoid one.
3. **Hypothesis first.** Before building a strategy, write down what you
   think the edge is, why it should exist, and what result would prove you
   wrong. "I swept 400 combinations and this one won" isn't a hypothesis.
4. **Evidence for every choice.** For each parameter, asset and threshold,
   the report shows why it was chosen and what lost. Choose parameters from a
   *plateau* (stable results across nearby values), not from the peak of a
   sweep.

## 4. What can be traded

- **Assets:** any US-listed stocks or ETFs (single names, sectors, factors,
  bonds, commodities, volatility products), leveraged or unleveraged.
- **Signals and methods:** any. Use your own calculations, statistics or
  models.
- **Holding periods:** any, from minutes to months.
- **Long-only by default.** Short positions are allowed only if you model
  borrow cost (≥ 0.5%/yr general collateral; more for hard-to-borrow names)
  and keep gross exposure ≤ 2×.

## 5. Data

Currently local: 1-minute and daily QQQ / TQQQ / BIL in `data/intraday-hf/`,
plus SPY in `data/cache/dukascopy/`. Agents may fetch more data, subject to
these rules:

- **Store data** under `data/round3/<source>/`, as parquet, with a
  `SOURCE.md` saying where it came from, when it was fetched, and whether
  prices are split- and dividend-adjusted.
- **Survivorship bias:** a stock-selection strategy must use a point-in-time
  universe (the members as of each date, including stocks later delisted). If
  that isn't available, say so in the report and restrict the universe to
  ETFs or to large caps that existed for the whole period.
- **No future information:** fundamentals and events must use the date they
  became public, not the period they describe.
- `research/bt.py` works with any number of assets. `bt.run` and
  `bt.simulate` take any `(n, k)` weight matrix, and `bt.panel` loads any
  symbol that has a `data/intraday-hf/<SYMBOL>-1m.parquet` file. Daily-only
  data needs a thin loader that returns the same `(ts, opens, closes)` shape.

The **data subagent** (section 7a) fetches and validates shared data once, so
researchers do not each download their own copy.

## 6. Evaluation rules (non-negotiable)

These rules come from bugs found when rounds 1–2 were audited. Each one is
here because it happened.

**Periods.** Development is 2016-01-04 → 2023-12-29. The holdout is
**2024-01-02 → 2026-10-23**. Researchers may not look at holdout performance
of any variant. The lead agent runs each *final, frozen* strategy on the
holdout exactly once and reports it as is. Also report the 10y
(2017-01-03 →) and 5y (2021-10-25 →) windows for comparison with earlier
rounds, labelled as overlapping the holdout.

**Simulation.**
- Weights set at bar *i*'s close fill at bar *i+1*'s open (`bt.run`).
- 2% band, 1 bp slippage as the headline, plus 5 bp and 10 bp sensitivity.
- **Mark equity on 1-minute bars** wherever minute data exists for the assets
  held, even for daily strategies. Use `research/minute_marks.py:to_minutes`.
  Daily marks hide intraday troughs; on the same strategy, a 36.9% daily-mark
  drawdown was 42.2% on minute marks.
- **Find session boundaries per day.** Half days end at 13:00. Never use a
  global "last bar = 389" or "bar count = 77".
- **Index by bar, not by time of day,** or explicitly map one to the other.
  18 of 2,718 QQQ sessions have missing minutes.

**Benchmarks**, all on the same marks and windows: TQQQ, QQQ and SPY
buy-and-hold.

**Target.** On the holdout and on both comparison windows: CAGR above TQQQ
buy-and-hold and max drawdown well below it. A strategy that misses TQQQ's
CAGR but clearly beats QQQ on a risk-adjusted basis is still worth reporting.
Label it honestly.

**Overfitting controls.** Report all of these:
- the number of variants tried;
- a parameter-neighbourhood table (headline ±1 step on each parameter);
- performance by sub-period: 2016–19, 2020–21, 2022–23;
- a random or placebo control (e.g. the same number of trades on random days);
- for any edge resting on fewer than 100 events, the event count and a
  bootstrap p-value.

## 7. Team structure: spawn these subagents

Use the Agent tool. Give every subagent this brief plus its own instructions.
Run researchers in parallel, each with `isolation: "worktree"`, so they cannot
overwrite each other's files.

### 7a. Data subagent (one, runs first)

- Fetch and validate the shared datasets the researchers ask for.
- Write `data/round3/<source>/SOURCE.md` and a `research/agents3/data_check.md`
  covering gaps, stale prices, split/dividend adjustment checks, and the
  point-in-time universe status.
- Put any loader in `research/agents3/_shared/` and test it.

### 7b. Researcher subagents (5–8, in parallel)

Don't hand researchers a fixed idea. Ask each one to propose its own
direction first, in a short pitch:
- the hypothesis,
- the assets it will trade,
- the data it needs,
- why it might beat TQQQ with a lower drawdown.

The lead reviews all the pitches together and only asks for changes where two
pitches overlap, so the round covers different ground. If a researcher has
no strong idea, the lead may offer starting points. These are examples, not
assignments: cross-sectional momentum, sector rotation, volatility targeting
or leverage timing, multi-asset allocation, overnight vs intraday effects,
event or earnings drift, pairs and mean reversion, volatility risk premium,
or a model built on the researcher's own features.

Each researcher:

1. Writes its hypothesis and the evidence that would refute it, *before*
   building a strategy.
2. Tests it on the development period only.
3. Builds one final strategy in `research/agents3/<slug>/strategy.py` that
   exposes `build_weights(...) -> (weights, info)` and has a `main()` that
   writes `result.json`.
4. Writes `report.md` covering the hypothesis, evidence, rules, results,
   failures, and the overfitting controls from section 6.
5. **Freezes** the strategy by committing it in its worktree, and tells the
   lead the commit hash. It does not look at holdout results.

Failed hypotheses are valuable. A researcher whose idea doesn't work writes it
up as a negative result and stops. It must not keep sweeping until something
passes.

### 7c. Auditor subagents (one per finished strategy, never the same agent that wrote it)

Each auditor checks one strategy and writes `research/agents3/<slug>/AUDIT.md`
with pass/fail on each item:

1. **Look-ahead test.** Build weights on the full panel and on a panel
   truncated mid-session, at 2020-03-12 11:07 and 2022-09-13 10:41. Weights
   before the cut must match exactly. For a model-based strategy, also
   truncate at 2022-06-30 and confirm the earlier predictions don't change.
2. **Spec vs code.** Every rule in the docstring and report exists in the
   code, with the same thresholds and inequalities (`<` vs `≤`), and nothing in
   the code is missing from the spec. (Round 1 shipped a strategy whose
   report described three votes the code never computed.)
3. **Reproduction.** Run `strategy.py` from a clean shell. Every number in
   the report must match `result.json`. No hand-typed numbers.
4. **Harness use.** Next-open fills, 2% band, minute marks, per-session
   boundaries, bar vs time-of-day indexing, no float32 caches, and caches
   keyed by data mtime.
5. **Ground rules.** Section 3: no inherited code, a hypothesis written
   before results, evidence for every choice, and parameters taken from a
   plateau.
6. **Data.** Survivorship bias, point-in-time fundamentals, adjusted prices.
7. **Overfitting.** Are the section 6 controls present and honest? Flag any
   edge resting on a small event count or on a threshold picked from a sweep.

### 7d. Fixer subagents (spawned per failed audit)

For each audit with any failure, spawn a fixer with the audit file and the
strategy folder. The fixer:

- fixes the defect, not the symptom (never edit `result.json` by hand);
- re-runs `strategy.py`;
- appends to `AUDIT.md` what changed and how the numbers moved, including
  when they got worse;
- hands the strategy back to a **fresh** auditor.

Repeat audit → fix until the audit passes, or until three rounds have failed.
In that case, mark the strategy `rejected` in its report and say why. A fix
must not change the strategy's idea. If it would, the strategy is rejected
instead.

## 8. Lead agent's final steps

1. **Run the holdout** once per frozen, audited strategy, and record it in
   each `result.json` under `windows.holdout`.
2. **Compute the correlations** of daily returns between the new strategies,
   plus each one against TQQQ and against the earlier rounds' leader
   (for information only). Save the matrix to
   `research/agents3/correlations.json`.
3. **Update the leaderboard.** Add `research/agents3` to the directories
   scanned by `research/export_web_compare.py` and `research/compare_agents.py`,
   and run the export. The export already refuses to drop unreadable agents;
   do not weaken that check. Use `EXCLUDED` only for documented negative
   results.
4. **Write the summary** in `research/agents3/SUMMARY.md` covering:
   - what was tried;
   - what passed;
   - what failed and why;
   - holdout vs development performance for each strategy;
   - the correlation matrix;
   - an honest assessment of how much of each edge is likely to survive.
5. **Report back** to the user with that summary. Do not claim a strategy
   works unless it passed audit and its holdout result is shown next to its
   development result.

### `result.json` headline format (required)

```json
{
  "agent": "<slug>",
  "status": "passed | negative_result | rejected",
  "hypothesis": "<one sentence>",
  "universe": ["<symbols or universe description>"],
  "frozen_commit": "<hash>",
  "variants_tried": 0,
  "windows": {
    "dev":     {"1bp": {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "fills": 0}, "5bp": {}, "10bp": {}},
    "holdout": {"1bp": {}, "5bp": {}, "10bp": {}},
    "10y":     {"1bp": {}, "5bp": {}},
    "5y":      {"1bp": {}, "5bp": {}}
  },
  "marks": "1m",
  "benchmarks": {"tqqq": {}, "qqq": {}, "spy": {}}
}
```

`max_drawdown` is a positive fraction measured on 1-minute marks. `windows/<w>/1bp`
is the headline the leaderboard reads.

## 9. Things that will get a strategy rejected late, so avoid them early

- It reuses round 1–2 code or positions instead of being built from scratch.
- A choice (signal, parameter, asset, leverage) has no evidence in the report
  beyond "it scored best".
- Its numbers come from a scratch script instead of `strategy.py`.
- The report describes something the code doesn't do.
- Its drawdown is measured on daily marks while other strategies use minute marks.
- Its edge rests on about 100 events with a threshold picked from a sweep.
- Its stock universe only includes today's survivors.
- The researcher looked at the holdout before freezing.
