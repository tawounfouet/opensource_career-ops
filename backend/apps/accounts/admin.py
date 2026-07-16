from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CareerOpsUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Career ops", {"fields": ("location", "timezone", "target_roles", "salary_min", "salary_max", "currency", "spend_tier", "preferred_cli", "synced_to_file")}),
    )
