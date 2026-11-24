"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "@/lib/types";
import { downsample, pct, yearTicks } from "@/lib/format";
import { ChartTooltip } from "./chart-tooltip";
import { LegendDot } from "./ui";

export function DrawdownChart({
  series,
  strategyMax,
  qqqMax,
}: {
  series: SeriesPoint[];
  strategyMax: number;
  qqqMax: number | null;
}) {
  const data = useMemo(() => downsample(series, 1500), [series]);
  const ticks = useMemo(() => yearTicks(data, 12), [data]);
  const tickFormatter = (value: string) => value.slice(0, 4);

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Risk</div>
          <h3 className="mt-1 text-lg font-semibold text-zinc-100">Drawdown from peak</h3>
        </div>
        <div className="flex items-center gap-3">
          <LegendDot color="#fb7185" label={`Strategy ${pct(-strategyMax)}`} />
          <LegendDot color="#71717a" label={`QQQ ${pct(qqqMax == null ? null : -qqqMax)}`} />
        </div>
      </div>
      <div className="h-[240px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
            <defs>
              <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fb7185" stopOpacity={0.04} />
                <stop offset="100%" stopColor="#fb7185" stopOpacity={0.22} />
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
              domain={["auto", 0]}
              tick={{ fill: "#6f7680", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
              width={42}
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
                  valueFormatter={(value) => pct(value)}
                />
              }
            />
            <ReferenceLine y={0} stroke="#2a3037" />
            <Area
              type="monotone"
              dataKey="drawdown"
              name="Strategy"
              stroke="#fb7185"
              strokeWidth={1.6}
              fill="url(#ddFill)"
              dot={false}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="qqqDrawdown"
              name="QQQ"
              stroke="#52525b"
              strokeWidth={1.1}
              fill="transparent"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


