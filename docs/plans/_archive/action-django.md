# Plan d'Action — Moteur Django pour career-ops

> **Objectif :** Créer un backend Django robuste avec admin personnalisé, auth, ORM, et management commands, connecté au frontend Next.js existant (`web/`).

> **Variante FastAPI :** voir [action-fastapi.md](action-fastapi.md) pour l'approche lightweight.

---

## Table des matières

1. [Pourquoi Django vs FastAPI](#1-pourquoi-django-vs-fastapi)
2. [Architecture cible](#2-architecture-cible)
3. [Inventaire des 31 routes API](#3-inventaire-des-31-routes-api)
4. [Structure du projet Django](#4-structure-du-projet-django)
5. [Modèles de données](#5-modèles-de-données)
6. [Admin personnalisé](#6-admin-personnalisé)
7. [Authentification et permissions](#7-authentification-et-permissions)
8. [Management commands (remplacement des .mjs)](#8-management-commands)
9. [API REST (DRF)](#9-api-rest-drf)
10. [Streaming NDJSON et temps réel](#10-streaming-ndjson-et-temps-réel)
11. [Phases de migration](#11-phases-de-migration)
12. [Matrice de couverture](#12-matrice-de-couverture)
13. [Comparaison finale](#13-comparaison-finale)
14. [Estimation temporelle](#14-estimation-temporelle)

---

## 1. Pourquoi Django vs FastAPI

### Ce que Django apporte de unique

| Fonctionnalité | FastAPI | Django | Impact career-ops |
|----------------|---------|--------|-------------------|
| **Admin personnalisé** | ❌ À coder (挫折) | ✅ Gratuit, auto-généré | Gestion visuelle du tracker, portals, plugins |
| **Auth built-in** | ❌ À coder (JWT, OAuth...) | ✅ Sessions + JWT + OAuth2 | Protéger le dashboard, multi-user |
| **ORM + Migrations** | ❌SQLAlchemy à configurer | ✅ Migrations auto, shell, fixtures | Schéma evolutif, seed data |
| **CSRF/XSS/SQLi** | ❌ À configurer manuellement | ✅ Middleware automatique | Sécurité zero-config |
| **Management commands** | ❌ Click/typer à ajouter | ✅ `python manage.py` natif | Remplacement naturel des .mjs |
| **Signals** | ❌ Non | ✅ Post-save, pre-save | Hooks automatiques après évaluation |
| **Middleware** | ✅ Dépendances injectées | ✅ Middleware chain | Logging, rate limiting, caching |
| **Template engine** | ❌ Jinja2 à ajouter | ✅ Django templates | Emails HTML, exports |
| **Serializers** | ✅ Pydantic natif | ✅ DRF serializers | Validation + documentation API |
| **Rate limiting** | ❌ slowapi à ajouter | ✅ Django-ratelimit | Protection API |
| **Logging structuré** | ✅ Python logging | ✅ Django logging config | Monitoring production |
| **Documentation API** | ✅ Swagger auto | ✅ DRF Swagger/ReDoc | API docs automatiques |
| **Celery integration** | ❌ À configurer | ✅django-celery-results | Jobs asynchrones (scan batch) |
| **File uploads** | ✅ UploadFile | ✅ FileField + validation | Upload CV, JD |
| **Tests** | ✅ pytest | ✅ pytest + Django TestCase | Fixtures, base de données test |

### Quand choisir quoi

```
┌─────────────────────────────────────────────────────────────┐
│                    CHOIX DU FRAMEWORK                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FastAPI si :                                                │
│  • Proto-rapide, peu de pages admin                          │
│  • Pas besoin d'auth complexe                               │
│  • API pure (pas de templates serveur)                       │
│  • Équipe backend petite, veut du minimal                    │
│                                                              │
│  Django si :                                                 │
│  • Admin dashboard pour gérer les données                    │
│  • Auth multi-utilisateurs nécessaire                        │
│  • Évolutivité long terme (ajout de modèles, features)      │
│  • Management commands pour remplacer les .mjs               │
│  • Équipe plus grande, veut de la structure                   │
│  • Production-grade dès le départ                            │
│                                                              │
│  → Django est le MEILLEUR choix pour career-ops :            │
│    l'admin seul vaut le coup (gérer 45+ portals, tracker,   │
│    plugins, blacklist, etc. sans écrire une ligne de UI)     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Verdict pour career-ops

**Django est supérieur** parce que :
1. **L'admin** permet de gérer `portals.yml`, `applications.md`, `blacklist.md`, `plugins` sans YAML manuel
2. **L'auth** protège le dashboard (aujourd'hui zéro protection)
3. **Les management commands** remplacent naturellement les 84 scripts .mjs
4. **Les signals** déclenchent des actions après évaluation (merge tracker, send notification)
5. **DRF** documente l'API automatiquement (Swagger/ReDoc)
6. **Les migrations** permettent d'évoluer le schéma sans casser les données

---

## 2. Architecture cible

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend React (web/)                      │
│  Next.js 16 — pur client, sert le bundle React              │
└──────────────────────┬──────────────────────────────────────┘
                       │ fetch("http://localhost:8000/api/...")
┌──────────────────────▼──────────────────────────────────────┐
│                    Django Backend                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  DRF API      │  │  Django Admin│  │  Management      │  │
│  │  /api/*       │  │  /admin/*    │  │  Commands         │  │
│  │  (31 routes)  │  │  (auto-gen)  │  │  manage.py scan   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                     │            │
│  ┌──────▼─────────────────▼─────────────────────▼─────────┐ │
│  │                    Services Layer                        │ │
│  │  tracker_service / scan_service / runner_service / ...  │ │
│  └──────────────────────┬──────────────────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────────┐ │
│  │              Django ORM + File Bridge                    │ │
│  │  Modèles : Application, Portal, Plugin, UserProfile     │ │
│  │  Fichiers : cv.md, reports/, pipeline.md (sync bidir)   │ │
│  └──────────────────────┬──────────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│   SQLite/PG  │ │ career-ops   │ │  CLI IA           │
│  (ORM data)  │ │ core .mjs    │ │  (claude, codex)  │
│              │ │ (scripts)    │ │  child_process     │
└──────────────┘ └──────────────┘ └──────────────────┘
```

### Hybride : fichiers + base de données

Django ne **remplace** pas les fichiers Markdown — il les **enrichit** :

| Donnée | Stockage | Raison |
|--------|----------|--------|
| `cv.md` | Fichier (source de vérité) | Le CLI IA le lit directement |
| `data/applications.md` | **DB + sync fichier** | ORM pour admin/query, fichier pour CLI |
| `portals.yml` | **DB + sync fichier** | Admin pour gérer, YAML pour scanner |
| `reports/*.md` | Fichiers (générés) | Les scripts .mjs les écrivent |
| `data/pipeline.md` | **DB + sync fichier** | Inbox gérable via admin |
| `config/profile.yml` | **DB + sync fichier** | Admin pour éditer, YAML pour scripts |
| `data/blacklist.md` | **DB + sync fichier** | Admin pour gérer |
| `plugins/` | **DB** | Admin natif |
| `users` | **DB** | Django auth natif |
| `sessions` | **DB** | Django sessions |
| `scan-history.tsv` | Fichier | Log d'append-only |

---

## 3. Inventaire des 31 routes API

*(Identique au plan FastAPI — voir [action-fastapi.md §2](action-fastapi.md#2-inventaire-des-31-routes-api))*

### Mapping Django

| Route | Vue DRF | ViewSet/View | Admin |
|-------|---------|-------------|-------|
| `GET /api/pipeline` | `PipelineViewSet` | `list()` | — |
| `GET/POST /api/cv` | `CvViewSet` | `get()`, `update()` | CVModelAdmin |
| `POST /api/cv/ingest` | `CvIngestView` | `post()` | — |
| `GET /api/cv-pdf` | `CvPdfView` | `get()` | — |
| `GET/POST /api/profile` | `ProfileViewSet` | `get()`, `update()` | ProfileModelAdmin |
| `GET/POST /api/portals` | `PortalViewSet` | `list()`, `update()` | PortalModelAdmin |
| `POST /api/portals/verify` | `PortalVerifyView` | `post()` | — |
| `POST /api/tracker/delete` | `TrackerDeleteView` | `post()` | ApplicationModelAdmin |
| `POST /api/status` | `StatusView` | `post()` | — |
| `GET/POST /api/memory` | `MemoryView` | `get()`, `post()` | — |
| `GET /api/doctor` | `DoctorView` | `get()` | — |
| `GET /api/version` | `VersionView` | `get()` | — |
| `GET /api/whats-new` | `WhatsNewView` | `get()` | — |
| `GET /api/followups` | `FollowupViewSet` | `list()` | FollowupModelAdmin |
| `POST /api/followups/log` | `FollowupLogView` | `post()` | — |
| `GET /api/usage` | `UsageView` | `get()` | — |
| `POST /api/report/shape` | `ReportShapeView` | `post()` | — |
| `POST /api/run` | `RunView` | `post()` | — |
| `POST /api/assistant` | `AssistantView` | `post()` | — |
| `POST /api/explore` | `ExploreView` | `post()` | — |
| `POST /api/explore/ai` | `ExploreAiView` | `post()` | — |
| `GET /api/explore/ai/known` | `ExploreAiKnownView` | `get()` | — |
| `POST /api/explore/add` | `ExploreAddView` | `post()` | — |
| `POST /api/apply/session` | `ApplySessionView` | `post()` | — |
| `POST /api/apply/prefill` | `ApplyPrefillView` | `post()` | — |
| `POST /api/apply/fill` | `ApplyFillView` | `post()` | — |
| `POST /api/apply/drive` | `ApplyDriveView` | `post()` | — |
| `POST /api/apply/close` | `ApplyCloseView` | `post()` | — |
| `POST /api/runs/save` | `RunsSaveView` | `post()` | RunLogModelAdmin |
| `GET /api/clis` | `ClisView` | `get()` | — |
| `GET /api/logo` | Static file | — | — |

---

## 4. Structure du projet Django

```
backend/
├── manage.py
├── pyproject.toml
├── .env
├── .env.example
│
├── config/                          # settings Django
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                 # settings partagés
│   │   ├── development.py          # dev (debug, SQLite)
│   │   └── production.py           # prod (PG, Redis, etc.)
│   ├── urls.py                     # URL routing principal
│   └── wsgi.py
│
├── apps/
│   ├── core/                       # App fondamentale
│   │   ├── __init__.py
│   │   ├── models.py              # — (pas de modèle DB ici)
│   │   ├── paths.py               # career_ops_root(), root_script()
│   │   ├── safe_write.py          # atomic_write, backup
│   │   ├── states.py              # Canonical states (lecture states.yml)
│   │   ├── tracker_parse.py       # Header-aware column mapping
│   │   ├── run_registry.py        # In-memory write token registry
│   │   ├── ndjson.py              # Streaming NDJSON helpers
│   │   └── management/
│   │       └── commands/
│   │           ├── scan_portals.py    # python manage.py scan_portals
│   │           ├── verify_pipeline.py # python manage.py verify_pipeline
│   │           ├── merge_tracker.py   # python manage.py merge_tracker
│   │           ├── normalize_statuses.py
│   │           ├── dedup_tracker.py
│   │           ├── doctor.py          # python manage.py doctor
│   │           └── update_system.py
│   │
│   ├── tracker/                    # App tracker
│   │   ├── __init__.py
│   │   ├── models.py              # Application, PipelineJob, ScanHistory
│   │   ├── admin.py               # ApplicationModelAdmin (custom)
│   │   ├── serializers.py         # DRF serializers
│   │   ├── views.py               # DRF viewsets
│   │   ├── services.py            # Business logic
│   │   ├── signals.py             # post_save → sync fichier
│   │   └── migrations/
│   │
│   ├── cv/                         # App CV
│   │   ├── models.py              # CvDocument, CvVersion
│   │   ├── admin.py               # CVModelAdmin
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py
│   │   └── migrations/
│   │
│   ├── portals/                    # App Portals
│   │   ├── models.py              # Portal, Company, SearchQuery
│   │   ├── admin.py               # PortalModelAdmin
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py
│   │   ├── tasks.py               # Celery tasks (scan async)
│   │   └── migrations/
│   │
│   ├── scan/                       # App Scan
│   │   ├── models.py              # ScanRun, DiscoveredOffer
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── views.py               # NDJSON streaming
│   │   ├── services.py            # scan-ats-full.mjs orchestration
│   │   └── migrations/
│   │
│   ├── runner/                     # App Runner (CLI orchestration)
│   │   ├── models.py              # RunLog, RunEvent
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── views.py               # /api/run, /api/assistant
│   │   ├── services.py            # CLI spawning + NDJSON
│   │   ├── cli_detector.py        # Détection CLIs installés
│   │   └── migrations/
│   │
│   ├── apply/                      # App Apply (Playwright)
│   │   ├── models.py              # ApplySession
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py            # Playwright session management
│   │   └── migrations/
│   │
│   ├── reports/                    # App Reports
│   │   ├── models.py              # Report (index only, files stay)
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── services.py
│   │
│   ├── followups/                  # App Followups
│   │   ├── models.py              # FollowupEntry
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py
│   │   └── migrations/
│   │
│   └── accounts/                   # App Auth
│       ├── models.py              # UserProfile (extend User)
│       ├── admin.py               # UserAdmin custom
│       ├── serializers.py
│       ├── views.py               # Login, logout, profile
│       ├── backends.py            # Auth backends
│       └── migrations/
│
├── templates/                      # Django templates
│   ├── admin/                      # Admin skin custom
│   │   ├── base_site.html
│   │   └── tracker/
│   │       └── change_list.html    # Custom tracker list
│   └── emails/                     # Email templates
│
├── static/                         # Static files
│   ├── admin/                      # Admin custom CSS
│   └── css/
│
├── tests/                          # Tests
│   ├── conftest.py
│   ├── test_tracker/
│   ├── test_cv/
│   ├── test_scan/
│   ├── test_runner/
│   └── test_api_compat.py          # Compat avec les réponses Node.js
│
└── scripts/
    └── dev.sh                      # Lance Django + Next.js
```

---

## 5. Modèles de données

### 5.1 `apps/tracker/models.py`

```python
from django.db import models

class Application(models.Model):
    """Gère une candidature — sync bidirectionnelle avec data/applications.md"""

    class Status(models.TextChoices):
        EVALUATED = "Evaluated", "Evaluated"
        APPLIED = "Applied", "Applied"
        RESPONDED = "Responded", "Responded"
        INTERVIEW = "Interview", "Interview"
        OFFER = "Offer", "Offer"
        REJECTED = "Rejected", "Rejected"
        DISCARDED = "Discarded", "Discarded"
        SKIP = "SKIP", "SKIP"

    number = models.PositiveIntegerField(unique=True, db_index=True)
    date = models.DateField()
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=300)
    via = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EVALUATED)
    score = models.CharField(max_length=10, blank=True, default="")  # "4.2/5"
    has_pdf = models.BooleanField(default=False)
    report_file = models.CharField(max_length=500, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # Sync state
    synced_to_file = models.BooleanField(default=False)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]

    def __str__(self):
        return f"#{self.number} {self.company} — {self.role}"

    def to_tsv_row(self) -> str:
        """Export as TSV row for merge-tracker.mjs"""
        pdf = "✅" if self.has_pdf else "❌"
        return "\t".join([
            str(self.number),
            self.date.isoformat(),
            self.company,
            self.role,
            self.status,
            self.score,
            pdf,
            f"[{self.number}]({self.report_file})",
            self.notes,
        ])


class PipelineJob(models.Model):
    """Entrée dans data/pipeline.md — inbox des URLs à évaluer"""

    url = models.URLField(unique=True, db_index=True)
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=300)
    location = models.CharField(max_length=200, blank=True)
    compensation = models.CharField(max_length=200, blank=True)
    done = models.BooleanField(default=False)
    posted_at = models.DateField(null=True, blank=True)

    # Sync
    synced_to_file = models.BooleanField(default=False)

    class Meta:
        ordering = ["-posted_at"]

    def __str__(self):
        return f"{self.company} — {self.role}"


class ScanHistory(models.Model):
    """Append-only log de scan (data/scan-history.tsv)"""

    url = models.URLField(db_index=True)
    first_seen = models.DateField()
    last_seen = models.DateField(auto_now=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ["url", "source"]
        ordering = ["-first_seen"]
```

### 5.2 `apps/portals/models.py`

```python
class Portal(models.Model):
    """Entreprise configurée pour le scan (remplace portals.yml)"""

    class ATSChoices(models.TextChoices):
        GREENHOUSE = "greenhouse", "Greenhouse"
        ASHBY = "ashby", "Ashby"
        LEVER = "lever", "Lever"
        WORKDAY = "workday", "Workday"
        BAMBOOHR = "bamboohr", "BambooHR"
        PERSONIO = "personio", "Personio"
        SMARTRECRUITERS = "smartrecruiters", "SmartRecruiters"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=200, unique=True)
    ats = models.CharField(max_length=50, choices=ATSChoices.choices)
    enabled = models.BooleanField(default=True)
    greenhouse_token = models.CharField(max_length=200, blank=True)
    ashby_slug = models.CharField(max_length=200, blank=True)
    lever_slug = models.CharField(max_length=200, blank=True)
    careers_url = models.URLField(blank=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    is_live = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        status = "✅" if self.is_live else "❌"
        return f"{status} {self.name} ({self.ats})"


class SearchQuery(models.Model):
    """Requête de scan (remplace search_queries dans portals.yml)"""

    query = models.CharField(max_length=300)
    source = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.query
```

### 5.3 `apps/accounts/models.py`

```python
from django.contrib.auth.models import AbstractUser

class UserProfile(AbstractUser):
    """Profil étendu — sync avec config/profile.yml"""

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
    preferred_cli = models.CharField(max_length=50, blank=True, default="claude")

    # Sync
    synced_to_file = models.BooleanField(default=False)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
```

### 5.4 `apps/runner/models.py`

```python
class RunLog(models.Model):
    """Log d'exécution d'un worker (évaluation, PDF, recherche)"""

    class RunKind(models.TextChoices):
        EVALUATE = "evaluate", "Evaluate"
        PDF = "pdf", "Generate PDF"
        RESEARCH = "research", "Research"
        FIX_PORTAL = "fix-portal", "Fix Portal"

    class RunStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=20, choices=RunKind.choices)
    status = models.CharField(max_length=20, choices=RunStatus.choices, default=RunStatus.PENDING)
    input_text = models.TextField()
    cli_id = models.CharField(max_length=50)
    report_number = models.PositiveIntegerField(null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"[{self.kind}] {self.status} — {self.started_at}"
```

### 5.5 `apps/reports/models.py`

```python
class Report(models.Model):
    """Index des rapports (les fichiers .md restent dans reports/)"""

    number = models.PositiveIntegerField(unique=True)
    company_slug = models.CharField(max_length=200)
    date = models.DateField()
    filename = models.CharField(max_length=500)
    score = models.CharField(max_length=10, blank=True)
    legitimacy = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-number"]

    def __str__(self):
        return f"#{self.number} {self.company_slug}"

    @property
    def file_path(self):
        return settings.CAREER_OPS_ROOT / "reports" / self.filename
```

---

## 6. Admin personnalisé

### 6.1 `apps/tracker/admin.py`

```python
from django.contrib import admin
from django.utils.html import format_html
from .models import Application, PipelineJob, ScanHistory

@admin.register(Application)
class ApplicationModelAdmin(admin.ModelAdmin):
    list_display = ["number", "company", "role", "status_badge", "score", "has_pdf", "date"]
    list_filter = ["status", "has_pdf", "date"]
    search_fields = ["company", "role", "notes"]
    readonly_fields = ["number", "date", "synced_to_file", "last_synced"]
    list_editable = ["status"]
    list_per_page = 50
    actions = ["mark_applied", "mark_rejected", "export_tsv"]

    fieldsets = (
        ("Identité", {"fields": ("number", "date", "company", "role", "via")}),
        ("Statut", {"fields": ("status", "score", "has_pdf", "report_file", "notes")}),
        ("Sync", {"fields": ("synced_to_file", "last_synced"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colors = {
            "Evaluated": "#3b82f6",
            "Applied": "#f59e0b",
            "Interview": "#8b5cf6",
            "Offer": "#10b981",
            "Rejected": "#ef4444",
            "Discarded": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{}</span>',
            color, obj.status
        )
    status_badge.short_description = "Status"

    @admin.action(description="Mark as Applied")
    def mark_applied(self, request, queryset):
        queryset.update(status="Applied")

    @admin.action(description="Mark as Rejected")
    def mark_rejected(self, request, queryset):
        queryset.update(status="Rejected")

    @admin.action(description="Export as TSV")
    def export_tsv(self, request, queryset):
        tsv = "\n".join(app.to_tsv_row() for app in queryset)
        response = HttpResponse(tsv, content_type="text/tab-separated-values")
        response["Content-Disposition"] = "attachment; filename=tracker-export.tsv"
        return response


@admin.register(PipelineJob)
class PipelineJobModelAdmin(admin.ModelAdmin):
    list_display = ["company", "role", "location", "done", "posted_at"]
    list_filter = ["done", "posted_at"]
    search_fields = ["company", "role", "url"]
    list_editable = ["done"]
    actions = ["mark_all_done"]

    @admin.action(description="Mark all as done")
    def mark_all_done(self, request, queryset):
        queryset.update(done=True)


@admin.register(ScanHistory)
class ScanHistoryModelAdmin(admin.ModelAdmin):
    list_display = ["url", "first_seen", "last_seen", "source"]
    readonly_fields = ["url", "first_seen", "last_seen", "source"]
```

### 6.2 `apps/portals/admin.py`

```python
@admin.register(Portal)
class PortalModelAdmin(admin.ModelAdmin):
    list_display = ["name", "ats_badge", "enabled", "is_live", "last_verified"]
    list_filter = ["ats", "enabled", "is_live"]
    search_fields = ["name"]
    list_editable = ["enabled", "is_live"]
    actions = ["verify_portals", "export_yaml"]

    @admin.action(description="Verify selected portals")
    def verify_portals(self, request, queryset):
        # Lance verify-portals.mjs pour chaque portal sélectionné
        for portal in queryset:
            verify_portal.delay(portal.id)

    @admin.action(description="Export as portals.yml")
    def export_yaml(self, request, queryset):
        yaml_content = portals_to_yaml(queryset)
        response = HttpResponse(yaml_content, content_type="text/yaml")
        response["Content-Disposition"] = "attachment; filename=portals.yml"
        return response
```

### 6.3 `apps/followups/admin.py`

```python
@admin.register(FollowupEntry)
class FollowupModelAdmin(admin.ModelAdmin):
    list_display = ["application", "scheduled_date", "status", "channel", "sent_at"]
    list_filter = ["status", "channel", "scheduled_date"]
    list_editable = ["status"]
    date_hierarchy = "scheduled_date"
```

### 6.4 Admin custom skin

```python
# config/settings/base.py
ADMIN_SITE_HEADER = "career-ops"
ADMIN_SITE_TITLE = "career-ops Admin"
ADMIN_INDEX_TEMPLATE = "admin/custom_index.html"
```

```html
<!-- templates/admin/custom_index.html -->
{% extends "admin/index.html" %}
{% block content %}
<div class="module" style="padding: 20px;">
    <h2>career-ops Dashboard</h2>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
        <div class="stat-card">
            <h3>{{ total_applications }}</h3>
            <p>Applications</p>
        </div>
        <div class="stat-card">
            <h3>{{ total_evaluated }}</h3>
            <p>Evaluated</p>
        </div>
        <div class="stat-card">
            <h3>{{ total_interviews }}</h3>
            <p>Interviews</p>
        </div>
        <div class="stat-card">
            <h3>{{ total_offers }}</h3>
            <p>Offers</p>
        </div>
    </div>
</div>
{{ block.super }}
{% endblock %}
```

---

## 7. Authentification et permissions

### 7.1 `apps/accounts/backends.py`

```python
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    """Auth par email au lieu de username"""
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email", username)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        if user.check_password(password):
            return user
```

### 7.2 Permissions custom

```python
# apps/core/permissions.py
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """L'utilisateur ne peut modifier que ses propres données"""

class CanManageTracker(permissions.BasePermission):
    """Peut gérer le tracker (admin ou owner)"""

class CanRunEvaluations(permissions.BasePermission):
    """Peut lancer des évaluations (coûte des tokens)"""

class CanAccessApply(permissions.BasePermission):
    """Peut utiliser le mode apply (Playwright sessions)"""
```

### 7.3 Settings auth

```python
# config/settings/base.py
AUTH_USER_MODEL = "accounts.UserProfile"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/api/pipeline"
```

---

## 8. Management commands (remplacement des .mjs)

Chaque script .mjs principal devient un `manage.py` command :

| Script .mjs | Management command | Description |
|-------------|-------------------|-------------|
| `scan.mjs` | `python manage.py scan_portals` | Scan zero-token |
| `scan-ats-full.mjs` | `python manage.py scan_discover` | Scan inversé complet |
| `verify-pipeline.mjs` | `python manage.py verify_pipeline` | Health check (12 checks) |
| `merge-tracker.mjs` | `python manage.py merge_tracker` | Fusion TSV → tracker |
| `normalize-statuses.mjs` | `python manage.py normalize_statuses` | Normaliser les statuts |
| `dedup-tracker.mjs` | `python manage.py dedup_tracker` | Supprimer doublons |
| `set-status.mjs` | `python manage.py set_status <n> <status>` | Mettre à jour statut |
| `followup-cadence.mjs` | `python manage.py followup_cadence` | Calcul relances |
| `followup-seed.mjs` | `python manage.py followup_seed` | Seed relances |
| `analyze-patterns.mjs` | `python manage.py analyze_patterns` | Patterns de refus |
| `upskill.mjs` | `python manage.py upskill` | Gaps compétences |
| `stats.mjs` | `python manage.py pipeline_stats` | Stats pipeline |
| `doctor.mjs` | `python manage.py doctor` | Vérification setup |
| `update-system.mjs` | `python manage.py update_system` | Mise à jour système |
| `detect-reposts.mjs` | `python manage.py detect_reposts` | Détection reposts |
| `salary-gap.mjs` | `python manage.py salary_gap` | Écart salarial |
| `jd-skill-gap.mjs` | `python manage.py jd_skill_gap` | Gaps vs JD |
| `match-star.mjs` | `python manage.py match_star` | Match stories STAR |
| `invite-match.mjs` | `python manage.py invite_match` | Match invitations |
| `process-quality.mjs` | `python manage.py process_quality` | Qualité processus |
| `tracker.mjs` | `python manage.py tracker_query` | Requêtes tracker |

### Exemple : `scan_portals.py`

```python
# apps/core/management/commands/scan_portals.py
from django.core.management.base import BaseCommand
from apps.portals.models import Portal
from apps.scan.services import run_scan

class Command(BaseCommand):
    help = "Scan configured portals for new job postings (zero-token)"

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true", help="Verify liveness")
        parser.add_argument("--ats", type=str, help="Comma-separated ATS filter")
        parser.add_argument("--since", type=int, default=7, help="Days to look back")
        parser.add_argument("--json", action="store_true", help="JSON output")

    def handle(self, *args, **options):
        portals = Portal.objects.filter(enabled=True)
        if options["ats"]:
            ats_list = options["ats"].split(",")
            portals = portals.filter(ats__in=ats_list)

        self.stdout.write(f"Scanning {portals.count()} portals...")

        results = run_scan(
            portals=portals,
            since_days=options["since"],
            verify=options["verify"],
            json_output=options["json"],
        )

        if options["json"]:
            self.stdout.write(json.dumps(results))
        else:
            self.stdout.write(f"Found {len(results)} new postings")
```

### Exemple : `merge_tracker.py`

```python
# apps/core/management/commands/merge_tracker.py
from django.core.management.base import BaseCommand
from pathlib import Path
from apps.tracker.services import merge_tsv_additions

class Command(BaseCommand):
    help = "Merge TSV additions from batch/tracker-additions/ into applications.md"

    def handle(self, *args, **options):
        additions_dir = settings.CAREER_OPS_ROOT / "batch" / "tracker-additions"
        tsv_files = list(additions_dir.glob("*.tsv"))

        if not tsv_files:
            self.stdout.write("No TSV files to merge")
            return

        for tsv_file in tsv_files:
            self.stdout.write(f"Merging {tsv_file.name}...")
            result = merge_tsv_additions(tsv_file)
            self.stdout.write(f"  → {result.added} added, {result.skipped} skipped")

            # Archive processed TSV
            archive_dir = additions_dir / "processed"
            archive_dir.mkdir(exist_ok=True)
            tsv_file.rename(archive_dir / tsv_file.name)
```

---

## 9. API REST (DRF)

### 9.1 `apps/tracker/serializers.py`

```python
from rest_framework import serializers
from .models import Application, PipelineJob

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = "__all__"
        read_only_fields = ["number", "synced_to_file", "last_synced"]

class PipelineJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineJob
        fields = "__all__"
        read_only_fields = ["synced_to_file"]

class PipelineSummarySerializer(serializers.Serializer):
    root = serializers.CharField()
    rootExists = serializers.BooleanField()
    inbox = PipelineJobSerializer(many=True)
    applications = ApplicationSerializer(many=True)
```

### 9.2 `apps/tracker/views.py`

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import StreamingHttpResponse
import json

from .models import Application, PipelineJob
from .serializers import ApplicationSerializer, PipelineSummarySerializer
from .services import TrackerService
from apps.core.permissions import CanManageTracker

class PipelineViewSet(viewsets.ViewSet):
    """GET /api/pipeline — résumé complet du pipeline"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        service = TrackerService()
        summary = service.build_summary()
        return Response(PipelineSummarySerializer(summary).data)


class ApplicationViewSet(viewsets.ModelViewSet):
    """CRUD sur les candidatures"""
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, CanManageTracker]
    lookup_field = "number"

    @action(detail=True, methods=["post"])
    def set_status(self, request, number=None):
        app = self.get_object()
        new_status = request.data.get("status")
        if new_status not in dict(Application.Status.choices):
            return Response({"error": "invalid status"}, status=400)
        app.status = new_status
        app.save()
        # Signal post_save sync automatiquement le fichier
        return Response({"ok": True, "status": new_status})

    @action(detail=True, methods=["post"])
    def delete_row(self, request, number=None):
        app = self.get_object()
        # Appelle tracker.mjs delete --num N
        from apps.core.management.commands.merge_tracker import delete_tracker_row
        result = delete_tracker_row(number)
        return Response(result)
```

### 9.3 `apps/runner/views.py` (streaming)

```python
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import StreamingHttpResponse
import json, asyncio

class RunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        kind = request.data.get("kind", "evaluate")
        input_text = request.data.get("input")
        cli_id = request.data.get("cli_id")

        if not input_text or not cli_id:
            return Response({"error": "input and cli_id required"}, status=400)

        async def stream():
            proc = await asyncio.create_subprocess_exec(
                *self._build_args(kind, input_text, cli_id),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            async for line in proc.stdout:
                yield json.dumps({"type": "text", "text": line.decode()}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

        return StreamingHttpResponse(stream(), content_type="text/plain")
```

### 9.4 URLs

```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"pipeline", PipelineViewSet, basename="pipeline")
router.register(r"applications", ApplicationViewSet, basename="application")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/cv/", include("apps.cv.urls")),
    path("api/portals/", include("apps.portals.urls")),
    path("api/scan/", include("apps.scan.urls")),
    path("api/run/", RunView.as_view(), name="run"),
    path("api/assistant/", AssistantView.as_view(), name="assistant"),
    path("api/explore/", include("apps.scan.urls_explore")),
    path("api/apply/", include("apps.apply.urls")),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/doctor/", DoctorView.as_view(), name="doctor"),
    path("api/version/", VersionView.as_view(), name="version"),
    path("api/memory/", MemoryView.as_view(), name="memory"),
    path("api/followups/", include("apps.followups.urls")),
]
```

---

## 10. Streaming NDJSON et temps réel

### 10.1 `apps/core/ndjson.py`

```python
import json
from typing import AsyncGenerator
from django.http import StreamingHttpResponse

async def ndjson_stream(generator: AsyncGenerator[dict, None]):
    """Wrapper pour streaming NDJSON — compatible avec le frontend existant"""
    async for event in generator:
        yield json.dumps(event) + "\n"

def stream_response(generator: AsyncGenerator[dict, None], content_type="text/plain"):
    """Crée une StreamingHttpResponse NDJSON"""
    return StreamingHttpResponse(
        ndjson_stream(generator),
        content_type=content_type,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
```

### 10.2 Patterns de streaming

Le frontend parse du NDJSON. Chaque event a un `type` :

```python
# Types d'événements supportés
EVENTS = {
    "text":     {"type": "text", "text": "..."},
    "tool":     {"type": "tool", "name": "Read"},
    "status":   {"type": "status", "label": "Agent ready"},
    "error":    {"type": "error", "msg": "..."},
    "done":     {"type": "done", "tokens": 1234, "costUsd": 0.001},
    "offer":    {"type": "offer", "company": "...", "title": "...", "url": "..."},
    "progress": {"type": "progress", "ats": "greenhouse", "scanned": 10, "total": 50},
    "summary":  {"type": "summary", "companiesScanned": 45, "matches": 12},
}
```

---

## 11. Phases de migration

### Phase 1 — Fondations (3-4 jours)

```
✅ Créer le projet Django (startproject, apps)
✅ Configurer settings (CAREER_OPS_ROOT, auth, DRF)
✅ Créer les modèles de base (Application, Portal, PipelineJob)
✅ Créer les management commands de base (doctor, verify_pipeline)
✅ Sync fichiers → DB (import initial depuis applications.md, portals.yml)
✅ Admin de base (listes, filtres, recherche)
```

### Phase 2 — Core data + Admin avancé (4-5 jours)

```
✅ Admin personnalisé (badges, actions, fieldsets, export)
✅ Tracker service (parse applications.md, sync bidirectionnelle)
✅ CV service (read/write cv.md avec backup)
✅ Profile service (read/write profile.yml)
✅ Portals service (sync DB ↔ YAML)
✅ Memory service (managed block dans _profile.md)
✅ Tests de compatibilité avec les réponses Node.js
```

### Phase 3 — Orchestration CLI (4-5 jours)

```
✅ Runner service (asyncio.create_subprocess_exec)
✅ Assistant service (streaming NDJSON)
✅ Scan service (scan-ats-full.mjs orchestration)
✅ Explore service (découverte IA + dédup)
✅ CLI detector (shutil.which)
✅ Run log model + admin
```

### Phase 4 — Apply + Streaming (3-4 jours)

```
✅ Apply service (Playwright Python sessions)
✅ Streaming NDJSON pour tous les endpoints
✅ WebSocket pour assistant temps réel (optionnel)
✅ Rate limiting (django-ratelimit)
```

### Phase 5 — Frontend adaptation (2-3 jours)

```
✅ Proxy Next.js → Django (1 ligne config)
✅ Ou: direct URL swap dans le frontend
✅ Tests end-to-end
✅ Documentation API (Swagger/ReDoc)
```

### Phase 6 — Production (2-3 jours)

```
✅ Docker Compose (Django + Next.js + PostgreSQL)
✅ Gunicorn + Nginx config
✅ CI/CD (GitHub Actions pour Django)
✅ Monitoring (Sentry, health checks)
✅ Documentation déploiement
```

---

## 12. Matrice de couverture

*(Identique au plan FastAPI — voir [action-fastapi.md §13](action-fastapi.md#13-matrice-de-couverture))*

---

## 13. Comparaison finale

| Critère | FastAPI | Django | Gagnant |
|---------|---------|--------|---------|
| **Vitesse de setup** | 1 jour | 2-3 jours | FastAPI |
| **Admin UI** | ❌ À coder | ✅ Gratuit | Django |
| **Auth** | ❌ JWT/OAuth à coder | ✅ Sessions natif | Django |
| **ORM** | SQLAlchemy (config lourde) | Django ORM (simple) | Django |
| **Migrations** | Alembic (manuel) | Auto (django) | Django |
| **Management commands** | Click/typer | `manage.py` natif | Django |
| **API docs** | Swagger natif | DRF Swagger | Égal |
| **Streaming** | Natif | StreamingHttpResponse | Égal |
| **Performance** | Ultra-rapide | Rapide (suffisant) | FastAPI |
| **Écosystème** | Moderne, léger | Mature, battle-tested | Django |
| **Apprentissage** | Facile (si connu Python) | Facile (plus de conventions) | Égal |
| **Long terme** | Bon | Excellent | Django |
| **Sécurité** | À configurer | Zero-config | Django |
| **Multi-user** | À coder | Natif | Django |
| **Admin dashboard** | 0% prêt | 80% prêt | Django |

### Recommandation

> **Django est le meilleur choix pour career-ops** car :
> 1. L'admin seul économise **2-3 semaines** de UI development
> 2. L'auth natif protège le dashboard immédiatement
> 3. Les management commands remplacent naturellement les 84 scripts .mjs
> 4. Les signals déclenchent des actions automatiques (sync fichier, notifications)
> 5. Le schema est evolutif via les migrations
> 6. L'écosystème est mature pour la production

---

## 14. Estimation temporelle

| Phase | Jours | FastAPI équivalent |
|-------|-------|--------------------|
| Phase 1 — Fondations | 3-4 | 2-3 |
| Phase 2 — Core data + Admin | 4-5 | 3-4 |
| Phase 3 — Orchestration CLI | 4-5 | 4-5 |
| Phase 4 — Apply + Streaming | 3-4 | 2-3 |
| Phase 5 — Frontend adaptation | 2-3 | 1-2 |
| Phase 6 — Production | 2-3 | 1 |
| **Total** | **18-24 jours** | **15-20 jours** |

**Django prend ~3-4 jours de plus** mais offre un résultat **nettement plus complet** (admin, auth, migrations, management commands).

### Ordre de recommandation

```
Semaine 1 : Phase 1 (fondations Django + modèles + admin de base)
Semaine 2 : Phase 2 (services + admin avancé + sync fichiers)
Semaine 3 : Phase 3 (orchestration CLI + streaming)
Semaine 4 : Phase 4-5 (apply + frontend adaptation)
Semaine 5 : Phase 6 (tests + production)
```

---

*Document généré le 14 juillet 2026. Comparaison avec FastAPI : [action-fastapi.md](action-fastapi.md). Analyse du projet : [analyse-projet.md](analyse-projet.md).*
