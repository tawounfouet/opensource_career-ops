from django.contrib import admin

from .models import CvDocument, CvVersion


@admin.register(CvDocument)
class CvDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "path", "updated_at"]


@admin.register(CvVersion)
class CvVersionAdmin(admin.ModelAdmin):
    list_display = ["document", "created_at"]
    readonly_fields = ["created_at"]
