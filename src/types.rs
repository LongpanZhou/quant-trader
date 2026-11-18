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
