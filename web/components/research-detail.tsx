"use client";

import { memo, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatSeriesDate, pct } from "@/lib/format";
import { Markdown } from "./markdown";
import { Pill } from "./ui";

type ProvenanceCard = {
  idea: string;
  source: string;
  url?: string | null;
  source_type?: string;
  role?: string;
  role_detail?: string;
  evidence?: string;
  confidence?: string;
};
type RejectedSource = {
  source: string;
  url?: string | null;
  why_rejected: string;
};
type Paper = { label: string; url: string };

export type Detail = {
  slug: string;
  name: string;
  tagline: string;
  summary: string;
  metrics: { cagr: number | null; dd: number | null; sharpe: number | null };
  window?: string;
  archive?: boolean;
  has_curve?: boolean;
  status?: string;
  assessment: { verdict?: string; reason?: string };
  paths: {
    report?: string | null;
    hypothesis?: string | null;
    spec?: string | null;
    provenance?: string | null;
    code?: string | null;
    code_public?: string | null;
  };
  extracted: { hypothesis: boolean; spec: boolean; provenance: boolean };
  decision: string;
  rules: string[];
  papers: Paper[];
  brief?: {
    origin: string;
    mechanism: string;
    steps: string[];
    why: string;
    falsifiers: string[];
    caveat?: string;
  };
  provenance_cards: ProvenanceCard[];
  rejected_sources: RejectedSource[];
  report_md: string;
  hypothesis_md: string;
  spec_md: string;
  provenance_md: string;
  code: string;
};

type CurvePayload = {
  start: string;
  end: string;
  dates: string[];
  values: (number | null)[];
  tqqq: (number | null)[] | null;
};

function host(url?: string | null) {
  if (!url) return "source";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "source";
  }
}

function roleClasses(role?: string) {
  const value = (role ?? "").toLowerCase();
  if (value.includes("reject") || value.includes("not used") || value.includes("counter"))
    return "border-rose-300/20 bg-rose-300/[0.06] text-rose-200";
  if (value.includes("inspired"))
    return "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200";
  if (value.includes("support"))
    return "border-sky-300/20 bg-sky-300/[0.06] text-sky-200";
  if (value.includes("test") || value.includes("benchmark") || value.includes("own"))
    return "border-amber-300/20 bg-amber-300/[0.06] text-amber-200";
  if (value.includes("literature"))
    return "border-violet-300/20 bg-violet-300/[0.06] text-violet-200";
  return "border-white/10 bg-white/[0.03] text-zinc-400";
}

function fmtPct(value: number | null | undefined) {
  return value == null ? "—" : pct(value);
}

// Memoized: the lab pages re-render on every keystroke and slider tick.
export const CurveChart = memo(function CurveChart({ slug }: { slug: string }) {
  const [payload, setPayload] = useState<CurvePayload | null>(null);
  const [scale, setScale] = useState<"log" | "linear">("log");

  useEffect(() => {
    const controller = new AbortController();
    setPayload(null);
    fetch(`/data/compare/curves/${encodeURIComponent(slug)}.json?v=2026-11-28-47`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<CurvePayload>;
      })
      .then(setPayload)
      .catch(() => {
        if (!controller.signal.aborted) setPayload(null);
      });
    return () => controller.abort();
  }, [slug]);

  const rows = useMemo(() => {
    if (!payload) return [];
    return payload.dates.map((date, index) => ({
      date,
      strategy: payload.values[index],
      tqqq: payload.tqqq?.[index] ?? null,
    }));
  }, [payload]);

  const ticks = useMemo(() => {
    const out: string[] = [];
    let last = "";
    rows.forEach((row) => {
      const year = row.date.slice(0, 4);
      if (year !== last && (out.length === 0 || Number(year) % 2 === 0)) {
        out.push(row.date);
        last = year;
      }
    });
    return out;
  }, [rows]);

  if (!payload || rows.length === 0) {
    return <div className="panel h-[320px] animate-pulse bg-white/[0.02]" />;
  }

  return (
    <section className="panel p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Equity curve</div>
          <h2 className="mt-1 text-lg font-semibold text-zinc-100">Growth of $100</h2>
          <p className="mt-1 text-[11px] text-zinc-500">
            {payload.start} to {payload.end} · daily close · 1 bp costs · TQQQ benchmark
          </p>
        </div>
        <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
          {(["linear", "log"] as const).map((option) => (
            <button
              key={option}
              onClick={() => setScale(option)}
              className={`rounded-md px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] transition ${
                scale === option ? "bg-white/10 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
      <div className="h-[380px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke="#22262c" strokeDasharray="4 6" vertical={false} />
            <XAxis
              dataKey="date"
              ticks={ticks}
              interval={0}
              tickFormatter={(value: string) => value.slice(0, 4)}
              tick={{ fill: "#9aa1ab", fontSize: 12 }}
              axisLine={{ stroke: "#2a3037" }}
              tickLine={false}
            />
            <YAxis
              scale={scale}
              domain={["auto", "auto"]}
              tick={{ fill: "#9aa1ab", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value: number) => `${Math.round(value)}`}
              width={46}
            />
            <Tooltip
              formatter={(value: number, name: string) => [`$${Number(value).toFixed(1)}`, name]}
              labelFormatter={(value: string) => formatSeriesDate(value)}
              contentStyle={{
                background: "#0b0d10",
                border: "1px solid #2a2f36",
                borderRadius: 12,
                fontSize: 12,
              }}
            />
            <Line
              type="linear"
              dataKey="tqqq"
              name="TQQQ"
              stroke="#71717a"
              strokeWidth={1.4}
              strokeDasharray="4 4"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="linear"
              dataKey="strategy"
              name="Strategy"
              stroke="#9ae6a5"
              strokeWidth={2.2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Brush
              dataKey="date"
              height={24}
              stroke="#3f3f46"
              fill="#0b0d10"
              travellerWidth={8}
              tickFormatter={(value: string) => value.slice(0, 4)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
});

function CodePanel({
  code,
  codeUrl,
  path,
  name,
}: {
  code: string;
  codeUrl?: string | null;
  path?: string | null;
  name: string;
}) {
  const [copied, setCopied] = useState(false);
  const lines = code ? code.split("\n").length : 0;

  const copy = async () => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  if (!code) {
    return (
      <section className="panel p-5">
        <div className="eyebrow">Source code</div>
        <h2 className="mt-1 text-lg font-semibold text-zinc-100">Code not found</h2>
        <p className="mt-2 text-[12px] text-zinc-500">
          No <code>strategy.py</code> was found for this strategy.
        </p>
      </section>
    );
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-4 sm:px-5">
        <div>
          <div className="eyebrow">Source code</div>
          <h2 className="mt-1 text-lg font-semibold text-zinc-100">{name} implementation</h2>
          <p className="mt-1 break-all text-[11px] text-zinc-500">
            {lines} lines · Python · {path}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={copy}
            className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
          >
            {copied ? "Copied" : "Copy"}
          </button>
          {codeUrl ? (
            <a
              href={codeUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
            >
              Raw .py →
            </a>
          ) : null}
        </div>
      </div>
      <pre className="max-h-[560px] overflow-auto p-4 text-[12.5px] leading-[1.55] text-zinc-300">
        <code>{code}</code>
      </pre>
    </section>
  );
}

function ProvenancePanel({ detail }: { detail: Detail }) {
  const cards = detail.provenance_cards ?? [];
  const rejected = detail.rejected_sources ?? [];
  const linked = cards.filter((item) => Boolean(item.url)).length;
  const internal = cards.length - linked;

  return (
    <section className="panel p-5">
      <div className="eyebrow">Provenance</div>
      <h2 className="mt-1 text-lg font-semibold text-zinc-100">
        Where each part comes from
      </h2>
      <p className="mt-2 max-w-3xl text-[11px] leading-relaxed text-zinc-500">
        Which paper or internal test supports each rule. A paper supporting a component does not
        prove this exact strategy. “Internal test” means the rule came from the research process,
        not an external paper.
      </p>

      <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.1em]">
        <span className="rounded-full border border-sky-300/20 bg-sky-300/[0.06] px-2 py-0.5 text-sky-200">
          {linked} linked paper{linked === 1 ? "" : "s"}
        </span>
        <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-2 py-0.5 text-amber-200">
          {internal} internal / own-test
        </span>
      </div>

      {!cards.length ? (
        <div className="mt-4 rounded-xl border border-dashed border-white/10 p-4 text-[11px] leading-relaxed text-zinc-500">
          {detail.provenance_md
            ? "No structured source cards were saved. The original provenance notes are reproduced below; citations without a URL are literature references, not linked papers."
            : "No component-level source mapping was saved by the original research agent. This strategy is an internal hypothesis; the rules and report are not an external replication."}
        </div>
      ) : null}

      {!cards.length && detail.provenance_md ? (
        <div className="mt-4">
          <Markdown>{detail.provenance_md}</Markdown>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {cards.map((item, index) => (
          <div
            key={`${item.source}-${index}`}
            className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full border px-2 py-0.5 text-[9px] uppercase tracking-[0.1em] ${roleClasses(item.role)}`}
              >
                {item.role || "source"}
              </span>
              {item.source_type ? (
                <span className="inline-block max-w-[240px] truncate text-[9px] uppercase tracking-[0.1em] text-zinc-600">
                  {item.source_type}
                </span>
              ) : null}
              {item.confidence ? (
                <span className="text-[9px] uppercase tracking-[0.1em] text-zinc-600">
                  {item.confidence} confidence
                </span>
              ) : null}
            </div>
            <div className="mt-2 text-[13px] font-medium leading-snug text-zinc-200">
              {item.idea}
            </div>
            <div className="mt-1 text-[11px] text-zinc-500">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-zinc-300 underline decoration-white/15 underline-offset-2 transition hover:text-emerald-200"
                >
                  {item.source}
                </a>
              ) : (
                item.source
              )}
              {item.url ? <span> · {host(item.url)}</span> : null}
            </div>
            {item.role_detail &&
            item.role_detail.toLowerCase() !== (item.role ?? "").toLowerCase() ? (
              <p className="mt-1 text-[10px] leading-relaxed text-zinc-600">{item.role_detail}</p>
            ) : null}
            {item.evidence ? (
              <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{item.evidence}</p>
            ) : null}
          </div>
        ))}
      </div>

      {rejected.length ? (
        <div className="mt-5">
          <div className="text-[10px] uppercase tracking-[0.14em] text-rose-200/80">
            Tested and rejected
          </div>
          <div className="mt-2 space-y-2">
            {rejected.map((item, index) => (
              <div
                key={`${item.source}-${index}`}
                className="rounded-lg border border-rose-300/10 bg-rose-300/[0.03] p-3"
              >
                <div className="text-[11px] text-zinc-300">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="underline decoration-white/15 underline-offset-2 hover:text-rose-200"
                    >
                      {item.source}
                    </a>
                  ) : (
                    item.source
                  )}
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
                  {item.why_rejected}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {detail.provenance_md ? (
        <details className="mt-5">
          <summary className="cursor-pointer text-[10px] uppercase tracking-[0.14em] text-zinc-500">
            Full provenance text
          </summary>
          <Markdown className="mt-3">{detail.provenance_md}</Markdown>
        </details>
      ) : null}
    </section>
  );
}

function DecisionPanel({ detail }: { detail: Detail }) {
  const rules = detail.rules ?? [];
  const reason = detail.assessment.reason;
  const verdict = detail.assessment.verdict;

  return (
    <div className="panel p-5">
      <div className="eyebrow">Decision process</div>
      <h2 className="mt-1 text-lg font-semibold text-zinc-100">How it decides</h2>
      <p className="mt-3 text-[13px] leading-relaxed text-zinc-400">
        {detail.decision || detail.summary}
      </p>
      {rules.length ? (
        <ol className="mt-4 space-y-3">
          {rules.map((rule, index) => (
            <li key={`${rule}-${index}`} className="flex gap-3 text-[13px] leading-relaxed text-zinc-300">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/10 text-[10px] text-zinc-400">
                {index + 1}
              </span>
              {rule}
            </li>
          ))}
        </ol>
      ) : detail.spec_md ? (
        <details className="mt-4">
          <summary className="cursor-pointer text-[10px] uppercase tracking-[0.14em] text-zinc-500">
            Full rule specification
          </summary>
          <Markdown className="mt-2">{detail.spec_md}</Markdown>
        </details>
      ) : null}
      <div className="mt-5 rounded-xl border border-amber-300/15 bg-amber-300/[0.04] p-4">
        <div className="text-[10px] uppercase tracking-[0.14em] text-amber-200/80">
          Audit assessment
        </div>
        <p className="mt-2 text-[13px] leading-relaxed text-zinc-300">
          {reason || "No separate assessment was recorded for this strategy."}
        </p>
        {verdict ? (
          <p className="mt-2 text-[10px] uppercase tracking-[0.1em] text-zinc-500">
            Verdict: <span className="text-zinc-300">{verdict}</span>
          </p>
        ) : null}
      </div>
    </div>
  );
}

function BriefCard({
  index,
  label,
  children,
}: {
  index: number;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full border border-white/10 text-[10px] text-zinc-400">
          {index}
        </span>
        <div className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">{label}</div>
      </div>
      <div className="mt-2 text-[12.5px] leading-relaxed text-zinc-300">{children}</div>
    </div>
  );
}

function ResearchBrief({ detail }: { detail: Detail }) {
  const brief = detail.brief;
  if (!brief) return null;
  const steps = (brief.steps ?? []).filter(Boolean).slice(0, 6);
  const falsifiers = (brief.falsifiers ?? []).filter(Boolean).slice(0, 6);

  return (
    <section className="panel p-5">
      <div className="eyebrow">Research brief</div>
      <h2 className="mt-1 text-lg font-semibold text-zinc-100">
        The idea, the mechanism and the evidence
      </h2>
      <p className="mt-2 max-w-3xl text-[11px] leading-relaxed text-zinc-500">
        Read this first: where the rule came from, how each part is meant to work, why it might
        survive, and what evidence would prove it wrong.
      </p>
      <div className="mt-5 grid items-start gap-4 md:grid-cols-2">
        <BriefCard index={1} label="Where the idea came from">
          <p>{brief.origin}</p>
        </BriefCard>
        <BriefCard index={2} label="How it works, part by part">
          <p>{brief.mechanism}</p>
          {steps.length ? (
            <ol className="mt-3 space-y-2">
              {steps.map((step, stepIndex) => (
                <li key={`${step}-${stepIndex}`} className="flex gap-2">
                  <span className="mt-0.5 text-[10px] tabular text-zinc-500">
                    {stepIndex + 1}.
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          ) : null}
        </BriefCard>
        <BriefCard index={3} label="Why it could work">
          <p>{brief.why}</p>
        </BriefCard>
        <BriefCard index={4} label="What would falsify it">
          {falsifiers.length ? (
            <ul className="space-y-2">
              {falsifiers.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`} className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-zinc-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No separate falsifiers were saved for this strategy.</p>
          )}
        </BriefCard>
      </div>
      <p className="mt-4 text-[11px] leading-relaxed text-zinc-500">
        Part-by-part source mapping follows in Provenance. A paper supporting a component does not
        prove this exact rule; where no paper is linked, the idea is an internal hypothesis.
      </p>
    </section>
  );
}

function PaperPanel({ detail }: { detail: Detail }) {
  const papers = detail.papers ?? [];
  return (
    <div className="panel p-5">
      <div className="eyebrow">Research</div>
      <h2 className="mt-1 text-lg font-semibold text-zinc-100">Papers & sources</h2>
      {papers.length ? (
        <div className="mt-4 space-y-3">
          {papers.map((paper) => (
            <a
              key={`${paper.label}-${paper.url}`}
              href={paper.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg border border-white/[0.06] p-3 transition hover:border-white/15 hover:bg-white/[0.02]"
            >
              <div className="text-[12px] font-medium leading-snug text-zinc-200">
                {paper.label}
              </div>
              <div className="mt-1 text-[10px] text-zinc-500">{host(paper.url)}</div>
            </a>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-zinc-500">
          No external paper is linked for this strategy. Its idea is documented as an internal
          research hypothesis in the report below; no external paper is implied.
        </p>
      )}
      <a
        href="#full-report"
        className="mt-4 inline-flex rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
      >
        Read full report ↓
      </a>
    </div>
  );
}

/**
 * A strategy's 2016-2026 record: metrics, curve, rules, sources, report and code.
 * `embedded` drops the page header so it can sit under a strategy dashboard.
 */
export function ResearchDetail({ detail, embedded = false }: { detail: Detail; embedded?: boolean }) {
  return (
    <div className="space-y-6">
      {embedded ? (
        <div>
          <div className="eyebrow">Same-window record</div>
          <h2 className="display mt-1 text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
            2016-2026 results, rules and Python code
          </h2>
          <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-zinc-500">
            The same rule run on the 2016-2026 window every strategy shares, so it can be compared
            with the rest of the library.
          </p>
        </div>
      ) : null}
      <div className={`flex flex-wrap items-center justify-between gap-3 ${embedded ? "hidden" : ""}`}>
        <a
          href="/strategies/"
          className="inline-flex text-[11px] text-zinc-500 transition hover:text-zinc-200"
        >
          ← Strategy library
        </a>
        <a
          href="/compare"
          className={`rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100 ${
            detail.archive ? "hidden" : ""
          }`}
        >
          Open in all-strategies view
        </a>
      </div>

      <section className={`panel-soft p-5 sm:p-6 ${embedded ? "hidden" : ""}`}>
        <div className="flex flex-wrap items-center gap-2">
          {detail.archive ? <Pill>Archived</Pill> : null}
          {detail.status ? <Pill>{detail.status}</Pill> : null}
          {detail.assessment.verdict ? <Pill>{detail.assessment.verdict}</Pill> : null}
          <span className="text-[11px] text-zinc-500">
            {(detail.papers ?? []).length
              ? `${(detail.papers ?? []).length} linked paper${(detail.papers ?? []).length === 1 ? "" : "s"}`
              : "no linked paper · internal hypothesis"}
          </span>
          <span className="text-[11px] text-zinc-500">
            {detail.window ?? "2016-2026"} · 1 bp
          </span>
        </div>
        <h1 className="display mt-4 text-[2.2rem] font-semibold text-zinc-50 sm:text-[3rem]">
          {detail.name}
        </h1>
        <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-zinc-300">{detail.tagline}</p>
        <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-zinc-400">{detail.summary}</p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="CAGR" value={fmtPct(detail.metrics.cagr)} tone="text-emerald-200" />
        <Metric label="Max drawdown" value={fmtPct(detail.metrics.dd)} tone="text-rose-200" />
        <Metric
          label="Sharpe"
          value={detail.metrics.sharpe == null ? "—" : detail.metrics.sharpe.toFixed(2)}
          tone="text-zinc-200"
        />
        <Metric label="Window" value={detail.window === "2016-2023" ? "2016-23" : "2016-26"} tone="text-zinc-200" />
      </section>

      {detail.brief?.caveat ? (
        <div className="rounded-xl border border-amber-300/20 bg-amber-300/[0.05] p-4">
          <div className="text-[10px] uppercase tracking-[0.14em] text-amber-200/80">
            Caveat
          </div>
          <p className="mt-2 text-[12.5px] leading-relaxed text-zinc-300">
            {detail.brief.caveat}
          </p>
        </div>
      ) : null}

      {detail.archive ? (
        <div className="panel-soft p-4 text-[12px] leading-relaxed text-zinc-400">
          This is a development-only or below-bar strategy. It is kept in the
          archive for completeness and is not part of the 2016-2026 above-TQQQ ranking.
        </div>
      ) : null}

      {detail.has_curve === false ? null : <CurveChart slug={detail.slug} />}

      <ResearchBrief detail={detail} />

      <section className="grid items-start gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <DecisionPanel detail={detail} />
        <PaperPanel detail={detail} />
      </section>

      <ProvenancePanel detail={detail} />

      {detail.hypothesis_md ? (
        <details className="panel p-5">
          <summary className="cursor-pointer text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            Pre-registered hypothesis {detail.extracted.hypothesis ? "(from report.md)" : ""}
          </summary>
          <Markdown className="mt-3">{detail.hypothesis_md}</Markdown>
        </details>
      ) : null}

      {detail.spec_md ? (
        <details className="panel p-5">
          <summary className="cursor-pointer text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            Specification and execution {detail.extracted.spec ? "(from report.md)" : ""}
          </summary>
          <Markdown className="mt-3">{detail.spec_md}</Markdown>
        </details>
      ) : null}

      <section id="full-report" className="panel p-5">
        <div className="eyebrow">Full report</div>
        <h2 className="mt-1 text-lg font-semibold text-zinc-100">
          Original pre-registration and notes
        </h2>
        <p className="mt-2 max-w-3xl text-[11px] leading-relaxed text-zinc-500">
          The record behind the rules: sources, falsifiers, results and limitations. The
          dated note at the top points to the consolidated audit.
        </p>
        <Markdown>{detail.report_md}</Markdown>
      </section>

      <CodePanel
        code={detail.code}
        codeUrl={detail.paths.code_public}
        path={detail.paths.code}
        name={detail.name}
      />

      <p className="text-[11px] leading-relaxed text-zinc-500">
        Metrics are 2016-2026 daily-close, next-open fills, 2% band and 1 bp costs. Where the
        post-freeze tune changed a strategy, this page shows the pre-registered freeze; the
        post-tune variant is documented in <code>WHY_UNDERPERFORM.md</code> §3.
      </p>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="panel-soft p-4">
      <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div className={`tabular mt-2 text-[1.45rem] font-semibold leading-none ${tone}`}>{value}</div>
    </div>
  );
}
