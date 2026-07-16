import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

function repoRoot(): string {
  return path.basename(process.cwd()) === "web" ? path.resolve(process.cwd(), "..") : process.cwd();
}

function parseJsonFromShell(stdout: string): unknown {
  const startObj = stdout.indexOf("{");
  const startArr = stdout.indexOf("[");
  const starts = [startObj, startArr].filter((i) => i >= 0);
  if (!starts.length) throw new Error("Django shell produced no JSON");
  return JSON.parse(stdout.slice(Math.min(...starts)));
}

function parseRequestJson(bodyText?: string): unknown {
  if (!bodyText) return {};
  try {
    return JSON.parse(bodyText);
  } catch {
    return {};
  }
}

async function djangoShellJson(code: string, timeoutMs = 30_000): Promise<Response> {
  const root = repoRoot();
  const python = path.join(root, "backend", ".venv", "bin", "python");
  const manage = path.join(root, "backend", "manage.py");
  const { stdout } = await execFileAsync(python, [manage, "shell", "-c", code], {
    cwd: root,
    timeout: timeoutMs,
    maxBuffer: 1024 * 1024 * 20,
  });
  return Response.json(parseJsonFromShell(stdout), { headers: { "Cache-Control": "no-store" } });
}

async function localFallback(req: Request, pathParts: string[], bodyText?: string): Promise<Response | null> {
  const route = pathParts.join("/");
  if (route === "profile") {
    const profileName = new URL(req.url).searchParams.get("profile") || "default";
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.discovery.models import SearchProfile
from apps.discovery.serializers import SearchProfileSerializer
profile, _ = SearchProfile.objects.get_or_create(name=${JSON.stringify(profileName)})
print(json.dumps(SearchProfileSerializer(profile).data, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "POST") {
      const data = parseRequestJson(bodyText);
      const payloadJson = JSON.stringify(data);
      return djangoShellJson(`
import json
from apps.discovery.models import SearchProfile
from apps.discovery.serializers import SearchProfileSerializer
payload = json.loads(${JSON.stringify(payloadJson)})
profile_name = str(payload.pop("profile", ${JSON.stringify(profileName)}) or "default")
profile, _ = SearchProfile.objects.get_or_create(name=profile_name)
serializer = SearchProfileSerializer(profile, data=payload, partial=True)
if serializer.is_valid():
    serializer.save()
    print(json.dumps(serializer.data, default=str, ensure_ascii=False))
else:
    print(json.dumps({"error": "invalid profile", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
  }

  if (req.method === "GET" && route === "digest/today") {
    return djangoShellJson(`
import json
from django.utils import timezone
from apps.discovery.models import DailyJobDigest, SearchProfile
from apps.discovery.serializers import DailyJobDigestSerializer
profile, _ = SearchProfile.objects.get_or_create(name="default")
digest = DailyJobDigest.objects.filter(profile=profile, date=timezone.localdate()).order_by("-created_at").first()
payload = {"date": timezone.localdate().isoformat(), "items": [], "empty": True} if digest is None else DailyJobDigestSerializer(digest).data
print(json.dumps(payload, default=str, ensure_ascii=False))
`);
  }

  if (req.method === "POST" && route === "run") {
    return djangoShellJson(`
import json
from apps.discovery.models import SearchProfile
from apps.discovery.services.scheduler import run_discovery
profile, _ = SearchProfile.objects.get_or_create(name="default")
print(json.dumps(run_discovery(profile, trigger="manual"), ensure_ascii=False))
`, 180_000);
  }

  const decisionMatch = route.match(/^items\/(\\d+)\/decision$/);
  if (req.method === "POST" && decisionMatch) {
    const body = parseRequestJson(bodyText) as { decision?: unknown; note?: unknown };
    const decision = String(body.decision || "");
    const note = String(body.note || "");
    const itemId = Number(decisionMatch[1]);
    return djangoShellJson(`
import json
from apps.discovery.models import DECISION, DailyJobDigestItem
from apps.discovery.services.exporters import apply_decision
allowed = {value for value, _ in DECISION}
decision = ${JSON.stringify(decision)}
note = ${JSON.stringify(note)}
item = DailyJobDigestItem.objects.get(pk=${itemId})
if decision not in allowed:
    print(json.dumps({"error": f"invalid decision '{decision}'", "allowed": sorted(allowed)}, ensure_ascii=False))
else:
    item = apply_decision(item, decision, note)
    print(json.dumps({"ok": True, "id": item.id, "decision": item.decision}, ensure_ascii=False))
`);
  }

  const exportMatch = route.match(/^items\/(\\d+)\/export-pipeline$/);
  if (req.method === "POST" && exportMatch) {
    const itemId = Number(exportMatch[1]);
    return djangoShellJson(`
import json
from apps.discovery.models import DailyJobDigestItem
from apps.discovery.services.exporters import export_item_to_pipeline
item = DailyJobDigestItem.objects.get(pk=${itemId})
print(json.dumps({"ok": True, **export_item_to_pipeline(item)}, ensure_ascii=False, default=str))
`);
  }

  return null;
}

async function proxy(req: Request, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const url = new URL(req.url);
  const query = url.search || "";
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  const django = await djangoResponse(`/api/discovery/${path.join("/")}${query}`, {
    method: req.method,
    body,
    headers: body ? { "Content-Type": req.headers.get("Content-Type") || "application/json" } : undefined,
    timeoutMs: 120_000,
  });
  if (django) return django;
  const local = await localFallback(req, path, body);
  if (local) return local;
  return Response.json(
    {
      error: "Django discovery API unavailable",
      hint: "Start the backend and set CAREER_OPS_API_URL=http://localhost:8000, or use a supported local fallback route.",
    },
    { status: 503 },
  );
}

export function GET(req: Request, context: RouteContext) {
  return proxy(req, context);
}

export function POST(req: Request, context: RouteContext) {
  return proxy(req, context);
}
