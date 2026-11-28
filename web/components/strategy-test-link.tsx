"use client";

import { useState } from "react";

export function StrategyTestLink({ slug }: { slug: string }) {
  const [start, setStart] = useState("2016-01-04");
  const [end, setEnd] = useState("2026-10-23");
  const valid = start < end;
  const href = `/lab?slug=${encodeURIComponent(slug)}&start=${start}&end=${end}`;

  return (
    <div className="panel-soft flex flex-col gap-3 p-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="eyebrow">Test this strategy</div>
        <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
          Choose any start and end date, then run this strategy in the research lab.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">
          Start
          <input
            type="date"
            min="2016-01-04"
            max="2026-10-23"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            className="mt-1 block rounded-lg border border-white/10 bg-[#0b0d10] px-2.5 py-1.5 text-[11px] text-zinc-200 outline-none focus:border-emerald-300/40"
          />
        </label>
        <label className="text-[9px] uppercase tracking-[0.12em] text-zinc-600">
          End
          <input
            type="date"
            min="2016-01-04"
            max="2026-10-23"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            className="mt-1 block rounded-lg border border-white/10 bg-[#0b0d10] px-2.5 py-1.5 text-[11px] text-zinc-200 outline-none focus:border-emerald-300/40"
          />
        </label>
        <a
          href={valid ? href : undefined}
          aria-disabled={!valid}
          className={`rounded-lg px-3 py-2 text-[11px] font-semibold transition ${
            valid
              ? "bg-emerald-300 text-[#07110a] hover:bg-emerald-200"
              : "cursor-not-allowed bg-white/5 text-zinc-600"
          }`}
        >
          Open in lab →
        </a>
      </div>
    </div>
  );
}
