#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse


DEFAULT_SUSPICIOUS_DOMAINS = [
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "forms.gle",
    "goo.gl",
    "shorturl.at",
    "rebrand.ly",
    "cutt.ly",
]
DEFAULT_ATS_ALLOWLIST = [
    "greenhouse.io",
    "ashbyhq.com",
    "lever.co",
    "workday.com",
    "smartrecruiters.com",
    "jobvite.com",
    "myworkdayjobs.com",
    "recruitee.com",
    "workable.com",
    "icims.com",
    "taleo.net",
    "applytojob.com",
    "breezy.hr",
    "jazz.co",
    "bamboohr.com",
    "teamtailor.com",
]
PENALTIES = {
    "invalid_url": 50,
    "missing_apply_url": 40,
    "suspicious_domain": 25,
    "company_domain_mismatch": 15,
}


def classify_trust_level(score: int | float) -> str:
    if score >= 90:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def validate_url(url: Any) -> dict[str, Any]:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"valid": False, "flag": "invalid_url"}
    return {"valid": True}


def matches_domain_list(hostname: str, domain_list: list[str]) -> bool:
    host = str(hostname or "").lower()
    for domain in domain_list:
        normalized = str(domain or "").lower().strip()
        if normalized and (host == normalized or host.endswith("." + normalized)):
            return True
    return False


def company_matches_hostname(company: Any, hostname: Any) -> bool:
    if not company or not hostname:
        return True
    normalized = re.sub(r"[^a-z0-9 ]", "", str(company).lower()).strip()
    if not normalized:
        return True
    host = str(hostname).lower()
    slug = re.sub(r"\s+", "", normalized)
    if slug and slug in host:
        return True
    return any(word in host for word in normalized.split() if len(word) >= 3)


def _domain_list(value: Any, fallback: list[str]) -> list[str]:
    source = value if isinstance(value, list) else fallback
    return [str(item).lower().strip() for item in source if str(item or "").strip()]


def build_trust_validator(config: dict[str, Any] | None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    if not config or config.get("enabled") is False:
        return lambda _job: {"score": 100, "flags": [], "level": "high"}
    suspicious_domains = _domain_list(config.get("suspicious_domains"), DEFAULT_SUSPICIOUS_DOMAINS)
    ats_allowlist = _domain_list(config.get("ats_allowlist"), DEFAULT_ATS_ALLOWLIST)

    def validate(job: dict[str, Any]) -> dict[str, Any]:
        flags: list[str] = []
        score = 100
        url = str(job.get("url") or "").strip() if isinstance(job, dict) else ""
        if not url:
            flags.append("missing_apply_url")
            score -= PENALTIES["missing_apply_url"]
            clamped = max(0, score)
            return {"score": clamped, "flags": flags, "level": classify_trust_level(clamped)}
        url_check = validate_url(url)
        if not url_check["valid"]:
            flags.append("invalid_url")
            score -= PENALTIES["invalid_url"]
            clamped = max(0, score)
            return {"score": clamped, "flags": flags, "level": classify_trust_level(clamped)}
        hostname = (urlparse(url).hostname or "").lower()
        if matches_domain_list(hostname, suspicious_domains):
            flags.append("suspicious_domain")
            score -= PENALTIES["suspicious_domain"]
        company = str(job.get("company") or "").strip()
        if company and not matches_domain_list(hostname, ats_allowlist) and not company_matches_hostname(company, hostname):
            flags.append("company_domain_mismatch")
            score -= PENALTIES["company_domain_mismatch"]
        score = max(0, min(100, score))
        return {"score": score, "flags": flags, "level": classify_trust_level(score)}

    return validate
