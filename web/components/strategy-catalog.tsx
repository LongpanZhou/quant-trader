"use client";

import { useEffect, useMemo, useState } from "react";
import { pct } from "@/lib/format";
import { Pill } from "./ui";

type CatalogItem = {
  id: string;
  slug: string;
  kind: "preset" | "research" | "blend";
  name: string;
  group: string;
  status: string;
  tagline: string;
  summary: string;
  metrics: { cagr10: number; dd10: number; cagr5: number; dd5: number };
  window?: string;
  cagr?: number;
  dd?: number;
  sharpe?: number;
  href: string;
  runnable: boolean;
  accent: string;
  tags: string[];
  papersCount: number;
  provenanceCount: number;
};

const FILTERS = ["All", "Runnable", "Research", "Leader", "Fragile", "Negative"] as const;
type Filter = (typeof FILTERS)[number];

const TONE: Record<string, "green" | "blue" | "amber" | "red" | "neutral"> = {
  Leader: "green",
  Verified: "green",
  Runnable: "green",
  Alternative: "blue",
  Blend: "blue",
  Fragile: "amber",
  Negative: "red",
};

export function StrategyCatalog() {
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>("All");

  useEffect(() => {
    fetch("/data/catalog/strategies.json?v=2026-11-28-43z", { cache: "no-store" })
      .then((response) => response.json() as Promise<{ strategies: CatalogItem[] }>)
      .then((payload) => setItems(payload.strategies))
      .catch(() => setItems([]));
  }, []);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (filter === "All") return items;
    if (filter === "Runnable") return items.filter((item) => item.runnable);
    if (filter === "Research") return items.filter((item) => item.kind !== "preset");
    return items.filter((item) => item.status === filter);
  }, [items, filter]);

  if (!items) {
    return <div className="h-[280px] animate-pulse rounded-2xl bg-white/[0.02]" />;
  }

  const presets = items.filter((item) => item.runnable).length;
  const research = items.length - presets;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((option) => (
            <button
              key={option}
              onClick={() => setFilter(option)}
              className={`rounded-full border px-3 py-1.5 text-[11px] transition ${
                filter === option
                  ? "border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-100"
                  : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <div className="text-[11px] text-zinc-500">
          {items.length} strategies · {presets} runnable · {research} research
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className="group panel flex flex-col overflow-hidden transition hover:border-white/20"
          >
            <div className="h-[3px] w-full" style={{ background: item.accent }} />
            <div className="flex flex-1 flex-col p-5">
              <div className="flex items-center justify-between gap-2">
                <Pill tone={TONE[item.status] ?? "neutral"}>{item.status}</Pill>
                <span className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                  {item.group}
                </span>
              </div>
              <h3 className="mt-3 text-[1.25rem] font-semibold leading-tight text-zinc-100">
                {item.name}
              </h3>
              <p className="mt-2 min-h-[42px] text-[12px] leading-relaxed text-zinc-400">
                {item.tagline}
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="rounded-md border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-zinc-500">
                  {item.runnable ? "Editable preset" : "Precomputed research"}
                </span>
                {item.provenanceCount > 0 ? (
                  <span className="rounded-md border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-zinc-500">
                    {item.provenanceCount} sources
                  </span>
                ) : null}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-3">
                {item.window === "2016-2026" ? (
                  <>
                    <Metric label="CAGR" value={pct(item.cagr)} tone="text-emerald-200" />
                    <Metric label="Max DD" value={pct(item.dd)} tone="text-rose-200" />
                    <Metric label="Sharpe" value={(item.sharpe ?? 0).toFixed(2)} />
                    <Metric label="Window" value="2016-26" />
                  </>
                ) : (
                  <>
                    <Metric label="10y CAGR" value={pct(item.metrics.cagr10)} tone="text-emerald-200" />
                    <Metric label="10y DD" value={pct(item.metrics.dd10)} tone="text-rose-200" />
                    <Metric label="5y CAGR" value={pct(item.metrics.cagr5)} />
                    <Metric label="5y DD" value={pct(item.metrics.dd5)} tone="text-rose-200/80" />
                  </>
                )}
              </div>
              <div className="mt-4 flex items-center justify-between text-[10px] text-zinc-500">
                <span>{item.runnable ? "Run and edit" : "Open research"}</span>
                <span className="transition group-hover:text-zinc-200">Open →</span>
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
