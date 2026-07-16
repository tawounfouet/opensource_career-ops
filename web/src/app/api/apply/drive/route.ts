import { getSession, finalizeDrivenSession, extractCurrent, isApplicationFormFn, handoffSession } from "@/lib/apply/session";
import { driveSession } from "@/lib/apply/drive";
import { classifyEmpty } from "@/lib/apply/diagnose";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

declare global {
  // eslint-disable-next-line no-var
  var __coDjangoApplySessions: Set<string> | undefined;
}

const DJANGO_SESSIONS: Set<string> = (globalThis.__coDjangoApplySessions ??= new Set());

// Streamed agentic drive over an OPEN session: the AI drives the headed page to
// REACH a fillable application form (the user watches each step live), then we
// extract + finalize. NEVER submits (enforced in driveSession).
export async function POST(req: Request) {
  let body: { sessionId?: string; cliId?: string; goal?: "reach" | "full"; answers?: { label: string; value: string }[] };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "bad json" }, { status: 400 });
  }
  const { sessionId, cliId = "", goal = "reach", answers } = body;
  if (sessionId && DJANGO_SESSIONS.has(sessionId)) {
    const django = await djangoResponse("/api/apply/drive", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 300_000,
    });
    if (django) {
      return new Response(django.body, {
        status: django.status,
        headers: {
          "Content-Type": django.headers.get("Content-Type") || "application/x-ndjson",
          "Cache-Control": "no-store",
        },
      });
    }
    DJANGO_SESSIONS.delete(sessionId);
  }
  const s = sessionId ? getSession(sessionId) : undefined;
  if (!s) return Response.json({ error: "apply session not found (it may have expired)" }, { status: 404 });

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (o: unknown) => {
        try {
          controller.enqueue(encoder.encode(JSON.stringify(o) + "\n"));
        } catch {
          /* client gone */
        }
      };
      try {
        const page = s.page;
        const isFormReady = async () => {
          try {
            return isApplicationFormFn((await extractCurrent(page, s.url)).form);
          } catch {
            return false;
          }
        };
        const budget = goal === "full" ? 16 : 7;
        const result = await driveSession(page, cliId, goal, isFormReady, (step) => emit({ t: "step", ...step }), budget, answers);

        if (goal === "full") {
          // The agent filled the real form — bring it to the front for the human
          // to review + submit themselves. We never submit.
          if (result.reached) await handoffSession(s.id).catch(() => {});
          emit({ t: "done", filled: result.reached, turns: result.turns, reason: result.reason });
          controller.close();
          return;
        }

        if (result.reached) {
          const fin = await finalizeDrivenSession(s.id, cliId);
          if (fin) {
            emit({ t: "done", reached: true, turns: result.turns, title: fin.title, fields: fin.fields, issues: fin.issues });
            controller.close();
            return;
          }
        }
        // Didn't reach a real form → classify why for a clear message.
        const why = await classifyEmpty(page, s.url).catch(() => ({ message: "Couldn't reach a fillable form on this page." }));
        emit({ t: "error", reason: result.reason, message: result.reason === "stuck" ? result.steps.at(-1)?.detail || why.message : why.message });
      } catch (e) {
        emit({ t: "error", message: e instanceof Error ? e.message.slice(0, 160) : "drive failed" });
      } finally {
        controller.close();
      }
    },
  });
  return new Response(stream, { headers: { "Content-Type": "application/x-ndjson", "Cache-Control": "no-store" } });
}
