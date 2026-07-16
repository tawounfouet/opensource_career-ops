from rest_framework import serializers

from .models import (
    Education,
    EducationCompetency,
    SkillCompetency,
    SkillDevelopmentAction,
    SkillEvidence,
    SkillExperience,
    SkillExtractionRun,
)


class SkillExperienceSerializer(serializers.ModelSerializer):
    competencies_count = serializers.IntegerField(source="competencies.count", read_only=True)
    evidence_count = serializers.IntegerField(source="evidence.count", read_only=True)

    class Meta:
        model = SkillExperience
        fields = "__all__"


class SkillEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillEvidence
        fields = "__all__"


class SkillCompetencySerializer(serializers.ModelSerializer):
    experience_ids = serializers.PrimaryKeyRelatedField(
        source="experiences", queryset=SkillExperience.objects.all(), many=True, required=False
    )
    evidence_ids = serializers.PrimaryKeyRelatedField(
        source="evidence", queryset=SkillEvidence.objects.all(), many=True, required=False
    )
    experiences_detail = SkillExperienceSerializer(source="experiences", many=True, read_only=True)
    evidence_detail = SkillEvidenceSerializer(source="evidence", many=True, read_only=True)

    class Meta:
        model = SkillCompetency
        fields = [
            "id", "label", "formulation", "category", "action_verb", "object", "context",
            "experience_ids", "evidence_ids", "experiences_detail", "evidence_detail",
            "mastery_level", "mastery_rationale", "confidence", "status", "tags",
            "market_keywords", "created_by", "validated_at", "created_at", "updated_at",
        ]
        read_only_fields = ["validated_at", "created_at", "updated_at"]


class SkillDevelopmentActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillDevelopmentAction
        fields = "__all__"


class SkillExtractionRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillExtractionRun
        fields = "__all__"


class EducationCompetencySerializer(serializers.ModelSerializer):
    competency_label = serializers.CharField(source="competency.label", read_only=True)

    class Meta:
        model = EducationCompetency
        fields = ["id", "education", "competency", "competency_label", "relevance", "created_at"]
        read_only_fields = ["created_at"]


class EducationSerializer(serializers.ModelSerializer):
    competencies_count = serializers.IntegerField(source="competencies.count", read_only=True)
    education_links = EducationCompetencySerializer(many=True, read_only=True)

    class Meta:
        model = Education
        fields = [
            "id", "title", "institution", "education_type", "status",
            "start_date", "end_date", "credential_url", "credential_id",
            "hours", "description", "experience", "competencies_count",
            "education_links", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    @staticmethod
    def _pad_date(value):
        if not value or isinstance(value, str) is False:
            return value
        parts = value.strip().split("-")
        if len(parts) == 1:
            return f"{parts[0]}-01-01"
        if len(parts) == 2:
            return f"{parts[0]}-{parts[1]}-01"
        return value

    def to_internal_value(self, data):
        for field in ("start_date", "end_date"):
            if field in data and isinstance(data[field], str):
                data[field] = self._pad_date(data[field])
        return super().to_internal_value(data)

