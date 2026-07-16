"""Lever postings API connector — stable public JSON, low-risk.

Config: ``config["slugs"]`` = list of company slugs, e.g. ["netflix", "figma"].
Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from .ats_greenhouse import title_matches
from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

POSTINGS_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _parse_ms(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


@register("lever")
class LeverConnector(JobConnector):
    slug = "lever"
    strategy = "ats_api"

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        slugs = self.config.get("slugs") or []
        if not slugs:
            return []
        terms = criteria.title_terms()
        results: list[RawJob] = []
        errors: list[str] = []
        for slug in slugs:
            try:
                payload = self.fetch(POSTINGS_URL.format(slug=slug))
            except Exception as exc:
                errors.append(f"{slug}: {exc}")
                continue
            company = str(self.config.get("company") or slug)
            for job in payload or []:
                title = str(job.get("text") or "")
                if not title_matches(title, terms):
                    continue
                categories = job.get("categories") or {}
                results.append(
                    RawJob(
                        source_job_id=str(job.get("id") or ""),
                        url=str(job.get("hostedUrl") or ""),
                        title=title,
                        company=company,
                        location=str(categories.get("location") or ""),
                        contract_type=str(categories.get("commitment") or ""),
                        posted_at=_parse_ms(job.get("createdAt")),
                        description=str(job.get("descriptionPlain") or job.get("description") or ""),
                        apply_url=str(job.get("applyUrl") or job.get("hostedUrl") or ""),
                        raw_payload=job if isinstance(job, dict) else {},
                    )
                )
                if len(results) >= criteria.max_results_per_run:
                    break
        if errors and not results:
            raise ConnectorError("; ".join(errors))
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": False, "freshness": True, "pagination": False}
