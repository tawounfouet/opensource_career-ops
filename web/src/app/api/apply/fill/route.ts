import { fillSession, handoffSession, getSession } from "@/lib/apply/session";
import { resolveTailoredCv, companyFromTitle } from "@/lib/apply/cv";
import type { ApplyField } from "@/lib/apply/extract";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

declare global {
  // eslint-disable-next-line no-var
  var __coDjangoApplySessions: Set<string> | undefined;
}

const DJANGO_SESSIONS: Set<string> = (globalThis.__coDjangoApplySessions ??= new Set());

// Fill the real form behind the scenes (headed-but-off-screen), screenshotting
// each step for the "behind the scenes" strip, then bring the window to the front
// so the HUMAN reviews and submits. NEVER submits — there is no submit path here.
export async function POST(req: Request) {
  let body: { sessionId?: string; answers?: Record<string, string>; fields?: ApplyField[]; handoff?: boolean; company?: string };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }
  const { sessionId, answers = {}, fields = [], handoff, company } = body;
  if (!sessionId) return Response.json({ error: "sessionId required" }, { status: 400 });
  if (DJANGO_SESSIONS.has(sessionId)) {
    const django = await djangoResponse("/api/apply/fill", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 120_000,
    });
    if (django) {
      return new Response(django.body, {
        status: django.status,
        headers: {
          "Content-Type": django.headers.get("Content-Type") || "application/json",
          "Cache-Control": "no-store",
        },
      });
    }
    DJANGO_SESSIONS.delete(sessionId);
  }

  // Resolve the tailored CV server-side (never trust a client path): by the
  // offer's company if known, else best-effort from the form title.
  const session = getSession(sessionId);
  const cvPath = resolveTailoredCv(company) ?? resolveTailoredCv(companyFromTitle(session?.title)) ?? undefined;

  try {
    const result = await fillSession(sessionId, answers, fields, cvPath);
    if (handoff) await handoffSession(sessionId).catch(() => {});
    return Response.json({ ...result, handedOff: !!handoff, cvAttached: !!cvPath });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message.slice(0, 200) : "fill failed" }, { status: 500 });
  }
}
