//! One interface over the two ways of paper trading.

use crate::alpaca::Alpaca;
use crate::config::{BrokerKind, Config, Timeframe};
use crate::sim::SimBroker;
use crate::types::{Account, Bar, Fill, Position, Side};
use crate::dukascopy::Dukascopy;
use crate::yahoo::Yahoo;
use anyhow::Result;
use std::collections::HashMap;
use std::path::Path;

pub enum Backend {
    Sim {
        broker: SimBroker,
        data: Yahoo,
        /// Long intraday history for backtests, when configured.
        history: Option<Dukascopy>,
    },
    Alpaca(Alpaca),
}

impl Backend {
    pub fn new(cfg: &Config, data_dir: &Path) -> Result<Backend> {
        Ok(match cfg.broker {
            BrokerKind::Sim => Backend::Sim {
                broker: SimBroker::open(
                    data_dir.join("sim_ledger.json"),
                    cfg.sim.starting_cash,
                    cfg.risk.slippage_bps,
                )?
                .with_leverage(cfg.risk.max_leverage),
                data: Yahoo::new(),
                history: (cfg.history == "dukascopy")
                    .then(|| Dukascopy::new(std::path::PathBuf::from("data/cache/dukascopy"))),
            },
            BrokerKind::Alpaca => Backend::Alpaca(Alpaca::new(&cfg.alpaca)),
        })
    }

    pub fn describe(&self) -> &'static str {
        match self {
            Backend::Sim { .. } => "local paper ledger + Yahoo Finance live prices",
            Backend::Alpaca(_) => "Alpaca paper account + Alpaca market data",
        }
    }

    pub fn market_open(&self) -> Result<bool> {
        match self {
            Backend::Sim { data, .. } => data.market_open(),
            Backend::Alpaca(a) => a.market_open(),
        }
    }

    /// When the current session ends (unix seconds).
    pub fn session_close(&self) -> Result<i64> {
        match self {
            Backend::Sim { data, .. } => data.session_close(),
            Backend::Alpaca(a) => a.session_close(),
        }
    }

    pub fn bars(&self, symbol: &str, tf: Timeframe, days: i64) -> Result<Vec<Bar>> {
        match self {
            Backend::Sim { history: Some(h), data, .. } => {
                let mut bars = h.bars(symbol, tf, days)?;
                // Raw history is not adjusted for splits or dividends; line
                // it up with the adjusted daily closes.
                match data.bars(symbol, Timeframe::D1, days + 10) {
                    Ok(daily) => crate::dukascopy::adjust_to_daily(&mut bars, &daily),
                    Err(e) => println!("  WARNING {symbol}: could not load daily prices to adjust for splits: {e}"),
                }
                if let Some((ts, jump)) = crate::dukascopy::split_jump(&bars) {
                    let when = chrono::DateTime::from_timestamp(ts, 0).map(|d| d.date_naive().to_string());
                    println!(
                        "  WARNING {symbol}: price jumps {:.0}% on {} - results for this symbol are unreliable",
                        jump * 100.0,
                        when.unwrap_or_default()
                    );
                }
                Ok(bars)
            }
            Backend::Sim { data, .. } => data.bars(symbol, tf, days),
            Backend::Alpaca(a) => a.bars(symbol, tf, days),
        }
    }

    /// Fetch bars for many symbols at once (a few requests in parallel).
    /// Results come back in the same order as `symbols`.
    pub fn bars_many(&self, symbols: &[String], tf: Timeframe, days: i64) -> Vec<Result<Vec<Bar>>> {
        // The long-history source throttles hard: one request at a time.
        if matches!(self, Backend::Sim { history: Some(_), .. }) {
            return symbols.iter().map(|s| self.bars(s, tf, days)).collect();
        }
        let next = std::sync::atomic::AtomicUsize::new(0);
        let out: Vec<std::sync::Mutex<Option<Result<Vec<Bar>>>>> =
            symbols.iter().map(|_| std::sync::Mutex::new(None)).collect();
        std::thread::scope(|scope| {
            for _ in 0..symbols.len().min(8) {
                scope.spawn(|| loop {
                    let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    let Some(sym) = symbols.get(i) else { break };
                    *out[i].lock().unwrap() = Some(self.bars(sym, tf, days));
                });
            }
        });
        out.into_iter()
            .map(|m| m.into_inner().unwrap().unwrap_or_else(|| Err(anyhow::anyhow!("not fetched"))))
            .collect()
    }

    pub fn last_price(&self, symbol: &str) -> Result<f64> {
        match self {
            Backend::Sim { data, .. } => data.last_price(symbol),
            Backend::Alpaca(a) => a.last_price(symbol),
        }
    }

    /// Tell the simulator the latest price (Alpaca marks positions itself).
    pub fn set_mark(&mut self, symbol: &str, price: f64) {
        if let Backend::Sim { broker, .. } = self {
            broker.set_mark(symbol, price);
        }
    }

    pub fn account(&self) -> Result<Account> {
        match self {
            Backend::Sim { broker, .. } => Ok(broker.account()),
            Backend::Alpaca(a) => a.account(),
        }
    }

    pub fn positions(&self) -> Result<HashMap<String, Position>> {
        match self {
            Backend::Sim { broker, .. } => Ok(broker.positions()),
            Backend::Alpaca(a) => a.positions(),
        }
    }

    pub fn realized_pnl(&self) -> Option<f64> {
        match self {
            Backend::Sim { broker, .. } => Some(broker.realized_pnl()),
            Backend::Alpaca(_) => None,
        }
    }

    /// Market order. `market_price` is the latest real price, used by the simulator.
    pub fn submit(&mut self, symbol: &str, side: Side, qty: f64, market_price: f64) -> Result<Fill> {
        match self {
            Backend::Sim { broker, .. } => broker.submit(symbol, side, qty, market_price),
            Backend::Alpaca(a) => a.submit(symbol, side, qty),
        }
    }
}
