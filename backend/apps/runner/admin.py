from django.contrib import admin

from .models import RunEvent, RunLog


class RunEventInline(admin.TabularInline):
    model = RunEvent
    extra = 0
    readonly_fields = ["event", "payload", "created_at"]


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ["kind", "status", "cli_id", "report_number", "started_at", "finished_at"]
    list_filter = ["kind", "status", "cli_id"]
    search_fields = ["input_text", "stdout", "stderr", "error_message"]
    inlines = [RunEventInline]


@admin.register(RunEvent)
class RunEventAdmin(admin.ModelAdmin):
    list_display = ["run", "event", "created_at"]
    search_fields = ["event"]
