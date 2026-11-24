"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { YearRow } from "@/lib/types";
import { pct } from "@/lib/format";
import { ChartTooltip } from "./chart-tooltip";
import { LegendDot } from "./ui";

export function YearlyChart({ yearly, benchmark }: { yearly: YearRow[]; benchmark: string }) {
  const data = yearly.map((row) => ({
    ...row,
    label: row.year,
  }));

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Calendar years</div>
          <h3 className="mt-1 text-lg font-semibold text-zinc-100">Yearly returns</h3>
        </div>
        <div className="flex items-center gap-3">
          <LegendDot color="#9ae6a5" label="Strategy" />
          <LegendDot color="#52525b" label={benchmark} />
        </div>
      </div>
      <div className="h-[270px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: -14 }} barGap={2}>
            <CartesianGrid stroke="#22262c" strokeDasharray="4 6" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#6f7680", fontSize: 10 }}
              axisLine={{ stroke: "#2a3037" }}
              tickLine={false}
              interval={data.length > 20 ? 2 : data.length > 12 ? 1 : 0}
              angle={data.length > 12 ? -45 : 0}
              textAnchor={data.length > 12 ? "end" : "middle"}
              height={data.length > 12 ? 48 : 30}
            />
            <YAxis
              tick={{ fill: "#6f7680", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
              width={44}
            />
            <Tooltip
              content={
                <ChartTooltip
                  labelFormatter={(value) => String(value)}
                  valueFormatter={(value) => pct(value)}
                />
              }
            />
            <ReferenceLine y={0} stroke="#3a4048" />
            <Bar
              dataKey="strategy"
              name="Strategy"
              radius={[3, 3, 0, 0]}
              maxBarSize={18}
              isAnimationActive={false}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.year}
                  fill={entry.strategy >= 0 ? "#9ae6a5" : "#fb7185"}
                  fillOpacity={0.9}
                />
              ))}
            </Bar>
            <Bar
              dataKey="qqq"
              name={benchmark}
              fill="#52525b"
              radius={[3, 3, 0, 0]}
              maxBarSize={18}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


