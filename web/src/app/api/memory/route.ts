import { NextResponse } from "next/server";
import { readMemory, rememberFact } from "@/lib/career-ops";
import { djangoJsonResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const django = await djangoJsonResponse("/api/memory");
  if (django) return django;

  return NextResponse.json({ memory: readMemory() });
}

// Append a durable fact the assistant learned about the user. Written to the
// CANONICAL modes/_profile.md (single source of truth) so the CLI/TUI see it too
// — never a web-only memory store.
export async function POST(req: Request) {
  let b: { fact?: string };
  try {
    b = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  const fact = (b.fact ?? "").toString();
  if (!fact.trim()) return NextResponse.json({ error: "fact required" }, { status: 400 });
  const django = await djangoJsonResponse("/api/memory", { method: "POST", body: JSON.stringify(b) });
  if (django) return django;

  const result = rememberFact(fact);
  if (result === "error") return NextResponse.json({ error: "write failed" }, { status: 500 });
  return NextResponse.json({ ok: true, deduped: result === "deduped" });
}
