"""Deterministic normalization of a raw posting into JobPosting fields.

Every rule here is explainable and unit-tested. No LLM, no fabrication: when a
value can't be detected we return the neutral fallback (``unknown``/empty),
never a guess.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import urlparse, urlunparse

from django.utils.text import slugify

from ..connectors.base import RawJob

# --- Remote detection -------------------------------------------------------

_REMOTE_FULL = re.compile(
    r"\b(full[\s-]?remote|100\s*%?\s*(?:remote|t[ée]l[ée]travail)|remote[\s-]?first|"
    r"t[ée]l[ée]travail\s+total|enti[èe]rement\s+[àa]\s+distance|fully\s+remote)\b",
    re.IGNORECASE,
)
_REMOTE_HYBRID = re.compile(
    r"\b(hybrid|hybride|t[ée]l[ée]travail\s+partiel|partial\s+remote|remote\s+friendly|"
    r"[0-9]\s*(?:jours?|days?)\s*(?:de\s*)?(?:t[ée]l[ée]travail|remote|sur\s*site))\b",
    re.IGNORECASE,
)
_REMOTE_ONSITE = re.compile(
    r"\b(on[\s-]?site|sur[\s-]?site|pr[ée]sentiel|no\s+remote|pas\s+de\s+t[ée]l[ée]travail)\b",
    re.IGNORECASE,
)
_REMOTE_MENTION = re.compile(r"\b(remote|t[ée]l[ée]travail)\b", re.IGNORECASE)


def detect_remote(*texts: str) -> str:
    blob = " \n ".join(t for t in texts if t)
    if _REMOTE_FULL.search(blob):
        return "remote"
    if _REMOTE_HYBRID.search(blob):
        return "hybrid"
    if _REMOTE_ONSITE.search(blob):
        return "onsite"
    if _REMOTE_MENTION.search(blob):
        # A bare "remote" mention without a full/hybrid qualifier → treat as hybrid.
        return "hybrid"
    return "unknown"


# --- Contract detection -----------------------------------------------------

_CONTRACT_PATTERNS = [
    ("alternance", re.compile(r"\b(alternance|apprentissage|contrat\s+pro|professionnalisation)\b", re.IGNORECASE)),
    ("stage", re.compile(r"\b(stage|stagiaire|internship|intern)\b", re.IGNORECASE)),
    ("internship", re.compile(r"\binternship\b", re.IGNORECASE)),
    ("portage", re.compile(r"\bportage\s+salarial\b", re.IGNORECASE)),
    ("freelance", re.compile(r"\b(freelance|ind[ée]pendant|contractor|mission\s+freelance|consultant\s+ind)\b", re.IGNORECASE)),
    ("cdd", re.compile(r"\b(cdd|fixed[\s-]?term|contrat\s+[àa]\s+dur[ée]e\s+d[ée]termin[ée]e)\b", re.IGNORECASE)),
    ("cdi", re.compile(r"\b(cdi|permanent|full[\s-]?time\s+permanent|contrat\s+[àa]\s+dur[ée]e\s+ind[ée]termin[ée]e)\b", re.IGNORECASE)),
]

# Map connector-supplied contract labels onto our ids.
_CONTRACT_HINTS = {
    "full-time": "cdi",
    "fulltime": "cdi",
    "permanent": "cdi",
    "contract": "freelance",
    "temporary": "cdd",
    "internship": "stage",
    "apprenticeship": "alternance",
}


def detect_contract(hint: str, *texts: str) -> str:
    hint_low = (hint or "").strip().lower()
    if hint_low in _CONTRACT_HINTS:
        return _CONTRACT_HINTS[hint_low]
    blob = " \n ".join([hint] + [t for t in texts if t])
    for contract_id, pattern in _CONTRACT_PATTERNS:
        if pattern.search(blob):
            return "stage" if contract_id == "internship" else contract_id
    return "unknown"


# --- Salary extraction ------------------------------------------------------

_CURRENCY = {"€": "EUR", "eur": "EUR", "euros": "EUR", "$": "USD", "usd": "USD", "£": "GBP", "gbp": "GBP"}
_NUM = r"(\d{1,3}(?:[ .,]\d{3})*(?:[.,]\d+)?|\d+)"
_K_RANGE = re.compile(rf"{_NUM}\s*[kK]?\s*[-–—à]\s*{_NUM}\s*([kK€$£]|eur|euros|usd|gbp)?", re.IGNORECASE)
_K_SINGLE = re.compile(rf"{_NUM}\s*([kK])\s*(€|\$|£|eur|euros|usd|gbp)?", re.IGNORECASE)
_PLAIN = re.compile(rf"{_NUM}\s*(€|\$|£|eur|euros|usd|gbp)", re.IGNORECASE)


def _to_int(token: str, is_k: bool) -> int | None:
    cleaned = token.replace(" ", "").replace(".", "").replace(",", "")
    if not cleaned.isdigit():
        # handle decimal like 45,5 → treat as k thousands
        cleaned = re.sub(r"\D", "", token)
        if not cleaned.isdigit():
            return None
    value = int(cleaned)
    if is_k:
        value *= 1000
    # Reject implausible values (avoid picking up e.g. "2024")
    return value if 8000 <= value <= 1_000_000 else None


def extract_salary(*texts: str) -> tuple[int | None, int | None, str]:
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None, None, ""

    def currency_of(marker: str | None) -> str:
        if not marker:
            return "EUR"
        return _CURRENCY.get(marker.strip().lower(), "EUR")

    m = _K_RANGE.search(blob)
    if m:
        marker = (m.group(3) or "").lower()
        is_k = "k" in marker or bool(re.search(r"\d\s*[kK]", m.group(0)))
        low = _to_int(m.group(1), is_k)
        high = _to_int(m.group(2), is_k)
        if low or high:
            cur = "EUR" if marker in ("k", "") else currency_of(marker)
            return low, high, cur

    m = _K_SINGLE.search(blob)
    if m:
        value = _to_int(m.group(1), True)
        if value:
            return value, None, currency_of(m.group(3))

    m = _PLAIN.search(blob)
    if m:
        value = _to_int(m.group(1), False)
        if value:
            return value, None, currency_of(m.group(2))
    return None, None, ""


# --- Seniority --------------------------------------------------------------

_SENIORITY = [
    ("lead", re.compile(r"\b(lead|principal|staff|head\s+of|director|vp|chief)\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(senior|sr\.?|confirm[ée]|exp[ée]riment[ée])\b", re.IGNORECASE)),
    ("junior", re.compile(r"\b(junior|jr\.?|d[ée]butant|entry[\s-]?level|graduate)\b", re.IGNORECASE)),
]


def detect_seniority(*texts: str) -> str:
    blob = " ".join(t for t in texts if t)
    for label, pattern in _SENIORITY:
        if pattern.search(blob):
            return label
    return ""


# --- Language ---------------------------------------------------------------

_FR_MARKERS = re.compile(r"\b(le|la|les|des|une|nous|vous|et|pour|avec|dans|entreprise|poste|missions?)\b", re.IGNORECASE)
_EN_MARKERS = re.compile(r"\b(the|and|for|with|you|we|our|team|role|about|responsibilities)\b", re.IGNORECASE)


def detect_language(*texts: str) -> str:
    blob = " ".join(t for t in texts if t)
    if not blob.strip():
        return ""
    fr = len(_FR_MARKERS.findall(blob))
    en = len(_EN_MARKERS.findall(blob))
    if fr == en == 0:
        return ""
    return "fr" if fr >= en else "en"


# --- URL / hashing ----------------------------------------------------------

_TRACKING_PARAMS = re.compile(r"^(utm_|gh_|lever-|ref$|source$|src$)", re.IGNORECASE)


def canonical_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def content_hash(*parts: str) -> str:
    blob = "".join((p or "").strip().lower() for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    # Drop trailing " - Company" / " | Location" style suffixes that ATS append.
    title = re.sub(r"\s*[|·–—]\s*(remote|full[\s-]?remote|cdi|paris|france|h/f|m/f|w/m/d)\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def clean_company(company: str) -> str:
    company = re.sub(r"\s+", " ", (company or "").strip())
    company = re.sub(r"\s*[,·|-]?\s*\b(sas|sarl|inc\.?|ltd\.?|gmbh|llc)\b\.?\s*$", "", company, flags=re.IGNORECASE)
    return company.strip()


# --- Public entry point -----------------------------------------------------

def normalize_job(raw: RawJob, market: str = "france") -> dict:
    """Return a dict of normalized JobPosting fields for a raw posting."""
    title = clean_title(raw.title)
    company = clean_company(raw.company)
    description = raw.description or ""
    requirements = raw.requirements or ""
    location = re.sub(r"\s+", " ", (raw.location or "").strip())

    remote_type = detect_remote(title, location, description, requirements)
    contract_type = detect_contract(raw.contract_type, title, description, requirements)
    salary_min, salary_max, currency = extract_salary(raw.salary_text, description)
    seniority = detect_seniority(title, description)
    language = detect_language(title, description) or ""

    source_url = canonical_url(raw.url)
    company_slug = slugify(company)[:150]

    return {
        "title": title,
        "company": company,
        "company_slug": company_slug,
        "location": location,
        "remote_type": remote_type,
        "contract_type": contract_type,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "seniority": seniority,
        "description_text": description,
        "requirements_text": requirements,
        "apply_url": raw.apply_url or raw.url,
        "source_url": raw.url,
        "posted_at": raw.posted_at if isinstance(raw.posted_at, date) else None,
        "content_hash": content_hash(company_slug, title, location),
        "language": language,
        "market": market,
        "canonical_url": source_url,
    }


def canonical_key(normalized: dict) -> str:
    """Stable dedup key: company slug + normalized title + coarse location."""
    company = normalized.get("company_slug") or slugify(normalized.get("company", ""))
    title = slugify(normalized.get("title", ""))[:120]
    loc = slugify((normalized.get("location") or "").split(",")[0])[:40]
    return f"{company}|{title}|{loc}".strip("|")
