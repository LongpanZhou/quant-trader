"use client";

import { memo, useMemo } from "react";
import type { SeriesPoint } from "@/lib/types";
import { pct } from "@/lib/format";

type Episode = {
  peak: string;
  trough: string;
  recovery: string | null;
  depth: number;
  days: number;
};

function daysBetween(start: string, end: string) {
  return Math.max(
    0,
    Math.round(
      (new Date(`${end}T00:00:00Z`).getTime() - new Date(`${start}T00:00:00Z`).getTime()) /
        86_400_000,
    ),
  );
}

function episodes(series: SeriesPoint[]): Episode[] {
  if (!series.length) return [];
  const out: Episode[] = [];
  let peak = series[0].strategy;
  let peakDate = series[0].date;
  let trough = peak;
  let troughDate = peakDate;
  let inDrawdown = false;

  for (const point of series) {
    if (point.strategy >= peak) {
      if (inDrawdown && trough < peak) {
        out.push({
          peak: peakDate,
          trough: troughDate,
          recovery: point.date,
          depth: trough / peak - 1,
          days: daysBetween(peakDate, troughDate),
        });
      }
      peak = point.strategy;
      peakDate = point.date;
      trough = peak;
      troughDate = peakDate;
      inDrawdown = false;
    } else {
      inDrawdown = true;
      if (point.strategy < trough) {
        trough = point.strategy;
        troughDate = point.date;
      }
    }
  }
  if (inDrawdown && trough < peak) {
    out.push({
      peak: peakDate,
      trough: troughDate,
      recovery: null,
      depth: trough / peak - 1,
      days: daysBetween(peakDate, troughDate),
    });
  }
  return out.sort((a, b) => a.depth - b.depth).slice(0, 3);
}

// Memoized: the lab pages re-render on every keystroke and slider tick.
export const DrawdownEpisodes = memo(function DrawdownEpisodes({ series }: { series: SeriesPoint[] }) {
  const items = useMemo(() => episodes(series), [series]);
  return (
    <div className="space-y-2.5">
      {items.map((item) => (
        <div key={`${item.peak}-${item.trough}`} className="rounded-lg border border-white/[0.05] bg-black/20 p-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="tabular text-[12px] font-medium text-rose-200">{pct(item.depth)}</span>
            <span className="text-[10px] text-zinc-600">{item.days} days</span>
          </div>
          <div className="mt-1 text-[10px] text-zinc-500">
            {item.peak} → {item.trough}
            {item.recovery ? <span className="text-zinc-700"> · back {item.recovery}</span> : <span className="text-zinc-700"> · ongoing</span>}
          </div>
        </div>
      ))}
    </div>
  );
});
