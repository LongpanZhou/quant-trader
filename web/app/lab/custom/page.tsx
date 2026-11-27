"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { PerformanceData } from "@/lib/types";
import { BENCHMARKS } from "@/lib/presets";
import {
  CUSTOM_MAX_SYMBOLS,
  CUSTOM_TICKER,
  CUSTOM_TIMEOUT_MS,
  type CustomWorkerRequest,
  type CustomWorkerResponse,
  type PricesPayload,
} from "@/lib/custom-engine";
import { isoRange, multiple, num, pct, points } from "@/lib/format";
import { EquityChart } from "@/components/equity-chart";
import { DrawdownChart } from "@/components/drawdown-chart";
import { YearlyChart } from "@/components/yearly-chart";
import { TradePanel } from "@/components/trade-panel";
import { RangeSelector, filterSeries, type SeriesRange } from "@/components/range-selector";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { Pill, StatCard } from "@/components/ui";

const inputClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-[#0b0d10] px-3 py-2 text-[12px] text-zinc-200 outline-none transition focus:border-emerald-300/40";

const TIMEFRAMES = [
  {
    value: "1d",
    label: "Daily",
    windows: [
      { label: "5 years", days: 1824 },
      { label: "10 years", days: 3650 },
      { label: "20 years", days: 7299 },
      { label: "26 years", days: 9500 },
    ],
  },
  {
    value: "1h",
    label: "1 hour",
    windows: [
      { label: "6 months", days: 182 },
      { label: "1 year", days: 365 },
      { label: "2 years", days: 729 },
    ],
  },
  {
    value: "15m",
    label: "15 minutes",
    windows: [
      { label: "10 days", days: 10 },
      { label: "30 days", days: 30 },
      { label: "59 days", days: 59 },
    ],
  },
  {
    value: "5m",
    label: "5 minutes",
    windows: [
      { label: "10 days", days: 10 },
      { label: "30 days", days: 30 },
      { label: "59 days", days: 59 },
    ],
  },
  {
    value: "1m",
    label: "1 minute",
    windows: [
      { label: "2 days", days: 2 },
      { label: "5 days", days: 5 },
      { label: "7 days", days: 7 },
    ],
  },
] as const;

type TimeframeValue = (typeof TIMEFRAMES)[number]["value"];

const SAMPLE_DAILY = `// decide(ctx) runs once per completed daily bar.
// Use only data through today; the engine fills at tomorrow's open.
// Return weights as fractions of equity. Cash is 1 - sum(weights).

function decide(ctx) {
  const sma = ctx.sma("QQQ", 165);
  if (sma === null) return { BIL: 1 };

  const aboveTrend = ctx.close("QQQ") > sma;
  if (!aboveTrend) return { BIL: 1 };

  const vol = ctx.vol("QQQ", 20);
  if (vol === null) return { BIL: 1 };

  // 40% annualised volatility target, capped at 3x exposure.
  const exposure = Math.min(0.4 / vol, 3);
  if (exposure <= 1) {
    return { QQQ: exposure, BIL: 1 - exposure };
  }

  // 1x QQQ plus 2x extra TQQQ gives 3x total exposure.
  const extra = (exposure - 1) / 2;
  return { QQQ: 1 - extra, TQQQ: extra };
}
`;

const SAMPLE_INTRADAY = `// Short intraday example: follow the 50-bar trend.
// Minute windows are short, so use short lookbacks.
function decide(ctx) {
  if (ctx.index < 50) return { BIL: 1 };
  const sma = ctx.sma("QQQ", 50);
  if (sma === null) return { BIL: 1 };
  return ctx.close("QQQ") > sma ? { QQQ: 1 } : { BIL: 1 };
}
`;

const SAMPLES = {
  daily: { label: "Daily trend", code: SAMPLE_DAILY },
  intraday: { label: "Intraday 50-bar trend", code: SAMPLE_INTRADAY },
} as const;

type SampleId = keyof typeof SAMPLES;

type Meta = {
  bars: number;
  elapsedMs: number;
  cache: "hit" | "miss" | "stale";
  fetchedAt?: string;
  interval: string;
  from: string;
  to: string;
  warnings: string[];
};

export default function CustomLabPage() {
  const [symbolsInput, setSymbolsInput] = useState("QQQ,TQQQ,BIL");
  const [benchmarkInput, setBenchmarkInput] = useState("QQQ");
  const [timeframe, setTimeframe] = useState<TimeframeValue>("1d");
  const [days, setDays] = useState(3650);
  const [sampleId, setSampleId] = useState<SampleId>("daily");
  const [slippage, setSlippage] = useState(1);
  const [refresh, setRefresh] = useState(false);
  const [code, setCode] = useState(SAMPLE_DAILY);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [priceNote, setPriceNote] = useState<string | null>(null);
  const [data, setData] = useState<PerformanceData | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [range, setRange] = useState<SeriesRange>("all");

  const workerRef = useRef<Worker | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);
  const priceCacheRef = useRef<{ key: string; payload: PricesPayload } | null>(null);

  const activeTimeframe = TIMEFRAMES.find((item) => item.value === timeframe) ?? TIMEFRAMES[0];
  const chooseTimeframe = (next: TimeframeValue) => {
    setTimeframe(next);
    const config = TIMEFRAMES.find((item) => item.value === next) ?? TIMEFRAMES[0];
    setDays(config.windows[0].days);
    // Only swap the built-in sample if the editor still holds that sample
    // unchanged; never overwrite code the user has edited.
    if (code === SAMPLES[sampleId].code) {
      const target: SampleId = next === "1d" ? "daily" : "intraday";
      setSampleId(target);
      setCode(SAMPLES[target].code);
    }
  };
  const chooseSample = (next: SampleId) => {
    setSampleId(next);
    setCode(SAMPLES[next].code);
  };

  useEffect(
    () => () => {
      runIdRef.current += 1;
      abortRef.current?.abort();
      workerRef.current?.terminate();
      if (timeoutRef.current != null) window.clearTimeout(timeoutRef.current);
    },
    [],
  );

  const cancel = () => {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    workerRef.current?.terminate();
    workerRef.current = null;
    if (timeoutRef.current != null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setRunning(false);
    setError("Run cancelled. The backtest was stopped.");
  };

  const run = async () => {
    if (running) return;
    const id = ++runIdRef.current;
    setRunning(true);
    setError(null);
    setPriceNote(null);
    setData(null);
    setMeta(null);

    try {
      const symbols = Array.from(
        new Set(
          symbolsInput
            .split(",")
            .map((symbol) => symbol.trim().toUpperCase())
            .filter(Boolean),
        ),
      );
      if (symbols.length === 0) throw new Error("Enter at least one symbol.");
      if (symbols.length > CUSTOM_MAX_SYMBOLS) {
        throw new Error(`Use at most ${CUSTOM_MAX_SYMBOLS} symbols.`);
      }
      const invalid = symbols.find((symbol) => !CUSTOM_TICKER.test(symbol));
      if (invalid) throw new Error(`'${invalid}' is not a plain ticker.`);

      const benchmark = benchmarkInput.trim().toUpperCase();
      if (!CUSTOM_TICKER.test(benchmark)) {
        throw new Error("Benchmark must be a plain ticker such as QQQ, SPY or ^NDX.");
      }

      const slippageBps = Number.isFinite(slippage)
        ? Math.min(100, Math.max(0, Math.round(slippage)))
        : 1;
      const key = `${symbols.join(",")}|${benchmark}|${timeframe}|${days}`;

      let cached = priceCacheRef.current;
      if (!cached || cached.key !== key || refresh) {
        const params = new URLSearchParams({
          symbols: symbols.join(","),
          benchmark,
          interval: timeframe,
          days: String(days),
        });
        if (refresh) params.set("refresh", "1");

        const controller = new AbortController();
        abortRef.current = controller;
        const response = await fetch(`/api/prices?${params.toString()}`, {
          signal: controller.signal,
        });
        if (id !== runIdRef.current) return;
        const payload = (await response.json()) as PricesPayload & { error?: string };
        if (!response.ok || !payload.symbols) {
          throw new Error(payload.error ?? "Could not download prices from Yahoo Finance.");
        }
        cached = { key, payload };
        priceCacheRef.current = cached;
        abortRef.current = null;
      }

      if (id !== runIdRef.current) return;
      if (cached.payload.warning) setPriceNote(cached.payload.warning);
      else if (cached.payload.stale) {
        setPriceNote("Yahoo Finance was unavailable; this run uses the stale local price cache.");
      }

      const worker = new Worker(new URL("./engine.worker.ts", import.meta.url));
      if (id !== runIdRef.current) {
        worker.terminate();
        return;
      }
      workerRef.current = worker;

      timeoutRef.current = window.setTimeout(() => {
        if (id !== runIdRef.current) return;
        worker.terminate();
        workerRef.current = null;
        timeoutRef.current = null;
        setRunning(false);
        setError(
          `Stopped after ${CUSTOM_TIMEOUT_MS / 1000}s. Check decide(ctx) for an infinite loop or a very slow per-bar calculation.`,
        );
      }, CUSTOM_TIMEOUT_MS);

      worker.onmessage = (event: MessageEvent<CustomWorkerResponse>) => {
        if (id !== runIdRef.current) return;
        if (timeoutRef.current != null) {
          window.clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        worker.terminate();
        workerRef.current = null;
        if (event.data.type === "done") {
          const result = event.data.result;
          setData(result.data);
          setMeta({
            bars: result.bars,
            elapsedMs: result.elapsedMs,
            cache: cached.payload.cache ?? "miss",
            fetchedAt: cached.payload.fetchedAt,
            interval: cached.payload.interval ?? timeframe,
            from: cached.payload.from,
            to: cached.payload.to,
            warnings: result.warnings,
          });
          setRange("all");
        } else {
          setError(event.data.error);
        }
        setRunning(false);
      };

      worker.onerror = (event) => {
        if (id !== runIdRef.current) return;
        if (timeoutRef.current != null) {
          window.clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        worker.terminate();
        workerRef.current = null;
        setRunning(false);
        setError(`Run error: ${event.message}`);
      };

      const request: CustomWorkerRequest = {
        type: "run",
        input: {
          prices: cached.payload,
          symbols,
          benchmark,
          slippageBps,
          code,
          timeframe,
        },
      };
      worker.postMessage(request);
    } catch (reason) {
      if (id !== runIdRef.current) return;
      abortRef.current = null;
      if (timeoutRef.current != null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      workerRef.current?.terminate();
      workerRef.current = null;
      setRunning(false);
      setError(reason instanceof Error ? reason.message : "Custom backtest failed.");
    }
  };

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
  // Annualising a two-day intraday run produces absurd CAGR figures. Show the
  // actual window return for intraday bars and keep CAGR for the daily lab.
  const intraday = Boolean(data && data.timeframe !== "1d");
  const headlineReturn = data
    ? intraday
      ? data.metrics.totalReturn
      : data.metrics.cagr
    : 0;
  const headlineBenchmark = data
    ? intraday
      ? data.metrics.buyHoldReturn
      : (data.metrics.benchmarkCagr ?? 0)
    : 0;
  const headlineExcess = intraday
    ? headlineReturn - headlineBenchmark
    : (data?.metrics.excess ?? 0);

  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="lab" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="mb-4 flex flex-wrap gap-2">
                <Pill tone="green">Custom strategy</Pill>
                <Pill>Runs locally</Pill>
                <Pill tone="blue">Yahoo price bars</Pill>
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                Write your
                <br />
                <span className="text-emerald-200">own rules.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[14px] leading-relaxed text-zinc-400">
                Write a strategy in plain JavaScript and test it on daily or intraday bars. It runs
                locally in your browser, fills at the next open, and uses Yahoo price bars.
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-4 text-[11px] text-zinc-500">
                <a href="/lab" className="transition hover:text-zinc-200">
                  ← Back to the backtest lab
                </a>
                <a href="#data" className="transition hover:text-zinc-200">
                  Data & limits ↓
                </a>
              </div>
            </div>
            <div className="panel-soft max-w-sm p-4 text-[11px] leading-relaxed text-zinc-500">
              <div className="eyebrow mb-2">One decision per bar</div>
              Decide after the bar closes, fill at the next open, charge slippage, hold the
              remainder in cash. No look-ahead. This is a research tool, not a broker.
            </div>
          </div>
        </section>

        <section id="workspace" className="scroll-mt-24 pt-10">
          <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
            <div className="panel min-w-0 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="eyebrow">Strategy code</div>
                  <h2 className="mt-1 text-lg font-semibold text-zinc-100">
                    define <span className="font-mono text-[15px] text-emerald-200">decide(ctx)</span>
                  </h2>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={sampleId}
                    onChange={(event) => chooseSample(event.target.value as SampleId)}
                    className="rounded-md border border-white/10 bg-[#0b0d10] px-2 py-1 text-[10px] text-zinc-300 outline-none"
                    aria-label="Load a strategy sample"
                  >
                    {Object.entries(SAMPLES).map(([id, sample]) => (
                      <option key={id} value={id}>
                        {sample.label}
                      </option>
                    ))}
                  </select>
                  <Pill tone="green">Runs in your browser</Pill>
                </div>
              </div>

              <textarea
                value={code}
                onChange={(event) => setCode(event.target.value)}
                spellCheck={false}
                autoCapitalize="off"
                autoCorrect="off"
                className="mt-4 h-[440px] w-full resize-y rounded-xl border border-white/10 bg-[#07090b] p-4 font-mono text-[11px] leading-5 text-zinc-300 outline-none transition focus:border-emerald-300/40"
              />

              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <ContextRow code="ctx.date" body="bar timestamp; includes time on intraday" />
                <ContextRow code="ctx.index" body="bar index in the aligned history" />
                <ContextRow code='ctx.close("QQQ")' body="adjusted close at bar i" />
                <ContextRow code='ctx.open("QQQ")' body="adjusted open at bar i" />
                <ContextRow code='ctx.sma("QQQ", 165)' body="mean close, null until enough bars" />
                <ContextRow code='ctx.vol("QQQ", 20)' body="annualised stdev of bar returns" />
                <ContextRow code='ctx.returns("QQQ", 20)' body="array of recent bar returns" />
                <ContextRow code='return { QQQ: 0.5, BIL: 0.5 }' body="weights; cash is 1 - sum" />
              </div>

              <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
                The daily sample expects QQQ, TQQQ and BIL; the intraday sample uses QQQ and BIL.
                Weights must be finite, non-negative and sum to 1 or less. Shorting, margin and
                borrowed cash are not supported. Plain synchronous JavaScript only: no imports or
                async decide functions. The code runs with the page&apos;s browser permissions, so
                only run code you trust. A run is stopped after {CUSTOM_TIMEOUT_MS / 1000} seconds.
              </p>
            </div>

            <div className="panel h-fit p-5">
              <div className="eyebrow mb-4">Inputs</div>

              <label className="block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                Symbols
                <input
                  value={symbolsInput}
                  onChange={(event) => setSymbolsInput(event.target.value)}
                  placeholder="QQQ,TQQQ,BIL"
                  spellCheck={false}
                  className={`${inputClass} font-mono`}
                />
              </label>

              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                  Timeframe
                  <select
                    value={timeframe}
                    onChange={(event) => chooseTimeframe(event.target.value as TimeframeValue)}
                    className={inputClass}
                  >
                    {TIMEFRAMES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                  Window
                  <select
                    value={days}
                    onChange={(event) => setDays(Number(event.target.value))}
                    className={inputClass}
                  >
                    {activeTimeframe.windows.map((window) => (
                      <option key={window.days} value={window.days}>
                        {window.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="mt-3 block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                Benchmark
                <input
                  value={benchmarkInput}
                  onChange={(event) => setBenchmarkInput(event.target.value)}
                  list="custom-benchmarks"
                  spellCheck={false}
                  className={`${inputClass} font-mono`}
                />
                <datalist id="custom-benchmarks">
                  {BENCHMARKS.map((item) => (
                    <option key={item.value} value={item.value} />
                  ))}
                </datalist>
              </label>

              <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
                Yahoo limits: 1m ≤7 days, 5m/15m ≤59 days, 1h ≤2 years. The benchmark is always
                downloaded for comparison; only symbols in the list above can receive weights.
              </p>

              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-[10px] uppercase tracking-[0.12em] text-zinc-600">
                  Slippage bps
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={slippage}
                    onChange={(event) => setSlippage(Number(event.target.value))}
                    className={inputClass}
                  />
                </label>
                <label className="flex items-end gap-2 pb-2 text-[11px] text-zinc-500">
                  <input
                    type="checkbox"
                    checked={refresh}
                    onChange={(event) => setRefresh(event.target.checked)}
                    className="h-3.5 w-3.5 rounded border-white/20 bg-black/30"
                  />
                  Ignore price cache
                </label>
              </div>

              <div className="mt-5 flex gap-2">
                <button
                  onClick={() => void run()}
                  disabled={running}
                  className="flex-1 rounded-lg bg-emerald-300 px-4 py-2.5 text-[12px] font-semibold text-[#07110a] transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60"
                >
                  {running ? "Running..." : "Run strategy"}
                </button>
                {running ? (
                  <button
                    onClick={cancel}
                    className="rounded-lg border border-white/10 px-3 py-2.5 text-[11px] text-zinc-400 transition hover:border-rose-300/30 hover:text-rose-200"
                  >
                    Stop
                  </button>
                ) : null}
              </div>

              <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
                The first run downloads bars for the selected timeframe from Yahoo Finance and can
                take a few seconds.
                Price data is cached on this machine for 6 hours; each code change reruns the
                backtest locally. The strategy code is not sent to the server.
              </p>

              {error ? (
                <div className="mt-3 max-h-56 overflow-auto rounded-lg border border-rose-300/20 bg-rose-300/[0.05] p-3 text-[10px] leading-relaxed text-rose-200">
                  {error}
                </div>
              ) : null}

              {priceNote ? (
                <div className="mt-3 rounded-lg border border-amber-300/20 bg-amber-300/[0.05] p-3 text-[10px] leading-relaxed text-amber-200">
                  {priceNote}
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section id="results" className="scroll-mt-24 pt-8">
          {!data ? (
            <div className="panel flex min-h-[260px] flex-col items-center justify-center p-8 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200">
                {"</>"}
              </div>
              <div className="text-[14px] font-medium text-zinc-300">No custom run yet</div>
              <p className="mt-2 max-w-md text-[11px] leading-relaxed text-zinc-600">
                Edit the code or parameters, then run. You will get the same equity, drawdown and
                trade panels as the shipped strategies, plus yearly bars for daily runs, the
                aligned date range and the price cache status.
              </p>
            </div>
          ) : (
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] text-zinc-500">
                    {data.name} · {isoRange(data.start, data.end)} ·{" "}
                    {TIMEFRAMES.find((item) => item.value === data.timeframe)?.label ??
                      data.timeframe}
                  </div>
                  <div className="mt-1 text-[10px] text-zinc-600">
                    {meta ? `${num(meta.bars)} bars · ran in ${meta.elapsedMs} ms locally` : null}
                    {meta
                      ? ` · prices ${meta.cache === "hit" ? "from local cache" : meta.cache === "stale" ? "from stale local cache" : "downloaded"}`
                      : null}
                    {meta?.fetchedAt
                      ? ` · fetched ${new Date(meta.fetchedAt).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}`
                      : null}
                  </div>
                </div>
                <RangeSelector
                  value={range}
                  onChange={setRange}
                  series={viewSeries}
                  name={data.name}
                  benchmark={data.benchmark}
                  intraday={data.timeframe !== "1d"}
                  suffix={data.timeframe}
                />
              </div>

              {meta?.warnings.length ? (
                <div className="mb-3 rounded-lg border border-amber-300/15 bg-amber-300/[0.04] px-3 py-2 text-[10px] leading-relaxed text-amber-200/90">
                  {meta.warnings.join(" · ")}
                </div>
              ) : null}

              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
                <StatCard
                  label={intraday ? "Return" : "CAGR"}
                  value={pct(headlineReturn)}
                  sub={
                    intraday
                      ? `${data.benchmark} ${pct(headlineBenchmark)} over window`
                      : `${data.benchmark} ${pct(headlineBenchmark)} / yr`
                  }
                  tone="green"
                />
                <StatCard
                  label={`Excess vs ${data.benchmark}`}
                  value={points(headlineExcess)}
                  sub={intraday ? "over this window, after slippage" : "per year, after slippage"}
                  tone="green"
                />
                <StatCard
                  label="Max drawdown"
                  value={pct(-data.metrics.maxDrawdown)}
                  sub={`${data.benchmark} ${
                    data.metrics.benchmarkMaxDrawdown == null
                      ? "—"
                      : pct(-data.metrics.benchmarkMaxDrawdown)
                  }`}
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

              <div className="panel mt-4 min-w-0 p-5">
                <EquityChart
                  series={viewSeries}
                  start={viewSeries[0]?.date ?? data.start}
                  end={data.end}
                  benchmark={data.benchmark}
                  accent="#9ae6a5"
                  timeframe={data.timeframe}
                />
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
                <div className="panel min-w-0 p-5">
                  <DrawdownChart
                    series={viewSeries}
                    strategyMax={maxDrawdown}
                    qqqMax={benchmarkDrawdown}
                    benchmark={data.benchmark}
                    timeframe={data.timeframe}
                  />
                </div>
                <div className="panel min-w-0 p-5">
                  <TradePanel metrics={data.metrics} />
                </div>
              </div>
              {data.timeframe === "1d" ? (
                <div className="panel mt-4 min-w-0 p-5">
                  <YearlyChart yearly={data.yearly} benchmark={data.benchmark} />
                </div>
              ) : null}
              <p className="mt-3 text-[10px] leading-relaxed text-zinc-600">
                Execution model: completed bars of the selected timeframe, Yahoo prices (adjusted
                where available), next-bar-open fills, slippage in basis points, long-only weights,
                fractional shares, cash at 0%. It rebalances to the returned weights every bar they
                change; add a band in your code if you want less churn. “Round trips” counts
                realized sells using average cost, including partial rebalance sells. Sharpe,
                Sortino and volatility are annualised from bar returns, so short intraday windows
                are noisy.
              </p>
            </div>
          )}
        </section>

        <section id="data" className="scroll-mt-24 pt-16">
          <div className="eyebrow mb-2">Data & limits</div>
          <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
            What this local dataset does and does not contain
          </h2>
          <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-zinc-500">
            The custom lab is price-only. It can test rules on daily or intraday bars of liquid
            tickers, but it is not a point-in-time institutional dataset. The limitations below are
            real boundaries of the tool, not footnotes.
          </p>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DataCard title="Prices and corporate actions" tone="green">
              Yahoo Finance bars. On daily bars the adjusted close embeds splits and dividends;
              adjusted open/high/low are reconstructed by scaling each raw bar by adj close ÷
              close, because Yahoo does not publish an official adjusted OHLC series. Intraday bars
              use Yahoo&apos;s raw OHLC when an adjusted close is not published, and an incomplete
              intraday bar is dropped. Yahoo limits history to 7 days at 1m, 59 days at 5m/15m and
              2 years at 1h.
            </DataCard>
            <DataCard title="Delisting and survivorship" tone="amber">
              Delisting is not modeled for arbitrary stock universes. The engine aligns on the
              intersection of available bars; if a ticker stops trading, the run simply ends at the
              last common bar. There is no terminal delisting return and no survivorship-free
              universe. A point-in-time delisting feed would be required to model that honestly.
            </DataCard>
            <DataCard title="Financial statements" tone="red">
              SEC/EDGAR financial statements are not in the local dataset. Revenue, earnings,
              balance-sheet and filing-date inputs are not available here, and this page does not
              fabricate them. Fundamentals need a separate data layer, CIK mapping, point-in-time
              filing dates and a cache before they can be a strategy input.
            </DataCard>
            <DataCard title="Execution and costs" tone="blue">
              One decision per completed bar, filled at the next bar&apos;s open. The engine
              rebalances to the returned weights whenever they change, so add a no-trade band in
              your own code if you want less churn. Slippage is charged on traded notional. No
              commissions, taxes, bid/ask spread beyond slippage, borrow costs, margin interest,
              shorting or corporate-action timing. Cash earns 0%. Intraday results show the window
              return rather than an annualised CAGR.
            </DataCard>
            <DataCard title="Where the code runs" tone="green">
              Your code runs locally in the browser. Only ticker symbols are sent to the local price
              route; the strategy source and the backtest result stay in the browser. A 30-second
              timeout stops runaway loops.
            </DataCard>
            <DataCard title="What is reproducible" tone="blue">
              The run pins the aligned start/end timestamps and the symbol set. Yahoo history can
              be revised, and the local cache expires after 6 hours. Save the CSV if you need an
              exact copy of a result.
            </DataCard>
          </div>

          <div className="panel-soft mt-4 flex flex-col gap-2 p-4 text-[11px] leading-relaxed text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <span>Want to test a preset strategy instead? Use the Backtest Lab.</span>
            <a className="shrink-0 text-zinc-300 transition hover:text-emerald-200" href="/lab">
              Open the backtest lab →
            </a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function ContextRow({ code, body }: { code: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-white/[0.06] bg-white/[0.015] px-3 py-2">
      <code className="font-mono text-[10px] text-emerald-200/80">{code}</code>
      <span className="text-[10px] leading-relaxed text-zinc-600">{body}</span>
    </div>
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
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-300">
        {title}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{children}</p>
    </div>
  );
}
