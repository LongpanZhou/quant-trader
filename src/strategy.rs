use crate::config::{Config, StrategyConfig};
use crate::edgar::{Edgar, Report};
use crate::indicators::{linreg, rsi, sma, stddev};
use crate::types::{Bar, Signal};
use anyhow::{bail, Result};
use chrono::{Datelike, NaiveDate};
use std::cell::{Cell, RefCell};
use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};
use std::path::Path;
use std::time::{Duration, Instant};

/// How often a live session re-checks the SEC for newly filed reports.
const LIVE_REPORT_REFRESH: Duration = Duration::from_secs(6 * 3600);

/// A strategy is either *per-symbol* (implements `signal`) or *portfolio-level*
/// (implements `targets` and returns true from `is_portfolio`).
///
/// Bars are always completed bars, oldest first; the last element is the bar
/// that just closed.
pub trait Strategy {
    fn name(&self) -> String;
    /// Bars of history needed before the strategy can act.
    fn warmup(&self) -> usize;
    /// How many trailing bars to hand the strategy on each evaluation.
    fn lookback(&self) -> usize {
        (self.warmup() * 5).max(250)
    }

    /// Per-symbol decision.
    fn signal(&self, _bars: &[Bar], _in_position: bool) -> Signal {
        Signal::Hold
    }

    fn is_portfolio(&self) -> bool {
        false
    }
    /// Portfolio decision: on a rebalance bar, return every symbol that should
    /// be held with its target weight (fraction of account equity), highest
    /// priority first. Anything not listed is sold. Return None when it is
    /// not time to rebalance.
    fn targets(&self, _universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        None
    }
    /// Existing positions are only resized when they are off target by more
    /// than this fraction of equity (turnover control). Infinite = never.
    fn rebalance_band(&self) -> f64 {
        f64::INFINITY
    }
}

/// Where the strategy will run. Live trading acts at the open on everything
/// known up to the previous close; a backtest fills at the close of the bar
/// it evaluates, so it must not use anything published that same day.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Live,
    Backtest,
}

/// Build the configured strategy. `cache_dir` is where downloaded reference
/// data (company financial reports) is kept between runs.
pub fn build(cfg: &Config, mode: Mode, cache_dir: &Path) -> Result<Box<dyn Strategy>> {
    build_kind(&cfg.strategy, cfg, mode, cache_dir)
}

fn build_kind(
    kind: &StrategyConfig,
    cfg: &Config,
    mode: Mode,
    cache_dir: &Path,
) -> Result<Box<dyn Strategy>> {
    Ok(match kind {
        StrategyConfig::LsMomentum {
            lookback_days,
            skip_days,
            long_frac,
            short_frac,
            long_gross,
            short_gross,
            rebalance_band,
            index,
            score,
            seed,
        } => Box::new(LsMomentum {
            score: score.clone(),
            seed: *seed,
            lookback: *lookback_days,
            skip: *skip_days,
            long_frac: *long_frac,
            short_frac: *short_frac,
            long_gross: *long_gross,
            short_gross: *short_gross,
            band: *rebalance_band,
            index: index.to_uppercase(),
        }),
        StrategyConfig::IntradayLsMomentum {
            lookback_days,
            skip_days,
            long_frac,
            short_frac,
            long_gross,
            short_gross,
            rebalance_band,
            index,
            rebalance_minutes,
        } => Box::new(IntradayLsMomentum {
            lookback: *lookback_days,
            skip: *skip_days,
            long_frac: *long_frac,
            short_frac: *short_frac,
            long_gross: *long_gross,
            short_gross: *short_gross,
            band: *rebalance_band,
            index: index.to_uppercase(),
            bars_per_day: cfg.timeframe.bars_per_day(),
            bar_secs: cfg.timeframe.secs(),
            // Re-ranking during the day only makes sense on intraday candles.
            rebalance_mins: if cfg.timeframe.secs() < 86_400 { *rebalance_minutes as i32 } else { 0 },
        }),
        StrategyConfig::EarningsDrift {
            long_sue,
            short_sue,
            hold_days,
            position_weight,
            max_long,
            max_short,
            rebalance_band,
        } => {
            let ciks: Vec<(String, u64)> = cfg
                .symbols
                .iter()
                .filter_map(|s| cfg.ciks.get(s).map(|c| (s.clone(), *c)))
                .collect();
            if ciks.is_empty() {
                bail!(
                    "earnings_drift needs SEC company ids: set symbols_file to a file with \
                     SYMBOL,CIK lines (see universes/sp500.csv)"
                );
            }
            let edgar = Edgar::new(&cfg.edgar.user_agent, cache_dir.join("edgar"));
            let max_age = match mode {
                Mode::Live => LIVE_REPORT_REFRESH,
                Mode::Backtest => Duration::from_secs(7 * 86_400),
            };
            println!("Loading financial reports for {} companies from SEC EDGAR...", ciks.len());
            let (reports, failed) = edgar.load_all(&ciks, max_age);
            println!("Financial reports loaded for {} companies ({} unavailable)", reports.len(), failed.len());
            if reports.is_empty() {
                bail!("could not load any financial reports from SEC EDGAR");
            }
            Box::new(EarningsDrift {
                long_sue: *long_sue,
                short_sue: *short_sue,
                hold_days: *hold_days,
                weight: *position_weight,
                max_long: *max_long,
                max_short: *max_short,
                band: *rebalance_band,
                live: mode == Mode::Live,
                reports: RefCell::new(reports),
                loaded_at: Cell::new(Instant::now()),
                source: Some((edgar, ciks)),
            })
        }
        StrategyConfig::VwapTrend { position_weight, allow_short, flatten_minutes, rebalance_band } => {
            Box::new(VwapTrend {
                weight: *position_weight,
                allow_short: *allow_short,
                flatten_secs: *flatten_minutes as i64 * 60,
                band: *rebalance_band,
                bar_secs: cfg.timeframe.secs(),
            })
        }
        StrategyConfig::OpeningRange {
            range_minutes,
            atr_days,
            stop_atr,
            target_r,
            risk_pct,
            max_weight,
            allow_short,
            flatten_minutes,
            rebalance_band,
            top_n,
            min_rel_volume,
            min_price,
            min_atr,
        } => Box::new(OpeningRange {
            range_secs: *range_minutes as i64 * 60,
            atr_days: *atr_days,
            stop_atr: *stop_atr,
            target_r: *target_r,
            risk_pct: *risk_pct,
            max_weight: *max_weight,
            allow_short: *allow_short,
            flatten_secs: *flatten_minutes as i64 * 60,
            band: *rebalance_band,
            bar_secs: cfg.timeframe.secs(),
            bars_per_day: cfg.timeframe.bars_per_day(),
            top_n: *top_n,
            min_rel_volume: *min_rel_volume,
            min_price: *min_price,
            min_atr: *min_atr,
            gross_cap: cfg.risk.max_leverage,
        }),
        StrategyConfig::LeveragedIndex {
            index,
            risk_asset,
            leverage,
            safe_asset,
            sma_days,
            target_vol,
            vol_days,
            rebalance_band,
        } => Box::new(LeveragedIndex {
            index: index.to_uppercase(),
            risk_asset: risk_asset.to_uppercase(),
            leverage: *leverage,
            safe_asset: safe_asset.to_uppercase(),
            sma_days: *sma_days,
            target_vol: *target_vol,
            vol_days: *vol_days,
            band: *rebalance_band,
            bars_per_day: cfg.timeframe.bars_per_day(),
            bars_per_year: cfg.timeframe.bars_per_year(),
        }),
        StrategyConfig::Tsmom {
            lookback_days,
            vol_days,
            target_vol,
            max_weight,
            max_long,
            max_short,
            allow_short,
            rebalance_band,
        } => Box::new(Tsmom {
            lookbacks: lookback_days.clone(),
            vol_days: *vol_days,
            target_vol: *target_vol,
            max_weight: *max_weight,
            max_long: *max_long,
            max_short: *max_short,
            allow_short: *allow_short,
            band: *rebalance_band,
        }),
        StrategyConfig::ValueMomentum {
            momentum_days,
            momentum_skip,
            value_days,
            value_skip,
            long_frac,
            short_frac,
            long_gross,
            short_gross,
            rebalance_band,
            index,
        } => Box::new(ValueMomentum {
            mom_days: *momentum_days,
            mom_skip: *momentum_skip,
            val_days: *value_days,
            val_skip: *value_skip,
            sides: Sides {
                long_frac: *long_frac,
                short_frac: *short_frac,
                long_gross: *long_gross,
                short_gross: *short_gross,
            },
            band: *rebalance_band,
            index: index.to_uppercase(),
        }),
        StrategyConfig::Profitability { long_frac, short_frac, long_gross, short_gross, rebalance_band, index } => {
            let ciks: Vec<(String, u64)> = cfg
                .symbols
                .iter()
                .filter_map(|s| cfg.ciks.get(s).map(|c| (s.clone(), *c)))
                .collect();
            if ciks.is_empty() {
                bail!(
                    "profitability needs SEC company ids: set symbols_file to a file with \
                     SYMBOL,CIK lines (see universes/sp500.csv)"
                );
            }
            let edgar = Edgar::new(&cfg.edgar.user_agent, cache_dir.join("edgar"));
            println!("Loading profits and balance sheets for {} companies from SEC EDGAR...", ciks.len());
            // Quarterly data: a week-old copy is fresh enough, live or not.
            let (data, failed) = edgar.load_profitability(&ciks, Duration::from_secs(7 * 86_400));
            println!("Loaded {} companies ({} unavailable)", data.len(), failed.len());
            if data.is_empty() {
                bail!("could not load any financial data from SEC EDGAR");
            }
            Box::new(Profitability {
                sides: Sides {
                    long_frac: *long_frac,
                    short_frac: *short_frac,
                    long_gross: *long_gross,
                    short_gross: *short_gross,
                },
                band: *rebalance_band,
                index: index.to_uppercase(),
                data,
            })
        }
        StrategyConfig::Combo { parts, rebalance_band, max_long, max_short } => {
            let mut built = Vec::new();
            for part in parts {
                let inner = build_kind(&part.strategy, cfg, mode, cache_dir)?;
                // Per-symbol strategies get a sleeve that tracks their own
                // virtual holdings and turns them into weights.
                let inner: Box<dyn Strategy> = if inner.is_portfolio() {
                    inner
                } else {
                    Box::new(Sleeve {
                        inner,
                        weight: part.position_pct,
                        max_positions: part.max_positions,
                        book: RefCell::new(None),
                    })
                };
                built.push((part.allocation, inner));
            }
            Box::new(Combo { parts: built, band: *rebalance_band, max_long: *max_long, max_short: *max_short })
        }
        StrategyConfig::SmaCross { fast, slow } => Box::new(SmaCross { fast: *fast, slow: *slow }),
        StrategyConfig::RsiReversion { period, oversold, exit_above } => {
            Box::new(RsiReversion { period: *period, oversold: *oversold, exit_above: *exit_above })
        }
        StrategyConfig::Breakout { entry_lookback, exit_lookback } => {
            Box::new(Breakout { entry_lookback: *entry_lookback, exit_lookback: *exit_lookback })
        }
        StrategyConfig::ConnorsRsi2 { rsi_period, entry_below, trend_sma, exit_sma } => {
            Box::new(ConnorsRsi2 {
                rsi_period: *rsi_period,
                entry_below: *entry_below,
                trend_sma: *trend_sma,
                exit_sma: *exit_sma,
            })
        }
        StrategyConfig::Bollinger { lookback, entry_z, exit_z } => {
            Box::new(Bollinger { lookback: *lookback, entry_z: *entry_z, exit_z: *exit_z })
        }
        StrategyConfig::IntradayMomentum { lookback_days, check_minutes } => {
            Box::new(IntradayMomentum {
                lookback_days: *lookback_days,
                check_secs: *check_minutes as i64 * 60,
                bar_secs: cfg.timeframe.secs(),
                bars_per_day: cfg.timeframe.bars_per_day(),
            })
        }
        StrategyConfig::NoiseArea {
            lookback_days,
            vol_days,
            check_minutes,
            target_daily_vol,
            max_weight,
            allow_short,
            flatten_minutes,
            rebalance_band,
        } => Box::new(NoiseArea {
            lookback_days: *lookback_days,
            vol_days: *vol_days,
            check_secs: *check_minutes as i64 * 60,
            target_vol: *target_daily_vol,
            max_weight: *max_weight,
            allow_short: *allow_short,
            flatten_secs: *flatten_minutes as i64 * 60,
            band: *rebalance_band,
            bar_secs: cfg.timeframe.secs(),
            bars_per_day: cfg.timeframe.bars_per_day(),
        }),
        StrategyConfig::MonthlyTrend { months } => Box::new(MonthlyTrend { months: *months }),
        StrategyConfig::MomentumRotation { momentum_days, trend_sma, index_sma, top_n, index } => {
            Box::new(MomentumRotation {
                momentum_days: *momentum_days,
                trend_sma: *trend_sma,
                index_sma: *index_sma,
                top_n: *top_n,
                index: index.to_uppercase(),
                weight: cfg.risk.position_pct,
            })
        }
        StrategyConfig::TrendVolTarget {
            entry_lookback,
            exit_lookback,
            keltner_mult,
            vol_days,
            position_vol_target,
            max_weight,
            max_gross,
            rebalance_band,
            index,
            index_sma,
            park_cash_in_index,
            max_names,
        } => Box::new(TrendVolTarget {
            entry_lookback: *entry_lookback,
            exit_lookback: *exit_lookback,
            keltner_mult: *keltner_mult,
            vol_days: *vol_days,
            position_vol_target: *position_vol_target,
            max_weight: *max_weight,
            max_gross: *max_gross,
            band: *rebalance_band,
            index: index.to_uppercase(),
            index_sma: *index_sma,
            park_cash: *park_cash_in_index,
            max_names: *max_names,
        }),
    })
}

fn closes(bars: &[Bar]) -> Vec<f64> {
    bars.iter().map(|b| b.close).collect()
}

// ---------------------------------------------------------------------------
// Trend following: fast/slow moving-average crossover.

pub struct SmaCross {
    fast: usize,
    slow: usize,
}

impl Strategy for SmaCross {
    fn name(&self) -> String {
        format!("SMA cross ({}/{})", self.fast, self.slow)
    }

    fn warmup(&self) -> usize {
        self.slow + 1
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        if bars.len() < self.warmup() {
            return Signal::Hold;
        }
        let c = closes(bars);
        let prev = &c[..c.len() - 1];
        let (Some(f), Some(s), Some(pf), Some(ps)) = (
            sma(&c, self.fast),
            sma(&c, self.slow),
            sma(prev, self.fast),
            sma(prev, self.slow),
        ) else {
            return Signal::Hold;
        };
        if in_position {
            if f < s {
                return Signal::Sell;
            }
        } else if pf <= ps && f > s {
            // Enter only on a fresh upward cross, so a stopped-out trade is
            // not immediately re-entered in the same trend leg.
            return Signal::Buy;
        }
        Signal::Hold
    }
}

// ---------------------------------------------------------------------------
// Mean reversion: classic RSI oversold / recovered.

pub struct RsiReversion {
    period: usize,
    oversold: f64,
    exit_above: f64,
}

impl Strategy for RsiReversion {
    fn name(&self) -> String {
        format!(
            "RSI reversion (period {}, buy < {}, sell > {})",
            self.period, self.oversold, self.exit_above
        )
    }

    fn warmup(&self) -> usize {
        self.period * 3
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        if bars.len() < self.warmup() {
            return Signal::Hold;
        }
        let Some(r) = rsi(&closes(bars), self.period) else {
            return Signal::Hold;
        };
        if in_position && r > self.exit_above {
            Signal::Sell
        } else if !in_position && r < self.oversold {
            Signal::Buy
        } else {
            Signal::Hold
        }
    }
}

// ---------------------------------------------------------------------------
// Donchian channel breakout.

pub struct Breakout {
    entry_lookback: usize,
    exit_lookback: usize,
}

impl Strategy for Breakout {
    fn name(&self) -> String {
        format!(
            "Donchian breakout (entry {}, exit {})",
            self.entry_lookback, self.exit_lookback
        )
    }

    fn warmup(&self) -> usize {
        self.entry_lookback.max(self.exit_lookback) + 1
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        if bars.len() < self.warmup() {
            return Signal::Hold;
        }
        let (last, prior) = bars.split_last().unwrap();
        if in_position {
            let low = prior[prior.len() - self.exit_lookback..]
                .iter()
                .map(|b| b.low)
                .fold(f64::INFINITY, f64::min);
            if last.close < low {
                return Signal::Sell;
            }
        } else {
            let high = prior[prior.len() - self.entry_lookback..]
                .iter()
                .map(|b| b.high)
                .fold(f64::NEG_INFINITY, f64::max);
            if last.close > high {
                return Signal::Buy;
            }
        }
        Signal::Hold
    }
}

// ---------------------------------------------------------------------------
// Connors & Alvarez, "Short Term Trading Strategies That Work" (2008):
// buy a sharp pullback (2-period RSI very low) in a stock that is in a
// long-term uptrend; sell when it closes back above its short moving average.

pub struct ConnorsRsi2 {
    rsi_period: usize,
    entry_below: f64,
    trend_sma: usize,
    exit_sma: usize,
}

impl Strategy for ConnorsRsi2 {
    fn name(&self) -> String {
        format!(
            "Connors RSI({}) pullback (buy < {}, above SMA{}, exit > SMA{})",
            self.rsi_period, self.entry_below, self.trend_sma, self.exit_sma
        )
    }

    fn warmup(&self) -> usize {
        self.trend_sma + 1
    }

    fn lookback(&self) -> usize {
        self.trend_sma + 60
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        if bars.len() < self.warmup() {
            return Signal::Hold;
        }
        let c = closes(bars);
        let last = *c.last().unwrap();
        if in_position {
            match sma(&c, self.exit_sma) {
                Some(m) if last > m => Signal::Sell,
                _ => Signal::Hold,
            }
        } else {
            // RSI only needs recent history; Wilder smoothing converges fast.
            let recent = &c[c.len().saturating_sub(self.rsi_period * 25 + 1)..];
            match (sma(&c, self.trend_sma), rsi(recent, self.rsi_period)) {
                (Some(trend), Some(r)) if last > trend && r < self.entry_below => Signal::Buy,
                _ => Signal::Hold,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Bollinger-band mean reversion (Chan, "Algorithmic Trading", 2013), long
// side only: buy when price is `entry_z` standard deviations below its moving
// average, sell when it has reverted to within `exit_z` of the average.

pub struct Bollinger {
    lookback: usize,
    entry_z: f64,
    exit_z: f64,
}

impl Strategy for Bollinger {
    fn name(&self) -> String {
        format!(
            "Bollinger mean reversion ({} bars, enter z < -{}, exit z > -{})",
            self.lookback, self.entry_z, self.exit_z
        )
    }

    fn warmup(&self) -> usize {
        self.lookback
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        if bars.len() < self.warmup() {
            return Signal::Hold;
        }
        let c = closes(bars);
        let (Some(mean), Some(sd)) = (sma(&c, self.lookback), stddev(&c, self.lookback)) else {
            return Signal::Hold;
        };
        if sd <= 0.0 {
            return Signal::Hold;
        }
        let z = (c[c.len() - 1] - mean) / sd;
        if in_position && z >= -self.exit_z {
            Signal::Sell
        } else if !in_position && z < -self.entry_z {
            Signal::Buy
        } else {
            Signal::Hold
        }
    }
}

// ---------------------------------------------------------------------------
// Zarattini, Aziz & Barbon, "Beat the Market: An Effective Intraday Momentum
// Strategy for S&P500 ETF (SPY)" (2024), long side only.
//
// For each time of day, the "noise area" is how far price has typically
// strayed from the open by that time over the last N sessions. A close above
// the upper edge of that area signals an abnormal (trend) day: go long, trail
// a stop at max(upper edge, VWAP), and always be flat before the close.

const SESSION_SECS: i64 = 23_400; // 9:30-16:00 ET

pub struct IntradayMomentum {
    lookback_days: usize,
    check_secs: i64,
    bar_secs: i64,
    bars_per_day: usize,
}

fn utc_day(b: &Bar) -> i64 {
    // The US regular session never crosses midnight UTC, so the UTC date
    // identifies the trading day.
    b.ts.div_euclid(86_400)
}

impl Strategy for IntradayMomentum {
    fn name(&self) -> String {
        format!(
            "Intraday momentum / noise area ({}-day, checks every {} min)",
            self.lookback_days,
            self.check_secs / 60
        )
    }

    fn warmup(&self) -> usize {
        (self.lookback_days + 1) * self.bars_per_day
    }

    fn lookback(&self) -> usize {
        (self.lookback_days + 3) * self.bars_per_day
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        let Some(last) = bars.last() else { return Signal::Hold };
        let today = utc_day(last);
        let (hist, cur) = bars.split_at(bars.partition_point(|b| utc_day(b) < today));
        let Some(prev) = hist.last() else { return Signal::Hold };
        let offset = last.ts - cur[0].ts;
        let bar_end = offset + self.bar_secs;
        let closing = bar_end >= SESSION_SECS - self.bar_secs;

        if in_position && closing {
            return Signal::Sell; // never hold overnight
        }

        // Average absolute move from the open to this time of day.
        let mut moves = Vec::with_capacity(self.lookback_days);
        let mut hi = hist.len();
        while hi > 0 && moves.len() < self.lookback_days {
            let d = utc_day(&hist[hi - 1]);
            let lo = hist[..hi].partition_point(|b| utc_day(b) < d);
            let day = &hist[lo..hi];
            let k = day.partition_point(|b| b.ts - day[0].ts <= offset);
            moves.push((day[k - 1].close / day[0].open - 1.0).abs());
            hi = lo;
        }
        if moves.len() < self.lookback_days {
            return Signal::Hold;
        }
        let sigma = moves.iter().sum::<f64>() / moves.len() as f64;
        let upper = cur[0].open.max(prev.close) * (1.0 + sigma);

        // As in the paper, both entries and the trailing stop are only
        // evaluated at the check marks (:00 and :30), not on every bar.
        if bar_end % self.check_secs != 0 {
            return Signal::Hold;
        }
        if in_position {
            let (mut pv, mut vol) = (0.0, 0.0);
            for b in cur {
                pv += (b.high + b.low + b.close) / 3.0 * b.volume;
                vol += b.volume;
            }
            let vwap = if vol > 0.0 { pv / vol } else { last.close };
            if last.close < upper.max(vwap) {
                return Signal::Sell;
            }
        } else if !closing && last.close > upper {
            return Signal::Buy;
        }
        Signal::Hold
    }
}

// ---------------------------------------------------------------------------
// The full version of the same paper: long above and short below the noise
// area, trailing exits at the VWAP, and position size set by a daily
// volatility target. Calm days get leverage (up to `max_weight`), rough days
// less. Like the opening range strategy it replays the day so far on every
// evaluation, so it needs no memory and survives restarts.

pub struct NoiseArea {
    lookback_days: usize,
    vol_days: usize,
    check_secs: i64,
    target_vol: f64,
    max_weight: f64,
    allow_short: bool,
    flatten_secs: i64,
    band: f64,
    bar_secs: i64,
    bars_per_day: usize,
}

impl NoiseArea {
    /// Average absolute move from the open to time-of-day `offset`, over the
    /// last `lookback_days` completed sessions.
    fn sigma(&self, hist: &[Bar], offset: i64) -> Option<f64> {
        let (mut sum, mut n) = (0.0, 0);
        let mut hi = hist.len();
        while hi > 0 && n < self.lookback_days {
            let d = utc_day(&hist[hi - 1]);
            let lo = hist[..hi].partition_point(|b| utc_day(b) < d);
            let day = &hist[lo..hi];
            let k = day.partition_point(|b| b.ts - day[0].ts <= offset).max(1);
            sum += (day[k - 1].close / day[0].open - 1.0).abs();
            n += 1;
            hi = lo;
        }
        (n == self.lookback_days).then(|| sum / n as f64)
    }

    /// Standard deviation of the last `vol_days` daily close-to-close returns.
    fn daily_vol(&self, hist: &[Bar]) -> Option<f64> {
        let mut closes = Vec::with_capacity(self.vol_days + 1);
        let mut hi = hist.len();
        while hi > 0 && closes.len() <= self.vol_days {
            let d = utc_day(&hist[hi - 1]);
            closes.push(hist[hi - 1].close);
            hi = hist[..hi].partition_point(|b| utc_day(b) < d);
        }
        if closes.len() <= self.vol_days {
            return None;
        }
        let rets: Vec<f64> = closes.windows(2).map(|w| w[0] / w[1] - 1.0).collect();
        let mean = rets.iter().sum::<f64>() / rets.len() as f64;
        Some((rets.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / (rets.len() - 1) as f64).sqrt())
    }

    /// Signed target weight for one symbol right now.
    fn weight(&self, bars: &[Bar]) -> f64 {
        let Some(last) = bars.last() else { return 0.0 };
        let today = utc_day(last);
        let (hist, cur) = bars.split_at(bars.partition_point(|b| utc_day(b) < today));
        let (Some(prev), Some(dvol)) = (hist.last(), self.daily_vol(hist)) else { return 0.0 };
        if dvol <= 0.0 {
            return 0.0;
        }
        let size = (self.target_vol / dvol).min(self.max_weight);
        let open = cur[0].open;
        let (up_ref, dn_ref) = (open.max(prev.close), open.min(prev.close));

        // Replay the day: positions change only at the check marks.
        let (mut pos, mut pv, mut vol) = (0.0f64, 0.0, 0.0);
        for b in cur {
            pv += (b.high + b.low + b.close) / 3.0 * b.volume;
            vol += b.volume;
            let offset = b.ts - cur[0].ts;
            let bar_end = offset + self.bar_secs;
            if bar_end >= SESSION_SECS - self.flatten_secs {
                return 0.0;
            }
            if bar_end % self.check_secs != 0 {
                continue;
            }
            let Some(sigma) = self.sigma(hist, offset) else { return 0.0 };
            let (upper, lower) = (up_ref * (1.0 + sigma), dn_ref * (1.0 - sigma));
            let vwap = if vol > 0.0 { pv / vol } else { b.close };
            let was = pos;
            if (pos > 0.0 && b.close < upper.max(vwap)) || (pos < 0.0 && b.close > lower.min(vwap)) {
                pos = 0.0;
            }
            if was == 0.0 {
                if b.close > upper {
                    pos = 1.0;
                } else if b.close < lower && self.allow_short {
                    pos = -1.0;
                }
            }
        }
        pos * size
    }
}

impl Strategy for NoiseArea {
    fn name(&self) -> String {
        format!(
            "Noise-area momentum ({}-day bands, {:.1}% daily vol target, up to {}x{})",
            self.lookback_days,
            self.target_vol * 100.0,
            self.max_weight,
            if self.allow_short { ", long/short" } else { ", long only" }
        )
    }

    fn warmup(&self) -> usize {
        (self.lookback_days.max(self.vol_days) + 2) * self.bars_per_day
    }

    fn lookback(&self) -> usize {
        (self.lookback_days.max(self.vol_days) + 4) * self.bars_per_day
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let newest = universe.values().filter_map(|b| b.last()).map(|b| b.ts).max()?;
        let mut out: Vec<(String, f64)> = universe
            .iter()
            .filter(|(_, b)| b.last().is_some_and(|l| newest - l.ts <= 2 * self.bar_secs))
            .map(|(s, b)| (s.to_string(), self.weight(b)))
            .filter(|t| t.1 != 0.0)
            .collect();
        for side in [1.0, -1.0] {
            let gross: f64 = out.iter().filter(|t| t.1 * side > 0.0).map(|t| t.1.abs()).sum();
            if gross > self.max_weight {
                let k = self.max_weight / gross;
                out.iter_mut().filter(|t| t.1 * side > 0.0).for_each(|t| t.1 *= k);
            }
        }
        out.sort_by(|a, b| a.0.cmp(&b.0));
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Faber, "A Quantitative Approach to Tactical Asset Allocation" (2007):
// hold an asset only while its last month-end close is above the average of
// its last N month-end closes. Runs on daily bars.

pub struct MonthlyTrend {
    months: usize,
}

fn month_key(ts: i64) -> i32 {
    let d = chrono::DateTime::from_timestamp(ts, 0).unwrap_or_default();
    d.year() * 12 + d.month() as i32
}

impl Strategy for MonthlyTrend {
    fn name(&self) -> String {
        format!("Faber monthly trend ({}-month moving average)", self.months)
    }

    fn warmup(&self) -> usize {
        self.months * 22 + 5
    }

    fn lookback(&self) -> usize {
        (self.months + 2) * 23
    }

    fn signal(&self, bars: &[Bar], in_position: bool) -> Signal {
        // Closing price of every completed month in the window.
        let mut month_ends = Vec::new();
        let mut key = match bars.first() {
            Some(b) => month_key(b.ts),
            None => return Signal::Hold,
        };
        for w in bars.windows(2) {
            let k = month_key(w[1].ts);
            if k != key {
                month_ends.push(w[0].close);
                key = k;
            }
        }
        let Some(avg) = sma(&month_ends, self.months) else { return Signal::Hold };
        let last = month_ends[month_ends.len() - 1];
        if last > avg && !in_position {
            Signal::Buy
        } else if last < avg && in_position {
            Signal::Sell
        } else {
            Signal::Hold
        }
    }
}

// ---------------------------------------------------------------------------
// Clenow, "Stocks on the Move" (2015): once a week, rank the universe by
// volatility-adjusted momentum (annualised slope of an exponential regression
// over ~90 days, multiplied by its R-squared). Hold the top names; drop any
// that fall out of the top group or below their 100-day average; only open
// new positions while the index is above its 200-day average.
// Simplification: positions are equal-weighted (risk.position_pct) instead of
// the book's ATR-based risk parity.

pub struct MomentumRotation {
    momentum_days: usize,
    trend_sma: usize,
    index_sma: usize,
    top_n: usize,
    index: String,
    weight: f64,
}

fn week_key(ts: i64) -> i64 {
    // Weeks starting on Monday (1970-01-05 was a Monday).
    (ts.div_euclid(86_400) + 3).div_euclid(7)
}

impl MomentumRotation {
    fn score(&self, bars: &[Bar]) -> Option<f64> {
        if bars.len() < self.momentum_days.max(self.trend_sma) + 1 {
            return None;
        }
        let c = closes(bars);
        let last = c[c.len() - 1];
        if last <= sma(&c, self.trend_sma)? {
            return None;
        }
        let window = &c[c.len() - self.momentum_days - 1..];
        // Skip stocks with a >15% single-day jump (earnings gaps, deal news).
        if window.windows(2).any(|w| (w[1] / w[0] - 1.0).abs() > 0.15) {
            return None;
        }
        let logs: Vec<f64> = window[1..].iter().map(|v| v.ln()).collect();
        let (slope, r2) = linreg(&logs)?;
        let score = ((slope * 252.0).exp() - 1.0) * r2;
        (score > 0.0).then_some(score)
    }
}

impl Strategy for MomentumRotation {
    fn name(&self) -> String {
        format!(
            "Clenow momentum rotation (top {}, {}-day momentum, weekly)",
            self.top_n, self.momentum_days
        )
    }

    fn warmup(&self) -> usize {
        self.index_sma.max(self.trend_sma).max(self.momentum_days) + 1
    }

    fn lookback(&self) -> usize {
        self.warmup() + 10
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, held: &[&str]) -> Option<Vec<(String, f64)>> {
        // Rebalance on the first bar of each week.
        let reference = universe
            .get(self.index.as_str())
            .copied()
            .or_else(|| universe.values().copied().max_by_key(|b| b.len()))?;
        let n = reference.len();
        if n < 2 || week_key(reference[n - 1].ts) == week_key(reference[n - 2].ts) {
            return None;
        }

        let market_ok = match universe.get(self.index.as_str()) {
            Some(b) => match sma(&closes(b), self.index_sma) {
                Some(avg) => b[b.len() - 1].close > avg,
                None => false,
            },
            None => true,
        };

        let mut ranked: Vec<(f64, &str)> = universe
            .iter()
            .filter(|(s, _)| **s != self.index)
            .filter_map(|(s, b)| self.score(b).map(|sc| (sc, *s)))
            .collect();
        ranked.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(b.1)));
        let top: Vec<&str> = ranked.iter().take(self.top_n).map(|r| r.1).collect();

        let mut out: Vec<(String, f64)> = top
            .iter()
            .filter(|s| held.contains(s))
            .map(|s| (s.to_string(), self.weight))
            .collect();
        if market_ok {
            for s in &top {
                if out.len() >= self.top_n {
                    break;
                }
                if !held.contains(s) {
                    out.push((s.to_string(), self.weight));
                }
            }
        }
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Volatility-sized trend following. A long-only, unleveraged synthesis of:
//   - Zarattini & Antonacci, "A Century of Profitable Industry Trends" (2024):
//     enter when the close breaks above the 20-day Donchian or Keltner upper
//     band; exit on a trailing stop at the 40-day lower band that is never
//     lowered; size every position to contribute equal risk.
//   - Zarattini, Pagani & Wilcox, "Does Trend-Following Still Work on
//     Stocks?" (2025): turnover control, so small accounts are not eaten by
//     trading costs (positions are only resized outside a tolerance band).
//   - Faber-style regime filter for idle cash: whatever the trend book does
//     not use is parked in the index while the index is above its long-term
//     average, instead of sitting in cash.
//
// The strategy is a pure function of the bars: each evaluation replays the
// entry/stop rules over the lookback window to find out whether a symbol is
// currently in a trend. That makes live trading restart-safe and identical
// to the backtest.

pub struct TrendVolTarget {
    entry_lookback: usize,
    exit_lookback: usize,
    keltner_mult: f64,
    vol_days: usize,
    /// Annualised volatility each position should contribute.
    position_vol_target: f64,
    max_weight: f64,
    /// Cap on total invested fraction (1.0 = no leverage).
    max_gross: f64,
    band: f64,
    index: String,
    index_sma: usize,
    park_cash: bool,
    max_names: Option<usize>,
}

impl TrendVolTarget {
    /// Replay the rules over `bars`; true if the symbol is in a trend now.
    fn in_trend(&self, bars: &[Bar]) -> bool {
        let (n_in, n_out) = (self.entry_lookback, self.exit_lookback);
        let start = n_in.max(n_out) + 1;
        if bars.len() <= start {
            return false;
        }
        // True range per bar (index 0 has no previous close).
        let tr: Vec<f64> = (0..bars.len())
            .map(|i| {
                let b = &bars[i];
                if i == 0 {
                    b.high - b.low
                } else {
                    let pc = bars[i - 1].close;
                    (b.high - b.low).max((b.high - pc).abs()).max((b.low - pc).abs())
                }
            })
            .collect();
        let (k_in, k_out) = (2.0 / (n_in as f64 + 1.0), 2.0 / (n_out as f64 + 1.0));
        let (mut ema_in, mut ema_out) = (bars[0].close, bars[0].close);
        let mut long = false;
        let mut stop = f64::NEG_INFINITY;

        // Rolling window state, so the replay is linear in the number of
        // bars (this runs for every symbol on every bar). Before bar i is
        // examined, each structure covers the bars strictly before i.
        let mut highs: VecDeque<usize> = VecDeque::new(); // indices, highs decreasing
        let mut lows: VecDeque<usize> = VecDeque::new(); // indices, lows increasing
        let (mut tr_in, mut tr_out) = (0.0, 0.0);
        let mut push = |i: usize, highs: &mut VecDeque<usize>, lows: &mut VecDeque<usize>| {
            while highs.back().is_some_and(|&j| bars[j].high <= bars[i].high) {
                highs.pop_back();
            }
            highs.push_back(i);
            if highs.front().is_some_and(|&j| j + n_in <= i) {
                highs.pop_front();
            }
            while lows.back().is_some_and(|&j| bars[j].low >= bars[i].low) {
                lows.pop_back();
            }
            lows.push_back(i);
            if lows.front().is_some_and(|&j| j + n_out <= i) {
                lows.pop_front();
            }
            tr_in += tr[i] - if i >= n_in { tr[i - n_in] } else { 0.0 };
            tr_out += tr[i] - if i >= n_out { tr[i - n_out] } else { 0.0 };
            (tr_in, tr_out)
        };
        let (mut sum_in, mut sum_out) = push(0, &mut highs, &mut lows);

        for i in 1..bars.len() {
            // Bands are built from bars strictly before bar i.
            if i >= start {
                let hi = bars[highs[0]].high;
                let lo = bars[lows[0]].low;
                let atr_in = sum_in / n_in as f64;
                let atr_out = sum_out / n_out as f64;
                let upper = hi.min(ema_in + self.keltner_mult * atr_in);
                let lower = lo.max(ema_out - self.keltner_mult * atr_out);
                let close = bars[i].close;
                if long {
                    stop = stop.max(lower); // ratchet: never lowered
                    if close < stop {
                        long = false;
                    }
                } else if close > upper {
                    long = true;
                    stop = lower;
                }
            }
            ema_in += k_in * (bars[i].close - ema_in);
            ema_out += k_out * (bars[i].close - ema_out);
            (sum_in, sum_out) = push(i, &mut highs, &mut lows);
        }
        long
    }

    /// Annualised volatility of daily returns over the last `vol_days` bars.
    fn volatility(&self, bars: &[Bar]) -> Option<f64> {
        if bars.len() < self.vol_days + 1 {
            return None;
        }
        let rets: Vec<f64> = bars[bars.len() - self.vol_days - 1..]
            .windows(2)
            .map(|w| w[1].close / w[0].close - 1.0)
            .collect();
        let sd = stddev(&rets, rets.len())?;
        Some(sd * 252f64.sqrt())
    }
}

impl Strategy for TrendVolTarget {
    fn name(&self) -> String {
        format!(
            "Volatility-sized trend following ({}/{}-day channels{})",
            self.entry_lookback,
            self.exit_lookback,
            if self.park_cash { format!(", idle cash in {}", self.index) } else { String::new() }
        )
    }

    fn warmup(&self) -> usize {
        // Long enough for the replay to settle and for the index average.
        (self.exit_lookback * 4).max(self.index_sma + 1)
    }

    fn lookback(&self) -> usize {
        self.warmup() + 20
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, held: &[&str]) -> Option<Vec<(String, f64)>> {
        // (symbol, weight, already held, trend strength)
        let mut picks: Vec<(&str, f64, bool, f64)> = Vec::new();
        for (sym, bars) in universe {
            if *sym == self.index || !self.in_trend(bars) {
                continue;
            }
            let Some(vol) = self.volatility(bars) else { continue };
            // Inverse-volatility sizing: calm stocks get more capital.
            let w = if vol > 0.0 { self.position_vol_target / vol } else { self.max_weight };
            // Strength = six-month return per unit of volatility.
            let back = bars.len().saturating_sub(127);
            let strength = (bars[bars.len() - 1].close / bars[back].close - 1.0) / vol.max(1e-9);
            picks.push((*sym, w.min(self.max_weight), held.contains(sym), strength));
        }
        if let Some(cap) = self.max_names {
            // Names already held keep their place while they still trend
            // (avoids churning); free slots go to the strongest trends.
            picks.sort_by(|a, b| b.2.cmp(&a.2).then(b.3.total_cmp(&a.3)).then(a.0.cmp(b.0)));
            picks.truncate(cap);
        }
        let mut out: Vec<(String, f64)> = picks.iter().map(|p| (p.0.to_string(), p.1)).collect();
        // Largest weights first; ties broken by name so results are reproducible.
        out.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));

        // No leverage: scale everything down if the book is oversubscribed.
        let gross: f64 = out.iter().map(|t| t.1).sum();
        if gross > self.max_gross {
            let k = self.max_gross / gross;
            out.iter_mut().for_each(|t| t.1 *= k);
        }

        // Park unused capital in the index while the market regime is healthy.
        if self.park_cash {
            if let Some(ib) = universe.get(self.index.as_str()) {
                let spare = self.max_gross - out.iter().map(|t| t.1).sum::<f64>();
                let healthy = match sma(&closes(ib), self.index_sma) {
                    Some(avg) => ib[ib.len() - 1].close > avg,
                    None => false,
                };
                if healthy && spare > 0.005 {
                    out.push((self.index.clone(), spare));
                }
            }
        }
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Long/short cross-sectional momentum (Jegadeesh & Titman, 1993): once a
// month, rank every stock by its return over the past year, skipping the most
// recent month. Buy the strongest group and short the weakest group.
//
// The ranking is always computed as of the last completed month, so the
// strategy is a pure function of the bars and safe to restart at any time.

pub struct LsMomentum {
    lookback: usize,
    skip: usize,
    long_frac: f64,
    short_frac: f64,
    /// Total weight of the long side / the short side.
    long_gross: f64,
    short_gross: f64,
    band: f64,
    index: String,
    /// "", "return", "risk_adjusted", "high52" or "random" (see the config).
    score: String,
    seed: u64,
}

impl Strategy for LsMomentum {
    fn name(&self) -> String {
        format!(
            "Long/short momentum ({}-{} day, long top {:.0}% / short bottom {:.0}%, monthly)",
            self.lookback,
            self.skip,
            self.long_frac * 100.0,
            self.short_frac * 100.0
        )
    }

    fn warmup(&self) -> usize {
        self.lookback + 25
    }

    fn lookback(&self) -> usize {
        self.lookback + 50
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let reference = universe
            .get(self.index.as_str())
            .copied()
            .or_else(|| universe.values().copied().max_by_key(|b| b.len()))?;
        // Last bar of the most recently completed month.
        let Some(j) = (1..reference.len())
            .rev()
            .find(|&i| month_key(reference[i].ts) != month_key(reference[i - 1].ts))
        else {
            return Some(Vec::new());
        };
        let cutoff = utc_day(&reference[j - 1]);
        let today = utc_day(&reference[reference.len() - 1]);

        let mut scores: Vec<(f64, &str)> = Vec::new();
        for (sym, bars) in universe {
            if *sym == self.index {
                continue;
            }
            let end = bars.partition_point(|b| utc_day(b) <= cutoff);
            // Needs a full year of history, a current quote, and a non-penny price.
            if end < self.lookback + 1 || utc_day(&bars[bars.len() - 1]) + 5 < today {
                continue;
            }
            let (recent, past) = (bars[end - 1 - self.skip].close, bars[end - 1 - self.lookback].close);
            if past <= 0.0 || bars[end - 1].close < 5.0 {
                continue;
            }
            let ret = recent / past - 1.0;
            let score = match self.score.as_str() {
                "risk_adjusted" => {
                    // Return per unit of daily volatility over the same window.
                    let w = &bars[end - 1 - self.lookback..=end - 1 - self.skip];
                    let rets: Vec<f64> = w.windows(2).map(|p| p[1].close / p[0].close - 1.0).collect();
                    let mean = rets.iter().sum::<f64>() / rets.len() as f64;
                    let sd = (rets.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / rets.len() as f64).sqrt();
                    ret / sd.max(1e-6)
                }
                "random" => {
                    // A placebo: the same universe and rebalance dates, but
                    // the picks are a fixed pseudo-random draw per month.
                    use std::hash::{Hash, Hasher};
                    let mut h = std::collections::hash_map::DefaultHasher::new();
                    (self.seed, *sym, month_key(reference[j].ts)).hash(&mut h);
                    (h.finish() >> 11) as f64 / (1u64 << 53) as f64
                }
                "high52" => {
                    let lo = end.saturating_sub(252);
                    let high = bars[lo..end].iter().map(|b| b.close).fold(f64::MIN, f64::max);
                    bars[end - 1].close / high
                }
                _ => ret,
            };
            scores.push((score, sym));
        }
        scores.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(b.1)));

        let n = scores.len();
        let pick = |frac: f64| if frac > 0.0 { ((n as f64 * frac).round() as usize).max(1) } else { 0 };
        let (n_long, n_short) = (pick(self.long_frac), pick(self.short_frac));
        if n == 0 || n_long + n_short > n {
            return Some(Vec::new());
        }
        let mut out = Vec::with_capacity(n_long + n_short);
        for s in &scores[..n_long] {
            out.push((s.1.to_string(), self.long_gross / n_long as f64));
        }
        for s in &scores[n - n_short..] {
            out.push((s.1.to_string(), -self.short_gross / n_short as f64));
        }
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Intraday long/short cross-sectional momentum: the same ranking as
// `LsMomentum`, but measured over the last N trading days of intraday bars and
// rebalanced once a day, shortly before the close. Positions are held
// overnight.
//
// The strategy only returns targets on the bar that starts two bars before the
// 16:00 ET close. That bar closes with one poll interval left before the
// market shuts, so the live engine can still act on it. On every other bar it
// returns None, which tells the engine to keep the existing book. The decision
// is a pure function of the bars, so restarts are safe.

pub struct IntradayLsMomentum {
    /// Momentum window and skipped days, both in trading days.
    lookback: usize,
    skip: usize,
    long_frac: f64,
    short_frac: f64,
    /// Total weight of the long side / the short side.
    long_gross: f64,
    short_gross: f64,
    band: f64,
    index: String,
    bars_per_day: usize,
    bar_secs: i64,
    /// 0 = once a day near the close. Otherwise also every this many minutes
    /// after the open, ranking on prices that include today's move.
    rebalance_mins: i32,
}

impl IntradayLsMomentum {
    /// True when the bar starting at `ts` ends on one of the intraday
    /// re-ranking times (and early enough to still trade before the close).
    fn is_intraday_rebalance_bar(&self, ts: i64) -> bool {
        if self.rebalance_mins <= 0 {
            return false;
        }
        let end = et_minute_of_day(ts) + (self.bar_secs / 60) as i32;
        let since_open = end - (9 * 60 + 30);
        since_open > 0 && since_open % self.rebalance_mins == 0 && end <= 15 * 60 + 50
    }
}

/// US Eastern offset (seconds east of UTC), following the US DST rule: EDT
/// from the second Sunday of March to the first Sunday of November, EST
/// otherwise.
fn us_eastern_offset_secs(ts: i64) -> i64 {
    let dt = chrono::DateTime::from_timestamp(ts, 0)
        .map(|d| d.naive_utc())
        .unwrap_or_default();
    let dst_start = nth_sunday(dt.year(), 3, 2).and_hms_opt(7, 0, 0).unwrap();
    let dst_end = nth_sunday(dt.year(), 11, 1).and_hms_opt(6, 0, 0).unwrap();
    if dt >= dst_start && dt < dst_end { -4 * 3600 } else { -5 * 3600 }
}

/// The `n`-th Sunday of a month (1-based).
fn nth_sunday(year: i32, month: u32, n: u32) -> NaiveDate {
    let first = NaiveDate::from_ymd_opt(year, month, 1).unwrap();
    let first_sunday = 1 + (7 - first.weekday().num_days_from_sunday()) % 7;
    NaiveDate::from_ymd_opt(year, month, first_sunday + 7 * (n - 1)).unwrap()
}

fn et_minute_of_day(ts: i64) -> i32 {
    let local = ts + us_eastern_offset_secs(ts);
    (local.rem_euclid(86_400) / 60) as i32
}

/// True on the bar that starts two bars before the 16:00 ET close. That bar
/// is complete with one poll interval left before the market shuts.
fn is_daily_rebalance_bar(ts: i64, bar_secs: i64) -> bool {
    et_minute_of_day(ts) + 2 * (bar_secs / 60) as i32 == 16 * 60
}

impl Strategy for IntradayLsMomentum {
    fn name(&self) -> String {
        format!(
            "Intraday long/short momentum ({}-{} day, daily near the close, long top {:.0}% / short bottom {:.0}%)",
            self.lookback,
            self.skip,
            self.long_frac * 100.0,
            self.short_frac * 100.0
        )
    }

    fn warmup(&self) -> usize {
        (self.lookback + 2) * self.bars_per_day
    }

    fn lookback(&self) -> usize {
        // Enough intraday bars for the momentum window plus a few sessions.
        (self.lookback + 4) * self.bars_per_day
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let reference = universe
            .get(self.index.as_str())
            .copied()
            .or_else(|| universe.values().copied().max_by_key(|b| b.len()))?;
        let last = reference.last()?;
        // On daily bars every bar is a rebalance: rank on the sessions before
        // it and trade at its close, which is what the intraday version does
        // a few minutes earlier.
        let active = self.rebalance_mins > 0;
        if self.bar_secs < 86_400
            && !is_daily_rebalance_bar(last.ts, self.bar_secs)
            && !self.is_intraday_rebalance_bar(last.ts)
        {
            return None;
        }
        let today = utc_day(last);
        // Last session that has finished by the time today's near-close bar
        // prints (weekends and holidays simply skip).
        let last_completed = reference.iter().rev().map(utc_day).find(|d| *d < today)?;

        let mut scores: Vec<(f64, &str)> = Vec::new();
        for (sym, bars) in universe {
            if *sym == self.index {
                continue;
            }
            // Last close of every completed session. Today's partial bars are
            // excluded: the ranking is a pure function of finished days.
            let mut days: Vec<(i64, f64)> = Vec::new();
            for b in *bars {
                let d = utc_day(b);
                // Re-ranking through the day counts today's latest price as
                // the newest "close"; the once-a-day version stops at
                // yesterday.
                if d > today || (d == today && !active) {
                    break;
                }
                match days.last_mut() {
                    Some(prev) if prev.0 == d => prev.1 = b.close,
                    _ => days.push((d, b.close)),
                }
            }
            let end = days.len();
            if end < self.lookback + 1 {
                continue;
            }
            let (last_day, last_close) = days[end - 1];
            // Needs a recent quote and a non-penny price.
            if last_day + 5 < last_completed || last_close < 5.0 {
                continue;
            }
            // When today's price is part of the ranking, every stock must
            // actually have traded today, or the days would not line up.
            if active && last_day != today {
                continue;
            }
            let (_, recent) = days[end - 1 - self.skip];
            let (_, past) = days[end - 1 - self.lookback];
            if past <= 0.0 {
                continue;
            }
            scores.push((recent / past - 1.0, *sym));
        }
        scores.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(b.1)));

        let n = scores.len();
        let pick = |frac: f64| if frac > 0.0 { ((n as f64 * frac).round() as usize).max(1) } else { 0 };
        let (n_long, n_short) = (pick(self.long_frac), pick(self.short_frac));
        if n == 0 || n_long + n_short > n {
            // Not enough names: keep the current book rather than liquidate.
            return None;
        }
        let mut out = Vec::with_capacity(n_long + n_short);
        for s in &scores[..n_long] {
            out.push((s.1.to_string(), self.long_gross / n_long as f64));
        }
        for s in &scores[n - n_short..] {
            out.push((s.1.to_string(), -self.short_gross / n_short as f64));
        }
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Earnings surprise (post-earnings-announcement drift; Ball & Brown 1968,
// Bernard & Thomas 1989). Reads each company's quarterly financial report
// from SEC EDGAR as soon as it is filed, scores how surprising the profit
// was (see edgar.rs), and the next trading day takes a large position:
// long after a strongly positive surprise, short after a strongly negative
// one. Positions are held for a fixed number of days.

pub struct EarningsDrift {
    long_sue: f64,
    short_sue: f64,
    /// Calendar days to hold after the filing.
    hold_days: i64,
    /// Size of every position, as a fraction of equity.
    weight: f64,
    max_long: f64,
    max_short: f64,
    band: f64,
    live: bool,
    reports: RefCell<HashMap<String, Vec<Report>>>,
    loaded_at: Cell<Instant>,
    /// Where to re-download reports from during a live session.
    source: Option<(Edgar, Vec<(String, u64)>)>,
}

impl Strategy for EarningsDrift {
    fn name(&self) -> String {
        format!(
            "Earnings surprise (long SUE >= {}, short SUE <= {}, {:.0}% positions, hold {} days)",
            self.long_sue,
            self.short_sue,
            self.weight * 100.0,
            self.hold_days
        )
    }

    fn warmup(&self) -> usize {
        2
    }

    fn lookback(&self) -> usize {
        10
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        // Live: pick up reports filed since the last check.
        if self.live && self.loaded_at.get().elapsed() > LIVE_REPORT_REFRESH {
            if let Some((edgar, ciks)) = &self.source {
                let (fresh, _) = edgar.load_all(ciks, LIVE_REPORT_REFRESH);
                if !fresh.is_empty() {
                    *self.reports.borrow_mut() = fresh;
                }
            }
            self.loaded_at.set(Instant::now());
        }

        let today = universe.values().filter_map(|b| b.last()).map(utc_day).max()?;
        let reports = self.reports.borrow();
        let (mut longs, mut shorts): (Vec<(f64, &str)>, Vec<(f64, &str)>) = (Vec::new(), Vec::new());
        for (sym, bars) in universe {
            let (Some(list), Some(last)) = (reports.get(*sym), bars.last()) else { continue };
            if utc_day(last) + 5 < today {
                continue; // no current quote
            }
            // Most recent report that was public before this decision.
            let known = list.partition_point(|r| if self.live { r.filed <= today } else { r.filed < today });
            let Some(r) = known.checked_sub(1).map(|i| list[i]) else { continue };
            if today - r.filed > self.hold_days {
                continue;
            }
            if r.sue >= self.long_sue {
                longs.push((r.sue, sym));
            } else if r.sue <= self.short_sue {
                shorts.push((r.sue, sym));
            }
        }
        // Biggest surprises first.
        longs.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(b.1)));
        shorts.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(b.1)));
        let slots = |cap: f64| (cap / self.weight + 1e-9).floor() as usize;

        let mut out: Vec<(String, f64)> = Vec::new();
        out.extend(longs.iter().take(slots(self.max_long)).map(|l| (l.1.to_string(), self.weight)));
        out.extend(shorts.iter().take(slots(self.max_short)).map(|s| (s.1.to_string(), -self.weight)));
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// VWAP trend (Zarattini & Aziz, 2023, "Volume Weighted Average Price (VWAP)
// The Holy Grail for Day Trading Systems"). Built for 1-minute bars: after
// every bar, be long if the close is above the session's volume-weighted
// average price and short if it is below. Everything is closed shortly
// before the end of the session; nothing is held overnight.

pub struct VwapTrend {
    /// Position size per symbol, as a fraction of equity.
    weight: f64,
    allow_short: bool,
    /// Go flat this many seconds before the session ends.
    flatten_secs: i64,
    band: f64,
    bar_secs: i64,
}

impl VwapTrend {
    /// +1 long, -1 short, 0 flat for one symbol, from its own bars.
    fn side(&self, bars: &[Bar]) -> f64 {
        let Some(last) = bars.last() else { return 0.0 };
        let today = utc_day(last);
        let cur = &bars[bars.partition_point(|b| utc_day(b) < today)..];
        let bar_end = last.ts - cur[0].ts + self.bar_secs;
        if bar_end >= SESSION_SECS - self.flatten_secs {
            return 0.0;
        }
        let (mut pv, mut vol) = (0.0, 0.0);
        for b in cur {
            pv += (b.high + b.low + b.close) / 3.0 * b.volume;
            vol += b.volume;
        }
        if vol <= 0.0 {
            return 0.0;
        }
        let vwap = pv / vol;
        if last.close > vwap {
            1.0
        } else if last.close < vwap && self.allow_short {
            -1.0
        } else {
            0.0
        }
    }
}

impl Strategy for VwapTrend {
    fn name(&self) -> String {
        format!(
            "VWAP trend ({}, {:.0}% per symbol, flat {} min before close)",
            if self.allow_short { "long/short" } else { "long only" },
            self.weight * 100.0,
            self.flatten_secs / 60
        )
    }

    fn warmup(&self) -> usize {
        1
    }

    fn lookback(&self) -> usize {
        // One full session is all it ever looks at.
        (SESSION_SECS / self.bar_secs) as usize + 10
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let newest = universe.values().filter_map(|b| b.last()).map(|b| b.ts).max()?;
        let mut out: Vec<(String, f64)> = universe
            .iter()
            // A symbol whose latest bar is old (no recent trades) is left flat.
            .filter(|(_, b)| b.last().is_some_and(|l| newest - l.ts <= 2 * self.bar_secs))
            .map(|(s, b)| (s.to_string(), self.side(b) * self.weight))
            .filter(|t| t.1 != 0.0)
            .collect();
        out.sort_by(|a, b| a.0.cmp(&b.0));
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Opening range breakout (Zarattini & Aziz, 2023, "Can Day Trading Really Be
// Profitable?"). One trade per symbol per day: when the first few minutes of
// the session close above the open, go long (below: short). The stop sits a
// small fraction of the stock's average daily range away from the entry, the
// profit target a multiple of that distance, and whatever is still open is
// closed before the end of the session. Position size is set so that a
// stopped-out trade costs a fixed fraction of the account, capped at
// `max_weight` (the paper allows 4x leverage; this does not).
//
// Like the trend strategy, it replays the day so far on every evaluation, so
// it needs no memory and survives restarts.

pub struct OpeningRange {
    range_secs: i64,
    atr_days: usize,
    /// Stop distance as a fraction of the average daily range.
    stop_atr: f64,
    /// Profit target as a multiple of the stop distance.
    target_r: f64,
    /// Fraction of equity lost if the stop is hit.
    risk_pct: f64,
    max_weight: f64,
    allow_short: bool,
    flatten_secs: i64,
    band: f64,
    bar_secs: i64,
    bars_per_day: usize,
    /// Stocks in play (Zarattini, Barbon & Aziz, 2024): keep only the
    /// `top_n` symbols by relative opening volume (0 = all).
    top_n: usize,
    min_rel_volume: f64,
    min_price: f64,
    min_atr: f64,
    /// Most the long (or short) side may add up to, as a multiple of equity.
    gross_cap: f64,
}

impl OpeningRange {
    /// From the last `atr_days` completed sessions: the average true range,
    /// and the average volume traded during the opening range.
    fn history_stats(&self, hist: &[Bar]) -> Option<(f64, f64)> {
        let (mut ranges, mut volumes) = (Vec::with_capacity(self.atr_days), Vec::with_capacity(self.atr_days));
        let mut hi = hist.len();
        while hi > 0 && ranges.len() < self.atr_days {
            let d = utc_day(&hist[hi - 1]);
            let lo = hist[..hi].partition_point(|b| utc_day(b) < d);
            let day = &hist[lo..hi];
            let high = day.iter().map(|b| b.high).fold(f64::NEG_INFINITY, f64::max);
            let low = day.iter().map(|b| b.low).fold(f64::INFINITY, f64::min);
            ranges.push(match lo.checked_sub(1).map(|i| hist[i].close) {
                Some(pc) => (high - low).max((high - pc).abs()).max((low - pc).abs()),
                None => high - low,
            });
            volumes.push(
                day.iter().take_while(|b| b.ts - day[0].ts < self.range_secs).map(|b| b.volume).sum::<f64>(),
            );
            hi = lo;
        }
        if ranges.len() < self.atr_days {
            return None;
        }
        let n = ranges.len() as f64;
        Some((ranges.iter().sum::<f64>() / n, volumes.iter().sum::<f64>() / n))
    }

    /// Today's setup for one symbol, once its opening range is complete:
    /// (opening volume relative to normal, signed target weight right now).
    /// The weight is 0 after the stop or target was touched and near the
    /// close. None means the symbol has no trade today.
    fn setup(&self, bars: &[Bar]) -> Option<(f64, f64)> {
        let last = bars.last()?;
        let today = utc_day(last);
        let (hist, cur) = bars.split_at(bars.partition_point(|b| utc_day(b) < today));
        let bar_end = last.ts - cur[0].ts + self.bar_secs;
        if bar_end < self.range_secs {
            return None;
        }
        let (atr, normal_volume) = self.history_stats(hist)?;
        let stop_dist = self.stop_atr * atr;

        // Direction of the opening range.
        let n_range = cur.partition_point(|b| b.ts - cur[0].ts < self.range_secs);
        let (open, entry) = (cur[0].open, cur[n_range - 1].close);
        let dir = if entry > open {
            1.0
        } else if entry < open && self.allow_short {
            -1.0
        } else {
            return None;
        };
        if stop_dist <= 0.0 || entry <= 0.0 || entry < self.min_price || atr < self.min_atr {
            return None;
        }
        let opening_volume: f64 = cur[..n_range].iter().map(|b| b.volume).sum();
        let rel_volume = if normal_volume > 0.0 { opening_volume / normal_volume } else { 0.0 };
        if rel_volume < self.min_rel_volume {
            return None;
        }

        let (stop, target) = (entry - dir * stop_dist, entry + dir * self.target_r * stop_dist);
        // Once the stop or the target has been touched, the day's trade is over.
        let finished = cur[n_range..].iter().any(|b| {
            if dir > 0.0 {
                b.low <= stop || b.high >= target
            } else {
                b.high >= stop || b.low <= target
            }
        });
        if finished || bar_end >= SESSION_SECS - self.flatten_secs {
            return Some((rel_volume, 0.0));
        }
        Some((rel_volume, dir * (self.risk_pct * entry / stop_dist).min(self.max_weight)))
    }

    /// Signed target weight for one symbol, from its own bars.
    #[cfg(test)]
    fn weight(&self, bars: &[Bar]) -> f64 {
        self.setup(bars).map_or(0.0, |s| s.1)
    }
}

impl Strategy for OpeningRange {
    fn name(&self) -> String {
        format!(
            "Opening range breakout ({}-min range, stop {:.0}% of ATR({}), target {}R{})",
            self.range_secs / 60,
            self.stop_atr * 100.0,
            self.atr_days,
            self.target_r,
            if self.allow_short { "" } else { ", long only" }
        )
    }

    fn warmup(&self) -> usize {
        (self.atr_days + 1) * self.bars_per_day
    }

    fn lookback(&self) -> usize {
        (self.atr_days + 3) * self.bars_per_day
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let newest = universe.values().filter_map(|b| b.last()).map(|b| b.ts).max()?;
        // (symbol, relative opening volume, weight now)
        let mut setups: Vec<(&str, f64, f64)> = universe
            .iter()
            .filter(|(_, b)| b.last().is_some_and(|l| newest - l.ts <= 2 * self.bar_secs))
            .filter_map(|(s, b)| self.setup(b).map(|(rv, w)| (*s, rv, w)))
            .collect();
        if self.top_n > 0 {
            // The day's list is fixed by the opening range: a name that has
            // finished its trade keeps its slot, so nothing enters late.
            setups.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(b.0)));
            setups.truncate(self.top_n);
        }
        let mut out: Vec<(String, f64)> =
            setups.iter().filter(|t| t.2 != 0.0).map(|t| (t.0.to_string(), t.2)).collect();
        // With margin the limit is on the whole book (as in the paper: 4x in
        // total); without it, each side may use the account once.
        if self.gross_cap > 1.0 {
            let gross: f64 = out.iter().map(|t| t.1.abs()).sum();
            if gross > self.gross_cap {
                out.iter_mut().for_each(|t| t.1 *= self.gross_cap / gross);
            }
        }
        for side in [1.0, -1.0] {
            let gross: f64 = out.iter().filter(|t| t.1 * side > 0.0).map(|t| t.1.abs()).sum();
            if gross > self.gross_cap {
                let k = self.gross_cap / gross;
                out.iter_mut().filter(|t| t.1 * side > 0.0).for_each(|t| t.1 *= k);
            }
        }
        out.sort_by(|a, b| a.0.cmp(&b.0));
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Leverage rotation (Gayed & Bilello, 2016, "Leverage for the Long Run",
// Charles H. Dow Award). Leverage is only dangerous when markets are
// volatile, and markets are most volatile below their long-term average.
// So: while the index closes above its 200-day average, hold a leveraged
// index fund; when it closes below, move to Treasuries (or cash).
//
// Optional volatility targeting (Moreira & Muir, 2017): in an uptrend, mix
// the index and the leveraged fund so that expected volatility stays near
// `target_vol`: more leverage in calm markets, less in rough ones.
//
// The leverage comes from the ETF itself, so the account never borrows and
// the fund's financing costs are already in its price.

pub struct LeveragedIndex {
    index: String,
    risk_asset: String,
    leverage: f64,
    safe_asset: String,
    sma_days: usize,
    target_vol: f64,
    vol_days: usize,
    band: f64,
    /// Bar size: the day counts above are converted to bars, so the same
    /// rule runs on daily or intraday candles (checked on every candle).
    bars_per_day: usize,
    bars_per_year: f64,
}

/// Split an effective market exposure into a leveraged fund and the plain
/// index. exposure 1.0 -> all index; exposure == leverage -> all risk asset.
fn blend_exposure(exposure: f64, leverage: f64) -> (f64, f64) {
    if leverage <= 1.0 {
        return (0.0, 1.0);
    }
    let w = ((exposure - 1.0) / (leverage - 1.0)).clamp(0.0, 1.0);
    (w, 1.0 - w)
}

impl LeveragedIndex {
    fn sma_bars(&self) -> usize {
        self.sma_days * self.bars_per_day
    }
    fn vol_bars(&self) -> usize {
        self.vol_days * self.bars_per_day
    }
}

impl Strategy for LeveragedIndex {
    fn name(&self) -> String {
        format!(
            "Leverage rotation ({} {}x while {} > {}-day average{}, else {})",
            self.risk_asset,
            self.leverage,
            self.index,
            self.sma_days,
            if self.target_vol > 0.0 {
                format!(", {:.0}% volatility target", self.target_vol * 100.0)
            } else {
                String::new()
            },
            if self.safe_asset.is_empty() { "cash" } else { self.safe_asset.as_str() }
        )
    }

    fn warmup(&self) -> usize {
        self.sma_bars().max(self.vol_bars()) + 1
    }

    fn lookback(&self) -> usize {
        self.warmup() + 10
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        // Without the index there is no signal: keep whatever is held.
        let index = universe.get(self.index.as_str())?;
        let c = closes(index);
        let avg = sma(&c, self.sma_bars())?;
        let safe = |w: f64| -> Vec<(String, f64)> {
            if self.safe_asset.is_empty() || w <= 0.0 {
                Vec::new()
            } else {
                vec![(self.safe_asset.clone(), w)]
            }
        };
        if c[c.len() - 1] <= avg {
            return Some(safe(1.0));
        }
        if self.target_vol <= 0.0 {
            return Some(vec![(self.risk_asset.clone(), 1.0)]);
        }
        // Desired market exposure, between 0 and the fund's full leverage.
        let rets: Vec<f64> = c[c.len().saturating_sub(self.vol_bars() + 1)..]
            .windows(2)
            .map(|w| w[1] / w[0] - 1.0)
            .collect();
        let vol = stddev(&rets, rets.len()).unwrap_or(0.0) * self.bars_per_year.sqrt();
        // A flat/degenerate vol estimate must not become full 3x leverage.
        let exposure = if vol > 1e-9 { (self.target_vol / vol).min(self.leverage) } else { 1.0 };
        let mut out = Vec::new();
        if exposure >= 1.0 {
            // Blend the plain index with the leveraged fund.
            let (w_risk, w_index) = blend_exposure(exposure, self.leverage);
            if w_risk > 0.0 {
                out.push((self.risk_asset.clone(), w_risk));
            }
            if w_index > 0.0 {
                out.push((self.index.clone(), w_index));
            }
        } else {
            out.push((self.index.clone(), exposure));
            out.extend(safe(1.0 - exposure));
        }
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Helpers shared by the monthly ranking strategies below.

/// Day number of the last bar of the most recently completed month, so that
/// monthly strategies decide "as of last month-end" on every bar (pure
/// function of the bars; safe to restart at any time).
fn month_end_cutoff(reference: &[Bar]) -> Option<i64> {
    (1..reference.len())
        .rev()
        .find(|&i| month_key(reference[i].ts) != month_key(reference[i - 1].ts))
        .map(|i| utc_day(&reference[i - 1]))
}

/// The series that defines the calendar: the index if present, else the longest.
fn reference_series<'a>(universe: &HashMap<&str, &'a [Bar]>, index: &str) -> Option<&'a [Bar]> {
    universe.get(index).copied().or_else(|| universe.values().copied().max_by_key(|b| b.len()))
}

/// How a ranked list is turned into a long group and a short group.
struct Sides {
    long_frac: f64,
    short_frac: f64,
    long_gross: f64,
    short_gross: f64,
}

impl Sides {
    /// `scores`: (score, symbol), any order. Buys the highest-scoring group
    /// and shorts the lowest, each side equal-weighted.
    fn pick(&self, mut scores: Vec<(f64, &str)>) -> Vec<(String, f64)> {
        scores.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(b.1)));
        let n = scores.len();
        let count = |frac: f64| if frac > 0.0 { ((n as f64 * frac).round() as usize).max(1) } else { 0 };
        let (n_long, n_short) = (count(self.long_frac), count(self.short_frac));
        if n == 0 || n_long + n_short > n {
            return Vec::new();
        }
        let mut out = Vec::with_capacity(n_long + n_short);
        for s in &scores[..n_long] {
            out.push((s.1.to_string(), self.long_gross / n_long as f64));
        }
        for s in &scores[n - n_short..] {
            out.push((s.1.to_string(), -self.short_gross / n_short as f64));
        }
        out
    }
}

/// Rank of each value as a fraction from 0 (lowest) to 1 (highest).
fn percentile_ranks(values: &[f64]) -> Vec<f64> {
    let mut order: Vec<usize> = (0..values.len()).collect();
    order.sort_by(|&a, &b| values[a].total_cmp(&values[b]));
    let mut ranks = vec![0.0; values.len()];
    let denom = (values.len().max(2) - 1) as f64;
    for (rank, &i) in order.iter().enumerate() {
        ranks[i] = rank as f64 / denom;
    }
    ranks
}

// ---------------------------------------------------------------------------
// Time-series momentum / trend following across asset classes (Moskowitz,
// Ooi & Pedersen, 2012; Hurst, Ooi & Pedersen, 2017). Each asset is judged
// only against its own past: long if it has been rising, short (or flat) if
// it has been falling, measured over several horizons. Positions are sized
// inversely to volatility so every asset carries similar risk. Run on ETFs
// for stocks, bonds, commodities and currencies, this is the strategy with
// the longest track record in the literature and the one that has tended to
// make money during stock-market crashes.

pub struct Tsmom {
    /// Horizons in trading days; the signal is the average direction over them.
    lookbacks: Vec<usize>,
    vol_days: usize,
    target_vol: f64,
    max_weight: f64,
    max_long: f64,
    max_short: f64,
    allow_short: bool,
    band: f64,
}

impl Strategy for Tsmom {
    fn name(&self) -> String {
        format!(
            "Multi-asset trend following ({:?}-day horizons, {})",
            self.lookbacks,
            if self.allow_short { "long/short" } else { "long/flat" }
        )
    }

    fn warmup(&self) -> usize {
        self.lookbacks.iter().copied().max().unwrap_or(0).max(self.vol_days) + 30
    }

    fn lookback(&self) -> usize {
        self.warmup() + 40
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let reference = reference_series(universe, "")?;
        let Some(cutoff) = month_end_cutoff(reference) else { return Some(Vec::new()) };
        let today = utc_day(&reference[reference.len() - 1]);
        let longest = self.lookbacks.iter().copied().max().unwrap_or(0);

        // (symbol, average direction in -1..1, annualised volatility)
        let mut assets: Vec<(&str, f64, f64)> = Vec::new();
        for (sym, bars) in universe {
            let end = bars.partition_point(|b| utc_day(b) <= cutoff);
            if end <= longest.max(self.vol_days) || utc_day(&bars[bars.len() - 1]) + 5 < today {
                continue;
            }
            let last = bars[end - 1].close;
            let direction: f64 = self
                .lookbacks
                .iter()
                .map(|&l| (last / bars[end - 1 - l].close - 1.0).signum())
                .sum::<f64>()
                / self.lookbacks.len() as f64;
            let rets: Vec<f64> = bars[end - 1 - self.vol_days..end]
                .windows(2)
                .map(|w| w[1].close / w[0].close - 1.0)
                .collect();
            let vol = stddev(&rets, rets.len()).unwrap_or(0.0) * 252f64.sqrt();
            if vol > 0.0 {
                assets.push((sym, direction, vol));
            }
        }
        if assets.is_empty() {
            return Some(Vec::new());
        }
        let n = assets.len() as f64;
        let mut out: Vec<(String, f64)> = assets
            .iter()
            .map(|(s, dir, vol)| (s.to_string(), (dir * self.target_vol / vol / n).clamp(-self.max_weight, self.max_weight)))
            .filter(|(_, w)| self.allow_short || *w > 0.0)
            .collect();
        // No leverage: scale each side down to its limit if needed.
        let long: f64 = out.iter().filter(|t| t.1 > 0.0).map(|t| t.1).sum();
        let short: f64 = -out.iter().filter(|t| t.1 < 0.0).map(|t| t.1).sum::<f64>();
        let k_long = if long > self.max_long { self.max_long / long } else { 1.0 };
        let k_short = if short > self.max_short { self.max_short / short } else { 1.0 };
        for t in &mut out {
            t.1 *= if t.1 > 0.0 { k_long } else { k_short };
        }
        out.retain(|t| t.1.abs() >= 0.002);
        out.sort_by(|a, b| b.1.abs().total_cmp(&a.1.abs()).then(a.0.cmp(&b.0)));
        Some(out)
    }
}

// ---------------------------------------------------------------------------
// Value and momentum combined (Asness, Moskowitz & Pedersen, 2013, "Value and
// Momentum Everywhere"). The two tend to win at different times, so a stock
// is ranked on both and the ranks are averaged.
//   momentum = return over the past year, skipping the latest month
//   value    = how far the price has FALLEN over the past five years,
//              skipping the latest year (cheap after a long decline)
// The paper measures value with book-to-price for stocks and with this
// five-year reversal for other assets; this implementation uses the price
// version everywhere because it needs no accounting data.

pub struct ValueMomentum {
    mom_days: usize,
    mom_skip: usize,
    val_days: usize,
    val_skip: usize,
    sides: Sides,
    band: f64,
    index: String,
}

impl Strategy for ValueMomentum {
    fn name(&self) -> String {
        format!(
            "Value + momentum (long top {:.0}% / short bottom {:.0}%, monthly)",
            self.sides.long_frac * 100.0,
            self.sides.short_frac * 100.0
        )
    }

    fn warmup(&self) -> usize {
        self.val_days.max(self.mom_days) + 25
    }

    fn lookback(&self) -> usize {
        self.warmup() + 30
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let reference = reference_series(universe, &self.index)?;
        let Some(cutoff) = month_end_cutoff(reference) else { return Some(Vec::new()) };
        let today = utc_day(&reference[reference.len() - 1]);
        let need = self.val_days.max(self.mom_days) + 1;

        let (mut names, mut mom, mut val) = (Vec::new(), Vec::new(), Vec::new());
        for (sym, bars) in universe {
            if *sym == self.index {
                continue;
            }
            let end = bars.partition_point(|b| utc_day(b) <= cutoff);
            if end < need || utc_day(&bars[bars.len() - 1]) + 5 < today || bars[end - 1].close < 5.0 {
                continue;
            }
            let px = |back: usize| bars[end - 1 - back].close;
            if px(self.mom_days) <= 0.0 || px(self.val_days) <= 0.0 {
                continue;
            }
            names.push(*sym);
            mom.push(px(self.mom_skip) / px(self.mom_days) - 1.0);
            val.push(-(px(self.val_skip) / px(self.val_days) - 1.0));
        }
        let (rm, rv) = (percentile_ranks(&mom), percentile_ranks(&val));
        let scores = names.iter().enumerate().map(|(i, s)| ((rm[i] + rv[i]) / 2.0, *s)).collect();
        Some(self.sides.pick(scores))
    }
}

// ---------------------------------------------------------------------------
// Profitability (Novy-Marx, 2013; one of the few factors found to survive
// trading costs, Novy-Marx & Velikov, 2016). Once a month, rank companies by
// return on assets (profit over the last four quarters / total assets, from
// their SEC filings) and hold the most profitable group. Slow by design:
// the ranking only changes when companies report.
// The original paper uses gross profit; net income is used here because
// every company reports it.

pub struct Profitability {
    sides: Sides,
    band: f64,
    index: String,
    /// Per symbol: (day the figure became public, return on assets).
    data: HashMap<String, Vec<(i64, f64)>>,
}

impl Strategy for Profitability {
    fn name(&self) -> String {
        format!(
            "Profitability (return on assets; long top {:.0}% / short bottom {:.0}%, monthly)",
            self.sides.long_frac * 100.0,
            self.sides.short_frac * 100.0
        )
    }

    fn warmup(&self) -> usize {
        30
    }

    fn lookback(&self) -> usize {
        60
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let reference = reference_series(universe, &self.index)?;
        let Some(cutoff) = month_end_cutoff(reference) else { return Some(Vec::new()) };
        let today = utc_day(&reference[reference.len() - 1]);
        let mut scores: Vec<(f64, &str)> = Vec::new();
        for (sym, bars) in universe {
            let (Some(series), Some(last)) = (self.data.get(*sym), bars.last()) else { continue };
            if *sym == self.index || utc_day(last) + 5 < today || last.close < 5.0 {
                continue;
            }
            // Latest figure that was public at the month-end, if still current.
            let known = series.partition_point(|x| x.0 <= cutoff);
            let Some(&(filed, roa)) = known.checked_sub(1).map(|i| &series[i]) else { continue };
            if cutoff - filed <= 200 {
                scores.push((roa, sym));
            }
        }
        Some(self.sides.pick(scores))
    }
}

// ---------------------------------------------------------------------------
// Sleeve: lets a per-symbol strategy take part in a combined portfolio. It
// keeps the strategy's own virtual list of holdings (updated from its
// buy/sell signals on every bar) and reports them as equal weights.

struct Sleeve {
    inner: Box<dyn Strategy>,
    weight: f64,
    max_positions: usize,
    /// Virtual holdings; None until the first evaluation.
    book: RefCell<Option<BTreeSet<String>>>,
}

/// Bars replayed on the first evaluation to rebuild the virtual holdings
/// (so a restarted live session picks up where the last one stopped).
const SLEEVE_WARM_START: usize = 30;

impl Sleeve {
    fn step(&self, book: &mut BTreeSet<String>, sym: &str, bars: &[Bar]) {
        let held = book.contains(sym);
        match self.inner.signal(bars, held) {
            Signal::Buy if !held && book.len() < self.max_positions => {
                book.insert(sym.to_string());
            }
            Signal::Sell if held => {
                book.remove(sym);
            }
            _ => {}
        }
    }
}

impl Strategy for Sleeve {
    fn name(&self) -> String {
        self.inner.name()
    }

    fn warmup(&self) -> usize {
        self.inner.warmup() + SLEEVE_WARM_START
    }

    fn lookback(&self) -> usize {
        self.inner.lookback() + SLEEVE_WARM_START
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, _held: &[&str]) -> Option<Vec<(String, f64)>> {
        let mut slot = self.book.borrow_mut();
        let first = slot.is_none();
        let book = slot.get_or_insert_with(BTreeSet::new);
        let mut symbols: Vec<&str> = universe.keys().copied().collect();
        symbols.sort_unstable(); // deterministic order

        if first {
            for back in (1..=SLEEVE_WARM_START).rev() {
                for sym in &symbols {
                    let bars = universe[sym];
                    if bars.len() > back {
                        self.step(book, sym, &bars[..bars.len() - back]);
                    }
                }
            }
        }
        for sym in &symbols {
            self.step(book, sym, universe[sym]);
        }
        Some(book.iter().map(|s| (s.clone(), self.weight)).collect())
    }
}

// ---------------------------------------------------------------------------
// Combo: runs several strategies on one account. Each part manages a share
// of the capital (`allocation`); the parts' target weights are added up per
// symbol, so a long from one part and a short from another net out.

struct Combo {
    parts: Vec<(f64, Box<dyn Strategy>)>,
    band: f64,
    max_long: f64,
    max_short: f64,
}

impl Strategy for Combo {
    fn name(&self) -> String {
        let names: Vec<String> = self
            .parts
            .iter()
            .map(|(a, s)| format!("{:.0}% {}", a * 100.0, s.name()))
            .collect();
        format!("Combination: {}", names.join(" + "))
    }

    fn warmup(&self) -> usize {
        self.parts.iter().map(|p| p.1.warmup()).max().unwrap_or(0)
    }

    fn lookback(&self) -> usize {
        self.parts.iter().map(|p| p.1.lookback()).max().unwrap_or(0)
    }

    fn is_portfolio(&self) -> bool {
        true
    }

    fn rebalance_band(&self) -> f64 {
        self.band
    }

    fn targets(&self, universe: &HashMap<&str, &[Bar]>, held: &[&str]) -> Option<Vec<(String, f64)>> {
        let mut net: BTreeMap<String, f64> = BTreeMap::new();
        for (allocation, part) in &self.parts {
            for (sym, w) in part.targets(universe, held).unwrap_or_default() {
                *net.entry(sym).or_insert(0.0) += allocation * w;
            }
        }
        // Keep each side within its limit (no leverage on the long side).
        let long: f64 = net.values().filter(|w| **w > 0.0).sum();
        let short: f64 = -net.values().filter(|w| **w < 0.0).sum::<f64>();
        let (k_long, k_short) = (
            if long > self.max_long { self.max_long / long } else { 1.0 },
            if short > self.max_short { self.max_short / short } else { 1.0 },
        );
        let mut out: Vec<(String, f64)> = net
            .into_iter()
            .map(|(s, w)| (s, if w > 0.0 { w * k_long } else { w * k_short }))
            .filter(|(_, w)| w.abs() >= 0.002)
            .collect();
        out.sort_by(|a, b| b.1.abs().total_cmp(&a.1.abs()).then(a.0.cmp(&b.0)));
        Some(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DAY: i64 = 86_400;
    // Monday 2024-01-01 14:30 UTC (a 9:30 ET open).
    const MON: i64 = 1_704_119_400;

    fn bars(closes: &[f64]) -> Vec<Bar> {
        series(closes, 0, 60)
    }

    fn series(closes: &[f64], start: i64, step: i64) -> Vec<Bar> {
        closes
            .iter()
            .enumerate()
            .map(|(i, &c)| Bar {
                ts: start + i as i64 * step,
                open: c,
                high: c,
                low: c,
                close: c,
                volume: 1.0,
            })
            .collect()
    }

    #[test]
    fn sma_cross_buys_on_cross_and_sells_below() {
        let s = SmaCross { fast: 2, slow: 4 };
        // Downtrend then a sharp turn up: fast crosses above slow on the last bar.
        let b = bars(&[10.0, 9.0, 8.0, 7.0, 6.0, 10.0]);
        assert_eq!(s.signal(&b, false), Signal::Buy);
        // Already above (no fresh cross) -> no new entry.
        let b2 = bars(&[10.0, 9.0, 8.0, 7.0, 6.0, 10.0, 11.0]);
        assert_eq!(s.signal(&b2, false), Signal::Hold);
        // Falling again while holding -> exit.
        let b3 = bars(&[6.0, 9.0, 10.0, 11.0, 8.0, 5.0]);
        assert_eq!(s.signal(&b3, true), Signal::Sell);
    }

    #[test]
    fn breakout_signals() {
        let s = Breakout { entry_lookback: 3, exit_lookback: 2 };
        assert_eq!(s.signal(&bars(&[5.0, 6.0, 5.0, 7.0]), false), Signal::Buy);
        assert_eq!(s.signal(&bars(&[5.0, 6.0, 5.0, 5.5]), false), Signal::Hold);
        assert_eq!(s.signal(&bars(&[5.0, 6.0, 5.0, 4.0]), true), Signal::Sell);
    }

    #[test]
    fn connors_buys_pullback_in_uptrend_only() {
        let s = ConnorsRsi2 { rsi_period: 2, entry_below: 10.0, trend_sma: 20, exit_sma: 5 };
        // Steady uptrend, then three sharp down days: still above the 20-bar average.
        let mut up: Vec<f64> = (0..40).map(|i| 100.0 + i as f64).collect();
        up.extend([137.0, 135.0, 133.0]);
        assert_eq!(s.signal(&bars(&up), false), Signal::Buy);
        // Same pullback in a downtrend is ignored.
        let mut down: Vec<f64> = (0..40).map(|i| 200.0 - i as f64).collect();
        down.extend([158.0, 156.0, 154.0]);
        assert_eq!(s.signal(&bars(&down), false), Signal::Hold);
        // Exit once price closes back above the 5-bar average.
        up.push(140.0);
        assert_eq!(s.signal(&bars(&up), true), Signal::Sell);
    }

    #[test]
    fn bollinger_buys_low_band_sells_at_mean() {
        let s = Bollinger { lookback: 10, entry_z: 2.0, exit_z: 0.0 };
        let mut c = vec![10.0, 10.2, 9.8, 10.1, 9.9, 10.0, 10.2, 9.8, 10.0, 8.0];
        assert_eq!(s.signal(&bars(&c), false), Signal::Buy);
        assert_eq!(s.signal(&bars(&c), true), Signal::Hold);
        c.push(10.1);
        assert_eq!(s.signal(&bars(&c), true), Signal::Sell);
    }

    /// `days` flat sessions of 30-minute bars, with intraday prices from `today`.
    fn intraday(days: usize, today: &[f64]) -> Vec<Bar> {
        let mut out = Vec::new();
        for d in 0..days {
            // Every prior session wiggles 0.5% away from its open and back.
            let c: Vec<f64> = (0..13).map(|i| if i % 2 == 0 { 100.0 } else { 100.5 }).collect();
            let mut day = series(&c, MON + d as i64 * DAY, 1800);
            day[0].open = 100.0;
            out.extend(day);
        }
        let mut cur = series(today, MON + days as i64 * DAY, 1800);
        cur[0].open = 100.0;
        out.extend(cur);
        out
    }

    #[test]
    fn intraday_momentum_trades_breakouts_and_goes_flat() {
        let s = IntradayMomentum { lookback_days: 3, check_secs: 1800, bar_secs: 1800, bars_per_day: 13 };
        // Inside the noise area (<= 0.5% from the open): nothing to do.
        assert_eq!(s.signal(&intraday(3, &[100.0, 100.3]), false), Signal::Hold);
        // Clear break above it: buy.
        assert_eq!(s.signal(&intraday(3, &[100.0, 101.5]), false), Signal::Buy);
        // Falls back inside: trailing stop.
        assert_eq!(s.signal(&intraday(3, &[100.0, 101.5, 100.2]), true), Signal::Sell);
        // Still trending: hold.
        assert_eq!(s.signal(&intraday(3, &[100.0, 101.5, 102.0]), true), Signal::Hold);
        // Second-to-last bar of the session: flat before the close, no new entries.
        let late: Vec<f64> = (0..12).map(|i| 100.0 + i as f64).collect();
        assert_eq!(s.signal(&intraday(3, &late), true), Signal::Sell);
        assert_eq!(s.signal(&intraday(3, &late), false), Signal::Hold);
        // Not enough history yet.
        assert_eq!(s.signal(&intraday(2, &[100.0, 101.5]), false), Signal::Hold);
    }

    #[test]
    fn monthly_trend_follows_month_end_average() {
        let s = MonthlyTrend { months: 3 };
        // One bar every 10 days: month-end closes rise, so be long.
        let rising: Vec<f64> = (0..16).map(|i| 100.0 + i as f64).collect();
        assert_eq!(s.signal(&series(&rising, MON, 10 * DAY), false), Signal::Buy);
        assert_eq!(s.signal(&series(&rising, MON, 10 * DAY), true), Signal::Hold);
        let falling: Vec<f64> = (0..16).map(|i| 100.0 - i as f64).collect();
        assert_eq!(s.signal(&series(&falling, MON, 10 * DAY), true), Signal::Sell);
        assert_eq!(s.signal(&series(&falling, MON, 10 * DAY), false), Signal::Hold);
    }

    #[test]
    fn rotation_ranks_and_respects_filters() {
        let s = MomentumRotation {
            momentum_days: 20,
            trend_sma: 10,
            index_sma: 10,
            top_n: 1,
            index: "SPY".into(),
            weight: 0.5,
        };
        // 31 daily bars ending on a Monday, so the last bar starts a new week.
        let start = MON + 7 * DAY - 30 * DAY;
        let grow = |rate: f64| -> Vec<Bar> {
            let c: Vec<f64> = (0..31).map(|i| 100.0 * (1.0 + rate).powi(i)).collect();
            series(&c, start, DAY)
        };
        let (fast, slow, falling, index) = (grow(0.01), grow(0.002), grow(-0.01), grow(0.001));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("FAST", &fast);
        u.insert("SLOW", &slow);
        u.insert("DOWN", &falling);
        u.insert("SPY", &index);
        assert_eq!(s.targets(&u, &[]), Some(vec![("FAST".to_string(), 0.5)]));
        // A held stock that is no longer in the top group is dropped.
        assert_eq!(s.targets(&u, &["SLOW"]), Some(vec![("FAST".to_string(), 0.5)]));
        // Mid-week: no rebalance.
        let mid: HashMap<&str, &[Bar]> =
            u.iter().map(|(k, v)| (*k, &v[..v.len() - 2])).collect();
        assert_eq!(s.targets(&mid, &[]), None);
        // Index below its average: keep winners, but open nothing new.
        let bear = grow(-0.001);
        u.insert("SPY", &bear);
        assert_eq!(s.targets(&u, &[]), Some(vec![]));
        assert_eq!(s.targets(&u, &["FAST"]), Some(vec![("FAST".to_string(), 0.5)]));
    }

    fn trend() -> TrendVolTarget {
        TrendVolTarget {
            entry_lookback: 5,
            exit_lookback: 10,
            keltner_mult: 2.0,
            vol_days: 5,
            position_vol_target: 0.02,
            max_weight: 0.30,
            max_gross: 1.0,
            band: 0.02,
            index: "SPY".into(),
            index_sma: 20,
            park_cash: true,
            max_names: None,
        }
    }

    /// Daily bars with a +/-`wiggle` zig-zag around `path` so volatility is non-zero.
    fn wiggly(path: &[f64], wiggle: f64) -> Vec<Bar> {
        let c: Vec<f64> = path
            .iter()
            .enumerate()
            .map(|(i, p)| p * (1.0 + if i % 2 == 0 { wiggle } else { -wiggle }))
            .collect();
        series(&c, MON, DAY)
    }

    #[test]
    fn trend_replay_enters_on_breakout_and_exits_on_ratcheted_stop() {
        let s = trend();
        let flat: Vec<f64> = vec![100.0; 30];
        assert!(!s.in_trend(&series(&flat, MON, DAY)));
        // Breaks out and keeps climbing: in a trend.
        let mut up = flat.clone();
        up.extend((1..=15).map(|i| 100.0 + 2.0 * i as f64));
        assert!(s.in_trend(&series(&up, MON, DAY)));
        // Then collapses through the trailing stop: out, and stays out.
        let mut bust = up.clone();
        bust.extend([110.0, 100.0, 95.0, 95.0, 95.0]);
        assert!(!s.in_trend(&series(&bust, MON, DAY)));
    }

    #[test]
    fn trend_weights_are_inverse_vol_capped_and_cash_is_parked() {
        let s = trend();
        let rising: Vec<f64> = (0..45).map(|i| 100.0 * 1.01f64.powi(i)).collect();
        let flat: Vec<f64> = vec![100.0; 45];
        let (calm, wild) = (wiggly(&rising, 0.001), wiggly(&rising, 0.004));
        let (dead, index) = (wiggly(&flat, 0.001), wiggly(&rising, 0.001));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("CALM", &calm);
        u.insert("WILD", &wild);
        u.insert("DEAD", &dead);
        u.insert("SPY", &index);
        let t: HashMap<String, f64> = s.targets(&u, &[]).unwrap().into_iter().collect();
        // Not trending -> not held. Calmer stock gets the bigger (capped) weight.
        assert!(!t.contains_key("DEAD"));
        assert!(t["CALM"] > t["WILD"] && t["WILD"] > 0.0);
        assert!(t["CALM"] <= 0.30 + 1e-12);
        // Whatever is left goes to the index; nothing is levered.
        let total: f64 = t.values().sum();
        assert!((total - 1.0).abs() < 1e-9, "total weight {total}");
        // Index below its average: spare capital stays in cash.
        let weak = wiggly(&(0..45).map(|i| 100.0 * 0.99f64.powi(i)).collect::<Vec<_>>(), 0.001);
        u.insert("SPY", &weak);
        let t2: HashMap<String, f64> = s.targets(&u, &[]).unwrap().into_iter().collect();
        assert!(!t2.contains_key("SPY"));
        assert!(t2.values().sum::<f64>() < 1.0);
    }

    /// 5-minute session bars (09:30-15:50 ET) growing at `rate` per day.
    fn intraday_grow(rate: f64, days: usize) -> Vec<Bar> {
        let mut out = Vec::new();
        for d in 0..days {
            let close = 100.0 * (1.0 + rate).powi(d as i32);
            for i in 0..77 {
                out.push(Bar {
                    ts: MON + d as i64 * DAY + i as i64 * 300,
                    open: close,
                    high: close,
                    low: close,
                    close,
                    volume: 1.0,
                });
            }
        }
        out
    }

    #[test]
    fn intraday_momentum_rebalances_once_near_the_close() {
        let s = IntradayLsMomentum {
            lookback: 5,
            skip: 1,
            long_frac: 0.2,
            short_frac: 0.2,
            long_gross: 1.0,
            short_gross: 0.5,
            band: 0.005,
            index: "SPY".into(),
            bars_per_day: 78,
            bar_secs: 300,
            rebalance_mins: 0,
        };
        let (fast, slow) = (intraday_grow(0.01, 10), intraday_grow(0.002, 10));
        let (down, flat) = (intraday_grow(-0.01, 10), intraday_grow(0.0, 10));
        let (flat2, spy) = (intraday_grow(0.0001, 10), intraday_grow(0.001, 10));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("FAST", &fast);
        u.insert("SLOW", &slow);
        u.insert("DOWN", &down);
        u.insert("FLAT", &flat);
        u.insert("FLAT2", &flat2);
        u.insert("SPY", &spy);
        let t: HashMap<String, f64> = s.targets(&u, &[]).unwrap().into_iter().collect();
        assert_eq!(t.len(), 2);
        assert_eq!(t["FAST"], 1.0);
        assert_eq!(t["DOWN"], -0.5);

        // One bar earlier is not the daily decision bar: keep the book.
        let spy_short = &spy[..spy.len() - 1];
        let mut u2 = u.clone();
        u2.insert("SPY", spy_short);
        assert_eq!(s.targets(&u2, &[]), None);
    }

    #[test]
    fn intraday_decision_bar_follows_eastern_time_across_dst() {
        // 2026-10-30 15:50 EDT and 2026-11-10 15:50 EST.
        let oct = NaiveDate::from_ymd_opt(2026, 10, 30)
            .unwrap()
            .and_hms_opt(19, 50, 0)
            .unwrap()
            .and_utc()
            .timestamp();
        let nov = NaiveDate::from_ymd_opt(2026, 11, 10)
            .unwrap()
            .and_hms_opt(20, 50, 0)
            .unwrap()
            .and_utc()
            .timestamp();
        assert!(is_daily_rebalance_bar(oct, 300));
        assert!(is_daily_rebalance_bar(nov, 300));
        assert!(!is_daily_rebalance_bar(oct + 300, 300));
    }

    #[test]
    fn trend_max_names_keeps_holdings_then_strongest() {
        let mut s = trend();
        s.park_cash = false;
        s.max_names = Some(1);
        let path = |rate: f64| -> Vec<f64> { (0..45).map(|i| 100.0 * (1.0f64 + rate).powi(i)).collect() };
        let (strong, weak) = (wiggly(&path(0.02), 0.001), wiggly(&path(0.01), 0.001));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("STRONG", &strong);
        u.insert("WEAK", &weak);
        let names = |held: &[&str]| -> Vec<String> {
            s.targets(&u, held).unwrap().into_iter().map(|t| t.0).collect()
        };
        assert_eq!(names(&[]), vec!["STRONG"]);
        // A position that is still trending is not swapped out for a stronger one.
        assert_eq!(names(&["WEAK"]), vec!["WEAK"]);
    }

    /// One session of 1-minute bars with the given closes.
    fn minute_bars(closes: &[f64]) -> Vec<Bar> {
        series(closes, MON, 60)
    }

    #[test]
    fn noise_area_goes_long_on_a_breakout_with_vol_scaled_size_and_exits_at_vwap() {
        let s = NoiseArea {
            lookback_days: 2,
            vol_days: 2,
            check_secs: 1800,
            target_vol: 0.02,
            max_weight: 4.0,
            allow_short: true,
            flatten_secs: 900,
            band: 0.1,
            bar_secs: 1800,
            bars_per_day: 13,
        };
        let mut out = Vec::new();
        for (d, px) in [(3, 100.0), (2, 101.0), (1, 100.0)] {
            out.extend(series(&[px; 13], MON - d * DAY, 1800));
        }
        let day = |closes: &[f64]| {
            let mut v = out.clone();
            v.extend(series(closes, MON, 1800));
            v
        };
        assert_eq!(s.weight(&day(&[100.0, 100.0])), 0.0);
        let w = s.weight(&day(&[100.0, 100.0, 102.0]));
        assert!(w > 1.0 && w <= 4.0, "{w}");
        // Falling back below the VWAP ends the trade.
        assert_eq!(s.weight(&day(&[100.0, 100.0, 102.0, 99.0])), 0.0);
        // A breakout downwards is a short, and nothing is held at the close.
        assert!(s.weight(&day(&[100.0, 100.0, 98.0])) < -1.0);
        let late = [100.0, 100.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0, 102.0];
        assert_eq!(s.weight(&day(&late)), 0.0);
    }

    fn vwap(allow_short: bool) -> VwapTrend {
        VwapTrend { weight: 0.5, allow_short, flatten_secs: 180, band: 0.1, bar_secs: 60 }
    }

    #[test]
    fn vwap_trend_follows_price_relative_to_vwap_and_flattens() {
        let s = vwap(true);
        assert_eq!(s.side(&minute_bars(&[100.0, 100.0, 101.0])), 1.0);
        assert_eq!(s.side(&minute_bars(&[100.0, 100.0, 99.0])), -1.0);
        assert_eq!(vwap(false).side(&minute_bars(&[100.0, 100.0, 99.0])), 0.0);
        // Yesterday's prices do not count towards today's VWAP.
        let mut two_days = series(&[200.0; 5], MON - DAY, 60);
        two_days.extend(minute_bars(&[100.0, 100.0, 101.0]));
        assert_eq!(s.side(&two_days), 1.0);
        // 387 rising bars end at 15:57: inside the last 3 minutes -> flat.
        let late: Vec<f64> = (0..387).map(|i| 100.0 + i as f64 * 0.01).collect();
        assert_eq!(s.side(&minute_bars(&late)), 0.0);
        assert_eq!(s.side(&minute_bars(&late[..386])), 1.0);
        // Portfolio view: signed weights per symbol.
        let (up, down) = (minute_bars(&[100.0, 100.0, 101.0]), minute_bars(&[100.0, 100.0, 99.0]));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("UP", &up);
        u.insert("DOWN", &down);
        assert_eq!(s.targets(&u, &[]), Some(vec![("DOWN".to_string(), -0.5), ("UP".to_string(), 0.5)]));
    }

    fn earnings(live: bool, reports: Vec<(&str, i64, f64)>) -> EarningsDrift {
        let mut map: HashMap<String, Vec<Report>> = HashMap::new();
        for (s, filed, sue) in reports {
            map.entry(s.to_string()).or_default().push(Report { filed, sue });
        }
        EarningsDrift {
            long_sue: 2.0,
            short_sue: -2.0,
            hold_days: 30,
            weight: 0.2,
            max_long: 0.4,
            max_short: 0.2,
            band: 0.05,
            live,
            reports: RefCell::new(map),
            loaded_at: Cell::new(Instant::now()),
            source: None,
        }
    }

    #[test]
    fn earnings_trades_the_day_after_the_filing_and_never_before() {
        let day0 = MON.div_euclid(DAY);
        // Ten daily bars: the last bar is day0 + 9.
        let px = series(&[100.0; 10], MON, DAY);
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        for s in ["GOOD", "BAD", "MEH", "SAMEDAY", "OLD", "BEST", "BETTER"] {
            u.insert(s, &px);
        }
        let reports = vec![
            ("GOOD", day0 + 5, 3.0),
            ("BAD", day0 + 5, -4.0),
            ("MEH", day0 + 5, 0.5),     // not surprising enough
            ("SAMEDAY", day0 + 9, 9.0), // filed on the day being decided
            ("OLD", day0 - 40, 9.0),    // filed too long ago
            ("BEST", day0 + 8, 6.0),
            ("BETTER", day0 + 7, 5.0),
        ];
        // Backtest: a report filed today is not known yet. The two long
        // slots go to the biggest surprises.
        let t = earnings(false, reports.clone()).targets(&u, &[]).unwrap();
        assert_eq!(
            t,
            vec![("BEST".to_string(), 0.2), ("BETTER".to_string(), 0.2), ("BAD".to_string(), -0.2)]
        );
        // Live: deciding at the next open, yesterday's filing is usable.
        let live = earnings(true, reports).targets(&u, &[]).unwrap();
        assert_eq!(live[0], ("SAMEDAY".to_string(), 0.2));
    }

    #[test]
    fn combo_nets_parts_and_wraps_per_symbol_strategies() {
        // Part 1: per-symbol breakout wrapped in a sleeve. Part 2: VWAP long/short.
        let sleeve = Sleeve {
            inner: Box::new(Breakout { entry_lookback: 3, exit_lookback: 2 }),
            weight: 0.5,
            max_positions: 5,
            book: RefCell::new(None),
        };
        let mut both = vwap(true);
        both.weight = 1.0;
        let combo = Combo {
            parts: vec![(0.5, Box::new(sleeve)), (0.5, Box::new(both))],
            band: 0.02,
            max_long: 1.0,
            max_short: 0.1,
        };
        let (up, down) = (minute_bars(&[5.0, 6.0, 5.0, 7.0]), minute_bars(&[5.0, 6.0, 5.0, 4.0]));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("UP", &up);
        u.insert("DOWN", &down);
        let t: HashMap<String, f64> = combo.targets(&u, &[]).unwrap().into_iter().collect();
        // UP: breakout sleeve 0.5 * 0.5 plus VWAP long 0.5 * 1.0.
        assert!((t["UP"] - 0.75).abs() < 1e-12, "{:?}", t);
        // DOWN: VWAP short 0.5, scaled down to the 10% short limit.
        assert!((t["DOWN"] + 0.1).abs() < 1e-12, "{:?}", t);
        // The sleeve still holds UP on the next bar.
        let up2 = minute_bars(&[5.0, 6.0, 5.0, 7.0, 7.0]);
        u.insert("UP", &up2);
        let t2: HashMap<String, f64> = combo.targets(&u, &[]).unwrap().into_iter().collect();
        assert!(t2["UP"] >= 0.25, "{:?}", t2);
    }

    fn orb() -> OpeningRange {
        OpeningRange {
            range_secs: 300,
            atr_days: 2,
            stop_atr: 0.1,
            target_r: 10.0,
            risk_pct: 0.01,
            max_weight: 0.5,
            allow_short: true,
            flatten_secs: 180,
            band: 0.1,
            bar_secs: 60,
            bars_per_day: 390,
            top_n: 0,
            min_rel_volume: 0.0,
            min_price: 0.0,
            min_atr: 0.0,
            gross_cap: 1.0,
        }
    }

    /// Two prior sessions that each range from 99 to 101 (ATR = 2), then today.
    fn orb_bars(today: &[f64]) -> Vec<Bar> {
        let mut out = Vec::new();
        for d in [2, 1] {
            out.extend(series(&[100.0, 101.0, 99.0, 100.0], MON - d * DAY, 60));
        }
        out.extend(minute_bars(today));
        out
    }

    #[test]
    fn opening_range_trades_once_and_respects_stop_and_target() {
        let s = orb();
        // Stop distance = 10% of ATR 2 = 0.2. Still inside the first 5 minutes: wait.
        assert_eq!(s.weight(&orb_bars(&[100.0, 100.1, 100.2, 100.3])), 0.0);
        // Range closes up at 100.5: long. Risk 1% with a 0.2 stop wants a
        // 5x position, so the 50% cap applies.
        let up = [100.0, 100.1, 100.2, 100.3, 100.5];
        assert_eq!(s.weight(&orb_bars(&up)), 0.5);
        // Range closes down: short.
        assert_eq!(s.weight(&orb_bars(&[100.0, 99.9, 99.8, 99.7, 99.5])), -0.5);
        // Holding while neither stop (100.3) nor target (102.5) is touched.
        let mut day = up.to_vec();
        day.extend([100.6, 100.4, 101.0]);
        assert_eq!(s.weight(&orb_bars(&day)), 0.5);
        // Stop touched: out, and it does not re-enter when price recovers.
        day.extend([100.2, 101.5]);
        assert_eq!(s.weight(&orb_bars(&day)), 0.0);
        // Target reached: out.
        let mut win = up.to_vec();
        win.extend([101.0, 102.6, 102.0]);
        assert_eq!(s.weight(&orb_bars(&win)), 0.0);
        // Not enough history for the ATR: no trade.
        assert_eq!(s.weight(&minute_bars(&up)), 0.0);
        // A wide stop gives a smaller position: 1% risk / (2.0 / 100.5).
        let mut wide = orb();
        wide.stop_atr = 1.0;
        wide.max_weight = 1.0;
        assert!((wide.weight(&orb_bars(&up)) - 0.01 * 100.5 / 2.0).abs() < 1e-12);
    }

    fn rotation(target_vol: f64) -> LeveragedIndex {
        LeveragedIndex {
            index: "SPY".into(),
            risk_asset: "UPRO".into(),
            leverage: 3.0,
            safe_asset: "BIL".into(),
            sma_days: 20,
            target_vol,
            vol_days: 10,
            band: 0.05,
            bars_per_day: 1,
            bars_per_year: 252.0,
        }
    }

    #[test]
    fn blend_exposure_splits_at_the_right_ratio() {
        // 20% vol with a 40% target -> 2.0x exposure -> half TQQQ, half QQQ.
        assert_eq!(blend_exposure(2.0, 3.0), (0.5, 0.5));
        // 30% vol -> 1.333x -> one sixth in the 3x fund.
        let (w, rest) = blend_exposure(0.40 / 0.30, 3.0);
        assert!((w - 1.0 / 6.0).abs() < 1e-12, "{w}");
        assert!((rest - 5.0 / 6.0).abs() < 1e-12, "{rest}");
        // Full leverage -> all risk asset; 1.0x -> all index.
        assert_eq!(blend_exposure(3.0, 3.0), (1.0, 0.0));
        assert_eq!(blend_exposure(1.0, 3.0), (0.0, 1.0));
    }

    #[test]
    fn leverage_rotation_follows_the_trend_and_the_volatility_target() {
        let rising: Vec<f64> = (0..40).map(|i| 100.0 * 1.002f64.powi(i)).collect();
        let falling: Vec<f64> = (0..40).map(|i| 100.0 * 0.998f64.powi(i)).collect();
        let weights = |s: &LeveragedIndex, bars: &[Bar]| -> HashMap<String, f64> {
            let mut u: HashMap<&str, &[Bar]> = HashMap::new();
            u.insert("SPY", bars);
            s.targets(&u, &[]).unwrap().into_iter().collect()
        };
        // Uptrend: all in the leveraged fund. Downtrend: all in the safe asset.
        let up = wiggly(&rising, 0.001);
        assert_eq!(weights(&rotation(0.0), &up), HashMap::from([("UPRO".to_string(), 1.0)]));
        let down = wiggly(&falling, 0.001);
        assert_eq!(weights(&rotation(0.0), &down), HashMap::from([("BIL".to_string(), 1.0)]));
        // No safe asset configured: a downtrend means cash.
        let mut cash = rotation(0.0);
        cash.safe_asset = String::new();
        assert!(weights(&cash, &down).is_empty());

        // Volatility target: the wilder the index, the less leverage.
        let exposure = |w: &HashMap<String, f64>| {
            3.0 * w.get("UPRO").copied().unwrap_or(0.0) + w.get("SPY").copied().unwrap_or(0.0)
        };
        let calm = weights(&rotation(0.20), &wiggly(&rising, 0.0005));
        let rough = weights(&rotation(0.20), &wiggly(&rising, 0.004));
        let wild = weights(&rotation(0.20), &wiggly(&rising, 0.02));
        assert!((exposure(&calm) - 3.0).abs() < 1e-9, "{calm:?}"); // capped at full leverage
        assert!(exposure(&rough) > 1.0 && exposure(&rough) < 3.0, "{rough:?}");
        assert!(exposure(&wild) < 1.0 && wild.contains_key("BIL"), "{wild:?}");
        // The account is always fully allocated, never more.
        for w in [&calm, &rough, &wild] {
            assert!((w.values().sum::<f64>() - 1.0).abs() < 1e-9, "{w:?}");
        }
        // No index data: no decision (keep the current book).
        let u: HashMap<&str, &[Bar]> = HashMap::new();
        assert_eq!(rotation(0.0).targets(&u, &[]), None);
    }

    /// Daily bars from a path of closes, ending a few days into a new month
    /// so that a completed month-end exists.
    fn daily_to(path: &[f64]) -> Vec<Bar> {
        // 2024-03-05 14:30 UTC is the last bar.
        let last = 1_709_649_000;
        series(path, last - (path.len() as i64 - 1) * DAY, DAY)
    }

    #[test]
    fn tsmom_goes_with_each_assets_own_trend() {
        let s = Tsmom {
            lookbacks: vec![5, 20],
            vol_days: 10,
            target_vol: 0.10,
            max_weight: 0.5,
            max_long: 1.0,
            max_short: 0.5,
            allow_short: true,
            band: 0.02,
        };
        let path = |rate: f64, wiggle: f64| -> Vec<Bar> {
            let c: Vec<f64> = (0..60)
                .map(|i| 100.0 * (1.0 + rate).powi(i) * (1.0 + if i % 2 == 0 { wiggle } else { -wiggle }))
                .collect();
            daily_to(&c)
        };
        let (up, down, wild_up) = (path(0.004, 0.002), path(-0.004, 0.002), path(0.004, 0.008));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("UP", &up);
        u.insert("DOWN", &down);
        u.insert("WILD", &wild_up);
        let t: HashMap<String, f64> = s.targets(&u, &[]).unwrap().into_iter().collect();
        assert!(t["UP"] > 0.0 && t["DOWN"] < 0.0 && t["WILD"] > 0.0, "{t:?}");
        // Same trend, more volatility -> smaller position.
        assert!(t["UP"] > t["WILD"], "{t:?}");
        // Limits hold.
        let long: f64 = t.values().filter(|w| **w > 0.0).sum();
        let short: f64 = -t.values().filter(|w| **w < 0.0).sum::<f64>();
        assert!(long <= 1.0 + 1e-9 && short <= 0.5 + 1e-9, "{t:?}");
        // Long/flat version simply drops the falling asset.
        let flat = Tsmom { allow_short: false, lookbacks: vec![5, 20], ..s };
        let t2: HashMap<String, f64> = flat.targets(&u, &[]).unwrap().into_iter().collect();
        assert!(!t2.contains_key("DOWN") && t2["UP"] > 0.0, "{t2:?}");
    }

    #[test]
    fn value_momentum_prefers_cheap_and_rising() {
        let s = ValueMomentum {
            mom_days: 20,
            mom_skip: 2,
            val_days: 80,
            val_skip: 20,
            sides: Sides { long_frac: 0.25, short_frac: 0.25, long_gross: 1.0, short_gross: 0.5 },
            band: 0.01,
            index: "SPY".into(),
        };
        // Two-phase paths: `early` rate for the first 70 bars, `late` after.
        let path = |early: f64, late: f64| -> Vec<Bar> {
            let mut c = vec![100.0];
            for i in 1..110 {
                let r = if i < 85 { early } else { late };
                c.push(c[i - 1] * (1.0 + r));
            }
            daily_to(&c)
        };
        // Fell for a long time, now rising: cheap and strong -> best.
        let best = path(-0.004, 0.006);
        // Rose for a long time, now falling: expensive and weak -> worst.
        let worst = path(0.004, -0.006);
        let (mid1, mid2) = (path(0.004, 0.006), path(-0.004, -0.006));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("BEST", &best);
        u.insert("WORST", &worst);
        u.insert("MID1", &mid1);
        u.insert("MID2", &mid2);
        assert_eq!(
            s.targets(&u, &[]),
            Some(vec![("BEST".to_string(), 1.0), ("WORST".to_string(), -0.5)])
        );
    }

    #[test]
    fn profitability_uses_only_figures_public_at_month_end() {
        let px = daily_to(&[100.0; 40]);
        let month_end = month_end_cutoff(&px).unwrap();
        let mut data: HashMap<String, Vec<(i64, f64)>> = HashMap::new();
        data.insert("HIGH".into(), vec![(month_end - 30, 0.20)]);
        data.insert("LOW".into(), vec![(month_end - 30, 0.01)]);
        // Reported a great number, but only after the month-end: not usable yet.
        data.insert("LATE".into(), vec![(month_end - 30, 0.05), (month_end + 2, 0.90)]);
        // Has not reported for a long time: dropped.
        data.insert("STALE".into(), vec![(month_end - 400, 0.99)]);
        let s = Profitability {
            sides: Sides { long_frac: 0.34, short_frac: 0.0, long_gross: 1.0, short_gross: 0.0 },
            band: 0.01,
            index: "SPY".into(),
            data,
        };
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        for sym in ["HIGH", "LOW", "LATE", "STALE", "NODATA"] {
            u.insert(sym, &px);
        }
        assert_eq!(s.targets(&u, &[]), Some(vec![("HIGH".to_string(), 1.0)]));
    }

    #[test]
    fn percentile_ranks_run_from_zero_to_one() {
        assert_eq!(percentile_ranks(&[3.0, 1.0, 2.0]), vec![1.0, 0.0, 0.5]);
    }

    #[test]
    fn opening_range_picks_stocks_in_play_by_relative_volume() {
        let mut s = orb();
        s.top_n = 1;
        s.max_weight = 0.2;
        // Same price path, different opening volume today.
        let with_volume = |today_vol: f64, closes: &[f64]| -> Vec<Bar> {
            let mut b = orb_bars(closes);
            let n = b.len();
            for bar in &mut b[n - closes.len()..] {
                bar.volume = today_vol;
            }
            b
        };
        let up = [100.0, 100.1, 100.2, 100.3, 100.5];
        let (busy, quiet) = (with_volume(10.0, &up), with_volume(2.0, &up));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("BUSY", &busy);
        u.insert("QUIET", &quiet);
        // Only the name trading far above its normal volume is taken.
        assert_eq!(s.targets(&u, &[]), Some(vec![("BUSY".to_string(), 0.2)]));
        // After BUSY is stopped out, QUIET does not take its place.
        let mut stopped = up.to_vec();
        stopped.extend([100.2, 100.6]);
        let busy_done = with_volume(10.0, &stopped);
        let mut later = up.to_vec();
        later.extend([100.6, 100.7]);
        let quiet_on = with_volume(2.0, &later);
        u.insert("BUSY", &busy_done);
        u.insert("QUIET", &quiet_on);
        assert_eq!(s.targets(&u, &[]), Some(vec![]));
        // Minimum relative volume filters out ordinary days entirely.
        s.top_n = 0;
        s.min_rel_volume = 3.0;
        assert_eq!(s.targets(&u, &[]), Some(vec![]));
    }

    #[test]
    fn intraday_momentum_reranks_during_the_day_when_asked() {
        let active = IntradayLsMomentum {
            lookback: 2,
            skip: 0,
            long_frac: 0.5,
            short_frac: 0.0,
            long_gross: 1.0,
            short_gross: 0.0,
            band: 0.02,
            index: "SPY".into(),
            bars_per_day: 13,
            bar_secs: 1800,
            rebalance_mins: 60,
        };
        // 30-minute bars; MON 14:30 UTC is 9:30 Eastern. Bars ending 10:30,
        // 11:30, ... are re-ranking times; a bar ending 10:00 is not.
        assert!(!active.is_intraday_rebalance_bar(MON));
        assert!(active.is_intraday_rebalance_bar(MON + 1800));
        assert!(!active.is_intraday_rebalance_bar(MON + 3600));
        // Too close to the end of the session: left to the near-close rebalance.
        assert!(!active.is_intraday_rebalance_bar(MON + 12 * 1800));

        // Three flat prior sessions, then today: A jumps, B drops.
        let history = |today: &[f64]| -> Vec<Bar> {
            let mut out = Vec::new();
            for d in [3, 2, 1] {
                out.extend(series(&[100.0, 100.0], MON - d * DAY, 1800));
            }
            out.extend(series(today, MON, 1800));
            out
        };
        let (a, b, idx) = (history(&[100.0, 104.0]), history(&[100.0, 97.0]), history(&[100.0, 100.0]));
        let mut u: HashMap<&str, &[Bar]> = HashMap::new();
        u.insert("A", &a);
        u.insert("B", &b);
        u.insert("SPY", &idx);
        // Today's move decides the ranking at 10:30.
        assert_eq!(active.targets(&u, &[]), Some(vec![("A".to_string(), 1.0)]));
        // The once-a-day version says nothing at 10:30.
        let daily = IntradayLsMomentum { rebalance_mins: 0, index: "SPY".into(), ..active };
        assert_eq!(daily.targets(&u, &[]), None);
    }
}
