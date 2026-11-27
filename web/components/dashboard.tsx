"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { PerformanceData, StrategyMeta, WindowId } from "@/lib/types";
import { WINDOWS } from "@/lib/types";
import { BENCHMARKS } from "@/lib/presets";
import { PAPERS, REPLICATION, COUNTER_EVIDENCE } from "@/lib/research";
import {
  isoRange,
  multiple,
  num,
  pct,
  points,
  signedMoney,
} from "@/lib/format";
import { EquityChart } from "./equity-chart";
import { DrawdownChart } from "./drawdown-chart";
import { YearlyChart } from "./yearly-chart";
import { MonthlyHeatmap } from "./monthly-heatmap";
import { TradePanel } from "./trade-panel";
import { DrawdownEpisodes } from "./drawdown-episodes";
import { SiteFooter, SiteHeader } from "./site-chrome";
import { RangeSelector, filterSeries, type SeriesRange } from "./range-selector";
import { Pill, SectionHeading, StatCard } from "./ui";

const REPO = "https://github.com/LongpanZhou/quant-trader";

export function StrategyDashboard({ strategy }: { strategy: StrategyMeta }) {
  const windows = WINDOWS.filter((window) => strategy.windows.includes(window.id));
  const [windowId, setWindowId] = useState<WindowId>(
    strategy.defaultWindow ?? strategy.windows[0],
  );
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<SeriesRange>("all");
  const [benchmarkBusy, setBenchmarkBusy] = useState(false);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("window");
    if (requested && strategy.windows.includes(requested as WindowId)) {
      setWindowId(requested as WindowId);
    }
  }, [strategy.windows]);

  const chooseWindow = (next: WindowId) => {
    setWindowId(next);
    const url = new URL(window.location.href);
    url.searchParams.set("window", next);
    window.history.replaceState(null, "", url);
  };

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetch(`/data/${strategy.slug}/${windowId}.json`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Could not load ${windowId} data`);
        return response.json() as Promise<PerformanceData>;
      })
      .then((next) => {
        setData(next);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Could not load data");
        setLoading(false);
      });
    return () => controller.abort();
  }, [strategy.slug, windowId]);

  const selected = windows.find((window) => window.id === windowId) ?? windows[0];
  const viewSeries = useMemo(
    () => (data ? filterSeries(data.series, range) : []),
    [data, range],
  );
  const viewMaxDrawdown = useMemo(
    () => Math.max(0, ...viewSeries.map((point) => -point.drawdown)),
    [viewSeries],
  );
  const viewBenchmarkDrawdown = useMemo(
    () =>
      Math.max(
        0,
        ...viewSeries.map((point) => (point.qqqDrawdown == null ? 0 : -point.qqqDrawdown)),
      ),
    [viewSeries],
  );
  const nameWords = strategy.name.split(" ");
  const lastWord = nameWords.pop() ?? strategy.name;
  const leadWords = nameWords.join(" ");
  const statusLabel =
    strategy.status === "current"
      ? "Current strategy"
      : strategy.status === "research"
        ? "Research variant"
        : "Ablation";
  const statusTone =
    strategy.status === "current" ? "green" : strategy.status === "research" ? "blue" : "amber";
  const asOf = new Date(`${strategy.asOf}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  const changeBenchmark = async (next: string) => {
    if (!data || next === data.benchmark || benchmarkBusy) return;
    setBenchmarkBusy(true);
    setBenchmarkError(null);
    try {
      const response = await fetch("/api/backtest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          preset: strategy.slug,
          window: windowId,
          benchmark: next,
        }),
      });
      const payload = (await response.json()) as {
        data?: PerformanceData;
        error?: string;
      };
      if (!response.ok || !payload.data) {
        throw new Error(payload.error ?? "Benchmark backtest failed");
      }
      setData(payload.data);
    } catch (reason) {
      setBenchmarkError(reason instanceof Error ? reason.message : "Benchmark backtest failed");
    } finally {
      setBenchmarkBusy(false);
    }
  };

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="strategy" />

      <main id="top" className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Pill tone={statusTone}>{statusLabel}</Pill>
                <Pill>Long-only · daily</Pill>
                <Pill tone="blue">{strategy.tags.slice(0, 3).join(" / ")}</Pill>
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                {leadWords}
                <br />
                <span style={{ color: strategy.accent }}>{lastWord.toLowerCase()}.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[14px] leading-relaxed text-zinc-400">
                {strategy.description}
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                <span
                  className="h-1.5 w-1.5 animate-pulse rounded-full"
                  style={{ background: strategy.accent }}
                />
                Data through {asOf}
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Pill>1bp slippage</Pill>
                <Pill>next-open fills</Pill>
                <Pill>Yahoo Finance</Pill>
              </div>
            </div>
          </div>
        </section>

        <section id="performance" className="scroll-mt-24 pt-14">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
            <SectionHeading
              eyebrow="Performance"
              title={`The record, ${windows.length} horizons`}
              description={strategy.dataNote}
            />
            <div
              className={`grid w-full min-w-0 gap-2 lg:w-auto ${
                windows.length === 3 ? "grid-cols-3" : "grid-cols-2 sm:grid-cols-4"
              }`}
            >
              {windows.map((window) => {
                const active = windowId === window.id;
                const synthetic = strategy.syntheticWindows.includes(window.id);
                return (
                  <button
                    key={window.id}
                    onClick={() => chooseWindow(window.id)}
                    aria-pressed={active}
                    className={`group min-w-0 rounded-xl border px-3.5 py-2.5 text-left transition ${
                      active ? "" : "border-white/10 bg-white/[0.02] hover:border-white/20"
                    }`}
                    style={
                      active
                        ? {
                            borderColor: `${strategy.accent}55`,
                            background: `${strategy.accent}14`,
                          }
                        : undefined
                    }
                  >
                    <div
                      className="text-[12px] font-medium"
                      style={{ color: active ? strategy.accent : "#d4d4d8" }}
                    >
                      {window.label}
                    </div>
                    <div className="text-[10px] text-zinc-600">
                      {window.years}
                      {synthetic ? " · synthetic" : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {error ? (
            <div className="panel mt-4 p-6 text-sm text-rose-200">{error}</div>
          ) : !data ? (
            <LoadingPanels />
          ) : (
            <div className={`transition-opacity duration-300 ${loading ? "opacity-60" : "opacity-100"}`}>
              <div className="mb-3 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-[11px] text-zinc-500">
                    {selected.label} · {isoRange(data.start, data.end)}
                  </div>
                  {benchmarkBusy ? (
                    <span className="text-[10px] text-zinc-500">updating benchmark...</span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                    Compare
                    <select
                      value={data.benchmark}
                      onChange={(event) => void changeBenchmark(event.target.value)}
                      disabled={benchmarkBusy}
                      className="rounded-md border border-white/10 bg-[#0b0d10] px-2 py-1 text-[10px] text-zinc-300 outline-none transition disabled:opacity-50"
                    >
                      {Array.from(
                        new Set([data.benchmark, ...BENCHMARKS.map((item) => item.value)]),
                      ).map((symbol) => (
                        <option key={symbol} value={symbol}>
                          {symbol}
                        </option>
                      ))}
                    </select>
                  </label>
                  <RangeSelector
                    value={range}
                    onChange={setRange}
                    series={viewSeries}
                    name={strategy.name}
                    benchmark={data.benchmark}
                  />
                </div>
              </div>
              {benchmarkError ? (
                <div className="mb-3 rounded-lg border border-rose-300/20 bg-rose-300/[0.05] px-3 py-2 text-[11px] text-rose-200">
                  {benchmarkError}
                </div>
              ) : null}

              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
                <StatCard
                  label="CAGR"
                  value={pct(data.metrics.cagr)}
                  sub={`${data.benchmark} ${pct(data.metrics.benchmarkCagr)} / yr`}
                  tone="green"
                />
                <StatCard
                  label={`Excess vs ${data.benchmark}`}
                  value={points(data.metrics.excess)}
                  sub="per year, after costs"
                  tone="green"
                />
                <StatCard
                  label="Max drawdown"
                  value={pct(-data.metrics.maxDrawdown)}
                  sub={`${data.benchmark} ${pct(data.metrics.benchmarkMaxDrawdown)}`}
                  tone="red"
                />
                <StatCard
                  label="Sharpe"
                  value={data.metrics.sharpe.toFixed(2)}
                  sub={`Sortino ${data.metrics.sortino.toFixed(2)} · vol ${pct(data.metrics.volatility)}`}
                  tone="blue"
                />
                <StatCard
                  label="Win rate"
                  value={pct(data.metrics.winRate)}
                  sub={`${data.metrics.wins} wins · ${data.metrics.losses} losses`}
                />
                <StatCard
                  label="Round trips"
                  value={num(data.metrics.closedTrades)}
                  sub={`${num(data.metrics.fills)} fills · ${multiple(data.metrics.turnover)} turnover`}
                />
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr]">
                <div className="panel min-w-0 p-5">
                  <EquityChart
                    series={viewSeries}
                    start={viewSeries[0]?.date ?? data.start}
                    end={data.end}
                    benchmark={data.benchmark}
                    accent={strategy.accent}
                  />
                </div>
                <div id="trades" className="panel scroll-mt-24 p-5">
                  <TradePanel metrics={data.metrics} />
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="panel min-w-0 p-5">
                  <DrawdownChart
                    series={viewSeries}
                    strategyMax={viewMaxDrawdown}
                    qqqMax={viewBenchmarkDrawdown}
                    benchmark={data.benchmark}
                  />
                </div>
                <div className="panel min-w-0 p-5">
                  <YearlyChart yearly={data.yearly} benchmark={data.benchmark} />
                </div>
              </div>

              <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1.35fr_1fr]">
                <div className="panel min-w-0 p-5">
                  <MonthlyHeatmap series={data.series} />
                </div>
                <div className="panel p-5 lg:sticky lg:top-24">
                  <div className="eyebrow mb-4">Book</div>
                  <div className="space-y-3">
                    <BookRow label="CAGR" value={pct(data.metrics.cagr)} />
                    <BookRow label="Total return" value={pct(data.metrics.totalReturn)} />
                    <BookRow label="Ending equity" value={`$${num(data.metrics.endEquity)}`} />
                    <BookRow label="Volatility" value={pct(data.metrics.volatility)} />
                    <BookRow label="Calmar" value={data.metrics.calmar.toFixed(2)} />
                    <BookRow label="Avg trade" value={signedMoney(data.metrics.avgTradePnl)} />
                    <BookRow label="Long exposure" value={pct(data.metrics.longExposure, 0)} />
                    <BookRow
                      label={`${data.benchmark} max drawdown`}
                      value={pct(data.metrics.benchmarkMaxDrawdown)}
                    />
                  </div>
                  <div className="mt-4 border-t border-white/[0.06] pt-3">
                    <div className="eyebrow mb-2">Worst drawdowns</div>
                    <DrawdownEpisodes series={data.series} />
                  </div>
                  <p className="mt-4 border-t border-white/[0.06] pt-3 text-[10px] leading-relaxed text-zinc-600">
                    Costs include 1bp slippage, T-bill financing and the synthetic fund fee where
                    applicable.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        <StrategySection strategy={strategy} data={data} />
        <ResearchSection strategy={strategy} />
      </main>
      <SiteFooter />
    </div>
  );
}

function LoadingPanels() {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="panel-soft h-[118px] animate-pulse bg-white/[0.02]" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
        <div className="panel h-[430px] animate-pulse bg-white/[0.015]" />
        <div className="panel h-[430px] animate-pulse bg-white/[0.015]" />
      </div>
    </div>
  );
}

function BookRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-white/[0.05] pb-2 last:border-0">
      <span className="text-[11px] text-zinc-500">{label}</span>
      <span className="tabular text-[12px] font-medium text-zinc-200">{value}</span>
    </div>
  );
}

function StrategySection({
  strategy,
  data,
}: {
  strategy: StrategyMeta;
  data: PerformanceData | null;
}) {
  const index = data?.params.index ?? "QQQ";
  const risk = data?.params.riskAsset ?? "TQQQ";
  const safe = data?.params.safeAsset ?? "BIL";
  const sma = data?.params.smaDays ?? 165;
  const volDays = data?.params.volDays ?? 20;
  const targetVol = data?.params.targetVol ?? 0;
  const leverage = data?.params.leverage ?? 3;
  const band = data?.params.rebalanceBand ?? 0.02;
  const hasTarget = targetVol > 0;

  const formula = hasTarget
    ? `sma  = SMA(${index} close, ${sma})
vol  = stdev(${index} daily returns, ${volDays})
       * sqrt(252)
trend = ${index} close > sma

if not trend:
    ${safe} = 1
else:
    exposure = min(${targetVol.toFixed(2)} / vol, ${leverage.toFixed(1)})
    if exposure <= 1:
        ${index} = exposure
        ${safe} = 1 - exposure
    else:
        ${risk} = (exposure - 1) / ${(leverage - 1).toFixed(1)}
        ${index}  = 1 - ${risk}`
    : `sma  = SMA(${index} close, ${sma})
trend = ${index} close > sma

if not trend:
    ${safe} = 1
else:
    ${risk} = 1`;

  return (
    <section id="strategy" className="scroll-mt-24 pt-16">
      <SectionHeading
        eyebrow="The rule"
        title="How it works"
        description={
          hasTarget
            ? "A trend filter plus a risk budget. The strategy does not forecast returns; it decides how much exposure to hold and when to step aside."
            : "A trend filter with fixed leverage. One decision per day, no forecast and no volatility target."
        }
      />

      <div>
        <div className="panel min-w-0 p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <RuleCard number="01" title="Trend" color="text-emerald-200">
              {index} above its {sma}-day average? Invested. Below it? {safe}.
            </RuleCard>
            <RuleCard number="02" title="Size" color="text-sky-200">
              {hasTarget
                ? `Target ${pct(targetVol, 0)} annualised volatility. Calm markets get up to ${leverage}x; rough markets get under 1x.`
                : `Full ${leverage}x exposure in an uptrend. No volatility target.`}
            </RuleCard>
            <RuleCard number="03" title="Timing" color="text-amber-200">
              Decide after the close. Fill at the next open. No same-bar look-ahead.
            </RuleCard>
            <RuleCard number="04" title="Churn" color="text-rose-200">
              Only rebalance when the book is more than {pct(band, 0)} of equity off target.
            </RuleCard>
          </div>

          <div className="mt-5 rounded-xl border border-white/[0.07] bg-black/30 p-4">
            <div className="mb-3 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
              <span className="eyebrow">Exact sizing</span>
              {data ? (
                <div className="flex flex-wrap gap-1.5">
                  <Pill>{sma}d SMA</Pill>
                  {hasTarget ? <Pill>{volDays}d vol</Pill> : null}
                  {hasTarget ? <Pill>{pct(targetVol, 0)} target</Pill> : null}
                  <Pill>{leverage}x cap</Pill>
                  <Pill>{pct(band, 0)} band</Pill>
                </div>
              ) : null}
            </div>
            <pre className="overflow-x-auto text-[10px] leading-6 text-zinc-400 sm:text-[11px]">
              <code>{formula}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

function RuleCard({
  number,
  title,
  color,
  children,
}: {
  number: string;
  title: string;
  color: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
      <div className="flex items-center justify-between">
        <span className={`text-[11px] font-medium uppercase tracking-[0.14em] ${color}`}>{title}</span>
        <span className="font-mono text-[10px] text-zinc-700">{number}</span>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{children}</p>
    </div>
  );
}

function ResearchSection({ strategy }: { strategy: StrategyMeta }) {
  const papers = strategy.papers.map((id) => PAPERS[id]);
  return (
    <section id="research" className="scroll-mt-24 pt-16">
      <SectionHeading
        eyebrow="Research"
        title="What the rule is built on"
        description={
          strategy.replication
            ? "The family is published. The exact 165-day / 40% / 2% settings are local calibrations, not copied from a paper."
            : "The family is published. The exact parameters are local calibrations, not copied from a paper."
        }
      />
      <div className={papers.length === 1 ? "grid gap-3" : "grid gap-3 sm:grid-cols-2"}>
        {papers.map((paper) => (
          <a
            key={paper.id}
            href={paper.url}
            target="_blank"
            rel="noreferrer"
            className="group rounded-xl border border-white/[0.07] bg-white/[0.015] p-4 transition hover:border-emerald-300/20 hover:bg-emerald-300/[0.03]"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">{paper.role}</span>
              <span className="text-[10px] text-zinc-700 transition group-hover:text-emerald-200/70">
                paper ↗
              </span>
            </div>
            <h3 className="mt-2 text-[14px] font-medium leading-snug text-zinc-200">{paper.title}</h3>
            <div className="mt-1 text-[11px] text-zinc-500">
              {paper.authors} · {paper.year}
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">{paper.body}</p>
          </a>
        ))}
      </div>

      <div
        className={`mt-4 grid gap-3 ${
          strategy.replication ? "lg:grid-cols-[1.2fr_1fr]" : "lg:grid-cols-1"
        }`}
      >
        {strategy.replication ? (
          <div className="panel-soft p-4">
            <div className="eyebrow mb-2">Closest independent replication</div>
            <p className="text-[12px] leading-relaxed text-zinc-400">
              <a
                className="text-emerald-200/90 underline decoration-emerald-200/20 underline-offset-2 hover:decoration-emerald-200/60"
                href={REPLICATION.url}
                target="_blank"
                rel="noreferrer"
              >
                {REPLICATION.label}
              </a>{" "}
              {REPLICATION.body}
            </p>
          </div>
        ) : null}
        <div className="panel-soft p-4">
          <div className="eyebrow mb-2">Counter-evidence</div>
          <p className="text-[12px] leading-relaxed text-zinc-400">
            {COUNTER_EVIDENCE.map((item, index) => (
              <span key={item.label}>
                <a
                  className="text-zinc-200 underline decoration-white/10 underline-offset-2"
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {item.label}
                </a>{" "}
                {item.body}
                {index < COUNTER_EVIDENCE.length - 1 ? " " : ""}
              </span>
            ))}
          </p>
        </div>
      </div>
      {strategy.researchMap ? (
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-zinc-600">
          <a
            className="transition hover:text-zinc-300"
            href={`${REPO}/blob/main/docs/nasdaq_leveraged_trend.md`}
            target="_blank"
            rel="noreferrer"
          >
            Full study ↗
          </a>
          <a
            className="transition hover:text-zinc-300"
            href={`${REPO}/blob/main/docs/live_readiness_audit.md`}
            target="_blank"
            rel="noreferrer"
          >
            Live-readiness audit ↗
          </a>
          <a
            className="transition hover:text-zinc-300"
            href={`${REPO}/blob/main/docs/more_trades_research.md`}
            target="_blank"
            rel="noreferrer"
          >
            More-trades research ↗
          </a>
        </div>
      ) : null}
    </section>
  );
}


