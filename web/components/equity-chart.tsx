"use client";

import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "@/lib/types";
import { downsample, yearTicks } from "@/lib/format";
import { ChartTooltip } from "./chart-tooltip";
import { LegendDot } from "./ui";

export function EquityChart({
  series,
  start,
  end,
}: {
  series: SeriesPoint[];
  start: string;
  end: string;
}) {
  const [scale, setScale] = useState<"linear" | "log">("log");
  const data = useMemo(() => downsample(series, 1500), [series]);
  const ticks = useMemo(() => yearTicks(data, 12), [data]);
  const maxValue = useMemo(
    () => Math.max(...data.map((point) => Math.max(point.strategy, point.qqq ?? 0))),
    [data],
  );
  const yTicks = useMemo(() => {
    if (scale !== "log") return undefined;
    const candidates = [50, 75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000, 20000];
    const filtered = candidates.filter((value) => value >= 80 && value <= maxValue * 1.15);
    if (filtered.length <= 7) return filtered;
    const step = Math.ceil(filtered.length / 7);
    return filtered.filter((_, index) => index % step === 0);
  }, [scale, maxValue]);

  const tickFormatter = (value: string) => value.slice(0, 4);

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Equity curve</div>
          <div className="mt-1 flex items-baseline gap-2">
            <h3 className="text-lg font-semibold text-zinc-100">Growth of $100</h3>
            <span className="text-[11px] text-zinc-500">after costs</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-3 sm:flex">
            <LegendDot color="#9ae6a5" label="Strategy" />
            <LegendDot color="#71717a" label="QQQ" />
          </div>
          <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
            {(["linear", "log"] as const).map((option) => (
              <button
                key={option}
                onClick={() => setScale(option)}
                className={`rounded-md px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] transition ${
                  scale === option
                    ? "bg-white/10 text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="h-[360px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
            <defs>
              <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#9ae6a5" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#9ae6a5" stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#22262c" strokeDasharray="4 6" vertical={false} />
            <XAxis
              dataKey="date"
              ticks={ticks}
              interval={0}
              tickFormatter={tickFormatter}
              tick={{ fill: "#6f7680", fontSize: 10 }}
              axisLine={{ stroke: "#2a3037" }}
              tickLine={false}
            />
            <YAxis
              scale={scale}
              domain={["auto", "auto"]}
              ticks={yTicks}
              tick={{ fill: "#6f7680", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value: number) => `${Math.round(value)}`}
              width={46}
            />
            <Tooltip
              content={
                <ChartTooltip
                  labelFormatter={(value) =>
                    new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                      timeZone: "UTC",
                    })
                  }
                  valueFormatter={(value) => `$${value.toFixed(1)}`}
                />
              }
            />
            <ReferenceLine y={100} stroke="#2a3037" strokeDasharray="4 4" />
            <Area
              type="monotone"
              dataKey="strategy"
              name="Strategy"
              stroke="#9ae6a5"
              strokeWidth={2}
              fill="url(#equityFill)"
              dot={false}
              isAnimationActive={false}
              activeDot={{ r: 3, fill: "#9ae6a5", stroke: "#08090b", strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="qqq"
              name="QQQ"
              stroke="#71717a"
              strokeWidth={1.4}
              dot={false}
              connectNulls
              isAnimationActive={false}
              activeDot={{ r: 2.5, fill: "#a1a1aa", stroke: "#08090b", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-between text-[10px] text-zinc-600">
        <span>{start}</span>
        <span>{end}</span>
      </div>
    </div>
  );
}


