import type { SeriesPoint } from "./types";

export const pct = (value: number | null | undefined, digits = 1) =>
  value == null || Number.isNaN(value) ? "—" : `${(value * 100).toFixed(digits)}%`;

export const signedPct = (value: number | null | undefined, digits = 1) => {
  if (value == null || Number.isNaN(value)) return "—";
  const text = `${(value * 100).toFixed(digits)}%`;
  return value > 0 ? `+${text}` : text;
};

export const points = (value: number | null | undefined, digits = 1) => {
  if (value == null || Number.isNaN(value)) return "—";
  const text = `${(value * 100).toFixed(digits)}pp`;
  return value > 0 ? `+${text}` : text;
};

export const money = (value: number, digits = 0) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);

export const compactMoney = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);

export const num = (value: number, digits = 0) =>
  new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);

export const multiple = (value: number, digits = 1) => `${value.toFixed(digits)}x`;

export const signedMoney = (value: number) => {
  const text = money(Math.abs(value), 0);
  return value > 0 ? `+${text}` : value < 0 ? `-${text}` : text;
};

export const monthName = (month: number) =>
  new Date(Date.UTC(2020, month, 1)).toLocaleDateString("en-US", {
    month: "short",
    timeZone: "UTC",
  });

export function parseSeriesDate(value: string) {
  if (value.includes("T")) {
    const normalized = value.length === 16 ? `${value}:00Z` : value.endsWith("Z") ? value : `${value}Z`;
    return new Date(normalized);
  }
  return new Date(`${value}T00:00:00Z`);
}

export function formatSeriesDate(value: string) {
  const date = parseSeriesDate(value);
  const intraday = value.includes("T");
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(intraday ? { hour: "numeric", minute: "2-digit", timeZoneName: "short" } : {}),
    timeZone: intraday ? "America/New_York" : "UTC",
  });
}

export const isoRange = (start: string, end: string) =>
  `${formatSeriesDate(start)} — ${formatSeriesDate(end)}`;

/** X-axis ticks for daily or intraday series. */
export function xTicks(series: SeriesPoint[], timeframe: string, maxTicks = 10) {
  if (timeframe === "1d") return yearTicks(series, maxTicks);
  if (series.length === 0) return [];
  const limit = timeframe === "1m" ? 5 : 6;
  const first = parseSeriesDate(series[0].date).getTime();
  const last = parseSeriesDate(series[series.length - 1].date).getTime();
  const spanDays = (last - first) / 86_400_000;
  if (spanDays > 3) {
    // Multi-day intraday runs read better at session starts than at arbitrary
    // times produced by even downsampling.
    const seen = new Set<string>();
    const sessions = series.filter((point) => {
      const day = point.date.slice(0, 10);
      if (seen.has(day)) return false;
      seen.add(day);
      return true;
    });
    const step = Math.max(1, Math.ceil(sessions.length / limit));
    return sessions.filter((_, index) => index % step === 0).map((point) => point.date);
  }
  const step = Math.max(1, Math.ceil(series.length / limit));
  return series.filter((_, index) => index % step === 0).map((point) => point.date);
}

export function xTickLabel(value: string, timeframe: string, series?: SeriesPoint[]) {
  if (timeframe === "1d") return value.slice(0, 4);
  // Intraday timestamps are stored in UTC but the market is in New York, so
  // format the ticks in ET instead of showing 14:30 for the opening bell.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(parseSeriesDate(value));
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  if (timeframe === "1h") return `${part("year")}-${part("month")}-${part("day")}`;
  let multiDay = true;
  if (series && series.length > 1) {
    const first = parseSeriesDate(series[0].date).getTime();
    const last = parseSeriesDate(series[series.length - 1].date).getTime();
    multiDay = (last - first) / 86_400_000 > 3;
  }
  return multiDay
    ? `${part("month")}-${part("day")}`
    : `${part("hour")}:${part("minute")}`;
}

export function yearTicks(series: SeriesPoint[], maxTicks = 12) {
  const seen = new Set<string>();
  const ticks: string[] = [];
  for (const point of series) {
    const year = point.date.slice(0, 4);
    if (!seen.has(year)) {
      seen.add(year);
      ticks.push(point.date);
    }
  }
  // A window that starts in November would put 2021 and 2022 on top of each
  // other. The start date is printed below the chart, so drop the stub year.
  if (ticks.length > 1 && Number(ticks[0].slice(5, 7)) > 1) ticks.shift();
  if (ticks.length <= maxTicks) return ticks;
  const step = Math.ceil(ticks.length / maxTicks);
  return ticks.filter((_, index) => index % step === 0);
}

export function downsample<T>(data: T[], maxPoints = 1600): T[] {
  if (data.length <= maxPoints) return data;
  const step = Math.ceil(data.length / maxPoints);
  const out: T[] = [];
  for (let i = 0; i < data.length; i += step) out.push(data[i]);
  if (out[out.length - 1] !== data[data.length - 1]) out.push(data[data.length - 1]);
  return out;
}

export function monthlyReturns(series: SeriesPoint[]) {
  const acc = new Map<string, { first: number; last: number }>();
  for (const point of series) {
    const key = point.date.slice(0, 7);
    const current = acc.get(key);
    if (!current) acc.set(key, { first: point.strategy, last: point.strategy });
    else current.last = point.strategy;
  }
  const result = new Map<string, number>();
  for (const [key, value] of acc) result.set(key, value.last / value.first - 1);
  return result;
}

export function monthlyGrid(series: SeriesPoint[]) {
  const returns = monthlyReturns(series);
  const years = Array.from(new Set(series.map((p) => Number(p.date.slice(0, 4))))).sort(
    (a, b) => a - b,
  );
  return { years, returns };
}

export function maxAbs(values: number[]) {
  return values.reduce((max, value) => Math.max(max, Math.abs(value)), 0) || 1;
}
