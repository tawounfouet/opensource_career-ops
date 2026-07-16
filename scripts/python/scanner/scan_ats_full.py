#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

from scripts.python import PROJECT_ROOT
from scripts.python.other.openrouter_runner import add_to_pipeline


PIPELINE_PATH = "data/pipeline.md"
CACHE_DIR = "data/cache/ats-companies"
CACHE_TTL_HOURS = 24
DATASET_BASE = "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data"
SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class SourceSpec:
    name: str
    dataset: str
    to_entry: Callable[[Any], dict[str, str] | None]


def entry_on_host(name: str, careers_url: str, is_canonical_host: Callable[[str], bool]) -> dict[str, str] | None:
    try:
        parsed = urlparse(careers_url)
        host = parsed.hostname or ""
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not host:
        return None
    return {"name": name, "careers_url": careers_url} if is_canonical_host(host) else None


def source_specs() -> dict[str, SourceSpec]:
    return {
        "greenhouse": SourceSpec(
            "greenhouse",
            f"{DATASET_BASE}/greenhouse_companies.json",
            lambda slug: entry_on_host(str(slug), f"https://job-boards.greenhouse.io/{slug}", lambda h: h == "job-boards.greenhouse.io")
            if SLUG_RE.match(str(slug))
            else None,
        ),
        "lever": SourceSpec(
            "lever",
            f"{DATASET_BASE}/lever_companies.json",
            lambda slug: entry_on_host(str(slug), f"https://jobs.lever.co/{slug}", lambda h: h == "jobs.lever.co") if SLUG_RE.match(str(slug)) else None,
        ),
        "ashby": SourceSpec(
            "ashby",
            f"{DATASET_BASE}/ashby_companies.json",
            lambda slug: entry_on_host(str(slug), f"https://jobs.ashbyhq.com/{slug}", lambda h: h == "jobs.ashbyhq.com") if SLUG_RE.match(str(slug)) else None,
        ),
        "workday": SourceSpec("workday", f"{DATASET_BASE}/workday_companies.json", workday_entry),
    }


def workday_entry(line: Any) -> dict[str, str] | None:
    parts = str(line).split("|")
    if len(parts) != 3:
        return None
    tenant, instance, site = parts
    if not all(part and SLUG_RE.match(part) for part in parts):
        return None
    host = f"{tenant}.{instance}.myworkdayjobs.com"
    return entry_on_host(tenant, f"https://{host}/{site}", lambda h: h == host and h.endswith(".myworkdayjobs.com"))


KNOWN_FLAGS = {
    "--since",
    "--limit",
    "--ats",
    "--seeds",
    "--dry-run",
    "--liveness",
    "--verbose",
    "--md-out",
    "--json",
    "--include-undated",
    "--shuffle",
    "--help",
    "-h",
}
VALUE_FLAGS = {"--since", "--limit", "--ats", "--seeds", "--md-out"}


def value_of(args: list[str], flag: str) -> str | None:
    for idx, item in enumerate(args):
        if item == flag and idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            return args[idx + 1]
        if item.startswith(flag + "="):
            return item.split("=", 1)[1]
    return None


def parse_args(argv: list[str], *, available_sources: list[str] | None = None) -> dict[str, Any]:
    sources = available_sources or list(source_specs())
    consumed_values = set()
    for idx, item in enumerate(argv):
        if item in VALUE_FLAGS and idx + 1 < len(argv) and not argv[idx + 1].startswith("--"):
            consumed_values.add(idx + 1)
    unknown_flags = [item for idx, item in enumerate(argv) if item.startswith("-") and idx not in consumed_values and item.split("=", 1)[0] not in KNOWN_FLAGS]
    if unknown_flags:
        raise ValueError(f"unrecognized flag(s): {', '.join(unknown_flags)}")
    seeds = [item.strip().lower() for item in (value_of(argv, "--seeds") or "").split(",") if item.strip()]
    ats_arg = value_of(argv, "--ats")
    ats = [item.strip().lower() for item in ats_arg.split(",") if item.strip()] if ats_arg else ([] if seeds else sources)
    unknown = [item for item in ats if item not in sources]
    if unknown:
        raise ValueError(f"unknown ATS source(s): {', '.join(unknown)}")
    return {
        "sinceDays": int(value_of(argv, "--since") or 3),
        "limit": float("inf") if value_of(argv, "--limit") is None else int(value_of(argv, "--limit") or 0),
        "ats": ats,
        "seeds": seeds,
        "dryRun": "--dry-run" in argv,
        "liveness": "--liveness" in argv,
        "verbose": "--verbose" in argv,
        "mdOut": value_of(argv, "--md-out"),
        "json": "--json" in argv,
        "includeUndated": "--include-undated" in argv,
        "shuffle": "--shuffle" in argv,
    }


def classify_posting_date(job: dict[str, Any], cutoff_ms: int) -> str:
    posted = job.get("postedAt")
    if isinstance(posted, (int, float)) and posted < cutoff_ms:
        return "stale"
    if not posted:
        return "undated"
    return "keep"


def sample_companies(items: list[Any], limit: int | float, shuffle: bool, *, rng: random.Random | None = None) -> list[Any]:
    if limit == float("inf") or limit >= len(items):
        return list(items)
    if not shuffle:
        return list(items[: int(limit)])
    copy = list(items)
    (rng or random).shuffle(copy)
    return copy[: int(limit)]


def default_fetch_json(url: str, timeout: int = 30) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def load_company_list(
    name: str,
    url: str,
    *,
    root: str | Path = PROJECT_ROOT,
    now_ms: int | None = None,
    fetch_json: Callable[[str], Any] = default_fetch_json,
) -> dict[str, Any]:
    project = Path(root)
    cache_dir = project / CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{name}.json"
    now = now_ms if now_ms is not None else int(date.today().strftime("%s")) * 1000
    if cache_file.exists():
        age_hours = (now - int(cache_file.stat().st_mtime * 1000)) / 3_600_000
        if age_hours < CACHE_TTL_HOURS:
            try:
                return {"list": json.loads(cache_file.read_text(encoding="utf-8")), "status": "ok"}
            except Exception:
                pass
    try:
        data = fetch_json(url)
        if isinstance(data, list):
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return {"list": data, "status": "ok"}
    except Exception:
        pass
    if cache_file.exists():
        try:
            return {"list": json.loads(cache_file.read_text(encoding="utf-8")), "status": "stale"}
        except Exception:
            pass
    return {"list": [], "status": "empty"}


def keyword_filter(config: dict[str, Any] | None, *, key: str = "title_filter") -> Callable[[Any], bool]:
    section = (config or {}).get(key) or {}
    positive = [str(item).lower().strip() for item in (section.get("positive") or []) if str(item).strip()]
    negative = [str(item).lower().strip() for item in (section.get("negative") or []) if str(item).strip()]

    def matches(value: Any) -> bool:
        lower = str(value or "").lower()
        return (not positive or any(item in lower for item in positive)) and not any(item in lower for item in negative)

    return matches


def location_filter(config: dict[str, Any] | None) -> Callable[[Any], bool]:
    section = (config or {}).get("location_filter") or {}
    allow = [str(item).lower().strip() for item in (section.get("allow") or []) if str(item).strip()]
    block = [str(item).lower().strip() for item in (section.get("block") or []) if str(item).strip()]
    always_allow = [str(item).lower().strip() for item in (section.get("always_allow") or []) if str(item).strip()]

    def matches(value: Any) -> bool:
        if not isinstance(value, str) or not value.strip():
            return True
        lower = value.lower()
        if always_allow and any(item in lower for item in always_allow):
            return True
        if block and any(item in lower for item in block):
            return False
        return True if not allow else any(item in lower for item in allow)

    return matches


def filter_jobs(
    jobs: list[dict[str, Any]],
    *,
    cutoff_ms: int,
    include_undated: bool,
    title_matches: Callable[[Any], bool],
    location_matches: Callable[[Any], bool],
    seen_urls: set[str] | None = None,
    source: str = "ats-full",
) -> tuple[list[dict[str, Any]], int]:
    seen = seen_urls if seen_urls is not None else set()
    offers = []
    dropped_no_date = 0
    for job in jobs:
        if not job.get("url") or not job.get("title"):
            continue
        date_class = classify_posting_date(job, cutoff_ms)
        if date_class == "stale":
            continue
        if date_class == "undated" and not include_undated:
            dropped_no_date += 1
            continue
        if not title_matches(job.get("title")) or not location_matches(job.get("location")) or job["url"] in seen:
            continue
        seen.add(job["url"])
        offers.append({**job, "source": source, "dateStatus": "dated" if job.get("postedAt") else "unknown"})
    return offers, dropped_no_date


def markdown_digest(offers: list[dict[str, Any]], *, scan_date: str, since_days: int, liveness: bool) -> str:
    lines = [
        f"# Reverse ATS Scan — {scan_date}",
        f"> {len(offers)} jobs | since {since_days}d | {'liveness ✓' if liveness else 'no liveness check'}",
        "",
    ]
    for offer in offers:
        posted = date.fromtimestamp(offer["postedAt"] / 1000).isoformat() if offer.get("postedAt") else "n/a"
        lines.append(f"- [{offer['title']} @ {offer['company']}]({offer['url']}) — {offer.get('location') or 'N/A'} | {offer.get('source')} | {posted}")
    lines.append("")
    return "\n".join(lines)


def json_summary(
    *,
    scan_date: str,
    opts: dict[str, Any],
    total_available: int,
    total_scanned: int,
    cap_hit: bool,
    dataset_status: dict[str, str],
    offers: list[dict[str, Any]],
    dropped_no_date: int,
    total_errors: int,
    saved: bool,
) -> dict[str, Any]:
    return {
        "date": scan_date,
        "sources": opts["ats"],
        "sinceDays": opts["sinceDays"],
        "companiesAvailable": total_available,
        "companiesScanned": total_scanned,
        "capHit": cap_hit,
        "datasetStatus": dataset_status,
        "postingsKept": len(offers),
        "postingsDroppedNoDate": dropped_no_date,
        "unreachableBoards": total_errors,
        "saved": saved,
        "offers": [
            {
                "company": offer.get("company"),
                "title": offer.get("title"),
                "url": offer.get("url"),
                "location": offer.get("location") or None,
                "postedAt": date.fromtimestamp(offer["postedAt"] / 1000).isoformat() if offer.get("postedAt") else None,
                "dateStatus": offer.get("dateStatus") or ("dated" if offer.get("postedAt") else "unknown"),
                "source": offer.get("source"),
            }
            for offer in offers
        ],
    }


def run_reverse_scan(
    *,
    root: str | Path = PROJECT_ROOT,
    argv: list[str] | None = None,
    provider_fetchers: dict[str, Callable[[dict[str, str]], list[dict[str, Any]]]] | None = None,
    fetch_json: Callable[[str], Any] = default_fetch_json,
    today: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    specs = source_specs()
    opts = parse_args(argv or [], available_sources=list(specs))
    project = Path(root)
    portals = project / "config/portals.yml"
    if not portals.exists():
        raise FileNotFoundError("portals.yml not found")
    config = yaml.safe_load(portals.read_text(encoding="utf-8")) or {}
    title_matches = keyword_filter(config)
    location_matches = location_filter(config)
    scan_date = today or date.today().isoformat()
    cutoff_ms = (now_ms if now_ms is not None else int(date.today().strftime("%s")) * 1000) - opts["sinceDays"] * 86_400_000
    provider_fetchers = provider_fetchers or {}
    seen_urls: set[str] = set()
    offers: list[dict[str, Any]] = []
    total_available = total_scanned = total_errors = dropped_no_date = 0
    cap_hit = False
    dataset_status: dict[str, str] = {}

    for name in opts["ats"]:
        spec = specs[name]
        loaded = load_company_list(name, spec.dataset, root=project, now_ms=now_ms, fetch_json=fetch_json)
        company_list = loaded["list"]
        dataset_status[name] = loaded["status"]
        total_available += len(company_list)
        if opts["limit"] < len(company_list):
            cap_hit = True
        entries = [entry for item in sample_companies(company_list, opts["limit"], opts["shuffle"]) if (entry := spec.to_entry(item))]
        total_scanned += len(entries)
        fetcher = provider_fetchers.get(name)
        if not fetcher:
            continue
        for entry in entries:
            try:
                jobs = fetcher(entry)
            except Exception:
                total_errors += 1
                continue
            kept, no_date = filter_jobs(
                jobs,
                cutoff_ms=cutoff_ms,
                include_undated=opts["includeUndated"],
                title_matches=title_matches,
                location_matches=location_matches,
                seen_urls=seen_urls,
                source=f"{name}-full",
            )
            offers.extend(kept)
            dropped_no_date += no_date

    offers.sort(key=lambda offer: offer.get("postedAt") or 0, reverse=True)
    saved = False
    if offers and not opts["dryRun"]:
        add_to_pipeline(offers, root=project, today=scan_date)
        saved = True
        if opts["mdOut"]:
            out = project / opts["mdOut"]
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{scan_date}.md").write_text(markdown_digest(offers, scan_date=scan_date, since_days=opts["sinceDays"], liveness=opts["liveness"]), encoding="utf-8")
    return json_summary(
        scan_date=scan_date,
        opts=opts,
        total_available=total_available,
        total_scanned=total_scanned,
        cap_hit=cap_hit,
        dataset_status=dataset_status,
        offers=offers,
        dropped_no_date=dropped_no_date,
        total_errors=total_errors,
        saved=saved,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reverse ATS discovery scanner.")
    parser.add_argument("--since", default="3")
    parser.add_argument("--limit")
    parser.add_argument("--ats")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--include-undated", action="store_true")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--md-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_reverse_scan(argv=argv)
    except Exception as error:
        print(f"Fatal: {error}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
