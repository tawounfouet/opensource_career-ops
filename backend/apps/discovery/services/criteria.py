"""Turn a stored SearchProfile into a normalized SearchCriteria for connectors."""

from __future__ import annotations

from ..connectors.base import SearchCriteria


def criteria_from_profile(profile) -> SearchCriteria:
    return SearchCriteria(
        target_titles=[str(t) for t in (profile.target_titles or [])],
        positive_keywords=[str(k).lower() for k in (profile.positive_keywords or [])],
        negative_keywords=[str(k).lower() for k in (profile.negative_keywords or [])],
        required_keywords=[str(k).lower() for k in (profile.required_keywords or [])],
        locations=[str(loc) for loc in (profile.locations or [])],
        remote_policy=profile.remote_policy or "any",
        contract_types=[str(c).lower() for c in (profile.contract_types or [])],
        freshness_days=profile.freshness_days or 7,
        max_results_per_run=profile.max_results_per_run or 100,
        language=profile.language or "fr",
    )
