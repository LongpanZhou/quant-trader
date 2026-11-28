import type { PerformanceData, StrategyMeta, WindowId } from "@/lib/types";
import { num, pct, points } from "@/lib/format";
import { Pill } from "./ui";
import { Sparkline } from "./sparkline";

const STATUS = {
  current: { label: "Current strategy", tone: "green" as const },
  variant: { label: "Variant", tone: "blue" as const },
  ablation: { label: "Ablation", tone: "amber" as const },
};

export function StrategyCard({
  strategy,
  window,
  data,
}: {
  strategy: StrategyMeta;
  window: WindowId;
  data: PerformanceData | null;
}) {
  const status = STATUS[strategy.status];
  return (
    <a
      href={`/strategies/${strategy.slug}/`}
      className="group panel relative flex flex-col overflow-hidden transition hover:border-white/20"
    >
      <div className="h-[3px] w-full" style={{ background: strategy.accent }} />
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center justify-between gap-3">
          <Pill tone={status.tone}>{status.label}</Pill>
          <span className="text-[10px] text-zinc-600 transition group-hover:text-zinc-300">
            Open portal ↗
          </span>
        </div>
        <h2 className="mt-4 text-[1.35rem] font-semibold leading-tight text-zinc-100">
          {strategy.name}
        </h2>
        <p className="mt-2 min-h-[40px] text-[12px] leading-relaxed text-zinc-500">
          {strategy.tagline}
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {strategy.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-zinc-500"
            >
              {tag}
            </span>
          ))}
        </div>

        {data ? (
          <>
            <div className="mt-4">
              <Sparkline
                values={data.series.map((point) => point.strategy)}
                color={strategy.accent}
                id={strategy.slug}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-white/[0.06] pt-3">
              <Metric label="CAGR" value={pct(data.metrics.cagr)} tone="text-emerald-200" />
              <Metric label="Excess" value={points(data.metrics.excess)} tone="text-emerald-200" />
              <Metric label="Max drawdown" value={pct(-data.metrics.maxDrawdown)} tone="text-rose-200" />
              <Metric label="Win rate" value={pct(data.metrics.winRate)} />
            </div>
            <div className="mt-auto flex items-center justify-between gap-3 pt-4 text-[10px] text-zinc-600">
              <span>{window === "5y" ? "5-year test" : `${window} test`}</span>
              <span>{num(data.metrics.closedTrades)} trades · {num(data.metrics.fills)} fills</span>
            </div>
          </>
        ) : (
          <div className="mt-6 rounded-lg border border-white/[0.06] bg-black/20 p-4 text-[11px] text-zinc-500">
            Data has not been exported for this strategy yet.
          </div>
        )}
      </div>
    </a>
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
