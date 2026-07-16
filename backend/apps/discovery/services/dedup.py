"""Deterministic deduplication by tiers (see plan §Déduplication).

Priority of signals, strongest first:
  1. Same canonical URL / apply URL     → confidence 1.0
  2. Same canonical_key (company+title+location) → 0.9
  3. Same content hash (company+title+location) → 0.8
``all_sources`` accumulates every source slug an offer appears under.
"""

from __future__ import annotations

from ..models import JobPosting
from .normalize import canonical_key, canonical_url


def resolve_duplicate(normalized: dict) -> tuple[JobPosting | None, float]:
    """Find an existing JobPosting that this normalized offer duplicates."""
    key = canonical_key(normalized)
    apply_canon = canonical_url(normalized.get("apply_url", ""))
    source_canon = normalized.get("canonical_url") or canonical_url(normalized.get("source_url", ""))
    chash = normalized.get("content_hash", "")

    # Tier 1 — identical canonical URL (either apply or source side).
    if apply_canon or source_canon:
        for existing in JobPosting.objects.filter(canonical_key=key) | JobPosting.objects.filter(content_hash=chash):
            for candidate in (canonical_url(existing.apply_url), canonical_url(existing.source_url)):
                if candidate and candidate in (apply_canon, source_canon):
                    return existing, 1.0

    # Tier 2 — same canonical key.
    existing = JobPosting.objects.filter(canonical_key=key).first()
    if existing:
        return existing, 0.9

    # Tier 3 — same content hash (title/company/location) under a different key.
    if chash:
        existing = JobPosting.objects.filter(content_hash=chash).first()
        if existing:
            return existing, 0.8

    return None, 1.0


def upsert_job_posting(normalized: dict, source, today) -> tuple[JobPosting, bool]:
    """Create or merge a JobPosting. Returns (job, created)."""
    key = canonical_key(normalized)
    existing, confidence = resolve_duplicate(normalized)

    if existing is None:
        job = JobPosting.objects.create(
            canonical_key=key,
            title=normalized["title"] or "(untitled)",
            company=normalized["company"],
            company_slug=normalized["company_slug"],
            location=normalized["location"],
            remote_type=normalized["remote_type"],
            contract_type=normalized["contract_type"],
            salary_min=normalized["salary_min"],
            salary_max=normalized["salary_max"],
            salary_currency=normalized["salary_currency"],
            seniority=normalized["seniority"],
            description_text=normalized["description_text"],
            requirements_text=normalized["requirements_text"],
            apply_url=normalized["apply_url"],
            source_url=normalized["source_url"],
            primary_source=source,
            all_sources=[source.slug],
            posted_at=normalized["posted_at"],
            is_active=True,
            dedup_confidence=1.0,
            content_hash=normalized["content_hash"],
            language=normalized["language"],
            market=normalized["market"],
        )
        return job, True

    # Merge: record the extra source, refresh liveness and any missing facts.
    changed_sources = source.slug not in existing.all_sources
    if changed_sources:
        existing.all_sources = [*existing.all_sources, source.slug]
    existing.is_active = True
    existing.dedup_confidence = min(existing.dedup_confidence, confidence)
    # Backfill values only where the current record is empty/unknown.
    if not existing.salary_min and normalized["salary_min"]:
        existing.salary_min = normalized["salary_min"]
        existing.salary_max = normalized["salary_max"]
        existing.salary_currency = normalized["salary_currency"]
    if existing.remote_type == "unknown" and normalized["remote_type"] != "unknown":
        existing.remote_type = normalized["remote_type"]
    if existing.contract_type == "unknown" and normalized["contract_type"] != "unknown":
        existing.contract_type = normalized["contract_type"]
    if not existing.description_text and normalized["description_text"]:
        existing.description_text = normalized["description_text"]
    if not existing.posted_at and normalized["posted_at"]:
        existing.posted_at = normalized["posted_at"]
    existing.save()
    return existing, False
