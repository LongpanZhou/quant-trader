import strategiesJson from "@/public/data/strategies.json";
import type {
  PaperId,
  StrategyMeta,
  StrategyStatus,
  WindowId,
} from "./types";

type RawStrategy = Omit<
  StrategyMeta,
  "status" | "windows" | "defaultWindow" | "syntheticWindows" | "papers"
> & {
  status: string;
  windows: string[];
  defaultWindow: string;
  syntheticWindows?: string[];
  papers: string[];
};

const raw = strategiesJson as { updated: string; strategies: RawStrategy[] };

export const DATA_UPDATED = raw.updated;

export const STRATEGIES: StrategyMeta[] = raw.strategies.map((strategy) => ({
  ...strategy,
  status: strategy.status as StrategyStatus,
  windows: strategy.windows as WindowId[],
  defaultWindow: strategy.defaultWindow as WindowId,
  syntheticWindows: (strategy.syntheticWindows ?? []) as WindowId[],
  papers: strategy.papers as PaperId[],
}));

export function getStrategy(slug: string): StrategyMeta | undefined {
  return STRATEGIES.find((strategy) => strategy.slug === slug);
}
