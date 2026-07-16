"""Integration tests for a full discovery run with fake connectors (offline)."""

from datetime import date

import pytest

from apps.discovery.models import (
    DailyJobDigest,
    DiscoveryRun,
    JobPosting,
    JobRanking,
    JobSource,
    RawJobPosting,
    SearchProfile,
)
from apps.discovery.services.scheduler import run_discovery


def _fake_source(slug, jobs):
    return JobSource.objects.create(
        name=slug.title(), slug=slug, kind="jobboard", strategy="api",
        connector="fake", enabled=True, market="france", config={"jobs": jobs},
    )


def _profile():
    return SearchProfile.objects.create(
        name="default",
        target_titles=["Data Engineer", "AI Engineer"],
        positive_keywords=["python"],
        negative_keywords=["php"],
        remote_policy="any",
        locations=["Paris"],
        contract_types=["cdi", "freelance"],
        freshness_days=3650,  # keep everything for deterministic ranking
        daily_digest_size=10,
    )


@pytest.fixture()
def today_iso():
    from django.utils import timezone

    return timezone.localdate().isoformat()


@pytest.mark.django_db
def test_full_run_collects_normalizes_and_builds_digest(today_iso):
    profile = _profile()
    _fake_source("boarda", [
        {"url": "https://a.test/1", "title": "Senior Data Engineer", "company": "Acme",
         "location": "Paris", "posted_at": today_iso, "description": "Full remote CDI python spark"},
        {"url": "https://a.test/2", "title": "PHP Developer", "company": "LegacyCo",
         "location": "Lyon", "posted_at": today_iso, "description": "php wordpress onsite"},
    ])

    summary = run_discovery(profile, trigger="manual")

    run = DiscoveryRun.objects.get()
    assert run.status == "success"
    assert summary["status"] == "success"
    assert run.offers_seen == 2
    assert JobPosting.objects.count() == 2
    assert RawJobPosting.objects.count() == 2

    digest = DailyJobDigest.objects.get(profile=profile)
    # PHP dev doesn't match a target title but is not hard-rejected; the data
    # engineer must outrank it and appear first.
    assert digest.items_count >= 1
    top = digest.items.order_by("rank").first()
    assert top.job.company == "Acme"
    assert top.ranking.score > 0
    assert not top.ranking.rejected


@pytest.mark.django_db
def test_dedup_merges_same_offer_across_two_sources(today_iso):
    profile = _profile()
    offer = {"title": "Data Engineer", "company": "Acme", "location": "Paris",
             "posted_at": today_iso, "description": "python"}
    _fake_source("boarda", [{**offer, "url": "https://a.test/1"}])
    _fake_source("boardb", [{**offer, "url": "https://b.test/9"}])

    run_discovery(profile, trigger="manual")

    assert JobPosting.objects.count() == 1
    job = JobPosting.objects.get()
    assert set(job.all_sources) == {"boarda", "boardb"}
    run = DiscoveryRun.objects.get()
    assert run.offers_seen == 2
    assert run.offers_new == 1
    assert run.offers_deduped == 1


@pytest.mark.django_db
def test_rejected_offers_excluded_from_digest(today_iso):
    profile = _profile()
    profile.companies_block = ["BadCorp"]
    profile.save()
    _fake_source("boarda", [
        {"url": "https://a.test/1", "title": "Data Engineer", "company": "BadCorp",
         "location": "Paris", "posted_at": today_iso, "description": "python"},
        {"url": "https://a.test/2", "title": "Data Engineer", "company": "GoodCorp",
         "location": "Paris", "posted_at": today_iso, "description": "python"},
    ])

    run_discovery(profile, trigger="manual")

    digest = DailyJobDigest.objects.get(profile=profile)
    companies = {item.job.company for item in digest.items.all()}
    assert companies == {"GoodCorp"}
    bad_ranking = JobRanking.objects.get(job__company="BadCorp")
    assert bad_ranking.rejected


@pytest.mark.django_db
def test_connector_error_is_recorded_and_run_continues(today_iso):
    profile = _profile()
    # Missing connector key → source fails, run is partial, other source succeeds.
    JobSource.objects.create(name="Broken", slug="broken", connector="does-not-exist",
                             strategy="api", enabled=True, market="france")
    _fake_source("boarda", [
        {"url": "https://a.test/1", "title": "Data Engineer", "company": "Acme",
         "location": "Paris", "posted_at": today_iso, "description": "python"},
    ])

    summary = run_discovery(profile, trigger="manual")

    run = DiscoveryRun.objects.get()
    assert run.status == "partial"
    assert "broken" in run.sources_failed
    assert "boarda" in run.sources_success
    assert summary["sources"]["broken"]["errors"]
