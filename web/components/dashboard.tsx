"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { PerformanceData, WindowId } from "@/lib/types";
import { WINDOWS } from "@/lib/types";
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
import { LegendDot, LogoMark, Pill, SectionHeading, StatCard } from "./ui";

const REPO = "https://github.com/LongpanZhou/quant-trader";

export function Dashboard() {
  const [windowId, setWindowId] = useState<WindowId>("5y");
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("window");
    if (requested && WINDOWS.some((window) => window.id === requested)) {
      setWindowId(requested as WindowId);
    }
  }, []);

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
    fetch(`/data/${windowId}.json`, { signal: controller.signal })
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
  }, [windowId]);

  const selected = WINDOWS.find((window) => window.id === windowId)!;

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#08090b]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-5 lg:px-8">
          <a href="#top" className="flex items-center gap-2.5">
            <LogoMark className="h-7 w-7" />
            <span className="text-[13px] font-semibold tracking-[-0.01em] text-zinc-200">
              quant-trader
              <span className="ml-2 hidden text-[11px] font-normal text-zinc-600 sm:inline">
                research dashboard
              </span>
            </span>
          </a>
          <nav className="hidden items-center gap-6 text-[11px] text-zinc-500 md:flex">
            <a className="transition hover:text-zinc-200" href="#performance">Performance</a>
            <a className="transition hover:text-zinc-200" href="#trades">Trades</a>
            <a className="transition hover:text-zinc-200" href="#strategy">Strategy</a>
            <a className="transition hover:text-zinc-200" href="#research">Research</a>
          </nav>
          <a
            href={REPO}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.14em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
          >
            GitHub
            <span aria-hidden="true">↗</span>
          </a>
        </div>
      </header>

      <main id="top" className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Pill tone="green">Paper research</Pill>
                <Pill>Long-only · daily</Pill>
                <Pill tone="blue">QQQ / TQQQ / BIL</Pill>
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                Nasdaq leveraged
                <br />
                <span className="text-emerald-200">trend.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[14px] leading-relaxed text-zinc-400">
                Own a volatility-sized mix of QQQ and TQQQ while the Nasdaq-100 is above its
                165-day average. When the trend breaks, move to T-bills. Built as a research
                instrument, traded on paper only.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
                Data through 20 Nov 2026
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
              title="The record, across four horizons"
              description="Same rule, no re-tuning. The 20- and 26-year runs use a synthetic 3x QQQ series before TQQQ existed, and after 2010 to keep one consistent path."
            />
            <div className="grid w-full min-w-0 grid-cols-2 gap-2 sm:grid-cols-4 lg:w-auto">
              {WINDOWS.map((window) => (
                <button
                  key={window.id}
                  onClick={() => chooseWindow(window.id)}
                  aria-pressed={windowId === window.id}
                  className={`group min-w-0 rounded-xl border px-3.5 py-2.5 text-left transition ${
                    windowId === window.id
                      ? "border-emerald-300/30 bg-emerald-300/[0.08]"
                      : "border-white/10 bg-white/[0.02] hover:border-white/20"
                  }`}
                >
                  <div
                    className={`text-[12px] font-medium ${
                      windowId === window.id ? "text-emerald-100" : "text-zinc-300"
                    }`}
                  >
                    {window.label}
                  </div>
                  <div className="text-[10px] text-zinc-600">
                    {window.years}
                    {window.note ? ` · ${window.note}` : ""}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {error ? (
            <div className="panel mt-4 p-6 text-sm text-rose-200">{error}</div>
          ) : !data ? (
            <LoadingPanels />
          ) : (
            <div className={`transition-opacity duration-300 ${loading ? "opacity-60" : "opacity-100"}`}>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div className="text-[11px] text-zinc-500">
                  {selected.label} · {isoRange(data.start, data.end)}
                </div>
                <div className="flex items-center gap-3">
                  <LegendDot color="#9ae6a5" label="Strategy" />
                  <LegendDot color="#71717a" label="QQQ benchmark" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
                <StatCard
                  label="CAGR"
                  value={pct(data.metrics.cagr)}
                  sub={`QQQ ${pct(data.metrics.benchmarkCagr)} / yr`}
                  tone="green"
                />
                <StatCard
                  label="Excess vs QQQ"
                  value={points(data.metrics.excess)}
                  sub="per year, after costs"
                  tone="green"
                />
                <StatCard
                  label="Max drawdown"
                  value={pct(-data.metrics.maxDrawdown)}
                  sub={`QQQ ${pct(data.metrics.benchmarkMaxDrawdown)}`}
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
                  <EquityChart series={data.series} start={data.start} end={data.end} />
                </div>
                <div id="trades" className="panel scroll-mt-24 p-5">
                  <TradePanel metrics={data.metrics} />
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="panel min-w-0 p-5">
                  <DrawdownChart
                    series={data.series}
                    strategyMax={data.metrics.maxDrawdown}
                    qqqMax={data.metrics.benchmarkMaxDrawdown}
                  />
                </div>
                <div className="panel min-w-0 p-5">
                  <YearlyChart yearly={data.yearly} />
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
                      label="QQQ max drawdown"
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

        <StrategySection data={data} />
        <ResearchSection />
      </main>

      <footer className="relative border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-3 px-5 py-8 text-[11px] text-zinc-600 sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <div>
            <span className="text-zinc-400">quant-trader</span> · paper trading only · not investment
            advice
          </div>
          <div className="flex items-center gap-4">
            <span>Data: Yahoo Finance</span>
            <a className="transition hover:text-zinc-300" href={REPO} target="_blank" rel="noreferrer">
              Source ↗
            </a>
          </div>
        </div>
      </footer>
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

const CODE_MAP = [
  {
    file: "src/strategy.rs",
    title: "The signal",
    body: "LeveragedIndex computes the 165-day SMA and 20-day volatility, then blend_exposure splits the target between QQQ and TQQQ.",
  },
  {
    file: "src/backtest.rs",
    title: "The test",
    body: "Loads adjusted daily bars, builds the synthetic 3x series, runs the event loop with next-open fills and writes the JSON behind this page.",
  },
  {
    file: "src/engine.rs",
    title: "The live loop",
    body: "Once per completed bar: fetch data, compute targets, apply the 2% band, send paper orders. Retries, stale data and splits are handled here.",
  },
  {
    file: "src/config.rs",
    title: "The config",
    body: "Parses config.toml, validates parameters, and checks that QQQ, TQQQ and BIL are present before a run starts.",
  },
];

function StrategySection({ data }: { data: PerformanceData | null }) {
  return (
    <section id="strategy" className="scroll-mt-24 pt-16">
      <SectionHeading
        eyebrow="Under the hood"
        title="A simple rule, implemented literally"
        description="The strategy is a trend filter plus a risk budget. The code does not forecast returns; it decides how much Nasdaq exposure to hold and when to step aside."
      />

      <div className="grid gap-4 lg:grid-cols-[1.05fr_1fr]">
        <div className="panel min-w-0 p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <RuleCard number="01" title="Trend" color="text-emerald-200">
              QQQ above its 165-day average? Invested. Below it? BIL.
            </RuleCard>
            <RuleCard number="02" title="Size" color="text-sky-200">
              Target 40% annualised volatility. Calm markets get up to 3x; rough markets get under
              1x.
            </RuleCard>
            <RuleCard number="03" title="Timing" color="text-amber-200">
              Decide after the close. Fill at the next open. No same-bar look-ahead.
            </RuleCard>
            <RuleCard number="04" title="Churn" color="text-rose-200">
              Only rebalance when the book is more than 2% of equity off target.
            </RuleCard>
          </div>

          <div className="mt-5 rounded-xl border border-white/[0.07] bg-black/30 p-4">
            <div className="mb-3 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
              <span className="eyebrow">Exact sizing</span>
              {data ? (
                <div className="flex flex-wrap gap-1.5">
                  <Pill>{data.params.smaDays}d SMA</Pill>
                  <Pill>{data.params.volDays}d vol</Pill>
                  <Pill>{pct(data.params.targetVol ?? 0, 0)} target</Pill>
                  <Pill>{data.params.leverage}x cap</Pill>
                </div>
              ) : null}
            </div>
            <pre className="overflow-x-auto text-[10px] leading-6 text-zinc-400 sm:text-[11px]">
              <code>{`sma  = SMA(QQQ close, 165)
vol  = stdev(QQQ daily returns, 20)
       * sqrt(252)
trend = QQQ close > sma

if not trend:
    BIL = 1
else:
    exposure = min(0.40 / vol, 3.0)
    if exposure <= 1:
        QQQ = exposure
        BIL = 1 - exposure
    else:
        TQQQ = (exposure - 1) / 2
        QQQ  = 1 - TQQQ`}</code>
            </pre>
          </div>
        </div>

        <div className="panel min-w-0 p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="eyebrow">Code map</div>
              <h3 className="mt-1 text-lg font-semibold text-zinc-100">Where it lives</h3>
            </div>
            <Pill tone="green">Rust</Pill>
          </div>
          <div className="space-y-3">
            {CODE_MAP.map((item) => (
              <div
                key={item.file}
                className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3.5"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-[11px] text-emerald-200/80">{item.file}</span>
                  <span className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                    {item.title}
                  </span>
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">{item.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2 text-[10px] text-zinc-600">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-300/70" />
            JSON is generated by <span className="font-mono text-zinc-500">--json</span> and served
            statically.
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

const PAPERS = [
  {
    authors: "Gayed & Bilello",
    year: "2016",
    title: "Leverage for the Long Run",
    role: "Trend + leverage",
    body: "Hold leveraged equity while the index is above its long average; move to T-bills below it.",
    href: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701",
  },
  {
    authors: "Faber",
    year: "2007",
    title: "A Quantitative Approach to Tactical Asset Allocation",
    role: "The moving-average filter",
    body: "The 10-month SMA rule: own an asset above its average, sit in T-bills below it.",
    href: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461",
  },
  {
    authors: "Moreira & Muir",
    year: "2017",
    title: "Volatility-Managed Portfolios",
    role: "The risk budget",
    body: "Scale exposure by trailing realised variance instead of holding a fixed leverage all the time.",
    href: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431",
  },
  {
    authors: "Zarattini & Antonacci",
    year: "2024",
    title: "A Century of Profitable Industry Trends",
    role: "Volatility-targeted trend",
    body: "Per-asset volatility targeting with trend filters across a century of industry portfolios.",
    href: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230",
  },
];

function ResearchSection() {
  return (
    <section id="research" className="scroll-mt-24 pt-16">
      <SectionHeading
        eyebrow="Research"
        title="What the rule is built on"
        description="The family is published. The exact 165-day / 40% / 2% settings are local calibrations, not copied from a paper."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {PAPERS.map((paper) => (
          <a
            key={paper.href}
            href={paper.href}
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

      <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_1fr]">
        <div className="panel-soft p-4">
          <div className="eyebrow mb-2">Closest independent replication</div>
          <p className="text-[12px] leading-relaxed text-zinc-400">
            <a
              className="text-emerald-200/90 underline decoration-emerald-200/20 underline-offset-2 hover:decoration-emerald-200/60"
              href="https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf"
              target="_blank"
              rel="noreferrer"
            >
              Nygård & Liukko (2026)
            </a>{" "}
            test a 3x Nasdaq-100 rule with a 200-day filter and an implied-volatility filter over
            2001-2026: about <span className="text-zinc-200">22% a year</span> with a{" "}
            <span className="text-zinc-200">-64.8%</span> drawdown. That is roughly buy-and-hold&apos;s
            21% return with a much smaller drawdown — not a new source of alpha.
          </p>
        </div>
        <div className="panel-soft p-4">
          <div className="eyebrow mb-2">Counter-evidence</div>
          <p className="text-[12px] leading-relaxed text-zinc-400">
            <a
              className="text-zinc-200 underline decoration-white/10 underline-offset-2"
              href="https://www.lehigh.edu/~xuy219/research/COWY.pdf"
              target="_blank"
              rel="noreferrer"
            >
              Cederburg et al. (2020)
            </a>{" "}
            find volatility management does not systematically beat unmanaged portfolios out of
            sample.{" "}
            <a
              className="text-zinc-200 underline decoration-white/10 underline-offset-2"
              href="https://arxiv.org/abs/2412.14361"
              target="_blank"
              rel="noreferrer"
            >
              Massaad et al. (2024)
            </a>{" "}
            find published trend results weaken under robust testing.
          </p>
        </div>
      </div>
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
    </section>
  );
}


