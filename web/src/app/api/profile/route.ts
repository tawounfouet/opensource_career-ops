import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import { careerOpsRoot } from "@/lib/career-ops";
import { atomicWriteWithBackup } from "@/lib/core/safe-write";
import { djangoJsonResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Profile API — reads/writes config/profile.yml with optional variant support.
// Django backend (ProfileView) handles the full read/write when available.
// Fallback: direct file access for when Django is not running.

type ProfilePatch = {
  name?: string;
  email?: string;
  location?: string;
  roles?: string[];
  compMin?: number;
  compMax?: number;
  currency?: string;
  remote?: string;
  full_name?: string;
  phone?: string;
  linkedin?: string;
  portfolio_url?: string;
  github?: string;
  headline?: string;
  exit_story?: string;
  objective?: string;
  superpowers?: string[];
  languages?: Array<{ language: string; level: string; note?: string }>;
  interests?: string[];
  regulations?: string[];
  spend_tier?: string;
  candidate?: Record<string, unknown>;
  narrative?: Record<string, unknown>;
  compensation?: Record<string, unknown>;
  location_obj?: Record<string, unknown>;
  language?: Record<string, unknown>;
  cv?: Record<string, unknown>;
  cover_letter?: Record<string, unknown>;
  [key: string]: unknown;
};

function isObj(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function deepMerge(dst: unknown, src: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = isObj(dst) ? { ...dst } : {};
  for (const [k, v] of Object.entries(src)) {
    out[k] = isObj(v) ? deepMerge(out[k], v) : v;
  }
  return out;
}

function patchToProfile(p: ProfilePatch): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  // Full object overrides
  if (p.candidate) out.candidate = p.candidate;
  if (p.narrative) out.narrative = p.narrative;
  if (p.compensation) out.compensation = p.compensation;
  if (p.location_obj) out.location = p.location_obj;
  if (p.language) out.language = p.language;
  if (p.cv) out.cv = p.cv;
  if (p.cover_letter) out.cover_letter = p.cover_letter;
  if (p.languages) out.languages = p.languages;
  if (p.interests) out.interests = p.interests;
  if (p.regulations) out.regulations = p.regulations;
  if (p.spend_tier) out.spend_tier = p.spend_tier;

  // Flat shortcuts (backward compat)
  const candidate: Record<string, unknown> = {};
  if (p.full_name || p.name) candidate.full_name = p.full_name || p.name;
  if (p.email) candidate.email = p.email;
  if (p.phone) candidate.phone = p.phone;
  if (p.location) candidate.location = p.location;
  if (p.linkedin) candidate.linkedin = p.linkedin;
  if (p.portfolio_url) candidate.portfolio_url = p.portfolio_url;
  if (p.github) candidate.github = p.github;
  if (Object.keys(candidate).length) out.candidate = candidate;

  if (p.roles?.length) out.target_roles = { primary: p.roles.slice(0, 6) };

  const comp: Record<string, unknown> = {};
  if (p.compMin && p.compMax) comp.target_range = `${p.compMin}-${p.compMax}`;
  if (p.currency) comp.currency = p.currency;
  if (p.remote) comp.location_flexibility = p.remote;
  if (Object.keys(comp).length) out.compensation = comp;

  const narrative: Record<string, unknown> = {};
  if (p.headline) narrative.headline = p.headline;
  if (p.exit_story) narrative.exit_story = p.exit_story;
  if (p.objective) narrative.objective = p.objective;
  if (p.superpowers) narrative.superpowers = p.superpowers;
  if (Object.keys(narrative).length) out.narrative = narrative;

  return out;
}

// List variant names from config/profiles/
function listVariants(): string[] {
  const dir = path.join(careerOpsRoot(), "config", "profiles");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".yml"))
    .map((f) => f.replace(/\.yml$/, ""))
    .sort();
}

function loadVariant(name: string): Record<string, unknown> {
  const file = path.join(careerOpsRoot(), "config", "profiles", `${name}.yml`);
  try {
    return (yaml.load(fs.readFileSync(file, "utf8")) as Record<string, unknown>) || {};
  } catch {
    return {};
  }
}

function resolveProfile(variantName?: string): Record<string, unknown> {
  const base = loadBaseProfile();
  if (variantName) {
    const override = loadVariant(variantName);
    return deepMerge(base, override);
  }
  return base;
}

function loadBaseProfile(): Record<string, unknown> {
  const file = path.join(careerOpsRoot(), "config", "profile.yml");
  try {
    return (yaml.load(fs.readFileSync(file, "utf8")) as Record<string, unknown>) || {};
  } catch {
    return {};
  }
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const variant = url.searchParams.get("variant");

  // Try Django first
  const djangoPath = variant ? `/api/profile?variant=${encodeURIComponent(variant)}` : "/api/profile";
  const django = await djangoJsonResponse(djangoPath);
  if (django) return django;

  // Fallback: direct file access
  const profile = resolveProfile(variant || undefined);
  const variants = listVariants();
  return Response.json({ profile, variants, active_variant: variant });
}

export async function POST(req: Request) {
  let patch: ProfilePatch;
  try {
    patch = (await req.json()) as ProfilePatch;
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }
  const proposed = patchToProfile(patch);
  if (Object.keys(proposed).length === 0) return Response.json({ error: "nothing to write" }, { status: 400 });

  const django = await djangoJsonResponse("/api/profile", { method: "POST", body: JSON.stringify(patch) });
  if (django) return django;

  // Fallback: direct file write
  const root = careerOpsRoot();
  const file = path.join(root, "config", "profile.yml");
  let base: Record<string, unknown> = {};
  let seeded = false;
  if (!fs.existsSync(file)) {
    try {
      base = (yaml.load(fs.readFileSync(path.join(root, "config", "profile.example.yml"), "utf8")) as Record<string, unknown>) || {};
      seeded = Object.keys(base).length > 0;
    } catch {
      base = {};
    }
  } else {
    let parsed: unknown;
    try {
      parsed = yaml.load(fs.readFileSync(file, "utf8"));
    } catch {
      return Response.json({ error: "config/profile.yml exists but is not valid YAML" }, { status: 409 });
    }
    base = isObj(parsed) ? (parsed as Record<string, unknown>) : {};
  }
  const merged = deepMerge(base, proposed);
  try {
    atomicWriteWithBackup(file, yaml.dump(merged, { lineWidth: 100, noRefs: true }));
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "write failed" }, { status: 500 });
  }
  return Response.json({ ok: true, seeded });
}

export async function PATCH(req: Request) {
  let patch: ProfilePatch;
  try {
    patch = (await req.json()) as ProfilePatch;
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }

  const url = new URL(req.url);
  const variant = url.searchParams.get("variant");
  const djangoPath = variant ? `/api/profile?variant=${encodeURIComponent(variant)}` : "/api/profile";
  const django = await djangoJsonResponse(djangoPath, { method: "PATCH", body: JSON.stringify(patch) });
  if (django) return django;

  // Fallback: direct file write
  const root = careerOpsRoot();
  if (variant) {
    const dir = path.join(root, "config", "profiles");
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${variant}.yml`);
    const existing = loadVariant(variant);
    const merged = deepMerge(existing, patch);
    try {
      atomicWriteWithBackup(file, yaml.dump(merged, { lineWidth: 100, noRefs: true }));
    } catch (e) {
      return Response.json({ error: e instanceof Error ? e.message : "write failed" }, { status: 500 });
    }
  } else {
    const file = path.join(root, "config", "profile.yml");
    const base = loadBaseProfile();
    const merged = deepMerge(base, patch);
    try {
      atomicWriteWithBackup(file, yaml.dump(merged, { lineWidth: 100, noRefs: true }));
    } catch (e) {
      return Response.json({ error: e instanceof Error ? e.message : "write failed" }, { status: 500 });
    }
  }
  return Response.json({ ok: true, variant });
}
