"""Models for the user-owned skills portfolio.

The portfolio turns experiences into explicit, evidenced competencies. LLMs may
help draft/formalize content, but validated competencies must stay grounded in
user-provided experiences and proof.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


EXPERIENCE_TYPE = [
    ("professional", "Professional"),
    ("project", "Project"),
    ("education", "Education"),
    ("volunteer", "Volunteer"),
    ("personal", "Personal"),
    ("travel", "Travel"),
    ("cultural", "Cultural"),
    ("other", "Other"),
]

COMPETENCY_CATEGORY = [
    ("knowledge", "Savoir"),
    ("hard_skill", "Savoir-faire"),
    ("soft_skill", "Savoir-etre"),
]

MASTERY_LEVEL = [
    ("beginner", "Debutant"),
    ("junior", "Junior"),
    ("confirmed", "Confirme"),
    ("expert", "Expert"),
]

CONFIDENCE = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

COMPETENCY_STATUS = [
    ("draft", "Draft"),
    ("validated", "Validated"),
    ("rejected", "Rejected"),
    ("archived", "Archived"),
]

EVIDENCE_TYPE = [
    ("deliverable", "Deliverable"),
    ("metric", "Metric"),
    ("feedback", "Feedback"),
    ("certificate", "Certificate"),
    ("portfolio_link", "Portfolio link"),
    ("report", "Report"),
    ("story", "Story"),
    ("document", "Document"),
    ("other", "Other"),
]

TRUST_LEVEL = [
    ("user_confirmed", "User confirmed"),
    ("imported", "Imported"),
    ("inferred_pending_review", "Inferred pending review"),
]

RUN_STATUS = [
    ("success", "Success"),
    ("failed", "Failed"),
    ("partial", "Partial"),
]


class SkillExperience(models.Model):
    """A user-provided source experience from which competencies are derived."""

    title = models.CharField(max_length=240)
    type = models.CharField(max_length=24, choices=EXPERIENCE_TYPE, default="professional")
    organization = models.CharField(max_length=240, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=240, blank=True, default="")
    description = models.TextField(blank=True, default="")
    missions = models.JSONField(default=list, blank=True)
    responsibilities = models.JSONField(default=list, blank=True)
    deliverables = models.JSONField(default=list, blank=True)
    outcomes = models.JSONField(default=list, blank=True)
    tools = models.JSONField(default=list, blank=True)
    people_context = models.TextField(blank=True, default="")
    source_refs = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at", "title"]

    def __str__(self) -> str:
        return self.title


class SkillEvidence(models.Model):
    """Proof attached to one or more competencies."""

    type = models.CharField(max_length=32, choices=EVIDENCE_TYPE, default="other")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True, default="")
    url = models.URLField(blank=True, default="")
    file_path = models.CharField(max_length=500, blank=True, default="")
    metric = models.CharField(max_length=240, blank=True, default="")
    source_experience = models.ForeignKey(
        SkillExperience, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidence"
    )
    trust_level = models.CharField(max_length=32, choices=TRUST_LEVEL, default="user_confirmed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class SkillCompetency(models.Model):
    """A contextualized and evidenced capability."""

    label = models.CharField(max_length=240)
    formulation = models.TextField()
    category = models.CharField(max_length=24, choices=COMPETENCY_CATEGORY)
    action_verb = models.CharField(max_length=80, blank=True, default="")
    object = models.CharField(max_length=240, blank=True, default="")
    context = models.TextField(blank=True, default="")
    experiences = models.ManyToManyField(SkillExperience, blank=True, related_name="competencies")
    evidence = models.ManyToManyField(SkillEvidence, blank=True, related_name="competencies")
    mastery_level = models.CharField(max_length=24, choices=MASTERY_LEVEL, default="junior")
    mastery_rationale = models.TextField(blank=True, default="")
    confidence = models.CharField(max_length=16, choices=CONFIDENCE, default="medium")
    status = models.CharField(max_length=24, choices=COMPETENCY_STATUS, default="draft")
    tags = models.JSONField(default=list, blank=True)
    market_keywords = models.JSONField(default=list, blank=True)
    created_by = models.CharField(max_length=24, default="user")
    validated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label"]
        verbose_name_plural = "skill competencies"

    def __str__(self) -> str:
        return self.label

    def validate(self) -> None:
        if not self.evidence.exists():
            raise ValidationError("A competency needs at least one evidence item before validation.")
        self.status = "validated"
        self.validated_at = timezone.now()
        self.save(update_fields=["status", "validated_at", "updated_at"])

    def reject(self) -> None:
        self.status = "rejected"
        self.save(update_fields=["status", "updated_at"])


class SkillDevelopmentAction(models.Model):
    competency = models.ForeignKey(SkillCompetency, on_delete=models.CASCADE, related_name="development_actions")
    target_level = models.CharField(max_length=24, choices=MASTERY_LEVEL, default="confirmed")
    reason = models.TextField(blank=True, default="")
    actions = models.JSONField(default=list, blank=True)
    resources = models.JSONField(default=list, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, default="planned")
    review_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deadline", "-created_at"]

    def __str__(self) -> str:
        return f"{self.competency}: {self.target_level}"


EDUCATION_TYPE = [
    ("formation", "Formation"),
    ("certification", "Certification"),
    ("rncp", "Titre RNCP"),
    ("professional", "Formation professionnelle"),
    ("mooc", "MOOC / e-learning"),
]

EDUCATION_STATUS = [
    ("planned", "Planifiee"),
    ("in_progress", "En cours"),
    ("completed", "Terminee"),
    ("expired", "Expiree"),
]

EDUCATION_RELEVANCE = [
    ("validated", "Validee par cette formation"),
    ("acquired", "Acquise pendant cette formation"),
    ("targeted", "Objectif de cette formation"),
]


class Education(models.Model):
    """A training, certification, or academic credential."""

    title = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True, default="")
    education_type = models.CharField(max_length=20, choices=EDUCATION_TYPE, default="formation")
    status = models.CharField(max_length=20, choices=EDUCATION_STATUS, default="planned")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    credential_url = models.URLField(blank=True, default="")
    credential_id = models.CharField(max_length=255, blank=True, default="")
    hours = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    competencies = models.ManyToManyField(
        SkillCompetency, through="EducationCompetency", blank=True, related_name="educations"
    )
    experience = models.ForeignKey(
        SkillExperience, null=True, blank=True, on_delete=models.SET_NULL, related_name="educations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at", "title"]

    def __str__(self) -> str:
        return self.title


class EducationCompetency(models.Model):
    """Link between an education entry and a competency."""

    education = models.ForeignKey(Education, on_delete=models.CASCADE, related_name="education_links")
    competency = models.ForeignKey(SkillCompetency, on_delete=models.CASCADE, related_name="education_links")
    relevance = models.CharField(max_length=20, choices=EDUCATION_RELEVANCE, default="acquired")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("education", "competency")

    def __str__(self) -> str:
        return f"{self.education} → {self.competency} ({self.relevance})"


class SkillExtractionRun(models.Model):
    """Audit trail for LLM-assisted extraction/formalization."""

    experience = models.ForeignKey(SkillExperience, null=True, blank=True, on_delete=models.SET_NULL, related_name="extraction_runs")
    provider = models.CharField(max_length=80, blank=True, default="")
    model = models.CharField(max_length=160, blank=True, default="")
    prompt_template = models.CharField(max_length=160)
    input_hash = models.CharField(max_length=80, blank=True, default="")
    output_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=RUN_STATUS, default="success")
    error = models.TextField(blank=True, default="")
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.prompt_template} [{self.status}]" 
