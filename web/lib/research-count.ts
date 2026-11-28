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
