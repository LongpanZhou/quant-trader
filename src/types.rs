use crate::config::Timeframe;
use serde::{Deserialize, Serialize};

/// One OHLCV candle. `ts` is the bar's start time in unix seconds (UTC).
#[derive(Debug, Clone, Copy)]
pub struct Bar {
    pub ts: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

impl Bar {
    /// True once the bar can no longer change: its whole period has elapsed.
    /// Intraday bars must also be minute-aligned — Yahoo appends the latest
    /// quote as a bar with an odd timestamp, and that is not a real candle.
    /// This is the single definition the live loop and `preflight` share.
    pub fn is_complete(&self, tf: Timeframe, now: i64) -> bool {
        self.ts + tf.secs() <= now && (tf == Timeframe::D1 || self.ts % 60 == 0)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Signal {
    Buy,
    Sell,
    Hold,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

impl Side {
    pub fn as_str(self) -> &'static str {
        match self {
            Side::Buy => "buy",
            Side::Sell => "sell",
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Position {
    pub qty: f64,
    pub avg_price: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct Account {
    pub cash: f64,
    pub equity: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct Fill {
    pub qty: f64,
    pub price: f64,
}

/// Whole shares to buy: `pct` of equity, limited by available cash.
pub fn order_qty(equity: f64, cash: f64, price: f64, pct: f64) -> f64 {
    if price <= 0.0 {
        return 0.0;
    }
    ((equity * pct).min(cash) / price).floor().max(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_bar_is_complete_only_after_its_period() {
        let b = Bar { ts: 1_000_000, open: 1.0, high: 1.0, low: 1.0, close: 1.0, volume: 1.0 };
        assert!(!b.is_complete(Timeframe::D1, b.ts + 86_399));
        assert!(b.is_complete(Timeframe::D1, b.ts + 86_400));

        // A non-minute-aligned quote bar is never a real intraday candle.
        let quote = Bar { ts: 1_000_021, ..b };
        assert!(!quote.is_complete(Timeframe::M1, quote.ts + 60));
        let minute = Bar { ts: 1_000_020, ..b };
        assert!(!minute.is_complete(Timeframe::M1, minute.ts + 59));
        assert!(minute.is_complete(Timeframe::M1, minute.ts + 60));
    }
}
