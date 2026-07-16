from django.db import models


class ScanMethod(models.TextChoices):
    AUTO = "auto", "Auto-detect"
    API = "api", "Direct API"
    WEBSEARCH = "websearch", "Web Search"
    LOCAL_PARSER = "local_parser", "Local Parser"


class Portal(models.Model):
    name = models.CharField(max_length=200, unique=True)
    careers_url = models.URLField(blank=True)
    enabled = models.BooleanField(default=True)
    ats = models.CharField(max_length=50, blank=True)
    api_endpoint = models.URLField(blank=True)
    scan_method = models.CharField(
        max_length=20, choices=ScanMethod.choices, default=ScanMethod.AUTO
    )
    scan_query = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    provider = models.CharField(max_length=50, blank=True)
    parser_config = models.JSONField(null=True, blank=True)
    max_pages = models.PositiveIntegerField(null=True, blank=True)
    extra_config = models.JSONField(default=dict, blank=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    is_live = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        status = "✅" if self.is_live and self.enabled else "❌"
        return f"{status} {self.name} ({self.ats or self.scan_method or 'custom'})"


class SearchQuery(models.Model):
    name = models.CharField(max_length=200, blank=True)
    query = models.CharField(max_length=300)
    source = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        label = self.name or self.query[:60]
        return label


class TitleFilter(models.Model):
    positive = models.JSONField(default=list, blank=True)
    negative = models.JSONField(default=list, blank=True)
    seniority_boost = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "title filter"
        verbose_name_plural = "title filters"

    def __str__(self) -> str:
        return f"title filter ({len(self.positive)} positive, {len(self.negative)} negative)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LocationFilter(models.Model):
    allow = models.JSONField(default=list, blank=True)
    block = models.JSONField(default=list, blank=True)
    always_allow = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "location filter"
        verbose_name_plural = "location filters"

    def __str__(self) -> str:
        return f"location filter ({len(self.allow)} allow, {len(self.block)} block)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class JobBoard(models.Model):
    name = models.CharField(max_length=200, unique=True)
    careers_url = models.URLField(blank=True)
    provider = models.CharField(max_length=50, blank=True)
    enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    extra_config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        status = "✅" if self.enabled else "⏸️"
        return f"{status} {self.name} ({self.provider or 'custom'})"
