import fs from "node:fs";
import path from "node:path";
import { careerOpsRoot } from "@/lib/career-ops";
import { djangoResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function DELETE(_req: Request, context: { params: Promise<{ name: string }> }) {
  const { name } = await context.params;

  const django = await djangoResponse(`/api/profile/variants/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (django) return django;

  const file = path.join(careerOpsRoot(), "config", "profiles", `${name}.yml`);
  if (fs.existsSync(file)) {
    fs.unlinkSync(file);
    return Response.json({ ok: true });
  }
  return Response.json({ error: "variant not found" }, { status: 404 });
}
