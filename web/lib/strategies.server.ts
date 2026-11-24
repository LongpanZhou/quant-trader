import fs from "node:fs";
import path from "node:path";
import type { PerformanceData, StrategyMeta, WindowId } from "./types";

export function readStrategyWindow(
  slug: string,
  window: WindowId,
): PerformanceData | null {
  const file = path.join(process.cwd(), "public", "data", slug, `${window}.json`);
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as PerformanceData;
  } catch {
    return null;
  }
}

export function loadCard(strategy: StrategyMeta) {
  const window = strategy.defaultWindow ?? strategy.windows[0];
  return {
    strategy,
    window,
    data: readStrategyWindow(strategy.slug, window),
  };
}
