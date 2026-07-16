"""Integration services — bridge the skills portfolio with other career-ops
modules (evaluation, CV, interview, discovery, upskill).

These services consume validated competencies and produce module-specific outputs.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.skills_portfolio.models import SkillCompetency

from .llm_client import LLMClient

logger = logging.getLogger(__name__)


def _format_competencies_block() -> str:
    """Format all validated competencies into a text block for LLM prompts."""
    comps = SkillCompetency.objects.filter(status="validated").prefetch_related("evidence", "experiences")
    if not comps.exists():
        return "Aucune compétence validée."

    lines: list[str] = []
    for c in comps:
        ev_count = c.evidence.count()
        exp_titles = ", ".join(e.title for e in c.experiences.all()) or "aucune"
        lines.append(
            f"- [{c.get_category_display()}] {c.label} "
            f"(niveau: {c.get_mastery_level_display()}, "
            f"confiance: {c.confidence}, "
            f"preuves: {ev_count}, "
            f"expériences: {exp_titles})"
        )
    return "\n".join(lines)


def _format_experiences_block() -> str:
    """Format experiences into a text block for discovery profile."""
    from apps.skills_portfolio.models import SkillExperience

    exps = SkillExperience.objects.all()
    if not exps.exists():
        return "Aucune expérience."
    lines = []
    for e in exps:
        lines.append(f"- {e.title} ({e.type})" + (f" — {e.organization}" if e.organization else ""))
    return "\n".join(lines)


# ------------------------------------------------------------------
# 1. Validated competencies — deterministic, no LLM
# ------------------------------------------------------------------

def get_validated_competencies() -> dict[str, Any]:
    """Return all validated competencies formatted for consumption by
    other career-ops modules (evaluation, CV, interview, etc.)."""
    comps = SkillCompetency.objects.filter(status="validated").prefetch_related("evidence", "experiences")

    result: list[dict[str, Any]] = []
    for c in comps:
        evidence = [
            {"id": e.id, "title": e.title, "type": e.type, "metric": e.metric}
            for e in c.evidence.all()
        ]
        result.append({
            "id": c.id,
            "label": c.label,
            "formulation": c.formulation,
            "category": c.category,
            "mastery_level": c.mastery_level,
            "confidence": c.confidence,
            "market_keywords": c.market_keywords,
            "tags": c.tags,
            "evidence": evidence,
            "experience_titles": [e.title for e in c.experiences.all()],
        })

    return {
        "count": len(result),
        "competencies": result,
    }


# ------------------------------------------------------------------
# 2. Skill gaps — deterministic, no LLM
# ------------------------------------------------------------------

def compute_skill_gaps(
    expected_labels: list[str],
    expected_categories: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare a list of expected competency labels against validated competencies.
    Returns matched, transferable (same category), and missing competencies.
    No LLM involved — pure set comparison."""
    validated = SkillCompetency.objects.filter(status="validated")
    validated_labels = {c.label.lower(): c for c in validated}

    matched: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []

    for label in expected_labels:
        key = label.lower()
        if key in validated_labels:
            c = validated_labels[key]
            matched.append({
                "expected": label,
                "matched_with": c.label,
                "mastery_level": c.mastery_level,
                "category": c.category,
            })
        else:
            cat = (expected_categories or {}).get(label, "unknown")
            missing.append({
                "expected": label,
                "category": cat,
            })

    # Transferable: validated competencies in same categories as missing ones
    missing_cats = {m["category"] for m in missing if m["category"] != "unknown"}
    transferable = []
    for c in validated:
        if c.category in missing_cats and c.label.lower() not in {m["expected"].lower() for m in missing}:
            # Check if this competency could cover a missing one
            for m in missing:
                if m["category"] == c.category:
                    transferable.append({
                        "missing": m["expected"],
                        "transferable_from": c.label,
                        "category": c.category,
                        "note": "Même catégorie, potentiellement transférable",
                    })
                    break

    return {
        "expected_count": len(expected_labels),
        "matched_count": len(matched),
        "missing_count": len(missing),
        "matched": matched,
        "missing": missing,
        "transferable": transferable,
    }


# ------------------------------------------------------------------
# 3. Discovery profile keywords — deterministic extraction
# ------------------------------------------------------------------

def extract_discovery_keywords() -> dict[str, Any]:
    """Extract search keywords from validated competencies for the discovery
    module's SearchProfile. Deterministic — no LLM."""
    comps = SkillCompetency.objects.filter(status="validated")

    tools: set[str] = set()
    keywords: set[str] = set()
    all_market_keywords: list[str] = []

    for c in comps:
        keywords.add(c.label)
        if c.market_keywords:
            all_market_keywords.extend(c.market_keywords)
            keywords.update(c.market_keywords)
        if c.tags:
            keywords.update(c.tags)

    # Deduplicate and sort
    return {
        "positive_keywords": sorted(keywords),
        "tools": sorted(tools),
        "market_keywords": sorted(set(all_market_keywords)),
        "competency_count": comps.count(),
    }


# ------------------------------------------------------------------
# 4. Apply discovery keywords to portals.yml
# ------------------------------------------------------------------

def apply_discovery_to_portals() -> dict[str, Any]:
    """Merge validated competency keywords into portals.yml title_filter.positive.
    Reads the existing portals.yml, merges keywords, and writes back.
    Returns a summary of what was added."""
    import os
    import yaml
    from pathlib import Path

    portals_path = Path(os.environ.get("PORTALS_YAML", "config/portals.yml"))
    if not portals_path.exists():
        return {"error": "portals.yml not found. Copy templates/portals.example.yml to portals.yml first."}

    keywords = extract_discovery_keywords()
    new_keywords = set(keywords["positive_keywords"])

    with open(portals_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Ensure structure exists
    if "title_filter" not in config:
        config["title_filter"] = {}
    if "positive" not in config["title_filter"]:
        config["title_filter"]["positive"] = []

    existing = set(config["title_filter"]["positive"])
    added = new_keywords - existing

    if added:
        config["title_filter"]["positive"] = sorted(existing | new_keywords)
        with open(portals_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return {
        "added_count": len(added),
        "added_keywords": sorted(added),
        "total_count": len(config["title_filter"]["positive"]),
        "source_competencies": keywords["competency_count"],
    }
