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

export const isoRange = (start: string, end: string) =>
  `${new Date(`${start}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  })} – ${new Date(`${end}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  })}`;

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
