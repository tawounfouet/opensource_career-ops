"""Greenhouse board API connector — stable public JSON, low-risk.

Config: ``config["boards"]`` = list of board tokens, e.g. ["stripe", "figma"].
Endpoint: https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""

from __future__ import annotations

from datetime import date, datetime

from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _parse_iso(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def title_matches(title: str, terms: list[str]) -> bool:
    if not terms:
        return True
    low = title.lower()
    return any(term in low for term in terms)


@register("greenhouse")
class GreenhouseConnector(JobConnector):
    slug = "greenhouse"
    strategy = "ats_api"

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        boards = self.config.get("boards") or []
        if not boards:
            return []
        terms = criteria.title_terms()
        results: list[RawJob] = []
        errors: list[str] = []
        for token in boards:
            try:
                payload = self.fetch(BOARD_URL.format(token=token))
            except Exception as exc:  # network/parse — record and continue other boards
                errors.append(f"{token}: {exc}")
                continue
            company = str(self.config.get("company") or token)
            for job in payload.get("jobs", []) or []:
                title = str(job.get("title") or "")
                if not title_matches(title, terms):
                    continue
                location = ""
                if isinstance(job.get("location"), dict):
                    location = str(job["location"].get("name") or "")
                results.append(
                    RawJob(
                        source_job_id=str(job.get("id") or ""),
                        url=str(job.get("absolute_url") or ""),
                        title=title,
                        company=company,
                        location=location,
                        posted_at=_parse_iso(job.get("updated_at") or job.get("first_published")),
                        description=str(job.get("content") or ""),
                        apply_url=str(job.get("absolute_url") or ""),
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
