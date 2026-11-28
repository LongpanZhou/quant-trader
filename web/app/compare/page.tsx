import type { Metadata } from "next";
import { AllStrategiesChart } from "@/components/all-strategies-chart";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { Pill } from "@/components/ui";
import { researchStrategyCount } from "@/lib/research-count";

export const metadata: Metadata = {
  title: "All strategies, one graph  -  quant-trader",
  description:
    "Every strategy on one normalized equity chart, with a risk/return map and full metrics.",
};

export const dynamic = "force-dynamic";

export default function ComparePage() {
  const researchCount = researchStrategyCount();
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="catalog" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="max-w-3xl">
            <div className="mb-4 flex flex-wrap gap-2">
              <Pill tone="green">All strategies</Pill>
              <Pill>One graph</Pill>
              <Pill>1 bp costs</Pill>
            </div>
            <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
              One graph.
              <br />
              <span className="text-emerald-200">Every strategy.</span>
            </h1>
            <p className="mt-5 max-w-2xl text-[14px] leading-relaxed text-zinc-400">
              {researchCount} strategies on one shared window, with the same rules, costs and
              metrics. Set any start and end date, then compare every strategy on that exact
              period. TQQQ and QQQ are shown for reference.
            </p>
          </div>
        </section>

        <section className="pt-8">
          <div className="panel-soft p-4 text-[12px] leading-relaxed text-zinc-400 sm:p-5">
            <span className="font-medium text-zinc-200">One standard.</span> Every strategy uses
            the same selected window, 1 bp costs and daily close marks. Change the start or end
            date and the chart, table and scatter recompute together, so the ranking stays
            directly comparable across every strategy.
          </div>
        </section>

        <section className="pt-8">
          <AllStrategiesChart />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

