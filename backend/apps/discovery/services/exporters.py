"""Bridge a reviewed digest item into the career-ops pipeline.

Export ONLY adds a line to ``data/pipeline.md`` (the career-ops inbox). It never
evaluates and never applies — the user later runs modes/fr/offre.md on it.
"""

from __future__ import annotations

from django.utils import timezone

from apps.core.paths import root_path
from apps.core.safe_write import atomic_write

from ..models import DailyJobDigestItem


def _pipeline_line(job) -> str:
    comp = ""
    if job.salary_min:
        cur = job.salary_currency or "EUR"
        comp = f"{cur} {job.salary_min}" + (f"-{job.salary_max}" if job.salary_max else "")
    parts = [job.apply_url or job.source_url, job.company or "?", job.title or "?", job.location or "", comp]
    # Trim trailing empties for a clean "url | company | role" minimum.
    while len(parts) > 3 and not parts[-1]:
        parts.pop()
    return "- [ ] " + " | ".join(parts)


def export_item_to_pipeline(item: DailyJobDigestItem) -> dict:
    """Append the item's offer to data/pipeline.md unless already present."""
    job = item.job
    url = job.apply_url or job.source_url
    if not url:
        return {"added": False, "reason": "offer has no URL"}

    path = root_path("data", "pipeline.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = "# Pipeline — pending offers\n\n"

    if url in existing:
        item.exported_to_pipeline_at = timezone.now()
        item.save(update_fields=["exported_to_pipeline_at"])
        return {"added": False, "reason": "already in pipeline", "url": url}

    body = existing.rstrip("\n") + "\n" + _pipeline_line(job) + "\n"
    atomic_write(path, body)

    item.exported_to_pipeline_at = timezone.now()
    if item.decision == "pending":
        item.decision = "evaluate"
    item.decided_at = timezone.now()
    item.save(update_fields=["exported_to_pipeline_at", "decision", "decided_at"])
    return {"added": True, "url": url}


def apply_decision(item: DailyJobDigestItem, decision: str, note: str = "") -> DailyJobDigestItem:
    """Record a user decision on a digest item (no side effects beyond the row)."""
    item.decision = decision
    item.decision_note = (note or "")[:500]
    item.decided_at = timezone.now()
    item.save(update_fields=["decision", "decision_note", "decided_at"])
    return item
