import type { WindowId } from "./types";

export const WINDOW_DAYS: Record<WindowId, number> = {
  "5y": 1824,
  "10y": 3650,
  "20y": 7299,
  "26y": 9500,
};

export const END_DATE = "2026-11-20";

export const BENCHMARKS = [
  { value: "QQQ", label: "QQQ · Nasdaq-100 ETF" },
  { value: "SPY", label: "SPY · S&P 500 ETF" },
  { value: "^NDX", label: "^NDX · Nasdaq-100 price" },
  { value: "^IXIC", label: "^IXIC · Nasdaq Composite" },
];

export type BotSettings = {
  index: string;
  riskAsset: string;
  leverage: number;
  safeAsset: string;
  smaDays: number;
  targetVol: number;
  volDays: number;
  rebalanceBand: number;
};

export type BotSynthetic = {
  symbol: string;
  index: string;
  leverage: number;
  feePct: number;
  spreadPct: number;
};

export type BotStrategy = {
  id: string;
  name: string;
  symbols: string[];
  benchmark: string;
  accent: string;
  windows: WindowId[];
  strategy: BotSettings;
  synthetic?: BotSynthetic;
};

export const BOT_STRATEGIES: Record<string, BotStrategy> = {
  "nasdaq-leveraged-trend": {
    id: "nasdaq-leveraged-trend",
    name: "Nasdaq Leveraged Trend",
    symbols: ["QQQ", "TQQQ", "BIL"],
    benchmark: "QQQ",
    accent: "#9ae6a5",
    windows: ["5y", "10y", "20y", "26y"],
    strategy: {
      index: "QQQ",
      riskAsset: "TQQQ",
      leverage: 3,
      safeAsset: "BIL",
      smaDays: 165,
      targetVol: 0.4,
      volDays: 20,
      rebalanceBand: 0.02,
    },
    synthetic: {
      symbol: "TQQQ",
      index: "QQQ",
      leverage: 3,
      feePct: 0.0095,
      spreadPct: 0,
    },
  },
  "sp500-2x-trend": {
    id: "sp500-2x-trend",
    name: "S&P 500 2x Trend",
    symbols: ["SPY", "SSO", "SHY"],
    benchmark: "SPY",
    accent: "#93c5fd",
    windows: ["5y", "10y", "20y"],
    strategy: {
      index: "SPY",
      riskAsset: "SSO",
      leverage: 2,
      safeAsset: "SHY",
      smaDays: 200,
      targetVol: 0,
      volDays: 20,
      rebalanceBand: 0.05,
    },
  },
  "nasdaq-3x-simple": {
    id: "nasdaq-3x-simple",
    name: "Nasdaq 3x Simple Trend",
    symbols: ["QQQ", "TQQQ", "BIL"],
    benchmark: "QQQ",
    accent: "#fcd34d",
    windows: ["5y", "10y", "20y", "26y"],
    strategy: {
      index: "QQQ",
      riskAsset: "TQQQ",
      leverage: 3,
      safeAsset: "BIL",
      smaDays: 200,
      targetVol: 0,
      volDays: 20,
      rebalanceBand: 0.05,
    },
    synthetic: {
      symbol: "TQQQ",
      index: "QQQ",
      leverage: 3,
      feePct: 0.0095,
      spreadPct: 0,
    },
  },
};

export const BOT_STRATEGY_LIST = Object.values(BOT_STRATEGIES);
