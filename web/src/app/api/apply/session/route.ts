import { openSession } from "@/lib/apply/session";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300; // the agentic drive + interpretation fallbacks spawn a planner

declare global {
  // eslint-disable-next-line no-var
  var __coDjangoApplySessions: Set<string> | undefined;
}

const DJANGO_SESSIONS: Set<string> = (globalThis.__coDjangoApplySessions ??= new Set());

// Open a persistent apply session: headed-but-off-screen Chrome opens the real
// form, we extract + tag its fields. The session stays open for fill + handoff.
// cliId enables the agentic fallback (the AI interprets the live form) when
// deterministic extraction is low-confidence.
export async function POST(req: Request) {
  let body: { url?: string; cliId?: string; agent?: boolean; _noApplyBtn?: boolean };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }
  const url = (body.url ?? "").trim();
  if (!/^https?:\/\//i.test(url)) return Response.json({ error: "A valid application URL (https://…) is required" }, { status: 400 });
  const django = await djangoResponse("/api/apply/session", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 45_000,
  });
  if (django?.ok) {
    const session = (await django.json()) as { id?: unknown };
    if (typeof session.id === "string") DJANGO_SESSIONS.add(session.id);
    return Response.json(session, { status: django.status });
  }
  try {
    const session = await openSession(url, body.cliId, body.agent, body._noApplyBtn);
    return Response.json(session);
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message.slice(0, 200) : "could not open the form" }, { status: 500 });
  }
}
