"""Manual-import connectors for strongly-protected platforms (LinkedIn, Indeed).

Per the plan's legal posture these are NEVER auto-scraped. The user pastes or
exports saved offers into ``source.config``:

- ``config["items"]``: list of offer dicts (url, title, company, location, ...)
- ``config["urls"]``: list of bare offer URLs (title/company left empty)

No network is ever touched here — it is a pure read of user-supplied data.
"""

from __future__ import annotations

from datetime import date

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


class ManualImportConnector(JobConnector):
    """Base for user-driven imports — reads config, performs no network I/O."""

    strategy = "manual_import"

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        results: list[RawJob] = []
        for i, item in enumerate(self.config.get("items") or []):
            if not isinstance(item, dict):
                continue
            results.append(
                RawJob(
                    source_job_id=str(item.get("source_job_id") or item.get("id") or f"{self.slug}-{i}"),
                    url=str(item.get("url") or ""),
                    title=str(item.get("title") or ""),
                    company=str(item.get("company") or ""),
                    location=str(item.get("location") or ""),
                    contract_type=str(item.get("contract_type") or ""),
                    salary_text=str(item.get("salary_text") or ""),
                    posted_at=_parse_date(item.get("posted_at")),
                    description=str(item.get("description") or ""),
                    apply_url=str(item.get("apply_url") or item.get("url") or ""),
                    raw_payload=item,
                )
            )
        for j, url in enumerate(self.config.get("urls") or []):
            url = str(url).strip()
            if url.startswith(("http://", "https://")):
                results.append(RawJob(source_job_id=f"{self.slug}-url-{j}", url=url, apply_url=url, raw_payload={"url": url}))
        return results

    def capabilities(self) -> dict:
        return {"keywords": False, "location": False, "remote": False, "freshness": False, "pagination": False}


@register("linkedin_manual")
class LinkedInManualConnector(ManualImportConnector):
    slug = "linkedin"


@register("indeed_manual")
class IndeedManualConnector(ManualImportConnector):
    slug = "indeed"
