use anyhow::{bail, Context, Result};
use serde::Deserialize;

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
    LeveragedIndex {
        /// Index whose trend and volatility drive the decision (e.g. QQQ).
        index: String,
        /// Leveraged fund tracking that index (e.g. TQQQ) and its multiple.
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
}

fn default_leverage() -> f64 {
    1.0
}
fn default_vol_days() -> usize {
    20
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
    /// Fixed end date (YYYY-MM-DD) for a reproducible window. Empty = today.
    /// Use this for published results; "last N days" otherwise moves daily.
    #[serde(default)]
    pub end_date: String,
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
    /// Extra financing spread over the T-bill rate, as a yearly fraction.
    #[serde(default)]
    pub synthetic_spread_pct: f64,
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
pub struct Config {
    pub broker: BrokerKind,
    #[serde(default)]
    pub symbols: Vec<String>,
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
        end_date: String::new(),
        synthetic_symbol: String::new(),
        synthetic_index: String::new(),
        synthetic_leverage: 0.0,
        synthetic_fee_pct: default_synth_fee(),
        synthetic_spread_pct: 0.0,
    }
}

impl StrategyConfig {
    fn validate(&self) -> Result<()> {
        match self {
            StrategyConfig::SmaCross { fast, slow } if *fast == 0 || fast >= slow => {
                bail!("config: sma_cross needs 0 < fast < slow")
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
        let mut seen = std::collections::HashSet::new();
        cfg.symbols.retain(|s| seen.insert(s.clone()));
        cfg.validate()?;
        Ok(cfg)
    }

    /// Check the settings are consistent. Call again after changing any.
    pub fn validate(&self) -> Result<()> {
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
        if !self.backtest.end_date.trim().is_empty() {
            if self.backtest.end_days_ago != 0 {
                bail!("config: use either backtest.end_date or end_days_ago, not both");
            }
            if chrono::NaiveDate::parse_from_str(self.backtest.end_date.trim(), "%Y-%m-%d").is_err() {
                bail!("config: backtest.end_date must be YYYY-MM-DD");
            }
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
                || !(0.0..=0.05).contains(&self.backtest.synthetic_spread_pct)
            {
                bail!(
                    "config: synthetic_symbol needs synthetic_index, synthetic_leverage >= 1, synthetic_fee_pct >= 0 and synthetic_spread_pct in [0, 0.05]"
                );
            }
        }
        self.strategy.validate()?;
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
