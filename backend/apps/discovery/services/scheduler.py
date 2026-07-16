"""Nightly discovery orchestration — collect, normalize, dedup, rank, digest.

Deterministic and offline-friendly: pass ``fetch`` to stub network in tests.
Never submits an application; only prepares a ranked short-list.
"""

from __future__ import annotations

import time
from datetime import date

from django.db import transaction
from django.utils import timezone

from ..connectors.base import build_connector
from ..models import (
    DailyJobDigest,
    DailyJobDigestItem,
    DiscoveryRun,
    JobPosting,
    JobRanking,
    JobSource,
    RawJobPosting,
    SearchProfile,
)
from .criteria import criteria_from_profile
from .dedup import upsert_job_posting
from .normalize import canonical_url, normalize_job
from .scoring import score_job


def _select_sources(profile: SearchProfile, sources) -> list[JobSource]:
    if sources is not None:
        return list(sources)
    qs = JobSource.objects.filter(enabled=True)
    slugs = list(profile.sources_enabled or [])
    if slugs:
        qs = qs.filter(slug__in=slugs)
    return [s for s in qs if s.is_automatable]


def _collect_source(run, source, connector, criteria, today) -> dict:
    stat = {"seen": 0, "new": 0, "updated": 0, "errors": []}
    raw_jobs = connector.search(criteria)
    for raw in raw_jobs:
        stat["seen"] += 1
        RawJobPosting.objects.create(
            run=run,
            source=source,
            source_job_id=raw.source_job_id,
            url=raw.url[:1000],
            canonical_url=canonical_url(raw.url)[:1000],
            raw_title=raw.title[:500],
            raw_company=raw.company[:300],
            raw_location=raw.location[:300],
            raw_payload=raw.raw_payload if isinstance(raw.raw_payload, dict) else {},
            posted_at=raw.posted_at if isinstance(raw.posted_at, date) else None,
            status="new",
        )
        normalized = normalize_job(raw, market=source.market)
        if not normalized["company"] and not normalized["title"]:
            continue
        _, created = upsert_job_posting(normalized, source, today)
        stat["new" if created else "updated"] += 1
    return stat


def _rank_and_digest(profile, run, today) -> DailyJobDigest:
    criteria = criteria_from_profile(profile)
    freshness_cutoff = today.toordinal() - criteria.freshness_days

    # Rank every currently-active posting for this profile.
    rankings: list[JobRanking] = []
    for job in JobPosting.objects.filter(is_active=True):
        if job.posted_at and job.posted_at.toordinal() < freshness_cutoff:
            continue
        job_dict = {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "remote_type": job.remote_type,
            "contract_type": job.contract_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "description_text": job.description_text,
            "requirements_text": job.requirements_text,
            "posted_at": job.posted_at,
        }
        result = score_job(job_dict, profile, today)
        ranking, _ = JobRanking.objects.update_or_create(
            job=job,
            run=run,
            defaults={
                "profile": profile,
                "score": result["score"],
                "freshness_score": result["freshness_score"],
                "title_score": result["title_score"],
                "keyword_score": result["keyword_score"],
                "location_score": result["location_score"],
                "remote_score": result["remote_score"],
                "contract_score": result["contract_score"],
                "salary_score": result["salary_score"],
                "company_score": result["company_score"],
                "negative_penalty": result["negative_penalty"],
                "rejected": result["rejected"],
                "reject_reason": result["reject_reason"],
                "explanations": result["explanations"],
            },
        )
        rankings.append(ranking)

    kept = sorted(
        [r for r in rankings if not r.rejected],
        key=lambda r: (-r.score, -(r.job.posted_at.toordinal() if r.job.posted_at else 0)),
    )
    for i, ranking in enumerate(kept, start=1):
        if ranking.rank != i:
            ranking.rank = i
            ranking.save(update_fields=["rank"])

    digest, _ = DailyJobDigest.objects.update_or_create(
        profile=profile,
        date=today,
        defaults={"run": run, "status": "prepared", "total_candidates": len(kept)},
    )
    digest.items.all().delete()
    top = kept[: profile.daily_digest_size]
    DailyJobDigestItem.objects.bulk_create(
        [
            DailyJobDigestItem(digest=digest, job=r.job, ranking=r, rank=r.rank, decision="pending")
            for r in top
        ]
    )
    digest.items_count = len(top)
    digest.save(update_fields=["items_count"])
    return digest


def run_discovery(profile: SearchProfile, *, sources=None, trigger: str = "manual", fetch=None) -> dict:
    started = time.monotonic()
    today = timezone.localdate()
    selected = _select_sources(profile, sources)
    criteria = criteria_from_profile(profile)

    run = DiscoveryRun.objects.create(
        profile=profile,
        status="running",
        trigger=trigger,
        sources_requested=[s.slug for s in selected],
    )

    per_source: dict[str, dict] = {}
    succeeded: list[str] = []
    failed: list[str] = []
    errors: list[str] = []

    for source in selected:
        connector = build_connector(source, fetch=fetch)
        source.last_checked_at = timezone.now()
        if connector is None:
            failed.append(source.slug)
            source.last_error = f"no connector registered for '{source.connector}'"
            source.save(update_fields=["last_checked_at", "last_error"])
            per_source[source.slug] = {"seen": 0, "new": 0, "errors": [source.last_error]}
            errors.append(f"{source.slug}: {source.last_error}")
            continue
        try:
            with transaction.atomic():
                stat = _collect_source(run, source, connector, criteria, today)
            per_source[source.slug] = stat
            succeeded.append(source.slug)
            source.last_success_at = timezone.now()
            source.last_error = ""
        except Exception as exc:  # connector-local failure; keep the run going
            failed.append(source.slug)
            source.last_error = str(exc)[:2000]
            per_source[source.slug] = {"seen": 0, "new": 0, "errors": [str(exc)]}
            errors.append(f"{source.slug}: {exc}")
        source.save(update_fields=["last_checked_at", "last_success_at", "last_error"])

    digest = _rank_and_digest(profile, run, today)

    run.finished_at = timezone.now()
    run.status = "success" if not failed else ("partial" if succeeded else "failed")
    run.sources_success = succeeded
    run.sources_failed = failed
    run.offers_seen = sum(s.get("seen", 0) for s in per_source.values())
    run.offers_new = sum(s.get("new", 0) for s in per_source.values())
    run.offers_updated = sum(s.get("updated", 0) for s in per_source.values())
    run.offers_deduped = max(0, run.offers_seen - run.offers_new)
    run.errors = errors
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.save()

    return {
        "runId": run.id,
        "status": run.status,
        "sources": {slug: {"seen": s.get("seen", 0), "new": s.get("new", 0), "errors": s.get("errors", [])}
                    for slug, s in per_source.items()},
        "digest": {"date": today.isoformat(), "items": digest.items_count, "candidates": digest.total_candidates},
    }
