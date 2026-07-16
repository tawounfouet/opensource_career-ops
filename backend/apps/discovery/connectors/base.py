"""Connector interface, transport, and registry."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

USER_AGENT = "career-ops-discovery/1.0 (+https://github.com/santifer)"
DEFAULT_TIMEOUT = 20


@dataclass
class SearchCriteria:
    """Normalized user criteria handed to every connector.

    Connectors use these to shape their query where the source supports it, and
    to loosely pre-filter. Authoritative filtering/scoring happens downstream.
    """

    target_titles: list[str] = field(default_factory=list)
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_policy: str = "any"
    contract_types: list[str] = field(default_factory=list)
    freshness_days: int = 7
    max_results_per_run: int = 100
    language: str = "fr"

    def title_terms(self) -> list[str]:
        """Lowercased individual words across target titles, for loose matching."""
        terms: set[str] = set()
        for title in self.target_titles:
            for word in str(title).lower().split():
                if len(word) >= 3:
                    terms.add(word)
        return sorted(terms)


@dataclass
class RawJob:
    """A single raw posting as returned by a connector (pre-normalization)."""

    source_job_id: str
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    contract_type: str = ""
    salary_text: str = ""
    posted_at: Optional[date] = None
    description: str = ""
    requirements: str = ""
    apply_url: str = ""
    raw_payload: dict = field(default_factory=dict)


def default_fetch(
    url: str,
    *,
    method: str = "GET",
    data=None,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    as_json: bool = True,
):
    """Minimal HTTP transport. Kept injectable so connectors are testable offline.

    Supports GET/POST and JSON or raw-text (HTML) responses. Only ever used
    against public, documented endpoints — never to bypass login/anti-bot.
    """
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json" if as_json else "text/html"}
    if headers:
        request_headers.update(headers)
    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8") if isinstance(data, (dict, list)) else str(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body_bytes, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (public endpoints only)
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body) if as_json else body


class ConnectorError(Exception):
    """Raised for a connector-local failure; the scheduler records and continues."""


class JobConnector:
    """Common connector interface.

    Subclasses set ``slug``/``strategy`` and implement ``search``. They must
    handle their own errors by raising ``ConnectorError`` (or a subclass) so the
    scheduler can log per-source without aborting the whole run.
    """

    slug: str = ""
    strategy: str = ""

    def __init__(self, source=None, fetch: Optional[Callable] = None):
        self.source = source
        self.fetch = fetch or default_fetch
        # Connector-specific config, typically JobSource.config.
        self.config: dict = dict(getattr(source, "config", None) or {})

    def search(self, criteria: SearchCriteria) -> list[RawJob]:  # pragma: no cover - interface
        raise NotImplementedError

    def capabilities(self) -> dict:
        return {
            "keywords": False,
            "location": False,
            "remote": False,
            "freshness": False,
            "pagination": False,
        }


# Registry is populated lazily to avoid import cycles at module import time.
CONNECTOR_REGISTRY: dict[str, type[JobConnector]] = {}


def register(key: str):
    def wrap(cls: type[JobConnector]) -> type[JobConnector]:
        CONNECTOR_REGISTRY[key] = cls
        return cls

    return wrap


def build_connector(source, fetch: Optional[Callable] = None) -> Optional[JobConnector]:
    """Instantiate the connector for a JobSource, or None if unknown/manual."""
    _ensure_registry_loaded()
    key = (getattr(source, "connector", "") or "").strip()
    cls = CONNECTOR_REGISTRY.get(key)
    if cls is None:
        return None
    return cls(source=source, fetch=fetch)


_registry_loaded = False


def _ensure_registry_loaded() -> None:
    global _registry_loaded
    if _registry_loaded:
        return
    # Import concrete connectors so their @register decorators run.
    from . import (  # noqa: F401
        apec,
        ats_ashby,
        ats_greenhouse,
        ats_lever,
        fake,
        france_travail,
        hellowork,
        manual,
        welcometothejungle,
    )

    _registry_loaded = True
