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
  // Find the first { or [ in stdout, try to parse. If trailing junk causes
  // failure, walk backwards from the last }/ ] to find a clean parse.
  const lines = stdout.split("\n");
  for (let i = lines.length - 1; i >= 0; i--) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;
    const firstBrace = trimmed.indexOf("{");
    const firstBracket = trimmed.indexOf("[");
    const start = [firstBrace, firstBracket].filter((x) => x >= 0).sort((a, b) => a - b)[0];
    if (start === undefined) continue;
    try {
      return JSON.parse(trimmed.slice(start));
    } catch {
      continue;
    }
  }
  // Fallback: original behavior
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
  try {
    const { stdout } = await execFileAsync(python, [manage, "shell", "-c", code], {
      cwd: root,
      timeout: timeoutMs,
      maxBuffer: 1024 * 1024 * 20,
    });
    return Response.json(parseJsonFromShell(stdout), { headers: { "Cache-Control": "no-store" } });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500, headers: { "Cache-Control": "no-store" } });
  }
}

function payloadCode(bodyText?: string): string {
  return `json.loads(${JSON.stringify(JSON.stringify(parseRequestJson(bodyText)))})`;
}

async function localFallback(req: Request, pathParts: string[], bodyText?: string): Promise<Response | null> {
  const route = pathParts.join("/");

  if (req.method === "GET" && route === "dashboard") {
    return djangoShellJson(`
import json
from django.db.models import Count
from apps.skills_portfolio.models import SkillCompetency, SkillEvidence, SkillExperience, Education
competencies = SkillCompetency.objects.all()
payload = {
  "experiences": SkillExperience.objects.count(),
  "competencies": competencies.count(),
  "evidence": SkillEvidence.objects.count(),
  "educations": Education.objects.count(),
  "by_status": dict(competencies.values_list("status").annotate(total=Count("id"))),
  "by_category": dict(competencies.values_list("category").annotate(total=Count("id"))),
  "without_evidence": competencies.annotate(evidence_total=Count("evidence")).filter(evidence_total=0).count(),
}
print(json.dumps(payload, default=str, ensure_ascii=False))
`);
  }

  if (route === "experiences") {
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillExperience
from apps.skills_portfolio.serializers import SkillExperienceSerializer
qs = SkillExperience.objects.all()
print(json.dumps({"experiences": SkillExperienceSerializer(qs, many=True).data}, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "POST") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.serializers import SkillExperienceSerializer
serializer = SkillExperienceSerializer(data=${payloadCode(bodyText)})
if serializer.is_valid():
    serializer.save()
    print(json.dumps(serializer.data, default=str, ensure_ascii=False))
else:
    print(json.dumps({"error": "invalid experience", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
  }

  if (route === "competencies") {
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.serializers import SkillCompetencySerializer
qs = SkillCompetency.objects.prefetch_related("experiences", "evidence")
print(json.dumps({"competencies": SkillCompetencySerializer(qs, many=True).data}, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "POST") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.serializers import SkillCompetencySerializer
serializer = SkillCompetencySerializer(data=${payloadCode(bodyText)})
if serializer.is_valid():
    serializer.save()
    print(json.dumps(serializer.data, default=str, ensure_ascii=False))
else:
    print(json.dumps({"error": "invalid competency", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
  }

  const competencyDetailMatch = route.match(/^competencies\/(\d+)$/);
  if (req.method === "PATCH" && competencyDetailMatch) {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.serializers import SkillCompetencySerializer
competency = SkillCompetency.objects.filter(pk=${Number(competencyDetailMatch[1])}).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    serializer = SkillCompetencySerializer(competency, data=${payloadCode(bodyText)}, partial=True)
    if serializer.is_valid():
        serializer.save()
        print(json.dumps(serializer.data, default=str, ensure_ascii=False))
    else:
        print(json.dumps({"error": "invalid competency", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
  }

  if (route === "evidence") {
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillEvidence
from apps.skills_portfolio.serializers import SkillEvidenceSerializer
qs = SkillEvidence.objects.select_related("source_experience")
print(json.dumps({"evidence": SkillEvidenceSerializer(qs, many=True).data}, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "POST") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.serializers import SkillEvidenceSerializer
serializer = SkillEvidenceSerializer(data=${payloadCode(bodyText)})
if serializer.is_valid():
    serializer.save()
    print(json.dumps(serializer.data, default=str, ensure_ascii=False))
else:
    print(json.dumps({"error": "invalid evidence", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
  }

  const validateMatch = route.match(/^competencies\/(\d+)\/validate$/);
  if (req.method === "POST" && validateMatch) {
    return djangoShellJson(`
import json
from django.core.exceptions import ValidationError
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.serializers import SkillCompetencySerializer
competency = SkillCompetency.objects.filter(pk=${Number(validateMatch[1])}).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    try:
        competency.validate()
        print(json.dumps(SkillCompetencySerializer(competency).data, default=str, ensure_ascii=False))
    except ValidationError as exc:
        print(json.dumps({"error": exc.message}, ensure_ascii=False))
`);
  }

  const rejectMatch = route.match(/^competencies\/(\d+)\/reject$/);
  if (req.method === "POST" && rejectMatch) {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.serializers import SkillCompetencySerializer
competency = SkillCompetency.objects.filter(pk=${Number(rejectMatch[1])}).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    competency.reject()
    print(json.dumps(SkillCompetencySerializer(competency).data, default=str, ensure_ascii=False))
`);
  }

  // ------------------------------------------------------------------
  // LLM-assisted endpoints
  // ------------------------------------------------------------------

  if (req.method === "POST" && route === "llm/extract-from-experience") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillExperience
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import extract_from_experience, persist_extracted_competencies
from apps.skills_portfolio.serializers import SkillCompetencySerializer
payload = ${payloadCode(bodyText)}
experience = SkillExperience.objects.filter(pk=payload.get("experience_id")).first()
if experience is None:
    print(json.dumps({"error": "experience not found"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = extract_from_experience(client, experience)
    if "error" in output:
        print(json.dumps(output, ensure_ascii=False))
    else:
        created = []
        if payload.get("persist"):
            objs = persist_extracted_competencies(output, experience)
            created = SkillCompetencySerializer(objs, many=True).data
        print(json.dumps({"extracted": output.get("competencies", []), "created": created, "count": len(created) if payload.get("persist") else len(output.get("competencies", []))}, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/formalize") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import formalize_competency
payload = ${payloadCode(bodyText)}
raw_label = payload.get("raw_label", "").strip()
if not raw_label:
    print(json.dumps({"error": "raw_label is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = formalize_competency(client, raw_label, payload.get("context", ""))
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/suggest-evidence") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import suggest_evidence_questions
payload = ${payloadCode(bodyText)}
competency = SkillCompetency.objects.prefetch_related("experiences").filter(pk=payload.get("competency_id")).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = suggest_evidence_questions(client, competency)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/evaluate-mastery") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import evaluate_mastery
payload = ${payloadCode(bodyText)}
competency = SkillCompetency.objects.prefetch_related("experiences", "evidence").filter(pk=payload.get("competency_id")).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = evaluate_mastery(client, competency)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/clarify-evidence") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import SkillCompetency
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import clarify_evidence
payload = ${payloadCode(bodyText)}
competency = SkillCompetency.objects.prefetch_related("experiences").filter(pk=payload.get("competency_id")).first()
if competency is None:
    print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
else:
    raw = payload.get("raw_evidence", "").strip()
    if not raw:
        print(json.dumps({"error": "raw_evidence is required"}, ensure_ascii=False))
    else:
        client = LLMClient()
        output = clarify_evidence(client, competency, raw)
        print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/benchmark") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.matching import benchmark_all_validated
payload = ${payloadCode(bodyText)}
target = payload.get("target_role", "").strip()
if not target:
    print(json.dumps({"error": "target_role is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = benchmark_all_validated(client, target)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/benchmark-summary") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import benchmark_summary
payload = ${payloadCode(bodyText)}
target = payload.get("target_role", "").strip()
jd = payload.get("jd_text", "").strip()
if not target:
    print(json.dumps({"error": "target_role is required"}, ensure_ascii=False))
elif not jd:
    print(json.dumps({"error": "jd_text is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = benchmark_summary(client, target, jd)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/parse-jd") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import parse_jd
payload = ${payloadCode(bodyText)}
jd = payload.get("jd_text", "").strip()
if not jd:
    print(json.dumps({"error": "jd_text is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = parse_jd(client, jd)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/development-plan") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.matching import generate_plan_for_gaps
payload = ${payloadCode(bodyText)}
target = payload.get("target_role", "").strip()
if not target:
    print(json.dumps({"error": "target_role is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = generate_plan_for_gaps(client, target, create_actions=payload.get("create_actions", False))
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/suggest-cv-bullets") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import suggest_cv_bullets
payload = ${payloadCode(bodyText)}
target = payload.get("target_role", "").strip()
if not target:
    print(json.dumps({"error": "target_role is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = suggest_cv_bullets(client, target)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/suggest-interview-questions") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import suggest_interview_questions
payload = ${payloadCode(bodyText)}
target = payload.get("target_role", "").strip()
if not target:
    print(json.dumps({"error": "target_role is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = suggest_interview_questions(client, target)
    print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/discovery-profile") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import generate_discovery_profile
client = LLMClient()
output = generate_discovery_profile(client)
print(json.dumps(output, default=str, ensure_ascii=False))
`, 120_000);
  }

  // ------------------------------------------------------------------
  // Integration endpoints (deterministic, no LLM)
  // ------------------------------------------------------------------

  if (req.method === "GET" && route === "integration/validated") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.integration import get_validated_competencies
print(json.dumps(get_validated_competencies(), default=str, ensure_ascii=False))
`);
  }

  if (req.method === "POST" && route === "integration/skill-gaps") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.integration import compute_skill_gaps
payload = ${payloadCode(bodyText)}
print(json.dumps(compute_skill_gaps(payload.get("expected_labels", []), payload.get("expected_categories", {})), default=str, ensure_ascii=False))
`);
  }

  if (req.method === "GET" && route === "integration/discovery-keywords") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.integration import extract_discovery_keywords
print(json.dumps(extract_discovery_keywords(), default=str, ensure_ascii=False))
`);
  }

  // ------------------------------------------------------------------
  // Education endpoints
  // ------------------------------------------------------------------

  if (route === "educations") {
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education
from apps.skills_portfolio.serializers import EducationSerializer
qs = Education.objects.prefetch_related("competencies", "education_links")
print(json.dumps({"educations": EducationSerializer(qs, many=True).data}, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "POST") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.serializers import EducationSerializer
serializer = EducationSerializer(data=${payloadCode(bodyText)})
if serializer.is_valid():
    serializer.save()
    print(json.dumps(serializer.data, default=str, ensure_ascii=False))
else:
    print(json.dumps({"error": "invalid education", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
  }

  const educationDetailMatch = route.match(/^educations\/(\d+)$/);
  if (educationDetailMatch) {
    const eduId = Number(educationDetailMatch[1]);
    if (req.method === "GET") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education
from apps.skills_portfolio.serializers import EducationSerializer
edu = Education.objects.prefetch_related("competencies", "education_links").filter(pk=${eduId}).first()
if edu is None:
    print(json.dumps({"error": "education not found"}, ensure_ascii=False))
else:
    print(json.dumps(EducationSerializer(edu).data, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "PATCH") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education
from apps.skills_portfolio.serializers import EducationSerializer
edu = Education.objects.filter(pk=${eduId}).first()
if edu is None:
    print(json.dumps({"error": "education not found"}, ensure_ascii=False))
else:
    serializer = EducationSerializer(edu, data=${payloadCode(bodyText)}, partial=True)
    if serializer.is_valid():
        serializer.save()
        print(json.dumps(serializer.data, default=str, ensure_ascii=False))
    else:
        print(json.dumps({"error": "invalid education", "details": serializer.errors}, default=str, ensure_ascii=False))
`);
    }
    if (req.method === "DELETE") {
      return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education
edu = Education.objects.filter(pk=${eduId}).first()
if edu is None:
    print(json.dumps({"error": "education not found"}, ensure_ascii=False))
else:
    edu.delete()
    print(json.dumps({"ok": True}, ensure_ascii=False))
`);
    }
  }

  const eduAttachMatch = route.match(/^educations\/(\d+)\/attach-competency$/);
  if (req.method === "POST" && eduAttachMatch) {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education, EducationCompetency, SkillCompetency
from apps.skills_portfolio.serializers import EducationSerializer
edu = Education.objects.filter(pk=${Number(eduAttachMatch[1])}).first()
if edu is None:
    print(json.dumps({"error": "education not found"}, ensure_ascii=False))
else:
    payload = ${payloadCode(bodyText)}
    comp_id = payload.get("competency_id")
    if not comp_id:
        print(json.dumps({"error": "competency_id is required"}, ensure_ascii=False))
    else:
        comp = SkillCompetency.objects.filter(pk=comp_id).first()
        if comp is None:
            print(json.dumps({"error": "competency not found"}, ensure_ascii=False))
        else:
            link, _ = EducationCompetency.objects.get_or_create(education=edu, competency=comp, defaults={"relevance": payload.get("relevance", "acquired")})
            print(json.dumps(EducationSerializer(edu).data, default=str, ensure_ascii=False))
`);
  }

  const eduDetachMatch = route.match(/^educations\/(\d+)\/detach-competency$/);
  if (req.method === "POST" && eduDetachMatch) {
    return djangoShellJson(`
import json
from apps.skills_portfolio.models import Education, EducationCompetency
from apps.skills_portfolio.serializers import EducationSerializer
edu = Education.objects.filter(pk=${Number(eduDetachMatch[1])}).first()
if edu is None:
    print(json.dumps({"error": "education not found"}, ensure_ascii=False))
else:
    payload = ${payloadCode(bodyText)}
    deleted, _ = EducationCompetency.objects.filter(education=edu, competency_id=payload.get("competency_id")).delete()
    if deleted == 0:
        print(json.dumps({"error": "link not found"}, ensure_ascii=False))
    else:
        print(json.dumps(EducationSerializer(edu).data, default=str, ensure_ascii=False))
`);
  }

  if (req.method === "POST" && route === "llm/extract-education") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import extract_education_from_text, persist_extracted_educations
from apps.skills_portfolio.serializers import EducationSerializer
from apps.skills_portfolio.models import SkillExperience
payload = ${payloadCode(bodyText)}
text = payload.get("text", "").strip()
if not text:
    print(json.dumps({"error": "text is required"}, ensure_ascii=False))
else:
    exp = None
    if payload.get("experience_id"):
        exp = SkillExperience.objects.filter(pk=payload["experience_id"]).first()
    client = LLMClient()
    output = extract_education_from_text(client, text)
    if "error" in output:
        print(json.dumps(output, ensure_ascii=False))
    else:
        created = []
        if payload.get("persist"):
            objs = persist_extracted_educations(output, exp)
            created = EducationSerializer(objs, many=True).data
        print(json.dumps({"extracted": output.get("educations", []), "created": created, "count": len(created) if payload.get("persist") else len(output.get("educations", []))}, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/extract-experience") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import extract_experiences_from_text, persist_extracted_experiences
from apps.skills_portfolio.serializers import SkillExperienceSerializer
payload = ${payloadCode(bodyText)}
text = payload.get("text", "").strip()
if not text:
    print(json.dumps({"error": "text is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = extract_experiences_from_text(client, text)
    if "error" in output:
        print(json.dumps(output, ensure_ascii=False))
    else:
        created = []
        if payload.get("persist"):
            objs = persist_extracted_experiences(output)
            created = SkillExperienceSerializer(objs, many=True).data
        print(json.dumps({"extracted": output.get("experiences", []), "created": created, "count": len(created) if payload.get("persist") else len(output.get("experiences", []))}, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/extract-profile") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import extract_profile_from_text
payload = ${payloadCode(bodyText)}
text = payload.get("text", "").strip()
if not text:
    print(json.dumps({"error": "text is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = extract_profile_from_text(client, text)
    if "error" in output:
        print(json.dumps(output, ensure_ascii=False))
    else:
        persist = payload.get("persist", False)
        variant = payload.get("variant")
        applied = {}
        if persist:
            import yaml
            from pathlib import Path
            if variant:
                profile_path = Path("config/profiles") / f"{variant}.yml"
            else:
                profile_path = Path("config/profile.yml")
            if not profile_path.exists():
                print(json.dumps({"error": f"Profile file not found: {profile_path}"}, ensure_ascii=False))
            else:
                with open(profile_path) as f:
                    doc = yaml.safe_load(f) or {}
                candidate = output.get("candidate", {})
                narrative = output.get("narrative", {})
                languages = output.get("languages", [])
                interests = output.get("interests", [])
                regulations = output.get("regulations", [])
                compensation = output.get("compensation", {})
                location_detail = output.get("location_detail", {})
                if candidate.get("full_name"):
                    doc.setdefault("candidate", {})["full_name"] = candidate["full_name"]
                    applied["full_name"] = candidate["full_name"]
                if candidate.get("email"):
                    doc.setdefault("candidate", {})["email"] = candidate["email"]
                    applied["email"] = candidate["email"]
                if candidate.get("phone"):
                    doc.setdefault("candidate", {})["phone"] = candidate["phone"]
                    applied["phone"] = candidate["phone"]
                if candidate.get("location"):
                    doc.setdefault("candidate", {})["location"] = candidate["location"]
                    applied["location"] = candidate["location"]
                if candidate.get("linkedin"):
                    doc.setdefault("candidate", {})["linkedin"] = candidate["linkedin"]
                    applied["linkedin"] = candidate["linkedin"]
                if candidate.get("portfolio_url"):
                    doc.setdefault("candidate", {})["portfolio_url"] = candidate["portfolio_url"]
                    applied["portfolio_url"] = candidate["portfolio_url"]
                if candidate.get("github"):
                    doc.setdefault("candidate", {})["github"] = candidate["github"]
                    applied["github"] = candidate["github"]
                if narrative.get("headline"):
                    doc.setdefault("narrative", {})["headline"] = narrative["headline"]
                    applied["headline"] = narrative["headline"]
                if narrative.get("exit_story"):
                    doc.setdefault("narrative", {})["exit_story"] = narrative["exit_story"]
                    applied["exit_story"] = narrative["exit_story"]
                if narrative.get("superpowers"):
                    doc.setdefault("narrative", {})["superpowers"] = narrative["superpowers"]
                    applied["superpowers"] = narrative["superpowers"]
                if languages:
                    doc["languages"] = languages
                    applied["languages"] = languages
                if interests:
                    existing_interests = doc.get("interests", [])
                    merged = list(set(existing_interests + interests))
                    doc["interests"] = merged
                    applied["interests"] = merged
                if regulations:
                    existing_regs = doc.get("regulations", [])
                    merged = list(set(existing_regs + regulations))
                    doc["regulations"] = merged
                    applied["regulations"] = merged
                if compensation.get("target_range"):
                    doc.setdefault("compensation", {})["target_range"] = compensation["target_range"]
                    applied["comp_target"] = compensation["target_range"]
                if compensation.get("currency"):
                    doc.setdefault("compensation", {})["currency"] = compensation["currency"]
                    applied["comp_currency"] = compensation["currency"]
                if location_detail.get("country"):
                    doc.setdefault("location", {})["country"] = location_detail["country"]
                    applied["country"] = location_detail["country"]
                if location_detail.get("city"):
                    doc.setdefault("location", {})["city"] = location_detail["city"]
                    applied["city"] = location_detail["city"]
                if location_detail.get("visa_status"):
                    doc.setdefault("location", {})["visa_status"] = location_detail["visa_status"]
                    applied["visa_status"] = location_detail["visa_status"]
                with open(profile_path, "w") as f:
                    yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(json.dumps({"extracted": output, "applied": applied, "count": len(applied)}, default=str, ensure_ascii=False))
`, 120_000);
  }

  if (req.method === "POST" && route === "llm/extract-portal") {
    const portalsAbsPath = path.join(repoRoot(), "config", "portals.yml");
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.extraction import extract_portal_from_text
payload = ${payloadCode(bodyText)}
text = payload.get("text", "").strip()
if not text:
    print(json.dumps({"error": "text is required"}, ensure_ascii=False))
else:
    client = LLMClient()
    output = extract_portal_from_text(client, text)
    if "error" in output:
        print(json.dumps(output, ensure_ascii=False))
    else:
        persist = payload.get("persist", False)
        appended = False
        if persist:
            import yaml
            from pathlib import Path
            portals_path = Path(${JSON.stringify(portalsAbsPath)})
            if not portals_path.exists():
                print(json.dumps({"error": "portals.yml not found"}, ensure_ascii=False))
            else:
                with open(portals_path) as f:
                    doc = yaml.safe_load(f) or {}
                companies = doc.get("tracked_companies", [])
                existing_names = {c.get("name", "").lower() for c in companies}
                if output["name"].lower() in existing_names:
                    print(json.dumps({"extracted": output, "appended": False, "error": f"Company '{output['name']}' already exists"}, ensure_ascii=False))
                else:
                    entry = {"name": output["name"], "careers_url": output["careers_url"]}
                    if output.get("api"):
                        entry["api"] = output["api"]
                    if output.get("scan_method") == "websearch":
                        entry["scan_method"] = "websearch"
                        if output.get("scan_query"):
                            entry["scan_query"] = output["scan_query"]
                    if output.get("notes"):
                        entry["notes"] = output["notes"]
                    entry["enabled"] = True
                    companies.append(entry)
                    doc["tracked_companies"] = companies
                    with open(portals_path, "w") as f:
                        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    appended = True
        print(json.dumps({"extracted": output, "appended": appended}, default=str, ensure_ascii=False))
`, 120_000);
  }

  // ------------------------------------------------------------------
  // Export endpoints
  // ------------------------------------------------------------------

  if (req.method === "GET" && route === "export/json") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.exports import export_to_json
print(json.dumps(export_to_json(), default=str, ensure_ascii=False))
`);
  }

  if (req.method === "GET" && route === "export/markdown") {
    return djangoShellJson(`
from apps.skills_portfolio.services.exports import export_to_markdown
print(export_to_markdown())
`);
  }

  if (req.method === "GET" && route === "export/cvdata") {
    const url = new URL(req.url);
    const variant = url.searchParams.get("variant") || "None";
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.exports import export_to_cvdata
v = ${JSON.stringify(variant)} if ${JSON.stringify(variant)} != "None" else None
print(json.dumps(export_to_cvdata(variant=v), default=str, ensure_ascii=False))
`);
  }

  if (req.method === "GET" && route === "export/cv-markdown") {
    const url = new URL(req.url);
    const variant = url.searchParams.get("variant") || "None";
    return djangoShellJson(`
from apps.skills_portfolio.services.exports import generate_cv_markdown
v = ${JSON.stringify(variant)} if ${JSON.stringify(variant)} != "None" else None
print(generate_cv_markdown(variant=v))
`);
  }

  if (req.method === "POST" && route === "integration/apply-discovery") {
    return djangoShellJson(`
import json
from apps.skills_portfolio.services.integration import apply_discovery_to_portals
print(json.dumps(apply_discovery_to_portals(), default=str, ensure_ascii=False))
`);
  }

  return null;
}

async function proxy(req: Request, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const url = new URL(req.url);
  const query = url.search || "";
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  const django = await djangoResponse(`/api/skills/${path.join("/")}${query}`, {
    method: req.method,
    body,
    headers: body ? { "Content-Type": req.headers.get("Content-Type") || "application/json" } : undefined,
    timeoutMs: 120_000,
  });
  if (django) return django;
  const local = await localFallback(req, path, body);
  if (local) return local;
  return Response.json({ error: "Django skills API unavailable" }, { status: 503 });
}

export function GET(req: Request, context: RouteContext) {
  return proxy(req, context);
}

export function POST(req: Request, context: RouteContext) {
  return proxy(req, context);
}

export function PATCH(req: Request, context: RouteContext) {
  return proxy(req, context);
}
