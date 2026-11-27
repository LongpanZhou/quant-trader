# Revisit brief: rebuild every strategy on its own base

You are the **lead agent**. Your job is to revisit every existing strategy in
this repo and rebuild each one so it **no longer shares the same base**. Plan
the work, spawn subagents to do it, audit their results, fix what the audits
find, and report back.

Repo: `C:\Users\27175\Desktop\quant-trader-research`

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
```

Don't use `python -I`; it ignores `PYTHONPATH`.

## 1. The problem

There are 26 strategies in `research/agents/` and `research/agents2/`. They
all sit on one shared base:

> Hold 100% TQQQ when QQQ closes above its 165-day SMA, otherwise hold 100% BIL.

Most round-2 strategies also inherit round 1's 4% armed minute stop. Each
strategy is just that base plus a small overlay. As a result, their daily
returns correlate at about 0.86, their equity curves look the same, and the
differences between them come from a few dozen days a year.

## 2. The task

For **each** strategy:

1. **Extract its idea.** Read its `strategy.py` and `report.md`, and write
   down in one or two sentences what is actually *new* in it, separate from
   the shared base. Examples: "TQQQ/QQQ ratio froth predicts reversals",
   "OpEx Fridays are weak", "relative volume marks dangerous sessions".
2. **Rebuild it on its own base.** Design a complete strategy in which that
   idea decides the position, with no 165-day QQQ regime and no round-1 stop
   underneath. The base has to come from the idea itself and from your own
   evidence: which assets to hold, when, and at what size.
3. **If the idea can't stand alone,** because it only ever worked as a
   filter on the shared base (for example a pure stop rule), say so, show the
   evidence, and mark it `retired: overlay-only`. Don't force it.

### Clarification (2026-11-26)

The goal is **not** to strip the shared base off 26 overlays and call the residue a
strategy. Each agent must **research and test a complete, genuinely different
strategy** from its assigned research area. The original strategy is only a
starting point.

You may change:

- universe: QQQ/TQQQ/BIL today, but also SPY, sectors, bonds, gold, volatility
  products, or long-lived large caps where the data supports it;
- timeframe and holding period;
- entry, exit, sizing and risk rules;
- long/short, with borrow cost and gross exposure limits;
- the regime definition, if the strategy needs one.

Do **not** use the old 165-day QQQ/TQQQ/SPY/NDX moving-average gate. Do not reuse
the old base weights. A strategy that is only a stop or filter should either be
rebuilt around the underlying effect as a full strategy, or retired with
evidence. Diversity is required: distinct return drivers, correlation below
0.60 with the old base and below 0.70 with every other rebuild.

**Research before code.** Write the hypothesis, source provenance and falsifiers
before building. Backtests remain paused until the lead/user authorizes the new
test.

**Hard rules for rebuilt strategies:**
- **No shared base.** The strategy may not use QQQ, TQQQ, SPY or NDX against
  any 100–250-day moving average as its gate, including renamed versions
  ("slow gate", EMA, 150 or 200 instead of 165).
- **No reused positions or code.** Don't call or copy the old `build_weights`
  or the round-1 winner's weights. Reading the old code to understand the idea
  is fine.
- **Low correlation with the old base:** daily-return correlation with the
  165-day baseline below **0.60** on the development period.
- **Low correlation with each other:** correlation with every other rebuilt
  strategy below **0.70**. If two rebuilt strategies collide, the lead asks one
  of them to change direction.
- **Any assets are allowed:** stocks, sector ETFs, bonds, gold, volatility
  products, leveraged or not. Long-only by default; shorts only with modelled
  borrow cost (≥ 0.5%/yr) and gross exposure ≤ 2×.
- **Leave the originals untouched.** Write each rebuild to
  `research/revisit/<slug>/`, using the same slug as the original.

## 3. The strategies

| Folder | Slug | Idea to extract (starting point; verify it) |
|---|---|---|
| agents | daily-regime-minute-entry | 4% intraday stop, armed when QQQ opens weak |
| agents | donchian-breakout | 55-bar 5-minute Donchian breakout entry |
| agents | drawdown-stop-overlay | threshold stop with 10-day-high re-entry |
| agents | ensemble-signals | volatility budget plus intraday crash vote |
| agents | intraday-mean-reversion | 3% stop from prior close |
| agents | intraday-momentum | overnight drift plus first-hour momentum |
| agents | ml-classifier | walk-forward logistic risk-off model |
| agents | opening-range-breakout | opening-range breakout |
| agents | time-of-day | overnight plus first 30 minutes |
| agents | vol-kelly-overlay | realised-volatility ladder from TQQQ to QQQ |
| agents2 | drawdown-regime | tighter stop while in drawdown |
| agents2 | dual-speed-regime | 60-minute EMA crossover |
| agents2 | dynamic-leverage-throttle | volatility-targeted leverage |
| agents2 | event-risk-overlay | weak option-expiry (OpEx) sessions |
| agents2 | gap-capitulation-reversal | buying after gap-down capitulation |
| agents2 | gap-fill-fade | fading gap-ups |
| agents2 | intraday-seasonality | late-day de-risking |
| agents2 | letf-rebalance-flow | leveraged-ETF rebalancing flow into the close |
| agents2 | ml-crash-overlay-winner | ML crash-day classifier |
| agents2 | overnight-crash-filter | first-hour gate plus volatility crash filter |
| agents2 | ratio-pairs | TQQQ/QQQ ratio froth |
| agents2 | risk-parity-hrp | risk-parity / HRP allocation |
| agents2 | stop-reentry-recovery | gradual re-entry after a stop |
| agents2 | vol-scaled-crash-stop | ATR-scaled stop |
| agents2 | volume-orderflow | relative-volume-armed stop |
| agents2 | winner-ensemble-blend | inverse-volatility blend of sleeves |

## 4. Data and engine

- **Local data:** 1-minute and daily QQQ / TQQQ / BIL in `data/intraday-hf/`,
  plus SPY in `data/cache/dukascopy/`.
- **New data:** goes in `data/round3/<source>/` with a `SOURCE.md` (source,
  fetch date, adjustment). Stock selection needs a point-in-time universe that
  includes delisted names; if that isn't available, say so and restrict to ETFs
  or long-lived large caps. Fundamentals and events use their publication date.
- **Engine:** use `research/bt.py`. `bt.run` / `bt.simulate` run on a compiled
  Rust core (about 25 ms for a full 1-minute run) and accept any `(n, k)`
  weight matrix. Use `bt.run_many` for sweeps; it runs a batch in parallel
  across all cores. Don't write a private simulator.
  - If `research/simcore/target/release/simcore.dll` is missing, build it with
    `cargo build --release --manifest-path research/simcore/Cargo.toml`.
    Otherwise `bt` silently falls back to the slow Python loop.

## 5. Evaluation rules (non-negotiable)

- **Periods:**
  - Development: 2016-01-04 → 2023-12-29.
  - Holdout: **2024-01-02 → 2026-10-23**.
  - Subagents never look at holdout results. The lead runs each frozen
    strategy on the holdout exactly once.
  - Also report the 10y (2017-01-03 →) and 5y (2021-10-25 →) windows so
    results compare with the originals. Label them as overlapping the holdout.
- **Fills:** weights set at bar *i*'s close fill at bar *i+1*'s open, with a
  2% band.
- **Costs:** 1 bp as the headline, plus 5 bp and 10 bp.
- **Minute marks:** mark equity on 1-minute bars for every strategy, including
  daily ones (`research/minute_marks.py:to_minutes`).
- **Sessions:** find each session's last bar per day (half days end at 13:00).
  Index by bar, not by time of day; 18 sessions have missing minutes.
- **Overfitting controls**, all reported:
  - variants tried;
  - a ±1-step parameter-neighbourhood table, with parameters chosen from a plateau;
  - sub-periods 2016–19, 2020–21 and 2022–23;
  - a random or placebo control;
  - for edges with fewer than 100 events, the event count and a bootstrap p-value.
- **Benchmarks:** TQQQ, QQQ and SPY buy-and-hold, plus the original strategy's
  own `result.json` numbers.

## 6. Team: spawn these subagents

Use the Agent tool. Pass each subagent this brief plus its own assignment.
Researchers run in parallel with `isolation: "worktree"`.

1. **Data subagent (one, first).** Fetch and validate whatever data the
   researchers need. Write `research/revisit/data_check.md`.
2. **Researcher subagents.** Group the 26 strategies into 6–9 batches of
   related ideas (stops, intraday timing, calendar and events, volatility and
   sizing, ML, flows and ratios, allocation). Give each researcher one batch.
   Per strategy, the researcher:
   1. writes the extracted idea and a hypothesis for a standalone version,
      including what would prove it wrong, *before* building anything;
   2. builds `research/revisit/<slug>/strategy.py` with
      `build_weights(...) -> (weights, info)`, and a `main()` that writes
      `result.json`;
   3. writes `report.md` covering the idea, hypothesis, evidence for each
      choice, results, failures, overfitting controls, and the two correlation
      numbers;
   4. freezes the strategy with a commit in its worktree and reports the hash;
   5. writes a retirement note instead if the idea is overlay-only.
3. **Auditor subagents.** One per finished strategy, never the agent that wrote
   it. Each writes `research/revisit/<slug>/AUDIT.md` with pass/fail on:
   1. **look-ahead:** weights must be identical before cuts at 2020-03-12
      11:07 and 2022-09-13 10:41, plus 2022-06-30 for models;
   2. **spec vs code:** every rule matches, including thresholds and `<` vs `≤`;
   3. **reproduction:** a clean run of `strategy.py` matches the report, with no
      hand-typed numbers;
   4. **harness:** next-open fills, band, minute marks, session boundaries and
      indexing;
   5. **no shared base:** the section 2 rules, with both correlations recomputed
      independently;
   6. **data:** survivorship and point-in-time checks;
   7. **overfitting:** the section 5 controls are present and honest.
4. **Fixer subagents.** Spawn one for each failed audit. The fixer:
   - fixes the cause, never `result.json` by hand;
   - re-runs the strategy;
   - logs in `AUDIT.md` how the numbers moved, including when they got worse;
   - hands the strategy to a **fresh** auditor.

   Stop after three failed rounds and mark the strategy `rejected`. If a fix
   would change the strategy's idea, reject it instead.

## 7. Lead agent's final steps

1. **Holdout:** run it once per audited, frozen strategy. Record it under
   `windows.holdout`.
2. **Correlations:** save `research/revisit/correlations.json`. It should
   include all rebuilt strategies, the 165-day baseline, TQQQ and the
   originals. The headline numbers are the average pairwise correlation of the
   rebuilt set vs the original set's 0.86.
3. **Leaderboard:** add `research/revisit` to the scan list in
   `research/compare_agents.py` and `research/export_web_compare.py`, and give
   it its own group. Run `research/minute_marks.py` if needed, then the export.
   Don't weaken the export's check that stops on unreadable agents. Use
   `EXCLUDED` only for documented retirements and rejections.
4. **Summary:** write `research/revisit/SUMMARY.md` with one row per strategy:
   - the idea;
   - the status (passed / retired / rejected);
   - original vs rebuilt results;
   - development vs holdout results;
   - correlation with the old base.

   Then give an honest overall assessment: did removing the shared base reveal
   real, independent edges, or were most ideas only overlays?
5. **Report back** to the user with that summary. Don't call any strategy
   working unless it passed audit and its holdout result sits next to its
   development result.

## `result.json` format (required)

```json
{
  "agent": "<slug>",
  "original": "research/agents2/<slug>",
  "status": "passed | retired_overlay_only | rejected",
  "idea": "<one sentence>",
  "hypothesis": "<one sentence>",
  "universe": ["<symbols or description>"],
  "frozen_commit": "<hash>",
  "variants_tried": 0,
  "corr_vs_165d_baseline": 0.0,
  "max_corr_vs_other_rebuilds": 0.0,
  "windows": {
    "dev":     {"1bp": {"cagr": 0, "max_drawdown": 0, "sharpe": 0, "fills": 0}, "5bp": {}, "10bp": {}},
    "holdout": {"1bp": {}, "5bp": {}, "10bp": {}},
    "10y":     {"1bp": {}, "5bp": {}},
    "5y":      {"1bp": {}, "5bp": {}}
  },
  "marks": "1m",
  "benchmarks": {"tqqq": {}, "qqq": {}, "spy": {}, "original": {}}
}
```

`max_drawdown` is a positive fraction on 1-minute marks. `windows/<w>/1bp` is
the headline the leaderboard reads.
