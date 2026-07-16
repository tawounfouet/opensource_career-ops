"""Deterministic V1 scoring — every point is justifiable by a rule.

Total budget = 100:
  freshness 20 + title 20 + keywords 30 (15 positive + 15 required)
  + remote 5 + location 5 + contract 10 + salary 5 + company 5.
Penalties (negative keywords) subtract up to 50. Hard rejects (blocked title,
onsite-vs-remote-only, unwanted stage/alternance, missing required keyword,
blocked company) flag the ranking so the digest skips it.
"""

from __future__ import annotations

import re
from datetime import date

from django.utils.text import slugify

_WORD = re.compile(r"[a-z0-9àâäéèêëïîôöùûüç]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "") if len(w) >= 2}


def _contains(blob: str, term: str) -> bool:
    term = (term or "").strip().lower()
    if not term:
        return False
    return re.search(r"\b" + re.escape(term) + r"\b", blob) is not None


def _blob(job: dict) -> str:
    return " ".join(
        [job.get("title", ""), job.get("description_text", ""), job.get("requirements_text", "")]
    ).lower()


# --- Sub-scorers ------------------------------------------------------------

def score_freshness(posted_at: date | None, today: date) -> tuple[int, str]:
    if not posted_at:
        return 5, "freshness: unknown date (+5)"
    days = (today - posted_at).days
    if days <= 0:
        return 20, "freshness: posted today (+20)"
    if days == 1:
        return 16, "freshness: posted yesterday (+16)"
    if days <= 3:
        return 12, f"freshness: {days}d old (+12)"
    if days <= 7:
        return 8, f"freshness: {days}d old (+8)"
    return 2, f"freshness: {days}d old (+2)"


def score_title(job: dict, target_titles: list[str], blocked_titles: list[str]) -> tuple[int, str, bool]:
    title = job.get("title", "")
    title_tokens = _tokens(title)
    title_slug = slugify(title)

    for blocked in blocked_titles or []:
        if _tokens(blocked) & title_tokens:
            return 0, f"title: blocked term '{blocked}' → reject", True

    if not target_titles:
        return 5, "title: no target titles set (+5 vague)", False

    for target in target_titles:
        if slugify(target) == title_slug:
            return 20, f"title: exact match '{target}' (+20)", False

    for target in target_titles:
        t_tokens = _tokens(target)
        if t_tokens and t_tokens <= title_tokens:
            return 15, f"title: all terms of '{target}' present (+15)", False

    blob = _blob(job)
    for target in target_titles:
        strong = {w for w in _tokens(target) if len(w) >= 4}
        if strong & title_tokens:
            return 10, f"title: partial title match '{target}' (+10)", False
        if strong & _tokens(blob):
            return 5, f"title: '{target}' terms appear in body (+5)", False
    return 0, "title: no target match (0)", False


def score_keywords(job: dict, positive: list[str], required: list[str], negative: list[str]):
    blob = _blob(job)
    explanations: list[str] = []

    # Required — a single miss rejects.
    required_score = 0
    if required:
        missing = [k for k in required if not _contains(blob, k)]
        if missing:
            return 0, 0, f"required keyword missing: {missing[0]}", explanations + [
                f"keywords: missing required '{missing[0]}' → reject"
            ]
        required_score = 15
        explanations.append(f"keywords: all {len(required)} required present (+15)")

    # Positive — proportional up to 15.
    positive_score = 0
    if positive:
        hits = [k for k in positive if _contains(blob, k)]
        positive_score = round(15 * len(hits) / len(positive))
        explanations.append(f"keywords: {len(hits)}/{len(positive)} positive (+{positive_score})")

    # Negative — up to -50.
    penalty = 0
    if negative:
        neg_hits = [k for k in negative if _contains(blob, k)]
        penalty = -min(50, 10 * len(neg_hits))
        if neg_hits:
            explanations.append(f"keywords: negative {neg_hits} ({penalty})")

    return positive_score + required_score, penalty, "", explanations


def score_remote(remote_type: str, policy: str) -> tuple[int, str, bool]:
    if policy == "remote":
        if remote_type == "remote":
            return 5, "remote: full remote matches policy (+5)", False
        if remote_type == "hybrid":
            return 2, "remote: hybrid vs remote-only (+2)", False
        if remote_type == "onsite":
            return 0, "remote: on-site vs remote-only → reject", True
        return 1, "remote: unknown vs remote-only (+1)", False
    if policy == "hybrid":
        return ({"remote": 5, "hybrid": 5, "onsite": 2}.get(remote_type, 3),
                f"remote: {remote_type} under hybrid policy", False)
    if policy == "onsite":
        return (5 if remote_type in ("onsite", "hybrid") else 3, f"remote: {remote_type} under on-site policy", False)
    # any
    return ({"remote": 5, "hybrid": 5, "onsite": 3}.get(remote_type, 2),
            f"remote: {remote_type} (any policy)", False)


def score_location(location: str, wanted: list[str], remote_type: str) -> tuple[int, str]:
    if remote_type == "remote":
        return 5, "location: remote (+5)"
    if not wanted:
        return 3, "location: no constraint (+3)"
    loc_low = (location or "").lower()
    for term in wanted:
        if term and term.lower() in loc_low:
            return 5, f"location: matches '{term}' (+5)"
    if not loc_low:
        return 2, "location: unknown (+2)"
    return 1, "location: outside wanted areas (+1)"


def score_contract(contract_type: str, wanted: list[str]) -> tuple[int, str, bool]:
    wanted = [w.lower() for w in (wanted or [])]
    if contract_type in ("stage", "alternance", "internship") and wanted and contract_type not in wanted:
        return 0, f"contract: {contract_type} not wanted → reject", True
    if not wanted:
        return 5, "contract: no constraint (+5)", False
    if contract_type in wanted:
        return 10, f"contract: {contract_type} matches (+10)", False
    if contract_type == "unknown":
        return 4, "contract: unknown (+4)", False
    return 2, f"contract: {contract_type} not preferred (+2)", False


def score_salary(job: dict, salary_min: int | None) -> tuple[int, int, str]:
    advertised = job.get("salary_max") or job.get("salary_min")
    if not salary_min:
        return 2, 0, "salary: no target set (+2)"
    if not advertised:
        return 2, 0, "salary: not advertised (+2)"
    if advertised >= salary_min:
        return 5, 0, f"salary: {advertised} ≥ target {salary_min} (+5)"
    return 0, -10, f"salary: {advertised} < target {salary_min} (-10)"


def score_company(company: str, allow: list[str], block: list[str]) -> tuple[int, str, bool]:
    low = (company or "").strip().lower()
    if any(low == b.strip().lower() for b in (block or [])):
        return 0, f"company: '{company}' blocked → reject", True
    if any(low == a.strip().lower() for a in (allow or [])):
        return 5, f"company: '{company}' on allow-list (+5)", False
    return 2, "company: neutral (+2)", False


# --- Aggregate --------------------------------------------------------------

def score_job(job: dict, profile, today: date) -> dict:
    """Return all sub-scores, total, explanations, and reject state."""
    explanations: list[str] = []

    freshness, exp = score_freshness(job.get("posted_at"), today)
    explanations.append(exp)

    title, exp, title_reject = score_title(
        job, list(profile.target_titles or []), list(profile.blocked_titles or [])
    )
    explanations.append(exp)

    keyword, penalty, kw_reject_reason, kw_exps = score_keywords(
        job,
        [k.lower() for k in (profile.positive_keywords or [])],
        [k.lower() for k in (profile.required_keywords or [])],
        [k.lower() for k in (profile.negative_keywords or [])],
    )
    explanations.extend(kw_exps)

    remote, exp, remote_reject = score_remote(job.get("remote_type", "unknown"), profile.remote_policy or "any")
    explanations.append(exp)

    location, exp = score_location(job.get("location", ""), list(profile.locations or []), job.get("remote_type", "unknown"))
    explanations.append(exp)

    contract, exp, contract_reject = score_contract(job.get("contract_type", "unknown"), list(profile.contract_types or []))
    explanations.append(exp)

    salary, salary_penalty, exp = score_salary(job, profile.salary_min)
    explanations.append(exp)

    company, exp, company_reject = score_company(
        job.get("company", ""), list(profile.companies_allow or []), list(profile.companies_block or [])
    )
    explanations.append(exp)

    total_penalty = penalty + salary_penalty
    total = freshness + title + keyword + remote + location + contract + salary + company + total_penalty
    total = max(0, min(100, total))

    reject_reason = ""
    if title_reject:
        reject_reason = "blocked title"
    elif kw_reject_reason:
        reject_reason = kw_reject_reason
    elif remote_reject:
        reject_reason = "on-site vs remote-only policy"
    elif contract_reject:
        reject_reason = "unwanted contract type"
    elif company_reject:
        reject_reason = "blocked company"
    rejected = bool(reject_reason)

    return {
        "score": total,
        "freshness_score": freshness,
        "title_score": title,
        "keyword_score": keyword,
        "location_score": location,
        "remote_score": remote,
        "contract_score": contract,
        "salary_score": salary,
        "company_score": company,
        "negative_penalty": total_penalty,
        "rejected": rejected,
        "reject_reason": reject_reason,
        "explanations": explanations,
    }
