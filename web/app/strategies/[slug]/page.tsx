import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { StrategyDashboard } from "@/components/dashboard";
import { STRATEGIES, getStrategy } from "@/lib/strategies";

export const dynamicParams = false;

export function generateStaticParams() {
  return STRATEGIES.map((strategy) => ({ slug: strategy.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const strategy = getStrategy(params.slug);
  if (!strategy) return { title: "Strategy not found" };
  return {
    title: `${strategy.name} — quant-trader`,
    description: strategy.description,
  };
}

export default function Page({ params }: { params: { slug: string } }) {
  const strategy = getStrategy(params.slug);
  if (!strategy) notFound();
  return <StrategyDashboard strategy={strategy} />;
}
