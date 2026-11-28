"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { PerformanceData, WindowId } from "@/lib/types";
import { BENCHMARKS, PRESETS, PRESET_LIST } from "@/lib/presets";
import { isoRange, multiple, num, pct, points } from "@/lib/format";
import { EquityChart } from "@/components/equity-chart";
import { DrawdownChart } from "@/components/drawdown-chart";
import { YearlyChart } from "@/components/yearly-chart";
import { TradePanel } from "@/components/trade-panel";
import { RangeSelector, filterSeries, type SeriesRange } from "@/components/range-selector";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { ResearchLabBrowser } from "@/components/research-lab-browser";
import { Pill, StatCard } from "@/components/ui";

const inputClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40";

export default function LabPage() {
  const first = PRESET_LIST[0];
  const [presetId, setPresetId] = useState(first.id);
  const preset = PRESETS[presetId] ?? first;
  const [windowId, setWindowId] = useState<WindowId>(preset.windows[0]);
  const [benchmark, setBenchmark] = useState(preset.benchmark);
  const [slippage, setSlippage] = useState(1);
  const [sma, setSma] = useState(preset.strategy.smaDays);
  const [targetVol, setTargetVol] = useState(preset.strategy.targetVol * 100);
  const [leverage, setLeverage] = useState(preset.strategy.leverage);
  const [band, setBand] = useState(preset.strategy.rebalanceBand * 100);
  const [refresh, setRefresh] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<PerformanceData | null>(null);
  const [meta, setMeta] = useState<{ cached: boolean; elapsedMs: number } | null>(null);
  const [range, setRange] = useState<SeriesRange>("all");
  const [selection, setSelection] = useState("research:ratio-pairs");
  const [catalog, setCatalog] = useState<
    { id: string; slug: string; name: string; runnable: boolean; status: string }[]
  >([]);
  const bootstrapped = useRef(false);
  const isResearch = selection.startsWith("research:");
  const researchSlug = isResearch ? selection.slice("research:".length) : "ratio-pairs";

  useEffect(() => {
    fetch("/data/catalog/strategies.json?v=2026-11-28-43f", { cache: "no-store" })
      .then((response) => response.json() as Promise<{ strategies: typeof catalog }>)
      .then((payload) => setCatalog(payload.strategies))
      .catch(() => setCatalog([]));
  }, []);

  const choosePreset = (id: string) => {
    const next = PRESETS[id];
    if (!next) return;
    setPresetId(id);
    setWindowId(next.windows[0]);
    setBenchmark(next.benchmark);
    setSma(next.strategy.smaDays);
    setTargetVol(next.strategy.targetVol * 100);
    setLeverage(next.strategy.leverage);
    setBand(next.strategy.rebalanceBand * 100);
    setData(null);
    setMeta(null);
    setError(null);
  };

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch("/api/backtest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          preset: presetId,
          window: windowId,
          benchmark,
          slippageBps: slippage,
          refresh,
          strategy: {
            smaDays: sma,
            targetVol: targetVol / 100,
            leverage,
            rebalanceBand: band / 100,
          },
        }),
      });
      const payload = (await response.json()) as {
        data?: PerformanceData;
        error?: string;
        cached?: boolean;
        elapsedMs?: number;
      };
      if (!response.ok || !payload.data) throw new Error(payload.error ?? "Backtest failed");
      setData(payload.data);
      setMeta({ cached: Boolean(payload.cached), elapsedMs: payload.elapsedMs ?? 0 });
      setRange("all");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Backtest failed");
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    if (isResearch || bootstrapped.current) return;
    bootstrapped.current = true;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isResearch]);

  const viewSeries = useMemo(
    () => (data ? filterSeries(data.series, range) : []),
    [data, range],
  );
  const maxDrawdown = useMemo(
    () => Math.max(0, ...viewSeries.map((point) => -point.drawdown)),
    [viewSeries],
  );
  const benchmarkDrawdown = useMemo(
    () =>
      Math.max(
        0,
        ...viewSeries.map((point) => (point.qqqDrawdown == null ? 0 : -point.qqqDrawdown)),
      ),
    [viewSeries],
  );

  const presetOptions = catalog.filter((item) => item.runnable).length
    ? catalog.filter((item) => item.runnable)
    : PRESET_LIST.map((item) => ({
        id: `preset:${item.id}`,
        slug: item.id,
        name: item.name,
        runnable: true,
        status: "Runnable",
      }));
  const researchOptions = catalog.filter((item) => !item.runnable);

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="lab" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="mb-4 flex flex-wrap gap-2">
                <Pill tone="green">Local backtest</Pill>
                <Pill tone="blue">Yahoo Finance</Pill>
                <Pill>32 strategies</Pill>
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                Backtest
                <br />
                <span className="text-emerald-200">lab.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[14px] leading-relaxed text-zinc-400">
                Choose any of the 32 strategies from one selector. Runnable presets open editable
                controls and rerun the Rust engine; research strategies show precomputed results,
                code and provenance.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <a
                href="/lab/custom"
                className="inline-flex items-center justify-center rounded-full bg-emerald-300 px-4 py-2 text-[11px] font-semibold text-[#07110a] transition hover:bg-emerald-200"
              >
                Write a custom strategy →
              </a>

            </div>
          </div>
        </section>

        <section id="lab" className="scroll-mt-24 pt-12">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <label className="min-w-[280px] flex-1 text-[10px] uppercase tracking-[0.12em] text-zinc-600">
              Strategy
              <select
                value={selection}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelection(value);
                  if (value.startsWith("preset:")) choosePreset(value.slice("preset:".length));
                }}
                className="mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40"
              >
                <optgroup label="Runnable presets (editable)">
                  {presetOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Research strategies (precomputed)">
                  {researchOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {item.status}
                    </option>
                  ))}
                </optgroup>
              </select>
            </label>
            <div className="text-[11px] text-zinc-500">
              {presetOptions.length} editable presets · {researchOptions.length} research results · one selector
            </div>
          </div>
          {!isResearch ? (
          <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
            <div className="panel min-w-0 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="eyebrow">Selected preset</div>
                  <div className="mt-1 text-[14px] font-medium text-zinc-100">{preset.name}</div>
                </div>
                <button
                  onClick={() => choosePreset(presetId)}
                  className="text-[10px] uppercase tracking-[0.12em] text-zinc-500 transition hover:text-zinc-200"
                >
                  Reset
                </button>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
                {preset.symbols.join(" / ")} · daily trend + leverage. Choose a period and costs,
                then run.
              </p>

              <div className="mt-5 eyebrow">Period</div>
              <div className="mt-2 grid grid-cols-4 gap-1.5">
                {preset.windows.map((window) => (
                  <button
                    key={window}
                    onClick={() => setWindowId(window)}
                    className={`rounded-lg border px-2 py-2 text-[11px] uppercase tracking-[0.08em] transition ${
                      windowId === window
                        ? "border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-100"
                        : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
                    }`}
                  >
                    {window.toUpperCase()}
                  </button>
                ))}
              </div>

              <div className="mt-5 eyebrow">Costs</div>
              <div className="mt-2 grid grid-cols-4 gap-1.5">
                {[0, 1, 5, 10].map((bp) => (
                  <button
                    key={bp}
                    onClick={() => setSlippage(bp)}
                    className={`rounded-lg border px-2 py-2 text-[11px] transition ${
                      slippage === bp
                        ? "border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-100"
                        : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
                    }`}
                  >
                    {bp} bp
                  </button>
                ))}
              </div>

              <label className="mt-4 block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                Benchmark
                <select
                  value={benchmark}
                  onChange={(event) => setBenchmark(event.target.value)}
                  className={inputClass}
                >
                  {BENCHMARKS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <details className="mt-4 rounded-lg border border-white/10 p-3">
                <summary className="cursor-pointer text-[11px] font-medium text-zinc-400 transition hover:text-zinc-200">
                  Advanced parameters
                </summary>
                <div className="mt-3 grid grid-cols-2 gap-3">
                <NumberInput label="Trend filter (days)" value={sma} setValue={setSma} min={2} max={500} step={1} />
                <NumberInput
                  label="Vol target % (0 = off)"
                  value={targetVol}
                  setValue={setTargetVol}
                  min={0}
                  max={100}
                  step={5}
                />
                <NumberInput
                  label="Leverage (1–5)"
                  value={leverage}
                  setValue={setLeverage}
                  min={1}
                  max={5}
                  step={0.5}
                />
                <NumberInput
                  label="Band %"
                  value={band}
                  setValue={setBand}
                  min={0}
                  max={50}
                  step={1}
                />
                <NumberInput
                  label="Custom slippage (bp)"
                  value={slippage}
                  setValue={setSlippage}
                  min={0}
                  max={100}
                  step={1}
                />
                <label className="flex items-end gap-2 pb-2 text-[11px] text-zinc-500">
                  <input
                    type="checkbox"
                    checked={refresh}
                    onChange={(event) => setRefresh(event.target.checked)}
                    className="h-3.5 w-3.5 rounded border-white/20 bg-black/30"
                  />
                  Ignore cache
                </label>
                </div>
              </details>

              <button
                onClick={() => void run()}
                disabled={running}
                className="mt-5 w-full rounded-lg bg-emerald-300 px-4 py-2.5 text-[12px] font-semibold text-[#07110a] transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60"
              >
                {running ? "Running backtest..." : "Run backtest"}
              </button>
              <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
                The first run downloads Yahoo data and can take several seconds. Results are cached
                locally by input hash.
              </p>
              {error ? (
                <div className="mt-3 max-h-48 overflow-auto rounded-lg border border-rose-300/20 bg-rose-300/[0.05] p-3 text-[10px] leading-relaxed text-rose-200">
                  {error}
                </div>
              ) : null}
            </div>

            <div className="min-w-0">
              {!data ? (
                <div className="panel flex min-h-[420px] flex-col items-center justify-center p-8 text-center">
                  <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200">
                    ▶
                  </div>
                  <div className="text-[14px] font-medium text-zinc-300">
                    {running ? "Running the first backtest…" : "No run yet"}
                  </div>
                  <p className="mt-2 max-w-sm text-[11px] leading-relaxed text-zinc-600">
                    Pick a strategy and horizon, then run the backtest. The result will appear here
                    with the same charts as the strategy portals.
                  </p>
                  <button
                    onClick={() => void run()}
                    disabled={running}
                    className="mt-4 rounded-full bg-emerald-300 px-4 py-2 text-[11px] font-semibold text-[#07110a] transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60"
                  >
                    {running ? "Running…" : "Run the default backtest"}
                  </button>
                </div>
              ) : (
                <div>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-[11px] text-zinc-500">
                        {preset.name} · {isoRange(data.start, data.end)}
                      </div>
                      <div className="mt-1 text-[10px] text-zinc-600">
                        {meta?.cached ? "cached result" : `ran in ${((meta?.elapsedMs ?? 0) / 1000).toFixed(1)}s`}
                        {" · "}
                        <a
                          href={`/strategies/${presetId}/`}
                          className="text-zinc-400 transition hover:text-zinc-200"
                        >
                          open full portal ↗
                        </a>
                      </div>
                    </div>
                    <RangeSelector
                      value={range}
                      onChange={setRange}
                      series={viewSeries}
                      name={preset.name}
                      benchmark={data.benchmark}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                    <StatCard label="CAGR" value={pct(data.metrics.cagr)} sub={`${data.benchmark} ${pct(data.metrics.benchmarkCagr)} / yr`} tone="green" />
                    <StatCard label={`Excess vs ${data.benchmark}`} value={points(data.metrics.excess)} sub="per year, after costs" tone="green" />
                    <StatCard label="Max drawdown" value={pct(-data.metrics.maxDrawdown)} sub={`${data.benchmark} ${pct(data.metrics.benchmarkMaxDrawdown)}`} tone="red" />
                    <StatCard label="Sharpe" value={data.metrics.sharpe.toFixed(2)} sub={`Sortino ${data.metrics.sortino.toFixed(2)}`} tone="blue" />
                    <StatCard label="Win rate" value={pct(data.metrics.winRate)} sub={`${data.metrics.wins} wins · ${data.metrics.losses} losses`} />
                    <StatCard label="Round trips" value={num(data.metrics.closedTrades)} sub={`${num(data.metrics.fills)} fills · ${multiple(data.metrics.turnover)} turnover`} />
                  </div>

                  <div className="panel mt-4 min-w-0 p-5">
                    <EquityChart series={viewSeries} start={viewSeries[0]?.date ?? data.start} end={data.end} benchmark={data.benchmark} accent={preset.accent} />
                  </div>
                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <div className="panel min-w-0 p-5">
                      <DrawdownChart series={viewSeries} strategyMax={maxDrawdown} qqqMax={benchmarkDrawdown} benchmark={data.benchmark} />
                    </div>
                    <div className="panel min-w-0 p-5">
                      <TradePanel metrics={data.metrics} compact />
                    </div>
                  </div>
                  <div className="panel mt-4 min-w-0 p-5">
                    <YearlyChart yearly={data.yearly} benchmark={data.benchmark} />
                  </div>
                </div>
              )}
            </div>
          </div>
          ) : (
            <ResearchLabBrowser initialSlug={researchSlug} showSelector={false} />
          )}
        </section>

        <section id="data" className="scroll-mt-24 pt-16">
          <div className="eyebrow mb-2">Data</div>
          <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
            What the lab does and does not model
          </h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DataCard title="Prices and corporate actions" tone="green">
              Yahoo Finance daily adjusted closes. Splits and dividends are embedded in the
              adjusted series, and the simulator applies them to the paper ledger. Backtests use
              next-open fills and 1bp default slippage.
            </DataCard>
            <DataCard title="Delisting" tone="amber">
              The shipped strategies trade ETFs, so there is no stock-delisting risk in these
              windows. The custom lab accepts arbitrary tickers but also does not model delisting:
              a run ends at the last common bar. A survivorship-free stock universe needs a
              point-in-time delisting feed; this local dataset does not claim one.
            </DataCard>
            <DataCard title="Financial statements" tone="red">
              Not in the local dataset yet. The current engine is price-only; the custom lab is
              price-only too. SEC/EDGAR fundamentals need a separate data layer, CIK mapping,
              point-in-time filing dates and a cache before they can be a strategy input.
            </DataCard>
            <DataCard title="Reproducibility" tone="blue">
              Every run pins the end date and caches by the input settings. Use “Ignore cache” to
              force a fresh download. The
              custom lab runs in your browser and caches Yahoo prices locally for six hours.
            </DataCard>
          </div>

          <div className="panel-soft mt-4 flex flex-col gap-2 p-4 text-[11px] leading-relaxed text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Want to test your own rule, daily or intraday? Write it in the custom workspace
              and get the same charts.
            </span>
            <a className="shrink-0 text-zinc-300 transition hover:text-emerald-200" href="/lab/custom">
              Open the custom strategy workspace →
            </a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function NumberInput({
  label,
  value,
  setValue,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  setValue: (value: number) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <label className="block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
      {label}
      <input
        type="number"
        value={Number.isFinite(value) ? value : 0}
        min={min}
        max={max}
        step={step}
        onChange={(event) => setValue(Number(event.target.value))}
        className={inputClass}
      />
    </label>
  );
}

function DataCard({
  title,
  tone,
  children,
}: {
  title: string;
  tone: "green" | "amber" | "red" | "blue";
  children: ReactNode;
}) {
  const border = {
    green: "border-emerald-300/15",
    amber: "border-amber-300/15",
    red: "border-rose-300/15",
    blue: "border-sky-300/15",
  }[tone];
  return (
    <div className={`panel-soft border ${border} p-4`}>
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-300">{title}</div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{children}</p>
    </div>
  );
}
