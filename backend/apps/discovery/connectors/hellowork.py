"""HelloWork connector — généraliste France, high priority.

HelloWork's public search-result pages embed schema.org ``JobPosting`` records
as JSON-LD (``<script type="application/ld+json">``). We parse ONLY that public
structured data — no login, no anti-bot bypass — and keep a strict rate limit
(``source.rate_limit_per_hour``). Ships disabled until opted in.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from .ats_greenhouse import title_matches
from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

SEARCH_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={query}&l={location}"
_LD_BLOCK = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def extract_job_postings(html: str) -> list[dict]:
    """Pull every schema.org JobPosting object out of a page's JSON-LD blocks."""
    postings: list[dict] = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "JobPosting" in types:
                postings.append(node)
            if "@graph" in node:
                walk(node["@graph"])
            if "itemListElement" in node:
                walk(node["itemListElement"])
            if "item" in node and isinstance(node["item"], (dict, list)):
                walk(node["item"])

    for raw in _LD_BLOCK.findall(html or ""):
        try:
            walk(json.loads(raw.strip()))
        except json.JSONDecodeError:
            continue
    return postings


def _location(posting: dict) -> str:
    loc = posting.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, dict):
        address = loc.get("address")
        if isinstance(address, dict):
            return str(address.get("addressLocality") or address.get("addressRegion") or "")
        if isinstance(address, str):
            return address
    if posting.get("jobLocationType") == "TELECOMMUTE":
        return "Remote"
    return ""


def _salary_text(posting: dict) -> str:
    salary = posting.get("baseSalary")
    if isinstance(salary, dict):
        value = salary.get("value")
        if isinstance(value, dict):
            lo, hi = value.get("minValue"), value.get("maxValue")
            if lo or hi:
                return f"{lo or ''}-{hi or ''} {salary.get('currency') or ''}".strip()
    return ""


@register("hellowork")
class HelloWorkConnector(JobConnector):
    slug = "hellowork"
    strategy = "html_public"

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        query = "+".join(" ".join(criteria.target_titles[:2]).split())
        location = criteria.locations[0] if criteria.locations else ""
        url = self.config.get("search_url") or SEARCH_URL.format(query=query, location=location)
        try:
            html = self.fetch(url, as_json=False)
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc

        terms = criteria.title_terms()
        results: list[RawJob] = []
        for posting in extract_job_postings(html):
            title = str(posting.get("title") or "")
            if not title_matches(title, terms):
                continue
            org = posting.get("hiringOrganization") or {}
            company = str(org.get("name") if isinstance(org, dict) else org or "")
            employment = posting.get("employmentType")
            if isinstance(employment, list):
                employment = employment[0] if employment else ""
            results.append(
                RawJob(
                    source_job_id=str(posting.get("identifier", {}).get("value") if isinstance(posting.get("identifier"), dict) else posting.get("identifier") or ""),
                    url=str(posting.get("url") or ""),
                    title=title,
                    company=company,
                    location=_location(posting),
                    contract_type=str(employment or ""),
                    salary_text=_salary_text(posting),
                    posted_at=_parse_date(posting.get("datePosted")),
                    description=str(posting.get("description") or ""),
                    apply_url=str(posting.get("url") or ""),
                    raw_payload=posting if isinstance(posting, dict) else {},
                )
            )
            if len(results) >= criteria.max_results_per_run:
                break
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": True, "freshness": True, "pagination": False}
