from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    location = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=100, blank=True)
    target_roles = models.JSONField(default=list, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=10, default="EUR")
    spend_tier = models.CharField(
        max_length=20,
        choices=[("economy", "Economy"), ("standard", "Standard"), ("premium", "Premium")],
        default="standard",
    )
    preferred_cli = models.CharField(max_length=50, blank=True, default="codex")
    synced_to_file = models.BooleanField(default=False)
