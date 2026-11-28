import fs from "node:fs";
import path from "node:path";

/** Count the visible research library rows at render/build time. */
export function researchStrategyCount(): number {
  try {
    const file = path.join(process.cwd(), "public", "data", "research", "rebuild.json");
    const data = JSON.parse(fs.readFileSync(file, "utf8")) as {
      strategies?: unknown[];
    };
    return Array.isArray(data.strategies) ? data.strategies.length : 0;
  } catch {
    return 0;
  }
}

/** Count every catalog strategy, and those the lab can rerun (they have a bot.toml). */
export function catalogCounts(): { total: number; adjustable: number } {
  try {
    const file = path.join(process.cwd(), "public", "data", "catalog", "strategies.json");
    const data = JSON.parse(fs.readFileSync(file, "utf8")) as {
      strategies?: { adjustable?: boolean }[];
    };
    const list = Array.isArray(data.strategies) ? data.strategies : [];
    return { total: list.length, adjustable: list.filter((s) => s.adjustable).length };
  } catch {
    return { total: 0, adjustable: 0 };
  }
}
