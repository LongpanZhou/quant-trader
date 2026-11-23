//! One interface over the two ways of paper trading.

use crate::alpaca::Alpaca;
use crate::config::{BrokerKind, Config, Timeframe};
use crate::sim::SimBroker;
use crate::types::{Account, Bar, Fill, Position, Side};
use crate::dukascopy::Dukascopy;
use crate::yahoo::{Events, Yahoo};
use anyhow::{bail, Result};
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

    /// Splits and dividends for a symbol over the last `days` calendar days.
    pub fn events(&self, symbol: &str, days: i64) -> Result<Events> {
        match self {
            Backend::Sim { data, .. } => data.events(symbol, days),
            // Alpaca has no event feed on the paper API; Yahoo is only used to
            // *detect* actions, never to price a trade.
            Backend::Alpaca(_) => Yahoo::new().events(symbol, days),
        }
    }

    /// (last market data time, exchange delay in seconds) for a symbol.
    pub fn quote_age(&self, symbol: &str) -> Result<(i64, i64)> {
        match self {
            Backend::Sim { data, .. } => data.quote_age(symbol),
            Backend::Alpaca(a) => a.quote_age(symbol),
        }
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

    /// Apply splits and dividends that happened since the ledger last checked.
    /// The sim broker keeps a persisted watermark. Alpaca paper does NOT apply
    /// corporate actions, so for Alpaca we only detect a recent split and stop
    /// trading rather than size against a corrupt position.
    pub fn apply_corporate_actions(&mut self) -> Result<usize> {
        if let Backend::Alpaca(_) = self {
            let held: Vec<String> = self.positions()?.keys().cloned().collect();
            if held.is_empty() {
                return Ok(0);
            }
            let yahoo = Yahoo::new();
            let now = chrono::Utc::now().timestamp();
            for symbol in held {
                let events = yahoo.events(&symbol, 14)?;
                if let Some((ts, ratio)) = events
                    .splits
                    .into_iter()
                    .rev()
                    .find(|(ts, _)| now - *ts <= 7 * 86_400)
                {
                    let when = chrono::DateTime::from_timestamp(ts, 0)
                        .map(|d| d.date_naive().to_string())
                        .unwrap_or_default();
                    bail!(
                        "{symbol} split {ratio}x on {when}, but Alpaca paper does not apply splits; reconcile or reset the paper account"
                    );
                }
            }
            return Ok(0);
        }
        let Backend::Sim { broker, data, .. } = self else { unreachable!() };
        let now = chrono::Utc::now().timestamp();
        let watermark = broker.last_action_ts();
        if watermark == 0 {
            // A new (or upgraded) ledger starts its clock now: applying years
            // of past dividends to today's position would be a windfall.
            broker.set_action_watermark(now)?;
            return Ok(0);
        }
        // Corporate actions are rare; checking once an hour is plenty and
        // saves a request per poll.
        if now - watermark < 3600 {
            return Ok(0);
        }
        let held: Vec<String> = broker.positions().keys().cloned().collect();
        let mut applied = 0usize;
        for symbol in held {
            // Long enough to catch a split that happened while the loop was
            // stopped; anything before the watermark is ignored below.
            let events = data.events(&symbol, 400)?;
            for (ts, ratio) in events.splits {
                if ts > watermark && ts <= now {
                    broker.apply_split(&symbol, ratio, ts)?;
                    applied += 1;
                }
            }
            for (ts, amount) in events.dividends {
                if ts > watermark && ts <= now {
                    broker.apply_dividend(&symbol, amount, ts)?;
                    applied += 1;
                }
            }
        }
        broker.set_action_watermark(now)?;
        Ok(applied)
    }

    /// Market order. `market_price` is the latest real price, used by the simulator.
    pub fn submit(&mut self, symbol: &str, side: Side, qty: f64, market_price: f64) -> Result<Fill> {
        match self {
            Backend::Sim { broker, .. } => broker.submit(symbol, side, qty, market_price),
            Backend::Alpaca(a) => a.submit(symbol, side, qty),
        }
    }
}
