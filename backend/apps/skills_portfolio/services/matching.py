"""Matching and benchmarking helpers — compare a user's competencies against
market standards for a target role.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.skills_portfolio.models import SkillCompetency, SkillDevelopmentAction

from .extraction import benchmark_competency, generate_development_plan
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


def benchmark_all_validated(
    client: LLMClient,
    target_role: str,
) -> dict[str, Any]:
    """Benchmark every validated competency against the target role.

    Returns ``{"results": [...], "target_role": "..."}``.
    """
    competencies = SkillCompetency.objects.filter(status="validated")
    results: list[dict[str, Any]] = []

    for comp in competencies:
        bench = benchmark_competency(client, comp, target_role)
        results.append({
            "competency_id": comp.id,
            "label": comp.label,
            "mastery_level": comp.mastery_level,
            "benchmark": bench,
        })

    return {"results": results, "target_role": target_role}


def generate_plan_for_gaps(
    client: LLMClient,
    target_role: str,
    *,
    create_actions: bool = False,
) -> dict[str, Any]:
    """For every validated competency with a gap, generate a development plan.

    If *create_actions* is True, SkillDevelopmentAction objects are persisted.
    """
    competencies = SkillCompetency.objects.filter(status="validated")
    plans: list[dict[str, Any]] = []

    for comp in competencies:
        bench = benchmark_competency(client, comp, target_role)
        gap = bench.get("gap", "none")
        if gap in ("none", "minor"):
            continue

        target_level = bench.get("market_level", comp.mastery_level)
        plan = generate_development_plan(client, comp, target_level, target_role)

        if create_actions and "actions" in plan:
            for act in plan["actions"]:
                SkillDevelopmentAction.objects.create(
                    competency=comp,
                    target_level=target_level,
                    reason=bench.get("recommendation", ""),
                    actions=[act.get("action", "")],
                    resources=act.get("resources", []),
                    status="planned",
                )

        plans.append({
            "competency_id": comp.id,
            "label": comp.label,
            "current_level": comp.mastery_level,
            "target_level": target_level,
            "gap": gap,
            "plan": plan,
        })

    return {"plans": plans, "target_role": target_role}
