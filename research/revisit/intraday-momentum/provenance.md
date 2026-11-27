# Provenance and source audit — intraday-momentum rebuild

**Rule:** every rule or claim below is tied to a source, or explicitly marked
`Own test / no external source`. The distinction between **inspired the rule**
and **tested and rejected** is kept separate.

## Sources used

### 1. The overnight-minus-intraday signal

- **Source:** Boyarchenko, Larsen & Whelan (2023), *The Overnight Drift*,
  *Review of Financial Studies* 36(9), 3502–3547.
- **Links:** NY Fed Staff Report 917 —
  https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf ;
  SSRN — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3546173
- **Exact claim used:** “overnight (intraday) returns predict subsequent
  overnight (intraday) returns positively, while overnight (intraday) returns
  predict subsequent intraday (overnight) returns negatively.” The paper also
  documents that U.S. equity returns are large and positive during the opening
  hours of European markets, positive in 20 of 23 years since 1998.
- **Role:** inspired the `S_on = Σ(overnight − intraday)` signal. The sign is
  the paper's continuation/reversal pattern: a positive overnight-minus-intraday
  spread is the state in which the overnight drift is stronger than the
  intraday drift.
- **Confidence:** high for the claim; medium for the weekly aggregation (the
  paper works at the daily/intraday level, not weekly).

### 2. The overnight/intraday decomposition

- **Source:** Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus
  Intraday Expected Returns*, *Journal of Financial Economics* 134(1), 192–213.
- **Link:** https://doi.org/10.1016/j.jfineco.2019.03.011
- **Exact claim used:** “profits are either earned entirely overnight (for
  reversal and a variety of momentum strategies) or entirely intraday,
  typically with profits of opposite signs across these components.”
- **Role:** supports the premise that the overnight and intraday components
  carry different premia and should be measured separately. It motivates the
  `overnight − intraday` spread rather than a single close-to-close return.
- **Confidence:** high.

### 3. The first-hour momentum component

- **Source:** Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*,
  *Journal of Financial Economics* 129(2), 394–414.
- **Link:** https://doi.org/10.1016/j.jfineco.2018.05.009
- **Exact claim used:** “the first half-hour return on the market as measured
  from the previous day's market close predicts the last half-hour return.”
- **Role:** inspired the first-hour component, `S_fh = Σ first_hour`. The
  original strategy used the same idea to gate the afternoon. The rebuild
  aggregates it over 5 sessions and uses it as one leg of the leverage ladder.
- **Confidence:** high for the source claim; **low for the exact last-30-minute
  implementation** in this sample — see “Tested and rejected” below.

### 4. The cross-sectional / industry-ETF evidence (fallback only)

- **Source:** Bogousslavsky (2021), *The Cross-Section of Intraday and
  Overnight Returns*, *Journal of Financial Economics* 141, 172–194.
- **Link:** https://doi.org/10.1016/j.jfineco.2020.07.020
- **Exact claim used:** “high overnight returns of industry ETFs are associated
  with sentiment-based trading.”
- **Role:** supports the deferred cross-sectional sector version (9 SPDR
  sectors, long top 3 overnight). It is **not** used in the primary
  single-asset ladder. It is the first fallback if the single-asset strategy
  correlates too highly with the old base.
- **Confidence:** medium (the DOI is taken from the publisher citation; the
  paper was not read in full).

### 5. The intraday-momentum mechanism

- **Source:** Baltussen, Da, Lammers & Martens (2021), *Hedging Demand and
  Market Intraday Momentum*, *Journal of Financial Economics* 142(1), 377–403.
- **Link:** https://doi.org/10.1016/j.jfineco.2021.04.029
- **Exact claim used:** “The return during the last 30 minutes before the market
  close is positively predicted by the return during the rest of the day (from
  previous market close to the last 30 minutes).” The paper links the effect to
  gamma hedging by option dealers and leveraged ETFs.
- **Role:** supports the economic mechanism for time-of-day momentum and the
  choice of QQQ/TQQQ. It is not the direct source of the weekly signal.
- **Confidence:** high.

### 6. TQQQ mechanics and path dependence

- **Source:** Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse
  Exchange-Traded Funds*, *Journal of Investment Management* 7(4).
- **Link:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
- **Exact claim used:** daily re-leveraging creates path dependence and
  end-of-day rebalancing flows; leveraged ETFs are not buy-and-hold vehicles.
- **Role:** supports using QQQ (not TQQQ) for the signal, and the report's
  caveat that TQQQ's 3x path may differ from a simple 3x overlay.
- **Confidence:** high.

## Design choices with no external source

- **26-week median normalization** of the weekly signals. Own choice. Reason:
  both raw signals have a positive mean, so a zero threshold would leave the
  strategy long most of the time and recreate the old base's high correlation.
  The median centers each signal on its own recent “usual” level.
- **5-session rebalance / holding period.** Own choice. Reason: daily
  time-of-day timing needs daily round trips (12–25%/yr at 5–10 bp); 5 sessions
  cuts turnover ~5x while keeping enough observations.
- **Three-state 3x/1x/0x ladder.** Own choice. Reason: a binary TQQQ/BIL rule
  has a high beta and a high correlation with the old base; the QQQ middle
  state is a genuine 1x alternative.
- **20-session overnight-vol caps (60% / 80%).** Own choice. Reason: a
  signal-derived crash filter; no price trend. The exact thresholds are
  pre-registered and will be tested in a ±1-step neighbourhood.
- **Minimum 13 weekly observations before the median is used.** Own choice, to
  avoid a noisy median. It creates an effective dev start around 2016-04.

## Tested and rejected (keep separate from sources)

### Gao et al. (2018) — last-30-minute version

- **Status:** tested in the original `intraday-momentum` work and **rejected**
  for this sample.
- **Evidence:** TQQQ's last-30-minute return after a positive first 30m was
  −1.60 bp/day on the 2017–2026 window and −2.43 bp/day on the 2021–2026
  window; the predictability was in the midday/afternoon, not the close.
- **Consequence:** the rebuild does not use a last-30-minute rule. It uses the
  first-hour return as a weekly state variable, not as a last-half-hour timing
  rule. This is a weaker, different use of the same source.

### Pure daily intraday momentum (own test)

- **Status:** tested and **rejected**.
- **Evidence:** long TQQQ only from 10:00/10:30 to the close on a positive
  first-30/60m signal, flat overnight, earned 12.89% / 8.96% CAGR on the
  10-year window (10.80% / 32.26% on 5y) after 1 bp costs — below TQQQ and
  below the daily baseline.
- **Consequence:** the rebuild does not use a pure intraday-only holding
  period.

### Overnight-only with the 165-day regime (own test)

- **Status:** tested and **rejected as a standalone**.
- **Evidence:** overnight-only + 165-day regime earned 27.66% / 47.18% on 10y
  and 14.42% / 34.69% on 5y; it passed the 5y TQQQ test but failed the 10y
  CAGR (27.66% < 39.28%). At 5 bp it lost −8.46%/yr because of daily round
  trips.
- **Consequence:** the rebuild uses a 5-session holding period, not a daily
  overnight-only one, and does not use the 165-day regime.

### Long-short overnight/intraday carry (own test, not run)

- **Status:** designed but **not usable** with the required harness.
- **Reason:** `research/bt.py` accepts only non-negative weights and sums
  ≤ 1. The brief forbids a private simulator, so a short QQQ intraday leg
  cannot be modelled inside the required engine.
- **Consequence:** the rebuild is long-only.

## Source-to-rule map

| Rule | Source | Role |
|---|---|---|
| `S_on = Σ(overnight − intraday)` | Boyarchenko et al. (2023) | inspired the rule |
| Overnight and intraday are separate premia | Lou, Polk & Skouras (2019) | supports assumption |
| `S_fh = Σ first_hour` | Gao et al. (2018) | inspired the rule |
| QQQ as the signal asset | Cheng & Madhavan (2009) | supports assumption |
| TQQQ 3x path caveat | Cheng & Madhavan (2009) | supports assumption |
| 26-week median, 5-session rebalance, 3-state ladder, vol caps | Own test / no external source | design choices |
| Cross-sectional sector fallback | Bogousslavsky (2021) | supports fallback (not used in primary) |
| Last-30-minute timing | Gao et al. (2018) | tested and rejected |
| Pure daily intraday only | Own test / no external source | tested and rejected |
| Overnight-only + 165-day regime | Own test / no external source | tested and rejected |
