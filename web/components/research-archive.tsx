"use client";

import { useEffect, useState } from "react";
import { pct } from "@/lib/format";

type ArchiveStrategy = {
  slug: string;
  name: string;
  family: string;
  tagline: string;
  summary: string;
  metrics: { cagr: number; dd: number; sharpe: number };
  window: string;
  status: string;
  note: string;
};

type Payload = { generated: string; note: string; strategies: ArchiveStrategy[] };

export function ResearchArchive() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/research/archive.json?v=2026-11-27-archive")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<Payload>;
      })
      .then(setData)
      .catch((reason) => setError(String(reason)));
  }, []);

  if (error) {
    return <div className="panel p-6 text-[12px] text-rose-200">Could not load archive: {error}</div>;
  }

  if (!data) {
    return <div className="panel h-[220px] animate-pulse bg-white/[0.02]" />;
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Research archive</div>
          <h2 className="display mt-1 text-2xl font-semibold text-zinc-100">
            {data.strategies.length} development and below-bar studies
          </h2>
          <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-zinc-500">
            {data.note}
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.strategies.map((strategy) => (
          <a
            key={strategy.slug}
            href={`/research/${strategy.slug}`}
            className="group panel flex flex-col overflow-hidden transition hover:border-white/20"
          >
            <div className="h-[3px] w-full bg-gradient-to-r from-zinc-500/50 via-zinc-400/30 to-transparent" />
            <div className="flex flex-1 flex-col p-5">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-[1.05rem] font-semibold leading-tight text-zinc-100">
                  {strategy.name}
                </h3>
                <span className="rounded-full border border-white/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.12em] text-zinc-500">
                  {strategy.family}
                </span>
              </div>
              <p className="mt-2 line-clamp-3 min-h-[42px] text-[12px] leading-relaxed text-zinc-400">
                {strategy.tagline}
              </p>
              <div className="mt-4 grid grid-cols-3 gap-3 border-t border-white/[0.06] pt-3">
                <Metric label="CAGR" value={pct(strategy.metrics.cagr)} />
                <Metric label="Max DD" value={pct(strategy.metrics.dd)} />
                <Metric label="Sharpe" value={strategy.metrics.sharpe.toFixed(2)} />
              </div>
              <div className="mt-4 flex items-center justify-between text-[10px] text-zinc-500">
                <span>
                  {strategy.window} - {strategy.status}
                </span>
                <span className="transition group-hover:text-zinc-200">Open record</span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.14em] text-zinc-600">{label}</div>
      <div className="mt-0.5 text-[13px] font-medium text-zinc-300">{value}</div>
    </div>
  );
}
