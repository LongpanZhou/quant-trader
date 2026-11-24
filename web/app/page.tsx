import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { StrategyCard } from "@/components/strategy-card";
import { DATA_UPDATED, STRATEGIES } from "@/lib/strategies";
import { loadCard } from "@/lib/strategies.server";
import { Pill } from "@/components/ui";

const UPDATED = new Date(`${DATA_UPDATED}T00:00:00Z`).toLocaleDateString("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

export default function Page() {
  const cards = STRATEGIES.map((strategy) => loadCard(strategy));
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="catalog" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="mb-4 flex flex-wrap gap-2">
                <Pill tone="green">Research portal</Pill>
                <Pill>Paper trading</Pill>
                <Pill tone="blue">Rust + Next.js</Pill>
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                Strategy
                <br />
                <span className="text-emerald-200">lab.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[14px] leading-relaxed text-zinc-400">
                A growing library of systematic rules. Each strategy gets its own portal: equity
                curve, drawdowns, yearly and monthly returns, trade statistics and the research
                behind it.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
                Data through {UPDATED}
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Pill>{STRATEGIES.length} strategies</Pill>
                <Pill>5 / 10 / 20 / 26 years</Pill>
                <Pill>1bp slippage</Pill>
              </div>
            </div>
          </div>
        </section>

        <section id="strategies" className="scroll-mt-24 pt-14">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="eyebrow mb-2">Library</div>
              <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
                Open a strategy portal
              </h2>
            </div>
            <p className="max-w-md text-[11px] leading-relaxed text-zinc-600">
              The current rule is the promoted strategy. The other entries are research variants and
              ablations, kept on the same engine so the comparison is like-for-like.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {cards.map(({ strategy, window, data }) => (
              <StrategyCard key={strategy.slug} strategy={strategy} window={window} data={data} />
            ))}
          </div>
        </section>

        <section id="method" className="scroll-mt-24 pt-16">
          <div className="mb-5">
            <div className="eyebrow mb-2">Method</div>
            <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
              One engine, one data contract
            </h2>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <MethodCard
              number="01"
              title="Rust engine"
              body="The backtester runs every rule through the same fill model, 1bp slippage, next-open execution and optional synthetic fund series."
            />
            <MethodCard
              number="02"
              title="Static JSON"
              body="Each run writes web/public/data/<slug>/<window>.json. No database, no API server, no runtime dependency on the Rust binary."
            />
            <MethodCard
              number="03"
              title="Next.js portal"
              body="The site reads the JSON and renders the same chart set for every strategy. Adding a strategy means a config, an export entry and one manifest entry."
            />
          </div>
          <div className="panel-soft mt-4 flex flex-col gap-2 p-4 text-[11px] leading-relaxed text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Add a strategy: write a config, export its JSON, add an entry to
              <span className="font-mono text-zinc-400"> web/public/data/strategies.json</span>.
            </span>
            <a
              className="text-zinc-400 transition hover:text-zinc-200"
              href="https://github.com/LongpanZhou/quant-trader/blob/main/scripts/export-web-data.ps1"
              target="_blank"
              rel="noreferrer"
            >
              Export script ↗
            </a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function MethodCard({ number, title, body }: { number: string; title: string; body: string }) {
  return (
    <div className="panel-soft p-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-300">{title}</div>
        <span className="font-mono text-[10px] text-zinc-700">{number}</span>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{body}</p>
    </div>
  );
}
