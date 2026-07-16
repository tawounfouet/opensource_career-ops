"""Export the skills portfolio to JSON, Markdown, and CV formats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from apps.core.paths import root_path
from apps.skills_portfolio.models import SkillCompetency, SkillEvidence, SkillExperience, Education
from apps.skills_portfolio.serializers import (
    SkillCompetencySerializer,
    SkillEvidenceSerializer,
    SkillExperienceSerializer,
)


def export_to_json() -> dict[str, Any]:
    """Full portfolio export as a JSON-serializable dict."""
    experiences = SkillExperience.objects.all()
    competencies = SkillCompetency.objects.prefetch_related("experiences", "evidence").all()
    evidence = SkillEvidence.objects.select_related("source_experience").all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "counts": {
            "experiences": experiences.count(),
            "competencies": competencies.count(),
            "evidence": evidence.count(),
        },
        "experiences": SkillExperienceSerializer(experiences, many=True).data,
        "competencies": SkillCompetencySerializer(competencies, many=True).data,
        "evidence": SkillEvidenceSerializer(evidence, many=True).data,
    }


def export_to_json_string() -> str:
    return json.dumps(export_to_json(), ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Profile loader
# ------------------------------------------------------------------


def _load_profile(variant: str | None = None) -> dict[str, Any]:
    """Load config/profile.yml as a dict, with optional variant override.
    Returns empty dict on missing/malformed."""
    import os
    base_path = root_path("config", "profile.yml")
    try:
        base = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    except Exception:
        base = {}

    if variant:
        variant_path = root_path("config", "profiles", f"{variant}.yml")
        try:
            override = yaml.safe_load(variant_path.read_text(encoding="utf-8")) or {}
            base = _deep_merge(base, override)
        except Exception:
            pass

    return base


def _deep_merge(dst: dict, src: dict) -> dict:
    """Deep-merge src onto dst (objects recurse; arrays/scalars replace)."""
    out = dict(dst)
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# ------------------------------------------------------------------
# Markdown export (competency portfolio)
# ------------------------------------------------------------------

_STATUS_ICONS = {
    "validated": "✅",
    "draft": "📝",
    "rejected": "❌",
    "archived": "🗃️",
}

_CATEGORY_LABELS = {
    "hard_skill": "Savoir-faire",
    "soft_skill": "Savoir-être",
    "knowledge": "Savoir",
}


def export_to_markdown() -> str:
    """Render the validated competencies as a clean Markdown document."""
    competencies = SkillCompetency.objects.prefetch_related("evidence", "experiences").all()
    lines: list[str] = ["# Portefeuille de compétences\n"]

    # Group by category
    by_category: dict[str, list] = {}
    for comp in competencies:
        by_category.setdefault(comp.category, []).append(comp)

    for cat_key in ("hard_skill", "soft_skill", "knowledge"):
        items = by_category.get(cat_key, [])
        if not items:
            continue
        cat_label = _CATEGORY_LABELS.get(cat_key, cat_key)
        lines.append(f"\n## {cat_label}\n")

        for c in items:
            icon = _STATUS_ICONS.get(c.status, "")
            mastery = c.get_mastery_level_display()
            lines.append(f"- {icon} **{c.label}** — {mastery}")
            if c.evidence.exists():
                ev_titles = ", ".join(e.title for e in c.evidence.all())
                lines.append(f"  - Preuves : {ev_titles}")
            if c.market_keywords:
                lines.append(f"  - Mots-clés marché : {', '.join(c.market_keywords)}")

    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------
# CV section formatters (Gap 2)
# ------------------------------------------------------------------

_MONTH_NAMES = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
    7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.",
}


def _format_date_fr(date_str: str | None) -> str:
    """Format a YYYY-MM-DD date to 'Mois YYYY' in French. Returns '' if empty."""
    if not date_str:
        return ""
    parts = date_str.split("-")
    year = parts[0]
    if len(parts) >= 2 and parts[1].isdigit():
        month = int(parts[1])
        return f"{_MONTH_NAMES.get(month, parts[1])} {year}"
    return year


def _format_period(start: str | None, end: str | None) -> str:
    """Format a date range like 'sept. 2024 → août 2025'."""
    s = _format_date_fr(start)
    e = _format_date_fr(end)
    if s and e:
        return f"{s} → {e}"
    if s:
        return f"{s} → en cours"
    if e:
        return e
    return ""


def format_experience_section(experiences: list[Any] | None = None) -> str:
    """Render experiences as a CV markdown section.

    Format:
      **Role** — Organization
      *Start → End* · Location
      - Mission/deliverable 1
      - Mission/deliverable 2
    """
    if experiences is None:
        experiences = list(SkillExperience.objects.all())
    if not experiences:
        return ""

    lines: list[str] = ["## Expériences\n"]
    for exp in experiences:
        # Title + organization
        org = f" — {exp.organization}" if exp.organization else ""
        lines.append(f"**{exp.title}{org}**")

        # Period + location
        meta_parts: list[str] = []
        period = _format_period(
            exp.start_date.isoformat() if exp.start_date else None,
            exp.end_date.isoformat() if exp.end_date else None,
        )
        if period:
            meta_parts.append(period)
        if exp.location:
            meta_parts.append(exp.location)
        if meta_parts:
            lines.append(f"*{' · '.join(meta_parts)}*")

        # Bullets: missions > deliverables > outcomes > description
        bullets = exp.missions or exp.deliverables or exp.outcomes or []
        if bullets:
            for item in bullets:
                lines.append(f"- {item}")
        elif exp.description:
            lines.append(f"- {exp.description}")

        lines.append("")  # blank line between entries

    return "\n".join(lines)


def format_education_section(educations: list[Any] | None = None) -> str:
    """Render education as a CV markdown section.

    Format:
      **Degree — Field**
      Institution · Year
    """
    if educations is None:
        educations = list(Education.objects.all())
    if not educations:
        return ""

    lines: list[str] = ["## Formation\n"]
    for edu in educations:
        # Title as degree
        lines.append(f"**{edu.title}**")

        # Institution + period
        meta_parts: list[str] = []
        if edu.institution:
            meta_parts.append(edu.institution)
        period = _format_period(
            edu.start_date.isoformat() if edu.start_date else None,
            edu.end_date.isoformat() if edu.end_date else None,
        )
        if period:
            meta_parts.append(period)
        if meta_parts:
            lines.append(f"*{' · '.join(meta_parts)}*")

        if edu.description:
            lines.append(edu.description)

        lines.append("")

    return "\n".join(lines)


def format_skills_section(competencies: list[Any] | None = None) -> str:
    """Render validated competencies grouped by category.

    Format:
      ## Savoir-faire
      - Compétence 1 (Confirmé)
      - Compétence 2 (Expert)
    """
    if competencies is None:
        competencies = list(
            SkillCompetency.objects.filter(status="validated")
            .prefetch_related("evidence")
        )
    if not competencies:
        return ""

    by_category: dict[str, list] = {}
    for comp in competencies:
        by_category.setdefault(comp.category, []).append(comp)

    lines: list[str] = []
    for cat_key in ("hard_skill", "soft_skill", "knowledge"):
        items = by_category.get(cat_key, [])
        if not items:
            continue
        cat_label = _CATEGORY_LABELS.get(cat_key, cat_key)
        lines.append(f"## {cat_label}\n")
        for c in items:
            mastery = c.get_mastery_level_display()
            lines.append(f"- {c.label} ({mastery})")
        lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------------
# CVData export (Gap 1) — maps portfolio to cv-generator format
# ------------------------------------------------------------------


def export_to_cvdata(variant: str | None = None) -> dict[str, Any]:
    """Convert portfolio models + config/profile.yml into CVData JSON.

    Returns a dict matching the cv-generator's CVData Pydantic model:
    {identity, experiences, education, projects, languages, regulations,
     hard_skills, soft_skills, interests}
    """
    profile = _load_profile(variant)
    candidate = profile.get("candidate", {})
    narrative = profile.get("narrative", {})

    # -- Identity --
    objective = narrative.get("objective", "") or narrative.get("headline", "")
    identity = {
        "name": candidate.get("full_name", ""),
        "title": narrative.get("headline", ""),
        "objective": objective,
        "email": candidate.get("email", ""),
        "phone": candidate.get("phone", ""),
        "location": candidate.get("location", ""),
        "mobility": profile.get("location", {}).get("visa_status", ""),
        "linkedin": candidate.get("linkedin", ""),
    }

    # -- Experiences --
    experiences = []
    for exp in SkillExperience.objects.all():
        # Build bullets from available fields
        bullets = exp.missions or exp.deliverables or exp.outcomes or []
        if not bullets and exp.description:
            bullets = [exp.description]

        experiences.append({
            "start": _format_date_fr(exp.start_date.isoformat() if exp.start_date else None),
            "end": _format_date_fr(exp.end_date.isoformat() if exp.end_date else None) or "Présent",
            "role": exp.title,
            "organization": exp.organization,
            "location": exp.location,
            "missions": bullets,
        })

    # -- Education --
    education = []
    for edu in Education.objects.all():
        # Try to split title into degree + field on "—"
        degree = edu.title
        field = ""
        if "—" in edu.title:
            parts = edu.title.split("—", 1)
            degree = parts[0].strip()
            field = parts[1].strip()

        year = ""
        if edu.end_date:
            year = str(edu.end_date.year)
        elif edu.start_date:
            year = str(edu.start_date.year)

        education.append({
            "year": year,
            "institution": edu.institution,
            "degree": degree,
            "field": field,
        })

    # -- Skills from validated competencies --
    hard_skills: list[str] = []
    soft_skills: list[str] = []
    for comp in SkillCompetency.objects.filter(status="validated"):
        label = comp.formulation or comp.label
        if comp.category == "soft_skill":
            soft_skills.append(label)
        else:
            hard_skills.append(label)

    # -- Languages, interests, regulations from profile --
    languages = profile.get("languages", [])
    interests = profile.get("interests", [])
    regulations = profile.get("regulations", [])

    return {
        "identity": identity,
        "experiences": experiences,
        "education": education,
        "projects": [],
        "languages": languages,
        "regulations": regulations,
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "interests": interests,
    }


# ------------------------------------------------------------------
# Full CV markdown generation (Gap 3)
# ------------------------------------------------------------------


def generate_cv_markdown(variant: str | None = None) -> str:
    """Assemble a complete CV in Markdown from profile + portfolio.

    Sections: Identity, Expériences, Formation, Compétences, Langues,
    Centres d'intérêt.
    """
    profile = _load_profile(variant)
    candidate = profile.get("candidate", {})
    narrative = profile.get("narrative", {})

    lines: list[str] = []

    # -- Header / Identity --
    name = candidate.get("full_name", "")
    if name:
        lines.append(f"# {name}\n")

    headline = narrative.get("headline", "")
    if headline:
        lines.append(f"**{headline}**\n")

    objective = narrative.get("objective", "")
    if objective:
        lines.append(f"{objective}\n")

    # Contact block
    contact_parts: list[str] = []
    if candidate.get("location"):
        contact_parts.append(f"📍 {candidate['location']}")
    if candidate.get("phone"):
        contact_parts.append(f"📞 {candidate['phone']}")
    if candidate.get("email"):
        contact_parts.append(f"✉️ {candidate['email']}")
    if candidate.get("linkedin"):
        contact_parts.append(f"🔗 {candidate['linkedin']}")
    if contact_parts:
        lines.append(" · ".join(contact_parts))
        lines.append("")

    # -- Experiences --
    exp_section = format_experience_section()
    if exp_section:
        lines.append(exp_section)

    # -- Education --
    edu_section = format_education_section()
    if edu_section:
        lines.append(edu_section)

    # -- Skills --
    skills_section = format_skills_section()
    if skills_section:
        lines.append(skills_section)

    # -- Languages --
    languages = profile.get("languages", [])
    if languages:
        lines.append("## Langues\n")
        for lang in languages:
            note = f" — {lang['note']}" if lang.get("note") else ""
            lines.append(f"- **{lang['language']}** : {lang['level']}{note}")
        lines.append("")

    # -- Regulations --
    regulations = profile.get("regulations", [])
    if regulations:
        lines.append("## Réglementation et normes\n")
        for reg in regulations:
            lines.append(f"- {reg}")
        lines.append("")

    # -- Interests --
    interests = profile.get("interests", [])
    if interests:
        lines.append("## Centres d'intérêt\n")
        for interest in interests:
            lines.append(f"- {interest}")
        lines.append("")

    return "\n".join(lines)
