"""Deterministic fixture connector — the backbone of offline tests.

Reads offers from ``source.config``:
- ``config["jobs"]``: inline list of raw offer dicts, or
- ``config["fixture_path"]``: absolute path to a JSON file with the same shape.

Each offer dict accepts: source_job_id, url, title, company, location,
contract_type, salary_text, posted_at (ISO date str), description, requirements,
apply_url.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .base import JobConnector, RawJob, SearchCriteria, register


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@register("fake")
class FakeConnector(JobConnector):
    slug = "fake"
    strategy = "manual_import"

    def _load_offers(self) -> list[dict]:
        if isinstance(self.config.get("jobs"), list):
            return self.config["jobs"]
        fixture_path = self.config.get("fixture_path")
        if fixture_path and Path(fixture_path).exists():
            data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("jobs", [])
            if isinstance(data, list):
                return data
        return []

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        jobs: list[RawJob] = []
        for i, offer in enumerate(self._load_offers()):
            jobs.append(
                RawJob(
                    source_job_id=str(offer.get("source_job_id") or offer.get("id") or f"fake-{i}"),
                    url=str(offer.get("url") or ""),
                    title=str(offer.get("title") or ""),
                    company=str(offer.get("company") or ""),
                    location=str(offer.get("location") or ""),
                    contract_type=str(offer.get("contract_type") or ""),
                    salary_text=str(offer.get("salary_text") or ""),
                    posted_at=_parse_date(offer.get("posted_at")),
                    description=str(offer.get("description") or ""),
                    requirements=str(offer.get("requirements") or ""),
                    apply_url=str(offer.get("apply_url") or offer.get("url") or ""),
                    raw_payload=offer if isinstance(offer, dict) else {},
                )
            )
        return jobs

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": True, "freshness": True, "pagination": False}
