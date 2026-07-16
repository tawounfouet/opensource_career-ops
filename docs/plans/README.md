# Plans & Roadmap

All architectural plans, migration strategies, and implementation roadmaps for career-ops.

## Active Plans

| Plan | Status | Description |
|------|--------|-------------|
| [Python Migration](python-migration.md) | In progress | Migration of 85 JS scripts → Python |
| [Python Migration Remaining](python-migration-remaining.md) | In progress | Current handoff checklist for remaining Python migration work |
| [Profile Architecture](profile-architecture.md) | In progress | Multi-profile system with YAML variants |
| [Django Remaining](django-remaining.md) | In progress | Remaining Django implementation checklist |

## Completed Plans

| Plan | Completed | Description |
|------|-----------|-------------|
| [Scripts Migration](/_archive/scripts-migration.md) | Done | Move 85 .mjs from root → `scripts/js/` |
| [Portals DB Sync](/_archive/portals-db-sync.md) | Done | Hybrid DB+YAML for portals configuration |
| [CV Pipeline](/architecture/cv-pipeline.md) | Done | Skills Portfolio → CV generation pipeline |
| [Education Portfolio](/_archive/education-portfolio.md) | Done | Education module in skills portfolio |
| [Suite Skills Portfolio](/_archive/suite-skills-portfolio.md) | Done | Full skills portfolio implementation |

## Archived Plans (historical context)

| Plan | Date | Description |
|------|------|-------------|
| [Action Django](/_archive/action-django.md) | 2026-07 | Initial Django backend plan |
| [Action FastAPI](/_archive/action-fastapi.md) | 2026-07 | FastAPI alternative (superseded by Django) |
| [Action France Jobboards](/_archive/action-france-jobboards.md) | 2026-07 | France job discovery module plan |
| [Action Skills Portfolio](/_archive/action-skills-portfolio.md) | 2026-07 | Initial skills portfolio plan |
| [Analyse Projet](/_archive/analyse-projet.md) | 2026-07 | Deep analysis of career-ops v1.19.0 |

## How Plans Are Organized

- **Active plans** live at `docs/plans/` root — these are being worked on
- **Completed plans** live at `docs/plans/_archive/` — kept for historical reference
- **Architecture decisions** are recorded inline in the relevant plan
- Plans that become obsolete are moved to `_archive/` with a completion note
