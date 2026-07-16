#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse

import yaml

from scripts.python import PROJECT_ROOT
from scripts.python.other.fingerprint_core import fingerprint_text, find_cross_listings
from scripts.python.scanner.classify_tier import classify_tier
from scripts.python.scanner.trust_validator import build_trust_validator
from scripts.python.tracker.parse import parse_tracker_row, resolve_columns
from scripts.python.tracker.utils import normalize_company


SCAN_HISTORY_PATH = "data/scan-history.tsv"
PIPELINE_PATH = "data/pipeline.md"
APPLICATIONS_PATH = "data/applications.md"
SCAN_RUNS_PATH = "data/scan-runs.tsv"
SCAN_RUNS_HEADER = (
    "timestamp\tstatus\tcompanies\tboards\tfound\tfiltered_title\tfiltered_tier\t"
    "filtered_location\tfiltered_posting_age\tfiltered_salary\tfiltered_content\t"
    "filtered_cooldown\tdupes\tnew_added\terrors\tfiltered_blacklist\n"
)
PIPELINE_SKELETON = """# Pipeline — Pending URLs

Paste job URLs below as `- [ ] {url}` then run `/career-ops pipeline`.

## Pending

## Processed
"""
PENDING_MARKERS = ["## Pending", "## Pendientes"]
PROCESSED_MARKERS = ["## Processed", "## Procesadas"]


def compile_keyword(keyword: str) -> Callable[[str], bool]:
    kw = str(keyword or "").lower()
    if re.match(r"^[a-z]{2,3}$", kw):
        pattern = re.compile(rf"\b{re.escape(kw)}\b")
        return lambda lower: bool(pattern.search(lower))
    return lambda lower: kw in lower


def normalize_keyword_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(item).lower().strip() for item in items if isinstance(item, str) and item.strip()]


def build_title_filter(title_filter: dict[str, Any] | None) -> Callable[[Any], bool]:
    section = title_filter or {}
    positive = [compile_keyword(item) for item in normalize_keyword_list(section.get("positive"))]
    negative = [compile_keyword(item) for item in normalize_keyword_list(section.get("negative"))]

    def matches(title: Any) -> bool:
        lower = str(title or "").lower()
        return (not positive or any(match(lower) for match in positive)) and not any(match(lower) for match in negative)

    return matches


def matched_title_keywords(title: Any, title_filter: dict[str, Any] | None) -> list[str]:
    raw = title_filter.get("positive") if isinstance(title_filter, dict) else []
    if not isinstance(raw, list):
        return []
    lower = str(title or "").lower()
    return [kw for kw in raw if isinstance(kw, str) and kw.strip() and compile_keyword(kw.strip().lower())(lower)]


def build_location_filter(location_filter: dict[str, Any] | None) -> Callable[[Any], bool]:
    if not location_filter:
        return lambda _location: True
    always_allow = normalize_keyword_list(location_filter.get("always_allow"))
    allow = normalize_keyword_list(location_filter.get("allow"))
    block = normalize_keyword_list(location_filter.get("block"))

    def matches(location: Any) -> bool:
        if not isinstance(location, str) or not location.strip():
            return True
        lower = location.lower()
        if always_allow and any(item in lower for item in always_allow):
            return True
        if block and any(item in lower for item in block):
            return False
        if not allow:
            return True
        return any(item in lower for item in allow)

    return matches


def build_posting_age_filter(max_age_days: Any, now_ms: int | None = None) -> Callable[[Any], bool]:
    try:
        max_days = int(max_age_days)
    except Exception:
        return lambda _posted_at: True
    if max_days <= 0:
        return lambda _posted_at: True
    now = now_ms if now_ms is not None else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    cutoff = now - max_days * 86_400_000
    return lambda posted_at: not isinstance(posted_at, (int, float)) or posted_at >= cutoff


def build_content_filter(content_filter: dict[str, Any] | None) -> Callable[[Any, list[str] | None], bool]:
    if not content_filter:
        return lambda _description, _matched_keywords=None: True
    positive = normalize_keyword_list(content_filter.get("positive"))
    negative = normalize_keyword_list(content_filter.get("negative"))
    by_title_keyword: dict[str, dict[str, list[str]]] = {}
    by_raw = content_filter.get("by_title_keyword")
    if isinstance(by_raw, dict):
        for keyword, rule in by_raw.items():
            if not isinstance(keyword, str) or not keyword.strip():
                continue
            by_title_keyword[keyword.strip().lower()] = {
                "positive": normalize_keyword_list((rule or {}).get("positive") if isinstance(rule, dict) else None),
                "negative": normalize_keyword_list((rule or {}).get("negative") if isinstance(rule, dict) else None),
            }

    def rule_passes(lower: str, rule: dict[str, list[str]]) -> bool:
        if rule["negative"] and any(item in lower for item in rule["negative"]):
            return False
        return True if not rule["positive"] else any(item in lower for item in rule["positive"])

    def matches(description: Any, matched_keywords: list[str] | None = None) -> bool:
        if not isinstance(description, str) or not description.strip():
            return True
        lower = description.lower()
        overrides = [by_title_keyword.get(str(keyword).strip().lower()) for keyword in (matched_keywords or [])]
        overrides = [rule for rule in overrides if rule]
        if overrides:
            return any(rule_passes(lower, rule) for rule in overrides)
        if negative and any(item in lower for item in negative):
            return False
        return True if not positive else any(item in lower for item in positive)

    return matches


def build_salary_filter(salary_filter: dict[str, Any] | None) -> Callable[[Any], bool]:
    if not salary_filter:
        return lambda _salary: True
    try:
        minimum = float(salary_filter.get("min", 0) or 0)
        maximum = float(salary_filter.get("max", 0) or 0)
    except Exception:
        return lambda _salary: True
    if minimum < 0 or maximum < 0 or (maximum > 0 and minimum > maximum) or (minimum == 0 and maximum == 0):
        return lambda _salary: True
    filter_currency = str(salary_filter.get("currency") or "").upper().strip()

    def matches(salary: Any) -> bool:
        if not isinstance(salary, dict):
            return True
        job_min = salary.get("min", salary.get("max"))
        job_max = salary.get("max", salary.get("min"))
        if job_min is None and job_max is None:
            return True
        job_currency = str(salary.get("currency") or "").upper().strip()
        if filter_currency and job_currency and filter_currency != job_currency:
            return False
        if minimum > 0 and job_max is not None and float(job_max) < minimum:
            return False
        if maximum > 0 and job_min is not None and float(job_min) > maximum:
            return False
        return True

    return matches


def company_match(job_company: Any, window_company: Any) -> bool:
    def clean_no_spaces(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    c1 = clean_no_spaces(job_company)
    c2 = clean_no_spaces(window_company)
    if c1 == c2:
        return True

    def clean_spaces(value: Any) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()

    s1 = clean_spaces(job_company)
    s2 = clean_spaces(window_company)
    if not s1 or not s2:
        return False
    return bool(re.search(rf"\b{re.escape(s2)}\b", s1) or re.search(rf"\b{re.escape(s1)}\b", s2))


def add_days(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=days)).date().isoformat()


def build_cooldown_filter(windows: dict[str, Any] | None, today: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    if not windows:
        return lambda _job: {"skip": False}
    generic_keywords = {"all", "roles", "role", "family", "bucket", "group", "team"}

    def check(job: dict[str, Any]) -> dict[str, Any]:
        title = str(job.get("title") or "").lower()
        for company, window in windows.items():
            if not isinstance(window, dict) or not company_match(job.get("company") or "", company):
                continue
            last_apply_date = window.get("last_apply_date")
            same_role_days = int(window.get("same_role_days") or 0)
            if not isinstance(last_apply_date, str):
                continue
            cooldown_until = add_days(last_apply_date, same_role_days)
            if today >= cooldown_until:
                continue
            applied_to = window.get("applied_to")
            if isinstance(applied_to, list) and any(str(role).lower() in title for role in applied_to):
                return {"skip": True, "reason": f"cooldown:{company}:{cooldown_until}", "cooldownUntil": cooldown_until}
            bucket = window.get("cross_role_bucket")
            if isinstance(bucket, str):
                keywords = [kw for kw in bucket.lower().split("_") if kw and kw not in generic_keywords]
                if any((re.search(r"\bem\b", title) or "engineering manager" in title) if kw == "em" else kw in title for kw in keywords):
                    return {"skip": True, "reason": f"cooldown:{company}:{cooldown_until}", "cooldownUntil": cooldown_until}
        return {"skip": False}

    return check


def build_company_canonicalizer(aliases: dict[str, Any] | None) -> Callable[[Any], str]:
    mapping: dict[str, str] = {}
    if isinstance(aliases, dict):
        canonical_keys = {str(key).strip().lower() for key in aliases if str(key).strip()}
        mapping.update({key: key for key in canonical_keys})
        alias_targets: dict[str, set[str]] = {}
        for canonical, values in aliases.items():
            canon = str(canonical).strip().lower()
            if not canon:
                continue
            arr = values if isinstance(values, list) else [values]
            for alias in arr:
                key = str(alias or "").strip().lower()
                if not key or key in canonical_keys:
                    continue
                alias_targets.setdefault(key, set()).add(canon)
        for alias, targets in alias_targets.items():
            if len(targets) == 1:
                mapping[alias] = next(iter(targets))

    def canonicalize(name: Any) -> str:
        key = str(name or "").strip().lower()
        return mapping.get(key, key)

    return canonicalize


ROLE_LOCATION_SUFFIXES = {
    "amer",
    "americas",
    "amsterdam",
    "apac",
    "austin",
    "barcelona",
    "bay area",
    "belgium",
    "berlin",
    "boston",
    "brussels",
    "canada",
    "dublin",
    "emea",
    "eu",
    "europe",
    "france",
    "germany",
    "india",
    "london",
    "madrid",
    "netherlands",
    "new york",
    "north america",
    "nyc",
    "on site",
    "onsite",
    "paris",
    "remote",
    "san francisco",
    "spain",
    "uk",
    "united kingdom",
    "united states",
    "us",
    "usa",
}
ROLE_REMOTE_SUFFIXES = {"distributed", "hybrid", "on site", "onsite", "remote", "wfh", "work from home"}


def normalize_role_suffix_tag(tag: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(tag or "").lower()).strip())


def is_role_location_suffix(tag: Any) -> bool:
    normalized = normalize_role_suffix_tag(tag)
    if not normalized:
        return False
    if normalized in ROLE_LOCATION_SUFFIXES:
        return True
    parts = [normalize_role_suffix_tag(part) for part in re.split(r"[,/|;]+|\s+(?:and|or)\s+", str(tag or "").lower())]
    parts = [part for part in parts if part]
    if len(parts) > 1 and all(part in ROLE_LOCATION_SUFFIXES for part in parts):
        return True
    for remote in ROLE_REMOTE_SUFFIXES:
        prefix = f"{remote} "
        if normalized.startswith(prefix) and normalized[len(prefix) :] in ROLE_LOCATION_SUFFIXES:
            return True
    return False


def normalize_role_for_dedup(role: Any) -> str:
    title = str(role or "").lower()
    while True:
        match = re.search(r"\s*[\[(]([^[\]()]+)[\])]\s*$", title)
        if not match or not is_role_location_suffix(match.group(1)):
            break
        title = title[: match.start()].rstrip()
    return re.sub(r"[^a-z0-9]+", " ", title).strip()


def company_role_dedup_key(company: Any, role: Any, canonicalize: Callable[[Any], str] | None = None) -> str:
    canon = canonicalize or (lambda value: str(value or "").strip().lower())
    return f"{canon(company)}::{normalize_role_for_dedup(role)}"


def load_seen_company_roles(root: str | Path = PROJECT_ROOT, canonicalize: Callable[[Any], str] | None = None) -> set[str]:
    file = Path(root) / APPLICATIONS_PATH
    if not file.exists():
        return set()
    lines = file.read_text(encoding="utf-8").splitlines()
    colmap = resolve_columns(lines)
    seen = set()
    for line in lines:
        row = parse_tracker_row(line, colmap)
        if not row:
            continue
        company = str(row.company or "").strip()
        role = str(row.role or "").strip()
        if company and role:
            seen.add(company_role_dedup_key(company, role, canonicalize))
    return seen


def normalize_scan_scalar(value: Any) -> str:
    return re.sub(r" {2,}", " ", re.sub(r"[\r\n\t]+", " ", str(value if value is not None else ""))).strip()


def normalize_scan_url(value: Any) -> str:
    return str(value if value is not None else "").strip().split()[0] if str(value if value is not None else "").strip() else ""


def sanitize_markdown_field(value: Any) -> str:
    return normalize_scan_scalar(value).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "/")


def sanitize_pipeline_url(value: Any) -> str:
    return normalize_scan_url(value).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "%7C")


def sanitize_tsv_field(value: Any) -> str:
    normalized = normalize_scan_scalar(value)
    return f"'{normalized}" if re.match(r"^[=+\-@]", normalized) else normalized


def posted_at_iso_date(posted_at: Any) -> str:
    if not isinstance(posted_at, (int, float)) or posted_at <= 0:
        return ""
    return datetime.fromtimestamp(posted_at / 1000, tz=timezone.utc).date().isoformat()


def format_compensation(salary: Any) -> str:
    if not isinstance(salary, dict):
        return ""

    def num(value: Any) -> str | None:
        return str(round(float(value))) if isinstance(value, (int, float)) and float(value) > 0 else None

    lo = num(salary.get("min"))
    hi = num(salary.get("max"))
    amount = f"{lo}-{hi}" if lo and hi and lo != hi else (lo or hi or "")
    if not amount:
        return ""
    currency = str(salary.get("currency") or "").strip()
    return sanitize_markdown_field(f"{amount} {currency}" if currency else amount)


def format_pipeline_offer(offer: dict[str, Any]) -> str:
    base = f"- [ ] {sanitize_pipeline_url(offer.get('url'))} | {sanitize_markdown_field(offer.get('company'))} | {sanitize_markdown_field(offer.get('title'))}"
    location = sanitize_markdown_field(offer.get("location")) if isinstance(offer.get("location"), str) else ""
    compensation = format_compensation(offer.get("salary"))
    line = base
    if compensation:
        line = f"{base} | {location} | {compensation}"
    elif location:
        line = f"{base} | {location}"
    posted = posted_at_iso_date(offer.get("postedAt"))
    if posted:
        line = f"{line} | posted: {posted}"
    note = sanitize_markdown_field(offer.get("note")) if isinstance(offer.get("note"), str) else ""
    return f"{line} | note: {note}" if note else line


def format_scan_history_row(offer: dict[str, Any], scan_date: str, status: str = "added") -> str:
    return "\t".join(
        sanitize_tsv_field(value)
        for value in [
            normalize_scan_url(offer.get("url")),
            scan_date,
            offer.get("source"),
            offer.get("title"),
            offer.get("company"),
            status,
            offer.get("location") or "",
            offer.get("fingerprint") or fingerprint_text(str(offer.get("description") or "")),
            posted_at_iso_date(offer.get("postedAt")),
        ]
    )


def append_to_pipeline(offers: list[dict[str, Any]], root: str | Path = PROJECT_ROOT) -> None:
    if not offers:
        return
    file = Path(root) / PIPELINE_PATH
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_text(PIPELINE_SKELETON, encoding="utf-8")
    text = file.read_text(encoding="utf-8")
    marker = next((item for item in PENDING_MARKERS if item in text), None)
    block = "\n" + "\n".join(format_pipeline_offer(offer) for offer in offers) + "\n"
    if marker is None:
        processed_positions = [text.find(item) for item in PROCESSED_MARKERS if text.find(item) != -1]
        insert_at = min(processed_positions) if processed_positions else len(text)
        text = text[:insert_at] + "\n## Pending\n" + block + "\n" + text[insert_at:]
    else:
        idx = text.index(marker)
        after_marker = idx + len(marker)
        next_section = text.find("\n## ", after_marker)
        insert_at = len(text) if next_section == -1 else next_section
        text = text[:insert_at] + block + text[insert_at:]
    file.write_text(text, encoding="utf-8")


def append_to_scan_history(offers: list[dict[str, Any]], scan_date: str, root: str | Path = PROJECT_ROOT, status: str = "added") -> None:
    file = Path(root) / SCAN_HISTORY_PATH
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_text("url\tfirst_seen\tportal\ttitle\tcompany\tstatus\tlocation\tfingerprint\tposted_date\n", encoding="utf-8")
    with file.open("a", encoding="utf-8") as handle:
        for offer in offers:
            handle.write(format_scan_history_row(offer, scan_date, status) + "\n")


PERMANENT_SCAN_HISTORY_STATUSES = {"skipped_invalid_url", "skipped_blocked_host"}


def days_between_iso_dates(start: str, end: str) -> int | None:
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (end_date - start_date).days


def should_dedup_scan_history_row(
    row: dict[str, str],
    *,
    recheck_after_days: int | None = None,
    today: str | None = None,
) -> bool:
    status = row.get("status") or "added"
    first_seen = row.get("firstSeen") or row.get("first_seen") or ""
    current = today or date.today().isoformat()
    if status in PERMANENT_SCAN_HISTORY_STATUSES:
        return True
    if status.startswith("cooldown:"):
        cooldown_until = status.split(":")[-1]
        return current < cooldown_until
    if status != "added":
        return True
    if recheck_after_days is None:
        return True
    age_days = days_between_iso_dates(first_seen, current)
    if age_days is None:
        return True
    return age_days < recheck_after_days


def scan_history_policy(config: dict[str, Any] | None = None) -> dict[str, int | None]:
    raw = ((config or {}).get("scan_history") or {}).get("recheck_after_days")
    try:
        parsed = int(raw)
    except Exception:
        parsed = -1
    return {"recheckAfterDays": parsed if parsed >= 0 else None}


def load_seen_urls(root: str | Path = PROJECT_ROOT, *, recheck_after_days: int | None = None, today: str | None = None) -> dict[str, Any]:
    project = Path(root)
    seen: set[str] = set()
    recheck_eligible = 0
    history = project / SCAN_HISTORY_PATH
    if history.exists():
        for line in history.read_text(encoding="utf-8").splitlines()[1:]:
            cols = line.split("\t")
            if not cols or not cols[0]:
                continue
            row = {"url": cols[0], "firstSeen": cols[1] if len(cols) > 1 else "", "status": cols[5] if len(cols) > 5 else "added"}
            if should_dedup_scan_history_row(row, recheck_after_days=recheck_after_days, today=today):
                seen.add(row["url"])
            else:
                recheck_eligible += 1
    pipeline = project / PIPELINE_PATH
    if pipeline.exists():
        for match in re.finditer(r"- \[[ x]\] (https?://\S+)", pipeline.read_text(encoding="utf-8")):
            seen.add(match.group(1))
    applications = project / APPLICATIONS_PATH
    if applications.exists():
        for match in re.finditer(r"https?://[^\s|)]+", applications.read_text(encoding="utf-8")):
            seen.add(match.group(0))
    return {"seen": seen, "recheckEligible": recheck_eligible}


def load_fingerprint_history(root: str | Path = PROJECT_ROOT) -> list[dict[str, str]]:
    file = Path(root) / SCAN_HISTORY_PATH
    if not file.exists():
        return []
    rows = []
    for line in file.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if cols and cols[0] == "url":
            continue
        if len(cols) < 8 or not cols[7].strip():
            continue
        rows.append(
            {
                "url": (cols[0] or "").strip(),
                "dateStr": (cols[1] or "").strip(),
                "title": (cols[3] or "").strip(),
                "company": (cols[4] or "").strip(),
                "fingerprint": cols[7].strip(),
            }
        )
    return rows


def parse_blacklist(text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for line in str(text or "").replace("\r", "").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        company = cells[1] if len(cells) > 1 else ""
        if not company or re.match(r"^[-: ]+$", company) or company.lower() == "company":
            continue
        key = normalize_company(company)
        if key and key not in entries:
            entries[key] = {
                "company": company,
                "since": cells[2] if len(cells) > 2 else "",
                "scope": cells[3] if len(cells) > 3 else "",
                "reason": cells[4] if len(cells) > 4 else "",
            }
    return entries


def load_blacklist(root: str | Path = PROJECT_ROOT) -> dict[str, dict[str, str]]:
    file = Path(root) / "data/blacklist.md"
    return parse_blacklist(file.read_text(encoding="utf-8")) if file.exists() else {}


def default_fetch_json(url: str, opts: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    options = opts or {}
    headers = {
        "user-agent": "career-ops-python-scan/1.0",
        "accept": "application/json",
        **{str(k): str(v) for k, v in (options.get("headers") or {}).items()},
    }
    body = options.get("body")
    data = body.encode("utf-8") if isinstance(body, str) else body
    request = urllib.request.Request(url, data=data, headers=headers, method=options.get("method"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def default_fetch_text(url: str, opts: dict[str, Any] | None = None, timeout: int = 30) -> str:
    options = opts or {}
    headers = {
        "user-agent": "career-ops-python-scan/1.0",
        "accept": "text/plain,text/markdown,*/*",
        **{str(k): str(v) for k, v in (options.get("headers") or {}).items()},
    }
    request = urllib.request.Request(url, headers=headers, method=options.get("method"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json_call(fetch_json: Callable[..., Any], url: str | None, opts: dict[str, Any] | None = None) -> Any:
    if not url:
        raise ValueError("missing provider API URL")
    try:
        return fetch_json(url, opts or {})
    except TypeError:
        return fetch_json(url)


def fetch_text_call(fetch_text: Callable[..., str], url: str | None, opts: dict[str, Any] | None = None) -> str:
    if not url:
        raise ValueError("missing provider feed URL")
    try:
        return fetch_text(url, opts or {})
    except TypeError:
        return fetch_text(url)


def parse_epoch_ms(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        text = str(value).replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).timestamp() * 1000)
    except Exception:
        return None


def assert_hosted_url(url: str, *, allowed_hosts: set[str], label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"{label}: URL must use HTTPS: {url}")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"{label}: untrusted hostname {parsed.hostname!r}")
    return url


def greenhouse_api_url(entry: dict[str, Any]) -> str | None:
    allowed = {"boards-api.greenhouse.io", "boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
    if entry.get("api"):
        return assert_hosted_url(str(entry["api"]), allowed_hosts=allowed, label="greenhouse")
    match = re.search(r"job-boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)", str(entry.get("careers_url") or ""))
    return f"https://boards-api.greenhouse.io/v1/boards/{match.group(1)}/jobs" if match else None


def lever_api_url(entry: dict[str, Any]) -> str | None:
    allowed = {"api.lever.co", "api.eu.lever.co"}
    if entry.get("api"):
        return assert_hosted_url(str(entry["api"]), allowed_hosts=allowed, label="lever")
    parsed = urlparse(str(entry.get("careers_url") or ""))
    host_match = re.match(r"^jobs\.((?:eu\.)?lever\.co)$", parsed.hostname or "")
    parts = [part for part in parsed.path.split("/") if part]
    if not host_match or not parts:
        return None
    return f"https://api.{host_match.group(1)}/v0/postings/{parts[0]}"


ASHBY_INTERVAL_MULTIPLIERS = {
    "1 HOUR": 2080,
    "1 DAY": 260,
    "1 WEEK": 52,
    "2 WEEK": 26,
    "0.5 MONTH": 24,
    "1 MONTH": 12,
    "2 MONTH": 6,
    "3 MONTH": 4,
    "6 MONTH": 2,
    "1 YEAR": 1,
}


def ashby_api_url(entry: dict[str, Any]) -> str | None:
    if entry.get("api"):
        return assert_hosted_url(str(entry["api"]), allowed_hosts={"api.ashbyhq.com"}, label="ashby")
    match = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", str(entry.get("careers_url") or ""))
    return f"https://api.ashbyhq.com/posting-api/job-board/{match.group(1)}?includeCompensation=true" if match else None


def parse_ashby_compensation(job: dict[str, Any]) -> dict[str, Any] | None:
    comp = job.get("compensation") if isinstance(job, dict) else None
    if not isinstance(comp, dict):
        return None
    multiplier = ASHBY_INTERVAL_MULTIPLIERS.get(str(comp.get("interval") or "1 YEAR"))
    if not multiplier:
        return None

    def number(value: Any) -> float | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            parsed = float(value)
        except Exception:
            return None
        return parsed if parsed >= 0 else None

    min_value = number(comp.get("minValue"))
    max_value = number(comp.get("maxValue"))
    if min_value is None and max_value is None:
        return None
    low = (min_value if min_value is not None else max_value) * multiplier
    high = (max_value if max_value is not None else min_value) * multiplier
    return {"min": min(low, high), "max": max(low, high), "currency": str(comp.get("currency") or "").upper().strip()}


def ashby_location(job: dict[str, Any]) -> str:
    parts: list[str] = []
    if isinstance(job.get("location"), str) and job["location"].strip():
        parts.append(job["location"].strip())
    for secondary in job.get("secondaryLocations") if isinstance(job.get("secondaryLocations"), list) else []:
        if not isinstance(secondary, dict):
            continue
        if isinstance(secondary.get("location"), str) and secondary["location"].strip():
            parts.append(secondary["location"].strip())
        postal = ((secondary.get("address") or {}).get("postalAddress") or {}) if isinstance(secondary.get("address"), dict) else {}
        for key in ["addressLocality", "addressCountry"]:
            if isinstance(postal.get(key), str) and postal[key].strip():
                parts.append(postal[key].strip())
    return " · ".join(dict.fromkeys(parts))


WORKDAY_PAGE_SIZE = 20
WORKDAY_DEFAULT_MAX_PAGES = 100
WORKDAY_MAX_PAGES_CAP = 1500
WORKDAY_EARLY_STOP_MARGIN_MS = 2 * 86_400_000
SMARTRECRUITERS_CAREERS_HOSTS = {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}
SMARTRECRUITERS_PAGE_SIZE = 100
SMARTRECRUITERS_MAX_PAGES = 50


def resolve_workday_max_pages(entry: dict[str, Any]) -> int:
    value = entry.get("max_pages")
    return min(value, WORKDAY_MAX_PAGES_CAP) if isinstance(value, int) and value > 0 else WORKDAY_DEFAULT_MAX_PAGES


def workday_endpoint(entry: dict[str, Any]) -> dict[str, str] | None:
    for raw in [entry.get("api"), entry.get("careers_url")]:
        if not isinstance(raw, str) or not raw.strip():
            continue
        match = re.match(r"^https://([\w-]+)\.(wd[\w-]*)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)", raw)
        if not match:
            continue
        tenant, instance, site = match.groups()
        origin = f"https://{tenant}.{instance}.myworkdayjobs.com"
        return {
            "api": f"{origin}/wday/cxs/{tenant}/{site}/jobs",
            "jobBase": f"{origin}/{site}",
            "origin": origin,
            "tenant": tenant,
            "site": site,
        }
    return None


def parse_workday_posted_on(label: Any, now_ms: int | None = None) -> int | None:
    if not label:
        return None
    now = now_ms if now_ms is not None else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    text = str(label)
    if re.search(r"posted\s+today", text, re.IGNORECASE):
        return now
    if re.search(r"posted\s+yesterday", text, re.IGNORECASE):
        return now - 86_400_000
    match = re.search(r"posted\s+(\d+)(\+?)\s*day", text, re.IGNORECASE)
    if not match or match.group(2) == "+":
        return None
    return now - int(match.group(1)) * 86_400_000


def workday_location_from_path(external_path: Any) -> str:
    match = re.search(r"/job/([^/]+)/", str(external_path or ""))
    if not match:
        return ""
    from urllib.parse import unquote

    return unquote(match.group(1)).replace("-", " ")


def parse_workday_response(payload: Any, entry: dict[str, Any], now_ms: int | None = None) -> list[dict[str, Any]]:
    endpoint = workday_endpoint(entry)
    job_base = endpoint["jobBase"] if endpoint else ""
    postings = payload.get("jobPostings") if isinstance(payload, dict) and isinstance(payload.get("jobPostings"), list) else []
    jobs = []
    for job in postings:
        if not isinstance(job, dict):
            continue
        external_path = job.get("externalPath")
        title = str(job.get("title") or "").strip()
        if not external_path or not title:
            continue
        jobs.append(
            {
                "title": title,
                "url": f"{job_base}{external_path}",
                "company": entry.get("name"),
                "location": job.get("locationsText") or workday_location_from_path(external_path),
                "postedAt": parse_workday_posted_on(job.get("postedOn"), now_ms=now_ms),
            }
        )
    return jobs


def workday_page_is_past_window(jobs: list[dict[str, Any]], since_ms: int | None) -> bool:
    if not isinstance(since_ms, int):
        return False
    dated = [job.get("postedAt") for job in jobs if isinstance(job.get("postedAt"), (int, float))]
    return bool(dated) and min(dated) < since_ms - WORKDAY_EARLY_STOP_MARGIN_MS


def smartrecruiters_slug(entry: dict[str, Any]) -> str | None:
    for raw in [entry.get("api"), entry.get("careers_url")]:
        if not isinstance(raw, str) or not raw.strip():
            continue
        parsed = urlparse(raw)
        if parsed.scheme != "https" or parsed.hostname not in SMARTRECRUITERS_CAREERS_HOSTS:
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[0]
    return None


def smartrecruiters_postings_url(slug: str, offset: int = 0) -> str:
    return f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit={SMARTRECRUITERS_PAGE_SIZE}&offset={offset}&status=PUBLIC"


def smartrecruiters_api_url(entry: dict[str, Any]) -> str | None:
    slug = smartrecruiters_slug(entry)
    return smartrecruiters_postings_url(slug, 0) if slug else None


def slugify_job(value: Any) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()))


def parse_smartrecruiters_response(payload: Any, company_name: str) -> list[dict[str, Any]]:
    items = payload.get("content") if isinstance(payload, dict) and isinstance(payload.get("content"), list) else []
    jobs = []
    for job in items:
        if not isinstance(job, dict):
            continue
        location = job.get("location") if isinstance(job.get("location"), dict) else {}
        full_location = location.get("fullLocation") or ", ".join(str(location.get(key)) for key in ["city", "region", "country"] if location.get(key))
        loc = ", ".join(part for part in [full_location, "Remote" if location.get("remote") else ""] if part)
        url = ""
        ref = job.get("ref")
        if isinstance(ref, str):
            parsed = urlparse(ref)
            if parsed.scheme == "https" and parsed.hostname == "api.smartrecruiters.com" and parsed.path.startswith("/v1/companies/"):
                url = f"https://jobs.smartrecruiters.com/{parsed.path[len('/v1/companies/'):]}"
        if not url and job.get("id"):
            company_slug = slugify_job(company_name)
            title_slug = slugify_job(job.get("name"))
            if company_slug:
                url = f"https://jobs.smartrecruiters.com/{company_slug}/{job['id']}-{title_slug}"
        jobs.append({"title": job.get("name") or "", "url": url, "location": loc, "company": company_name})
    return jobs


def workable_feed_url(entry: dict[str, Any]) -> str | None:
    raw = entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname != "apply.workable.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    return f"https://apply.workable.com/{parts[0]}/jobs.md" if parts else None


def parse_workable_markdown(text: Any, company_name: str) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    jobs = []
    for line in text.splitlines():
        if not line.startswith("|") or "[View]" not in line:
            continue
        cols = [col.strip() for col in line.split("|")]
        if len(cols) < 8:
            continue
        title = cols[1]
        if not title or title == "Title":
            continue
        match = re.search(r"\[View\]\(([^)]+)\)", line)
        url = match.group(1) if match else ""
        if url.endswith(".md"):
            url = url[:-3]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "apply.workable.com":
            continue
        jobs.append({"title": title, "url": parsed.geturl(), "company": company_name, "location": cols[3] or ""})
    return jobs


TEAMTAILOR_HOST_RE = re.compile(r"^([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\.teamtailor\.com$", re.IGNORECASE)
PERSONIO_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.jobs\.personio\.(de|com)$", re.IGNORECASE)
RECRUITEE_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.recruitee\.com$", re.IGNORECASE)
PINPOINT_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.pinpointhq\.com$", re.IGNORECASE)
BAMBOOHR_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.bamboohr\.com$", re.IGNORECASE)
COMEET_API_HOST = "www.comeet.co"
REMOTEOK_FEED_URL = "https://remoteok.com/api"
REMOTIVE_FEED_URL = "https://remotive.com/api/remote-jobs"
CSOD_PAGE_SIZE = 25
CSOD_MAX_PAGES = 40
CSOD_MAX_JOBS = 1000
PHENOM_PAGE_SIZE = 100
PHENOM_MAX_PAGES = 40
PHENOM_MAX_JOBS = 1000
SUCCESSFACTORS_MAX_PAGES = 40
SUCCESSFACTORS_MAX_JOBS = 1000
SUCCESSFACTORS_CSB_PAGE_SIZE = 10
SUCCESSFACTORS_CSB_MAX_PAGES_PER_LOCALE = 100
SUCCESSFACTORS_CSB_MAX_LOCALES = 16
SUCCESSFACTORS_CSB_DEFAULT_LOCALES = ["de_DE", "en_US"]
SUCCESSFACTORS_CSB_LOCALE_PRIORITY = ["de_DE", "en_US", "en_GB", "en_EN"]


def teamtailor_feed_url(entry: dict[str, Any], *, explicit: bool = False) -> str | None:
    raw = entry.get("api") or entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if not explicit and not TEAMTAILOR_HOST_RE.match(parsed.hostname):
        return None
    return f"https://{parsed.hostname}/jobs.rss"


def xml_tag_text(block: str, tag: str) -> str:
    match = re.search(rf"<{re.escape(tag)}\b[^>]*>([\s\S]*?)</{re.escape(tag)}>", block, re.IGNORECASE)
    if not match:
        return ""
    inner = match.group(1)
    cdata = re.match(r"^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$", inner)
    return (cdata.group(1) if cdata else unescape(inner)).strip()


def parse_rss_date(value: str) -> int | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    except Exception:
        return parse_epoch_ms(value)


def teamtailor_location(item: str) -> str:
    place = ", ".join(part for part in [xml_tag_text(item, "tt:city"), xml_tag_text(item, "tt:country")] if part)
    if place:
        return place
    return "Remote" if xml_tag_text(item, "remoteStatus").lower() in {"fully", "temporary"} else ""


def clean_https_url(value: str) -> str:
    parsed = urlparse(value.strip())
    return parsed.geturl() if parsed.scheme == "https" and parsed.hostname else ""


def parse_teamtailor_feed(xml: Any, default_company: str = "Teamtailor") -> list[dict[str, Any]]:
    if not isinstance(xml, str):
        return []
    company = default_company.strip() if isinstance(default_company, str) and default_company.strip() else "Teamtailor"
    jobs = []
    for item in re.findall(r"<item\b[^>]*>[\s\S]*?</item>", xml, flags=re.IGNORECASE):
        url = clean_https_url(xml_tag_text(item, "link"))
        title = xml_tag_text(item, "title")
        if not url or not title:
            continue
        job = {"title": title, "company": company, "location": teamtailor_location(item), "url": url}
        posted_at = parse_rss_date(xml_tag_text(item, "pubDate"))
        if posted_at is not None:
            job["postedAt"] = posted_at
        jobs.append(job)
    return jobs


def personio_feed_url(entry: dict[str, Any]) -> str | None:
    raw = entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or not PERSONIO_HOST_RE.match(parsed.hostname):
        return None
    return f"https://{parsed.hostname}/xml"


def parse_personio_xml(xml: Any, company_name: str, host: str) -> list[dict[str, Any]]:
    if not isinstance(xml, str):
        return []
    stripped = re.sub(r"<jobDescriptions\b[^>]*>[\s\S]*?</jobDescriptions>", "", xml, flags=re.IGNORECASE)
    jobs = []
    for block in re.findall(r"<position\b[^>]*>[\s\S]*?</position>", stripped, flags=re.IGNORECASE):
        title = xml_tag_text(block, "name")
        job_id = xml_tag_text(block, "id")
        if not title or not re.match(r"^\d+$", job_id):
            continue
        offices: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"<office\b[^>]*>([\s\S]*?)</office>", block, flags=re.IGNORECASE):
            office = unescape(match.group(1)).strip()
            if office and office not in seen:
                seen.add(office)
                offices.append(office)
        job = {
            "title": title,
            "url": f"https://{host}/job/{job_id}",
            "location": ", ".join(offices),
            "company": company_name,
        }
        posted_at = parse_epoch_ms(xml_tag_text(block, "createdAt"))
        if posted_at is not None:
            job["postedAt"] = posted_at
        jobs.append(job)
    return jobs


def recruitee_api_url(entry: dict[str, Any]) -> str | None:
    raw = entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or not RECRUITEE_HOST_RE.match(parsed.hostname):
        return None
    return f"https://{parsed.hostname}/api/offers/"


def parse_recruitee_response(payload: Any, company_name: str) -> list[dict[str, Any]]:
    offers = payload.get("offers") if isinstance(payload, dict) and isinstance(payload.get("offers"), list) else []
    jobs = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        raw_url = offer.get("careers_url") or offer.get("url") or ""
        url = ""
        if isinstance(raw_url, str) and raw_url:
            parsed = urlparse(raw_url)
            if parsed.scheme == "https" and parsed.hostname:
                url = parsed.geturl()
        location = offer.get("location") or ", ".join(
            part for part in [offer.get("city") or "", offer.get("country") or "", "Remote" if offer.get("remote") else ""] if part
        )
        jobs.append({"title": offer.get("title") or "", "url": url, "location": location, "company": company_name})
    return jobs


def pinpoint_api_url(entry: dict[str, Any]) -> str | None:
    raw = entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or not PINPOINT_HOST_RE.match(parsed.hostname):
        return None
    return f"https://{parsed.hostname}/postings.json"


def parse_pinpoint_response(payload: Any, company_name: str) -> list[dict[str, Any]]:
    postings = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), list) else []
    jobs = []
    for posting in postings:
        if not isinstance(posting, dict):
            continue
        title = str(posting.get("title") or "").strip()
        raw_url = str(posting.get("url") or "").strip()
        parsed = urlparse(raw_url)
        if not title or parsed.scheme != "https" or not parsed.hostname:
            continue
        location = posting.get("location") if isinstance(posting.get("location"), dict) else {}
        loc_name = str(location.get("name") or "").strip()
        city = str(location.get("city") or "").strip()
        province = str(location.get("province") or "").strip()
        jobs.append({"title": title, "url": parsed.geturl(), "location": loc_name or ", ".join(part for part in [city, province] if part), "company": company_name})
    return jobs


def bamboohr_origin(entry: dict[str, Any]) -> str | None:
    raw = entry.get("api") or entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or not BAMBOOHR_HOST_RE.match(parsed.hostname):
        return None
    return f"https://{parsed.hostname}"


def bamboohr_api_url(entry: dict[str, Any]) -> str | None:
    origin = bamboohr_origin(entry)
    return f"{origin}/careers/list" if origin else None


def parse_bamboohr_response(payload: Any, company_name: str, origin: str) -> list[dict[str, Any]]:
    rows = payload.get("result") if isinstance(payload, dict) and isinstance(payload.get("result"), list) else []
    jobs = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("jobOpeningName") or str(row.get("id") or "").strip() == "":
            continue
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        loc = ", ".join(part for part in [location.get("city"), location.get("state"), "Remote" if row.get("isRemote") else ""] if part)
        jobs.append(
            {
                "title": str(row.get("jobOpeningName")),
                "url": f"{origin}/careers/{str(row.get('id')).strip()}",
                "company": company_name,
                "location": loc,
            }
        )
    return jobs


def is_comeet_api_url(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    parsed = urlparse(raw)
    return parsed.scheme == "https" and parsed.hostname == COMEET_API_HOST and parsed.path.startswith("/careers-api/")


def comeet_api_url(entry: dict[str, Any]) -> str | None:
    if is_comeet_api_url(entry.get("api")):
        return str(entry.get("api"))
    if is_comeet_api_url(entry.get("careers_url")):
        return str(entry.get("careers_url"))
    return None


def redact_comeet_token(url: Any) -> str:
    text = str(url or "")
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        from urllib.parse import parse_qsl, urlencode, urlunparse

        query = urlencode([(key, "REDACTED" if key.lower() == "token" else value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)])
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))
    return re.sub(r"([?&]token=)[^&#]*", r"\1REDACTED", text, flags=re.IGNORECASE)


def parse_comeet_response(payload: Any, company_name: str) -> list[dict[str, Any]]:
    positions = payload if isinstance(payload, list) else []
    jobs = []
    for row in positions:
        job = row if isinstance(row, dict) else {}
        raw_url = job.get("url_active_page") or job.get("url_comeet_hosted_page") or ""
        parsed = urlparse(raw_url) if isinstance(raw_url, str) else urlparse("")
        title = str(job.get("name") or "").strip()
        if not title or parsed.scheme != "https" or not parsed.hostname:
            continue
        location_data = job.get("location") if isinstance(job.get("location"), dict) else {}
        base = str(location_data.get("name") or "").strip()
        remote = "Remote" if location_data.get("is_remote") else ""
        location = base if remote and re.search(r"remote", base, re.IGNORECASE) else ", ".join(part for part in [base, remote] if part)
        result = {"title": title, "url": parsed.geturl(), "location": location, "company": company_name}
        posted_at = parse_epoch_ms(job.get("time_updated"))
        if posted_at is not None:
            result["postedAt"] = posted_at
        jobs.append(result)
    return jobs


def parse_remoteok_response(payload: Any, board_name: str) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    jobs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("position") or "").strip()
        raw_url = str(row.get("url") or "").strip()
        parsed = urlparse(raw_url)
        if not title or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        company = str(row.get("company") or "").strip() or board_name or "RemoteOK"
        location = str(row.get("location") or "").strip()
        jobs.append({"title": title, "url": parsed.geturl(), "company": company, "location": location})
    return jobs


def parse_remotive_response(payload: Any, board_name: str) -> list[dict[str, Any]]:
    rows = payload.get("jobs") if isinstance(payload, dict) and isinstance(payload.get("jobs"), list) else []
    jobs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        raw_url = str(row.get("url") or "").strip()
        parsed = urlparse(raw_url)
        if not title or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        company = str(row.get("company_name") or "").strip() or board_name or "Remotive"
        location = str(row.get("candidate_required_location") or "").strip()
        jobs.append({"title": title, "url": parsed.geturl(), "company": company, "location": location})
    return jobs


def csod_config(entry: dict[str, Any]) -> dict[str, Any] | None:
    raw = entry.get("api") or entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"https", "http"} or (host != "csod.com" and not host.endswith(".csod.com")):
        return None
    match = re.search(r"/ux/ats/careersite/(\d+)(?:/|$)", parsed.path, re.IGNORECASE)
    if not match:
        return None
    site_id = int(match.group(1))
    from urllib.parse import parse_qs

    corp_name = (parse_qs(parsed.query).get("c") or [host.split(".")[0]])[0]
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "origin": origin,
        "siteId": site_id,
        "corpName": corp_name,
        "homeUrl": f"{origin}/ux/ats/careersite/{site_id}/home?c={quote(corp_name)}",
        "searchApi": f"{origin}/services/x/career-site/v1/search",
    }


def extract_csod_token(html: Any) -> str:
    match = re.search(r'"token"\s*:\s*"([A-Za-z0-9._-]+)"', html if isinstance(html, str) else "")
    return match.group(1) if match else ""


def parse_csod_date(raw: Any) -> int | None:
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", str(raw or "").strip())
    if not match:
        return None
    month, day, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        parsed = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000)


def clean_csod_locations(raw: Any) -> str:
    rows = raw if isinstance(raw, list) else []
    locations: list[str] = []
    for loc in rows:
        if not isinstance(loc, dict):
            continue
        city = str(loc.get("city") or "").strip()
        country = str(loc.get("country") or "").strip()
        item = f"{city}, {country}" if city and country else city or country
        if item and item not in locations:
            locations.append(item)
    return " / ".join(locations)


def parse_csod_requisitions(payload: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (((payload or {}).get("data") or {}).get("requisitions") if isinstance(payload, dict) else [])
    rows = rows if isinstance(rows, list) else []
    out = []
    for req in rows:
        if not isinstance(req, dict):
            continue
        req_id = str(req.get("requisitionId") or "").strip()
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(req.get("displayJobTitle") or ""))).strip()
        if not req_id or not title:
            continue
        row = {
            "id": req_id,
            "title": title,
            "url": f"{cfg['origin']}/ux/ats/careersite/{cfg['siteId']}/home/requisition/{req_id}?c={quote(str(cfg['corpName']))}",
            "location": clean_csod_locations(req.get("locations")),
        }
        posted_at = parse_csod_date(req.get("postingEffectiveDate"))
        if posted_at is not None:
            row["postedAt"] = posted_at
        out.append(row)
    return out


def phenom_config(entry: dict[str, Any]) -> dict[str, Any] | None:
    raw = entry.get("api") or entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return None
    block = entry.get("phenom") if isinstance(entry.get("phenom"), dict) else {}
    url_prefix = str(block.get("urlPrefix") or "global/en").strip("/")
    selected_fields = block.get("selectedFields") if isinstance(block.get("selectedFields"), dict) else {}
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "origin": origin,
        "widgetsApi": f"{origin}/widgets",
        "lang": block.get("lang") if isinstance(block.get("lang"), str) else "en_global",
        "country": block.get("country") if isinstance(block.get("country"), str) else "global",
        "urlPrefix": url_prefix,
        "selectedFields": selected_fields,
    }


def phenom_slugify(title: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(title or ""))
    asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"(^-+|-+$)", "", re.sub(r"[^a-zA-Z0-9]+", "-", asciiish)) or "job"


def parse_phenom_date(raw: Any) -> int | None:
    return parse_epoch_ms(raw)


def phenom_job_location(job: Any) -> str:
    data = job if isinstance(job, dict) else {}
    direct = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(data.get("location") or data.get("cityStateCountry") or data.get("cityState") or ""))).strip()
    if direct:
        return direct
    parts = []
    for key in ["city", "state", "country"]:
        value = str(data.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts)


def parse_phenom_refine_search(payload: Any, cfg: dict[str, Any]) -> dict[str, Any]:
    refine = payload.get("refineSearch") if isinstance(payload, dict) and isinstance(payload.get("refineSearch"), dict) else {}
    total = refine.get("totalHits") if isinstance(refine.get("totalHits"), int) else None
    jobs = ((refine.get("data") or {}).get("jobs") if isinstance(refine.get("data"), dict) else [])
    rows = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("jobId") or "").strip()
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(job.get("title") or ""))).strip()
        if not job_id or not title:
            continue
        row = {
            "id": job_id,
            "title": title,
            "url": f"{cfg['origin']}/{cfg['urlPrefix']}/job/{quote(job_id)}/{phenom_slugify(title)}",
            "location": phenom_job_location(job),
        }
        posted_at = parse_phenom_date(job.get("postedDate") or job.get("dateCreated"))
        if posted_at is not None:
            row["postedAt"] = posted_at
        rows.append(row)
    return {"total": total, "rows": rows}


def successfactors_config(entry: dict[str, Any]) -> dict[str, str] | None:
    raw = entry.get("api") or entry.get("careers_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "origin": origin,
        "tileApi": f"{origin}/tile-search-results/",
        "jobBase": origin,
        "jobsApi": f"{origin}/services/recruiting/v1/jobs",
        "searchPage": f"{origin}/search/",
    }


def sf_clean_html(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", unescape(str(value or "")))).strip()


def successfactors_city_from_slug(data_url: Any, title: Any) -> str:
    from urllib.parse import unquote

    path = unquote(str(data_url or ""))
    match = re.search(r"/job/([^/]+)/", path)
    if not match:
        return ""
    slug = match.group(1).lower()
    words = re.findall(r"[\w]+", str(title or "").lower(), flags=re.UNICODE)
    if not words:
        return ""
    anchor = r"[^\w]+".join(re.escape(word) for word in words[:2])
    hit = re.search(anchor, slug, flags=re.UNICODE)
    if not hit or hit.start() <= 0:
        return ""
    return " ".join(word[:1].upper() + word[1:] for word in re.split(r"[^\w]+", slug[: hit.start()], flags=re.UNICODE) if word)


def parse_successfactors_tiles(html_text: Any, job_base: str) -> list[dict[str, str]]:
    if not isinstance(html_text, str):
        return []
    rows = []
    for match in re.finditer(r'<li class="job-tile job-id-(\d+)\b[\s\S]*?</li>', html_text):
        job_id = match.group(1)
        block = match.group(0)
        url_match = re.search(r'data-url="([^"]+)"', block)
        title_match = re.search(r'class="jobTitle-link[^"]*"[^>]*>([\s\S]*?)</a>', block)
        if not url_match or not title_match:
            continue
        path = unescape(url_match.group(1))
        title = sf_clean_html(title_match.group(1))
        if not title:
            continue
        city_match = re.search(r'id="[^"]*-section-city-value">([\s\S]*?)</div>', block)
        location = sf_clean_html(city_match.group(1)) if city_match else successfactors_city_from_slug(path, title)
        url = path if re.match(r"^https?://", path, flags=re.IGNORECASE) else f"{job_base}{path if path.startswith('/') else '/' + path}"
        rows.append({"id": job_id, "title": title, "url": url, "location": location})
    return rows


def successfactors_extract_locales(html_text: Any) -> list[str]:
    if not isinstance(html_text, str):
        return []
    found = []
    for locale in re.findall(r"locale=([a-z]{2}_[A-Z]{2})\b", html_text):
        if locale not in found:
            found.append(locale)
    priority = {locale: index for index, locale in enumerate(SUCCESSFACTORS_CSB_LOCALE_PRIORITY)}
    found.sort(key=lambda value: (priority.get(value, len(priority)), value))
    return found[:SUCCESSFACTORS_CSB_MAX_LOCALES]


def parse_successfactors_csb_date(raw: Any) -> int | None:
    text = str(raw or "").strip()
    slash = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", text)
    dot = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", text)
    if slash:
        month, day, year = int(slash.group(1)), int(slash.group(2)), int(slash.group(3))
    elif dot:
        day, month, year = int(dot.group(1)), int(dot.group(2)), int(dot.group(3))
    else:
        return None
    if year < 100:
        year += 2000
    try:
        parsed = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000)


def clean_successfactors_csb_location(raw: Any) -> str:
    parts = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    cleaned = []
    for part in parts:
        value = sf_clean_html(part)
        if value and value not in cleaned:
            cleaned.append(value)
    return " / ".join(cleaned)


def parse_successfactors_csb_jobs(payload: Any, cfg: dict[str, str], locale: str) -> list[dict[str, Any]]:
    items = payload.get("jobSearchResult") if isinstance(payload, dict) and isinstance(payload.get("jobSearchResult"), list) else []
    rows = []
    for item in items:
        response = item.get("response") if isinstance(item, dict) and isinstance(item.get("response"), dict) else None
        if not response:
            continue
        job_id = str(response.get("id") or "").strip()
        title = sf_clean_html(response.get("unifiedStandardTitle") or response.get("jobTitle") or "")
        if not job_id or not title:
            continue
        slug = unescape(str(response.get("unifiedUrlTitle") or response.get("urlTitle") or "job"))
        slug = re.sub(r"-{2,}", "-", re.sub(r"[?#&]+", "-", slug))
        row = {
            "id": job_id,
            "title": title,
            "url": f"{cfg['origin']}/job/{slug}/{job_id}-{locale}",
            "location": clean_successfactors_csb_location(response.get("jobLocationShort")),
        }
        posted_at = parse_successfactors_csb_date(response.get("unifiedStandardStart"))
        if posted_at is not None:
            row["postedAt"] = posted_at
        rows.append(row)
    return rows


LOCAL_PARSER_ALLOWED_INTERPRETERS = {"python3", "python", "node", "deno", "bun", "sh", "bash"}
LOCAL_PARSER_DEFAULT_TIMEOUT_MS = 20_000
LOCAL_PARSER_MAX_BUFFER_BYTES = 2_000_000


def local_parser_detect(entry: dict[str, Any]) -> bool:
    parser = entry.get("parser")
    if not isinstance(parser, dict):
        return False
    command = str(parser.get("command") or "").strip()
    if not command:
        return False
    return command in LOCAL_PARSER_ALLOWED_INTERPRETERS or (Path(command).is_file() and not command.startswith("-"))


def local_parser_resolve_interpreter(command: str) -> str | None:
    if command in LOCAL_PARSER_ALLOWED_INTERPRETERS:
        return command
    return None


def local_parser_validate_url(url: str, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{label}: URL must use http(s): {url}")


def local_parser_validate_arg(arg: str, label: str) -> None:
    if arg.startswith("-"):
        raise ValueError(f"{label}: argument must not start with '-': {arg}")


def local_parser_resolve_inside_root(path_str: str, root: Path, label: str) -> Path:
    resolved = (root / path_str).resolve()
    if not str(resolved).startswith(str(root.resolve())):
        raise ValueError(f"{label}: path escapes project root: {path_str}")
    return resolved


def local_parser_fetch(entry: dict[str, Any], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    import json as _json
    import subprocess

    parser = entry.get("parser") or {}
    command = str(parser.get("command") or "").strip()
    script_raw = str(parser.get("script") or "").strip()
    extra_args = parser.get("args") or []
    timeout_ms = int(parser.get("timeout_ms") or LOCAL_PARSER_DEFAULT_TIMEOUT_MS)
    max_buffer = int(parser.get("max_buffer_bytes") or LOCAL_PARSER_MAX_BUFFER_BYTES)
    root = Path(ctx.get("root") or PROJECT_ROOT)

    if not command or not script_raw:
        raise ValueError("local-parser: command and script are required")

    interpreter = local_parser_resolve_interpreter(command)
    script_path = local_parser_resolve_inside_root(script_raw, root, "local-parser")

    cmd_args: list[str] = []
    if interpreter:
        cmd_args = [interpreter, str(script_path)]
    else:
        cmd_args = [str(local_parser_resolve_inside_root(command, root, "local-parser")), str(script_path)]

    careers_url = str(entry.get("careers_url") or "")
    company = str(entry.get("name") or "")
    if careers_url:
        local_parser_validate_url(careers_url, "local-parser")
    if company:
        local_parser_validate_arg(company, "local-parser company name")

    resolved_args: list[str] = []
    for arg in extra_args:
        if isinstance(arg, str):
            expanded = arg.replace("{careers_url}", careers_url).replace("{company}", company)
            local_parser_validate_arg(expanded, "local-parser arg")
            resolved_args.append(expanded)
    cmd_args.extend(resolved_args)

    timeout_s = max(1, timeout_ms // 1000)
    result = subprocess.run(
        cmd_args,
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(f"local-parser: exit code {result.returncode}: {(result.stderr or result.stdout)[:500]}")

    stdout = result.stdout[:max_buffer]
    data = _json.loads(stdout)
    if isinstance(data, dict):
        data = data.get("jobs") or data.get("results") or []
    if not isinstance(data, list):
        raise ValueError("local-parser: output must be a JSON array or {jobs:[...]}/{results:[...]}")

    jobs: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("job_title") or "").strip()
        url = str(item.get("url") or item.get("jobUrl") or item.get("apply_url") or "").strip()
        if not title or not url:
            continue
        job: dict[str, Any] = {"title": title, "url": url, "company": entry.get("name")}
        if isinstance(item.get("location"), str) and item["location"].strip():
            job["location"] = item["location"]
        if isinstance(item.get("salary"), dict):
            job["salary"] = item["salary"]
        if isinstance(item.get("postedAt"), (int, float)):
            job["postedAt"] = item["postedAt"]
        if isinstance(item.get("description"), str):
            job["description"] = item["description"]
        jobs.append(job)
    return jobs


def builtin_providers(fetch_json: Callable[..., Any] = default_fetch_json, fetch_text: Callable[..., str] = default_fetch_text) -> dict[str, dict[str, Any]]:
    def greenhouse_detect(entry: dict[str, Any]) -> bool:
        try:
            return greenhouse_api_url(entry) is not None
        except Exception:
            return False

    def greenhouse_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        data = fetch_json_call(fetch_json, greenhouse_api_url(entry))
        return [
            {
                "title": job.get("title") or "",
                "url": job.get("absolute_url") or "",
                "company": entry.get("name"),
                "location": (job.get("location") or {}).get("name") if isinstance(job.get("location"), dict) else "",
                "postedAt": parse_epoch_ms(job.get("first_published")),
            }
            for job in (data.get("jobs") if isinstance(data, dict) and isinstance(data.get("jobs"), list) else [])
            if job.get("absolute_url")
        ]

    def lever_detect(entry: dict[str, Any]) -> bool:
        try:
            return lever_api_url(entry) is not None
        except Exception:
            return False

    def lever_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        data = fetch_json_call(fetch_json, lever_api_url(entry))
        return [
            {
                "title": job.get("text") or "",
                "url": job.get("hostedUrl") or "",
                "company": entry.get("name"),
                "location": (job.get("categories") or {}).get("location") if isinstance(job.get("categories"), dict) else "",
                "description": job.get("descriptionPlain") if isinstance(job.get("descriptionPlain"), str) else "",
                "postedAt": job.get("createdAt") if isinstance(job.get("createdAt"), (int, float)) else None,
            }
            for job in data
        ] if isinstance(data, list) else []

    def ashby_detect(entry: dict[str, Any]) -> bool:
        try:
            return ashby_api_url(entry) is not None
        except Exception:
            return False

    def ashby_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        data = fetch_json_call(fetch_json, ashby_api_url(entry))
        jobs = data.get("jobs") if isinstance(data, dict) and isinstance(data.get("jobs"), list) else []
        return [
            {
                "title": job.get("title") or "",
                "url": job.get("jobUrl") or "",
                "company": entry.get("name"),
                "location": ashby_location(job),
                "salary": parse_ashby_compensation(job),
                "postedAt": parse_epoch_ms(job.get("publishedAt")),
            }
            for job in jobs
        ]

    def workday_detect(entry: dict[str, Any]) -> bool:
        return workday_endpoint(entry) is not None

    def workday_fetch(entry: dict[str, Any], ctx: dict[str, Any]) -> list[dict[str, Any]]:
        endpoint = workday_endpoint(entry)
        if not endpoint:
            raise ValueError(f"workday: cannot derive CXS endpoint for {entry.get('name')}")

        def page_opts(offset: int) -> dict[str, Any]:
            return {
                "method": "POST",
                "headers": {
                    "content-type": "application/json",
                    "accept": "application/json",
                    "user-agent": "career-ops-python-scan/1.0",
                    "accept-language": "en-US,en;q=0.9",
                    "origin": endpoint["origin"],
                    "referer": f"{endpoint['jobBase']}/",
                },
                "body": json.dumps({"limit": WORKDAY_PAGE_SIZE, "offset": offset, "searchText": "", "appliedFacets": {}}),
            }

        now = ctx.get("nowMs") if isinstance(ctx.get("nowMs"), int) else None
        first = fetch_json_call(fetch_json, endpoint["api"], page_opts(0))
        jobs = parse_workday_response(first, entry, now_ms=now)
        first_postings = first.get("jobPostings") if isinstance(first, dict) and isinstance(first.get("jobPostings"), list) else []
        total = first.get("total") if isinstance(first, dict) and isinstance(first.get("total"), (int, float)) else None
        max_pages = resolve_workday_max_pages(entry)
        pages_to_fetch = min((int(total) + WORKDAY_PAGE_SIZE - 1) // WORKDAY_PAGE_SIZE, max_pages) if total is not None else (max_pages if len(first_postings) >= WORKDAY_PAGE_SIZE else 1)
        ctx_cap = ctx.get("maxPages")
        if isinstance(ctx_cap, int) and ctx_cap > 0:
            pages_to_fetch = min(pages_to_fetch, ctx_cap)
        since_ms = ctx.get("sinceMs") if isinstance(ctx.get("sinceMs"), int) else None

        stop = workday_page_is_past_window(jobs, since_ms)
        if since_ms is not None and ctx.get("includeUndated") is not True and jobs and not any(isinstance(job.get("postedAt"), (int, float)) for job in jobs):
            stop = True
            setattr(jobs, "workdayNoDateSkip", True) if hasattr(jobs, "__dict__") else None
        page = 1
        while not stop and page < pages_to_fetch:
            payload = fetch_json_call(fetch_json, endpoint["api"], page_opts(page * WORKDAY_PAGE_SIZE))
            page_jobs = parse_workday_response(payload, entry, now_ms=now)
            jobs.extend(page_jobs)
            if total is None:
                postings = payload.get("jobPostings") if isinstance(payload, dict) and isinstance(payload.get("jobPostings"), list) else []
                if len(postings) < WORKDAY_PAGE_SIZE:
                    break
            if workday_page_is_past_window(page_jobs, since_ms):
                break
            page += 1
        return jobs

    def smartrecruiters_detect(entry: dict[str, Any]) -> bool:
        return smartrecruiters_api_url(entry) is not None

    def smartrecruiters_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        slug = smartrecruiters_slug(entry)
        if not slug:
            raise ValueError(f"smartrecruiters: cannot derive API URL for {entry.get('name')}")
        jobs: list[dict[str, Any]] = []
        for page in range(SMARTRECRUITERS_MAX_PAGES):
            api_url = smartrecruiters_postings_url(slug, page * SMARTRECRUITERS_PAGE_SIZE)
            assert_hosted_url(api_url, allowed_hosts={"api.smartrecruiters.com"}, label="smartrecruiters")
            payload = fetch_json_call(fetch_json, api_url, {"redirect": "error"})
            parsed = parse_smartrecruiters_response(payload, str(entry.get("name") or ""))
            if not parsed:
                break
            jobs.extend(parsed)
            if len(parsed) < SMARTRECRUITERS_PAGE_SIZE:
                break
        return jobs

    def workable_detect(entry: dict[str, Any]) -> bool:
        return workable_feed_url(entry) is not None

    def workable_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        feed_url = workable_feed_url(entry)
        if not feed_url:
            raise ValueError(f"workable: cannot derive feed URL for {entry.get('name')}")
        assert_hosted_url(feed_url, allowed_hosts={"apply.workable.com"}, label="workable")
        text = fetch_text_call(fetch_text, feed_url, {"redirect": "error"})
        return parse_workable_markdown(text, str(entry.get("name") or ""))

    def teamtailor_detect(entry: dict[str, Any]) -> bool:
        return teamtailor_feed_url(entry, explicit=False) is not None

    def teamtailor_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        explicit = entry.get("provider") == "teamtailor"
        feed_url = teamtailor_feed_url(entry, explicit=explicit)
        if not feed_url:
            raise ValueError(f"teamtailor: cannot derive jobs.rss URL for {entry.get('name') or 'Teamtailor'}")
        parsed = urlparse(feed_url)
        if parsed.scheme != "https" or not parsed.hostname or (not explicit and not TEAMTAILOR_HOST_RE.match(parsed.hostname)):
            raise ValueError(f"teamtailor: untrusted feed URL: {feed_url}")
        text = fetch_text_call(fetch_text, feed_url, {"redirect": "error"})
        return parse_teamtailor_feed(text, str(entry.get("name") or "Teamtailor"))

    def personio_detect(entry: dict[str, Any]) -> bool:
        return personio_feed_url(entry) is not None

    def personio_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        feed_url = personio_feed_url(entry)
        if not feed_url:
            raise ValueError(f"personio: cannot derive feed URL for {entry.get('name')}")
        parsed = urlparse(feed_url)
        if parsed.scheme != "https" or not parsed.hostname or not PERSONIO_HOST_RE.match(parsed.hostname):
            raise ValueError(f"personio: untrusted feed URL: {feed_url}")
        text = fetch_text_call(fetch_text, feed_url, {"redirect": "error"})
        return parse_personio_xml(text, str(entry.get("name") or ""), parsed.hostname)

    def recruitee_detect(entry: dict[str, Any]) -> bool:
        return recruitee_api_url(entry) is not None

    def recruitee_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        api_url = recruitee_api_url(entry)
        if not api_url:
            raise ValueError(f"recruitee: cannot derive API URL for {entry.get('name')}")
        parsed = urlparse(api_url)
        if parsed.scheme != "https" or not parsed.hostname or not RECRUITEE_HOST_RE.match(parsed.hostname):
            raise ValueError(f"recruitee: untrusted API URL: {api_url}")
        payload = fetch_json_call(fetch_json, api_url, {"redirect": "error"})
        return parse_recruitee_response(payload, str(entry.get("name") or ""))

    def pinpoint_detect(entry: dict[str, Any]) -> bool:
        return pinpoint_api_url(entry) is not None

    def pinpoint_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        api_url = pinpoint_api_url(entry)
        if not api_url:
            raise ValueError(f"pinpoint: cannot derive API URL for {entry.get('name')}")
        parsed = urlparse(api_url)
        if parsed.scheme != "https" or not parsed.hostname or not PINPOINT_HOST_RE.match(parsed.hostname):
            raise ValueError(f"pinpoint: untrusted API URL: {api_url}")
        payload = fetch_json_call(fetch_json, api_url, {"redirect": "error"})
        return parse_pinpoint_response(payload, str(entry.get("name") or ""))

    def bamboohr_detect(entry: dict[str, Any]) -> bool:
        return bamboohr_api_url(entry) is not None

    def bamboohr_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        origin = bamboohr_origin(entry)
        api_url = bamboohr_api_url(entry)
        if not origin or not api_url:
            raise ValueError(f"bamboohr: cannot derive API URL for {entry.get('name')}")
        payload = fetch_json_call(fetch_json, api_url, {"redirect": "error"})
        return parse_bamboohr_response(payload, str(entry.get("name") or ""), origin)

    def comeet_detect(entry: dict[str, Any]) -> bool:
        return comeet_api_url(entry) is not None

    def comeet_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        api_url = comeet_api_url(entry)
        if not api_url:
            raise ValueError(f"comeet: cannot derive API URL for {entry.get('name')} (set api: to the full careers-api positions URL)")
        parsed = urlparse(api_url)
        if parsed.scheme != "https" or parsed.hostname != COMEET_API_HOST or not parsed.path.startswith("/careers-api/"):
            raise ValueError(f"comeet: untrusted API URL: {redact_comeet_token(api_url)}")
        payload = fetch_json_call(fetch_json, api_url, {"redirect": "error"})
        return parse_comeet_response(payload, str(entry.get("name") or ""))

    def remoteok_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        payload = fetch_json_call(fetch_json, REMOTEOK_FEED_URL, {"redirect": "error"})
        if not isinstance(payload, list):
            raise ValueError("remoteok: unexpected API response")
        return parse_remoteok_response(payload, str(entry.get("name") or "RemoteOK"))

    def remotive_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        payload = fetch_json_call(fetch_json, REMOTIVE_FEED_URL, {"redirect": "error"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("remotive: unexpected API response")
        return parse_remotive_response(payload, str(entry.get("name") or "Remotive"))

    def csod_detect(entry: dict[str, Any]) -> bool:
        return csod_config(entry) is not None

    def csod_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = csod_config(entry)
        if not cfg:
            raise ValueError(f"csod: cannot resolve careersite URL for {entry.get('name')}")
        html = fetch_text_call(fetch_text, cfg["homeUrl"], {"headers": {"accept": "text/html"}})
        token = extract_csod_token(html)
        if not token:
            raise ValueError(f"csod: no anonymous token on {cfg['homeUrl']}")
        max_pages = min(entry.get("max_pages"), CSOD_MAX_PAGES) if isinstance(entry.get("max_pages"), int) and entry.get("max_pages") > 0 else CSOD_MAX_PAGES
        jobs: list[dict[str, Any]] = []
        seen: set[str] = set()
        total = None
        for page in range(1, max_pages + 1):
            payload = fetch_json_call(
                fetch_json,
                cfg["searchApi"],
                {
                    "method": "POST",
                    "redirect": "error",
                    "headers": {"content-type": "application/json", "accept": "application/json", "authorization": f"Bearer {token}"},
                    "body": json.dumps(
                        {
                            "careerSiteId": cfg["siteId"],
                            "careerSitePageId": cfg["siteId"],
                            "pageNumber": page,
                            "pageSize": CSOD_PAGE_SIZE,
                            "cultureId": 1,
                            "cultureName": "en-US",
                            "searchText": "",
                            "states": [],
                            "countryCodes": [],
                            "cities": [],
                            "placeID": "",
                            "radius": None,
                            "postingsWithinDays": None,
                            "customFieldCheckboxKeys": [],
                            "customFieldDropdowns": [],
                            "customFieldRadios": [],
                        }
                    ),
                },
            )
            if total is None and isinstance(payload, dict):
                raw_total = (payload.get("data") or {}).get("totalCount") if isinstance(payload.get("data"), dict) else None
                total = raw_total if isinstance(raw_total, int) else None
            rows = parse_csod_requisitions(payload, cfg)
            if not rows:
                break
            fresh = 0
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                fresh += 1
                job = {"title": row["title"], "url": row["url"], "company": entry.get("name"), "location": row["location"]}
                if isinstance(row.get("postedAt"), int):
                    job["postedAt"] = row["postedAt"]
                jobs.append(job)
                if len(jobs) >= CSOD_MAX_JOBS:
                    break
            if fresh == 0 or len(jobs) >= CSOD_MAX_JOBS or len(rows) < CSOD_PAGE_SIZE:
                break
            if total is not None and page * CSOD_PAGE_SIZE >= total:
                break
        return jobs

    def phenom_detect(entry: dict[str, Any]) -> bool:
        raw = entry.get("api") or entry.get("careers_url")
        if not isinstance(raw, str):
            return False
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        return host == "phenompeople.com" or host.endswith(".phenompeople.com")

    def phenom_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = phenom_config(entry)
        if not cfg:
            raise ValueError(f"phenom: cannot resolve origin for {entry.get('name')}")
        max_pages = min(entry.get("max_pages"), PHENOM_MAX_PAGES) if isinstance(entry.get("max_pages"), int) and entry.get("max_pages") > 0 else PHENOM_MAX_PAGES
        jobs: list[dict[str, Any]] = []
        seen: set[str] = set()
        total = None
        for page in range(max_pages):
            payload = fetch_json_call(
                fetch_json,
                cfg["widgetsApi"],
                {
                    "method": "POST",
                    "redirect": "error",
                    "headers": {"content-type": "application/json", "accept": "application/json"},
                    "body": json.dumps(
                        {
                            "lang": cfg["lang"],
                            "deviceType": "desktop",
                            "country": cfg["country"],
                            "pageName": "search-results",
                            "ddoKey": "refineSearch",
                            "sortBy": "",
                            "subsearch": "",
                            "from": page * PHENOM_PAGE_SIZE,
                            "jobs": True,
                            "counts": True,
                            "all_fields": ["category", "country", "city"],
                            "size": PHENOM_PAGE_SIZE,
                            "clearAll": False,
                            "jdsource": "facets",
                            "isSliderEnable": False,
                            "pageId": "page10",
                            "siteType": "external",
                            "keywords": "",
                            "global": cfg["country"] == "global",
                            "selected_fields": cfg["selectedFields"],
                            "locationData": {},
                        }
                    ),
                },
            )
            parsed = parse_phenom_refine_search(payload, cfg)
            if total is None:
                total = parsed["total"]
            rows = parsed["rows"]
            if not rows:
                break
            fresh = 0
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                fresh += 1
                job = {"title": row["title"], "url": row["url"], "company": entry.get("name"), "location": row["location"]}
                if isinstance(row.get("postedAt"), int):
                    job["postedAt"] = row["postedAt"]
                jobs.append(job)
                if len(jobs) >= PHENOM_MAX_JOBS:
                    break
            if fresh == 0 or len(jobs) >= PHENOM_MAX_JOBS:
                break
            if total is not None and (page + 1) * PHENOM_PAGE_SIZE >= total:
                break
        return jobs

    def successfactors_detect(entry: dict[str, Any]) -> bool:
        raw = str(entry.get("api") or entry.get("careers_url") or "")
        return bool(re.search(r"successfactors\.(eu|com)|jobs2web\.com", raw, re.IGNORECASE))

    def successfactors_fetch_rmk(entry: dict[str, Any], cfg: dict[str, str]) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        seen: set[str] = set()
        startrow = 0
        for _page in range(SUCCESSFACTORS_MAX_PAGES):
            html_text = fetch_text_call(fetch_text, f"{cfg['tileApi']}?startrow={startrow}", {"redirect": "error", "headers": {"accept": "text/html"}})
            tiles = parse_successfactors_tiles(html_text, cfg["jobBase"])
            if not tiles:
                break
            fresh = 0
            for tile in tiles:
                if tile["id"] in seen:
                    continue
                seen.add(tile["id"])
                fresh += 1
                jobs.append({"title": tile["title"], "url": tile["url"], "company": entry.get("name"), "location": tile["location"]})
                if len(jobs) >= SUCCESSFACTORS_MAX_JOBS:
                    break
            if fresh == 0 or len(jobs) >= SUCCESSFACTORS_MAX_JOBS:
                break
            startrow += len(tiles)
        return jobs[:SUCCESSFACTORS_MAX_JOBS]

    def successfactors_csb_max_pages(entry: dict[str, Any]) -> int:
        value = entry.get("max_pages")
        return min(value, SUCCESSFACTORS_CSB_MAX_PAGES_PER_LOCALE) if isinstance(value, int) and value > 0 else SUCCESSFACTORS_CSB_MAX_PAGES_PER_LOCALE

    def successfactors_fetch_csb(entry: dict[str, Any], cfg: dict[str, str]) -> list[dict[str, Any]]:
        locales = SUCCESSFACTORS_CSB_DEFAULT_LOCALES
        try:
            html_text = fetch_text_call(fetch_text, cfg["searchPage"], {"redirect": "error", "headers": {"accept": "text/html"}})
            discovered = successfactors_extract_locales(html_text)
            if discovered:
                locales = discovered
        except Exception:
            pass
        max_pages = successfactors_csb_max_pages(entry)
        jobs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for locale in locales:
            if len(jobs) >= SUCCESSFACTORS_MAX_JOBS:
                break
            total = None
            for page in range(max_pages):
                try:
                    payload = fetch_json_call(
                        fetch_json,
                        cfg["jobsApi"],
                        {
                            "method": "POST",
                            "redirect": "error",
                            "headers": {"content-type": "application/json", "accept": "application/json"},
                            "body": json.dumps({"keywords": "", "locale": locale, "location": "", "pageNumber": page, "sortBy": "recent"}),
                        },
                    )
                except Exception:
                    break
                if total is None and isinstance(payload, dict):
                    total = payload.get("totalJobs") if isinstance(payload.get("totalJobs"), int) else None
                raw_count = len(payload.get("jobSearchResult")) if isinstance(payload, dict) and isinstance(payload.get("jobSearchResult"), list) else 0
                if raw_count == 0:
                    break
                rows = parse_successfactors_csb_jobs(payload, cfg, locale)
                for row in rows:
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    job = {"title": row["title"], "url": row["url"], "company": entry.get("name"), "location": row["location"]}
                    if isinstance(row.get("postedAt"), int):
                        job["postedAt"] = row["postedAt"]
                    jobs.append(job)
                    if len(jobs) >= SUCCESSFACTORS_MAX_JOBS:
                        break
                if len(jobs) >= SUCCESSFACTORS_MAX_JOBS:
                    break
                if total is not None and (page + 1) * SUCCESSFACTORS_CSB_PAGE_SIZE >= total:
                    break
                if raw_count < SUCCESSFACTORS_CSB_PAGE_SIZE:
                    break
        return jobs

    def successfactors_fetch(entry: dict[str, Any], _ctx: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = successfactors_config(entry)
        if not cfg:
            raise ValueError(f"successfactors: cannot resolve origin for {entry.get('name')}")
        if str(entry.get("sfVariant") or "").lower() == "csb":
            return successfactors_fetch_csb(entry, cfg)
        rmk_jobs = successfactors_fetch_rmk(entry, cfg)
        return rmk_jobs if rmk_jobs else successfactors_fetch_csb(entry, cfg)

    return {
        "greenhouse": {"id": "greenhouse", "detect": greenhouse_detect, "fetch": greenhouse_fetch},
        "lever": {"id": "lever", "detect": lever_detect, "fetch": lever_fetch},
        "ashby": {"id": "ashby", "detect": ashby_detect, "fetch": ashby_fetch},
        "workday": {"id": "workday", "detect": workday_detect, "fetch": workday_fetch},
        "smartrecruiters": {"id": "smartrecruiters", "detect": smartrecruiters_detect, "fetch": smartrecruiters_fetch},
        "workable": {"id": "workable", "detect": workable_detect, "fetch": workable_fetch},
        "teamtailor": {"id": "teamtailor", "detect": teamtailor_detect, "fetch": teamtailor_fetch},
        "personio": {"id": "personio", "detect": personio_detect, "fetch": personio_fetch},
        "recruitee": {"id": "recruitee", "detect": recruitee_detect, "fetch": recruitee_fetch},
        "pinpoint": {"id": "pinpoint", "detect": pinpoint_detect, "fetch": pinpoint_fetch},
        "bamboohr": {"id": "bamboohr", "detect": bamboohr_detect, "fetch": bamboohr_fetch},
        "comeet": {"id": "comeet", "detect": comeet_detect, "fetch": comeet_fetch},
        "remoteok": {"id": "remoteok", "fetch": remoteok_fetch},
        "remotive": {"id": "remotive", "fetch": remotive_fetch},
        "csod": {"id": "csod", "detect": csod_detect, "fetch": csod_fetch},
        "phenom": {"id": "phenom", "detect": phenom_detect, "fetch": phenom_fetch},
        "successfactors": {"id": "successfactors", "detect": successfactors_detect, "fetch": successfactors_fetch},
    }


def provider_id(provider: Any) -> str:
    if isinstance(provider, dict):
        return str(provider.get("id") or "")
    return str(getattr(provider, "id", ""))


def provider_fetch(provider: Any, entry: dict[str, Any], ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    fetcher = provider.get("fetch") if isinstance(provider, dict) else getattr(provider, "fetch", None)
    if not callable(fetcher):
        raise ValueError(f"provider {provider_id(provider) or '<unknown>'} has no fetch callable")
    try:
        result = fetcher(entry, ctx or {})
    except TypeError:
        result = fetcher(entry)
    if not isinstance(result, list):
        raise ValueError(f"{provider_id(provider)}: fetch() did not return a list")
    return result


def provider_detect(provider: Any, entry: dict[str, Any]) -> bool:
    detector = provider.get("detect") if isinstance(provider, dict) else getattr(provider, "detect", None)
    if not callable(detector):
        return False
    try:
        return bool(detector(entry))
    except Exception:
        return False


def normalize_providers(providers: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    if providers is None:
        return {}
    if isinstance(providers, dict):
        return providers
    return {provider_id(provider): provider for provider in providers if provider_id(provider)}


def load_provider_plugins(paths: list[str | Path] | None) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for raw_path in paths or []:
        directory = Path(raw_path)
        if not directory.exists() or not directory.is_dir():
            continue
        for file in sorted(directory.glob("*.py")):
            if file.name.startswith("_"):
                continue
            module_name = f"career_ops_provider_{abs(hash(str(file.resolve())))}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                provider = getattr(module, "provider", None)
                if provider is None and callable(getattr(module, "get_provider", None)):
                    provider = module.get_provider()
                pid = provider_id(provider)
                fetcher = provider.get("fetch") if isinstance(provider, dict) else getattr(provider, "fetch", None)
                if not pid or not callable(fetcher) or pid in loaded:
                    continue
                loaded[pid] = provider
            except Exception:
                continue
    return loaded


def merge_provider_plugins(base: dict[str, Any], plugin_providers: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    merged = dict(base)
    for pid, provider in normalize_providers(plugin_providers).items():
        if not pid or pid in merged:
            continue
        merged[pid] = provider
    return merged


def resolve_provider(entry: dict[str, Any], providers: dict[str, Any], *, skip_ids: set[str] | None = None) -> dict[str, Any] | None:
    skip_ids = skip_ids or set()
    explicit = entry.get("provider")
    if explicit:
        provider = providers.get(str(explicit))
        if not provider or str(explicit) in skip_ids:
            return {"error": f'unknown provider "{explicit}"'}
        return {"provider": provider}
    if "local-parser" not in skip_ids and local_parser_detect(entry):
        return {"provider": {"id": "local-parser", "detect": local_parser_detect, "fetch": local_parser_fetch}}
    for pid, provider in providers.items():
        if pid in skip_ids or pid == "local-parser":
            continue
        if provider_detect(provider, entry):
            return {"provider": provider}
    return None


def enabled_entries(config: dict[str, Any], *, filter_company: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def valid(items: Any) -> list[dict[str, Any]]:
        out = []
        for entry in items if isinstance(items, list) else []:
            if not isinstance(entry, dict) or entry.get("enabled") is False:
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            if filter_company and filter_company.lower() not in name.lower():
                continue
            out.append(dict(entry))
        return out

    return valid(config.get("tracked_companies")), valid(config.get("job_boards"))


def load_reapply_windows(root: str | Path = PROJECT_ROOT, profile_path: str = "config/profile.yml") -> dict[str, Any]:
    file = Path(root) / profile_path
    if not file.exists():
        return {}
    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    windows = raw.get("re_apply_windows") if isinstance(raw, dict) else {}
    return windows if isinstance(windows, dict) else {}


def careers_url_domain(careers_url: Any) -> str | None:
    if not careers_url:
        return None
    try:
        from urllib.parse import urlparse

        return urlparse(str(careers_url)).hostname
    except Exception:
        return None


def guard_status_for(code: str) -> str:
    return "skipped_blocked_host" if code == "blocked_host" else "skipped_invalid_url"


def liveness_dict(result: Any) -> dict[str, str]:
    if isinstance(result, dict):
        return {
            "result": str(result.get("result") or "uncertain"),
            "code": str(result.get("code") or ""),
            "reason": str(result.get("reason") or ""),
        }
    return {
        "result": str(getattr(result, "result", "uncertain")),
        "code": str(getattr(result, "code", "")),
        "reason": str(getattr(result, "reason", "")),
    }


def verify_offers(offers: list[dict[str, Any]], checker: Callable[[str], Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    if checker is None:
        return {"verified": offers, "expired": [], "dropped": [], "invalid": []}
    verified: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for offer in offers:
        check = liveness_dict(checker(str(offer.get("url") or "")))
        enriched = {**offer, "liveness": check}
        if check["result"] == "expired":
            expired.append(enriched)
        elif check["result"] == "uncertain" and check["code"] in {"invalid_url", "unsupported_protocol", "blocked_host"}:
            invalid.append(enriched)
        elif check["result"] == "uncertain" and check["code"] == "no_apply_control":
            dropped.append(enriched)
        else:
            verified.append(offer)
    return {"verified": verified, "expired": expired, "dropped": dropped, "invalid": invalid}


def append_scan_run_summary(counters: dict[str, Any], root: str | Path = PROJECT_ROOT) -> None:
    file = Path(root) / SCAN_RUNS_PATH
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_text(SCAN_RUNS_HEADER, encoding="utf-8")
    row = [
        counters.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        counters.get("status", "completed"),
        counters.get("companies", 0),
        counters.get("boards", 0),
        counters.get("found", 0),
        counters.get("filteredTitle", 0),
        counters.get("filteredTier", 0),
        counters.get("filteredLocation", 0),
        counters.get("filteredPostingAge", 0),
        counters.get("filteredSalary", 0),
        counters.get("filteredContent", 0),
        counters.get("filteredCooldown", 0),
        counters.get("dupes", 0),
        counters.get("newAdded", 0),
        counters.get("errors", 0),
        counters.get("filteredBlacklist", 0),
    ]
    with file.open("a", encoding="utf-8") as handle:
        handle.write("\t".join(str(item) for item in row) + "\n")


def run_scan(
    *,
    root: str | Path = PROJECT_ROOT,
    config: dict[str, Any] | None = None,
    providers: dict[str, Any] | list[Any] | None = None,
    provider_plugins: dict[str, Any] | list[Any] | None = None,
    dry_run: bool = False,
    verify: bool = False,
    liveness_checker: Callable[[str], Any] | None = None,
    include_blacklisted: bool = False,
    filter_company: str | None = None,
    today: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    project = Path(root)
    if config is None:
        portals = project / "config/portals.yml"
        if not portals.exists():
            raise FileNotFoundError("config/portals.yml not found")
        config = yaml.safe_load(portals.read_text(encoding="utf-8")) or {}
    providers_by_id = merge_provider_plugins(
        normalize_providers(providers) if providers is not None else builtin_providers(),
        provider_plugins,
    )
    companies, boards = enabled_entries(config, filter_company=filter_company)
    targets: list[dict[str, Any]] = []
    skipped_no_provider = 0
    errors: list[dict[str, str]] = []
    empty_targets: list[str] = []
    for is_board, entries in [(False, companies), (True, boards)]:
        for entry in entries:
            resolved = resolve_provider(entry, providers_by_id)
            if not resolved:
                skipped_no_provider += 1
                continue
            if resolved.get("error"):
                errors.append({"company": entry["name"], "error": resolved["error"]})
                continue
            targets.append({**entry, "_provider": resolved["provider"], "_isBoard": is_board})

    scan_date = today or date.today().isoformat()
    title_filter = build_title_filter(config.get("title_filter"))
    location_filter = build_location_filter(config.get("location_filter"))
    posting_age_filter = build_posting_age_filter(config.get("max_posting_age_days"), now_ms=now_ms)
    salary_filter = build_salary_filter(config.get("salary_filter"))
    content_filter = build_content_filter(config.get("content_filter"))
    trust_validator = build_trust_validator(config.get("trust_filter"))
    skip_tiers = {str(item).lower() for item in config.get("skip_tiers", []) if isinstance(item, str)}
    blacklist = load_blacklist(project)
    canonicalize_company = build_company_canonicalizer(config.get("company_aliases"))
    policy = scan_history_policy(config)
    seen_state = load_seen_urls(project, recheck_after_days=policy["recheckAfterDays"], today=scan_date)
    seen_urls: set[str] = seen_state["seen"]
    seen_company_roles = load_seen_company_roles(project, canonicalize_company)
    cooldown_filter = build_cooldown_filter(load_reapply_windows(project), scan_date)

    counters = {
        "companies": len([target for target in targets if not target.get("_isBoard")]),
        "boards": len([target for target in targets if target.get("_isBoard")]),
        "found": 0,
        "filteredTitle": 0,
        "filteredTier": 0,
        "filteredLocation": 0,
        "filteredPostingAge": 0,
        "filteredSalary": 0,
        "filteredContent": 0,
        "filteredCooldown": 0,
        "dupes": 0,
        "newAdded": 0,
        "errors": len(errors),
        "filteredBlacklist": 0,
        "skippedNoProvider": skipped_no_provider,
        "trustAnnotated": 0,
    }
    new_offers: list[dict[str, Any]] = []
    cooldown_offers: list[dict[str, Any]] = []

    for target in targets:
        provider = target["_provider"]
        source = f"{provider_id(provider)}-api"
        try:
            jobs = provider_fetch(provider, target, {"root": project})
        except Exception as error:
            if provider_id(provider) == "local-parser":
                fallback = resolve_provider(target, providers_by_id, skip_ids={"local-parser"})
                if fallback and not fallback.get("error"):
                    try:
                        provider = fallback["provider"]
                        source = f"{provider_id(provider)}-api"
                        jobs = provider_fetch(provider, target, {"root": project})
                    except Exception as fallback_error:
                        errors.append({"company": str(target.get("name") or ""), "error": str(fallback_error)})
                        counters["errors"] += 1
                        continue
                else:
                    errors.append({"company": str(target.get("name") or ""), "error": str(error)})
                    counters["errors"] += 1
                    continue
            else:
                errors.append({"company": str(target.get("name") or ""), "error": str(error)})
                counters["errors"] += 1
                continue
        counters["found"] += len(jobs)
        if not jobs and not target.get("_isBoard"):
            empty_targets.append(target.get("name") or "")
        for raw_job in jobs:
            if not isinstance(raw_job, dict):
                continue
            job = {**raw_job}
            job.setdefault("company", target.get("name"))
            trust = trust_validator(job)
            job["trustScore"] = trust["score"]
            job["trustFlags"] = trust["flags"]
            job["trustLevel"] = trust["level"]

            if blacklist:
                bl_entry = blacklist.get(normalize_company(str(job.get("company") or target.get("name") or "")))
                if bl_entry and not include_blacklisted:
                    counters["filteredBlacklist"] += 1
                    continue
                if bl_entry and include_blacklisted:
                    counters["trustAnnotated"] += 1
                    job["blacklisted"] = True
                    label = f"blacklisted{': ' + bl_entry['reason'] if bl_entry.get('reason') else ''}"
                    job["note"] = f"{label} — {job['note']}" if isinstance(job.get("note"), str) and job["note"].strip() else label

            if not title_filter(job.get("title")):
                counters["filteredTitle"] += 1
                continue
            if skip_tiers and classify_tier(job.get("title")) in skip_tiers:
                counters["filteredTier"] += 1
                continue
            if not location_filter(job.get("location")):
                counters["filteredLocation"] += 1
                continue
            if not posting_age_filter(job.get("postedAt")):
                counters["filteredPostingAge"] += 1
                continue
            if not salary_filter(job.get("salary")):
                counters["filteredSalary"] += 1
                continue
            if not content_filter(job.get("description"), matched_title_keywords(job.get("title"), config.get("title_filter"))):
                counters["filteredContent"] += 1
                continue
            url = normalize_scan_url(job.get("url"))
            if not url or url in seen_urls:
                counters["dupes"] += 1
                continue
            key = company_role_dedup_key(job.get("company"), job.get("title"), canonicalize_company)
            if key in seen_company_roles:
                counters["dupes"] += 1
                continue
            cooldown = cooldown_filter(job)
            if cooldown.get("skip"):
                counters["filteredCooldown"] += 1
                cooldown_offers.append({"job": {**job, "source": source}, "status": cooldown["reason"]})
                continue
            seen_urls.add(url)
            seen_company_roles.add(key)
            domain = careers_url_domain(target.get("careers_url"))
            new_offers.append({**job, "url": url, "source": source, "tracked": bool(domain), "careersUrlDomain": domain})

    verification = verify_offers(new_offers, liveness_checker if verify else None)
    verified = verification["verified"]
    expired = verification["expired"]
    dropped = verification["dropped"]
    invalid = verification["invalid"]
    counters["newAdded"] = len(verified)

    cross_listings: list[dict[str, str]] = []
    if verified:
        history = load_fingerprint_history(project)
        if history:
            for offer in verified:
                offer["fingerprint"] = offer.get("fingerprint") or fingerprint_text(str(offer.get("description") or ""))
            cl_matches = find_cross_listings(verified, history, today=scan_date)
            for match in cl_matches:
                cross_listings.append({
                    "company": str(match.offer.get("company") or ""),
                    "title": str(match.offer.get("title") or ""),
                    "matchedCompany": str(match.row.get("company") or ""),
                    "url": str(match.offer.get("url") or ""),
                    "score": match.score,
                })

    if not dry_run:
        if verified:
            append_to_pipeline(verified, project)
            append_to_scan_history(verified, scan_date, project)
        if cooldown_offers:
            by_status: dict[str, list[dict[str, Any]]] = {}
            for item in cooldown_offers:
                by_status.setdefault(item["status"], []).append(item["job"])
            for status, group in by_status.items():
                append_to_scan_history(group, scan_date, project, status=status)
        if expired:
            append_to_scan_history(expired, scan_date, project, status="skipped_expired")
        if dropped:
            append_to_scan_history(dropped, scan_date, project, status="skipped_no_apply_control")
        if invalid:
            by_status: dict[str, list[dict[str, Any]]] = {}
            for offer in invalid:
                by_status.setdefault(guard_status_for(offer.get("liveness", {}).get("code", "")), []).append(offer)
            for status, group in by_status.items():
                append_to_scan_history(group, scan_date, project, status=status)
        append_scan_run_summary({**counters, "timestamp": f"{scan_date}T00:00:00Z", "status": "completed"}, project)

    return {
        "date": scan_date,
        "targets": len(targets),
        "companies": counters["companies"],
        "boards": counters["boards"],
        "skippedNoProvider": skipped_no_provider,
        "counters": counters,
        "offers": verified,
        "expired": expired,
        "dropped": dropped,
        "invalid": invalid,
        "cooldown": cooldown_offers,
        "crossListings": cross_listings,
        "errors": errors,
        "emptyTargets": empty_targets,
        "dryRun": dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zero-token portal scanner for career-ops.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Use ATS API liveness checks where available.")
    parser.add_argument("--verify-browser", action="store_true", help="Use ATS API checks, then Playwright browser fallback for inconclusive URLs.")
    parser.add_argument("--throttle", nargs="?", const="5000", default="0", help="Jittered delay in ms between --verify checks. Bare --throttle defaults to 5000ms.")
    parser.add_argument("--include-blacklisted", action="store_true")
    parser.add_argument("--company")
    parser.add_argument("--provider-dir", action="append", default=[], help="Directory containing Python provider plugins (*.py).")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checker = None
    verify = args.verify or args.verify_browser
    throttle_ms = int(args.throttle or 0)
    if verify:
        from scripts.python.scanner.check_liveness import build_liveness_checker

        checker = build_liveness_checker(use_browser=args.verify_browser)
    provider_plugins = load_provider_plugins(args.provider_dir)
    try:
        result = run_scan(
            dry_run=args.dry_run,
            verify=verify,
            liveness_checker=checker,
            provider_plugins=provider_plugins,
            include_blacklisted=args.include_blacklisted,
            filter_company=args.company,
        )
    except Exception as error:
        print(json.dumps({"error": str(error)}, indent=2) if args.json else f"ERROR: {error}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        counters = result["counters"]
        skip_tiers_configured = bool(throttle_ms)
        print(f"{'━' * 50}")
        print(f"Portal Scan — {result['date']}")
        print(f"{'━' * 50}")
        print(f"Companies scanned:     {result['companies']}")
        print(f"Job boards scanned:    {result['boards']}")
        print(f"Total jobs found:      {counters['found']}")
        print(f"Filtered by title:     {counters['filteredTitle']} removed")
        if counters.get("filteredTier"):
            print(f"Filtered by tier:      {counters['filteredTier']} removed")
        print(f"Filtered by location:  {counters['filteredLocation']} removed")
        if counters.get("filteredPostingAge"):
            print(f"Filtered by age:       {counters['filteredPostingAge']} removed")
        print(f"Filtered by salary:    {counters['filteredSalary']} removed")
        print(f"Filtered by content:   {counters['filteredContent']} removed")
        if counters.get("filteredCooldown"):
            print(f"Filtered by cooldown:  {counters['filteredCooldown']} removed")
        print(f"Duplicates:            {counters['dupes']} skipped")
        if counters.get("filteredBlacklist"):
            print(f"Blacklisted:           {counters['filteredBlacklist']} skipped")
        if counters.get("trustAnnotated"):
            print(f"Blacklisted:           {counters['trustAnnotated']} annotated (passed through)")
        print(f"New offers added:      {counters['newAdded']}")
        if result.get("expired"):
            print(f"Expired (verified):    {len(result['expired'])} dropped")
        if result.get("dropped"):
            print(f"No apply control:      {len(result['dropped'])} dropped")
        if result.get("invalid"):
            print(f"Invalid (guarded):     {len(result['invalid'])} dropped")
        if result.get("crossListings"):
            print(f"Cross-listings:        {len(result['crossListings'])} flagged (possible agency reposts)")
        if result.get("emptyTargets"):
            print(f"\nEmpty targets:")
            for name in result["emptyTargets"]:
                print(f"  ⚠ {name} (live but returned 0 jobs)")
        if result["errors"]:
            print(f"\nErrors ({len(result['errors'])}):")
            for err in result["errors"]:
                print(f"  ✗ {err['company']}: {err['error']}")
        if result["offers"]:
            print(f"\nNew offers:")
            for offer in result["offers"]:
                trust = f" [Trust: {offer.get('trustScore', '?')}/100" + (f" — {', '.join(offer.get('trustFlags', []))}" if offer.get('trustFlags') else "") + "]" if offer.get('trustScore') is not None else ""
                bl = " [BLACKLISTED]" if offer.get("blacklisted") else ""
                print(f"  + {offer.get('company', '?')} | {offer.get('title', '?')} | {offer.get('location', '')}{trust}{bl}")
        if not result.get("dryRun"):
            print(f"\nResults saved to data/scan-history.tsv and data/pipeline.md")
        else:
            print(f"\n(dry run — run without --dry-run to save results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
