use crate::config::{Config, StrategyConfig};
use crate::indicators::{sma, stddev};
use crate::types::{Bar, Signal};
use std::collections::HashMap;

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

/// Build the configured strategy.
pub fn build(cfg: &Config) -> Box<dyn Strategy> {
    match &cfg.strategy {
        StrategyConfig::SmaCross { fast, slow } => Box::new(SmaCross { fast: *fast, slow: *slow }),
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
    }
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
// Nasdaq-100 leveraged trend following with a volatility target.
//
// While the index is above its long moving average, hold a blend of the index
// and a daily-reset leveraged fund so that expected volatility stays near
// `target_vol`; below the average, hold the safe asset (T-bills) or cash.
//
// Trend filter: Faber (2007), Gayed & Bilello (2016).
// Volatility targeting: Moreira & Muir (2017); Zarattini & Antonacci (2024).

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
            })
            .collect()
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
}
