import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { StrategyCatalog } from "@/components/strategy-catalog";
import { Pill } from "@/components/ui";

export default function Page() {
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
              </div>
              <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
                Strategy
                <br />
                <span className="text-emerald-200">library.</span>
              </h1>
              <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-zinc-400">
                One catalog: three editable Rust presets and 27 strategies on the same
                2016-2026 window. Open a preset to run and edit it, or open the all-strategies
                view to compare every strategy.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-300" />
                Research data through Nov 26, 2026
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Pill>30 strategies</Pill>
                <Pill>3 runnable</Pill>
                <Pill>27 research</Pill>
                <Pill>1 bp costs</Pill>
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <a
                  href="/compare"
                  className="inline-flex items-center justify-center rounded-full border border-white/10 px-4 py-2 text-[11px] font-semibold text-zinc-300 transition hover:border-white/20 hover:text-zinc-50"
                >
                  All-strategy chart
                </a>
                <a
                  href="/research"
                  className="inline-flex items-center justify-center rounded-full border border-emerald-300/25 bg-emerald-300/[0.06] px-4 py-2 text-[11px] font-semibold text-emerald-100 transition hover:border-emerald-300/40 hover:bg-emerald-300/[0.10]"
                >
                  Research library
                </a>
                <a
                  href="/lab"
                  className="inline-flex items-center justify-center rounded-full bg-emerald-300 px-4 py-2 text-[11px] font-semibold text-[#07110a] transition hover:bg-emerald-200"
                >
                  Open backtest lab →
                </a>
              </div>
            </div>
          </div>
        </section>

        <section id="strategies" className="scroll-mt-24 pt-14">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="eyebrow mb-2">One library</div>
              <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">
                Presets and research, together
              </h2>
            </div>
            <p className="max-w-md text-[11px] leading-relaxed text-zinc-500">
              Runnable presets use the editable Rust engine. Research strategies are precomputed
              1-minute results with papers and provenance. Both open from the same catalog.
            </p>
          </div>
          <StrategyCatalog />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
