from __future__ import annotations

import os
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from shutil import which

import yaml

from .safe_write import atomic_write
from .paths import career_ops_root, root_path, root_script
from .tracker_parse import parse_applications


def read_text(rel: str) -> str | None:
    try:
        return root_path(*rel.split("/")).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def read_inbox() -> list[dict]:
    md = read_text("data/pipeline.md")
    if not md:
        return []
    jobs = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        marker = stripped[3:4].lower()
        rest = stripped[6:].strip() if stripped.startswith("- [ ]") or stripped.startswith("- [x]") or stripped.startswith("- [X]") else ""
        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 3 or not parts[0]:
            continue
        jobs.append(
            {
                "done": marker == "x",
                "url": parts[0],
                "company": parts[1],
                "role": parts[2],
                "location": parts[3] if len(parts) > 3 and parts[3] else None,
                "compensation": parts[4] if len(parts) > 4 and parts[4] else None,
            }
        )
    return jobs


def read_scan_dates() -> dict[str, str]:
    tsv = read_text("data/scan-history.tsv")
    if not tsv:
        return {}
    dates = {}
    for i, line in enumerate(tsv.splitlines()):
        if i == 0 and line.startswith("url\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        url, first_seen = parts[0], parts[1].strip()
        if url and first_seen and url not in dates:
            dates[url] = first_seen
    return dates


def read_applications() -> list[dict]:
    md = read_text("data/applications.md")
    if not md:
        return []
    return [
        {
            "n": str(row.num),
            "date": row.date,
            "company": row.company,
            "via": row.via,
            "role": row.role,
            "score": row.score,
            "status": row.status,
            "pdf": row.pdf,
            "report": row.report,
            "notes": row.notes,
        }
        for row in parse_applications(md)
    ]


def pipeline_summary() -> dict:
    scan_dates = read_scan_dates()
    inbox = [{**job, "postedAt": scan_dates.get(job["url"])} for job in read_inbox()]
    root = career_ops_root()
    return {"inbox": inbox, "applications": read_applications(), "root": str(root), "rootExists": root.exists()}


def doctor_state() -> dict:
    prereqs = ["cv.md", "config/profile.yml", "modes/_profile.md", "portals.yml"]
    missing = [p for p in prereqs if not root_path(*p.split("/")).exists()]
    has_cv = root_path("cv.md").exists()
    has_data = bool(read_applications()) or any(not j["done"] for j in read_inbox())
    onboarding_needed = bool(missing)
    phase = "first-run" if not has_cv and not has_data else "in-between" if onboarding_needed else "established"
    return {"phase": phase, "onboardingNeeded": onboarding_needed, "missing": missing, "hasCv": has_cv, "hasData": has_data}


def run_node_script(script_name: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    script = root_script(script_name)
    if not script.exists():
        raise FileNotFoundError(str(script))
    env = os.environ.copy()
    return subprocess.run(["node", str(script), *args], cwd=career_ops_root(), env=env, text=True, capture_output=True, timeout=timeout, check=False)


def detect_clis() -> list[dict]:
    names = ["claude", "codex", "opencode", "qwen", "agy", "grok", "copilot"]
    out = []
    from shutil import which

    for name in names:
        out.append({"id": name, "available": which(name) is not None})
    return out


CLI_SPECS = {
    "claude": {"name": "Claude Code", "bin": "claude", "args": lambda prompt: ["-p", prompt]},
    "codex": {"name": "Codex", "bin": "codex", "args": lambda prompt: ["exec", prompt]},
    "gemini": {"name": "Gemini CLI", "bin": "gemini", "args": lambda prompt: ["-p", prompt]},
    "opencode": {"name": "OpenCode", "bin": "opencode", "args": lambda prompt: ["run", prompt]},
    "copilot": {"name": "GitHub Copilot CLI", "bin": "copilot", "args": lambda prompt: ["-p", prompt]},
    "qwen": {"name": "Qwen CLI", "bin": "qwen", "args": lambda prompt: ["-p", prompt]},
    "antigravity": {"name": "Antigravity CLI", "bin": "agy", "args": lambda prompt: ["-p", prompt]},
}


def resolve_cli(cli_id: str) -> dict | None:
    spec = CLI_SPECS.get(cli_id)
    if not spec:
        return None
    bin_path = which(spec["bin"])
    if not bin_path:
        return None
    return {**spec, "id": cli_id, "path": bin_path}


NOTES_START = "<!-- co-web-notes:start -->"
NOTES_END = "<!-- co-web-notes:end -->"


def profile_path() -> Path:
    return root_path("modes", "_profile.md")


def read_memory() -> str:
    try:
        md = profile_path().read_text(encoding="utf-8")
        start = md.index(NOTES_START)
        end = md.index(NOTES_END)
        if end > start:
            return md[start + len(NOTES_START):end].strip()
    except Exception:
        pass
    try:
        return root_path(".career-ops-web", "memory.md").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def remember_fact(fact: str) -> str:
    clean = " ".join(str(fact).strip().split())[:300]
    if not clean:
        return "deduped"
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        md = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        md = ""
    try:
        start = md.index(NOTES_START)
        end = md.index(NOTES_END)
        if end > start:
            if clean in md[start:end]:
                return "deduped"
            atomic_write(path, md[:end] + f"- {clean}\n" + md[end:])
            return "ok"
    except ValueError:
        pass
    if clean in md:
        return "deduped"
    base = md.rstrip() + "\n" if md.strip() else "# Profile customization\n"
    section = f"\n## Notes from the web assistant\n{NOTES_START}\n- {clean}\n{NOTES_END}\n"
    atomic_write(path, base + section)
    return "ok"


def add_followup_log(company: str, num: str | None = None, note: str = "Followed up") -> None:
    from datetime import date

    safe_company = " ".join(str(company).strip().split())
    safe_note = " ".join(str(note or "Followed up").replace("\r", " ").replace("\n", " ").split())
    prefix = f"#{num} " if num is not None and str(num).strip() else ""
    line = f"- {date.today().isoformat()} · {prefix}{safe_company} — {safe_note}\n"
    path = root_path("data", "follow-ups.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Follow-ups\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def canon_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def known_discovery_urls() -> set[str]:
    urls: set[str] = set()
    tsv = read_text("data/scan-history.tsv")
    if tsv:
        for i, row in enumerate(tsv.splitlines()):
            if i == 0 and row.startswith("url\t"):
                continue
            url = row.split("\t")[0].strip()
            if url.startswith(("http://", "https://")):
                urls.add(canon_url(url))
    for job in read_inbox():
        if job.get("url"):
            urls.add(canon_url(job["url"]))
    return urls


def discovery_dedup_lines() -> list[str]:
    companies: set[str] = set()
    roles: set[str] = set()
    for job in read_inbox():
        if job.get("company"):
            companies.add(str(job["company"]).strip())
    for app in read_applications():
        if app.get("company"):
            companies.add(str(app["company"]).strip())
        if app.get("role"):
            roles.add(str(app["role"]).strip())
    lines = []
    comp_list = [c for c in sorted(companies) if c][:120]
    role_list = [r for r in sorted(roles) if r][:60]
    if comp_list:
        lines.append(f"Companies already in the user's pipeline/tracker (don't re-propose these): {', '.join(comp_list)}.")
    if role_list:
        lines.append(f"Roles already tracked: {', '.join(role_list)}.")
    lines.append(f"({len(known_discovery_urls())} posting URLs are already known and will be auto-filtered, so don't worry about matching exact URLs - just skip the companies above.)")
    return lines


def add_offers_to_pipeline(offers: list[dict]) -> dict:
    clean = []
    for offer in offers:
        url = str(offer.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        clean.append(
            {
                "url": url,
                "company": str(offer.get("company") or ""),
                "title": str(offer.get("title") or offer.get("role") or ""),
                "location": str(offer.get("location") or ""),
                "source": str(offer.get("source") or offer.get("ats") or "explorer"),
                "note": str(offer.get("note") or ""),
            }
        )
    if not clean:
        return {"added": 0}
    if not root_script("scan").exists():
        return {"added": 0, "error": "This checkout is data-only - the pipeline writer (scan.mjs) isn't available."}
    code = f"""
import {{ appendToPipeline, appendToScanHistory }} from {json.dumps(root_script("scan").as_uri())};
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => {{ input += d; }});
process.stdin.on("end", () => {{
  try {{
    const offers = JSON.parse(input);
    const date = new Date().toISOString().slice(0, 10);
    appendToPipeline(offers);
    appendToScanHistory(offers, date, "added");
    process.stdout.write(JSON.stringify({{ added: offers.length }}));
  }} catch (e) {{
    process.stdout.write(JSON.stringify({{ added: 0, error: String((e && e.message) || e) }}));
  }}
}});
"""
    child = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        cwd=career_ops_root(),
        input=json.dumps(clean),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    try:
        return json.loads((child.stdout or "{}").strip())
    except json.JSONDecodeError:
        return {"added": 0, "error": (child.stderr or "writer returned no result").strip()[:200]}


def write_temp_portals(filters: dict) -> str:
    try:
        doc = yaml.safe_load(root_path("portals.yml").read_text(encoding="utf-8")) or {}
    except Exception:
        doc = {}
    if filters.get("positive") is not None or filters.get("negative") is not None:
        title_filter = dict(doc.get("title_filter") or {})
        if isinstance(filters.get("positive"), list):
            title_filter["positive"] = [str(v) for v in filters["positive"] if str(v).strip()]
        if isinstance(filters.get("negative"), list):
            title_filter["negative"] = [str(v) for v in filters["negative"] if str(v).strip()]
        doc["title_filter"] = title_filter
    if filters.get("allow") is not None or filters.get("block") is not None or filters.get("alwaysAllow") is not None:
        location_filter = dict(doc.get("location_filter") or {})
        if isinstance(filters.get("allow"), list):
            location_filter["allow"] = [str(v) for v in filters["allow"] if str(v).strip()]
        if isinstance(filters.get("block"), list):
            location_filter["block"] = [str(v) for v in filters["block"] if str(v).strip()]
        if isinstance(filters.get("alwaysAllow"), list):
            location_filter["always_allow"] = [str(v) for v in filters["alwaysAllow"] if str(v).strip()]
        doc["location_filter"] = location_filter
    fd, path = tempfile.mkstemp(prefix="career-ops-portals-", suffix=".yml")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        yaml.safe_dump(doc, handle, sort_keys=False, allow_unicode=True, width=100)
    return path


def count_reports() -> int:
    try:
        return len([p for p in root_path("reports").iterdir() if p.name.endswith(".md")])
    except FileNotFoundError:
        return 0


def build_run_prompt(kind: str, input_text: str, memory: str, today: str) -> str:
    mem = f"\n\nDurable notes about the user (from their profile):\n{memory.strip()}\n" if memory.strip() else ""
    if kind == "research":
        return f"""You are investigating the user's OWN work / portfolio to surface job-search-relevant strengths, headless. Investigate the target (use WebFetch for URLs; read local files if referenced) and report: what it is, why it is impressive, and how to leverage it in their job search - which roles/claims it supports and how to frame it on a CV. Be specific, honest, and encouraging.{mem}

End with EXACTLY one final line: VERDICT: {{0-5 signal strength}}/5 - {{why it helps their search, <=12 words}}

Target: {input_text}"""
    if kind == "pdf":
        return f"""You are generating the user's ATS-optimized, TAILORED CV PDF for application #{input_text}, headless, on their machine. Run the REAL career-ops "pdf" mode - follow modes/pdf.md EXACTLY (do not improvise a format).
1. Read modes/pdf.md, cv.md, config/profile.yml, and the evaluation report at reports/{input_text}-*.md (for the JD keywords + analysis).
2. Tailor the CV per modes/pdf.md. NEVER invent skills - only reword REAL experience using the JD's vocabulary.
3. Fill templates/cv-template.html's placeholders with the tailored content.
4. Render the PDF with node generate-pdf.mjs.
5. Update the tracker PDF column for row #{input_text} from ❌ to ✅.
Do not submit anything anywhere.

End with EXACTLY one final line: VERDICT: {{5 if the PDF was written, else 1}}/5 - {{the output/ path, <=12 words}}"""
    if kind == "fix-portal":
        return f"""A company's job-portal ATS slug is BROKEN. Repair it headless:
1. Run `node verify-portals.mjs --add "{input_text}"`.
2. Open portals.yml and update only the "{input_text}" entry to the suggested working ATS URL.
3. Re-run `node verify-portals.mjs` and confirm it is live.
If no slug variant resolves, say so clearly and leave portals.yml unchanged.

End with EXACTLY one final line: VERDICT: {{5 if now live, else 1}}/5 - {{what you changed, <=12 words}}"""
    return f"""You are running the OFFICIAL career-ops job evaluation, HEADLESS, on the user's own machine. Today is {today}. Run the REAL career-ops evaluation - do NOT improvise your own scoring.

1. Read modes/oferta.md and follow it EXACTLY. Ground the fit in THIS person: read cv.md, config/profile.yml and modes/_profile.md. Use WebFetch to read the posting and mark the report header "Verification: unconfirmed (batch mode)".

2. Persist the result CANONICALLY:
   a. Reserve a report number: run `node reserve-report-num.mjs`.
   b. Write the full report to reports/{{num}}-{{company-slug}}-{today}.md.
   c. Append ONE row to batch/tracker-additions/{{num}}-{{company-slug}}.tsv with status BEFORE score.
   d. Merge into the tracker: run `node merge-tracker.mjs`.

3. NEVER submit an application, fill no forms, contact no one. This is evaluation + persistence ONLY.{mem}

After everything above is written and merged, output EXACTLY one final line, nothing after it:
VERDICT: {{score}}/5 - {{reason in 12 words or fewer}}

Posting URL: {input_text}"""
