"""Ashby job-board API connector — stable public JSON, low-risk.

Config: ``config["slugs"]`` = list of job-board slugs, e.g. ["ramp", "linear"].
Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}
"""

from __future__ import annotations

from datetime import date, datetime

from .ats_greenhouse import title_matches
from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

BOARD_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


def _parse_iso(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


@register("ashby")
class AshbyConnector(JobConnector):
    slug = "ashby"
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
                payload = self.fetch(BOARD_URL.format(slug=slug))
            except Exception as exc:
                errors.append(f"{slug}: {exc}")
                continue
            company = str(self.config.get("company") or slug)
            for job in payload.get("jobs", []) or []:
                title = str(job.get("title") or "")
                if not title_matches(title, terms):
                    continue
                location = str(job.get("location") or "")
                remote = job.get("isRemote")
                if remote and "remote" not in location.lower():
                    location = (location + " (remote)").strip()
                results.append(
                    RawJob(
                        source_job_id=str(job.get("id") or ""),
                        url=str(job.get("jobUrl") or job.get("applyUrl") or ""),
                        title=title,
                        company=company,
                        location=location,
                        contract_type=str(job.get("employmentType") or ""),
                        posted_at=_parse_iso(job.get("publishedAt") or job.get("updatedAt")),
                        description=str(job.get("descriptionPlain") or job.get("description") or ""),
                        apply_url=str(job.get("applyUrl") or job.get("jobUrl") or ""),
                        raw_payload=job if isinstance(job, dict) else {},
                    )
                )
                if len(results) >= criteria.max_results_per_run:
                    break
        if errors and not results:
            raise ConnectorError("; ".join(errors))
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": True, "freshness": True, "pagination": False}
