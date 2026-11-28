"use client";

import { useEffect, useMemo, useState } from "react";
import { pct } from "@/lib/format";
import { CurveChart } from "./research-detail";
import { Pill } from "./ui";

type ResearchStrategy = {
  slug: string;
  name: string;
  group: "Round 1" | "Round 2" | "Blend";
  status: "Leader" | "Verified" | "Alternative" | "Blend" | "Fragile" | "Negative";
  tagline: string;
  summary: string;
  decision: string;
  rules: string[];
  verdict: string;
  metrics: { cagr10: number; dd10: number; cagr5: number; dd5: number };
  curve: string | null;
};

type Payload = { strategies: ResearchStrategy[] };

const TONE: Record<ResearchStrategy["status"], "green" | "blue" | "amber" | "red" | "neutral"> = {
  Leader: "green",
  Verified: "green",
  Alternative: "blue",
  Blend: "blue",
  Fragile: "amber",
  Negative: "red",
};

export function ResearchLabBrowser({
  initialSlug = "ratio-pairs",
  showSelector = true,
}: {
  initialSlug?: string;
  showSelector?: boolean;
}) {
  const [data, setData] = useState<Payload | null>(null);
  const [slug, setSlug] = useState(initialSlug);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSlug(initialSlug);
  }, [initialSlug]);

  useEffect(() => {
    fetch("/data/research/strategies.json?v=2026-11-28-44c")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<Payload>;
      })
      .then(setData)
      .catch((reason) => setError(String(reason)));
  }, []);

  const selected = useMemo(
    () => data?.strategies.find((strategy) => strategy.slug === slug) ?? data?.strategies[0],
    [data, slug],
  );

  if (error) {
    return <div className="panel p-6 text-[12px] text-rose-200">Could not load strategies: {error}</div>;
  }

  if (!data || !selected) {
    return <div className="panel h-[360px] animate-pulse bg-white/[0.02]" />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="panel min-w-0 p-5">
        <div className="eyebrow">Precomputed research</div>
        <h2 className="mt-1 text-lg font-semibold text-zinc-100">Selected result</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-zinc-500">
          This is a saved 1-minute research result. Choose a runnable preset in the unified
          selector above to edit parameters and rerun the Rust engine.
        </p>

        {showSelector ? (
          <label className="mt-5 block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
            Strategy
            <select
              value={selected.slug}
              onChange={(event) => setSlug(event.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
            >
              {data.strategies.map((strategy) => (
                <option key={strategy.slug} value={strategy.slug}>
                  {strategy.name} · {strategy.status}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="mt-5 text-[11px] text-zinc-500">
            Selected from the unified strategy selector above.
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Pill tone={TONE[selected.status]}>{selected.status}</Pill>
          <Pill>{selected.group}</Pill>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-4">
          <Metric label="10y CAGR" value={pct(selected.metrics.cagr10)} tone="text-emerald-200" />
          <Metric label="10y DD" value={pct(selected.metrics.dd10)} tone="text-rose-200" />
          <Metric label="5y CAGR" value={pct(selected.metrics.cagr5)} />
          <Metric label="5y DD" value={pct(selected.metrics.dd5)} tone="text-rose-200/80" />
        </div>

        <a
          href={`/research/${selected.slug}`}
          className="mt-5 inline-flex rounded-full bg-emerald-300 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#07110a] transition hover:bg-emerald-200"
        >
          Open full research page →
        </a>
      </div>

      <div className="min-w-0 space-y-4">
        <div className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="eyebrow">Selected strategy</div>
              <h2 className="mt-1 text-lg font-semibold text-zinc-100">{selected.name}</h2>
            </div>
            <a href="/research" className="text-[10px] text-zinc-500 transition hover:text-zinc-200">
              Browse all 31 →
            </a>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-zinc-300">{selected.tagline}</p>
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-500">{selected.summary}</p>
          <div className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <div className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">
              Decision process
            </div>
            <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">{selected.decision}</p>
          </div>
        </div>

        {selected.curve ? (
          <CurveChart slug={selected.slug} />
        ) : (
          <div className="panel p-5 text-[12px] leading-relaxed text-zinc-500">
            An equity curve was not exported for this strategy. The metrics, rules and full report
            are available on its research page.
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, tone = "text-zinc-200" }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">{label}</div>
      <div className={`tabular mt-1 text-[16px] font-medium ${tone}`}>{value}</div>
    </div>
  );
}
