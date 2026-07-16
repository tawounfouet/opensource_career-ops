from django.db import models


class Application(models.Model):
    number = models.PositiveIntegerField(unique=True, db_index=True)
    date = models.DateField(null=True, blank=True)
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=300)
    via = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=40, default="Evaluated")
    score = models.CharField(max_length=20, blank=True, default="")
    has_pdf = models.BooleanField(default=False)
    report_file = models.CharField(max_length=500, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    synced_to_file = models.BooleanField(default=False)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]

    def __str__(self) -> str:
        return f"#{self.number} {self.company} - {self.role}"

    def to_tsv_row(self) -> str:
        pdf = "✅" if self.has_pdf else "❌"
        return "\t".join([str(self.number), self.date.isoformat() if self.date else "", self.company, self.role, self.status, self.score, pdf, self.report_file, self.notes])


class PipelineJob(models.Model):
    url = models.URLField(unique=True, db_index=True)
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=300)
    location = models.CharField(max_length=200, blank=True)
    compensation = models.CharField(max_length=200, blank=True)
    done = models.BooleanField(default=False)
    posted_at = models.DateField(null=True, blank=True)
    synced_to_file = models.BooleanField(default=False)

    class Meta:
        ordering = ["done", "-posted_at", "company"]

    def __str__(self) -> str:
        return f"{self.company} - {self.role}"


class ScanHistory(models.Model):
    url = models.URLField(db_index=True)
    first_seen = models.DateField()
    last_seen = models.DateField(auto_now=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ["url", "source"]
        ordering = ["-first_seen"]
