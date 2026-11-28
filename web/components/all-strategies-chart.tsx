"use client";

import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
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

type Curve = {
  id: string;
  name: string;
  color: string;
  values: (number | null)[];
};

type Metric = {
  id: string;
  name: string;
  cagr: number;
  dd: number;
  sharpe: number;
  benchmark: boolean;
  family?: string;
  family_winner?: boolean;
};

type Payload = {
  generated: string;
  start: string;
  end: string;
  window: string;
  dates: string[];
  series: Curve[];
  metrics: Metric[];
  note?: string;
};

function CompareTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const rows = [...payload]
    .filter((item: any) => item.value != null)
    .sort((a: any, b: any) => b.value - a.value);
  return (
    <div className="min-w-[220px] rounded-xl border border-white/10 bg-[#0b0d10]/95 p-3 text-[11px] shadow-2xl backdrop-blur">
      <div className="mb-2 text-zinc-500">{formatSeriesDate(String(label))}</div>
      <div className="space-y-1.5">
        {rows.map((item: any) => (
          <div key={item.dataKey} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-zinc-400">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: item.color ?? item.stroke }}
              />
              {item.name}
            </span>
            <span className="font-medium text-zinc-100">${Number(item.value).toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScatterPlot({
  metrics,
  colors,
  hoveredId,
  onHoverId,
}: {
  metrics: Metric[];
  colors: Record<string, string>;
  hoveredId: string | null;
  onHoverId: (id: string | null) => void;
}) {
  const xField = "dd";
  const yField = "cagr";
  const width = 620;
  const height = 340;
  const left = 50;
  const right = 18;
  const top = 18;
  const bottom = 38;
  const DEFAULT = { x0: 0, x1: 0.9, y0: -0.1, y1: 0.8 };
  const [view, setView] = useState(DEFAULT);
  const [hover, setHover] = useState<{ metric: Metric; x: number; y: number } | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const dragRef = useRef<
    { x0: number; x1: number; y0: number; y1: number; mx: number; my: number } | null
  >(null);

  const clampView = (next: { x0: number; x1: number; y0: number; y1: number }) => {
    const minSpan = 0.04;
    const spanX = Math.min(0.9, Math.max(minSpan, next.x1 - next.x0));
    const spanY = Math.min(0.9, Math.max(minSpan, next.y1 - next.y0));
    const x0 = Math.min(Math.max(0, next.x0), 0.9 - spanX);
    const y0 = Math.min(Math.max(-0.1, next.y0), 0.8 - spanY);
    return { x0, x1: x0 + spanX, y0, y1: y0 + spanY };
  };

  const sx = (value: number) =>
    left + ((value - view.x0) / (view.x1 - view.x0)) * (width - left - right);
  const sy = (value: number) =>
    height - bottom - ((value - view.y0) / (view.y1 - view.y0)) * (height - top - bottom);
  const xTicks = Array.from({ length: 5 }, (_, i) => view.x0 + (i / 4) * (view.x1 - view.x0));
  const yTicks = Array.from({ length: 5 }, (_, i) => view.y0 + (i / 4) * (view.y1 - view.y0));
  const color = (metric: Metric) =>
    colors[metric.id] ?? (metric.benchmark ? "#71717a" : "#9ae6a5");

  const track = (metric: Metric, event: MouseEvent<SVGCircleElement>) => {
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect) return;
    onHoverId(metric.id);
    setHover({ metric, x: event.clientX - rect.left, y: event.clientY - rect.top });
  };
  const clear = () => {
    setHover(null);
    onHoverId(null);
  };

  const zoom = (factor: number) => {
    const cx = (view.x0 + view.x1) / 2;
    const cy = (view.y0 + view.y1) / 2;
    const halfX = ((view.x1 - view.x0) * factor) / 2;
    const halfY = ((view.y1 - view.y0) * factor) / 2;
    setView(clampView({ x0: cx - halfX, x1: cx + halfX, y0: cy - halfY, y1: cy + halfY }));
  };

  useEffect(() => {
    const node = boxRef.current;
    if (!node) return;
    const handler = (event: WheelEvent) => {
      event.preventDefault();
      const rect = node.getBoundingClientRect();
      const v = viewRef.current;
      const mx = (event.clientX - rect.left) / rect.width;
      const my = (event.clientY - rect.top) / rect.height;
      const px = v.x0 + mx * (v.x1 - v.x0);
      const py = v.y1 - my * (v.y1 - v.y0);
      const factor = event.deltaY > 0 ? 1.2 : 0.84;
      setView(
        clampView({
          x0: px - (px - v.x0) * factor,
          x1: px + (v.x1 - px) * factor,
          y0: py - (py - v.y0) * factor,
          y1: py + (v.y1 - py) * factor,
        }),
      );
    };
    node.addEventListener("wheel", handler, { passive: false });
    return () => node.removeEventListener("wheel", handler);
  }, []);

  const onMouseDown = (event: MouseEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    dragRef.current = { ...view, mx: event.clientX, my: event.clientY };
  };

  const onMouseMove = (event: MouseEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = ((event.clientX - drag.mx) / rect.width) * (drag.x1 - drag.x0);
    const dy = ((event.clientY - drag.my) / rect.height) * (drag.y1 - drag.y0);
    setView(
      clampView({
        x0: drag.x0 - dx,
        x1: drag.x1 - dx,
        y0: drag.y0 + dy,
        y1: drag.y1 + dy,
      }),
    );
  };

  const onMouseUp = () => {
    dragRef.current = null;
  };

  const clipId = "scatter-clip";

  return (
    <div>
      <div
        ref={boxRef}
        className="relative h-[340px] w-full"
        onMouseLeave={() => {
          clear();
          dragRef.current = null;
        }}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-full w-full"
          style={{ touchAction: "none" }}
          role="img"
          aria-label="Risk return map of all strategies"
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
        >
          <defs>
            <clipPath id={clipId}>
              <rect x={left} y={top} width={width - left - right} height={height - top - bottom} />
            </clipPath>
          </defs>
          {xTicks.map((tick, index) => (
            <g key={`x-${index}`}>
              <line
                x1={sx(tick)}
                x2={sx(tick)}
                y1={top}
                y2={height - bottom}
                stroke="#22262c"
                strokeDasharray="4 6"
              />
              <text
                x={sx(tick)}
                y={height - 16}
                textAnchor="middle"
                fill="#9aa1ab"
                fontSize="12"
              >
                {Math.round(tick * 100)}%
              </text>
            </g>
          ))}
          {yTicks.map((tick, index) => (
            <g key={`y-${index}`}>
              <line
                x1={left}
                x2={width - right}
                y1={sy(tick)}
                y2={sy(tick)}
                stroke="#22262c"
                strokeDasharray="4 6"
              />
              <text x={left - 8} y={sy(tick) + 3} textAnchor="end" fill="#9aa1ab" fontSize="12">
                {Math.round(tick * 100)}%
              </text>
            </g>
          ))}
          <g clipPath={`url(#${clipId})`}>
            {metrics.map((metric) => {
              const active = hoveredId === metric.id;
              const dimmed = hoveredId !== null && !active;
              return (
                <g key={metric.id}>
                  <circle
                    cx={sx(metric[xField])}
                    cy={sy(metric[yField])}
                    r={active ? 6 : 4.5}
                    fill={color(metric)}
                    fillOpacity={dimmed ? 0.16 : active ? 1 : 0.9}
                    stroke={active ? "#f4f4f5" : "#08090b"}
                    strokeWidth={active ? 1.8 : 1.2}
                    onMouseDown={(event) => event.stopPropagation()}
                    onMouseEnter={(event) => track(metric, event)}
                    onMouseMove={(event) => track(metric, event)}
                    onMouseLeave={clear}
                    aria-label={`${metric.name}: ${pct(metric[yField])} CAGR, ${pct(metric[xField])} drawdown`}
                  >
                    <title>
                      {`${metric.name}: ${pct(metric[yField])} CAGR  -  ${pct(metric[xField])} DD`}
                    </title>
                  </circle>
                </g>
              );
            })}
          </g>
          <text
            x={(left + width - right) / 2}
            y={height - 2}
            textAnchor="middle"
            fill="#9aa1ab"
            fontSize="12"
          >
            Max drawdown
          </text>
          <text
            x={14}
            y={top + (height - top - bottom) / 2}
            textAnchor="middle"
            fill="#9aa1ab"
            fontSize="12"
            transform={`rotate(-90 14 ${top + (height - top - bottom) / 2})`}
          >
            CAGR
          </text>
        </svg>

        <div className="absolute right-1 top-1 z-10 flex items-center gap-1 rounded-lg border border-white/10 bg-[#08090b]/90 p-0.5 backdrop-blur">
          <button
            onClick={() => zoom(0.8)}
            className="rounded px-2 py-1 text-[12px] text-zinc-300 transition hover:bg-white/10 hover:text-white"
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            onClick={() => zoom(1.25)}
            className="rounded px-2 py-1 text-[12px] text-zinc-300 transition hover:bg-white/10 hover:text-white"
            aria-label="Zoom out"
          >
            -
          </button>
          <button
            onClick={() => setView(DEFAULT)}
            className="rounded px-2 py-1 text-[9px] uppercase tracking-[0.1em] text-zinc-500 transition hover:bg-white/10 hover:text-zinc-200"
            aria-label="Reset zoom"
          >
            Reset
          </button>
        </div>

        {hover ? (
          <div
            className="pointer-events-none absolute z-20 w-[230px] rounded-xl border border-white/10 bg-[#0b0d10]/95 p-3 shadow-2xl backdrop-blur"
            style={{ left: Math.min(hover.x + 14, 360), top: Math.max(8, hover.y - 10) }}
          >
            <div className="text-[12px] font-medium leading-snug text-zinc-100">
              {hover.metric.name}
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-zinc-500">
              2016-2026
            </div>
            <div className="mt-2 flex gap-3 text-[11px]">
              <span className="text-emerald-200">{pct(hover.metric[yField])} CAGR</span>
              <span className="text-rose-200">{pct(hover.metric[xField])} DD</span>
            </div>
          </div>
        ) : null}
      </div>
      <p className="mt-1 text-[10px] text-zinc-500">
        Scroll to zoom  -  drag to pan  -  hover for metrics
      </p>
    </div>
  );
}

export function AllStrategiesChart() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [scale, setScale] = useState<"linear" | "log">("log");
  const [above, setAbove] = useState<"all" | "tqqq" | "qqq">("all");
  const [family, setFamily] = useState<string>("all");
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/compare/all.json?v=2026-11-28-43v", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload: Payload) => setData(payload))
      .catch((reason) => setError(String(reason)));
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    return data.dates.map((date, index) => {
      const row: Record<string, string | number | null> = { date };
      data.series.forEach((curve) => {
        row[curve.id] = curve.values[index];
      });
      return row;
    });
  }, [data]);

  const ticks = useMemo(() => {
    if (!data) return [];
    const out: string[] = [];
    let lastYear = "";
    data.dates.forEach((date) => {
      const year = date.slice(0, 4);
      if (year !== lastYear && (out.length === 0 || Number(year) % 2 === 0)) {
        out.push(date);
        lastYear = year;
      }
    });
    return out;
  }, [data]);

  const metricById = useMemo(() => {
    const map = new Map<string, Metric>();
    (data?.metrics ?? []).forEach((metric) => map.set(metric.id, metric));
    return map;
  }, [data]);

  const colorById = useMemo(() => {
    const map: Record<string, string> = {};
    (data?.series ?? []).forEach((curve) => {
      map[curve.id] = curve.color;
    });
    return map;
  }, [data]);

  const families = useMemo(() => {
    const set = new Set<string>();
    (data?.metrics ?? []).forEach((metric) => {
      if (!metric.benchmark) set.add(metric.family ?? "other");
    });
    return [...set].sort();
  }, [data]);

  const inFamily = (id: string) =>
    family === "all" || (metricById.get(id)?.family ?? "other") === family;

  const legendSeries = useMemo(() => {
    if (!data) return [];
    return data.series.filter(
      (curve) => curve.id === "tqqq" || curve.id === "qqq" || inFamily(curve.id),
    );
  }, [data, family, metricById]);

  const visible =
    data?.series.filter(
      (curve) =>
        curve.id === "tqqq" || curve.id === "qqq" || (inFamily(curve.id) && !hidden.has(curve.id)),
    ) ?? [];

  const toggle = (id: string) => {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const showAll = () => {
    setAbove("all");
    setFamily("all");
    setHidden(new Set());
    setHovered(null);
  };

  const showTop = () => {
    if (!data) return;
    setAbove("all");
    setHovered(null);
    const top = new Set(
      data.metrics
        .filter((metric) => !metric.benchmark && (family === "all" || (metric.family ?? "other") === family))
        .sort((a, b) => b.cagr - a.cagr)
        .slice(0, 6)
        .map((metric) => metric.id),
    );
    top.add("tqqq");
    top.add("qqq");
    setHidden(new Set(data.series.filter((curve) => !top.has(curve.id)).map((curve) => curve.id)));
  };

  const applyAbove = (key: "all" | "tqqq" | "qqq", nextFamily: string) => {
    setAbove(key);
    setHovered(null);
    if (!data || key === "all") {
      setHidden(new Set());
      return;
    }
    const bench = data.metrics.find((metric) => metric.id === key && metric.benchmark);
    if (!bench) return;
    const keep = new Set<string>(["tqqq", "qqq"]);
    const matches = data.metrics.filter(
      (metric) =>
        !metric.benchmark &&
        metric.cagr > bench.cagr &&
        (nextFamily === "all" || (metric.family ?? "other") === nextFamily),
    );
    matches.forEach((metric) => keep.add(metric.id));
    setHidden(new Set(data.series.filter((curve) => !keep.has(curve.id)).map((curve) => curve.id)));
  };

  const filterAbove = (key: "all" | "tqqq" | "qqq") => applyAbove(key, family);

  const changeFamily = (next: string) => {
    setFamily(next);
    applyAbove(above, next);
  };

  const table = [...(data?.metrics ?? [])]
    .filter((metric) => visible.some((curve) => curve.id === metric.id))
    .sort((a, b) => {
      const bench = (a.benchmark ? 1 : 0) - (b.benchmark ? 1 : 0);
      return bench || b.cagr - a.cagr;
    });

  if (error) {
    return (
      <div className="panel p-6 text-[12px] text-rose-200">
        Could not load the comparison data: {error}
      </div>
    );
  }

  if (!data) {
    return <div className="panel h-[420px] animate-pulse bg-white/[0.02]" />;
  }

  const strategyCount = data.metrics.filter((metric) => !metric.benchmark).length;

  return (
    <div className="space-y-8">
      <section className="panel p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="eyebrow">All strategies, one graph</div>
            <h2 className="mt-1 text-lg font-semibold text-zinc-100">
              Growth of $100  -  normalized  -  1 bp costs
            </h2>
            <p className="mt-1 text-[11px] text-zinc-500">
              {data.start} to {data.end} - {data.series.length} curves - {strategyCount} strategies + TQQQ/QQQ
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
              {(["linear", "log"] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setScale(option)}
                  className={`rounded-md px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] transition ${
                    scale === option
                      ? "bg-white/10 text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-[10px] text-zinc-500">
              <span className="uppercase tracking-[0.12em]">Family</span>
              <select
                value={family}
                onChange={(event) => changeFamily(event.target.value)}
                className="max-w-[130px] bg-transparent text-[10px] text-zinc-200 outline-none"
                aria-label="Filter by family"
              >
                <option value="all">All families</option>
                {families.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => filterAbove("tqqq")}
              className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.14em] transition ${
                above === "tqqq"
                  ? "border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-100"
                  : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
              }`}
            >
              Above TQQQ
            </button>
            <button
              onClick={() => filterAbove("qqq")}
              className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.14em] transition ${
                above === "qqq"
                  ? "border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-100"
                  : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
              }`}
            >
              Above QQQ
            </button>
            <button
              onClick={showAll}
              className="rounded-full border border-white/10 px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
            >
              All
            </button>
            <button
              onClick={showTop}
              className="rounded-full border border-white/10 px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
            >
              Top 6
            </button>
          </div>
        </div>

        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-zinc-500">
          <span>
            Showing {visible.length} of {data.series.length} curves
            {family !== "all" ? ` in ${family}` : ""}
          </span>
          <span>Hover a line or row to highlight it</span>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {legendSeries.map((curve) => {
            const off = hidden.has(curve.id);
            const isHovered = hovered === curve.id;
            return (
              <button
                key={curve.id}
                onClick={() => toggle(curve.id)}
                onMouseEnter={() => setHovered(curve.id)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(curve.id)}
                onBlur={() => setHovered(null)}
                title={off ? `Show ${curve.name}` : `Hide ${curve.name}`}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] transition ${
                  isHovered
                    ? "border-emerald-300/40 bg-emerald-300/[0.08] text-emerald-100"
                    : off
                      ? "border-white/[0.06] text-zinc-600"
                      : "border-white/10 text-zinc-300 hover:border-white/20 hover:text-zinc-100"
                }`}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: off ? "#3f3f46" : curve.color }}
                />
                {curve.name}
              </button>
            );
          })}
        </div>

        <div className="h-[520px] w-full min-w-0">
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
              <Tooltip content={<CompareTooltip />} />
              {visible.map((curve) => {
                const isHovered = hovered === curve.id;
                const dimmed = hovered !== null && !isHovered;
                return (
                  <Line
                    key={curve.id}
                    type="monotone"
                    dataKey={curve.id}
                    name={curve.name}
                    stroke={curve.color}
                    strokeWidth={isHovered ? 3 : curve.id === "tqqq" ? 1.3 : 1.9}
                    strokeOpacity={dimmed ? 0.12 : 1}
                    strokeDasharray={curve.id === "tqqq" ? "4 4" : undefined}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                    activeDot={{ r: 2.5, fill: curve.color, stroke: "#08090b", strokeWidth: 2 }}
                  />
                );
              })}
              <Brush
                dataKey="date"
                height={26}
                stroke="#3f3f46"
                fill="#0b0d10"
                travellerWidth={8}
                tickFormatter={(value: string) => value.slice(0, 4)}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="panel p-4 sm:p-5">
          <div className="mb-4">
            <div className="eyebrow">Risk vs return</div>
            <h2 className="mt-1 text-lg font-semibold text-zinc-100">
              All strategies, same standard
            </h2>
            <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
              CAGR vs max drawdown, 2016-2026, 1 bp costs. Every strategy uses the same window and
              the same treatment. Scroll to zoom and drag to pan.
            </p>
          </div>
          <ScatterPlot
            metrics={data.metrics.filter((metric) =>
              visible.some((curve) => curve.id === metric.id),
            )}
            colors={colorById}
            hoveredId={hovered}
            onHoverId={setHovered}
          />
        </div>

        <div className="panel overflow-hidden">
          <div className="border-b border-white/[0.06] px-4 py-4 sm:px-5">
            <div className="eyebrow">Metrics</div>
            <h2 className="mt-1 text-lg font-semibold text-zinc-100">
              {family === "all" ? "All strategies" : `${family} strategies`}
            </h2>
            <p className="mt-1 text-[11px] text-zinc-500">
              2016-2026 daily curves, 1 bp costs, same window and rules for every row.
              Hover a row to highlight its line.
            </p>
          </div>
          <div className="max-h-[340px] overflow-auto">
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-[#0b0d10] text-zinc-500">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Strategy</th>
                  <th className="px-2 py-2 text-right font-medium">CAGR</th>
                  <th className="px-2 py-2 text-right font-medium">DD</th>
                  <th className="px-4 py-2 text-right font-medium">Sharpe</th>
                </tr>
              </thead>
              <tbody>
                {table.map((metric) => (
                  <tr
                    key={metric.id}
                    onMouseEnter={() => setHovered(metric.id)}
                    onMouseLeave={() => setHovered(null)}
                    className={`border-t border-white/[0.04] transition ${
                      hovered === metric.id ? "bg-white/[0.04]" : ""
                    }`}
                  >
                    <td className="px-4 py-2 text-zinc-300">
                      <span className="flex items-center gap-2">
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: colorById[metric.id] ?? "#71717a" }}
                        />
                        <span>
                          <span className="block">{metric.name}</span>
                          <span className="block text-[9px] uppercase tracking-[0.1em] text-zinc-600">
                            {metric.benchmark ? "benchmark" : metric.family ?? "other"}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right text-emerald-200/90">{pct(metric.cagr)}</td>
                    <td className="px-2 py-2 text-right text-rose-200/80">{pct(metric.dd)}</td>
                    <td className="px-4 py-2 text-right text-zinc-400">
                      {metric.sharpe.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}



