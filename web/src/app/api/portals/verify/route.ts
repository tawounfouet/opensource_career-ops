import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { careerOpsRoot, rootScript } from "@/lib/career-ops";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

// Orchestrates the core's verify-portals.mjs (#1016) — the SAME ATS-slug
// validator the CLI uses. Catches the silent 404s that quietly drop a company
// from every future scan (= lost offers). We parse its console output; we do NOT
// reimplement the validation.
//
// NOTE: verify-portals.mjs output is fully buffered when stdout is piped (Node.js
// default for non-TTY). The script can take 60-90s for100+ companies. We work
// around this by writing results to a temp file and reading it back, which avoids
// the buffering issue entirely.
const STATUS: Record<string, "live" | "empty" | "broken" | "skipped"> = {
  "✅": "live",
  "🟡": "empty",
  "❌": "broken",
  "➖": "skipped",
};

const TIMEOUT_MS = 118_000;
const lineRe = /^\s*(✅|🟡|❌|➖)\s+(.+?)\s+—\s+(.*)$/;

export async function GET() {
  const root = careerOpsRoot();
  const verifyPortals = rootScript("verify-portals");
  if (!fs.existsSync(verifyPortals)) {
    return Response.json({ available: false, configured: false, companies: [] });
  }
  if (!fs.existsSync(path.join(root, "portals.yml"))) {
    return Response.json({ available: true, configured: false, companies: [] });
  }

  // Write verify output to a temp file via shell redirect to avoid Node.js
  // piped-stdout buffering (console.log output is fully buffered when not a TTY).
  const tmpFile = path.join(root, ".verify-output.tmp");
  const shell = `node ${JSON.stringify(verifyPortals)} > ${JSON.stringify(tmpFile)} 2>&1`;

  await new Promise<void>((resolve) => {
    execFile(
      "bash",
      ["-c", shell],
      { cwd: root, timeout: TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024, env: process.env },
      () => resolve(), // ignore exit code — partial results are fine
    );
  });

  let output = "";
  try {
    output = fs.readFileSync(tmpFile, "utf8");
    fs.unlinkSync(tmpFile);
  } catch { /* file may not exist if script didn't start */ }

  const companies: { name: string; status: string; detail: string }[] = [];
  for (const line of output.split("\n")) {
    const m = line.match(lineRe);
    if (m) companies.push({ name: m[2].trim(), status: STATUS[m[1]] ?? "unknown", detail: m[3].trim() });
  }
  return Response.json({ available: true, configured: true, companies });
}
