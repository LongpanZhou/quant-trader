"use client";

import { memo } from "react";
import { pct } from "@/lib/format";
import { CurveChart } from "./research-detail";
import { Pill } from "./ui";

/** One catalog row (web/public/data/catalog/strategies.json). */
export type LabCatalogItem = {
  id: string;
  slug: string;
  name: string;
  status: string;
  tagline: string;
  summary: string;
  adjustable: boolean;
  window: string;
  cagr?: number;
  dd?: number;
  sharpe?: number;
};

/**
 * The lab view for a strategy without adjustable settings: its saved 2016-2026
 * result, curve and a link to its full page.
 */
export const SavedResultPanel = memo(function SavedResultPanel({ item }: { item: LabCatalogItem }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="panel min-w-0 p-5">
        <div className="eyebrow">Saved result</div>
        <h2 className="mt-1 text-lg font-semibold text-zinc-100">{item.name}</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-zinc-500">
          This strategy has a saved 2016-2026 result. Strategies marked adjustable in the selector
          above can have their settings changed and be rerun by the Rust engine.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <Pill>{item.window}</Pill>
          <Pill>1 bp costs</Pill>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3 border-t border-white/[0.06] pt-4">
          <Metric label="CAGR" value={pct(item.cagr)} tone="text-emerald-200" />
          <Metric label="Max DD" value={pct(item.dd)} tone="text-rose-200" />
          <Metric label="Sharpe" value={(item.sharpe ?? 0).toFixed(2)} />
        </div>

        <a
          href={`/strategies/${item.slug}/`}
          className="mt-5 inline-flex rounded-full bg-emerald-300 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#07110a] transition hover:bg-emerald-200"
        >
          Open strategy page →
        </a>
      </div>

      <div className="min-w-0 space-y-4">
        <div className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="eyebrow">Selected strategy</div>
              <h2 className="mt-1 text-lg font-semibold text-zinc-100">{item.name}</h2>
            </div>
            <a href="/strategies/" className="text-[10px] text-zinc-500 transition hover:text-zinc-200">
              Browse all →
            </a>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-zinc-300">{item.tagline}</p>
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-500">{item.summary}</p>
        </div>
        <CurveChart slug={item.slug} />
      </div>
    </div>
  );
});

function Metric({ label, value, tone = "text-zinc-200" }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">{label}</div>
      <div className={`tabular mt-1 text-[16px] font-medium ${tone}`}>{value}</div>
    </div>
  );
}
