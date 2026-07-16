from django.contrib import admin

from .models import (
    SkillCompetency,
    SkillDevelopmentAction,
    SkillEvidence,
    SkillExperience,
    SkillExtractionRun,
)


@admin.register(SkillExperience)
class SkillExperienceAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "organization", "start_date", "end_date", "updated_at"]
    search_fields = ["title", "organization", "description"]
    list_filter = ["type"]


@admin.register(SkillEvidence)
class SkillEvidenceAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "trust_level", "source_experience", "created_at"]
    search_fields = ["title", "description", "metric"]
    list_filter = ["type", "trust_level"]


@admin.register(SkillCompetency)
class SkillCompetencyAdmin(admin.ModelAdmin):
    list_display = ["label", "category", "mastery_level", "confidence", "status", "updated_at"]
    search_fields = ["label", "formulation", "action_verb", "object"]
    list_filter = ["category", "mastery_level", "confidence", "status"]
    filter_horizontal = ["experiences", "evidence"]


@admin.register(SkillDevelopmentAction)
class SkillDevelopmentActionAdmin(admin.ModelAdmin):
    list_display = ["competency", "target_level", "status", "deadline", "updated_at"]
    list_filter = ["target_level", "status"]


@admin.register(SkillExtractionRun)
class SkillExtractionRunAdmin(admin.ModelAdmin):
    list_display = ["prompt_template", "provider", "model", "status", "created_at"]
    list_filter = ["status", "provider", "model"]
