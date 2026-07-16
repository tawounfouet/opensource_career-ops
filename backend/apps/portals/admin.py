from django.contrib import admin, messages
from django.http import HttpResponse

from .models import JobBoard, Portal, SearchQuery, TitleFilter
from .services import export_db_to_yaml, import_yaml_to_db


@admin.register(Portal)
class PortalAdmin(admin.ModelAdmin):
    list_display = ["name", "ats_badge", "scan_method", "enabled", "is_live", "last_verified"]
    list_filter = ["enabled", "is_live", "ats", "scan_method"]
    list_editable = ["enabled", "is_live"]
    search_fields = ["name", "careers_url", "api_endpoint", "notes"]
    readonly_fields = ["last_verified"]
    actions = ["verify_portals", "export_yaml_action"]

    @admin.display(description="ATS")
    def ats_badge(self, obj):
        if obj.ats:
            return obj.ats
        if obj.api_endpoint:
            url = obj.api_endpoint
            if "greenhouse" in url:
                return "greenhouse"
            if "ashby" in url:
                return "ashby"
            if "lever" in url:
                return "lever"
            if "workday" in url:
                return "workday"
        return obj.scan_method or "—"

    @admin.action(description="Export selected to portals.yml")
    def export_yaml_action(self, request, queryset):
        result = export_db_to_yaml()
        self.message_user(request, f"Exported {result['exported']} records to {result['path']}")

    @admin.action(description="Verify selected portals (ATS liveness)")
    def verify_portals(self, request, queryset):
        import subprocess
        from django.conf import settings
        from pathlib import Path

        script = Path(settings.CAREER_OPS_ROOT) / "verify-portals.mjs"
        if not script.exists():
            self.message_user(request, "verify-portals.mjs not found", level=messages.ERROR)
            return

        names = list(queryset.values_list("name", flat=True))
        result = subprocess.run(
            ["node", str(script), "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(settings.CAREER_OPS_ROOT)),
        )
        self.message_user(request, f"Verification complete — {len(names)} portals checked")


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ["name", "query_short", "enabled"]
    list_filter = ["enabled"]
    list_editable = ["enabled"]
    search_fields = ["name", "query"]

    @admin.display(description="Query")
    def query_short(self, obj):
        return obj.query[:80] + ("…" if len(obj.query) > 80 else "")


@admin.register(TitleFilter)
class TitleFilterAdmin(admin.ModelAdmin):

    def has_add_permission(self, request):
        return not TitleFilter.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        tf = TitleFilter.load()
        extra_context = extra_context or {}
        extra_context["tf"] = tf
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(JobBoard)
class JobBoardAdmin(admin.ModelAdmin):
    list_display = ["name", "provider", "enabled"]
    list_filter = ["enabled", "provider"]
    list_editable = ["enabled"]
    search_fields = ["name", "notes"]
