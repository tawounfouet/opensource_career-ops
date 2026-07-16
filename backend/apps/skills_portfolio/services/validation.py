"""Structural validation of LLM outputs before persisting to the database.

These validators NEVER fabricate content — they only check that the LLM
response conforms to the expected JSON schema.
"""

from __future__ import annotations

from typing import Any

# Allowed values matching the model choices in models.py
_VALID_CATEGORIES = {"knowledge", "hard_skill", "soft_skill"}
_VALID_MASTERY = {"beginner", "junior", "confirmed", "expert"}
_VALID_CONFIDENCE = {"high", "medium", "low"}
_VALID_GAPS = {"none", "minor", "moderate", "significant"}
_VALID_ACTION_TYPES = {"training", "practice", "certification", "mentorship", "project"}

_REQUIRED_COMPETENCY_FIELDS = {"label", "formulation", "category", "mastery_level", "confidence"}


def validate_extraction_output(output: dict[str, Any]) -> list[str]:
    """Validate the structure of an extraction response.  Returns a list of
    human-readable error strings (empty = valid)."""
    errors: list[str] = []

    if not isinstance(output, dict):
        return ["Response is not a JSON object"]

    competencies = output.get("competencies")
    if not isinstance(competencies, list):
        return ["Missing or non-list 'competencies' key"]

    if len(competencies) == 0:
        errors.append("No competencies extracted")
        return errors

    for i, comp in enumerate(competencies):
        if not isinstance(comp, dict):
            errors.append(f"Competency #{i}: not a JSON object")
            continue

        missing = _REQUIRED_COMPETENCY_FIELDS - set(comp.keys())
        if missing:
            errors.append(f"Competency #{i}: missing fields {sorted(missing)}")

        cat = comp.get("category", "")
        if cat and cat not in _VALID_CATEGORIES:
            errors.append(f"Competency #{i}: invalid category '{cat}'")

        mastery = comp.get("mastery_level", "")
        if mastery and mastery not in _VALID_MASTERY:
            errors.append(f"Competency #{i}: invalid mastery_level '{mastery}'")

        conf = comp.get("confidence", "")
        if conf and conf not in _VALID_CONFIDENCE:
            errors.append(f"Competency #{i}: invalid confidence '{conf}'")

    return errors


def validate_formalize_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    formula = output.get("formulation", "")
    if not formula or not isinstance(formula, str):
        errors.append("Missing or empty 'formulation'")
    elif len(formula) > 300:
        errors.append(f"Formulation too long ({len(formula)} chars, max 300)")
    return errors


def validate_suggest_evidence_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    questions = output.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        errors.append("Missing or empty 'questions' list")
    return errors


def validate_benchmark_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    gap = output.get("gap", "")
    if gap and gap not in _VALID_GAPS:
        errors.append(f"Invalid gap value '{gap}'")
    if not output.get("recommendation"):
        errors.append("Missing 'recommendation'")
    return errors


def validate_development_plan_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    actions = output.get("actions")
    if not isinstance(actions, list) or len(actions) == 0:
        errors.append("Missing or empty 'actions' list")
        return errors
    for i, action in enumerate(actions):
        atype = action.get("type", "")
        if atype and atype not in _VALID_ACTION_TYPES:
            errors.append(f"Action #{i}: invalid type '{atype}'")
    return errors


# French mastery levels used in the LLM output (accents are expected)
_VALID_MASTERY_FR = {"debutant", "junior", "confirmé", "expert"}


def validate_mastery_evaluation_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    mastery = output.get("mastery_level", "")
    if mastery and mastery not in _VALID_MASTERY_FR and mastery not in _VALID_MASTERY:
        errors.append(f"Invalid mastery_level '{mastery}'")
    if not output.get("rationale"):
        errors.append("Missing 'rationale'")
    conf = output.get("confidence", "")
    if conf and conf not in _VALID_CONFIDENCE:
        errors.append(f"Invalid confidence '{conf}'")
    questions = output.get("missing_evidence_questions")
    if questions is not None and (not isinstance(questions, list) or len(questions) == 0):
        errors.append("'missing_evidence_questions' must be a non-empty list when present")
    return errors


def validate_clarify_evidence_output(output: dict[str, Any]) -> list[str]:
    _VALID_EVIDENCE_TYPES = {
        "deliverable", "metric", "feedback", "certificate",
        "portfolio_link", "report", "story", "document", "other",
    }
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    title = output.get("title", "")
    if not title or not isinstance(title, str):
        errors.append("Missing or empty 'title'")
    etype = output.get("type", "")
    if etype and etype not in _VALID_EVIDENCE_TYPES:
        errors.append(f"Invalid evidence type '{etype}'")
    desc = output.get("description", "")
    if not desc or not isinstance(desc, str):
        errors.append("Missing or empty 'description'")
    return errors


# ------------------------------------------------------------------
# JD parsing validation
# ------------------------------------------------------------------

_VALID_REQUIREMENTS = {"required", "preferred", "implicit"}


def validate_jd_parsing_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    competencies = output.get("expected_competencies")
    if not isinstance(competencies, list) or len(competencies) == 0:
        errors.append("Missing or empty 'expected_competencies' list")
        return errors
    for i, comp in enumerate(competencies):
        if not isinstance(comp, dict):
            errors.append(f"Competency #{i}: not a JSON object")
            continue
        if not comp.get("label"):
            errors.append(f"Competency #{i}: missing 'label'")
        cat = comp.get("category", "")
        if cat and cat not in _VALID_CATEGORIES:
            errors.append(f"Competency #{i}: invalid category '{cat}'")
        req = comp.get("requirement", "")
        if req and req not in _VALID_REQUIREMENTS:
            errors.append(f"Competency #{i}: invalid requirement '{req}'")
        lvl = comp.get("min_level", "")
        if lvl and lvl not in _VALID_MASTERY:
            errors.append(f"Competency #{i}: invalid min_level '{lvl}'")
    return errors


# ------------------------------------------------------------------
# Benchmark summary validation
# ------------------------------------------------------------------

_VALID_FIT_LABELS = {"excellent", "good", "partial", "weak", "poor"}
_VALID_MATCH_TYPES = {"exact", "transferable", "partial"}


def validate_benchmark_summary_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    fit_label = output.get("fit_label", "")
    if fit_label and fit_label not in _VALID_FIT_LABELS:
        errors.append(f"Invalid fit_label '{fit_label}'")
    if not output.get("summary"):
        errors.append("Missing 'summary'")
    for key in ("strong_matches", "transferable_matches", "gaps"):
        val = output.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"'{key}' must be a list when present")
    return errors


# ------------------------------------------------------------------
# CV bullets validation
# ------------------------------------------------------------------

def validate_cv_bullets_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    bullets = output.get("bullets")
    if not isinstance(bullets, list) or len(bullets) == 0:
        errors.append("Missing or empty 'bullets' list")
        return errors
    for i, b in enumerate(bullets):
        if not isinstance(b, dict):
            errors.append(f"Bullet #{i}: not a JSON object")
            continue
        if not b.get("bullet"):
            errors.append(f"Bullet #{i}: missing 'bullet' text")
        text = b.get("bullet", "")
        if len(text) > 200:
            errors.append(f"Bullet #{i}: too long ({len(text)} chars, max 200)")
    return errors


# ------------------------------------------------------------------
# Interview questions validation
# ------------------------------------------------------------------

_VALID_QUESTION_TYPES = {"technical", "behavioral", "clarification"}


def validate_interview_questions_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    questions = output.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        errors.append("Missing or empty 'questions' list")
        return errors
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            errors.append(f"Question #{i}: not a JSON object")
            continue
        if not q.get("question"):
            errors.append(f"Question #{i}: missing 'question' text")
        qtype = q.get("type", "")
        if qtype and qtype not in _VALID_QUESTION_TYPES:
            errors.append(f"Question #{i}: invalid type '{qtype}'")
    return errors


# ------------------------------------------------------------------
# Discovery profile validation
# ------------------------------------------------------------------

def validate_discovery_profile_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Response is not a JSON object"]
    for key in ("target_titles", "positive_keywords"):
        val = output.get(key)
        if not isinstance(val, list) or len(val) == 0:
            errors.append(f"Missing or empty '{key}' list")
    return errors
