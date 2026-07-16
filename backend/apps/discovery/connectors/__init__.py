"""Job connectors: each turns normalized search criteria into raw postings.

Connectors NEVER write to the DB. They fetch, parse, and return RawJob objects.
The scheduler persists and normalizes them.
"""

from .base import CONNECTOR_REGISTRY, JobConnector, RawJob, SearchCriteria, build_connector, default_fetch

__all__ = [
    "CONNECTOR_REGISTRY",
    "JobConnector",
    "RawJob",
    "SearchCriteria",
    "build_connector",
    "default_fetch",
]
