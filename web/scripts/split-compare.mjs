// Derive small browser-facing files from public/data/compare/all.json.
//
// all.json (~3 MB) stays the source of truth for the Python research scripts.
// The browser gets:
//   compare/all.min.json        - same shape, values rounded to 6 significant digits
//   compare/curves/<id>.json    - one strategy's curve plus the TQQQ benchmark
//
// Runs automatically before `next dev` and `next build` (see package.json).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const compareDir = path.join(root, "public", "data", "compare");
const source = path.join(compareDir, "all.json");
const curvesDir = path.join(compareDir, "curves");

const round = (value) => (value == null ? null : Number(value.toPrecision(6)));

const data = JSON.parse(fs.readFileSync(source, "utf8"));
const series = data.series.map((curve) => ({ ...curve, values: curve.values.map(round) }));

fs.writeFileSync(path.join(compareDir, "all.min.json"), JSON.stringify({ ...data, series }));

fs.rmSync(curvesDir, { recursive: true, force: true });
fs.mkdirSync(curvesDir, { recursive: true });
const tqqq = series.find((curve) => curve.id === "tqqq")?.values ?? null;
for (const curve of series) {
  const out = { start: data.start, end: data.end, dates: data.dates, values: curve.values, tqqq };
  fs.writeFileSync(path.join(curvesDir, `${curve.id}.json`), JSON.stringify(out));
}

console.log(`split-compare: all.min.json + ${series.length} curve files`);
