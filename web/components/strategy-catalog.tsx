"use client";

import { useEffect, useMemo, useState } from "react";
import { pct } from "@/lib/format";
import { Pill } from "./ui";

type CatalogItem = {
  id: string;
  slug: string;
  name: string;
  status: string;
  tagline: string;
  summary: string;
  metrics: { cagr10: number; dd10: number; cagr5: number; dd5: number };
  window?: string;
  cagr?: number;
  dd?: number;
  sharpe?: number;
  href: string;
  /** Has a bot.toml: the Rust bot trades it and the lab can rerun it with new settings. */
  adjustable: boolean;
  accent: string;
  tags: string[];
};

const FILTERS = ["All", "Adjustable"] as const;
type Filter = (typeof FILTERS)[number];

const TONE: Record<string, "green" | "blue" | "amber" | "red" | "neutral"> = {
  Adjustable: "green",
};

export function StrategyCatalog() {
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>("All");

  useEffect(() => {
    fetch("/data/catalog/strategies.json?v=2026-11-28-47")
      .then((response) => response.json() as Promise<{ strategies: CatalogItem[] }>)
      .then((payload) => setItems(payload.strategies))
      .catch(() => setItems([]));
  }, []);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (filter === "All") return items;
    return items.filter((item) => item.adjustable);
  }, [items, filter]);

  if (!items) {
    return <div className="h-[280px] animate-pulse rounded-2xl bg-white/[0.02]" />;
  }

  const adjustable = items.filter((item) => item.adjustable).length;

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
          {items.length} strategies · {adjustable} adjustable in the lab
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className="group panel flex flex-col overflow-hidden transition hover:border-white/20"
          >
            <div className="flex flex-1 flex-col p-5">
              <div className="flex items-center justify-between gap-2">
                <Pill tone={TONE[item.status] ?? "neutral"}>{item.status}</Pill>
                <span className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                  {item.window === "2016-2026" ? "2016-2026" : "10y / 5y"}
                </span>
              </div>
              <h3 className="mt-3 text-[1.25rem] font-semibold leading-tight text-zinc-100">
                {item.name}
              </h3>
              <p className="mt-2 min-h-[42px] text-[12px] leading-relaxed text-zinc-400">
                {item.tagline}
              </p>
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
                <span>{item.adjustable ? "Adjust and rerun" : "Results, rules and code"}</span>
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
