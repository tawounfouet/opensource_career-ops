"""API tests for the discovery endpoints."""

from pathlib import Path

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.discovery.models import (
    DailyJobDigest,
    DailyJobDigestItem,
    JobPosting,
    JobRanking,
    JobSource,
    SearchProfile,
)


@pytest.fixture()
def career_root(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    return tmp_path


@pytest.mark.django_db
def test_sources_endpoint_lists_sources(client):
    JobSource.objects.create(name="Greenhouse", slug="greenhouse", connector="greenhouse",
                             strategy="ats_api", enabled=True)
    response = client.get("/api/discovery/sources")
    assert response.status_code == 200
    assert response.json()["sources"][0]["slug"] == "greenhouse"


@pytest.mark.django_db
def test_profile_get_creates_default_then_post_updates(client):
    get = client.get("/api/discovery/profile")
    assert get.status_code == 200
    assert get.json()["name"] == "default"

    post = client.post(
        "/api/discovery/profile",
        {"remote_policy": "remote", "target_titles": ["AI Engineer"], "freshness_days": 5},
        content_type="application/json",
    )
    assert post.status_code == 200
    body = post.json()
    assert body["remote_policy"] == "remote"
    assert body["target_titles"] == ["AI Engineer"]
    assert SearchProfile.objects.get(name="default").freshness_days == 5


@pytest.mark.django_db
def test_run_endpoint_produces_digest(client):
    SearchProfile.objects.create(name="default", target_titles=["Data Engineer"],
                                 freshness_days=3650, positive_keywords=["python"])
    JobSource.objects.create(
        name="Fake", slug="fake", connector="fake", strategy="api", enabled=True,
        config={"jobs": [{"url": "https://a.test/1", "title": "Data Engineer", "company": "Acme",
                          "location": "Paris", "posted_at": timezone.localdate().isoformat(),
                          "description": "python"}]},
    )
    response = client.post("/api/discovery/run", {}, content_type="application/json")
    assert response.status_code == 200
    summary = response.json()
    assert summary["status"] == "success"
    assert summary["digest"]["items"] == 1

    today = client.get("/api/discovery/digest/today")
    assert today.status_code == 200
    items = today.json()["items"]
    assert items[0]["job"]["company"] == "Acme"
    assert "explanations" in items[0]["ranking"]


@pytest.mark.django_db
def test_digest_today_empty_when_no_run(client):
    response = client.get("/api/discovery/digest/today")
    assert response.status_code == 200
    assert response.json()["empty"] is True


@pytest.mark.django_db
def test_item_decision_validates_value(client):
    item = _make_item()
    bad = client.post(f"/api/discovery/items/{item.id}/decision",
                      {"decision": "nope"}, content_type="application/json")
    assert bad.status_code == 400

    ok = client.post(f"/api/discovery/items/{item.id}/decision",
                     {"decision": "skip", "note": "not a fit"}, content_type="application/json")
    assert ok.status_code == 200
    item.refresh_from_db()
    assert item.decision == "skip"
    assert item.decision_note == "not a fit"


@pytest.mark.django_db
def test_item_export_appends_to_pipeline(client, career_root):
    item = _make_item()
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post(f"/api/discovery/items/{item.id}/export-pipeline",
                               {}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["added"] is True
    pipeline = (career_root / "data" / "pipeline.md").read_text(encoding="utf-8")
    assert "https://a.test/1" in pipeline
    assert "Acme" in pipeline
    item.refresh_from_db()
    assert item.exported_to_pipeline_at is not None
    assert item.decision == "evaluate"


def _make_item() -> DailyJobDigestItem:
    from apps.discovery.models import DiscoveryRun

    profile = SearchProfile.objects.create(name="default")
    run = DiscoveryRun.objects.create(profile=profile, status="success")
    job = JobPosting.objects.create(
        canonical_key="acme|data-engineer|paris", title="Data Engineer", company="Acme",
        company_slug="acme", location="Paris", apply_url="https://a.test/1", source_url="https://a.test/1",
    )
    ranking = JobRanking.objects.create(job=job, profile=profile, run=run, score=80, rank=1)
    digest = DailyJobDigest.objects.create(profile=profile, date=timezone.localdate(), run=run,
                                           total_candidates=1, items_count=1)
    return DailyJobDigestItem.objects.create(digest=digest, job=job, ranking=ranking, rank=1)
