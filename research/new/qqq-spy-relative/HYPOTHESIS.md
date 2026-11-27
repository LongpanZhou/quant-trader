# QQQ/SPY Relative-Strength Leverage Ladder — pre-registration

**Status:** written before the final grid was run. Development window only:
2016-01-04 → 2023-12-29. The 2024-01-02 → 2026-10-23 holdout is never loaded,
inspected or used for selection. SPY daily data is physically sliced at
2023-12-29 with a Parquet filter.

**One-sentence hypothesis.** Nasdaq leadership versus the S&P 500, combined
with Nasdaq's own trend, defines four risk states. Mapping those states to a
3x / 2x / 1x / 0x Nasdaq exposure ladder and capping the TQQQ sleeve by its own
20-session realized volatility should keep most of TQQQ's bull-market
compounding while cutting its 82% drawdown enough to beat the 36.72%
development CAGR.

---

## 1. Motivation

TQQQ is a 3x daily-reset Nasdaq-100 ETF. Its 2016-2023 record (36.72% CAGR /
82.29% max DD, 1-minute marks) is a strong trend multiplied by three
deleveraging episodes: 2018-Q4, the 2020 COVID crash, and 2022. A 3x daily-reset
fund is path-dependent: the same volatility that makes the crash deep makes the
recovery explosive, so avoiding the worst compounding damage is worth more than
the return given up in whipsaws.

The mandate asks for a **QQQ/SPY relative-strength** signal. The economic story
is a leadership/risk-appetite state variable:

- When Nasdaq is outperforming the S&P 500, growth/tech leadership is intact
  and the leveraged Nasdaq sleeve is appropriate.
- When Nasdaq is lagging, the 3x sleeve is paid for a fading relative trend;
  de-lever to QQQ.
- Independently, when QQQ is below its own slow trend, the equity risk premium
  is not being paid; hold BIL (or QQQ only when tech is still leading).

The result is a **leverage ladder**, not a stock-selection or market-neutral
spread:

| Relative strength | Absolute trend | Position | Effective Nasdaq exposure |
|---|---|---|---|
| positive | positive | 100% TQQQ | 3x |
| negative | positive | 50% TQQQ + 50% QQQ | 2x |
| positive | negative | 100% QQQ | 1x |
| negative | negative | 100% BIL | 0x |

The 2x rung is the key compromise: when tech is lagging but the market is still
in an uptrend, the book stays invested at reduced leverage instead of jumping
between 3x and 1x. The 1x rung captures the rare "tech leading while the broad
market is below trend" state, which historically occurs near V-bottoms.

## 2. Exact rules

### 2.1 Data and calendar

- **Tradable:** QQQ, TQQQ, BIL. Long-only, weights ≥ 0, row sum ≤ 1.
- **Signal only:** SPY, Yahoo `adjclose` from
  `data/round3/yahoo/SPY-1d-yahoo.parquet`. No SPY 1-minute history exists for
  2016-2023, so SPY is never held or marked.
- **Daily closes:** the 15:59 ET close of each session from the 1-minute panel
  (`bt.panel(..., "1min")`). Before 2016-01-04, the Yahoo adjusted daily close is
  spliced at the first panel close, so 200-session indicators have warm-up from
  2015-01-02.
- **Session boundaries:** `bt.day_bounds`. Half-days are truncated at 13:00 by
  `bt.load_1m`.
- **Total return:** adjusted closes include dividends and the BIL 2017 reverse
  split repair.

### 2.2 Signals

For lookback `L` sessions:

```
M_L(asset, k) = P(asset, k) / P(asset, k-L) - 1
```

At the 15:59 close of session `k`:

- **Relative gate (R):** `M_126(QQQ, k-1) > M_126(SPY, k-1)`.
  SPY's official close is 16:00, one minute after the decision bar. To avoid a
  one-minute look-ahead **and** the one-day endpoint mismatch that a stale SPY
  leg would create, both legs are measured through session `k-1`. The whole
  relative comparison is therefore one session old; the absolute gate is
  current.
- **Absolute gate (A):** `QQQ(k) > SMA_150(QQQ, k)`, using the 15:59 close at
  the decision bar.

The one-session lag on the relative gate is deliberate and is stress-tested.
A same-day SPY close (look-ahead) is reported only as an upper bound, never as
the strategy.

### 2.3 Position mapping

| R | A | Target at session k's close |
|---|---|---|
| + | + | TQQQ 1.00 |
| − | + | TQQQ 0.50 + QQQ 0.50 |
| + | − | QQQ 1.00 |
| − | − | BIL 1.00 |

### 2.4 Volatility cap

Let `rv20(k)` be the annualized 20-session realized volatility of TQQQ daily
total returns through session `k`:

```
s(k) = min(1, 0.70 / rv20(k))
```

The TQQQ sleeve is multiplied by `s(k)`. The freed weight goes to QQQ when the
absolute gate is on, otherwise to BIL. This is a risk control, not a return
forecast: it cuts the 3x sleeve when realized volatility makes daily-reset decay
most damaging. It uses only past returns and has no full-sample normalization.

### 2.5 Execution

- Targets are refreshed every session at the close and filled at the next
  session's open.
- 2% band; costs 1 bp headline, 5 bp and 10 bp sensitivity.
- Equity is marked on every 1-minute bar.
- Daily refresh is intentional: the state machine changes rarely, but the
  volatility cap moves continuously, and the 2% band suppresses small trades.

## 3. Pre-registered grid (8 cells)

`p = 0.50` is the TQQQ fraction in the R−/A+ state. Changes are one-factor-at-a-
time around the centre A.

| ID | rel lookback | QQQ SMA | vol cap | p | note |
|---|---:|---:|---:|---:|---|
| **A** | **126** | **150** | **0.70** | **0.50** | **primary** |
| B | 126 | 150 | 0.60 | 0.50 | tighter vol cap |
| C | 126 | 150 | 0.80 | 0.50 | looser vol cap |
| D | 105 | 150 | 0.70 | 0.50 | shorter RS |
| E | 147 | 150 | 0.70 | 0.50 | longer RS |
| F | 126 | 180 | 0.70 | 0.50 | slower trend |
| G | 126 | 200 | 0.70 | 0.50 | classic 200-day |
| H | 126 | 150 | none | 0.50 | no vol cap |

The grid is a plateau probe, not a search. The primary is fixed at A before the
run. No cell is selected after seeing the result.

## 4. Falsifiers (fixed before the run)

1. **Headline:** primary CAGR ≤ 36.72% **or** max DD ≥ 60%.
2. **Plateau:** fewer than 5 of the 8 pre-registered cells pass the same bar.
3. **Costs:** primary 10 bp CAGR ≤ 36.72%.
4. **Placebo:** ≥ 10% of 200 circular shifts of the per-session target path
   match or beat the primary CAGR.
5. **Causality:** any cut-test rebuild differs from the full-run weights by
   more than 1e-12.
6. **Relative gate adds risk-adjusted value:** primary Sharpe is not at least
   0.02 above the absolute-only ladder (same vol cap, TQQQ when A+, QQQ when
   A−).
7. **Year dependence:** fewer than 5 of the 7 leave-one-year-out 7-year CAGRs
   exceed 36.72%.

Falsifiers 6 and 7 are the honest tests of whether this is more than Nasdaq
beta. They can fail while the headline passes; if so, the report says so.

## 5. Known risks and prior work

- **The relative signal is probably Nasdaq beta in disguise.** QQQ and SPY are
  roughly 0.9 correlated; QQQ usually outperforms in bull markets. The report
  measures gate agreement, the absolute-only and relative-only ablations, the
  static blend at the strategy's own average weights, and beta/correlation to
  TQQQ.
- **2022-style slow bear.** The absolute gate is a slow trend filter; it will
  not exit on day one of a bear market. The relative gate may turn first.
- **Whipsaw.** A 150-day SMA on QQQ whipsawed in 2016, 2019 and 2020. The 2x
  rung and the vol cap are there to soften it.
- **Overlap with existing work.** `research/new/cross-asset-momentum` also uses
  a QQQ/SPY relative gate and absolute gates with a TQQQ/QQQ/BIL book. That
  strategy uses a multi-horizon (21/42 OR, 84/105/126 majority) absolute
  ensemble, weekly rebalance, a full QQQ fallback and a 100% vol target. This
  one uses a single 150-day QQQ trend, a four-rung leverage ladder including a
  50% TQQQ rung, daily refresh and a 70% TQQQ vol cap. They are the same
  economic family; this is a simpler, more explicit ladder. The report states
  the overlap rather than claiming independence.
- **Exploratory status.** The state family (relative gate + absolute trend +
  vol cap) and the grid centre were chosen after daily-bar diagnostics on the
  same development window. The holdout must be run once, frozen, by the lead.
  This is not a clean out-of-sample pass.

## 6. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\qqq-spy-relative\strategy.py
```

`strategy.py` writes `result.json` and prints the grid. All fills go through
`research/bt.py` (compiled `simcore` when available).
