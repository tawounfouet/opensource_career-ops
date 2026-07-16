"""Bidirectional sync between config/portals.yml and the Django DB.

Usage::

    from apps.portals.services import import_yaml_to_db, export_db_to_yaml

    # Import (YAML → DB): YAML wins on conflicts
    result = import_yaml_to_db()
    print(result)

    # Export (DB → YAML): DB wins on conflicts
    result = export_db_to_yaml()
    print(result)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings

from apps.core.safe_write import atomic_write_with_backup
from apps.portals.models import JobBoard, LocationFilter, Portal, SearchQuery, TitleFilter

logger = logging.getLogger(__name__)

YAML_KNOWN_PORTAL_FIELDS = frozenset({
    "name", "careers_url", "enabled", "api", "scan_method",
    "scan_query", "notes", "provider", "parser", "max_pages",
})

YAML_KNOWN_BOARD_FIELDS = frozenset({
    "name", "careers_url", "provider", "enabled", "notes",
})


def _yaml_path() -> Path:
    return Path(settings.CAREER_OPS_ROOT) / "config" / "portals.yml"


# ---------------------------------------------------------------------------
# YAML → DB  (import)
# ---------------------------------------------------------------------------

def import_yaml_to_db(yaml_path: Path | None = None) -> dict[str, Any]:
    """Import config/portals.yml into the database.

    YAML is the source of truth: existing DB rows are updated to match.
    Rows in DB but absent from YAML are left untouched (no auto-delete on import).
    """
    path = yaml_path or _yaml_path()
    if not path.exists():
        return {"error": f"{path} not found"}

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    stats: dict[str, int] = {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    # --- TitleFilter (singleton) ---
    tf_data = data.get("title_filter", {})
    TitleFilter.objects.update_or_create(
        pk=1,
        defaults={
            "positive": tf_data.get("positive", []),
            "negative": tf_data.get("negative", []),
            "seniority_boost": tf_data.get("seniority_boost", []),
        },
    )

    # --- LocationFilter (singleton) ---
    lf_data = data.get("location_filter", {})
    if lf_data:
        LocationFilter.objects.update_or_create(
            pk=1,
            defaults={
                "allow": lf_data.get("allow", []),
                "block": lf_data.get("block", []),
                "always_allow": lf_data.get("always_allow", []),
            },
        )

    # --- tracked_companies ---
    seen_names: set[str] = set()
    for entry in data.get("tracked_companies", []):
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        seen_names.add(name)

        extra = {
            k: v for k, v in entry.items()
            if k not in YAML_KNOWN_PORTAL_FIELDS
        }

        defaults = {
            "careers_url": entry.get("careers_url", ""),
            "enabled": entry.get("enabled", True),
            "api_endpoint": entry.get("api", ""),
            "scan_method": entry.get("scan_method", "auto"),
            "scan_query": entry.get("scan_query", ""),
            "notes": entry.get("notes", ""),
            "provider": entry.get("provider", ""),
            "parser_config": entry.get("parser"),
            "max_pages": entry.get("max_pages"),
            "extra_config": extra,
        }

        _, created = Portal.objects.update_or_create(name=name, defaults=defaults)
        if created:
            stats["imported"] += 1
        else:
            stats["updated"] += 1

    # --- search_queries ---
    for entry in data.get("search_queries", []):
        query = (entry.get("query") or "").strip()
        if not query:
            continue
        _, created = SearchQuery.objects.update_or_create(
            query=query,
            defaults={
                "name": entry.get("name", ""),
                "source": entry.get("source", ""),
                "enabled": entry.get("enabled", True),
            },
        )
        if created:
            stats["imported"] += 1
        else:
            stats["updated"] += 1

    # --- job_boards ---
    for entry in data.get("job_boards", []):
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        extra = {
            k: v for k, v in entry.items()
            if k not in YAML_KNOWN_BOARD_FIELDS
        }
        _, created = JobBoard.objects.update_or_create(
            name=name,
            defaults={
                "careers_url": entry.get("careers_url", ""),
                "provider": entry.get("provider", ""),
                "enabled": entry.get("enabled", True),
                "notes": entry.get("notes", ""),
                "extra_config": extra,
            },
        )
        if created:
            stats["imported"] += 1
        else:
            stats["updated"] += 1

    logger.info("YAML→DB import: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# DB → YAML  (export)
# ---------------------------------------------------------------------------

def _portal_to_yaml_dict(p: Portal) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": p.name, "careers_url": p.careers_url}
    if p.api_endpoint:
        entry["api"] = p.api_endpoint
    if p.scan_method and p.scan_method != "auto":
        entry["scan_method"] = p.scan_method
    if p.scan_query:
        entry["scan_query"] = p.scan_query
    if p.notes:
        entry["notes"] = p.notes
    if not p.enabled:
        entry["enabled"] = False
    if p.provider:
        entry["provider"] = p.provider
    if p.parser_config:
        entry["parser"] = p.parser_config
    if p.max_pages:
        entry["max_pages"] = p.max_pages
    entry.update(p.extra_config)
    return entry


def _query_to_yaml_dict(q: SearchQuery) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    if q.name:
        entry["name"] = q.name
    entry["query"] = q.query
    if not q.enabled:
        entry["enabled"] = False
    return entry


def _board_to_yaml_dict(b: JobBoard) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": b.name,
        "careers_url": b.careers_url,
    }
    if b.provider:
        entry["provider"] = b.provider
    if not b.enabled:
        entry["enabled"] = False
    if b.notes:
        entry["notes"] = b.notes
    entry.update(b.extra_config)
    return entry


def export_db_to_yaml(yaml_path: Path | None = None) -> dict[str, Any]:
    """Export the database state to config/portals.yml.

    DB is the source of truth: the YAML is overwritten.
    Unknown top-level keys in the existing YAML are preserved.
    """
    path = yaml_path or _yaml_path()

    existing: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    tf = TitleFilter.load()
    lf = LocationFilter.load()
    doc: dict[str, Any] = {
        "title_filter": {
            "positive": tf.positive,
            "negative": tf.negative,
            "seniority_boost": tf.seniority_boost,
        },
        "location_filter": {
            "allow": lf.allow,
            "block": lf.block,
            "always_allow": lf.always_allow,
        },
        "search_queries": [
            _query_to_yaml_dict(q) for q in SearchQuery.objects.all()
        ],
        "tracked_companies": [
            _portal_to_yaml_dict(p) for p in Portal.objects.all()
        ],
        "job_boards": [
            _board_to_yaml_dict(b) for b in JobBoard.objects.all()
        ],
    }

    for key in existing:
        if key not in doc:
            doc[key] = existing[key]

    content = yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)
    atomic_write_with_backup(path, content)

    stats = {
        "exported": Portal.objects.count() + SearchQuery.objects.count() + JobBoard.objects.count(),
        "path": str(path),
    }
    logger.info("DB→YAML export: %s", stats)
    return stats
