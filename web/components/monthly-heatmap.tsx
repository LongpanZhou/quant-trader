"use client";

import { useMemo } from "react";
import type { SeriesPoint } from "@/lib/types";
import { maxAbs, monthName, monthlyGrid, pct } from "@/lib/format";

export function MonthlyHeatmap({ series }: { series: SeriesPoint[] }) {
  const { years, returns } = useMemo(() => monthlyGrid(series), [series]);
  const max = useMemo(() => maxAbs(Array.from(returns.values())), [returns]);

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Seasonality</div>
          <h3 className="mt-1 text-lg font-semibold text-zinc-100">Monthly returns</h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
          <span className="rounded px-1.5 py-0.5" style={{ background: "rgba(251,113,133,.35)" }}>
            negative
          </span>
          <span className="rounded px-1.5 py-0.5" style={{ background: "rgba(154,230,165,.35)" }}>
            positive
          </span>
          <span className="text-zinc-600 sm:hidden">swipe →</span>
        </div>
      </div>
      <div className="relative min-w-0">
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-8 bg-gradient-to-l from-[#0d0f12] to-transparent sm:hidden" />
        <div className="w-full min-w-0 overflow-x-auto pb-1">
          <div className="min-w-[640px]">
          <div className="grid grid-cols-[44px_repeat(12,minmax(0,1fr))] gap-1">
            <div />
            {Array.from({ length: 12 }, (_, month) => (
              <div key={month} className="pb-1 text-center text-[9px] uppercase tracking-[0.12em] text-zinc-600">
                {monthName(month)}
              </div>
            ))}
            {years.map((year) => (
              <div key={year} className="contents">
                <div className="flex items-center text-[10px] tabular text-zinc-500">{year}</div>
                {Array.from({ length: 12 }, (_, month) => {
                  const key = `${year}-${String(month + 1).padStart(2, "0")}`;
                  const value = returns.get(key);
                  if (value == null) {
                    return (
                      <div
                        key={key}
                        className="heat-cell border border-white/[0.03] bg-white/[0.015]"
                        aria-hidden="true"
                      />
                    );
                  }
                  const intensity = Math.min(Math.abs(value) / max, 1);
                  const alpha = 0.08 + intensity * 0.62;
                  const background =
                    value >= 0
                      ? `rgba(52, 211, 153, ${alpha})`
                      : `rgba(251, 113, 133, ${alpha})`;
                  return (
                    <div
                      key={key}
                      className="heat-cell flex items-center justify-center text-[9px] font-medium tabular text-white/80"
                      style={{ background }}
                      title={`${monthName(month)} ${year}: ${pct(value)}`}
                      aria-label={`${monthName(month)} ${year}: ${pct(value)}`}
                    >
                      {Math.abs(value) >= 0.1 ? `${value > 0 ? "+" : ""}${(value * 100).toFixed(0)}` : ""}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
      <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
        Strategy monthly return, first to last available close. Partial months at the start and end
        are included.
      </p>
    </div>
  );
}

