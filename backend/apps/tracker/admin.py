from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Application, PipelineJob, ScanHistory


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["number", "company", "role", "status_badge", "score", "has_pdf", "date"]
    list_filter = ["status", "has_pdf", "date"]
    search_fields = ["company", "role", "notes"]
    list_editable = ["score", "has_pdf"]
    actions = ["mark_applied", "mark_rejected", "export_tsv"]

    def status_badge(self, obj):
        colors = {"Evaluated": "#2563eb", "Applied": "#d97706", "Interview": "#7c3aed", "Offer": "#059669", "Rejected": "#dc2626", "Discarded": "#4b5563", "SKIP": "#111827"}
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:4px">{}</span>', colors.get(obj.status, "#6b7280"), obj.status)

    @admin.action(description="Mark as Applied")
    def mark_applied(self, request, queryset):
        queryset.update(status="Applied")

    @admin.action(description="Mark as Rejected")
    def mark_rejected(self, request, queryset):
        queryset.update(status="Rejected")

    @admin.action(description="Export as TSV")
    def export_tsv(self, request, queryset):
        response = HttpResponse("\n".join(app.to_tsv_row() for app in queryset), content_type="text/tab-separated-values")
        response["Content-Disposition"] = 'attachment; filename="tracker-export.tsv"'
        return response


@admin.register(PipelineJob)
class PipelineJobAdmin(admin.ModelAdmin):
    list_display = ["company", "role", "location", "done", "posted_at"]
    list_filter = ["done", "posted_at"]
    search_fields = ["company", "role", "url"]
    list_editable = ["done"]


@admin.register(ScanHistory)
class ScanHistoryAdmin(admin.ModelAdmin):
    list_display = ["url", "source", "first_seen", "last_seen"]
    search_fields = ["url", "source"]
