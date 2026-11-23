use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BrokerKind {
    Sim,
    Alpaca,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
pub enum Timeframe {
    #[serde(rename = "1m")]
    M1,
    #[serde(rename = "5m")]
    M5,
    #[serde(rename = "15m")]
    M15,
    #[serde(rename = "1h")]
    H1,
    #[serde(rename = "1d")]
    D1,
}

impl Timeframe {
    pub fn secs(self) -> i64 {
        match self {
            Timeframe::M1 => 60,
            Timeframe::M5 => 300,
            Timeframe::M15 => 900,
            Timeframe::H1 => 3600,
            Timeframe::D1 => 86400,
        }
    }

    pub fn parse(s: &str) -> Option<Timeframe> {
        [Timeframe::M1, Timeframe::M5, Timeframe::M15, Timeframe::H1, Timeframe::D1]
            .into_iter()
            .find(|tf| tf.yahoo() == s)
    }

    pub fn yahoo(self) -> &'static str {
        match self {
            Timeframe::M1 => "1m",
            Timeframe::M5 => "5m",
            Timeframe::M15 => "15m",
            Timeframe::H1 => "1h",
            Timeframe::D1 => "1d",
        }
    }

    pub fn alpaca(self) -> &'static str {
        match self {
            Timeframe::M1 => "1Min",
            Timeframe::M5 => "5Min",
            Timeframe::M15 => "15Min",
            Timeframe::H1 => "1Hour",
            Timeframe::D1 => "1Day",
        }
    }

    /// Bars in one regular trading session.
    pub fn bars_per_day(self) -> usize {
        match self {
            Timeframe::D1 => 1,
            Timeframe::H1 => 7,
            tf => (23400 / tf.secs()) as usize,
        }
    }

    /// How old the latest completed bar may be before the live loop refuses
    /// to trade on it. Daily bars must survive weekends and holidays.
    pub fn stale_after_secs(self) -> i64 {
        match self {
            Timeframe::D1 => 5 * 86400,
            tf => tf.secs() + 300,
        }
    }

    /// Approximate number of bars in a trading year (for annualising Sharpe).
    pub fn bars_per_year(self) -> f64 {
        match self {
            Timeframe::D1 => 252.0,
            Timeframe::H1 => 252.0 * 7.0,
            tf => 252.0 * 23400.0 / tf.secs() as f64,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum StrategyConfig {
    SmaCross {
        fast: usize,
        slow: usize,
    },
    RsiReversion {
        period: usize,
        oversold: f64,
        exit_above: f64,
    },
    Breakout {
        entry_lookback: usize,
        exit_lookback: usize,
    },
    ConnorsRsi2 {
        rsi_period: usize,
        entry_below: f64,
        trend_sma: usize,
        exit_sma: usize,
    },
    Bollinger {
        lookback: usize,
        entry_z: f64,
        exit_z: f64,
    },
    IntradayMomentum {
        lookback_days: usize,
        check_minutes: u32,
    },
    /// Zarattini, Aziz & Barbon (2024) "Beat the Market": long above / short
    /// below the "noise area" around the open, sized to a daily volatility
    /// target with leverage up to `max_weight`.
    NoiseArea {
        lookback_days: usize,
        #[serde(default = "default_vol_days")]
        vol_days: usize,
        check_minutes: u32,
        /// Daily volatility the position is scaled to (0.02 = 2%).
        target_daily_vol: f64,
        max_weight: f64,
        allow_short: bool,
        flatten_minutes: u32,
        rebalance_band: f64,
    },
    MonthlyTrend {
        months: usize,
    },
    MomentumRotation {
        momentum_days: usize,
        trend_sma: usize,
        index_sma: usize,
        top_n: usize,
        index: String,
    },
    TrendVolTarget {
        entry_lookback: usize,
        exit_lookback: usize,
        keltner_mult: f64,
        vol_days: usize,
        position_vol_target: f64,
        max_weight: f64,
        max_gross: f64,
        rebalance_band: f64,
        index: String,
        index_sma: usize,
        park_cash_in_index: bool,
        /// Hold at most this many trending names (strongest first). Needed
        /// for large universes, where hundreds of stocks trend at once.
        #[serde(default)]
        max_names: Option<usize>,
    },
    LsMomentum {
        lookback_days: usize,
        skip_days: usize,
        long_frac: f64,
        short_frac: f64,
        long_gross: f64,
        short_gross: f64,
        rebalance_band: f64,
        index: String,
        /// How stocks are ranked: "return" (default, past return),
        /// "risk_adjusted" (past return per unit of volatility) or
        /// "high52" (closeness to the 52-week high, George & Hwang 2004).
        #[serde(default)]
        score: String,
        /// Only for score = "random": which random draw (a placebo test).
        #[serde(default)]
        seed: u64,
    },
    IntradayLsMomentum {
        lookback_days: usize,
        skip_days: usize,
        long_frac: f64,
        short_frac: f64,
        long_gross: f64,
        short_gross: f64,
        rebalance_band: f64,
        index: String,
        /// 0 = rank once a day near the close (the original behaviour).
        /// N = also re-rank every N minutes during the session, counting
        /// today's price move, so the holdings change through the day.
        #[serde(default)]
        rebalance_minutes: u32,
    },
    EarningsDrift {
        long_sue: f64,
        short_sue: f64,
        hold_days: i64,
        position_weight: f64,
        max_long: f64,
        max_short: f64,
        rebalance_band: f64,
    },
    VwapTrend {
        position_weight: f64,
        allow_short: bool,
        flatten_minutes: u32,
        rebalance_band: f64,
    },
    LeveragedIndex {
        /// Index whose trend and volatility drive the decision (e.g. SPY).
        index: String,
        /// Leveraged fund tracking that index (e.g. UPRO) and its multiple.
        risk_asset: String,
        leverage: f64,
        /// Where the money sits in a downtrend ("" = cash).
        #[serde(default)]
        safe_asset: String,
        sma_days: usize,
        /// Annualised volatility to aim for; 0 = always full leverage in an uptrend.
        #[serde(default)]
        target_vol: f64,
        #[serde(default = "default_vol_days")]
        vol_days: usize,
        rebalance_band: f64,
    },
    OpeningRange {
        range_minutes: u32,
        atr_days: usize,
        stop_atr: f64,
        target_r: f64,
        risk_pct: f64,
        max_weight: f64,
        allow_short: bool,
        flatten_minutes: u32,
        rebalance_band: f64,
        /// "Stocks in play": trade only the N symbols with the highest
        /// opening volume relative to their own normal (0 = trade all).
        #[serde(default)]
        top_n: usize,
        /// Skip symbols whose opening volume is below this multiple of normal.
        #[serde(default)]
        min_rel_volume: f64,
        /// Skip symbols cheaper than this, or with a smaller average daily range.
        #[serde(default)]
        min_price: f64,
        #[serde(default)]
        min_atr: f64,
    },
    Tsmom {
        /// Trend horizons in trading days (e.g. 21, 63, 252).
        lookback_days: Vec<usize>,
        vol_days: usize,
        /// Annualised volatility each asset is scaled to before dividing by
        /// the number of assets.
        target_vol: f64,
        max_weight: f64,
        max_long: f64,
        max_short: f64,
        allow_short: bool,
        rebalance_band: f64,
    },
    ValueMomentum {
        momentum_days: usize,
        momentum_skip: usize,
        value_days: usize,
        value_skip: usize,
        long_frac: f64,
        short_frac: f64,
        long_gross: f64,
        short_gross: f64,
        rebalance_band: f64,
        index: String,
    },
    Profitability {
        long_frac: f64,
        short_frac: f64,
        long_gross: f64,
        short_gross: f64,
        rebalance_band: f64,
        index: String,
    },
    Combo {
        parts: Vec<ComboPart>,
        rebalance_band: f64,
        max_long: f64,
        max_short: f64,
    },
}

/// One sleeve of a combined strategy.
#[derive(Debug, Clone, Deserialize)]
pub struct ComboPart {
    /// Fraction of the account this sleeve manages.
    pub allocation: f64,
    /// For per-symbol strategies: size of each position within the sleeve.
    #[serde(default = "default_part_pct")]
    pub position_pct: f64,
    /// For per-symbol strategies: most positions the sleeve may hold.
    #[serde(default = "default_part_max")]
    pub max_positions: usize,
    pub strategy: StrategyConfig,
}

fn default_leverage() -> f64 {
    1.0
}
fn default_vol_days() -> usize {
    20
}
fn default_part_pct() -> f64 {
    0.10
}
fn default_part_max() -> usize {
    10
}

#[derive(Debug, Clone, Deserialize)]
pub struct RiskConfig {
    pub position_pct: f64,
    pub max_positions: usize,
    #[serde(default)]
    pub stop_loss_pct: f64,
    #[serde(default)]
    pub take_profit_pct: f64,
    #[serde(default)]
    pub slippage_bps: f64,
    /// Yearly cost of borrowing shares to short, as a fraction (backtest only).
    #[serde(default)]
    pub short_borrow_pct: f64,
    /// Largest total position value as a multiple of equity (1 = no borrowing).
    /// Above 1 the account borrows on margin.
    #[serde(default = "default_leverage")]
    pub max_leverage: f64,
    /// Yearly interest on borrowed money, charged on money still borrowed
    /// overnight (backtest only; positions closed the same day are free).
    #[serde(default)]
    pub margin_rate_pct: f64,
    /// Live safety net for day-trading strategies: close every position and
    /// stop trading this many minutes before the session ends (0 = off).
    /// Uses the exchange's real closing time, so it also works on half-days.
    #[serde(default)]
    pub flatten_before_close_minutes: u32,
    /// Cap the rebalance band at this fraction of a position's target weight
    /// (the "5/25 rule": rebalance when drift exceeds the tighter of the
    /// absolute band or 25% of the target). 0 = absolute band only.
    #[serde(default)]
    pub rebalance_band_rel: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SimConfig {
    pub starting_cash: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BacktestConfig {
    pub days: i64,
    /// Symbol whose buy & hold the results are measured against.
    #[serde(default = "default_benchmark")]
    pub benchmark: String,
    /// Hide the most recent N bars from the strategy before it decides, to
    /// model the live loop's one-session execution delay. 0 = act on the close.
    #[serde(default)]
    pub lag_bars: usize,
    /// Fill orders at the open of the bar after the signal bar, matching the
    /// live loop (decide after a close, trade at the next session's open).
    /// Default false = fill at the close of the bar being processed.
    #[serde(default)]
    pub fill_open: bool,
    /// End the test this many days before today. Non-zero shifts the whole
    /// window back, which shows how much of a result is the chosen end date.
    #[serde(default)]
    pub end_days_ago: i64,
    /// Replace this symbol's prices with a synthetic daily-reset leveraged
    /// fund built from `synthetic_index`, for tests that start before the
    /// real fund existed (e.g. TQQQ before 2010). Empty = use real prices.
    #[serde(default)]
    pub synthetic_symbol: String,
    /// Index the synthetic fund tracks (e.g. QQQ).
    #[serde(default)]
    pub synthetic_index: String,
    /// Daily leverage of the synthetic fund (e.g. 3.0).
    #[serde(default)]
    pub synthetic_leverage: f64,
    /// Yearly fund fee charged by the synthetic series, as a fraction.
    #[serde(default = "default_synth_fee")]
    pub synthetic_fee_pct: f64,
}

fn default_synth_fee() -> f64 {
    0.0095
}

fn default_benchmark() -> String {
    "SPY".into()
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct AlpacaConfig {
    #[serde(default)]
    pub key_id: String,
    #[serde(default)]
    pub secret_key: String,
    #[serde(default = "default_feed")]
    pub feed: String,
}

fn default_feed() -> String {
    "iex".into()
}

#[derive(Debug, Clone, Deserialize)]
pub struct EdgarConfig {
    /// Sent to SEC EDGAR with every request. The SEC asks automated clients
    /// to identify themselves; you may put your own contact details here.
    #[serde(default = "default_edgar_agent")]
    pub user_agent: String,
}

fn default_edgar_agent() -> String {
    "quant-trader/0.1 (paper trading research tool)".into()
}

impl Default for EdgarConfig {
    fn default() -> Self {
        EdgarConfig { user_agent: default_edgar_agent() }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub broker: BrokerKind,
    #[serde(default)]
    pub symbols: Vec<String>,
    /// Optional file with one symbol per line ("SYMBOL" or "SYMBOL,CIK"),
    /// added to `symbols`.
    #[serde(default)]
    pub symbols_file: Option<String>,
    /// SEC company identifiers read from `symbols_file`.
    #[serde(skip)]
    pub ciks: HashMap<String, u64>,
    #[serde(default)]
    pub edgar: EdgarConfig,
    /// Where backtests read price history from. Empty = the live data
    /// source; "dukascopy" = multi-year 1-minute history (SPY, QQQ and
    /// large US stocks), downloaded once and kept on disk.
    #[serde(default)]
    pub history: String,
    pub timeframe: Timeframe,
    #[serde(default = "default_poll")]
    pub poll_seconds: u64,
    pub strategy: StrategyConfig,
    pub risk: RiskConfig,
    #[serde(default = "default_sim")]
    pub sim: SimConfig,
    #[serde(default = "default_backtest")]
    pub backtest: BacktestConfig,
    #[serde(default)]
    pub alpaca: AlpacaConfig,
}

fn default_poll() -> u64 {
    30
}
fn default_sim() -> SimConfig {
    SimConfig { starting_cash: 100_000.0 }
}
fn default_backtest() -> BacktestConfig {
    BacktestConfig {
        days: 30,
        benchmark: default_benchmark(),
        lag_bars: 0,
        fill_open: false,
        end_days_ago: 0,
        synthetic_symbol: String::new(),
        synthetic_index: String::new(),
        synthetic_leverage: 0.0,
        synthetic_fee_pct: default_synth_fee(),
    }
}

impl StrategyConfig {
    fn validate(&self, tf: Timeframe, max_leverage: f64) -> Result<()> {
        let daily = tf == Timeframe::D1;
        match self {
            StrategyConfig::SmaCross { fast, slow } if *fast == 0 || fast >= slow => {
                bail!("config: sma_cross needs 0 < fast < slow")
            }
            StrategyConfig::RsiReversion { period, oversold, exit_above }
                if *period < 2 || oversold >= exit_above =>
            {
                bail!("config: rsi_reversion needs period >= 2 and oversold < exit_above")
            }
            StrategyConfig::Breakout { entry_lookback, exit_lookback }
                if *entry_lookback == 0 || *exit_lookback == 0 =>
            {
                bail!("config: breakout lookbacks must be at least 1")
            }
            StrategyConfig::ConnorsRsi2 { rsi_period, trend_sma, exit_sma, .. }
                if *rsi_period < 2 || *exit_sma == 0 || exit_sma >= trend_sma =>
            {
                bail!("config: connors_rsi2 needs rsi_period >= 2 and 0 < exit_sma < trend_sma")
            }
            StrategyConfig::Bollinger { lookback, entry_z, exit_z }
                if *lookback < 2 || *entry_z <= 0.0 || exit_z >= entry_z =>
            {
                bail!("config: bollinger needs lookback >= 2 and exit_z < entry_z")
            }
            StrategyConfig::IntradayMomentum { lookback_days, check_minutes } => {
                if daily {
                    bail!("config: intraday_momentum needs an intraday timeframe (5m, 15m or 1h)");
                }
                if *lookback_days == 0 || *check_minutes == 0 {
                    bail!("config: intraday_momentum needs lookback_days >= 1 and check_minutes >= 1");
                }
            }
            StrategyConfig::NoiseArea { lookback_days, vol_days, check_minutes, target_daily_vol, max_weight, rebalance_band, .. } => {
                if daily {
                    bail!("config: noise_area needs an intraday timeframe (5m recommended)");
                }
                if *lookback_days == 0 || *vol_days < 2 || *check_minutes == 0 || *target_daily_vol <= 0.0 || *rebalance_band < 0.0 {
                    bail!("config: noise_area needs lookback_days >= 1, vol_days >= 2, check_minutes >= 1, target_daily_vol > 0");
                }
                if !(*max_weight > 0.0 && *max_weight <= max_leverage) {
                    bail!("config: noise_area max_weight must be in (0, risk.max_leverage]");
                }
            }
            StrategyConfig::MonthlyTrend { months } => {
                if !daily {
                    bail!("config: monthly_trend needs timeframe = \"1d\"");
                }
                if *months < 2 {
                    bail!("config: monthly_trend needs months >= 2");
                }
            }
            StrategyConfig::MomentumRotation { momentum_days, trend_sma, index_sma, top_n, .. } => {
                if !daily {
                    bail!("config: momentum_rotation needs timeframe = \"1d\"");
                }
                if *momentum_days < 10 || *trend_sma == 0 || *index_sma == 0 || *top_n == 0 {
                    bail!("config: momentum_rotation needs momentum_days >= 10 and non-zero trend_sma, index_sma, top_n");
                }
            }
            StrategyConfig::TrendVolTarget {
                entry_lookback,
                exit_lookback,
                vol_days,
                position_vol_target,
                max_weight,
                max_gross,
                rebalance_band,
                index_sma,
                ..
            } => {
                if !daily {
                    bail!("config: trend_vol_target needs timeframe = \"1d\"");
                }
                if *entry_lookback < 2 || *exit_lookback < 2 || *vol_days < 2 || *index_sma == 0 {
                    bail!("config: trend_vol_target lookbacks and vol_days must be at least 2");
                }
                if *position_vol_target <= 0.0 || *max_weight <= 0.0 || *rebalance_band < 0.0 {
                    bail!("config: trend_vol_target needs positive position_vol_target and max_weight");
                }
                if !(*max_gross > 0.0 && *max_gross <= 1.0) {
                    bail!("config: trend_vol_target max_gross must be in (0, 1] (no leverage)");
                }
            }
            StrategyConfig::LsMomentum {
                lookback_days,
                skip_days,
                long_frac,
                short_frac,
                long_gross,
                short_gross,
                rebalance_band,
                score,
                ..
            } => {
                if !matches!(score.as_str(), "" | "return" | "risk_adjusted" | "high52" | "random") {
                    bail!("config: ls_momentum score must be return, risk_adjusted or high52");
                }
                if !daily {
                    bail!("config: ls_momentum needs timeframe = \"1d\"");
                }
                if skip_days >= lookback_days {
                    bail!("config: ls_momentum needs skip_days < lookback_days");
                }
                let frac_ok = |f: f64| (0.0..=0.5).contains(&f);
                if !frac_ok(*long_frac) || !frac_ok(*short_frac) || *long_frac + *short_frac <= 0.0 {
                    bail!("config: ls_momentum long_frac and short_frac must be in [0, 0.5]");
                }
                if !(0.0..=1.0).contains(long_gross) || !(0.0..=1.0).contains(short_gross) || *rebalance_band < 0.0 {
                    bail!("config: ls_momentum long_gross and short_gross must be in [0, 1]");
                }
            }
            StrategyConfig::IntradayLsMomentum {
                lookback_days,
                skip_days,
                long_frac,
                short_frac,
                long_gross,
                short_gross,
                rebalance_band,
                rebalance_minutes,
                ..
            } => {
                // Daily bars are allowed for long backtests: the ranking only
                // uses daily closes, so the decisions are the same.
                // Hourly candles are allowed for the re-ranking version (they
                // give two years of history); the once-a-day version needs a
                // candle that ends shortly before the close.
                let hourly_ok = tf == Timeframe::H1 && *rebalance_minutes >= 60;
                if !matches!(tf, Timeframe::M1 | Timeframe::M5 | Timeframe::M15 | Timeframe::D1) && !hourly_ok {
                    bail!("config: intraday_ls_momentum needs timeframe 1m, 5m, 15m or 1d (1h only with rebalance_minutes >= 60)");
                }
                if *lookback_days < 2 || *skip_days >= *lookback_days {
                    bail!("config: intraday_ls_momentum needs lookback_days >= 2 and skip_days < lookback_days");
                }
                let frac_ok = |f: f64| (0.0..=0.5).contains(&f);
                if !frac_ok(*long_frac) || !frac_ok(*short_frac) || *long_frac + *short_frac <= 0.0 {
                    bail!("config: intraday_ls_momentum long_frac and short_frac must be in [0, 0.5]");
                }
                if !(0.0..=1.0).contains(long_gross) || !(0.0..=1.0).contains(short_gross) || *rebalance_band < 0.0 {
                    bail!("config: intraday_ls_momentum long_gross and short_gross must be in [0, 1]");
                }
            }
            StrategyConfig::EarningsDrift {
                long_sue,
                short_sue,
                hold_days,
                position_weight,
                max_long,
                max_short,
                rebalance_band,
            } => {
                if !daily {
                    bail!("config: earnings_drift needs timeframe = \"1d\"");
                }
                if *long_sue <= 0.0 || *short_sue >= 0.0 || *hold_days < 1 {
                    bail!("config: earnings_drift needs long_sue > 0, short_sue < 0 and hold_days >= 1");
                }
                if !(*position_weight > 0.0 && *position_weight <= 1.0)
                    || !(0.0..=1.0).contains(max_long)
                    || !(0.0..=1.0).contains(max_short)
                    || *rebalance_band < 0.0
                {
                    bail!("config: earnings_drift weights must be in (0, 1]");
                }
            }
            StrategyConfig::VwapTrend { position_weight, rebalance_band, .. } => {
                if daily {
                    bail!("config: vwap_trend needs an intraday timeframe (1m is what it was designed for)");
                }
                if !(*position_weight > 0.0 && *position_weight <= 1.0) || *rebalance_band < 0.0 {
                    bail!("config: vwap_trend position_weight must be in (0, 1]");
                }
            }
            StrategyConfig::OpeningRange {
                range_minutes,
                atr_days,
                stop_atr,
                target_r,
                risk_pct,
                max_weight,
                rebalance_band,
                ..
            } => {
                if daily {
                    bail!("config: opening_range needs an intraday timeframe (1m or 5m)");
                }
                if *range_minutes == 0 || *atr_days == 0 || *stop_atr <= 0.0 || *target_r <= 0.0 {
                    bail!("config: opening_range needs positive range_minutes, atr_days, stop_atr and target_r");
                }
                if *risk_pct <= 0.0 || !(*max_weight > 0.0 && *max_weight <= max_leverage) || *rebalance_band < 0.0 {
                    bail!("config: opening_range needs risk_pct > 0 and max_weight in (0, risk.max_leverage]");
                }
            }
            StrategyConfig::LeveragedIndex {
                index,
                risk_asset,
                leverage,
                sma_days,
                target_vol,
                vol_days,
                rebalance_band,
                ..
            } => {
                if index.is_empty() || risk_asset.is_empty() {
                    bail!("config: leveraged_index needs index and risk_asset");
                }
                if *leverage <= 1.0 || *sma_days < 2 || *vol_days < 2 || *target_vol < 0.0 || *rebalance_band < 0.0 {
                    bail!("config: leveraged_index needs leverage > 1, sma_days >= 2, vol_days >= 2");
                }
            }
            StrategyConfig::Tsmom {
                lookback_days,
                vol_days,
                target_vol,
                max_weight,
                max_long,
                max_short,
                rebalance_band,
                ..
            } => {
                if !daily {
                    bail!("config: tsmom needs timeframe = \"1d\"");
                }
                if lookback_days.is_empty() || lookback_days.iter().any(|d| *d == 0) || *vol_days < 2 {
                    bail!("config: tsmom needs at least one positive lookback and vol_days >= 2");
                }
                if *target_vol <= 0.0
                    || !(*max_weight > 0.0 && *max_weight <= max_leverage)
                    || !(*max_long > 0.0 && *max_long <= max_leverage)
                    || !(0.0..=max_leverage.min(1.0)).contains(max_short)
                    || *rebalance_band < 0.0
                {
                    bail!("config: tsmom needs target_vol > 0, max_weight and max_long in (0, risk.max_leverage], max_short in [0, 1]");
                }
            }
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
                ..
            } => {
                if !daily {
                    bail!("config: value_momentum needs timeframe = \"1d\"");
                }
                if momentum_skip >= momentum_days || value_skip >= value_days {
                    bail!("config: value_momentum skips must be shorter than their lookbacks");
                }
                let frac_ok = |f: f64| (0.0..=0.5).contains(&f);
                if !frac_ok(*long_frac) || !frac_ok(*short_frac) || *long_frac + *short_frac <= 0.0 {
                    bail!("config: value_momentum long_frac and short_frac must be in [0, 0.5]");
                }
                if !(0.0..=1.0).contains(long_gross) || !(0.0..=1.0).contains(short_gross) || *rebalance_band < 0.0 {
                    bail!("config: value_momentum long_gross and short_gross must be in [0, 1]");
                }
            }
            StrategyConfig::Profitability { long_frac, short_frac, long_gross, short_gross, rebalance_band, .. } => {
                if !daily {
                    bail!("config: profitability needs timeframe = \"1d\"");
                }
                let frac_ok = |f: f64| (0.0..=0.5).contains(&f);
                if !frac_ok(*long_frac) || !frac_ok(*short_frac) || *long_frac + *short_frac <= 0.0 {
                    bail!("config: profitability long_frac and short_frac must be in [0, 0.5]");
                }
                if !(0.0..=1.0).contains(long_gross) || !(0.0..=1.0).contains(short_gross) || *rebalance_band < 0.0 {
                    bail!("config: profitability long_gross and short_gross must be in [0, 1]");
                }
            }
            StrategyConfig::Combo { parts, rebalance_band, max_long, max_short } => {
                if parts.is_empty() {
                    bail!("config: combo needs at least one [[strategy.parts]]");
                }
                if !(*max_long > 0.0 && *max_long <= 1.0) || !(0.0..=1.0).contains(max_short) || *rebalance_band < 0.0 {
                    bail!("config: combo max_long must be in (0, 1] and max_short in [0, 1]");
                }
                for part in parts {
                    if !(part.allocation > 0.0 && part.allocation <= 1.0) {
                        bail!("config: combo part allocation must be in (0, 1]");
                    }
                    if !(part.position_pct > 0.0 && part.position_pct <= 1.0) || part.max_positions == 0 {
                        bail!("config: combo part position_pct must be in (0, 1] and max_positions >= 1");
                    }
                    match part.strategy {
                        StrategyConfig::Combo { .. } => bail!("config: a combo cannot contain another combo"),
                        StrategyConfig::MomentumRotation { .. } => {
                            bail!("config: momentum_rotation cannot be used inside a combo")
                        }
                        _ => part.strategy.validate(tf, 1.0)?,
                    }
                }
            }
            _ => {}
        }
        Ok(())
    }
}

impl Config {
    pub fn load(path: &str) -> Result<Config> {
        let text = std::fs::read_to_string(path)
            .with_context(|| format!("cannot read config file '{path}'"))?;
        let mut cfg: Config =
            toml::from_str(&text).with_context(|| format!("invalid config in '{path}'"))?;

        if let Ok(v) = std::env::var("APCA_API_KEY_ID") {
            cfg.alpaca.key_id = v;
        }
        if let Ok(v) = std::env::var("APCA_API_SECRET_KEY") {
            cfg.alpaca.secret_key = v;
        }
        cfg.symbols = cfg.symbols.iter().map(|s| s.trim().to_uppercase()).collect();
        if let Some(file) = cfg.symbols_file.clone() {
            let text = std::fs::read_to_string(&file)
                .with_context(|| format!("cannot read symbols_file '{file}'"))?;
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }
                let mut cols = line.split(',');
                let sym = cols.next().unwrap_or("").trim().to_uppercase();
                if sym.is_empty() || sym == "SYMBOL" {
                    continue;
                }
                if let Some(cik) = cols.next().and_then(|c| c.trim().parse::<u64>().ok()) {
                    cfg.ciks.insert(sym.clone(), cik);
                }
                cfg.symbols.push(sym);
            }
        }
        let mut seen = std::collections::HashSet::new();
        cfg.symbols.retain(|s| seen.insert(s.clone()));
        cfg.validate()?;
        Ok(cfg)
    }

    /// Check the settings are consistent. Call again after changing any.
    pub fn validate(&self) -> Result<()> {
        if !matches!(self.history.as_str(), "" | "dukascopy") {
            bail!("config: history must be \"\" or \"dukascopy\"");
        }
        if self.symbols.is_empty() {
            bail!("config: 'symbols' is empty");
        }
        if !(self.risk.position_pct > 0.0 && self.risk.position_pct <= 1.0) {
            bail!("config: risk.position_pct must be in (0, 1]");
        }
        if self.risk.max_leverage < 1.0 || self.risk.margin_rate_pct < 0.0 {
            bail!("config: risk.max_leverage must be at least 1 and margin_rate_pct not negative");
        }
        if self.risk.max_positions == 0 {
            bail!("config: risk.max_positions must be at least 1");
        }
        if !(0.0..=1.0).contains(&self.risk.rebalance_band_rel) {
            bail!("config: risk.rebalance_band_rel must be in [0, 1]");
        }
        if self.poll_seconds == 0 {
            bail!("config: poll_seconds must be at least 1");
        }
        if self.backtest.benchmark.trim().is_empty() {
            bail!("config: backtest.benchmark must name a symbol");
        }
        if self.backtest.lag_bars > 10 {
            bail!("config: backtest.lag_bars must be 10 or less");
        }
        if !(0..=3650).contains(&self.backtest.end_days_ago) {
            bail!("config: backtest.end_days_ago must be in [0, 3650]");
        }
        if self.backtest.fill_open && self.backtest.lag_bars == 0 {
            bail!(
                "config: backtest.fill_open needs lag_bars >= 1; otherwise it fills at the signal bar's own open"
            );
        }
        if let StrategyConfig::LeveragedIndex { index, risk_asset, safe_asset, .. } = &self.strategy {
            for s in [index, risk_asset, safe_asset] {
                if !s.is_empty() && !self.symbols.iter().any(|x| x == s) {
                    bail!("config: leveraged_index symbol '{s}' must be listed in symbols");
                }
            }
        }
        if !self.backtest.synthetic_symbol.trim().is_empty() {
            if self.backtest.synthetic_index.trim().is_empty()
                || self.backtest.synthetic_leverage < 1.0
                || self.backtest.synthetic_fee_pct < 0.0
            {
                bail!(
                    "config: synthetic_symbol needs synthetic_index, synthetic_leverage >= 1 and synthetic_fee_pct >= 0"
                );
            }
        }
        self.strategy.validate(self.timeframe, self.risk.max_leverage)?;
        if self.broker == BrokerKind::Alpaca
            && (self.alpaca.key_id.is_empty() || self.alpaca.secret_key.is_empty())
        {
            bail!(
                "broker = \"alpaca\" but no API keys found. Set APCA_API_KEY_ID and \
                 APCA_API_SECRET_KEY, or fill in [alpaca] in the config file."
            );
        }
        Ok(())
    }
}
