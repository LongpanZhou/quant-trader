import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);
const CACHE = path.join(os.tmpdir(), "quant-trader-research-cache");

type Body = {
  slug?: string;
  start?: string;
  end?: string;
  params?: Record<string, unknown>;
  slippageBps?: number;
};

function repoRoot() {
  const cwd = process.cwd();
  if (fs.existsSync(path.join(cwd, "research", "web_runner.py"))) return cwd;
  return path.resolve(cwd, "..");
}

function validDate(value: unknown) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON body" }, { status: 400 });
  }

  const slug = String(body.slug ?? "").trim();
  const start = String(body.start ?? "").trim();
  const end = String(body.end ?? "").trim();
  const params = body.params && typeof body.params === "object" ? body.params : {};
  const slippage = Number(body.slippageBps ?? 1);

  if (!/^[a-z0-9-]{2,80}$/.test(slug)) {
    return NextResponse.json({ ok: false, error: "invalid strategy slug" }, { status: 400 });
  }
  if (!validDate(start) || !validDate(end) || start >= end) {
    return NextResponse.json({ ok: false, error: "start/end must be YYYY-MM-DD and start < end" }, { status: 400 });
  }
  if (!Number.isFinite(slippage) || slippage < 0 || slippage > 100) {
    return NextResponse.json({ ok: false, error: "slippage must be 0..100 bp" }, { status: 400 });
  }

  const key = createHash("sha256")
    .update(JSON.stringify({ slug, start, end, params, slippage }))
    .digest("hex");
  const cachePath = path.join(CACHE, `${key}.json`);
  if (fs.existsSync(cachePath)) {
    return NextResponse.json(JSON.parse(fs.readFileSync(cachePath, "utf8")));
  }

  const root = repoRoot();
  const script = path.join(root, "research", "web_runner.py");
  const args = [
    script,
    "--slug", slug,
    "--start", start,
    "--end", end,
    "--params", JSON.stringify(params),
    "--slippage", String(slippage),
  ];

  try {
    const { stdout } = await execFileAsync(process.env.RESEARCH_PYTHON || "python", args, {
      cwd: root,
      timeout: 300_000,
      maxBuffer: 64 * 1024 * 1024,
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", BT_THREADS: "1" },
    });
    const payload = JSON.parse(stdout.trim().split("\n").pop() ?? "{}");
    if (!payload.ok) {
      return NextResponse.json(payload, { status: 500 });
    }
    fs.mkdirSync(CACHE, { recursive: true });
    fs.writeFileSync(cachePath, JSON.stringify(payload));
    return NextResponse.json(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
