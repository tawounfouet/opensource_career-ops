from django.contrib import admin

from .models import (
    DailyJobDigest,
    DailyJobDigestItem,
    DiscoveryRun,
    JobPosting,
    JobRanking,
    JobSource,
    RawJobPosting,
    SearchProfile,
)


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "strategy", "connector", "enabled", "market", "last_success_at"]
    list_filter = ["strategy", "kind", "enabled", "market"]
    list_editable = ["enabled"]
    search_fields = ["name", "slug", "connector"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SearchProfile)
class SearchProfileAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "remote_policy", "freshness_days", "daily_digest_size", "updated_at"]
    list_filter = ["enabled", "remote_policy"]
    search_fields = ["name"]


@admin.register(DiscoveryRun)
class DiscoveryRunAdmin(admin.ModelAdmin):
    list_display = ["id", "profile", "status", "trigger", "offers_seen", "offers_new", "offers_deduped", "started_at"]
    list_filter = ["status", "trigger"]
    date_hierarchy = "started_at"


@admin.register(RawJobPosting)
class RawJobPostingAdmin(admin.ModelAdmin):
    list_display = ["id", "source", "raw_title", "raw_company", "status", "posted_at", "first_seen_at"]
    list_filter = ["source", "status"]
    search_fields = ["raw_title", "raw_company", "url"]


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "remote_type", "contract_type", "posted_at", "is_active", "dedup_confidence"]
    list_filter = ["remote_type", "contract_type", "is_active", "market"]
    search_fields = ["title", "company", "canonical_key"]


@admin.register(JobRanking)
class JobRankingAdmin(admin.ModelAdmin):
    list_display = ["job", "profile", "score", "rank", "rejected", "created_at"]
    list_filter = ["profile", "rejected"]
    search_fields = ["job__title", "job__company"]


class DailyJobDigestItemInline(admin.TabularInline):
    model = DailyJobDigestItem
    extra = 0
    fields = ["rank", "job", "decision", "decision_note", "exported_to_pipeline_at"]
    readonly_fields = ["job"]


@admin.register(DailyJobDigest)
class DailyJobDigestAdmin(admin.ModelAdmin):
    list_display = ["date", "profile", "status", "items_count", "total_candidates", "created_at"]
    list_filter = ["status", "profile"]
    date_hierarchy = "date"
    inlines = [DailyJobDigestItemInline]


@admin.register(DailyJobDigestItem)
class DailyJobDigestItemAdmin(admin.ModelAdmin):
    list_display = ["digest", "rank", "job", "decision", "exported_to_pipeline_at"]
    list_filter = ["decision"]
    search_fields = ["job__title", "job__company"]
