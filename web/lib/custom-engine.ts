import type { Metrics, PerformanceData, SeriesPoint, YearRow } from "./types";

/**
 * Client-side engine for the custom strategy workspace.
 *
 * The engine is deliberately small and boring:
 * - decide(ctx) is called once per completed bar (daily or intraday), using data through that bar
 * - the returned weights are filled at the next bar's open
 * - positions are long-only fractions of equity; the remainder is cash
 * - slippage is charged on every traded notional
 *
 * It is shared by the browser Web Worker and by local tests. It has no network
 * access and no knowledge of the page.
 */

export const CUSTOM_TIMEOUT_MS = 30_000;
export const CUSTOM_START_EQUITY = 100_000;
export const CUSTOM_MAX_SYMBOLS = 8;
/** Plain US tickers and Yahoo index symbols such as ^NDX. */
export const CUSTOM_TICKER = /^(?:\^[A-Z0-9.^-]{1,12}|[A-Z][A-Z0-9.^-]{0,12})$/;
export const CUSTOM_INTERVALS = ["1m", "5m", "15m", "1h", "1d"] as const;
export type CustomInterval = (typeof CUSTOM_INTERVALS)[number];
export const BARS_PER_YEAR: Record<CustomInterval, number> = {
  "1m": 252 * 390,
  "5m": 252 * 78,
  "15m": 252 * 26,
  "1h": 252 * 7,
  "1d": 252,
};
const MAX_BARS = 20_000;
const MAX_CODE_LENGTH = 100_000;

export type CompactPriceSeries = {
  d: string[];
  o: number[];
  h: number[];
  l: number[];
  c: number[];
  v: number[];
};

export type PricesPayload = {
  symbols: Record<string, CompactPriceSeries>;
  benchmark: string;
  interval?: CustomInterval;
  requested?: string[];
  from: string;
  to: string;
  fetchedAt?: string;
  source?: string;
  cache?: "hit" | "miss" | "stale";
  stale?: boolean;
  warning?: string;
};

export type CustomRunInput = {
  prices: PricesPayload;
  symbols: string[];
  benchmark: string;
  slippageBps: number;
  code: string;
  timeframe?: CustomInterval;
};

export type CustomRunOutput = {
  data: PerformanceData;
  bars: number;
  elapsedMs: number;
  warnings: string[];
};

export type CustomWorkerRequest = { type: "run"; input: CustomRunInput };

export type CustomWorkerResponse =
  | { type: "done"; result: CustomRunOutput }
  | { type: "error"; error: string };

type CustomContext = {
  date: string;
  index: number;
  close: (symbol: string) => number;
  open: (symbol: string) => number;
  sma: (symbol: string, n: number) => number | null;
  vol: (symbol: string, n: number) => number | null;
  returns: (symbol: string, n: number) => number[];
};

type AlignedSeries = {
  open: number[];
  close: number[];
};

const normalizeSymbol = (value: string) => value.trim().toUpperCase();

const round = (value: number, digits: number) => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

const mean = (values: number[]) =>
  values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;

const parseDate = (value: string) => {
  if (value.includes("T")) {
    const normalized = value.length === 16 ? `${value}:00Z` : value.endsWith("Z") ? value : `${value}Z`;
    return new Date(normalized);
  }
  return new Date(`${value}T00:00:00Z`);
};

const sampleStdDev = (values: number[]) => {
  if (values.length < 2) return 0;
  const average = mean(values);
  const variance =
    values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1);
  return Math.sqrt(Math.max(0, variance));
};

/** Returns the worst peak-to-trough move as a positive number, e.g. 0.35. */
const maxDrawdown = (equity: number[]) => {
  let peak = Number.NEGATIVE_INFINITY;
  let worst = 0;
  for (const value of equity) {
    if (value > peak) peak = value;
    if (peak > 0) worst = Math.min(worst, value / peak - 1);
  }
  return -worst;
};

function alignSeries(
  prices: PricesPayload,
  requested: string[],
  benchmark: string,
): { calendar: string[]; aligned: Record<string, AlignedSeries>; allSymbols: string[] } {
  const allSymbols = Array.from(new Set([...requested, benchmark]));
  const source = new Map<string, CompactPriceSeries>();
  const maps = new Map<string, Map<string, number>>();

  for (const symbol of allSymbols) {
    const series = prices.symbols?.[symbol];
    if (!series || !Array.isArray(series.d) || series.d.length === 0) {
      throw new Error(`No price history for ${symbol}. Check the ticker and try again.`);
    }
    if (
      series.o.length !== series.d.length ||
      series.h.length !== series.d.length ||
      series.l.length !== series.d.length ||
      series.c.length !== series.d.length ||
      series.v.length !== series.d.length
    ) {
      throw new Error(`Price arrays for ${symbol} are not the same length.`);
    }
    source.set(symbol, series);
    const map = new Map<string, number>();
    series.d.forEach((date, index) => map.set(date, index));
    maps.set(symbol, map);
  }

  // The base calendar is the first requested symbol. A date is kept only when
  // every requested symbol and the benchmark has a bar, so the strategy can
  // never read a hole in the data.
  const base = source.get(requested[0])!;
  const calendar: string[] = [];
  for (const date of base.d) {
    if (allSymbols.every((symbol) => maps.get(symbol)!.has(date))) calendar.push(date);
  }

  if (calendar.length < 40) {
    throw new Error(
      `Only ${calendar.length} common bars across ${allSymbols.join(", ")}. ` +
        "Pick tickers with overlapping history (at least 40 bars).",
    );
  }
  if (calendar.length > MAX_BARS) {
    throw new Error(`The aligned history is too long (${calendar.length} bars, limit ${MAX_BARS}).`);
  }

  const aligned: Record<string, AlignedSeries> = {};
  for (const symbol of allSymbols) {
    const series = source.get(symbol)!;
    const map = maps.get(symbol)!;
    const open: number[] = [];
    const close: number[] = [];
    for (const date of calendar) {
      const index = map.get(date)!;
      open.push(series.o[index]);
      close.push(series.c[index]);
    }
    aligned[symbol] = { open, close };
  }

  return { calendar, aligned, allSymbols };
}

function compileDecide(code: string): (ctx: CustomContext) => unknown {
  const source = [
    '"use strict";',
    code,
    "",
    'if (typeof decide !== "function") {',
    '  throw new Error("Your code must define a function named decide(ctx).");',
    "}",
    "return decide;",
  ].join("\n");

  try {
    return new Function(source)() as (ctx: CustomContext) => unknown;
  } catch (error) {
    throw new Error(
      `Could not compile decide(ctx): ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

export function runCustomBacktest(input: CustomRunInput): CustomRunOutput {
  const started = Date.now();

  const requested = Array.from(
    new Set(
      (Array.isArray(input.symbols) ? input.symbols : [])
        .map((symbol) => normalizeSymbol(String(symbol)))
        .filter(Boolean),
    ),
  );
  if (requested.length === 0) throw new Error("Choose at least one symbol.");
  if (requested.length > CUSTOM_MAX_SYMBOLS) {
    throw new Error(`Use at most ${CUSTOM_MAX_SYMBOLS} symbols.`);
  }

  const benchmark = normalizeSymbol(String(input.benchmark || requested[0]));
  if (!benchmark) throw new Error("Choose a benchmark.");

  const slippageBps = Math.min(100, Math.max(0, Number(input.slippageBps) || 0));
  const code = String(input.code ?? "");
  if (!code.trim()) throw new Error("Write a decide(ctx) function first.");
  if (code.length > MAX_CODE_LENGTH) {
    throw new Error(`The strategy code is too long (limit ${MAX_CODE_LENGTH} characters).`);
  }

  const timeframe = input.timeframe ?? input.prices.interval ?? "1d";
  const barsPerYear = BARS_PER_YEAR[timeframe] ?? 252;
  const { calendar, aligned, allSymbols } = alignSeries(input.prices, requested, benchmark);
  const decide = compileDecide(code);

  const tradable = new Set(requested);
  const bars = calendar.length;
  const close = (symbol: string): number => {
    const key = normalizeSymbol(symbol);
    const series = aligned[key];
    if (!series) {
      throw new Error(`Unknown symbol '${symbol}'. Available: ${allSymbols.join(", ")}.`);
    }
    return series.close[barIndex];
  };
  const open = (symbol: string): number => {
    const key = normalizeSymbol(symbol);
    const series = aligned[key];
    if (!series) {
      throw new Error(`Unknown symbol '${symbol}'. Available: ${allSymbols.join(", ")}.`);
    }
    return series.open[barIndex];
  };

  let barIndex = 0;
  const period = (n: number, minimum: number, label: string) => {
    if (!Number.isFinite(n)) throw new Error(`${label} period must be a number.`);
    const value = Math.floor(n);
    if (value < minimum || value > 5000) {
      throw new Error(`${label} period must be between ${minimum} and 5000.`);
    }
    return value;
  };

  const ctx: CustomContext = {
    date: calendar[0],
    index: 0,
    close,
    open,
    sma: (symbol, n) => {
      const length = period(n, 1, "sma");
      const series = aligned[normalizeSymbol(symbol)];
      if (!series) {
        throw new Error(`Unknown symbol '${symbol}'. Available: ${allSymbols.join(", ")}.`);
      }
      if (barIndex + 1 < length) return null;
      let sum = 0;
      for (let index = barIndex - length + 1; index <= barIndex; index += 1) {
        sum += series.close[index];
      }
      return sum / length;
    },
    vol: (symbol, n) => {
      const length = period(n, 2, "vol");
      const series = aligned[normalizeSymbol(symbol)];
      if (!series) {
        throw new Error(`Unknown symbol '${symbol}'. Available: ${allSymbols.join(", ")}.`);
      }
      if (barIndex < length) return null;
      const returns: number[] = [];
      for (let index = barIndex - length + 1; index <= barIndex; index += 1) {
        returns.push(series.close[index] / series.close[index - 1] - 1);
      }
      return sampleStdDev(returns) * Math.sqrt(barsPerYear);
    },
    returns: (symbol, n) => {
      const length = period(n, 1, "returns");
      const series = aligned[normalizeSymbol(symbol)];
      if (!series) {
        throw new Error(`Unknown symbol '${symbol}'. Available: ${allSymbols.join(", ")}.`);
      }
      const count = Math.min(length, barIndex);
      const values: number[] = [];
      for (let index = barIndex - count + 1; index <= barIndex; index += 1) {
        values.push(series.close[index] / series.close[index - 1] - 1);
      }
      return values;
    },
  };

  const normalizeWeights = (raw: unknown, date: string, index: number): Record<string, number> => {
    if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error(
        `decide(ctx) must return an object of weights on ${date} (bar ${index}), e.g. { QQQ: 0.5, BIL: 0.5 }.`,
      );
    }
    const weights: Record<string, number> = {};
    let sum = 0;
    for (const [rawSymbol, rawWeight] of Object.entries(raw as Record<string, unknown>)) {
      const symbol = normalizeSymbol(rawSymbol);
      if (!tradable.has(symbol)) {
        throw new Error(
          `decide(ctx) returned '${symbol}' on ${date}. Weights can only use: ${requested.join(", ")}.`,
        );
      }
      const weight = Number(rawWeight);
      if (!Number.isFinite(weight)) {
        throw new Error(`Weight for ${symbol} on ${date} is not a finite number.`);
      }
      if (weight < -1e-9) {
        throw new Error(`Weight for ${symbol} on ${date} is negative (${weight}). Shorting is not supported.`);
      }
      if (weight > 1 + 1e-9) {
        throw new Error(`Weight for ${symbol} on ${date} is above 1 (${weight}).`);
      }
      if (weight > 1e-12) {
        weights[symbol] = weight;
        sum += weight;
      }
    }
    if (sum > 1.001) {
      throw new Error(
        `Weights on ${date} sum to ${sum.toFixed(3)}; they must sum to 1 or less (the remainder is cash).`,
      );
    }
    if (sum > 1) {
      const scale = 1 / sum;
      for (const symbol of Object.keys(weights)) weights[symbol] *= scale;
    }
    return weights;
  };

  const shares: Record<string, number> = {};
  const averageCost: Record<string, number> = {};
  const partialPnl: Record<string, number> = {};
  for (const symbol of requested) {
    shares[symbol] = 0;
    averageCost[symbol] = 0;
    partialPnl[symbol] = 0;
  }

  let cash = CUSTOM_START_EQUITY;
  let totalTraded = 0;
  let fills = 0;
  let wins = 0;
  let losses = 0;
  let flat = 0;
  let grossProfit = 0;
  let grossLoss = 0;
  let realizedPnl = 0;
  let exposureSum = 0;
  const tradePnls: number[] = [];
  const equityCurve: number[] = [];

  const recordTrade = (pnl: number) => {
    tradePnls.push(round(pnl, 2));
    if (pnl > 0.01) {
      wins += 1;
      grossProfit += pnl;
    } else if (pnl < -0.01) {
      losses += 1;
      grossLoss += -pnl;
    } else {
      flat += 1;
    }
    realizedPnl += pnl;
  };

  const execute = (targets: Record<string, number>, index: number) => {
    const barOpen = (symbol: string) => aligned[symbol].open[index];
    let equityAtOpen = cash;
    for (const symbol of requested) {
      equityAtOpen += shares[symbol] * barOpen(symbol);
    }
    if (!(equityAtOpen > 0)) throw new Error(`Equity is not positive at ${calendar[index]}.`);

    // Sell first so the proceeds are available for buys. Weights sum to <= 1,
    // but slippage can still make a buy unaffordable, so buys are clipped to
    // available cash below.
    for (const symbol of requested) {
      const price = barOpen(symbol);
      const currentValue = shares[symbol] * price;
      const targetValue = (targets[symbol] ?? 0) * equityAtOpen;
      const delta = currentValue - targetValue;
      if (delta <= 1e-9 || shares[symbol] <= 1e-12) continue;
      const quantity = Math.min(shares[symbol], delta / price);
      const notional = quantity * price;
      const cost = (notional * slippageBps) / 10_000;
      cash += notional - cost;
      shares[symbol] -= quantity;
      totalTraded += notional;
      fills += 1;
      partialPnl[symbol] += quantity * (price - averageCost[symbol]) - cost;
      if (shares[symbol] < 1e-9) {
        shares[symbol] = 0;
        averageCost[symbol] = 0;
        recordTrade(partialPnl[symbol]);
        partialPnl[symbol] = 0;
      }
    }

    for (const symbol of requested) {
      const price = barOpen(symbol);
      const currentValue = shares[symbol] * price;
      const targetValue = (targets[symbol] ?? 0) * equityAtOpen;
      const delta = targetValue - currentValue;
      if (delta <= 1e-9 || price <= 0) continue;
      const costRate = slippageBps / 10_000;
      const affordable = Math.max(0, cash / (price * (1 + costRate)));
      const quantity = Math.min(delta / price, affordable);
      if (quantity <= 1e-12) continue;
      const notional = quantity * price;
      const cost = notional * costRate;
      if (notional + cost > cash + 1e-6) continue;
      cash -= notional + cost;
      const oldShares = shares[symbol];
      const newShares = oldShares + quantity;
      averageCost[symbol] =
        (averageCost[symbol] * oldShares + notional + cost) / newShares;
      shares[symbol] = newShares;
      totalTraded += notional;
      fills += 1;
    }
  };

  let pending: Record<string, number> | null = null;

  for (let index = 0; index < bars; index += 1) {
    if (index > 0 && pending) {
      try {
        execute(pending, index);
      } catch (error) {
        throw new Error(
          `Could not execute the decision from ${calendar[index - 1]} at the ${calendar[index]} open: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
      pending = null;
    }

    let equity = cash;
    for (const symbol of requested) equity += shares[symbol] * aligned[symbol].close[index];
    if (!Number.isFinite(equity) || equity <= 0) {
      throw new Error(`Equity became invalid on ${calendar[index]}.`);
    }
    equityCurve.push(equity);
    exposureSum += (equity - cash) / equity;

    if (index < bars - 1) {
      barIndex = index;
      ctx.date = calendar[index];
      ctx.index = index;
      let decision: unknown;
      try {
        decision = decide(ctx);
      } catch (error) {
        throw new Error(
          `decide(ctx) threw on ${calendar[index]} (bar ${index}): ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
      try {
        pending = normalizeWeights(decision, calendar[index], index);
      } catch (error) {
        throw new Error(error instanceof Error ? error.message : String(error));
      }
    }
  }

  const firstDate = calendar[0];
  const lastDate = calendar[bars - 1];
  const startEquity = CUSTOM_START_EQUITY;
  const endEquity = equityCurve[bars - 1];
  const totalReturn = endEquity / startEquity - 1;
  const years = Math.max(
    1 / 365.25,
    (parseDate(lastDate).getTime() - parseDate(firstDate).getTime()) /
      (365.25 * 24 * 60 * 60 * 1000),
  );
  const cagr = (endEquity / startEquity) ** (1 / years) - 1;

  const dailyReturns: number[] = [];
  for (let index = 1; index < bars; index += 1) {
    dailyReturns.push(equityCurve[index] / equityCurve[index - 1] - 1);
  }
  const dailyMean = mean(dailyReturns);
  const dailyStd = sampleStdDev(dailyReturns);
  const volatility = dailyStd * Math.sqrt(barsPerYear);
  const sharpe = dailyStd > 0 ? (dailyMean / dailyStd) * Math.sqrt(barsPerYear) : 0;
  const downside = dailyReturns.map((value) => Math.min(0, value));
  const downsideDev = Math.sqrt(mean(downside.map((value) => value * value)));
  const sortino = downsideDev > 0 ? (dailyMean / downsideDev) * Math.sqrt(barsPerYear) : 0;
  const strategyMaxDrawdown = maxDrawdown(equityCurve);
  const calmar = strategyMaxDrawdown > 0 ? cagr / strategyMaxDrawdown : 0;

  const benchmarkClose = aligned[benchmark].close;
  const benchmarkStart = benchmarkClose[0];
  const benchmarkEnd = benchmarkClose[bars - 1];
  const benchmarkTotalReturn = benchmarkEnd / benchmarkStart - 1;
  const benchmarkCagr = (benchmarkEnd / benchmarkStart) ** (1 / years) - 1;
  const benchmarkMaxDrawdown = maxDrawdown(benchmarkClose);
  const excess = cagr - benchmarkCagr;
  const closedTrades = wins + losses + flat;
  const profitFactor =
    grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 99 : 0;

  const series: SeriesPoint[] = [];
  let peak = Number.NEGATIVE_INFINITY;
  let benchmarkPeak = Number.NEGATIVE_INFINITY;
  for (let index = 0; index < bars; index += 1) {
    const strategyValue = (equityCurve[index] / startEquity) * 100;
    const benchmarkValue = (benchmarkClose[index] / benchmarkStart) * 100;
    peak = Math.max(peak, strategyValue);
    benchmarkPeak = Math.max(benchmarkPeak, benchmarkValue);
    series.push({
      date: calendar[index],
      strategy: round(strategyValue, 6),
      qqq: round(benchmarkValue, 6),
      drawdown: round(strategyValue / peak - 1, 6),
      qqqDrawdown: round(benchmarkValue / benchmarkPeak - 1, 6),
    });
  }

  const yearlyMap = new Map<
    number,
    { firstStrategy: number; lastStrategy: number; firstBenchmark: number; lastBenchmark: number; days: number }
  >();
  for (let index = 0; index < bars; index += 1) {
    const year = Number(calendar[index].slice(0, 4));
    const strategyValue = (equityCurve[index] / startEquity) * 100;
    const benchmarkValue = (benchmarkClose[index] / benchmarkStart) * 100;
    const row = yearlyMap.get(year);
    if (!row) {
      yearlyMap.set(year, {
        firstStrategy: strategyValue,
        lastStrategy: strategyValue,
        firstBenchmark: benchmarkValue,
        lastBenchmark: benchmarkValue,
        days: 1,
      });
    } else {
      row.lastStrategy = strategyValue;
      row.lastBenchmark = benchmarkValue;
      row.days += 1;
    }
  }
  const yearly: YearRow[] = Array.from(yearlyMap.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([year, row]) => {
      const strategy = row.lastStrategy / row.firstStrategy - 1;
      const qqq = row.lastBenchmark / row.firstBenchmark - 1;
      return {
        year,
        strategy: round(strategy, 6),
        qqq: round(qqq, 6),
        diff: round(strategy - qqq, 6),
        days: row.days,
      };
    });

  const metrics: Metrics = {
    cagr: round(cagr, 8),
    totalReturn: round(totalReturn, 8),
    benchmarkCagr: round(benchmarkCagr, 8),
    excess: round(excess, 8),
    maxDrawdown: round(strategyMaxDrawdown, 8),
    benchmarkMaxDrawdown: round(benchmarkMaxDrawdown, 8),
    sharpe: round(sharpe, 4),
    volatility: round(volatility, 8),
    sortino: round(sortino, 4),
    calmar: round(calmar, 4),
    startEquity,
    endEquity: round(endEquity, 2),
    closedTrades,
    wins,
    losses,
    flat,
    winRate: closedTrades > 0 ? round(wins / closedTrades, 8) : 0,
    profitFactor: round(profitFactor, 4),
    avgTradePnl: closedTrades > 0 ? round(realizedPnl / closedTrades, 2) : 0,
    fills,
    turnover: round(totalTraded / startEquity, 4),
    longExposure: round(exposureSum / bars, 8),
    shortExposure: 0,
    years: round(years, 6),
    buyHoldReturn: round(benchmarkTotalReturn, 8),
    buyHoldDrawdown: round(benchmarkMaxDrawdown, 8),
  };

  const warnings: string[] = [];
  const starts = allSymbols
    .map((symbol) => input.prices.symbols[symbol]?.d?.[0])
    .filter((value): value is string => Boolean(value))
    .sort();
  const ends = allSymbols
    .map((symbol) => {
      const dates = input.prices.symbols[symbol]?.d;
      return dates?.[dates.length - 1];
    })
    .filter((value): value is string => Boolean(value))
    .sort();
  if (starts.length > 1 && starts[0] !== starts[starts.length - 1]) {
    warnings.push(
      `The symbols and benchmark do not share a full history; the run starts on ${firstDate}, the first common bar.`,
    );
  }
  if (ends.length > 1 && ends[0] !== ends[ends.length - 1]) {
    warnings.push(
      `The symbols and benchmark do not share a common end date; the run ends on ${lastDate}, the last common bar.`,
    );
  }

  const data: PerformanceData = {
    name: `Custom strategy · ${requested.join(" / ")}`,
    benchmark,
    synthetic: false,
    timeframe,
    start: firstDate,
    end: lastDate,
    params: {
      kind: "custom",
      index: benchmark,
      symbols: requested,
      slippageBps,
    },
    metrics,
    series,
    yearly,
    trades: tradePnls,
  };

  return {
    data,
    bars,
    elapsedMs: Date.now() - started,
    warnings,
  };
}
