"""Welcome to the Jungle connector — startups/scaleups, high priority.

WTTJ's public search is served by Algolia. We call ONLY the Algolia query
endpoint the site itself uses, with the public app id / search key the user
supplies in ``config`` (``app_id``, ``api_key``, ``index``). No protection is
bypassed. Ships disabled until credentials are configured.
"""

from __future__ import annotations

from datetime import date, datetime

from .ats_greenhouse import title_matches
from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

QUERY_URL = "https://{app_id}-dsn.algolia.net/1/indexes/*/queries"
OFFER_URL = "https://www.welcometothejungle.com/fr/companies/{company}/jobs/{slug}"


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _location(hit: dict) -> str:
    offices = hit.get("offices") or []
    if offices and isinstance(offices[0], dict):
        return str(offices[0].get("city") or offices[0].get("country") or "")
    return str(hit.get("city") or "")


@register("wttj")
class WelcomeToTheJungleConnector(JobConnector):
    slug = "wttj"
    strategy = "api"

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        app_id = self.config.get("app_id")
        api_key = self.config.get("api_key")
        index = self.config.get("index", "wk_prod_jobs_production_v2")
        if not app_id or not api_key:
            raise ConnectorError("WTTJ requires config.app_id and config.api_key (public Algolia search keys).")

        query = " ".join(criteria.target_titles[:3])
        body = {
            "requests": [
                {
                    "indexName": index,
                    "params": f"query={query}&hitsPerPage={min(criteria.max_results_per_run, 100)}",
                }
            ]
        }
        headers = {"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": api_key}
        try:
            payload = self.fetch(
                QUERY_URL.format(app_id=app_id), method="POST", data=body, headers=headers
            )
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc

        terms = criteria.title_terms()
        results: list[RawJob] = []
        for block in (payload or {}).get("results", []) or []:
            for hit in block.get("hits", []) or []:
                title = str(hit.get("name") or hit.get("title") or "")
                if not title_matches(title, terms):
                    continue
                organization = hit.get("organization") or {}
                company = str(organization.get("name") or hit.get("company_name") or "")
                company_slug = str(organization.get("slug") or hit.get("company_slug") or "")
                slug = str(hit.get("slug") or hit.get("reference") or "")
                url = str(hit.get("url") or (OFFER_URL.format(company=company_slug, slug=slug) if company_slug and slug else ""))
                remote = ""
                if hit.get("remote") or hit.get("has_remote"):
                    remote = "remote"
                results.append(
                    RawJob(
                        source_job_id=str(hit.get("reference") or hit.get("objectID") or slug),
                        url=url,
                        title=title,
                        company=company,
                        location=" ".join(x for x in (_location(hit), remote) if x),
                        contract_type=str(hit.get("contract_type") or ""),
                        salary_text=str(hit.get("salary_min") or hit.get("salary") or ""),
                        posted_at=_parse_date(hit.get("published_at") or hit.get("published_at_date")),
                        description=str(hit.get("description") or hit.get("profile") or ""),
                        apply_url=url,
                        raw_payload=hit if isinstance(hit, dict) else {},
                    )
                )
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": True, "freshness": True, "pagination": True}
