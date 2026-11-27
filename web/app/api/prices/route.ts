import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  CUSTOM_INTERVALS,
  CUSTOM_MAX_SYMBOLS,
  CUSTOM_TICKER,
  type CompactPriceSeries,
  type CustomInterval,
  type PricesPayload,
} from "@/lib/custom-engine";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CACHE_VERSION = 5;
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const MIN_BARS = 40;
const YAHOO_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"];
const MAX_DAYS: Record<CustomInterval, number> = {
  "1m": 7,
  "5m": 59,
  "15m": 59,
  "1h": 729,
  "1d": 10950,
};
const INTERVAL_SECONDS: Record<CustomInterval, number> = {
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "1h": 3600,
  "1d": 86400,
};

type CachedPayload = {
  version: number;
  fetchedAt: number;
  days: number;
  interval: CustomInterval;
  requested: string[];
  benchmark: string;
  from: string;
  to: string;
  symbols: Record<string, CompactPriceSeries>;
  source: string;
};

type YahooChart = {
  chart?: {
    result?: Array<{
      meta?: { symbol?: string; currency?: string };
      timestamp?: number[];
      indicators?: {
        quote?: Array<{
          open?: (number | null)[];
          high?: (number | null)[];
          low?: (number | null)[];
          close?: (number | null)[];
          volume?: (number | null)[];
        }>;
        adjclose?: Array<{ adjclose?: (number | null)[] }>;
      };
    }>;
    error?: { code?: string; description?: string } | null;
  };
};

const price = (value: number) => Math.round(value * 10_000) / 10_000;

function parseTicker(raw: string | null): string | null {
  if (!raw) return null;
  const symbol = raw.trim().toUpperCase();
  return CUSTOM_TICKER.test(symbol) ? symbol : null;
}

function cachePath(key: string) {
  const root =
    process.env.QUANT_TRADER_CACHE_DIR || path.join(os.tmpdir(), "quant-trader-web", "prices");
  return path.join(root, `${key}.json`);
}

function readCache(file: string): CachedPayload | null {
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as CachedPayload;
    if (parsed?.version !== CACHE_VERSION) return null;
    if (!parsed.symbols || typeof parsed.fetchedAt !== "number") return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeCache(file: string, payload: CachedPayload) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(payload), "utf8");
}

async function fetchFromYahoo(
  host: string,
  symbol: string,
  days: number,
  interval: CustomInterval,
): Promise<CompactPriceSeries> {
  const end = Math.floor(Date.now() / 1000);
  const start = end - Math.round(days * 86_400);
  const url =
    `https://${host}/v8/finance/chart/${encodeURIComponent(symbol)}` +
    `?period1=${start}&period2=${end}&interval=${interval}` +
    `&events=div%2Csplit&includeAdjustedClose=true&includePrePost=false`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  let response: Response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) quant-trader-local/0.1 (research portal)",
        Accept: "application/json",
        "Accept-Language": "en-US,en;q=0.9",
      },
    });
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new Error(`${symbol}: Yahoo Finance returned HTTP ${response.status}`);
  }

  const body = (await response.json()) as YahooChart;
  const result = body.chart?.result?.[0];
  if (!result) {
    const detail = body.chart?.error?.description;
    throw new Error(`${symbol}: no chart data from Yahoo Finance${detail ? ` (${detail})` : ""}`);
  }

  const timestamps = result.timestamp;
  const quote = result.indicators?.quote?.[0];
  const adjusted = result.indicators?.adjclose?.[0]?.adjclose;
  if (!timestamps?.length || !quote) {
    throw new Error(`${symbol}: Yahoo Finance returned no price bars`);
  }

  const byDate = new Map<string, { o: number; h: number; l: number; c: number; v: number }>();
  for (let index = 0; index < timestamps.length; index += 1) {
    const timestamp = timestamps[index];
    const close = quote.close?.[index];
    const adjustedClose = adjusted?.[index] ?? close;
    if (
      !Number.isFinite(timestamp) ||
      close == null ||
      adjustedClose == null ||
      !Number.isFinite(close) ||
      !Number.isFinite(adjustedClose) ||
      close <= 0 ||
      adjustedClose <= 0
    ) {
      continue;
    }

    // Do not include a bar that is still forming.
    if (
      interval !== "1d" &&
      (timestamp + INTERVAL_SECONDS[interval]) * 1000 > Date.now()
    ) {
      continue;
    }

    // Yahoo publishes an adjusted close but not adjusted open/high/low.
    // Scale the raw OHLC by adjClose/close for each bar; the factor embeds
    // splits and dividends, so the whole bar is on the same total-return basis.
    // Intraday responses may omit adjclose; raw OHLC is then already consistent
    // inside the short window.
    const factor = adjustedClose / close;
    const rawOpen = quote.open?.[index] ?? close;
    const rawHigh = quote.high?.[index] ?? Math.max(rawOpen, close);
    const rawLow = quote.low?.[index] ?? Math.min(rawOpen, close);
    const iso = new Date(timestamp * 1000).toISOString();
    const date = interval === "1d" ? iso.slice(0, 10) : iso.slice(0, 16);
    byDate.set(date, {
      o: price(rawOpen * factor),
      h: price(rawHigh * factor),
      l: price(rawLow * factor),
      c: price(adjustedClose),
      v: Math.max(0, Math.round(quote.volume?.[index] ?? 0)),
    });
  }

  let rows = Array.from(byDate.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  // Yahoo can include today's still-forming bar. A daily bar is only complete
  // after the US close; use a conservative 21:30 UTC cutoff so the custom lab
  // cannot read a partial session. Weekends/holidays naturally have an older
  // last date, so this only drops a bar dated today.
  if (interval === "1d" && rows.length > 0) {
    const today = new Date().toISOString().slice(0, 10);
    const now = new Date();
    const closeCutoff = Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      21,
      30,
    );
    if (rows[rows.length - 1][0] >= today && Date.now() < closeCutoff) rows.pop();
  }

  if (rows.length < MIN_BARS) {
    throw new Error(
      `${symbol}: only ${rows.length} bars in the requested window (minimum ${MIN_BARS})`,
    );
  }

  const series: CompactPriceSeries = { d: [], o: [], h: [], l: [], c: [], v: [] };
  for (const [date, row] of rows) {
    series.d.push(date);
    series.o.push(row.o);
    series.h.push(row.h);
    series.l.push(row.l);
    series.c.push(row.c);
    series.v.push(row.v);
  }
  return series;
}

async function fetchSymbol(
  symbol: string,
  days: number,
  interval: CustomInterval,
): Promise<CompactPriceSeries> {
  let lastError: unknown = null;
  for (const host of YAHOO_HOSTS) {
    try {
      return await fetchFromYahoo(host, symbol, days, interval);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`${symbol}: download failed`);
}

function toPayload(cached: CachedPayload, cache: "hit" | "miss" | "stale"): PricesPayload {
  return {
    symbols: cached.symbols,
    benchmark: cached.benchmark,
    interval: cached.interval,
    requested: cached.requested,
    from: cached.from,
    to: cached.to,
    fetchedAt: new Date(cached.fetchedAt).toISOString(),
    source: cached.source,
    cache,
    stale: cache === "stale",
  };
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const rawSymbols = searchParams.get("symbols") ?? "";
  const tokens = rawSymbols
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  if (tokens.length === 0) {
    return NextResponse.json(
      { error: "symbols is required, e.g. ?symbols=QQQ,TQQQ,BIL" },
      { status: 400 },
    );
  }
  const invalid = tokens.find((item) => !CUSTOM_TICKER.test(item));
  if (invalid) {
    return NextResponse.json(
      { error: `'${invalid}' is not a plain ticker such as QQQ, TQQQ or ^NDX` },
      { status: 400 },
    );
  }
  const symbols = Array.from(new Set(tokens));
  if (symbols.length > CUSTOM_MAX_SYMBOLS) {
    return NextResponse.json(
      { error: `Use at most ${CUSTOM_MAX_SYMBOLS} symbols per request` },
      { status: 400 },
    );
  }

  const benchmark = parseTicker(searchParams.get("benchmark") ?? "QQQ");
  if (!benchmark) {
    return NextResponse.json(
      { error: "benchmark must be a plain ticker such as QQQ, SPY or ^NDX" },
      { status: 400 },
    );
  }

  const intervalParam = searchParams.get("interval") ?? "1d";
  if (!CUSTOM_INTERVALS.includes(intervalParam as CustomInterval)) {
    return NextResponse.json(
      { error: "interval must be one of 1m, 5m, 15m, 1h, 1d" },
      { status: 400 },
    );
  }
  const interval = intervalParam as CustomInterval;
  const requestedDays = Number(searchParams.get("days") ?? 3650);
  const days = Math.min(
    MAX_DAYS[interval],
    Math.max(1, Math.round(Number.isFinite(requestedDays) ? requestedDays : 3650)),
  );
  const refresh = ["1", "true", "yes"].includes(
    (searchParams.get("refresh") ?? "").toLowerCase(),
  );

  const allSymbols = Array.from(new Set([...symbols, benchmark]));
  const key = createHash("sha256")
    .update(
      JSON.stringify({
        version: CACHE_VERSION,
        symbols: [...allSymbols].sort(),
        benchmark,
        interval,
        days,
      }),
    )
    .digest("hex")
    .slice(0, 24);
  const file = cachePath(key);
  const cached = readCache(file);

  if (!refresh && cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
    return NextResponse.json(toPayload(cached, "hit"), {
      headers: { "cache-control": "no-store" },
    });
  }

  try {
    const downloaded = await Promise.all(
      allSymbols.map(async (symbol) => [symbol, await fetchSymbol(symbol, days, interval)] as const),
    );
    const series: Record<string, CompactPriceSeries> = {};
    for (const [symbol, value] of downloaded) series[symbol] = value;

    const from = downloaded
      .map(([, value]) => value.d[0])
      .sort((a, b) => a.localeCompare(b))[0];
    const to = downloaded
      .map(([, value]) => value.d[value.d.length - 1])
      .sort((a, b) => a.localeCompare(b))
      .at(-1)!;
    const payload: CachedPayload = {
      version: CACHE_VERSION,
      fetchedAt: Date.now(),
      days,
      interval,
      requested: symbols,
      benchmark,
      from,
      to,
      symbols: series,
      source: `Yahoo Finance chart API (${interval}${interval === "1d" ? ", adjusted" : ""})`,
    };
    writeCache(file, payload);
    return NextResponse.json(toPayload(payload, "miss"), {
      headers: { "cache-control": "no-store" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Price download failed";
    if (cached) {
      return NextResponse.json(
        {
          ...toPayload(cached, "stale"),
          warning: `Yahoo Finance was unavailable; using the local cache from ${new Date(
            cached.fetchedAt,
          ).toISOString()}. ${message}`,
        },
        { headers: { "cache-control": "no-store" } },
      );
    }
    return NextResponse.json(
      { error: `Could not download prices. ${message}` },
      { status: 502 },
    );
  }
}
