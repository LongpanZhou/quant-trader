"use client";

import { useEffect, useMemo, useState } from "react";
import { DrawdownChart } from "@/components/drawdown-chart";
import { EquityChart } from "@/components/equity-chart";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { Pill, StatCard } from "@/components/ui";
import { multiple, num, pct } from "@/lib/format";
import type { SeriesPoint } from "@/lib/types";

type StrategyRow = {
  slug: string;
  name: string;
  tagline: string;
  cagr: number;
  dd: number;
  sharpe: number;
};

type ParamField = {
  key: string;
  label: string;
  type: "int" | "float" | "bool" | "text";
  default: boolean | number | string;
  editable: boolean;
};

type ParamsFile = { strategies: Record<string, { fields: ParamField[] }> };

type ResearchResult = {
  ok: true;
  slug: string;
  start: string;
  end: string;
  benchmark: string;
  cagr: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  volatility: number;
  fills: number;
  turnover: number;
  daily_curve: { dates: string[]; values: number[] };
  benchmark_curve: { dates: string[]; values: number[] };
};

const START = "2016-01-04";
const END = "2026-10-23";
const HIDE_KEYS = new Set(["smaDays", "sma_days", "ma"]);

export default function LabPage() {
  const [strategies, setStrategies] = useState<StrategyRow[]>([]);
  const [schema, setSchema] = useState<ParamsFile>({ strategies: {} });
  const [slug, setSlug] = useState("family-regime-switch");
  const [start, setStart] = useState(START);
  const [end, setEnd] = useState(END);
  const [slippage, setSlippage] = useState(1);
  const [values, setValues] = useState<Record<string, boolean | number | string>>({});
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const qSlug = params.get("slug");
    const qStart = params.get("start");
    const qEnd = params.get("end");
    if (qSlug && /^[a-z0-9-]{2,80}$/.test(qSlug)) setSlug(qSlug);
    if (qStart && qStart >= START && qStart < END) setStart(qStart);
    if (qEnd && qEnd <= END && qEnd > START) setEnd(qEnd);
  }, []);

  useEffect(() => {
    fetch("/data/research/rebuild.json")
      .then((r) => r.json())
      .then((d: { strategies: StrategyRow[] }) => {
        setStrategies(d.strategies);
        if (!d.strategies.some((s) => s.slug === slug) && d.strategies[0]) {
          setSlug(d.strategies[0].slug);
        }
      })
      .catch(() => setStrategies([]));
    fetch("/data/research/params.json")
      .then((r) => r.json())
      .then((d: ParamsFile) => setSchema(d))
      .catch(() => setSchema({ strategies: {} }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fields = useMemo(() => {
    const raw = schema.strategies[slug]?.fields ?? [];
    return raw.filter((f) => !HIDE_KEYS.has(f.key) && !/trend|sma/i.test(f.label));
  }, [schema, slug]);

  useEffect(() => {
    const next: Record<string, boolean | number | string> = {};
    for (const f of fields) {
      if (f.editable) next[f.key] = f.default;
    }
    setValues(next);
    setResult(null);
    setError(null);
  }, [fields]);

  const selected = strategies.find((s) => s.slug === slug);

  const series = useMemo<SeriesPoint[]>(() => {
    if (!result) return [];
    const { dates, values: sv } = result.daily_curve;
    const bv = result.benchmark_curve.values;
    const base = sv[0] || 1;
    const bbase = bv[0] || 1;
    let peak = -Infinity;
    let bpeak = -Infinity;
    return dates.map((date, i) => {
      const strategy = (sv[i] / base) * 100;
      const qqq = ((bv[i] ?? bv[bv.length - 1] ?? 0) / bbase) * 100;
      peak = Math.max(peak, strategy);
      bpeak = Math.max(bpeak, qqq);
      return {
        date,
        strategy,
        qqq,
        drawdown: strategy / peak - 1,
        qqqDrawdown: qqq / bpeak - 1,
      };
    });
  }, [result]);

  const strategyMax = useMemo(
    () => Math.max(0, ...series.map((p) => -p.drawdown)),
    [series],
  );
  const qqqMax = useMemo(
    () => Math.max(0, ...series.map((p) => -(p.qqqDrawdown ?? 0))),
    [series],
  );

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch("/api/research-backtest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ slug, start, end, params: values, slippageBps: slippage }),
      });
      const payload = (await response.json()) as ResearchResult | { ok: false; error?: string };
      if (!response.ok || !("ok" in payload) || payload.ok !== true) {
        throw new Error("error" in payload && payload.error ? payload.error : "Backtest failed");
      }
      setResult(payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Backtest failed");
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="lab" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="mb-4 flex flex-wrap gap-2">
            <Pill tone="green">Research only</Pill>
            <Pill tone="blue">Python execution</Pill>
            <Pill>{strategies.length} strategies</Pill>
          </div>
          <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
            Backtest
            <br />
            <span className="text-emerald-200">any research strategy.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-[14px] leading-relaxed text-zinc-400">
            Pick a strategy, set any start and end date, edit its Python parameters, and run it
            on the local 1-minute QQQ/TQQQ/BIL panel. No presets and no fixed windows.
          </p>
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-[380px_1fr]">
          <div className="panel h-fit min-w-0 p-5">
            <label className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
              Strategy
              <select
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
              >
                {strategies.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            {selected ? (
              <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{selected.tagline}</p>
            ) : null}

            <div className="mt-5 grid grid-cols-2 gap-3">
              <label className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                Start
                <input
                  type="date"
                  min={START}
                  max={END}
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
                />
              </label>
              <label className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                End
                <input
                  type="date"
                  min={START}
                  max={END}
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
                />
              </label>
            </div>

            <label className="mt-4 block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
              Slippage (bp)
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={slippage}
                onChange={(event) => setSlippage(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
              />
            </label>

            <div className="mt-5 border-t border-white/5 pt-4">
              <div className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                Python parameters
              </div>
              {fields.length === 0 ? (
                <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
                  This strategy has no tunable parameters exposed. Date-range testing is still
                  available.
                </p>
              ) : (
                <div className="mt-3 grid gap-3">
                  {fields.map((field) => (
                    <label
                      key={field.key}
                      className="text-[10px] uppercase tracking-[0.08em] text-zinc-600"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span>{field.label}</span>
                        {!field.editable ? (
                          <span className="normal-case tracking-normal text-[9px] text-zinc-700">
                            fixed
                          </span>
                        ) : null}
                      </span>
                      {field.type === "bool" ? (
                        <input
                          type="checkbox"
                          checked={Boolean(values[field.key] ?? field.default)}
                          disabled={!field.editable}
                          onChange={(event) =>
                            setValues((v) => ({ ...v, [field.key]: event.target.checked }))
                          }
                          className="mt-2 h-4 w-4 rounded border-white/20 bg-black/30"
                        />
                      ) : (
                        <input
                          type={field.type === "text" ? "text" : "number"}
                          value={String(values[field.key] ?? field.default)}
                          disabled={!field.editable}
                          step={field.type === "int" ? 1 : "any"}
                          onChange={(event) =>
                            setValues((v) => ({
                              ...v,
                              [field.key]:
                                field.type === "text"
                                  ? event.target.value
                                  : Number(event.target.value),
                            }))
                          }
                          className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] normal-case tracking-normal text-zinc-200 outline-none transition disabled:opacity-40 focus:border-emerald-300/40"
                        />
                      )}
                    </label>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => void run()}
              disabled={running || !slug || !start || !end}
              className="mt-5 w-full rounded-lg bg-emerald-300 px-4 py-2.5 text-[12px] font-semibold text-[#07110a] transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60"
            >
              {running ? "Running Python backtest…" : "Run backtest"}
            </button>
            <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
              The first run loads the 1-minute panel and can take several seconds. Results are
              cached by strategy, dates and parameters.
            </p>
            {error ? (
              <div className="mt-3 max-h-40 overflow-auto rounded-lg border border-rose-300/20 bg-rose-300/[0.05] p-3 text-[10px] leading-relaxed text-rose-200">
                {error}
              </div>
            ) : null}
          </div>

          <div className="min-w-0">
            {!result ? (
              <div className="panel flex min-h-[460px] flex-col items-center justify-center p-8 text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200">
                  ▶
                </div>
                <div className="text-[14px] font-medium text-zinc-300">
                  {running ? "Running the selected strategy…" : "No run yet"}
                </div>
                <p className="mt-2 max-w-sm text-[11px] leading-relaxed text-zinc-600">
                  Choose a strategy, set the start and end dates, then run. The result uses the
                  same 1-minute execution and daily-close reporting as the research library.
                </p>
              </div>
            ) : (
              <div>
                <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <div className="text-[13px] font-medium text-zinc-200">
                      {selected?.name ?? result.slug}
                    </div>
                    <div className="mt-1 text-[10px] text-zinc-600">
                      {result.start} → {result.end} · {result.benchmark} benchmark ·{" "}
                      {slippage} bp costs
                    </div>
                  </div>
                  <a
                    href={`/strategies/${result.slug}/`}
                    className="text-[10px] uppercase tracking-[0.1em] text-zinc-500 transition hover:text-zinc-200"
                  >
                    Open research page ↗
                  </a>
                </div>

                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <StatCard label="CAGR" value={pct(result.cagr)} sub="custom window" tone="green" />
                  <StatCard
                    label="Max drawdown"
                    value={pct(result.max_drawdown)}
                    sub="daily close"
                    tone="red"
                  />
                  <StatCard label="Sharpe" value={result.sharpe.toFixed(2)} sub="daily" tone="blue" />
                  <StatCard
                    label="Fills"
                    value={num(result.fills)}
                    sub={`${multiple(result.turnover)} turnover`}
                  />
                </div>

                <div className="panel mt-4 min-w-0 p-5">
                  <EquityChart
                    series={series}
                    start={result.start}
                    end={result.end}
                    benchmark={result.benchmark}
                    accent="#9ae6a5"
                  />
                </div>

                <div className="panel mt-4 min-w-0 p-5">
                  <DrawdownChart
                    series={series}
                    strategyMax={strategyMax}
                    qqqMax={qqqMax}
                    benchmark={result.benchmark}
                  />
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <StatCard label="Sortino" value={result.sortino.toFixed(2)} />
                  <StatCard label="Volatility" value={pct(result.volatility)} />
                  <StatCard label="Turnover" value={multiple(result.turnover)} />
                  <StatCard label="Strategy" value={result.slug} />
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
