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

type LibraryPayload = { generated: string; window: string; strategies: Strategy[] };

type Curve = { id: string; values: (number | null)[] };

type ComparePayload = {
  start: string;
  end: string;
  dates: string[];
  series: Curve[];
};

export function ResearchLibrary() {
  const [data, setData] = useState<LibraryPayload | null>(null);
  const [compare, setCompare] = useState<ComparePayload | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/data/research/rebuild.json?v=2026-11-28-47").then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<LibraryPayload>;
      }),
      fetch("/data/compare/all.min.json?v=2026-11-28-47").then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<ComparePayload>;
      }),
    ])
      .then(([library, curves]) => {
        setData(library);
        setCompare(curves);
        setStart(curves.start);
        setEnd(curves.end);
      })
      .catch((reason) => setError(String(reason)));
  }, []);

  const range = useMemo(() => {
    if (!compare) return null;
    const lo = start || compare.start;
    const hi = end || compare.end;
    const indices = compare.dates
      .map((date, index) => ({ date, index }))
      .filter((item) => item.date >= lo && item.date <= hi)
      .map((item) => item.index);
    if (indices.length < 2) return null;
    const days = (Date.parse(compare.dates[indices[indices.length - 1]]) - Date.parse(compare.dates[indices[0]])) / 86_400_000;
    return { lo, hi, indices, years: days / 365.25 };
  }, [compare, start, end]);

  const strategies = useMemo(() => {
    if (!data) return [];
    if (!compare || !range) return data.strategies;
    const curves = new Map(compare.series.map((curve) => [curve.id, curve]));
    return data.strategies.map((strategy) => {
      const curve = curves.get(strategy.slug);
      if (!curve) return strategy;
      const values = range.indices
        .map((index) => curve.values[index])
        .filter((value): value is number => value != null);
      if (values.length < 2) return strategy;
      const first = values[0];
      const last = values[values.length - 1];
      const rets = values.slice(1).map((value, index) => value / values[index] - 1);
      const mean = rets.reduce((sum, value) => sum + value, 0) / rets.length;
      const sd = Math.sqrt(rets.reduce((sum, value) => sum + (value - mean) ** 2, 0) / rets.length);
      let peak = -Infinity;
      let dd = 0;
      for (const value of values) {
        peak = Math.max(peak, value);
        dd = Math.min(dd, value / peak - 1);
      }
      return {
        ...strategy,
        cagr: range.years > 0 ? (last / first) ** (1 / range.years) - 1 : 0,
        dd: Math.abs(dd),
        sharpe: sd > 0 ? (mean / sd) * Math.sqrt(252) : 0,
      };
    });
  }, [data, compare, range]);

  if (error) {
    return <div className="panel p-6 text-[12px] text-rose-200">Could not load strategies: {error}</div>;
  }

  if (!data || !compare) {
    return <div className="panel h-[320px] animate-pulse bg-white/[0.02]" />;
  }

  const lo = range?.lo ?? compare.start;
  const hi = range?.hi ?? compare.end;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[11px] text-zinc-500">
            {strategies.length} strategies · {lo} to {hi} · 1 bp costs
          </div>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">
              Start
              <input
                type="date"
                min={compare.start}
                max={compare.end}
                value={start || compare.start}
                onChange={(event) => setStart(event.target.value)}
                className="mt-1 block rounded-lg border border-white/10 bg-[#0b0d10] px-2.5 py-1.5 text-[11px] text-zinc-200 outline-none focus:border-emerald-300/40"
              />
            </label>
            <label className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">
              End
              <input
                type="date"
                min={compare.start}
                max={compare.end}
                value={end || compare.end}
                onChange={(event) => setEnd(event.target.value)}
                className="mt-1 block rounded-lg border border-white/10 bg-[#0b0d10] px-2.5 py-1.5 text-[11px] text-zinc-200 outline-none focus:border-emerald-300/40"
              />
            </label>
          </div>
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
            href={`/strategies/${strategy.slug}`}
            className="group panel flex flex-col overflow-hidden transition hover:border-white/20"
          >
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
                <span>
                  {lo} → {hi} · 1 bp
                </span>
                <span className="transition group-hover:text-zinc-200">Open</span>
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
