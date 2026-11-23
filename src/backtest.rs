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
use chrono::Datelike;
use std::collections::{BTreeSet, HashMap};

pub struct Report {
    pub bars: usize,
    pub span_days: f64,
    pub start_equity: f64,
    pub end_equity: f64,
    pub buy_hold_return: f64,
    pub buy_hold_drawdown: f64,
    /// Buy & hold of the configured benchmark over the same window.
    pub benchmark_return: Option<f64>,
    pub benchmark_drawdown: Option<f64>,
    pub max_drawdown: f64,
    pub sharpe: f64,
    /// Average long and short exposure as fractions of equity.
    pub long_exposure: f64,
    pub short_exposure: f64,
    pub trade_pnls: Vec<f64>,
    /// Profit split by side.
    pub long_pnl: f64,
    pub short_pnl: f64,
    /// Calendar-year results: (year, strategy return, benchmark return, days covered).
    pub yearly: Vec<(i32, f64, Option<f64>, usize)>,
    /// Equity after every tested bar: (timestamp, equity). Used to prove that
    /// later bars cannot change earlier results.
    pub curve: Vec<(i64, f64)>,
    /// Portfolio strategies: mean and worst sum of |actual weight - target|
    /// measured right after a rebalance (fraction of equity).
    pub avg_weight_error: f64,
    pub max_weight_error: f64,
    /// Mean signed gross exposure error (actual - target); negative means the
    /// book is systematically under-invested.
    pub avg_gross_error: f64,
    pub max_single_error: f64,
    /// Buys that could not reach their target because cash ran out.
    pub cash_capped_buys: usize,
}

/// Bars before `trade_from` are only used to warm up indicators; trading and
/// all statistics start at `trade_from`.
pub fn simulate(
    cfg: &Config,
    strat: &dyn Strategy,
    data: &HashMap<String, Vec<Bar>>,
    bench: &[Bar],
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
    // Open of each symbol's current bar, used when fills are modelled at the
    // next session's open.
    let mut open_px = vec![f64::NAN; n];
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
    let mut curve_ts: Vec<i64> = Vec::new();
    let mut weight_err_sum = 0.0f64;
    let mut weight_err_max = 0.0f64;
    let mut weight_err_n = 0usize;
    let mut gross_err_sum = 0.0f64;
    let mut max_single_err = 0.0f64;
    let mut cash_capped_buys = 0usize;
    let mut last_want: Option<Vec<f64>> = None;
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
            open_px[i] = bar.open;
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
            let end = next[i].saturating_sub(cfg.backtest.lag_bars);
            if end == 0 {
                continue;
            }
            let start = end.saturating_sub(lookback);
            let held = pos[i];
            let fill = if cfg.backtest.fill_open { bar.open } else { bar.close };
            let mark: &[f64] = if cfg.backtest.fill_open { &open_px } else { &last_px };
            match strat.signal(&bars[start..end], held.is_some()) {
                Signal::Sell => {
                    if let Some(p) = held {
                        trade!(i, -p.qty, fill);
                    }
                }
                Signal::Buy
                    if held.is_none() && pos.iter().filter(|p| p.is_some()).count() < risk.max_positions =>
                {
                    let eq = cash + held_value(&pos, mark);
                    let qty = order_qty(eq, cash + lev * eq, fill * (1.0 + slip), risk.position_pct);
                    if qty >= 1.0 {
                        trade!(i, qty, fill);
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
                .filter(|&i| next[i] > cfg.backtest.lag_bars)
                .map(|i| {
                    let end = next[i] - cfg.backtest.lag_bars;
                    (symbols[i].as_str(), &data[symbols[i]][end.saturating_sub(lookback)..end])
                })
                .collect();
            let held: Vec<&str> = (0..n).filter(|&i| pos[i].is_some()).map(|i| symbols[i].as_str()).collect();
            if let Some(targets) = strat.targets(&universe, &held) {
                let band = strat.rebalance_band();
                let rel = risk.rebalance_band_rel;
                let band_for = |w: f64| if rel > 0.0 { band.min(rel * w.abs()) } else { band };
                // When fills are at the open, size against the same open
                // prices: nothing from this bar's close is used before it is
                // known. Otherwise mark at the current close.
                let mark: &[f64] = if cfg.backtest.fill_open { &open_px } else { &last_px };
                let eq = cash + held_value(&pos, mark);
                let mut want = vec![0.0f64; n];
                for (s, w) in &targets {
                    if let Some(&i) = index_of.get(s.as_str()) {
                        want[i] = *w;
                    }
                }
                last_want = Some(want.clone());
                // 1. Exits (including positions on the wrong side) and sell-side resizes.
                for i in 0..n {
                    let Some(p) = pos[i] else { continue };
                    let close = mark[i];
                    if want[i] == 0.0 || want[i].signum() != p.qty.signum() {
                        trade!(i, -p.qty, close);
                        continue;
                    }
                    let excess = p.qty * close - want[i] * eq;
                    if excess > band_for(want[i]) * eq {
                        let qty = (excess / close).floor();
                        if qty >= 1.0 {
                            trade!(i, -qty, close);
                        }
                    }
                }
                // 2. New positions and buy-side resizes, highest priority first.
                for (s, w) in &targets {
                    let Some(&i) = index_of.get(s.as_str()) else { continue };
                    let close = mark[i];
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
                            if shortfall > band_for(*w) * eq {
                                let budget = if p.qty > 0.0 { shortfall.min(cash + lev * eq) } else { shortfall };
                                if p.qty > 0.0 && budget + 0.005 * eq < shortfall {
                                    cash_capped_buys += 1;
                                }
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

        // Drift between rebalances: how far the book is from the latest target
        // on every tested bar, not only on the bars where it traded.
        if let Some(w) = &last_want {
            let eq_now = cash + held_value(&pos, &last_px);
            if eq_now > 0.0 {
                let mut err = 0.0;
                let mut gross_actual = 0.0;
                for i in 0..n {
                    let actual = pos[i].map(|p| p.qty * last_px[i]).unwrap_or(0.0) / eq_now;
                    let d = actual - w[i];
                    err += d.abs();
                    gross_actual += actual.abs();
                    max_single_err = max_single_err.max(d.abs());
                }
                let gross_target: f64 = w.iter().map(|x| x.abs()).sum();
                gross_err_sum += gross_actual - gross_target;
                weight_err_sum += err;
                weight_err_max = weight_err_max.max(err);
                weight_err_n += 1;
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
        curve_ts.push(ts);

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
    let benchmark_return = match bench.iter().find(|x| x.ts >= trade_from) {
        Some(first) => bench.last().map(|l| l.close / first.close - 1.0),
        None => None,
    };
    let benchmark_drawdown = bench.iter().any(|x| x.ts >= trade_from).then(|| {
        let closes: Vec<f64> = bench.iter().filter(|x| x.ts >= trade_from).map(|x| x.close).collect();
        drawdown(&closes)
    });
    let bars = curve.len().max(1) as f64;

    // Year by year: equity (and the benchmark) at each year's last bar against
    // the previous year's. The first year starts from the starting equity.
    let year_of = |ts: i64| chrono::DateTime::from_timestamp(ts, 0).map(|d| d.year()).unwrap_or(0);
    let bench: Vec<&Bar> = bench.iter().filter(|x| x.ts >= trade_from).collect();
    let mut yearly = Vec::new();
    let (mut prev_eq, mut prev_bench) = (cfg.sim.starting_cash, bench.first().map(|b| b.close));
    let mut days_in_year = 0usize;
    for i in 0..curve.len() {
        if i == 0 || year_of(curve_ts[i]) != year_of(curve_ts[i - 1]) {
            days_in_year = 0;
        }
        if i == 0 || curve_ts[i] / 86_400 != curve_ts[i - 1] / 86_400 {
            days_in_year += 1;
        }
        if i + 1 == curve.len() || year_of(curve_ts[i + 1]) != year_of(curve_ts[i]) {
            let bench_end = bench.iter().rev().find(|b| b.ts <= curve_ts[i]).map(|b| b.close);
            let bench_ret = match (bench_end, prev_bench) {
                (Some(e), Some(p)) if p > 0.0 => Some(e / p - 1.0),
                _ => None,
            };
            yearly.push((year_of(curve_ts[i]), curve[i] / prev_eq - 1.0, bench_ret, days_in_year));
            prev_eq = curve[i];
            prev_bench = bench_end.or(prev_bench);
        }
    }

    Report {
        bars: curve.len(),
        span_days: (last_ts - first_ts.unwrap_or(last_ts)) as f64 / 86_400.0,
        start_equity: cfg.sim.starting_cash,
        end_equity,
        buy_hold_return: bh_curve.last().map(|v| v - 1.0).unwrap_or(0.0),
        buy_hold_drawdown: drawdown(&bh_curve),
        benchmark_return,
        benchmark_drawdown,
        max_drawdown: drawdown(&curve),
        sharpe,
        long_exposure: long_sum / bars,
        short_exposure: short_sum / bars,
        trade_pnls,
        long_pnl,
        short_pnl,
        yearly,
        curve: curve_ts.iter().copied().zip(curve.iter().copied()).collect(),
        avg_weight_error: if weight_err_n > 0 { weight_err_sum / weight_err_n as f64 } else { 0.0 },
        max_weight_error: weight_err_max,
        avg_gross_error: if weight_err_n > 0 { gross_err_sum / weight_err_n as f64 } else { 0.0 },
        max_single_error: max_single_err,
        cash_capped_buys,
    }
}

/// Peak-to-trough dates of the deepest drawdown in an equity curve.
fn drawdown_window(curve: &[(i64, f64)]) -> Option<(i64, i64, f64)> {
    let (mut peak, mut peak_ts) = (f64::MIN, 0i64);
    let (mut worst, mut from_ts, mut to_ts) = (0.0, 0i64, 0i64);
    for &(ts, eq) in curve {
        if eq > peak {
            peak = eq;
            peak_ts = ts;
        }
        let dd = if peak > 0.0 { 1.0 - eq / peak } else { 0.0 };
        if dd > worst {
            worst = dd;
            from_ts = peak_ts;
            to_ts = ts;
        }
    }
    (worst > 0.0).then_some((from_ts, to_ts, worst))
}

fn day(ts: i64) -> String {
    chrono::DateTime::from_timestamp(ts, 0)
        .map(|d| d.format("%Y-%m-%d").to_string())
        .unwrap_or_else(|| ts.to_string())
}

/// Build a synthetic daily-reset leveraged fund from an index series.
/// `r_fund = L * r_index - (L-1) * T-bill/252 - fee/252`, compounded daily.
/// Rates come from ^IRX closes (percent), using the last observation at or
/// before each bar, so nothing later than the bar is used.
fn synthetic_series(index: &[Bar], leverage: f64, fee_pct: f64, rates: &[Bar]) -> Vec<Bar> {
    let mut out = Vec::with_capacity(index.len());
    let mut px = 100.0f64;
    for (i, b) in index.iter().enumerate() {
        if i == 0 {
            out.push(Bar { ts: b.ts, open: px, high: px, low: px, close: px, volume: 1.0 });
            continue;
        }
        let r = b.close / index[i - 1].close - 1.0;
        let rate = rates
            .iter()
            .rev()
            .find(|x| x.ts <= b.ts)
            .map(|x| (x.close / 100.0).max(0.0))
            .unwrap_or(0.02);
        let financing = (leverage - 1.0) * rate / 252.0;
        let fee = fee_pct / 252.0;
        let prev = px;
        px = (px * (1.0 + leverage * r - financing - fee)).max(0.01);
        out.push(Bar { ts: b.ts, open: prev, high: prev.max(px), low: prev.min(px), close: px, volume: 1.0 });
    }
    out
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
    let now = chrono::Utc::now().timestamp() - cfg.backtest.end_days_ago * 86_400;
    let warmup_days = (strat.warmup() as f64 / tf.bars_per_day() as f64 * 1.5).ceil() as i64 + 5;
    let trade_from = now - cfg.backtest.days * 86_400;

    if cfg.symbols.len() > 100 {
        println!("Downloading price history for {} symbols...", cfg.symbols.len());
    }
    let mut data = HashMap::new();
    let mut failed = Vec::new();
    let results = backend.bars_many(
        &cfg.symbols,
        tf,
        cfg.backtest.days + warmup_days + cfg.backtest.end_days_ago,
    );
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

    // A synthetic fund lets the same rule be tested before the real fund
    // existed (TQQQ: 2010). It is built only from the index and from T-bill
    // yields at or before each bar, so it cannot contain later information.
    if !cfg.backtest.synthetic_symbol.is_empty() {
        let sym = cfg.backtest.synthetic_symbol.clone();
        let ix_sym = cfg.backtest.synthetic_index.clone();
        let index = match data.get(&ix_sym) {
            Some(b) => b.clone(),
            None => backend
                .bars(&ix_sym, tf, cfg.backtest.days + warmup_days + cfg.backtest.end_days_ago)
                .unwrap_or_default(),
        };
        if index.len() < 2 {
            bail!("synthetic {sym}: no daily data for index {ix_sym}");
        }
        let rates = backend
            .bars("^IRX", crate::config::Timeframe::D1, cfg.backtest.days + 400 + cfg.backtest.end_days_ago)
            .unwrap_or_default();
        let synth = synthetic_series(&index, cfg.backtest.synthetic_leverage, cfg.backtest.synthetic_fee_pct, &rates);
        println!(
            "Note: {sym} replaced by a synthetic {}x {ix_sym} series (fee {:.2}%/yr, T-bill financing; {} bars)",
            cfg.backtest.synthetic_leverage,
            cfg.backtest.synthetic_fee_pct * 100.0,
            synth.len()
        );
        data.insert(sym, synth);
    }

    // Buy & hold of the benchmark, always from daily closes so the comparison
    // is the same whatever bar size the strategy trades.
    let bench_sym = cfg.backtest.benchmark.clone();
    let bench = match backend.bars(
        &bench_sym,
        crate::config::Timeframe::D1,
        cfg.backtest.days + 10 + cfg.backtest.end_days_ago,
    ) {
        Ok(mut b) => {
            // Only completed daily bars, same rule as the traded symbols, so
            // a still-forming bar cannot leak into the benchmark either.
            b.retain(|x| x.ts + crate::config::Timeframe::D1.secs() <= now);
            b
        }
        Err(e) => {
            println!("Benchmark {bench_sym} unavailable: {e}");
            Vec::new()
        }
    };

    let r = simulate(cfg, strat, &data, &bench, trade_from);
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
    if let Some(ix) = r.benchmark_return {
        show(&format!("{bench_sym} buy & hold"), ix);
        if years >= 1.0 {
            println!(
                "{:<21}: {:+.2}% a year",
                format!("Excess vs {bench_sym}"),
                ann(total_ret) - ann(ix)
            );
        }
    }
    println!(
        "Max drawdown         : {:.2}%  (buy & hold: {:.2}%{})",
        r.max_drawdown * 100.0,
        r.buy_hold_drawdown * 100.0,
        r.benchmark_drawdown
            .map(|d| format!(", {bench_sym}: {:.2}%", d * 100.0))
            .unwrap_or_default()
    );
    if let Some((from, to, _)) = drawdown_window(&r.curve) {
        println!("Drawdown window      : {from_date} to {to_date}", from_date = day(from), to_date = day(to));
    }
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
    if r.max_weight_error > 0.0 {
        println!(
            "Weight tracking      : avg {:.2}% of equity off target, worst {:.2}% | gross {:+.2}% | worst single {:.2}%",
            r.avg_weight_error * 100.0,
            r.max_weight_error * 100.0,
            r.avg_gross_error * 100.0,
            r.max_single_error * 100.0
        );
        if r.cash_capped_buys > 0 {
            println!("Cash-limited buys    : {}", r.cash_capped_buys);
        }
    }
    println!("=========================================");
    if r.yearly.len() > 1 {
        println!("\nYear by year (a year with few days is partial):");
        println!("{:<6} {:>10} {:>10} {:>10} {:>6}", "Year", "Strategy", bench_sym, "Diff", "Days");
        for (y, ret, bench, days) in &r.yearly {
            let bench_txt = bench.map(|v| format!("{:+.1}%", v * 100.0)).unwrap_or_else(|| "-".into());
            let diff = bench.map(|b| format!("{:+.1}", (ret - b) * 100.0)).unwrap_or_else(|| "-".into());
            println!("{y:<6} {:>+9.1}% {bench_txt:>10} {diff:>10} {days:>6}", ret * 100.0);
        }
    }
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
                rebalance_band_rel: 0.0,
            },
            sim: SimConfig { starting_cash: 1000.0 },
            backtest: BacktestConfig {
                days: 1,
                benchmark: "SPY".into(),
                lag_bars: 0,
                fill_open: false,
                end_days_ago: 0,
                synthetic_symbol: String::new(),
                synthetic_index: String::new(),
                synthetic_leverage: 0.0,
                synthetic_fee_pct: 0.0095,
            },
            alpaca: AlpacaConfig::default(),
        }
    }

    fn run_sim(c: &Config, data: &HashMap<String, Vec<Bar>>, from: i64) -> Report {
        run_sim_bench(c, data, &[], from)
    }

    fn run_sim_bench(c: &Config, data: &HashMap<String, Vec<Bar>>, bench: &[Bar], from: i64) -> Report {
        let strat = strategy::build(c, Mode::Backtest, Path::new("data/cache")).unwrap();
        simulate(c, strat.as_ref(), data, bench, from)
    }

    #[test]
    fn benchmark_comes_from_its_own_series() {
        let c = cfg();
        let data = series(&[100.0, 100.0, 100.0, 100.0, 100.0]);
        let bench = vec![
            Bar { ts: 0, open: 100.0, high: 100.0, low: 100.0, close: 100.0, volume: 1.0 },
            Bar { ts: 900, open: 120.0, high: 120.0, low: 120.0, close: 120.0, volume: 1.0 },
        ];
        let r = run_sim_bench(&c, &data, &bench, 0);
        assert!((r.benchmark_return.unwrap() - 0.2).abs() < 1e-9);
        assert!(r.benchmark_drawdown.is_some());
    }

    fn bar(ts: i64, close: f64) -> Bar {
        Bar { ts, open: close, high: close, low: close, close, volume: 1.0 }
    }

    /// The engine must never let a later bar change an earlier result: this
    /// poisons everything after bar 80 (a 1000x jump) and requires the equity
    /// curve up to bar 80 to be bit-identical.
    #[test]
    fn later_bars_cannot_change_earlier_results() {
        let c = cfg();
        let closes: Vec<f64> = (0..120)
            .map(|i| 100.0 + (i as f64 * 0.7).sin() * 10.0 + i as f64 * 0.3)
            .collect();
        let data = series(&closes);
        let clean = run_sim(&c, &data, 0);

        let cut = 80 * 300;
        let mut poisoned = data.clone();
        for b in poisoned.get_mut("X").unwrap() {
            if b.ts > cut {
                b.open *= 1000.0;
                b.high *= 1000.0;
                b.low *= 1000.0;
                b.close *= 1000.0;
            }
        }
        let dirty = run_sim(&c, &poisoned, 0);

        let before = |r: &Report| -> Vec<(i64, f64)> {
            r.curve.iter().filter(|(ts, _)| *ts <= cut).copied().collect()
        };
        let a = before(&clean);
        let b = before(&dirty);
        assert_eq!(a.len(), b.len());
        assert_eq!(a.len(), 81);
        for ((t1, e1), (t2, e2)) in a.iter().zip(&b) {
            assert_eq!(t1, t2);
            assert!((e1 - e2).abs() < 1e-9, "equity at {t1} changed: {e1} vs {e2}");
        }
    }

    /// Same test for the portfolio branch (`leveraged_index`), which is the
    /// code path the Nasdaq strategy actually uses: universe slices, vol
    /// targeting and open fills must all be causal.
    #[test]
    fn portfolio_strategy_later_bars_cannot_change_earlier_results() {
        let mut c = cfg();
        c.symbols = vec!["QQQ".into(), "TQQQ".into(), "BIL".into()];
        c.timeframe = Timeframe::D1;
        c.risk.max_positions = 3;
        c.backtest.lag_bars = 1;
        c.backtest.fill_open = true;
        c.strategy = StrategyConfig::LeveragedIndex {
            index: "QQQ".into(),
            risk_asset: "TQQQ".into(),
            leverage: 3.0,
            safe_asset: "BIL".into(),
            sma_days: 5,
            target_vol: 0.40,
            vol_days: 3,
            rebalance_band: 0.05,
        };

        let make = |seed: f64| -> Vec<Bar> {
            (0..120)
                .map(|i| {
                    let px = seed
                        + 100.0
                        + i as f64 * 0.25
                        + (i as f64 * 0.55).sin() * 4.0;
                    Bar {
                        ts: 1_704_119_400 + i as i64 * DAY,
                        open: px,
                        high: px,
                        low: px,
                        close: px,
                        volume: 1.0,
                    }
                })
                .collect()
        };
        let mut data: HashMap<String, Vec<Bar>> = HashMap::from([
            ("QQQ".to_string(), make(0.0)),
            ("TQQQ".to_string(), make(3.0)),
            ("BIL".to_string(), make(20.0)),
        ]);

        let clean = run_sim(&c, &data, 0);
        let cut = 1_704_119_400 + 80 * DAY;

        for bars in data.values_mut() {
            for b in bars {
                if b.ts > cut {
                    b.open *= 1000.0;
                    b.high *= 1000.0;
                    b.low *= 1000.0;
                    b.close *= 1000.0;
                }
            }
        }
        let dirty = run_sim(&c, &data, 0);

        let before = |r: &Report| -> Vec<(i64, f64)> {
            r.curve.iter().filter(|(ts, _)| *ts <= cut).copied().collect()
        };
        let (a, b) = (before(&clean), before(&dirty));
        assert_eq!(a.len(), 81);
        assert_eq!(a.len(), b.len());
        for ((t1, e1), (t2, e2)) in a.iter().zip(&b) {
            assert_eq!(t1, t2);
            assert!((e1 - e2).abs() < 1e-9, "portfolio equity at {t1} changed: {e1} vs {e2}");
        }
    }

    #[test]
    fn synthetic_fund_compounds_leverage_daily() {        let index = vec![bar(0, 100.0), bar(DAY, 110.0)];
        let rates = vec![bar(0, 0.0)]; // zero T-bill yield, zero fee
        let s = synthetic_series(&index, 3.0, 0.0, &rates);
        assert!((s[0].close - 100.0).abs() < 1e-12);
        assert!((s[1].close - 130.0).abs() < 1e-9);
    }

    #[test]
    fn synthetic_fund_ignores_later_rates() {
        let index = grow(0.001, 60);
        let base = vec![bar(0, 2.0)];
        let mut future_spike = base.clone();
        future_spike.push(bar(1_704_119_400 + 30 * DAY, 20.0));
        let a = synthetic_series(&index, 3.0, 0.0095, &base);
        let b = synthetic_series(&index, 3.0, 0.0095, &future_spike);
        for i in 0..30 {
            assert!((a[i].close - b[i].close).abs() < 1e-12, "bar {i} used a later rate");
        }
        assert!((a[40].close - b[40].close).abs() > 1e-6);
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
            score: String::new(),
            seed: 0,
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
