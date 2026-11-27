import type { Metadata } from "next";
import { ResearchLibrary } from "@/components/research-library";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { Pill } from "@/components/ui";

export const metadata: Metadata = {
  title: "Research library  -  quant-trader",
  description:
    "Every research agent strategy: rules, metrics, the exact report, and the papers it cites.",
};

export default function ResearchPage() {
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="catalog" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="fade-up pt-12 sm:pt-16">
          <div className="max-w-3xl">
            <div className="mb-4 flex flex-wrap gap-2">
              <Pill tone="green">Research library</Pill>
              <Pill>37 strategies</Pill>
              <Pill>Same rules</Pill>
            </div>
            <h1 className="display text-[2.7rem] font-semibold text-zinc-50 sm:text-[3.6rem]">
              Every strategy.
              <br />
              <span className="text-emerald-200">Same standard.</span>
            </h1>
            <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
              37 verified strategies on the same 2016-2026 window, with the same
              costs and metrics. No groups, no pass/fail labels - just the ranking.
            </p>
          </div>
        </section>

        <section className="pt-10">
          <ResearchLibrary />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

