"use client";

import { useEffect, useState } from "react";
import { pct } from "@/lib/format";
import { Pill } from "./ui";

type Strategy = {
  slug: string;
  name: string;
  status: string;
  group: string;
  tagline: string;
  metrics: { cagr10: number; dd10: number; cagr5: number; dd5: number };
};

const TONE: Record<string, "green" | "blue" | "amber" | "red" | "neutral"> = {
  Leader: "green",
  Verified: "green",
  Alternative: "blue",
  Blend: "blue",
  Fragile: "amber",
  Negative: "red",
};

export function ResearchHighlights() {
  const [strategies, setStrategies] = useState<Strategy[] | null>(null);

  useEffect(() => {
    fetch("/data/research/strategies.json?v=2026-11-28-44a", { cache: "no-store" })
      .then((response) => response.json() as Promise<{ strategies: Strategy[] }>)
      .then((payload) => setStrategies(payload.strategies.slice(0, 6)))
      .catch(() => setStrategies([]));
  }, []);

  if (!strategies) {
    return <div className="h-[220px] animate-pulse rounded-2xl bg-white/[0.02]" />;
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Research library</div>
          <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
            All 31 research strategies
          </h2>
          <p className="mt-1 max-w-2xl text-[12px] text-zinc-500">
            Every agent result, not just the three runnable portals. Each card opens its rules,
            metrics, papers and source code.
          </p>
        </div>
        <a
          href="/research"
          className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
        >
          Browse all 31 →
        </a>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {strategies.map((strategy) => (
          <a
            key={strategy.slug}
            href={`/research/${strategy.slug}`}
            className="group panel flex flex-col p-5 transition hover:border-white/20"
          >
            <div className="flex items-center justify-between gap-2">
              <Pill tone={TONE[strategy.status] ?? "neutral"}>{strategy.status}</Pill>
              <span className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                {strategy.group}
              </span>
            </div>
            <h3 className="mt-3 text-[1.2rem] font-semibold leading-tight text-zinc-100">
              {strategy.name}
            </h3>
            <p className="mt-2 min-h-[42px] text-[12px] leading-relaxed text-zinc-400">
              {strategy.tagline}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-3">
              <Metric label="10y CAGR" value={pct(strategy.metrics.cagr10)} tone="text-emerald-200" />
              <Metric label="10y DD" value={pct(strategy.metrics.dd10)} tone="text-rose-200" />
              <Metric label="5y CAGR" value={pct(strategy.metrics.cagr5)} />
              <Metric label="5y DD" value={pct(strategy.metrics.dd5)} tone="text-rose-200/80" />
            </div>
            <div className="mt-4 text-[10px] text-zinc-500 transition group-hover:text-zinc-200">
              Open research view →
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, tone = "text-zinc-200" }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">{label}</div>
      <div className={`tabular mt-1 text-[15px] font-medium ${tone}`}>{value}</div>
    </div>
  );
}
