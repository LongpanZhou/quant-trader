import type { Metadata } from "next";
import fs from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import { ResearchDetail, type Detail } from "@/components/research-detail";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

function detailPath(slug: string) {
  return path.join(process.cwd(), "public", "data", "research", `${slug}.json`);
}

function readDetail(slug: string): Detail | null {
  try {
    return JSON.parse(fs.readFileSync(detailPath(slug), "utf8")) as Detail;
  } catch {
    return null;
  }
}

export const dynamicParams = false;

export function generateStaticParams() {
  try {
    const file = path.join(process.cwd(), "public", "data", "research", "rebuild.json");
    const data = JSON.parse(fs.readFileSync(file, "utf8")) as {
      strategies: { slug: string }[];
    };
    return data.strategies.map((s) => ({ slug: s.slug }));
  } catch {
    return [];
  }
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const detail = readDetail(params.slug);
  if (!detail) return { title: "Strategy research · quant-trader" };
  return {
    title: `${detail.name} · research · quant-trader`,
    description: detail.tagline || detail.summary,
  };
}

export default function ResearchDetailPage({ params }: { params: { slug: string } }) {
  const detail = readDetail(params.slug);
  if (!detail) notFound();
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 grid-lines opacity-40" />
      <SiteHeader mode="catalog" />
      <main className="relative mx-auto max-w-[1180px] px-5 pb-20 lg:px-8">
        <section className="pt-10">
          <ResearchDetail detail={detail} />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
