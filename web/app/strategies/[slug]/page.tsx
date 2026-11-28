import type { Metadata } from "next";
import fs from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import { ResearchDetail, type Detail } from "@/components/research-detail";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { StrategyTestLink } from "@/components/strategy-test-link";

// One page per research strategy. The strategy is defined by its Python
// record; no bot dashboard or trend-filter controls are rendered here.

function readDetail(slug: string): Detail | null {
  try {
    const file = path.join(process.cwd(), "public", "data", "research", `${slug}.json`);
    return JSON.parse(fs.readFileSync(file, "utf8")) as Detail;
  } catch {
    return null;
  }
}

function recordSlugs(): string[] {
  try {
    const file = path.join(process.cwd(), "public", "data", "research", "rebuild.json");
    const data = JSON.parse(fs.readFileSync(file, "utf8")) as { strategies: { slug: string }[] };
    return data.strategies.map((s) => s.slug);
  } catch {
    return [];
  }
}

export const dynamicParams = false;

export function generateStaticParams() {
  return recordSlugs().map((slug) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const detail = readDetail(params.slug);
  if (!detail) return { title: "Strategy not found" };
  return { title: `${detail.name} — quant-trader`, description: detail.tagline || detail.summary };
}

export default function Page({ params }: { params: { slug: string } }) {
  const detail = readDetail(params.slug);
  if (!detail) notFound();
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="catalog" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="pt-8">
          <StrategyTestLink slug={params.slug} />
        </section>
        <section className="pt-6">
          <ResearchDetail detail={detail} />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
