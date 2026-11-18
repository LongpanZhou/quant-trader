//! Replays real historical bars through the same strategy and risk rules
//! the live loop uses, with one shared cash pool across all symbols.
//!
//! Fill model: signals fill at the close of the bar that produced them;
//! stop-loss / take-profit fill at their trigger price (or the bar's open if
//! it gapped through). Slippage is applied to every fill. If a bar touches
//! both stop and target, the stop is assumed to have hit first.
//!
//! Positions are signed (negative = short). Short sale proceeds are added to
//! cash and the borrowed shares are marked to market as a liability; a
//! borrow fee is charged on the short value.

use crate::backend::Backend;
use crate::config::Config;
use crate::strategy::Strategy;
use crate::types::{order_qty, Bar, Position, Signal};
use anyhow::{bail, Result};
use std::collections::{BTreeSet, HashMap};

pub struct Report {
    pub bars: usize,
    pub span_days: f64,
    pub start_equity: f64,
    pub end_equity: f64,
    pub buy_hold_return: f64,
    pub buy_hold_drawdown: f64,
    /// SPY buy & hold over the same window, when SPY is among the symbols.
    pub index_return: Option<f64>,
    pub index_drawdown: Option<f64>,
    pub max_drawdown: f64,
    pub sharpe: f64,
    /// Average long and short exposure as fractions of equity.
    pub long_exposure: f64,
    pub short_exposure: f64,
    pub trade_pnls: Vec<f64>,
    /// Profit split by side.
    pub long_pnl: f64,
    pub short_pnl: f64,
}

/// Bars before `trade_from` are only used to warm up indicators; trading and
/// all statistics start at `trade_from`.
pub fn simulate(
    cfg: &Config,
    strat: &dyn Strategy,
    data: &HashMap<String, Vec<Bar>>,
    trade_from: i64,
) -> Report {
    let lookback = strat.lookback();
    let risk = &cfg.risk;
    let slip = risk.slippage_bps / 10_000.0;
    let borrow_per_bar = risk.short_borrow_pct / cfg.timeframe.bars_per_year();

    let timeline: BTreeSet<i64> = data.values().flatten().map(|b| b.ts).collect();
    let mut symbols: Vec<&String> = data.keys().collect();
    symbols.sort();
    let index_of: HashMap<&str, usize> = symbols.iter().enumerate().map(|(i, s)| (s.as_str(), i)).collect();
    let n = symbols.len();

    // Per-symbol state, indexed like `symbols`.
    let mut next = vec![0usize; n];
    let mut last_px = vec![f64::NAN; n];
    let mut pos: Vec<Option<Position>> = vec![None; n];
    // Profit already banked by trimming a position that is still open.
    let mut partial = vec![0.0f64; n];
    let mut bh_start = vec![f64::NAN; n];

    let mut cash = cfg.sim.starting_cash;
    // Margin: money that may be borrowed on top of cash, as a share of equity.
    let lev = risk.max_leverage - 1.0;
    let (mut prev_day, mut prev_loan) = (None::<i64>, 0.0f64);
    let mut trade_pnls = Vec::new();
    let (mut long_pnl, mut short_pnl) = (0.0, 0.0);
    let mut curve = Vec::new();
    let mut bh_curve = Vec::new();
    let (mut long_sum, mut short_sum) = (0.0, 0.0);
    let (mut first_ts, mut last_ts) = (None, 0);

    // Signed market value of all positions.
    let held_value = |pos: &[Option<Position>], px: &[f64]| -> f64 {
        pos.iter().zip(px).filter_map(|(p, x)| p.map(|p| p.qty * x)).sum()
    };

    // Buy (`qty` > 0) or sell (`qty` < 0) at `price`, before slippage.
    // Closing trades are recorded once the position is flat.
    macro_rules! trade {
        ($i:expr, $qty:expr, $price:expr) => {{
            let (i, qty): (usize, f64) = ($i, $qty);
            let px = $price * (1.0 + slip * qty.signum());
            cash -= qty * px;
            let old = pos[i].unwrap_or(Position { qty: 0.0, avg_price: 0.0 });
            let new_qty = old.qty + qty;
            if old.qty == 0.0 || old.qty.signum() == qty.signum() {
                let avg = (old.avg_price * old.qty.abs() + px * qty.abs()) / (old.qty.abs() + qty.abs());
                pos[i] = Some(Position { qty: new_qty, avg_price: avg });
            } else {
                // Reducing: realise profit on the part that was closed.
                let pnl = (px - old.avg_price) * qty.abs() * old.qty.signum();
                if old.qty > 0.0 {
                    long_pnl += pnl;
                } else {
                    short_pnl += pnl;
                }
                partial[i] += pnl;
                if new_qty.abs() < 1e-9 {
                    trade_pnls.push(partial[i]);
                    partial[i] = 0.0;
                    pos[i] = None;
                } else {
                    pos[i] = Some(Position { qty: new_qty, avg_price: old.avg_price });
                }
            }
        }};
    }

    for &ts in &timeline {
        let trading = ts >= trade_from;
        for i in 0..n {
            let bars = &data[symbols[i]];
            let k = next[i];
            if k >= bars.len() || bars[k].ts != ts {
                continue;
            }
            next[i] = k + 1;
            let bar = bars[k];
            last_px[i] = bar.close;
            if !trading {
                continue;
            }

            // Risk exits first, using this bar's range.
            if let Some(p) = pos[i] {
                let exit = if p.qty > 0.0 {
                    let stop = p.avg_price * (1.0 - risk.stop_loss_pct);
                    let target = p.avg_price * (1.0 + risk.take_profit_pct);
                    if risk.stop_loss_pct > 0.0 && bar.low <= stop {
                        Some(bar.open.min(stop))
                    } else if risk.take_profit_pct > 0.0 && bar.high >= target {
                        Some(bar.open.max(target))
                    } else {
                        None
                    }
                } else {
                    // Short: loses when the price rises.
                    let stop = p.avg_price * (1.0 + risk.stop_loss_pct);
                    let target = p.avg_price * (1.0 - risk.take_profit_pct);
                    if risk.stop_loss_pct > 0.0 && bar.high >= stop {
                        Some(bar.open.max(stop))
                    } else if risk.take_profit_pct > 0.0 && bar.low <= target {
                        Some(bar.open.min(target))
                    } else {
                        None
                    }
                };
                if let Some(px) = exit {
                    trade!(i, -p.qty, px);
                    continue;
                }
            }
            if strat.is_portfolio() {
                continue;
            }

            // Per-symbol strategies are long-only.
            let start = (k + 1).saturating_sub(lookback);
            let held = pos[i];
            match strat.signal(&bars[start..=k], held.is_some()) {
                Signal::Sell => {
                    if let Some(p) = held {
                        trade!(i, -p.qty, bar.close);
                    }
                }
                Signal::Buy
                    if held.is_none() && pos.iter().filter(|p| p.is_some()).count() < risk.max_positions =>
                {
                    let eq = cash + held_value(&pos, &last_px);
                    let qty = order_qty(eq, cash + lev * eq, bar.close * (1.0 + slip), risk.position_pct);
                    if qty >= 1.0 {
                        trade!(i, qty, bar.close);
                    }
                }
                _ => {}
            }
        }

        if !trading {
            continue;
        }

        if strat.is_portfolio() {
            let universe: HashMap<&str, &[Bar]> = (0..n)
                .filter(|&i| next[i] > 0)
                .map(|i| (symbols[i].as_str(), &data[symbols[i]][next[i].saturating_sub(lookback)..next[i]]))
                .collect();
            let held: Vec<&str> = (0..n).filter(|&i| pos[i].is_some()).map(|i| symbols[i].as_str()).collect();
            if let Some(targets) = strat.targets(&universe, &held) {
                let band = strat.rebalance_band();
                let eq = cash + held_value(&pos, &last_px);
                let mut want = vec![0.0f64; n];
                for (s, w) in &targets {
                    if let Some(&i) = index_of.get(s.as_str()) {
                        want[i] = *w;
                    }
                }
                // 1. Exits (including positions on the wrong side) and sell-side resizes.
                for i in 0..n {
                    let Some(p) = pos[i] else { continue };
                    let close = last_px[i];
                    if want[i] == 0.0 || want[i].signum() != p.qty.signum() {
                        trade!(i, -p.qty, close);
                        continue;
                    }
                    let excess = p.qty * close - want[i] * eq;
                    if excess > band * eq {
                        let qty = (excess / close).floor();
                        if qty >= 1.0 {
                            trade!(i, -qty, close);
                        }
                    }
                }
                // 2. New positions and buy-side resizes, highest priority first.
                for (s, w) in &targets {
                    let Some(&i) = index_of.get(s.as_str()) else { continue };
                    let close = last_px[i];
                    if !(close > 0.0) {
                        continue;
                    }
                    match pos[i] {
                        None => {
                            if pos.iter().filter(|p| p.is_some()).count() >= risk.max_positions {
                                continue;
                            }
                            let qty = if *w > 0.0 {
                                order_qty(eq, cash + lev * eq, close * (1.0 + slip), *w)
                            } else {
                                -(eq * -w / close).floor()
                            };
                            if qty.abs() >= 1.0 {
                                trade!(i, qty, close);
                            }
                        }
                        Some(p) => {
                            let shortfall = w * eq - p.qty * close;
                            if shortfall > band * eq {
                                let budget = if p.qty > 0.0 { shortfall.min(cash + lev * eq) } else { shortfall };
                                let qty = (budget / (close * (1.0 + slip))).floor();
                                if qty >= 1.0 {
                                    trade!(i, qty, close);
                                }
                            }
                        }
                    }
                }
            }
        }

        // Interest on money still borrowed overnight (intraday borrowing is free).
        let day = ts.div_euclid(86_400);
        if let Some(pd) = prev_day {
            if day != pd {
                cash -= prev_loan * risk.margin_rate_pct * (day - pd) as f64 / 365.0;
            }
        }
        prev_day = Some(day);

        // Cost of borrowing the shorted shares.
        let (mut longs, mut shorts) = (0.0, 0.0);
        for i in 0..n {
            if let Some(p) = pos[i] {
                let v = p.qty * last_px[i];
                if v > 0.0 {
                    longs += v;
                } else {
                    shorts -= v;
                }
            }
        }
        let fee = shorts * borrow_per_bar;
        cash -= fee;
        short_pnl -= fee;

        let eq = cash + longs - shorts;
        prev_loan = (-cash).max(0.0);
        long_sum += longs / eq;
        short_sum += shorts / eq;
        curve.push(eq);

        // Equal-weight buy & hold of every symbol, for comparison.
        let (mut total, mut count) = (0.0, 0);
        for i in 0..n {
            if last_px[i].is_nan() {
                continue;
            }
            if bh_start[i].is_nan() {
                bh_start[i] = last_px[i];
            }
            total += last_px[i] / bh_start[i];
            count += 1;
        }
        bh_curve.push(if count > 0 { total / count as f64 } else { 1.0 });
        first_ts.get_or_insert(ts);
        last_ts = ts;
    }

    // Statistics
    let end_equity = curve.last().copied().unwrap_or(cash);
    let drawdown = |curve: &[f64]| {
        let (mut peak, mut dd) = (f64::MIN, 0.0f64);
        for &e in curve {
            peak = peak.max(e);
            dd = dd.max(1.0 - e / peak);
        }
        dd
    };
    let rets: Vec<f64> = curve.windows(2).map(|w| w[1] / w[0] - 1.0).collect();
    let sharpe = if rets.len() > 1 {
        let mean = rets.iter().sum::<f64>() / rets.len() as f64;
        let var = rets.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / (rets.len() - 1) as f64;
        if var > 0.0 {
            mean / var.sqrt() * cfg.timeframe.bars_per_year().sqrt()
        } else {
            0.0
        }
    } else {
        0.0
    };
    let index_return = data.get("SPY").and_then(|b| {
        let first = b.iter().find(|x| x.ts >= trade_from)?;
        Some(b.last()?.close / first.close - 1.0)
    });
    let index_drawdown = data.get("SPY").map(|b| {
        let closes: Vec<f64> = b.iter().filter(|x| x.ts >= trade_from).map(|x| x.close).collect();
        drawdown(&closes)
    });
    let bars = curve.len().max(1) as f64;

    Report {
        bars: curve.len(),
        span_days: (last_ts - first_ts.unwrap_or(last_ts)) as f64 / 86_400.0,
        start_equity: cfg.sim.starting_cash,
        end_equity,
        buy_hold_return: bh_curve.last().map(|v| v - 1.0).unwrap_or(0.0),
        buy_hold_drawdown: drawdown(&bh_curve),
        index_return,
        index_drawdown,
        max_drawdown: drawdown(&curve),
        sharpe,
        long_exposure: long_sum / bars,
        short_exposure: short_sum / bars,
        trade_pnls,
        long_pnl,
        short_pnl,
    }
}

pub fn run(cfg: &Config, strat: &dyn Strategy, backend: &Backend) -> Result<()> {
    let tf = cfg.timeframe;
    println!(
        "Backtest: {} | {} bars | last {} days | {} symbols",
        strat.name(),
        tf.yahoo(),
        cfg.backtest.days,
        cfg.symbols.len()
    );

    // Load extra history in front of the test window so indicators are warm
    // on the first tested day.
    let now = chrono::Utc::now().timestamp();
    let warmup_days = (strat.warmup() as f64 / tf.bars_per_day() as f64 * 1.5).ceil() as i64 + 5;
    let trade_from = now - cfg.backtest.days * 86_400;

    if cfg.symbols.len() > 100 {
        println!("Downloading price history for {} symbols...", cfg.symbols.len());
    }
    let mut data = HashMap::new();
    let mut failed = Vec::new();
    let results = backend.bars_many(&cfg.symbols, tf, cfg.backtest.days + warmup_days);
    for (sym, res) in cfg.symbols.iter().zip(results) {
        match res {
            Ok(mut b) => {
                b.retain(|x| x.ts + tf.secs() <= now); // drop a still-forming bar
                if b.is_empty() {
                    failed.push(format!("{sym} (no data)"));
                } else {
                    data.insert(sym.clone(), b);
                }
            }
            Err(e) => failed.push(format!("{sym} ({e})")),
        }
    }
    if data.is_empty() {
        bail!("no historical data could be loaded: {}", failed.join(", "));
    }
    let total: usize = data.values().map(|b| b.len()).sum();
    println!("Loaded {total} bars for {} symbols", data.len());
    if !failed.is_empty() {
        let shown: Vec<&str> = failed.iter().take(5).map(|s| s.as_str()).collect();
        println!("Skipped {}: {}{}", failed.len(), shown.join(", "), if failed.len() > 5 { ", ..." } else { "" });
    }

    let r = simulate(cfg, strat, &data, trade_from);
    let wins: Vec<f64> = r.trade_pnls.iter().copied().filter(|p| *p > 0.0).collect();
    let losses: Vec<f64> = r.trade_pnls.iter().copied().filter(|p| *p <= 0.0).collect();
    let gross_win: f64 = wins.iter().sum();
    let gross_loss: f64 = -losses.iter().sum::<f64>();
    let n = r.trade_pnls.len();
    let total_ret = r.end_equity / r.start_equity - 1.0;
    let years = r.span_days / 365.25;

    println!("\n================ RESULTS ================");
    println!("Period tested        : {:.0} days ({} bars)", r.span_days, r.bars);
    println!("Starting equity      : ${:.2}", r.start_equity);
    println!("Ending equity        : ${:.2}", r.end_equity);
    let ann = |x: f64| ((1.0 + x).powf(1.0 / years.max(1e-9)) - 1.0) * 100.0;
    let show = |label: &str, total: f64| {
        if years >= 1.0 {
            println!("{label:<21}: {:+.2}%  ({:+.2}% a year)", total * 100.0, ann(total));
        } else {
            println!("{label:<21}: {:+.2}%", total * 100.0);
        }
    };
    show("Strategy return", total_ret);
    show("Buy & hold (eq-wt)", r.buy_hold_return);
    if let Some(ix) = r.index_return {
        show("SPY buy & hold", ix);
    }
    println!(
        "Max drawdown         : {:.2}%  (buy & hold: {:.2}%{})",
        r.max_drawdown * 100.0,
        r.buy_hold_drawdown * 100.0,
        r.index_drawdown.map(|d| format!(", SPY: {:.2}%", d * 100.0)).unwrap_or_default()
    );
    println!("Sharpe (annualised)  : {:.2}", r.sharpe);
    println!(
        "Avg exposure         : {:.0}% long, {:.0}% short",
        r.long_exposure * 100.0,
        r.short_exposure * 100.0
    );
    if r.short_exposure > 0.0 || r.short_pnl != 0.0 {
        println!("Realised P&L by side : long ${:+.0}, short ${:+.0}", r.long_pnl, r.short_pnl);
    }
    println!("Closed trades        : {n}");
    if n > 0 {
        println!("Win rate             : {:.1}%", wins.len() as f64 / n as f64 * 100.0);
        println!("Avg trade P&L        : ${:+.2}", r.trade_pnls.iter().sum::<f64>() / n as f64);
        if gross_loss > 0.0 {
            println!("Profit factor        : {:.2}", gross_win / gross_loss);
        }
    }
    println!("=========================================");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::*;
    use crate::strategy::{self, Mode};
    use std::path::Path;

    const DAY: i64 = 86_400;

    fn cfg() -> Config {
        Config {
            broker: BrokerKind::Sim,
            symbols: vec!["X".into()],
            symbols_file: None,
            ciks: HashMap::new(),
            edgar: EdgarConfig::default(),
            history: String::new(),
            timeframe: Timeframe::M5,
            poll_seconds: 30,
            strategy: StrategyConfig::SmaCross { fast: 2, slow: 4 },
            risk: RiskConfig {
                position_pct: 0.5,
                max_positions: 1,
                stop_loss_pct: 0.0,
                take_profit_pct: 0.0,
                slippage_bps: 0.0,
                short_borrow_pct: 0.0,
                max_leverage: 1.0,
                margin_rate_pct: 0.0,
                flatten_before_close_minutes: 0,
            },
            sim: SimConfig { starting_cash: 1000.0 },
            backtest: BacktestConfig { days: 1 },
            alpaca: AlpacaConfig::default(),
        }
    }

    fn run_sim(c: &Config, data: &HashMap<String, Vec<Bar>>, from: i64) -> Report {
        let strat = strategy::build(c, Mode::Backtest, Path::new("data/cache")).unwrap();
        simulate(c, strat.as_ref(), data, from)
    }

    fn series(closes: &[f64]) -> HashMap<String, Vec<Bar>> {
        let bars = closes
            .iter()
            .enumerate()
            .map(|(i, &c)| Bar { ts: i as i64 * 300, open: c, high: c, low: c, close: c, volume: 1.0 })
            .collect();
        HashMap::from([("X".to_string(), bars)])
    }

    /// Daily bars growing at `rate` per day.
    fn grow(rate: f64, days: i32) -> Vec<Bar> {
        (0..days)
            .map(|i| {
                let p = 100.0 * (1.0f64 + rate).powi(i);
                Bar { ts: 1_704_119_400 + i as i64 * DAY, open: p, high: p, low: p, close: p, volume: 1.0 }
            })
            .collect()
    }

    #[test]
    fn buys_cross_and_sells_reversal() {
        // Cross up at 10 (buy 50 shares), ride to 12, exit @ 8 when fast < slow.
        let data = series(&[10.0, 9.0, 8.0, 7.0, 6.0, 10.0, 11.0, 12.0, 8.0, 4.0]);
        let r = run_sim(&cfg(), &data, 0);
        assert_eq!(r.trade_pnls, vec![(8.0 - 10.0) * 50.0]);
        assert!((r.end_equity - 900.0).abs() < 1e-9);
    }

    #[test]
    fn stop_loss_caps_the_loss() {
        let mut c = cfg();
        c.risk.stop_loss_pct = 0.05;
        let data = series(&[10.0, 9.0, 8.0, 7.0, 6.0, 10.0, 10.0, 5.0, 5.0]);
        let r = run_sim(&c, &data, 0);
        // Bar gapped from 10 straight to 5, so the stop fills at the open (5).
        assert_eq!(r.trade_pnls, vec![(5.0 - 10.0) * 50.0]);
    }

    #[test]
    fn warmup_bars_are_not_traded() {
        // Same data, but trading only starts after the cross has happened.
        let data = series(&[10.0, 9.0, 8.0, 7.0, 6.0, 10.0, 11.0, 12.0, 8.0, 4.0]);
        let r = run_sim(&cfg(), &data, 6 * 300);
        assert!(r.trade_pnls.is_empty());
        assert_eq!(r.bars, 4);
        assert_eq!(r.end_equity, 1000.0);
    }

    #[test]
    fn portfolio_strategy_rotates_into_the_leader() {
        let mut c = cfg();
        c.timeframe = Timeframe::D1;
        c.symbols = vec!["FAST".into(), "SLOW".into()];
        c.strategy = StrategyConfig::MomentumRotation {
            momentum_days: 20,
            trend_sma: 10,
            index_sma: 10,
            top_n: 1,
            index: "SPY".into(),
        };
        let data = HashMap::from([("FAST".to_string(), grow(0.01, 60)), ("SLOW".to_string(), grow(0.002, 60))]);
        let r = run_sim(&c, &data, 0);
        // Bought the faster stock on a weekly rebalance and still holds it at a profit.
        assert!(r.trade_pnls.is_empty());
        assert!(r.end_equity > 1000.0, "equity {}", r.end_equity);
        assert!(r.long_exposure > 0.0 && r.short_exposure == 0.0);
    }

    #[test]
    fn long_short_momentum_profits_on_both_sides() {
        let mut c = cfg();
        c.timeframe = Timeframe::D1;
        c.risk.max_positions = 10;
        c.sim.starting_cash = 100_000.0;
        c.strategy = StrategyConfig::LsMomentum {
            lookback_days: 40,
            skip_days: 5,
            long_frac: 0.25,
            short_frac: 0.25,
            long_gross: 0.5,
            short_gross: 0.5,
            rebalance_band: 0.05,
            index: "SPY".into(),
        };
        // One clear winner, one clear loser, two flat names.
        let data = HashMap::from([
            ("UP".to_string(), grow(0.004, 150)),
            ("DOWN".to_string(), grow(-0.004, 150)),
            ("FLAT1".to_string(), grow(0.0001, 150)),
            ("FLAT2".to_string(), grow(-0.0001, 150)),
        ]);
        let r = run_sim(&c, &data, 0);
        // Long the winner and short the loser: both sides make money, and a
        // short that falls in value is a gain.
        assert!(r.long_exposure > 0.3 && r.short_exposure > 0.1, "{} / {}", r.long_exposure, r.short_exposure);
        assert!(r.end_equity > 110_000.0, "equity {}", r.end_equity);
        // The same portfolio loses on the short side once borrowing is very expensive.
        c.risk.short_borrow_pct = 2.0;
        let costly = run_sim(&c, &data, 0);
        assert!(costly.end_equity < r.end_equity);
        assert!(costly.short_pnl < 0.0);
    }
}
