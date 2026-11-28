export type WindowId = "5y" | "10y" | "20y" | "26y";

export type StrategyStatus = "current" | "variant" | "ablation";

export type PaperId =
  | "gayed-bilello-2016"
  | "faber-2007"
  | "moreira-muir-2017"
  | "zarattini-antonacci-2024";

export type StrategyMeta = {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  status: StrategyStatus;
  asOf: string;
  accent: string;
  tags: string[];
  windows: WindowId[];
  defaultWindow: WindowId;
  syntheticWindows: WindowId[];
  dataNote: string;
  papers: PaperId[];
  replication: boolean;
  researchMap: boolean;
};

export type SeriesPoint = {
  date: string;
  strategy: number;
  qqq: number | null;
  drawdown: number;
  qqqDrawdown: number | null;
};

export type YearRow = {
  year: number;
  strategy: number;
  qqq: number | null;
  diff: number | null;
  days: number;
};

export type Metrics = {
  cagr: number;
  totalReturn: number;
  benchmarkCagr: number | null;
  excess: number | null;
  maxDrawdown: number;
  benchmarkMaxDrawdown: number | null;
  sharpe: number;
  volatility: number;
  sortino: number;
  calmar: number;
  startEquity: number;
  endEquity: number;
  closedTrades: number;
  wins: number;
  losses: number;
  flat: number;
  winRate: number;
  profitFactor: number;
  avgTradePnl: number;
  fills: number;
  turnover: number;
  longExposure: number;
  shortExposure: number;
  years: number;
  buyHoldReturn: number;
  buyHoldDrawdown: number;
};

export type Params = {
  kind: string;
  index?: string;
  riskAsset?: string;
  leverage?: number;
  safeAsset?: string;
  smaDays?: number;
  targetVol?: number;
  volDays?: number;
  rebalanceBand?: number;
  /** Custom-lab additions. The bot strategies leave these undefined. */
  symbols?: string[];
  slippageBps?: number;
};

export type PerformanceData = {
  name: string;
  benchmark: string;
  synthetic: boolean;
  timeframe: string;
  start: string;
  end: string;
  params: Params;
  metrics: Metrics;
  series: SeriesPoint[];
  yearly: YearRow[];
  trades: number[];
};

export const WINDOWS: { id: WindowId; label: string; years: string }[] = [
  { id: "5y", label: "5 years", years: "2021–2026" },
  { id: "10y", label: "10 years", years: "2016–2026" },
  { id: "20y", label: "20 years", years: "2006–2026" },
  { id: "26y", label: "26 years", years: "2000–2026" },
];
