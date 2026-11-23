//! Live trading loop: poll real prices, run the strategy on each newly
//! completed bar, enforce risk limits, and send paper orders.
//!
//! Positions are signed: a negative quantity is a short.

use crate::backend::Backend;
use crate::config::{Config, Timeframe};
use crate::strategy::Strategy;
use crate::types::{order_qty, Account, Bar, Position, Side, Signal};
use anyhow::Result;
use std::collections::HashMap;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicI64, Ordering};
use std::time::{Duration, Instant};

/// Simulated clock for replay mode (unix seconds); 0 means "use real time".
static CLOCK: AtomicI64 = AtomicI64::new(0);

/// Current time: the real clock when trading live, the simulated one in a replay.
fn now_ts() -> i64 {
    match CLOCK.load(Ordering::Relaxed) {
        0 => chrono::Utc::now().timestamp(),
        t => t,
    }
}

fn stamp() -> String {
    use chrono::TimeZone;
    match chrono::Local.timestamp_opt(now_ts(), 0).single() {
        Some(t) => t.format("%Y-%m-%d %H:%M:%S").to_string(),
        None => now_ts().to_string(),
    }
}

/// How long to sleep between polls. While the market is closed, wake at least
/// once a minute so the first decision lands at the open rather than up to
/// `poll_seconds` later.
fn poll_interval(open: Option<bool>, poll_seconds: u64) -> u64 {
    if open == Some(true) {
        poll_seconds
    } else {
        poll_seconds.min(60)
    }
}

pub fn log(msg: &str) {
    println!("[{}] {msg}", stamp());
}

fn append_csv(path: &Path, header: &str, line: &str) {
    let write = || -> std::io::Result<()> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let new = !path.exists();
        let mut f = std::fs::OpenOptions::new().create(true).append(true).open(path)?;
        if new {
            writeln!(f, "{header}")?;
        }
        writeln!(f, "{line}")
    };
    if let Err(e) = write() {
        log(&format!("WARN could not write {}: {e}", path.display()));
    }
}

/// Key used in `last_bar` for portfolio-level strategies.
const PORTFOLIO: &str = "*";

type Positions = HashMap<String, Position>;
type BarCache = HashMap<String, (Instant, Vec<Bar>)>;

pub struct Engine {
    cfg: Config,
    backend: Backend,
    strategy: Box<dyn Strategy>,
    data_dir: PathBuf,
    /// Start time of the last bar already acted on, per symbol.
    last_bar: HashMap<String, i64>,
    market_was_open: Option<bool>,
    /// Latest bars per symbol and when they were fetched.
    bars: BarCache,
    /// When the current session ends (unix seconds), if known.
    session_close: Option<i64>,
    /// For the end-of-day summary.
    day_start_equity: Option<f64>,
    trades_today: usize,
    /// When the last "still running" line was printed.
    last_heartbeat: Option<Instant>,
    /// (bar ts, attempts) for a rebalance that had failed orders and should be
    /// retried on the next poll rather than waiting for the next day.
    retry: Option<(i64, u8)>,
    /// Last market-open answer and when it was asked (saves a request per poll).
    market_checked: Option<(Instant, bool)>,
}

impl Engine {
    pub fn new(cfg: Config, backend: Backend, strategy: Box<dyn Strategy>, data_dir: PathBuf) -> Self {
        Engine {
            cfg,
            backend,
            strategy,
            data_dir,
            last_bar: HashMap::new(),
            market_was_open: None,
            bars: HashMap::new(),
            session_close: None,
            day_start_equity: None,
            trades_today: 0,
            last_heartbeat: None,
            retry: None,
            market_checked: None,
        }
    }

    pub fn run(&mut self) -> Result<()> {
        log(&format!("quant-trader started | {}", self.backend.describe()));
        let symbols = &self.cfg.symbols;
        let shown = if symbols.len() <= 45 {
            symbols.join(", ")
        } else {
            format!("{}, ... ({} more)", symbols[..10].join(", "), symbols.len() - 10)
        };
        log(&format!(
            "strategy: {} on {} bars | {} symbols: {shown}",
            self.strategy.name(),
            self.cfg.timeframe.yahoo(),
            symbols.len(),
        ));
        let acct = self.backend.account()?;
        log(&format!("paper account: equity ${:.2}, cash ${:.2}", acct.equity, acct.cash));
        log("press Ctrl+C to stop");

        loop {
            if let Err(e) = self.tick() {
                log(&format!("WARN tick failed, will retry: {e}"));
            }
            // While the market is closed, wake at least once a minute so the
            // first decision lands at the open, not up to poll_seconds later.
            let sleep = poll_interval(self.market_was_open, self.cfg.poll_seconds);
            std::thread::sleep(Duration::from_secs(sleep));
        }
    }

    /// Send one order and keep the local position map in step.
    fn order(
        &mut self,
        symbol: &str,
        side: Side,
        qty: f64,
        price: f64,
        reason: &str,
        positions: &mut Positions,
    ) -> bool {
        let fill = match self.backend.submit(symbol, side, qty, price) {
            Ok(f) => f,
            Err(e) => {
                log(&format!("WARN {symbol}: {reason} {} failed: {e}", side.as_str()));
                return false;
            }
        };
        log(&format!(
            "{} {} {symbol} @ ${:.2}  ({reason})",
            side.as_str().to_uppercase(),
            fill.qty,
            fill.price
        ));
        append_csv(
            &self.data_dir.join("trades.csv"),
            "time,symbol,side,qty,price,reason",
            &format!(
                "{},{symbol},{},{},{:.4},{reason}",
                stamp(),
                side.as_str(),
                fill.qty,
                fill.price
            ),
        );
        self.trades_today += 1;
        let sign = if side == Side::Buy { 1.0 } else { -1.0 };
        let old = positions.get(symbol).copied().unwrap_or(Position { qty: 0.0, avg_price: 0.0 });
        let qty = old.qty + sign * fill.qty;
        if qty.abs() < 1e-9 {
            positions.remove(symbol);
        } else {
            let avg_price = if old.qty == 0.0 || old.qty.signum() == sign {
                (old.avg_price * old.qty.abs() + fill.price * fill.qty) / (old.qty.abs() + fill.qty)
            } else {
                old.avg_price
            };
            positions.insert(symbol.to_string(), Position { qty, avg_price });
        }
        true
    }

    /// Cash plus what may be borrowed on margin (just cash at leverage 1).
    fn buying_power(&self, acct: &Account) -> f64 {
        acct.cash + (self.cfg.risk.max_leverage - 1.0) * acct.equity
    }

    /// Factor applied to the price when sizing a buy: expected slippage plus
    /// a small cushion for the price moving before the order fills.
    fn fill_margin(&self) -> f64 {
        1.0 + self.cfg.risk.slippage_bps / 10_000.0 + 0.001
    }

    /// Close the whole position, long or short.
    fn close(&mut self, symbol: &str, price: f64, reason: &str, positions: &mut Positions) -> bool {
        let Some(p) = positions.get(symbol).copied() else { return false };
        let side = if p.qty > 0.0 { Side::Sell } else { Side::Buy };
        self.order(symbol, side, p.qty.abs(), price, reason, positions)
    }

    /// Open a new position worth `weight` of equity; negative opens a short.
    fn open(&mut self, symbol: &str, price: f64, weight: f64, reason: &str, positions: &mut Positions) -> bool {
        if positions.len() >= self.cfg.risk.max_positions {
            log(&format!("{symbol}: entry skipped (max positions reached)"));
            return false;
        }
        let acct = match self.backend.account() {
            Ok(a) => a,
            Err(e) => {
                log(&format!("WARN {symbol}: entry skipped, account unavailable: {e}"));
                return false;
            }
        };
        let (side, qty) = if weight > 0.0 {
            // Size against a slightly higher price, so slippage on the fill
            // cannot push a full-account order past the available cash.
            (Side::Buy, order_qty(acct.equity, self.buying_power(&acct), price * self.fill_margin(), weight))
        } else {
            (Side::Sell, (acct.equity * -weight / price).floor())
        };
        if qty < 1.0 {
            log(&format!("{symbol}: entry skipped (position too small or not enough cash)"));
            return false;
        }
        self.order(symbol, side, qty, price, reason, positions)
    }

    /// Move the account towards the strategy's target weights. Sell-side
    /// orders go first (they free up cash), then buy-side orders.
    fn rebalance(
        &mut self,
        targets: &[(String, f64)],
        prices: &HashMap<String, f64>,
        positions: &mut Positions,
    ) -> Result<(bool, usize)> {
        let band = self.strategy.rebalance_band();
        let rel = self.cfg.risk.rebalance_band_rel;
        let band_for = |w: f64| if rel > 0.0 { band.min(rel * w.abs()) } else { band };
        let equity = self.backend.account()?.equity;
        let symbols = self.cfg.symbols.clone();
        let weight = |s: &str| targets.iter().find(|t| t.0 == s).map(|t| t.1).unwrap_or(0.0);
        let mut acted = false;
        let mut failed = 0usize;
        macro_rules! attempt {
            ($e:expr) => {{
                let ok = $e;
                acted |= ok;
                if !ok {
                    failed += 1;
                }
            }};
        }

        // 1. Exits (including positions on the wrong side) and reductions.
        for s in &symbols {
            let (Some(p), Some(&px)) = (positions.get(s).copied(), prices.get(s)) else { continue };
            let w = weight(s);
            if w == 0.0 || w.signum() != p.qty.signum() {
                attempt!(self.close(s, px, "rebalance", positions));
                continue;
            }
            // Signed dollars the position is over its target.
            let excess = p.qty * px - w * equity;
            if excess > band_for(w) * equity {
                let qty = (excess / px).floor();
                if qty >= 1.0 {
                    // Trim a long, or add to a short.
                    attempt!(self.order(s, Side::Sell, qty, px, "resize", positions));
                }
            }
        }
        // 2. New positions and increases, highest priority first.
        for (s, w) in targets {
            let Some(&px) = prices.get(s) else { continue };
            match positions.get(s).copied() {
                None => attempt!(self.open(s, px, *w, "rebalance", positions)),
                Some(p) => {
                    let shortfall = w * equity - p.qty * px;
                    if shortfall > band_for(*w) * equity {
                        // Add to a long (limited by cash), or cover part of a short.
                        let budget = if p.qty > 0.0 { shortfall.min(self.buying_power(&self.backend.account()?)) } else { shortfall };
                        if p.qty > 0.0 && budget + 0.005 * equity < shortfall {
                            log(&format!(
                                "WARN {s}: buy limited by cash, wanted ${:.0}, can spend ${:.0}",
                                shortfall, budget
                            ));
                        }
                        let qty = (budget / (px * self.fill_margin())).floor();
                        if qty >= 1.0 {
                            attempt!(self.order(s, Side::Buy, qty, px, "resize", positions));
                        }
                    }
                }
            }
        }
        Ok((acted, failed))
    }

    /// Calendar days of history to load: enough to warm up the strategy
    /// (trading days are about 252 of 365), plus a weekend/holiday margin.
    fn history_days(&self) -> i64 {
        let per_day = self.cfg.timeframe.bars_per_day() as f64;
        (self.strategy.warmup() as f64 / per_day * 1.6).ceil() as i64 + 4
    }

    /// Replay the most recent trading session through the live decision
    /// code, one bar at a time, against a scratch paper account. Uses real
    /// recorded prices; nothing here knows about bars "in the future".
    pub fn replay(&mut self) -> Result<()> {
        let tf = self.cfg.timeframe;
        log(&format!("REPLAY | strategy: {} on {} bars", self.strategy.name(), tf.yahoo()));
        let symbols = self.cfg.symbols.clone();
        let results = self.backend.bars_many(&symbols, tf, self.history_days() + 3);
        let mut full: HashMap<String, Vec<Bar>> = HashMap::new();
        for (sym, res) in symbols.iter().zip(results) {
            match res {
                Ok(b) if !b.is_empty() => {
                    full.insert(sym.clone(), b);
                }
                Ok(_) => log(&format!("WARN {sym}: no data")),
                Err(e) => log(&format!("WARN {sym}: {e}")),
            }
        }
        // The latest session present in the data.
        let real_now = chrono::Utc::now().timestamp();
        let last_ts = full
            .values()
            .flatten()
            .filter(|b| b.ts + tf.secs() <= real_now)
            .map(|b| b.ts)
            .max()
            .ok_or_else(|| anyhow::anyhow!("no price history could be loaded"))?;
        let day = last_ts.div_euclid(86_400);
        let first_ts = full
            .values()
            .flatten()
            .filter(|b| b.ts.div_euclid(86_400) == day)
            .map(|b| b.ts)
            .min()
            .unwrap_or(last_ts);

        let start_equity = self.backend.account()?.equity;
        if tf != Timeframe::D1 {
            self.session_close = Some(first_ts + 23_400); // a regular 6.5-hour session
        }
        let mut clock = first_ts + tf.secs();
        CLOCK.store(clock, Ordering::Relaxed);
        log(&format!("replaying the session from its first bar; starting equity ${start_equity:.2}"));
        let mut steps = 0;
        while clock <= last_ts + tf.secs() {
            CLOCK.store(clock, Ordering::Relaxed);
            // What a live poll would have seen at this moment: completed bars only.
            let cache: BarCache = full
                .iter()
                .filter_map(|(s, b)| {
                    let n = b.partition_point(|x| x.ts + tf.secs() <= clock);
                    (n > 0).then(|| (s.clone(), (Instant::now(), b[..n].to_vec())))
                })
                .collect();
            let mut positions = self.backend.positions()?;
            self.decide(&cache, &mut positions)?;
            clock += tf.secs();
            steps += 1;
        }
        let acct = self.backend.account()?;
        let positions = self.backend.positions()?;
        log(&format!(
            "REPLAY DONE | {steps} bars | {} orders | equity ${:.2} ({:+.2}%) | {} position(s) still open",
            self.trades_today,
            acct.equity,
            (acct.equity / start_equity - 1.0) * 100.0,
            positions.len()
        ));
        CLOCK.store(0, Ordering::Relaxed);
        Ok(())
    }

    /// Refresh the bar cache. Daily bars only change once a day, so symbols
    /// that are not held are re-fetched at most hourly; held symbols are
    /// refreshed on every poll so stops and marks use the live price.
    fn refresh_bars(&mut self, positions: &Positions) {
        let tf = self.cfg.timeframe;
        let now = chrono::Utc::now().timestamp();
        // With stop-loss / take-profit switched on, held symbols need a fresh
        // price on every poll. Otherwise prices only matter once per bar.
        let stops = self.cfg.risk.stop_loss_pct > 0.0 || self.cfg.risk.take_profit_pct > 0.0;
        let need: Vec<String> = self
            .cfg
            .symbols
            .iter()
            .filter(|s| {
                let Some((at, bars)) = self.bars.get(*s) else { return true };
                if tf == Timeframe::D1 {
                    return positions.contains_key(*s) || at.elapsed() >= Duration::from_secs(3600);
                }
                // End of the newest finished bar already in the cache.
                let last_end = bars
                    .iter()
                    .rev()
                    .find(|b| b.ts % 60 == 0 && b.ts + tf.secs() <= now)
                    .map_or(0, |b| b.ts + tf.secs());
                // Never ask for the same symbol more often than this, even
                // while waiting for a bar the data source is slow to publish.
                let min_gap = (tf.secs() / 6).clamp(10, 60);
                let waited = at.elapsed().as_secs() as i64;
                (stops && positions.contains_key(*s))
                    // A newer bar should have finished by now.
                    || (now >= last_end + tf.secs() && waited >= min_gap)
                    || waited >= tf.secs().max(60)
            })
            .cloned()
            .collect();
        let first_load = need.iter().filter(|s| !self.bars.contains_key(*s)).count();
        if first_load > 50 {
            log(&format!("loading price history for {first_load} symbols..."));
        }
        // Intraday: once a symbol's history is loaded, each poll only fetches
        // the newest bars and splices them onto what is already cached.
        let history = self.history_days();
        let (recent, full): (Vec<String>, Vec<String>) = need
            .into_iter()
            .partition(|s| tf != Timeframe::D1 && self.bars.contains_key(s));
        let mut failed: Vec<String> = Vec::new();
        let full_results = self.backend.bars_many(&full, tf, history);
        for (sym, res) in full.iter().zip(full_results) {
            match res {
                Ok(b) if !b.is_empty() => {
                    self.bars.insert(sym.clone(), (Instant::now(), b));
                }
                Ok(_) => failed.push(format!("{sym} (empty)")),
                Err(e) => failed.push(format!("{sym} ({e})")),
            }
        }
        let oldest = chrono::Utc::now().timestamp() - history * 86_400;
        let recent_results = self.backend.bars_many(&recent, tf, 2);
        for (sym, res) in recent.iter().zip(recent_results) {
            match (res, self.bars.get_mut(sym)) {
                (Ok(new), Some((at, old))) if !new.is_empty() => {
                    let cut = new[0].ts;
                    old.retain(|b| b.ts < cut && b.ts >= oldest);
                    old.extend(new);
                    *at = Instant::now();
                }
                (Ok(_), _) => failed.push(format!("{sym} (empty)")),
                (Err(e), _) => failed.push(format!("{sym} ({e})")),
            }
        }
        if !failed.is_empty() {
            log(&format!("WARN no fresh data for {} symbol(s), e.g. {}", failed.len(), failed[0]));
        }
    }

    fn tick(&mut self) -> Result<()> {
        // Ask whether the market is open at most every 30 seconds.
        let open = match self.market_checked {
            Some((at, open)) if at.elapsed() < Duration::from_secs(30) => open,
            _ => {
                // QT_ASSUME_OPEN=1 is a testing aid: it runs the full polling
                // loop outside market hours. Intraday strategies will not
                // trade (stale prices are never acted on); daily strategies
                // will, so only use it with a throwaway account.
                let open = std::env::var_os("QT_ASSUME_OPEN").is_some() || self.backend.market_open()?;
                self.market_checked = Some((Instant::now(), open));
                open
            }
        };
        if self.market_was_open != Some(open) {
            log(if open {
                "market is OPEN - trading"
            } else {
                "market is CLOSED - waiting for the next session (US regular hours 9:30-16:00 ET)"
            });
            if open {
                // New session: note when it ends and where the account starts.
                self.session_close = self.backend.session_close().ok();
                self.day_start_equity = self.backend.account().ok().map(|a| a.equity);
                self.trades_today = 0;
            } else if self.market_was_open == Some(true) {
                if let (Ok(a), Some(start)) = (self.backend.account(), self.day_start_equity) {
                    log(&format!(
                        "SESSION SUMMARY | equity ${:.2} | day P&L ${:+.2} ({:+.2}%) | {} orders",
                        a.equity,
                        a.equity - start,
                        (a.equity / start - 1.0) * 100.0,
                        self.trades_today
                    ));
                }
            }
            self.market_was_open = Some(open);
        }
        if !open {
            // Show the window is alive while it waits.
            if self.last_heartbeat.map_or(true, |t| t.elapsed() >= Duration::from_secs(1800)) {
                if self.last_heartbeat.is_some() {
                    log("still running - waiting for the market to open");
                }
                self.last_heartbeat = Some(Instant::now());
            }
            return Ok(());
        }
        // Splits and dividends happen outside the API: apply anything since
        // the last poll before taking the position snapshot or trading, so a
        // held fund's price and share count stay consistent.
        match self.backend.apply_corporate_actions() {
            Ok(0) => {}
            Ok(n) => log(&format!("applied {n} corporate action(s) to the paper ledger")),
            Err(e) => log(&format!("WARN could not apply corporate actions: {e}")),
        }
        let mut positions = self.backend.positions()?;
        self.refresh_bars(&positions);
        // Lend the cache out so orders (which need `&mut self`) can be sent
        // while bar slices are still borrowed.
        let cache = std::mem::take(&mut self.bars);
        let result = self.decide(&cache, &mut positions);
        self.bars = cache;
        self.heartbeat(&positions);
        result
    }

    /// Print a status line at a steady rhythm, so a quiet strategy (one that
    /// trades once a day, or is finished for the day) is visibly still alive.
    fn heartbeat(&mut self, positions: &Positions) {
        let every = if self.cfg.timeframe == Timeframe::D1 { 300 } else { 60 };
        if self.last_heartbeat.is_some_and(|t| t.elapsed() < Duration::from_secs(every)) {
            return;
        }
        self.last_heartbeat = Some(Instant::now());
        let Ok(acct) = self.backend.account() else { return };
        let shorts = positions.values().filter(|p| p.qty < 0.0).count();
        let day = match self.day_start_equity {
            Some(start) if start > 0.0 => format!(" ({:+.2}% today)", (acct.equity / start - 1.0) * 100.0),
            _ => String::new(),
        };
        let with_data = self.cfg.symbols.iter().filter(|s| self.bars.contains_key(*s)).count();
        log(&format!(
            "running | equity ${:.2}{day} | {} long, {} short | {} orders today | prices for {}/{} symbols",
            acct.equity,
            positions.len() - shorts,
            shorts,
            self.trades_today,
            with_data,
            self.cfg.symbols.len()
        ));
    }

    fn decide(&mut self, cache: &BarCache, positions: &mut Positions) -> Result<()> {
        let tf = self.cfg.timeframe;
        let risk = self.cfg.risk.clone();
        let symbols = self.cfg.symbols.clone();
        let mut acted = false;
        let now = now_ts();
        let fresh = |last: &Bar| now - (last.ts + tf.secs()) <= tf.stale_after_secs();

        // --- 1. Mark positions, apply risk exits, find completed bars ---
        let mut complete: HashMap<&str, &[Bar]> = HashMap::new();
        let mut prices: HashMap<String, f64> = HashMap::new();
        for symbol in &symbols {
            let Some((_, bars)) = cache.get(symbol) else { continue };
            let price = bars[bars.len() - 1].close;
            self.backend.set_mark(symbol, price);
            prices.insert(symbol.clone(), price);

            // Checked on every poll against the live price.
            if let Some(p) = positions.get(symbol).copied() {
                // Profit as a fraction of entry: price up is good for a long, bad for a short.
                let gain = (price / p.avg_price - 1.0) * p.qty.signum();
                let reason = if risk.stop_loss_pct > 0.0 && gain <= -risk.stop_loss_pct {
                    Some("stop-loss")
                } else if risk.take_profit_pct > 0.0 && gain >= risk.take_profit_pct {
                    Some("take-profit")
                } else {
                    None
                };
                if let Some(reason) = reason {
                    acted |= self.close(symbol, price, reason, positions);
                    continue; // no strategy decision for this symbol this tick
                }
            }

            // Keep only completed bars for the strategy.
            // (Yahoo appends the latest quote as a bar with an odd timestamp;
            // only minute-aligned bars count as real intraday bars.)
            let done = bars
                .iter()
                .take_while(|b| b.is_complete(tf, now))
                .count();
            if done > 0 {
                complete.insert(symbol.as_str(), &bars[..done]);
            }
        }

        // --- Safety net: flat before the close, whatever the strategy says ---
        let flatten = risk.flatten_before_close_minutes as i64 * 60;
        let closing = flatten > 0 && self.session_close.is_some_and(|c| now >= c - flatten);
        if closing {
            for symbol in &symbols {
                if let (true, Some(&px)) = (positions.contains_key(symbol), prices.get(symbol)) {
                    acted |= self.close(symbol, px, "end of day", positions);
                }
            }
        }

        // --- 2. Strategy: evaluated once per newly completed bar ---
        let lookback = self.strategy.lookback();
        if closing {
            // No new decisions this late in the session.
        } else if self.strategy.is_portfolio() {
            let newest = complete.values().filter_map(|b| b.last()).max_by_key(|b| b.ts).copied();
            if let Some(last) = newest {
                let new_bar = self.last_bar.get(PORTFOLIO) != Some(&last.ts);
                let retrying = self
                    .retry
                    .as_ref()
                    .is_some_and(|(ts, n)| *ts == last.ts && *n < 3);
                if new_bar || retrying {
                    if new_bar {
                        self.last_bar.insert(PORTFOLIO.to_string(), last.ts);
                    }
                    // Never trade on stale data (holidays, feed gaps).
                    if fresh(&last) {
                        let universe: HashMap<&str, &[Bar]> = complete
                            .iter()
                            .map(|(s, b)| (*s, &b[b.len().saturating_sub(lookback)..]))
                            .collect();
                        let held: Vec<&str> = symbols
                            .iter()
                            .filter(|s| positions.contains_key(*s))
                            .map(|s| s.as_str())
                            .collect();
                        if let Some(targets) = self.strategy.targets(&universe, &held) {
                            let (did, failed) = self.rebalance(&targets, &prices, positions)?;
                            acted |= did;
                            if failed > 0 {
                                let attempts = self
                                    .retry
                                    .as_ref()
                                    .filter(|(ts, _)| *ts == last.ts)
                                    .map(|(_, n)| *n)
                                    .unwrap_or(0);
                                if attempts < 3 {
                                    self.retry = Some((last.ts, attempts + 1));
                                    log(&format!(
                                        "WARN {failed} order(s) failed; retrying the rebalance on the next poll ({}/3)",
                                        attempts + 1
                                    ));
                                } else {
                                    log("WARN rebalance still incomplete after 3 retries; waiting for the next bar");
                                    self.retry = None;
                                }
                            } else {
                                self.retry = None;
                            }
                        } else {
                            // No decision on this bar: nothing to retry.
                            self.retry = None;
                        }
                    }
                }
            }
        } else {
            for symbol in &symbols {
                let Some(bars) = complete.get(symbol.as_str()) else { continue };
                let last = bars[bars.len() - 1];
                if self.last_bar.get(symbol) == Some(&last.ts) {
                    continue;
                }
                self.last_bar.insert(symbol.clone(), last.ts);
                if !fresh(&last) {
                    continue;
                }
                // Per-symbol strategies are long-only.
                let held = positions.get(symbol).is_some_and(|p| p.qty > 0.0);
                let window = &bars[bars.len().saturating_sub(lookback)..];
                let price = prices[symbol];
                match self.strategy.signal(window, held) {
                    Signal::Sell if held => acted |= self.close(symbol, price, "signal", positions),
                    Signal::Buy if !positions.contains_key(symbol) => {
                        acted |= self.open(symbol, price, risk.position_pct, "signal", positions)
                    }
                    _ => {}
                }
            }
        }

        let acct = self.backend.account()?;
        append_csv(
            &self.data_dir.join("equity.csv"),
            "time,equity,cash,positions",
            &format!(
                "{},{:.2},{:.2},{}",
                stamp(),
                acct.equity,
                acct.cash,
                positions.len()
            ),
        );
        if acted {
            let shorts = positions.values().filter(|p| p.qty < 0.0).count();
            log(&format!(
                "equity ${:.2} | cash ${:.2} | {} long, {} short",
                acct.equity,
                acct.cash,
                positions.len() - shorts,
                shorts
            ));
        }
        Ok(())
    }
}

/// Print the account, open positions and their unrealised P&L.
pub fn status(cfg: &Config, backend: &mut Backend) -> Result<()> {
    println!("Backend : {}", backend.describe());
    println!(
        "Market  : {}",
        match backend.market_open() {
            Ok(true) => "open".to_string(),
            Ok(false) => "closed".to_string(),
            Err(e) => format!("unknown ({e})"),
        }
    );
    // A split or dividend may have happened while the loop was stopped.
    match backend.apply_corporate_actions() {
        Ok(n) if n > 0 => println!("Actions : applied {n} corporate action(s)"),
        Ok(_) => {}
        Err(e) => println!("Actions : WARN could not apply corporate actions: {e}"),
    }
    let positions = backend.positions()?;
    let mut rows = Vec::new();
    for (sym, p) in &positions {
        let price = backend.last_price(sym).unwrap_or(p.avg_price);
        backend.set_mark(sym, price);
        rows.push((sym.clone(), *p, price));
    }
    rows.sort_by(|a, b| a.0.cmp(&b.0));
    let acct = backend.account()?;
    println!("Equity  : ${:.2}", acct.equity);
    println!("Cash    : ${:.2}", acct.cash);
    if let Some(r) = backend.realized_pnl() {
        println!("Realized P&L : ${r:+.2}");
        println!(
            "Total return : {:+.2}% (from ${:.2} starting cash)",
            (acct.equity / cfg.sim.starting_cash - 1.0) * 100.0,
            cfg.sim.starting_cash
        );
    }
    if rows.is_empty() {
        println!("Positions: none");
    } else {
        println!("\n{:<8}{:>8}{:>12}{:>12}{:>12}{:>9}", "SYMBOL", "QTY", "ENTRY", "LAST", "P&L $", "P&L %");
        for (sym, p, price) in rows {
            println!(
                "{:<8}{:>8}{:>12.2}{:>12.2}{:>+12.2}{:>+8.2}%",
                sym,
                p.qty,
                p.avg_price,
                price,
                (price - p.avg_price) * p.qty,
                (price / p.avg_price - 1.0) * p.qty.signum() * 100.0
            );
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::poll_interval;

    #[test]
    fn closed_market_polls_at_least_every_minute() {
        assert_eq!(poll_interval(Some(true), 600), 600);
        assert_eq!(poll_interval(Some(false), 600), 60);
        assert_eq!(poll_interval(None, 600), 60);
        assert_eq!(poll_interval(Some(false), 30), 30);
        assert_eq!(poll_interval(Some(true), 30), 30);
    }
}
