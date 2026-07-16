from rest_framework import serializers

from .models import (
    DailyJobDigest,
    DailyJobDigestItem,
    DiscoveryRun,
    JobPosting,
    JobRanking,
    JobSource,
    SearchProfile,
)


class JobSourceSerializer(serializers.ModelSerializer):
    is_automatable = serializers.BooleanField(read_only=True)

    class Meta:
        model = JobSource
        fields = [
            "id", "name", "slug", "kind", "strategy", "connector", "base_url",
            "enabled", "country", "market", "rate_limit_per_hour", "requires_login",
            "config", "tos_notes", "robots_policy", "disabled_reason",
            "last_checked_at", "last_success_at", "last_error", "is_automatable",
        ]


class SearchProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchProfile
        exclude = ["created_at", "updated_at"]
        read_only_fields = ["id"]


class DiscoveryRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscoveryRun
        fields = "__all__"


class JobPostingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosting
        fields = [
            "id", "title", "company", "location", "remote_type", "contract_type",
            "salary_min", "salary_max", "salary_currency", "seniority",
            "apply_url", "source_url", "all_sources", "posted_at", "language",
            "market", "dedup_confidence",
        ]


class JobRankingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRanking
        fields = [
            "score", "freshness_score", "title_score", "keyword_score",
            "location_score", "remote_score", "contract_score", "salary_score",
            "company_score", "negative_penalty", "rejected", "reject_reason",
            "explanations", "rank",
        ]


class DailyJobDigestItemSerializer(serializers.ModelSerializer):
    job = JobPostingSerializer(read_only=True)
    ranking = JobRankingSerializer(read_only=True)

    class Meta:
        model = DailyJobDigestItem
        fields = [
            "id", "rank", "decision", "decision_note", "decided_at",
            "exported_to_pipeline_at", "job", "ranking",
        ]


class DailyJobDigestSerializer(serializers.ModelSerializer):
    items = DailyJobDigestItemSerializer(many=True, read_only=True)

    class Meta:
        model = DailyJobDigest
        fields = ["id", "date", "status", "total_candidates", "items_count", "created_at", "items"]
