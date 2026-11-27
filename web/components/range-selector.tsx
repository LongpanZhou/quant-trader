"use client";

import type { SeriesPoint } from "@/lib/types";
import { parseSeriesDate } from "@/lib/format";

export type SeriesRange = "all" | "5y" | "3y" | "1y";

const OPTIONS: { id: SeriesRange; label: string }[] = [
  { id: "all", label: "All" },
  { id: "5y", label: "5Y" },
  { id: "3y", label: "3Y" },
  { id: "1y", label: "1Y" },
];

export function filterSeries(series: SeriesPoint[], range: SeriesRange) {
  if (range === "all" || series.length < 2) return series;
  const years = range === "5y" ? 5 : range === "3y" ? 3 : 1;
  const last = parseSeriesDate(series[series.length - 1].date);
  last.setUTCFullYear(last.getUTCFullYear() - years);
  return series.filter((point) => parseSeriesDate(point.date) >= last);
}

function downloadCsv(
  series: SeriesPoint[],
  name: string,
  benchmark: string,
  intraday: boolean,
  suffix?: string,
) {
  const clean = (value: string) => value.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  const stamp = (value: string) => {
    if (!intraday) return value;
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(parseSeriesDate(value));
    const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
    return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}`;
  };
  const dateHeader = intraday ? "date_et" : "date";
  const header = `${dateHeader},strategy,${clean(benchmark)},strategy_drawdown,${clean(benchmark)}_drawdown`;
  const lines = series.map((point) =>
    [
      stamp(point.date),
      point.strategy.toFixed(4),
      point.qqq == null ? "" : point.qqq.toFixed(4),
      point.drawdown.toFixed(6),
      point.qqqDrawdown == null ? "" : point.qqqDrawdown.toFixed(6),
    ].join(","),
  );
  const blob = new Blob([`${header}\n${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${clean(name)}${suffix ? `-${clean(suffix)}` : ""}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function RangeSelector({
  value,
  onChange,
  series,
  name,
  benchmark,
  intraday = false,
  suffix,
}: {
  value: SeriesRange;
  onChange: (range: SeriesRange) => void;
  series: SeriesPoint[];
  name: string;
  benchmark: string;
  intraday?: boolean;
  suffix?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {intraday ? (
        <span className="rounded-md border border-white/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-zinc-500">
          All bars
        </span>
      ) : (
        <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
          {OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => onChange(option.id)}
              className={`rounded-md px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] transition ${
                value === option.id ? "bg-white/10 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
      <button
        onClick={() => downloadCsv(series, name, benchmark, intraday, suffix)}
        className="rounded-lg border border-white/10 px-2.5 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-500 transition hover:border-white/20 hover:text-zinc-200"
      >
        CSV ↓
      </button>
    </div>
  );
}
