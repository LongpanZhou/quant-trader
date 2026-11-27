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
    const dir = path.join(process.cwd(), "public", "data", "research");
    const main = JSON.parse(fs.readFileSync(path.join(dir, "rebuild.json"), "utf8")) as {
      strategies: { slug: string }[];
    };
    let archive: { slug: string }[] = [];
    try {
      const payload = JSON.parse(fs.readFileSync(path.join(dir, "archive.json"), "utf8")) as {
        strategies: { slug: string }[];
      };
      archive = payload.strategies;
    } catch {
      archive = [];
    }
    const slugs = new Set([...main.strategies, ...archive].map((s) => s.slug));
    return [...slugs].map((slug) => ({ slug }));
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
