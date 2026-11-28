"use client";

import { useEffect, useMemo, useState } from "react";
import { pct } from "@/lib/format";

type Strategy = {
  slug: string;
  name: string;
  tagline: string;
  summary: string;
  cagr: number;
  dd: number;
  sharpe: number;
};

type Payload = { generated: string; window: string; strategies: Strategy[] };

export function ResearchLibrary() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/research/rebuild.json?v=2026-11-28-44b", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<Payload>;
      })
      .then(setData)
      .catch((reason) => setError(String(reason)));
  }, []);

  const strategies = useMemo(() => data?.strategies ?? [], [data]);

  if (error) {
    return <div className="panel p-6 text-[12px] text-rose-200">Could not load research data: {error}</div>;
  }

  if (!data) {
    return <div className="panel h-[320px] animate-pulse bg-white/[0.02]" />;
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="text-[11px] text-zinc-500">
          {strategies.length} strategies  -  same 2016-2026 window  -  same rules
        </div>
        <a
          href="/compare"
          className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
        >
          Open all-strategies view
        </a>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {strategies.map((strategy) => (
          <a
            key={strategy.slug}
            href={`/research/${strategy.slug}`}
            className="group panel flex flex-col overflow-hidden transition hover:border-white/20"
          >
            <div className="h-[3px] w-full bg-gradient-to-r from-emerald-300/80 via-sky-300/60 to-transparent" />
            <div className="flex flex-1 flex-col p-5">
              <h2 className="text-[1.2rem] font-semibold leading-tight text-zinc-100">
                {strategy.name}
              </h2>
              <p className="mt-2 line-clamp-3 min-h-[42px] text-[12px] leading-relaxed text-zinc-400">
                {strategy.tagline}
              </p>
              <div className="mt-4 grid grid-cols-3 gap-3 border-t border-white/[0.06] pt-3">
                <Metric label="CAGR" value={pct(strategy.cagr)} tone="text-emerald-200" />
                <Metric label="Max DD" value={pct(strategy.dd)} tone="text-rose-200" />
                <Metric label="Sharpe" value={strategy.sharpe.toFixed(2)} />
              </div>
              <div className="mt-4 flex items-center justify-between text-[10px] text-zinc-500">
                <span>2016-2026  -  1 bp</span>
                <span className="transition group-hover:text-zinc-200">Open research</span>
              </div>
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


