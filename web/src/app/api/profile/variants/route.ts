import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import { careerOpsRoot } from "@/lib/career-ops";
import { atomicWriteWithBackup } from "@/lib/core/safe-write";
import { djangoJsonResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function loadVariant(name: string): Record<string, unknown> {
  const file = path.join(careerOpsRoot(), "config", "profiles", `${name}.yml`);
  try {
    return (yaml.load(fs.readFileSync(file, "utf8")) as Record<string, unknown>) || {};
  } catch {
    return {};
  }
}

function listVariants(): string[] {
  const dir = path.join(careerOpsRoot(), "config", "profiles");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".yml"))
    .map((f) => f.replace(/\.yml$/, ""))
    .sort();
}

export async function GET() {
  const django = await djangoJsonResponse("/api/profile/variants");
  if (django) return django;

  const variants = listVariants().map((name) => ({
    name,
    overrides: loadVariant(name),
  }));
  return Response.json({ variants });
}

export async function POST(req: Request) {
  let body: { name?: string; overrides?: Record<string, unknown> };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }

  const name = body.name?.trim().replace(/[^a-zA-Z0-9-]/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
  if (!name) return Response.json({ error: "name is required" }, { status: 400 });

  const django = await djangoJsonResponse("/api/profile/variants", { method: "POST", body: JSON.stringify({ name, overrides: body.overrides || {} }) });
  if (django) return django;

  const dir = path.join(careerOpsRoot(), "config", "profiles");
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}.yml`);
  try {
    atomicWriteWithBackup(file, yaml.dump(body.overrides || {}, { lineWidth: 100, noRefs: true }));
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "write failed" }, { status: 500 });
  }
  return Response.json({ ok: true, name });
}
