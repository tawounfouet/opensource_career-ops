import { closeSession } from "@/lib/apply/session";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

declare global {
  // eslint-disable-next-line no-var
  var __coDjangoApplySessions: Set<string> | undefined;
}

const DJANGO_SESSIONS: Set<string> = (globalThis.__coDjangoApplySessions ??= new Set());

// Explicitly close an apply session (the user hit "new" or left the page) so we
// free the off-screen browser tab promptly instead of waiting for the prune.
export async function POST(req: Request) {
  let body: { sessionId?: string };
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false }, { status: 400 });
  }
  if (body.sessionId && DJANGO_SESSIONS.has(body.sessionId)) {
    await djangoResponse("/api/apply/close", { method: "POST", body: JSON.stringify(body), timeoutMs: 5_000 });
    DJANGO_SESSIONS.delete(body.sessionId);
  } else if (body.sessionId) {
    await closeSession(body.sessionId).catch(() => {});
  }
  return Response.json({ ok: true });
}
