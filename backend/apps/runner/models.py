from django.db import models


class RunLog(models.Model):
    kind = models.CharField(max_length=40)
    status = models.CharField(max_length=40, default="pending")
    input_text = models.TextField(blank=True)
    cli_id = models.CharField(max_length=50, blank=True)
    report_number = models.PositiveIntegerField(null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.kind} {self.status}"


class RunEvent(models.Model):
    run = models.ForeignKey(RunLog, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=80)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
