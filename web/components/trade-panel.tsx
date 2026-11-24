"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { Metrics } from "@/lib/types";
import { compactMoney, multiple, num, pct, signedMoney } from "@/lib/format";

function Row({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-white/[0.05] py-2 last:border-0">
      <span className="text-[11px] text-zinc-500">{label}</span>
      <span className={`tabular text-[12px] font-medium ${tone || "text-zinc-200"}`}>{value}</span>
    </div>
  );
}

export function TradePanel({ metrics }: { metrics: Metrics }) {
  const data = [
    { name: "Wins", value: metrics.wins, color: "#9ae6a5" },
    { name: "Losses", value: metrics.losses, color: "#fb7185" },
    ...(metrics.flat > 0 ? [{ name: "Flat", value: metrics.flat, color: "#52525b" }] : []),
  ];
  const total = metrics.wins + metrics.losses + metrics.flat;

  return (
    <div className="min-w-0">
      <div className="mb-4">
        <div className="eyebrow">Execution</div>
        <h3 className="mt-1 text-lg font-semibold text-zinc-100">Trade quality</h3>
      </div>
      <div className="grid gap-6 sm:grid-cols-[180px_1fr] sm:items-center">
        <div className="relative mx-auto h-[170px] w-[170px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={78}
                paddingAngle={2}
                stroke="none"
                startAngle={90}
                endAngle={-270}
                isAnimationActive={false}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} fillOpacity={0.9} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <div className="stat-value text-[1.65rem] font-semibold text-zinc-100">
              {pct(metrics.winRate)}
            </div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">win rate</div>
          </div>
        </div>
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-[11px] text-zinc-400">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" /> {metrics.wins} wins
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-300" /> {metrics.losses} losses
            </span>
            <span className="text-zinc-600">{num(total)} closed</span>
          </div>
          <Row label="Profit factor" value={metrics.profitFactor.toFixed(2)} tone="text-emerald-200" />
          <Row
            label="Average trade"
            value={signedMoney(metrics.avgTradePnl)}
            tone={metrics.avgTradePnl >= 0 ? "text-emerald-200" : "text-rose-200"}
          />
          <Row label="Fills" value={num(metrics.fills)} />
          <Row label="Turnover" value={multiple(metrics.turnover)} />
          <Row label="Avg exposure" value={pct(metrics.longExposure, 0)} />
          <Row label="Ending equity" value={compactMoney(metrics.endEquity)} />
        </div>
      </div>
    </div>
  );
}


