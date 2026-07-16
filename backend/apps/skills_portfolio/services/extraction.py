"""Extract competencies from an experience using the LLM, then persist
draft SkillCompetency objects and record an audit trail.

Core rule: *skills are formalized, never fabricated.*
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from apps.skills_portfolio.models import (
    SkillCompetency,
    SkillEvidence,
    SkillExtractionRun,
    SkillExperience,
)

from .llm_client import LLMClient
from .prompts import (
    BENCHMARK_SYSTEM,
    BENCHMARK_SUMMARY_SYSTEM,
    BENCHMARK_SUMMARY_USER,
    BENCHMARK_USER,
    CLARIFY_EVIDENCE_SYSTEM,
    CLARIFY_EVIDENCE_USER,
    CV_BULLETS_SYSTEM,
    CV_BULLETS_USER,
    DEVELOPMENT_PLAN_SYSTEM,
    DEVELOPMENT_PLAN_USER,
    DISCOVERY_PROFILE_SYSTEM,
    DISCOVERY_PROFILE_USER,
    EDUCATION_EXTRACTION_SYSTEM,
    EDUCATION_EXTRACTION_USER,
    EXPERIENCE_EXTRACTION_SYSTEM,
    EXPERIENCE_EXTRACTION_USER,
    EXTRACTION_SYSTEM,
    EXTRACTION_USER,
    FORMALIZE_SYSTEM,
    FORMALIZE_USER,
    INTERVIEW_QUESTIONS_SYSTEM,
    INTERVIEW_QUESTIONS_USER,
    JD_PARSING_SYSTEM,
    JD_PARSING_USER,
    MASTERY_EVALUATION_SYSTEM,
    MASTERY_EVALUATION_USER,
    SUGGEST_EVIDENCE_SYSTEM,
    SUGGEST_EVIDENCE_USER,
)
from .validation import (
    validate_benchmark_output,
    validate_benchmark_summary_output,
    validate_clarify_evidence_output,
    validate_cv_bullets_output,
    validate_development_plan_output,
    validate_discovery_profile_output,
    validate_extraction_output,
    validate_formalize_output,
    validate_interview_questions_output,
    validate_jd_parsing_output,
    validate_mastery_evaluation_output,
    validate_suggest_evidence_output,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_experience(exp: SkillExperience) -> str:
    """Serialize an experience to a text block suitable for the LLM prompt."""
    lines: list[str] = [f"Titre : {exp.title}"]
    if exp.type:
        lines.append(f"Type : {exp.type}")
    if exp.organization:
        lines.append(f"Organisation : {exp.organization}")
    if exp.description:
        lines.append(f"Description : {exp.description}")
    if exp.missions:
        lines.append(f"Missions : {', '.join(exp.missions)}")
    if exp.deliverables:
        lines.append(f"Livrables : {', '.join(exp.deliverables)}")
    if exp.responsibilities:
        lines.append(f"Responsabilités : {', '.join(exp.responsibilities)}")
    if exp.outcomes:
        lines.append(f"Résultats : {', '.join(exp.outcomes)}")
    if exp.tools:
        lines.append(f"Outils / Technologies : {', '.join(exp.tools)}")
    if exp.people_context:
        lines.append(f"Contexte d'équipe : {exp.people_context}")
    return "\n".join(lines)


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _record_run(
    *,
    experience: SkillExperience | None,
    prompt_template: str,
    input_text: str,
    output: dict[str, Any],
    status: str,
    error: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    client: LLMClient,
) -> SkillExtractionRun:
    return SkillExtractionRun.objects.create(
        experience=experience,
        provider=client.base_url.split("//")[-1].split("/")[0] if client.base_url else "",
        model=client.model,
        prompt_template=prompt_template[:160],
        input_hash=_compute_hash(input_text),
        output_json=output,
        status=status,
        error=error[:1000] if error else "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ------------------------------------------------------------------
# 1. Extract competencies from an experience
# ------------------------------------------------------------------

def extract_from_experience(
    client: LLMClient,
    experience: SkillExperience,
) -> dict[str, Any]:
    """Call the LLM to extract competencies, validate, and return the raw output.

    Returns ``{"competencies": [...]}`` on success, or ``{"error": "..."}``.
    Audit trail is always written to SkillExtractionRun.
    """
    input_text = _format_experience(experience)
    user_prompt = EXTRACTION_USER.format(experience_text=input_text)

    try:
        raw_text = client.complete(EXTRACTION_SYSTEM, user_prompt)
        output = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        _record_run(
            experience=experience,
            prompt_template=EXTRACTION_SYSTEM,
            input_text=input_text,
            output={"raw": raw_text[:2000] if isinstance(raw_text, str) else ""},
            status="failed",
            error=f"JSON parse error: {exc}",
            client=client,
        )
        return {"error": f"LLM returned invalid JSON: {exc}"}
    except Exception as exc:
        _record_run(
            experience=experience,
            prompt_template=EXTRACTION_SYSTEM,
            input_text=input_text,
            output={},
            status="failed",
            error=str(exc),
            client=client,
        )
        return {"error": f"LLM request failed: {exc}"}

    errors = validate_extraction_output(output)
    if errors:
        _record_run(
            experience=experience,
            prompt_template=EXTRACTION_SYSTEM,
            input_text=input_text,
            output=output,
            status="failed",
            error="; ".join(errors),
            client=client,
        )
        return {"error": "; ".join(errors)}

    _record_run(
        experience=experience,
        prompt_template=EXTRACTION_SYSTEM,
        input_text=input_text,
        output=output,
        status="success",
        input_tokens=len(input_text.split()) * 2,
        output_tokens=len(json.dumps(output).split()) * 2,
        client=client,
    )
    return output


def persist_extracted_competencies(
    output: dict[str, Any],
    experience: SkillExperience,
) -> list[SkillCompetency]:
    """Create draft SkillCompetency objects from a validated extraction output."""
    created: list[SkillCompetency] = []
    for comp in output.get("competencies", []):
        c = SkillCompetency.objects.create(
            label=comp["label"],
            formulation=comp["formulation"],
            category=comp.get("category", "hard_skill"),
            action_verb=comp.get("action_verb", ""),
            object=comp.get("object", ""),
            context=comp.get("context", ""),
            mastery_level=comp.get("mastery_level", "junior"),
            confidence=comp.get("confidence", "medium"),
            mastery_rationale=comp.get("rationale", ""),
            status="draft",
            created_by="llm",
        )
        c.experiences.add(experience)
        created.append(c)
    return created


# ------------------------------------------------------------------
# 2. Formalize a raw competency label
# ------------------------------------------------------------------

def formalize_competency(
    client: LLMClient,
    raw_label: str,
    context: str = "",
) -> dict[str, Any]:
    user_prompt = FORMALIZE_USER.format(raw_label=raw_label, context=context or "général")
    try:
        output = client.complete_json(FORMALIZE_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_formalize_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 3. Suggest evidence questions for a competency
# ------------------------------------------------------------------

def suggest_evidence_questions(
    client: LLMClient,
    competency: SkillCompetency,
) -> dict[str, Any]:
    experiences = ", ".join(
        exp.title for exp in competency.experiences.all()
    ) or "aucune"
    user_prompt = SUGGEST_EVIDENCE_USER.format(
        label=competency.label,
        formulation=competency.formulation,
        experiences=experiences,
    )
    try:
        output = client.complete_json(SUGGEST_EVIDENCE_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_suggest_evidence_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 4. Benchmark a competency against the market
# ------------------------------------------------------------------

def benchmark_competency(
    client: LLMClient,
    competency: SkillCompetency,
    target_role: str,
) -> dict[str, Any]:
    user_prompt = BENCHMARK_USER.format(
        label=competency.label,
        mastery_level=competency.get_mastery_level_display(),
        target_role=target_role,
    )
    try:
        output = client.complete_json(BENCHMARK_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_benchmark_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 5. Generate a development plan
# ------------------------------------------------------------------

def generate_development_plan(
    client: LLMClient,
    competency: SkillCompetency,
    target_level: str,
    target_role: str,
) -> dict[str, Any]:
    user_prompt = DEVELOPMENT_PLAN_USER.format(
        label=competency.label,
        current_level=competency.get_mastery_level_display(),
        target_level=target_level,
        target_role=target_role,
        gap_description=f"{competency.mastery_level} → {target_level}",
    )
    try:
        output = client.complete_json(DEVELOPMENT_PLAN_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_development_plan_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 6. Mastery evaluation
# ------------------------------------------------------------------

def evaluate_mastery(
    client: LLMClient,
    competency: SkillCompetency,
) -> dict[str, Any]:
    """Evaluate mastery level of a competency based on its evidence."""
    experiences = ", ".join(exp.title for exp in competency.experiences.all()) or "aucune"
    evidence_items = competency.evidence.all()
    if evidence_items.exists():
        evidence_list = "\n".join(
            f"- [{e.type}] {e.title}: {e.description or 'pas de description'}"
            + (f" (métrique: {e.metric})" if e.metric else "")
            for e in evidence_items
        )
    else:
        evidence_list = "Aucune preuve attachée."

    user_prompt = MASTERY_EVALUATION_USER.format(
        label=competency.label,
        formulation=competency.formulation,
        category=competency.get_category_display(),
        experiences=experiences,
        evidence_list=evidence_list,
        current_level=competency.get_mastery_level_display(),
    )
    try:
        output = client.complete_json(MASTERY_EVALUATION_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_mastery_evaluation_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 7. Clarify evidence
# ------------------------------------------------------------------

def clarify_evidence(
    client: LLMClient,
    competency: SkillCompetency,
    raw_evidence: str,
) -> dict[str, Any]:
    """Help the user formulate a raw proof into a structured evidence."""
    experience_title = competency.experiences.first().title if competency.experiences.exists() else "aucune"

    user_prompt = CLARIFY_EVIDENCE_USER.format(
        label=competency.label,
        raw_evidence=raw_evidence,
        experience_title=experience_title,
    )
    try:
        output = client.complete_json(CLARIFY_EVIDENCE_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_clarify_evidence_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 8. JD parsing — extract expected competencies from a job description
# ------------------------------------------------------------------

def parse_jd(
    client: LLMClient,
    jd_text: str,
) -> dict[str, Any]:
    """Parse a job description and extract expected competencies."""
    user_prompt = JD_PARSING_USER.format(jd_text=jd_text)
    try:
        output = client.complete_json(JD_PARSING_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_jd_parsing_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 9. Full benchmark summary — user profile vs JD expectations
# ------------------------------------------------------------------

def benchmark_summary(
    client: LLMClient,
    target_role: str,
    jd_expectations: str,
) -> dict[str, Any]:
    """Compare all validated competencies against JD expectations in one call."""
    from apps.skills_portfolio.models import SkillCompetency

    validated = SkillCompetency.objects.filter(status="validated").prefetch_related("evidence")
    if not validated.exists():
        return {"error": "No validated competencies to benchmark. Validate at least one competency first."}

    user_lines = []
    for comp in validated:
        evidence_count = comp.evidence.count()
        user_lines.append(
            f"- [{comp.get_category_display()}] {comp.label} "
            f"(niveau: {comp.get_mastery_level_display()}, "
            f"confiance: {comp.confidence}, "
            f"preuves: {evidence_count})"
        )
    user_competencies = "\n".join(user_lines)

    user_prompt = BENCHMARK_SUMMARY_USER.format(
        user_competencies=user_competencies,
        jd_expectations=jd_expectations,
        target_role=target_role,
    )
    try:
        output = client.complete_json(BENCHMARK_SUMMARY_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_benchmark_summary_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 10. CV bullet suggestion
# ------------------------------------------------------------------

def suggest_cv_bullets(
    client: LLMClient,
    target_role: str,
) -> dict[str, Any]:
    """Generate CV bullet points from validated competencies."""
    from .integration import _format_competencies_block

    comps_block = _format_competencies_block()
    if comps_block == "Aucune compétence validée.":
        return {"error": "No validated competencies. Validate at least one competency first."}

    user_prompt = CV_BULLETS_USER.format(
        competencies_block=comps_block,
        target_role=target_role,
    )
    try:
        output = client.complete_json(CV_BULLETS_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_cv_bullets_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 11. Interview questions
# ------------------------------------------------------------------

def suggest_interview_questions(
    client: LLMClient,
    target_role: str,
) -> dict[str, Any]:
    """Generate likely interview questions based on the portfolio."""
    from .integration import _format_competencies_block

    comps_block = _format_competencies_block()
    if comps_block == "Aucune compétence validée.":
        return {"error": "No validated competencies. Validate at least one competency first."}

    user_prompt = INTERVIEW_QUESTIONS_USER.format(
        competencies_block=comps_block,
        target_role=target_role,
    )
    try:
        output = client.complete_json(INTERVIEW_QUESTIONS_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_interview_questions_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 12. Discovery profile
# ------------------------------------------------------------------

def generate_discovery_profile(
    client: LLMClient,
) -> dict[str, Any]:
    """Generate optimized search keywords for the discovery module."""
    from .integration import _format_competencies_block, _format_experiences_block

    comps_block = _format_competencies_block()
    exps_block = _format_experiences_block()
    if comps_block == "Aucune compétence validée.":
        return {"error": "No validated competencies. Validate at least one competency first."}

    user_prompt = DISCOVERY_PROFILE_USER.format(
        competencies_block=comps_block,
        experiences_block=exps_block,
    )
    try:
        output = client.complete_json(DISCOVERY_PROFILE_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    errors = validate_discovery_profile_output(output)
    if errors:
        return {"error": "; ".join(errors)}
    return output


# ------------------------------------------------------------------
# 13. Education extraction — text → education entries
# ------------------------------------------------------------------

def extract_education_from_text(
    client: LLMClient,
    input_text: str,
) -> dict[str, Any]:
    """Extract education entries (formations, certifications, RNCP) from free text."""
    user_prompt = EDUCATION_EXTRACTION_USER.format(input_text=input_text)
    try:
        output = client.complete_json(EDUCATION_EXTRACTION_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    if "educations" not in output:
        return {"error": "LLM response missing 'educations' key"}
    if not isinstance(output["educations"], list):
        return {"error": "'educations' must be a list"}

    return output


def _normalize_date(raw: str | None) -> str | None:
    """Pad partial dates to YYYY-MM-DD (Django DateField requirement).

    "2024" → "2024-01-01", "2024-01" → "2024-01-01", "2024-01-15" → unchanged.
    """
    if not raw:
        return None
    raw = raw.strip()
    parts = raw.split("-")
    if len(parts) == 1:          # YYYY
        return f"{parts[0]}-01-01"
    if len(parts) == 2:          # YYYY-MM
        return f"{parts[0]}-{parts[1]}-01"
    return raw                    # YYYY-MM-DD


def persist_extracted_educations(
    output: dict[str, Any],
    experience: "SkillExperience | None" = None,
) -> list["Education"]:
    """Create Education objects from a validated extraction output."""
    from apps.skills_portfolio.models import Education

    created: list[Education] = []
    for edu in output.get("educations", []):
        obj = Education.objects.create(
            title=edu.get("title", ""),
            institution=edu.get("institution", ""),
            education_type=edu.get("education_type", "formation"),
            status=edu.get("status", "completed"),
            start_date=_normalize_date(edu.get("start_date")),
            end_date=_normalize_date(edu.get("end_date")),
            credential_url=edu.get("credential_url", ""),
            credential_id=edu.get("credential_id", ""),
            hours=edu.get("hours") or None,
            description=edu.get("description", ""),
            experience=experience,
        )
        created.append(obj)
    return created


# ------------------------------------------------------------------
# Experience extraction from free text
# ------------------------------------------------------------------


def extract_experiences_from_text(
    client: LLMClient,
    input_text: str,
) -> dict[str, Any]:
    """Extract experience entries (professional, project, volunteer) from free text."""
    user_prompt = EXPERIENCE_EXTRACTION_USER.format(input_text=input_text)
    try:
        output = client.complete_json(EXPERIENCE_EXTRACTION_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    if "experiences" not in output:
        return {"error": "LLM response missing 'experiences' key"}
    if not isinstance(output["experiences"], list):
        return {"error": "'experiences' must be a list"}

    return output


def persist_extracted_experiences(
    output: dict[str, Any],
) -> list[SkillExperience]:
    """Create SkillExperience objects from a validated extraction output."""
    created: list[SkillExperience] = []
    for exp in output.get("experiences", []):
        obj = SkillExperience.objects.create(
            title=exp.get("title", ""),
            type=exp.get("type", "professional"),
            organization=exp.get("organization", ""),
            start_date=_normalize_date(exp.get("start_date")),
            end_date=_normalize_date(exp.get("end_date")),
            location=exp.get("location", ""),
            description=exp.get("description", ""),
            missions=exp.get("missions", []),
            responsibilities=exp.get("responsibilities", []),
            deliverables=exp.get("deliverables", []),
            outcomes=exp.get("outcomes", []),
            tools=exp.get("tools", []),
        )
        created.append(obj)
    return created


# ------------------------------------------------------------------
# 14. Profile extraction — free text → profile fields
# ------------------------------------------------------------------

def extract_profile_from_text(
    client: LLMClient,
    input_text: str,
) -> dict[str, Any]:
    """Extract profile fields (candidate info, narrative, languages, etc.) from free text."""
    from .prompts import PROFILE_EXTRACTION_SYSTEM, PROFILE_EXTRACTION_USER

    user_prompt = PROFILE_EXTRACTION_USER.format(input_text=input_text)
    try:
        output = client.complete_json(PROFILE_EXTRACTION_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    # Validate structure
    required_keys = ["candidate", "narrative"]
    for key in required_keys:
        if key not in output:
            return {"error": f"LLM response missing '{key}' key"}

    return output


# ------------------------------------------------------------------
# 15. Portal extraction — URL/text → portal config entry
# ------------------------------------------------------------------

def extract_portal_from_text(
    client: LLMClient,
    input_text: str,
) -> dict[str, Any]:
    """Extract portal configuration (company, ATS, API endpoint) from URL or text."""
    from .prompts import PORTAL_EXTRACTION_SYSTEM, PORTAL_EXTRACTION_USER

    user_prompt = PORTAL_EXTRACTION_USER.format(input_text=input_text)
    try:
        output = client.complete_json(PORTAL_EXTRACTION_SYSTEM, user_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    # Validate structure
    required_keys = ["name", "careers_url"]
    for key in required_keys:
        if key not in output:
            return {"error": f"LLM response missing '{key}' key"}

    return output
