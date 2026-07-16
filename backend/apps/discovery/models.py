"""Data model for the deterministic France job-discovery module.

V1 is intentionally LLM-free: every field here is populated by explainable,
testable rules. See PLAN-ACTION-FRANCE-JOBOARDS-DJANGO.md.
"""

from __future__ import annotations

from django.db import models


# --- Enumerations -----------------------------------------------------------

SOURCE_KIND = [
    ("jobboard", "Job board"),
    ("ats", "ATS"),
    ("company_site", "Company career site"),
    ("manual", "Manual import"),
]

# How a source is collected. Anything other than an automated network fetch
# (manual_import / disabled) is respected as a hard "do not scrape" signal.
SOURCE_STRATEGY = [
    ("api", "Public/partner API"),
    ("rss", "RSS/Atom feed"),
    ("ats_api", "ATS public JSON API"),
    ("html_public", "Light HTML parsing (if allowed)"),
    ("browser_public", "Rate-limited Playwright"),
    ("manual_import", "User pastes/exports offers"),
    ("disabled", "Listed but not automated"),
]

MARKET = [
    ("france", "France"),
    ("francophone", "Francophone"),
    ("remote_eu", "Remote EU"),
]

REMOTE_TYPE = [
    ("remote", "Full remote"),
    ("hybrid", "Hybrid"),
    ("onsite", "On-site"),
    ("unknown", "Unknown"),
]

CONTRACT_TYPE = [
    ("cdi", "CDI"),
    ("cdd", "CDD"),
    ("freelance", "Freelance"),
    ("portage", "Portage salarial"),
    ("alternance", "Alternance"),
    ("stage", "Stage"),
    ("internship", "Internship"),
    ("unknown", "Unknown"),
]

REMOTE_POLICY = [
    ("remote", "Remote only"),
    ("hybrid", "Hybrid ok"),
    ("onsite", "On-site ok"),
    ("any", "Any"),
]

RUN_STATUS = [
    ("running", "Running"),
    ("success", "Success"),
    ("partial", "Partial"),
    ("failed", "Failed"),
]

RUN_TRIGGER = [
    ("scheduled", "Scheduled"),
    ("manual", "Manual"),
    ("cli", "CLI"),
]

RAW_STATUS = [
    ("new", "New"),
    ("seen", "Seen"),
    ("expired", "Expired"),
    ("error", "Error"),
]

DIGEST_STATUS = [
    ("prepared", "Prepared"),
    ("reviewed", "Reviewed"),
    ("archived", "Archived"),
]

DECISION = [
    ("pending", "Pending"),
    ("evaluate", "Send to evaluation"),
    ("skip", "Skip"),
    ("blacklist_company", "Blacklist company"),
    ("save_for_later", "Save for later"),
    ("already_applied", "Already applied"),
]


# --- Sources ----------------------------------------------------------------

class JobSource(models.Model):
    """A platform or source the discovery module can collect from."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=SOURCE_KIND, default="jobboard")
    strategy = models.CharField(max_length=20, choices=SOURCE_STRATEGY, default="disabled")
    # Which connector class drives this source (registry key in connectors/base.py).
    connector = models.CharField(max_length=50, blank=True, default="")
    base_url = models.URLField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    country = models.CharField(max_length=40, blank=True, default="France")
    market = models.CharField(max_length=20, choices=MARKET, default="france")
    rate_limit_per_hour = models.PositiveIntegerField(default=60)
    requires_login = models.BooleanField(default=False)
    # Connector-specific config, e.g. {"boards": ["stripe", "figma"]} for an ATS.
    config = models.JSONField(default=dict, blank=True)
    tos_notes = models.TextField(blank=True, default="")
    robots_policy = models.CharField(max_length=200, blank=True, default="")
    disabled_reason = models.CharField(max_length=300, blank=True, default="")
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.strategy})"

    @property
    def is_automatable(self) -> bool:
        return self.enabled and self.strategy not in ("manual_import", "disabled")


# --- User search criteria ---------------------------------------------------

class SearchProfile(models.Model):
    """User-configurable search criteria.

    Source-of-truth note: user facts live here or in config/profile.yml, never
    in system-layer mode files. This mirrors the career-ops data contract.
    """

    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)

    target_titles = models.JSONField(default=list, blank=True)
    positive_keywords = models.JSONField(default=list, blank=True)
    negative_keywords = models.JSONField(default=list, blank=True)
    required_keywords = models.JSONField(default=list, blank=True)
    blocked_titles = models.JSONField(default=list, blank=True)

    locations = models.JSONField(default=list, blank=True)
    remote_policy = models.CharField(max_length=20, choices=REMOTE_POLICY, default="any")
    contract_types = models.JSONField(default=list, blank=True)  # subset of CONTRACT_TYPE ids

    seniority_min = models.PositiveIntegerField(null=True, blank=True)
    seniority_max = models.PositiveIntegerField(null=True, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_target = models.PositiveIntegerField(null=True, blank=True)

    industries_allow = models.JSONField(default=list, blank=True)
    industries_block = models.JSONField(default=list, blank=True)
    companies_allow = models.JSONField(default=list, blank=True)
    companies_block = models.JSONField(default=list, blank=True)
    ats_allow = models.JSONField(default=list, blank=True)
    sources_enabled = models.JSONField(default=list, blank=True)  # slugs; empty = all enabled

    freshness_days = models.PositiveIntegerField(default=7)
    max_results_per_run = models.PositiveIntegerField(default=100)
    daily_digest_size = models.PositiveIntegerField(default=20)

    language = models.CharField(max_length=10, default="fr")
    market_mode = models.CharField(max_length=40, default="modes/fr")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# --- Runs -------------------------------------------------------------------

class DiscoveryRun(models.Model):
    profile = models.ForeignKey(SearchProfile, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=RUN_STATUS, default="running")
    trigger = models.CharField(max_length=20, choices=RUN_TRIGGER, default="manual")

    sources_requested = models.JSONField(default=list, blank=True)
    sources_success = models.JSONField(default=list, blank=True)
    sources_failed = models.JSONField(default=list, blank=True)

    offers_seen = models.PositiveIntegerField(default=0)
    offers_new = models.PositiveIntegerField(default=0)
    offers_updated = models.PositiveIntegerField(default=0)
    offers_deduped = models.PositiveIntegerField(default=0)

    errors = models.JSONField(default=list, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Run #{self.pk} [{self.status}] {self.profile_id}"


# --- Raw + normalized postings ----------------------------------------------

class RawJobPosting(models.Model):
    """Raw capture, one row per (source, run) sighting."""

    run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, related_name="raw_postings")
    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name="raw_postings")
    source_job_id = models.CharField(max_length=300, blank=True, default="")
    url = models.URLField(max_length=1000)
    canonical_url = models.URLField(max_length=1000, blank=True, default="")
    raw_title = models.CharField(max_length=500, blank=True, default="")
    raw_company = models.CharField(max_length=300, blank=True, default="")
    raw_location = models.CharField(max_length=300, blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    raw_html_hash = models.CharField(max_length=64, blank=True, default="")
    first_seen_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(auto_now=True)
    posted_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=RAW_STATUS, default="new")

    class Meta:
        ordering = ["-first_seen_at"]
        indexes = [models.Index(fields=["source", "source_job_id"])]

    def __str__(self) -> str:
        return f"{self.source_id}:{self.source_job_id or self.url}"


class JobPosting(models.Model):
    """Normalized, deduplicated offer."""

    canonical_key = models.CharField(max_length=300, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    company = models.CharField(max_length=300)
    company_slug = models.SlugField(max_length=150, blank=True, default="")
    location = models.CharField(max_length=300, blank=True, default="")
    remote_type = models.CharField(max_length=20, choices=REMOTE_TYPE, default="unknown")
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE, default="unknown")
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=8, blank=True, default="")
    seniority = models.CharField(max_length=40, blank=True, default="")

    description_text = models.TextField(blank=True, default="")
    requirements_text = models.TextField(blank=True, default="")
    benefits_text = models.TextField(blank=True, default="")

    apply_url = models.URLField(max_length=1000, blank=True, default="")
    source_url = models.URLField(max_length=1000, blank=True, default="")
    primary_source = models.ForeignKey(
        JobSource, on_delete=models.SET_NULL, null=True, blank=True, related_name="primary_postings"
    )
    all_sources = models.JSONField(default=list, blank=True)  # list of source slugs

    posted_at = models.DateField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    dedup_confidence = models.FloatField(default=1.0)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    language = models.CharField(max_length=10, blank=True, default="")
    market = models.CharField(max_length=20, choices=MARKET, default="france")

    # Link back to a generated career-ops evaluation report, if any.
    report_file = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-posted_at", "-last_seen_at"]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company}"


class JobRanking(models.Model):
    """Deterministic score of a posting for a given profile/run."""

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="rankings")
    profile = models.ForeignKey(SearchProfile, on_delete=models.CASCADE, related_name="rankings")
    run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, related_name="rankings")

    score = models.IntegerField(default=0)
    freshness_score = models.IntegerField(default=0)
    title_score = models.IntegerField(default=0)
    keyword_score = models.IntegerField(default=0)
    location_score = models.IntegerField(default=0)
    remote_score = models.IntegerField(default=0)
    contract_score = models.IntegerField(default=0)
    salary_score = models.IntegerField(default=0)
    company_score = models.IntegerField(default=0)
    negative_penalty = models.IntegerField(default=0)
    rejected = models.BooleanField(default=False)
    reject_reason = models.CharField(max_length=200, blank=True, default="")

    explanations = models.JSONField(default=list, blank=True)
    rank = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank", "-score"]
        constraints = [
            models.UniqueConstraint(fields=["job", "run"], name="uniq_ranking_job_run"),
        ]

    def __str__(self) -> str:
        return f"{self.job_id} → {self.score}"


# --- Morning digest ---------------------------------------------------------

class DailyJobDigest(models.Model):
    profile = models.ForeignKey(SearchProfile, on_delete=models.CASCADE, related_name="digests")
    date = models.DateField()
    run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, related_name="digests")
    status = models.CharField(max_length=20, choices=DIGEST_STATUS, default="prepared")
    total_candidates = models.PositiveIntegerField(default=0)
    items_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "date"], name="uniq_digest_profile_date"),
        ]

    def __str__(self) -> str:
        return f"Digest {self.date} ({self.items_count})"


class DailyJobDigestItem(models.Model):
    digest = models.ForeignKey(DailyJobDigest, on_delete=models.CASCADE, related_name="items")
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="digest_items")
    ranking = models.ForeignKey(JobRanking, on_delete=models.SET_NULL, null=True, blank=True)
    rank = models.PositiveIntegerField(default=0)
    decision = models.CharField(max_length=30, choices=DECISION, default="pending")
    decision_note = models.CharField(max_length=500, blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)
    exported_to_pipeline_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["digest", "job"], name="uniq_digest_item_job"),
        ]

    def __str__(self) -> str:
        return f"#{self.rank} {self.job.company} ({self.decision})"
