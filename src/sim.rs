//! Local paper-money ledger. Orders fill instantly at the latest real market
//! price (plus slippage); the ledger is saved to disk so it survives restarts.
//!
//! Positions are signed: a negative quantity is a short. Selling short adds
//! the proceeds to cash and creates a liability that is marked to market, so
//! equity = cash + sum(qty * price) holds for longs and shorts alike.

use crate::types::{Account, Fill, Position, Side};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
struct State {
    cash: f64,
    realized_pnl: f64,
    positions: HashMap<String, Position>,
}

pub struct SimBroker {
    state: State,
    path: PathBuf,
    slippage: f64,
    marks: HashMap<String, f64>,
    /// Total position value may reach this multiple of equity (1 = no margin).
    max_leverage: f64,
}

impl SimBroker {
    pub fn open(path: PathBuf, starting_cash: f64, slippage_bps: f64) -> Result<Self> {
        let state = if path.exists() {
            let text = std::fs::read_to_string(&path)?;
            serde_json::from_str(&text)
                .with_context(|| format!("corrupt ledger file {}", path.display()))?
        } else {
            State { cash: starting_cash, realized_pnl: 0.0, positions: HashMap::new() }
        };
        Ok(SimBroker { state, path, slippage: slippage_bps / 10_000.0, marks: HashMap::new(), max_leverage: 1.0 })
    }

    /// Allow borrowing on margin up to `leverage` times equity.
    pub fn with_leverage(mut self, leverage: f64) -> Self {
        self.max_leverage = leverage.max(1.0);
        self
    }

    fn save(&self) -> Result<()> {
        if let Some(dir) = self.path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let tmp = self.path.with_extension("json.tmp");
        std::fs::write(&tmp, serde_json::to_string_pretty(&self.state)?)?;
        std::fs::rename(&tmp, &self.path)?;
        Ok(())
    }

    pub fn set_mark(&mut self, symbol: &str, price: f64) {
        self.marks.insert(symbol.to_string(), price);
    }

    pub fn realized_pnl(&self) -> f64 {
        self.state.realized_pnl
    }

    pub fn positions(&self) -> HashMap<String, Position> {
        self.state.positions.clone()
    }

    fn mark(&self, symbol: &str, p: &Position) -> f64 {
        self.marks.get(symbol).copied().unwrap_or(p.avg_price)
    }

    pub fn account(&self) -> Account {
        let held: f64 = self.state.positions.iter().map(|(s, p)| p.qty * self.mark(s, p)).sum();
        Account { cash: self.state.cash, equity: self.state.cash + held }
    }

    /// `qty` is always positive; `side` gives the direction. Selling more
    /// than is held is not allowed in one order: close the long first, then
    /// open the short (and the reverse for covering).
    pub fn submit(&mut self, symbol: &str, side: Side, qty: f64, market_price: f64) -> Result<Fill> {
        if qty <= 0.0 || market_price <= 0.0 {
            bail!("invalid order: {qty} {symbol} @ {market_price}");
        }
        let (sign, price) = match side {
            Side::Buy => (1.0, market_price * (1.0 + self.slippage)),
            Side::Sell => (-1.0, market_price * (1.0 - self.slippage)),
        };
        let held = self
            .state
            .positions
            .get(symbol)
            .copied()
            .unwrap_or(Position { qty: 0.0, avg_price: 0.0 });

        match side {
            Side::Buy if held.qty < 0.0 => {
                if qty > -held.qty + 1e-9 {
                    bail!("cannot buy {qty} {symbol}: only short {}", -held.qty);
                }
            }
            Side::Buy => {
                let cost = price * qty;
                let power = self.state.cash + (self.max_leverage - 1.0) * self.account().equity;
                if cost > power + 1e-9 {
                    bail!("insufficient cash: need ${cost:.2}, have ${power:.2}");
                }
            }
            Side::Sell if held.qty > 0.0 => {
                if qty > held.qty + 1e-9 {
                    bail!("cannot sell {qty} {symbol}, only hold {}", held.qty);
                }
            }
            Side::Sell => {
                // Opening or adding to a short: total short exposure may not
                // exceed account equity.
                let shorts: f64 = self
                    .state
                    .positions
                    .iter()
                    .filter(|(_, p)| p.qty < 0.0)
                    .map(|(s, p)| -p.qty * self.mark(s, p))
                    .sum();
                let equity = self.account().equity;
                if shorts + qty * price > self.max_leverage * equity + 1e-9 {
                    bail!("short exposure limit: ${:.2} short would exceed equity ${equity:.2}", shorts + qty * price);
                }
            }
        }

        self.state.cash -= sign * qty * price;
        let new_qty = held.qty + sign * qty;
        let avg_price = if held.qty == 0.0 || held.qty.signum() == sign {
            (held.avg_price * held.qty.abs() + price * qty) / (held.qty.abs() + qty)
        } else {
            // Reducing: profit is (exit - entry) for longs, (entry - exit) for shorts.
            self.state.realized_pnl += (price - held.avg_price) * qty * held.qty.signum();
            held.avg_price
        };
        if new_qty.abs() < 1e-9 {
            self.state.positions.remove(symbol);
        } else {
            self.state.positions.insert(symbol.to_string(), Position { qty: new_qty, avg_price });
        }
        self.save()?;
        Ok(Fill { qty, price })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn broker(name: &str, cash: f64) -> (SimBroker, PathBuf) {
        let path = std::env::temp_dir().join(format!("qt-sim-{name}-{}.json", std::process::id()));
        let _ = std::fs::remove_file(&path);
        (SimBroker::open(path.clone(), cash, 0.0).unwrap(), path)
    }

    #[test]
    fn round_trip_updates_cash_and_pnl() {
        let (mut b, path) = broker("long", 1000.0);
        b.submit("X", Side::Buy, 5.0, 100.0).unwrap();
        assert!(b.submit("X", Side::Buy, 100.0, 100.0).is_err());
        b.set_mark("X", 110.0);
        let a = b.account();
        assert_eq!((a.cash, a.equity), (500.0, 1050.0));
        assert!(b.submit("X", Side::Sell, 6.0, 110.0).is_err()); // would flip to short
        b.submit("X", Side::Sell, 5.0, 110.0).unwrap();
        assert_eq!(b.account().cash, 1050.0);
        assert_eq!(b.realized_pnl(), 50.0);
        // Ledger persists across restarts.
        let b2 = SimBroker::open(path.clone(), 1.0, 0.0).unwrap();
        assert_eq!(b2.account().cash, 1050.0);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn margin_allows_buying_beyond_cash_up_to_the_leverage_limit() {
        let (b, path) = broker("margin", 1000.0);
        let mut b = b.with_leverage(2.0);
        b.submit("X", Side::Buy, 15.0, 100.0).unwrap(); // $1,500 of a $1,000 account
        assert_eq!(b.account().cash, -500.0);
        assert_eq!(b.account().equity, 1000.0);
        assert!(b.submit("Y", Side::Buy, 6.0, 100.0).is_err()); // only $500 of power left
        b.submit("Y", Side::Buy, 5.0, 100.0).unwrap();
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn short_selling_profits_when_price_falls() {
        let (mut b, path) = broker("short", 1000.0);
        b.submit("X", Side::Sell, 5.0, 100.0).unwrap();
        assert_eq!(b.positions()["X"].qty, -5.0);
        // Proceeds are in cash, but equity is unchanged until the price moves.
        let a = b.account();
        assert_eq!((a.cash, a.equity), (1500.0, 1000.0));
        b.set_mark("X", 90.0);
        assert_eq!(b.account().equity, 1050.0);
        b.set_mark("X", 120.0);
        assert_eq!(b.account().equity, 900.0);
        // Cannot short more than the account is worth, or cover more than is short.
        assert!(b.submit("X", Side::Sell, 5.0, 120.0).is_err());
        assert!(b.submit("X", Side::Buy, 6.0, 90.0).is_err());
        b.submit("X", Side::Buy, 5.0, 90.0).unwrap();
        assert!(b.positions().is_empty());
        assert_eq!(b.account().cash, 1050.0);
        assert_eq!(b.realized_pnl(), 50.0);
        let _ = std::fs::remove_file(&path);
    }
}
