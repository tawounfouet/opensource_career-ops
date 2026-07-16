# career-ops Django backend

This is the incremental Django backend described in `../docs/plans/_archive/action-django.md`.
It is intentionally file-first: `cv.md`, `config/profile.yml`, `portals.yml`,
`data/pipeline.md`, and `data/applications.md` remain the source of truth while
Django adds API, admin, ORM indexing, and management commands.

## Setup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python manage.py migrate
python manage.py runserver 8000
```

Set `CAREER_OPS_ROOT=/path/to/career-ops` if the backend is run outside this
repository layout.

## Implemented API foundation

- `GET /api/pipeline`
- `GET/POST /api/cv`
- `GET /api/cv-pdf`
- `GET/POST /api/profile`
- `GET/POST /api/portals`
- `POST /api/portals/verify`
- `POST /api/status`
- `POST /api/tracker/delete`
- `GET /api/doctor`
- `GET /api/version`
- `GET /api/whats-new`
- `GET /api/clis`
- `POST /api/run`
- `POST /api/runs/save`

## Management commands

- `python manage.py doctor --json`
- `python manage.py scan_portals`
- `python manage.py verify_pipeline`
- `python manage.py merge_tracker`
- `python manage.py normalize_statuses`
- `python manage.py dedup_tracker`
- `python manage.py update_system check`
- `python manage.py import_tracker`

## France Job Discovery (`apps.discovery`)

Deterministic, LLM-free evening collector for the French job market
(`../docs/plans/_archive/action-france-jobboards.md`). It collects recent offers from
configured sources, normalizes and deduplicates them, scores each posting with
an explainable rule set, and prepares a ranked morning short-list. **No
application is ever submitted** — the user reviews the digest and optionally
exports an offer into `data/pipeline.md` for evaluation via `modes/fr/offre.md`.

### Setup + one run

```bash
python manage.py migrate
python manage.py seed_discovery                       # France sources + default profile
# Add ATS boards to activate a connector, e.g. in Django admin or a shell:
#   JobSource(slug=greenhouse).config = {"boards": ["stripe", "figma"]}
python manage.py discover_jobs --profile default --market france
python manage.py export_daily_jobs --profile default  # print today's short-list
```

- `discover_jobs` — collect → normalize → dedup → rank → build today's digest (JSON summary).
- `rank_daily_jobs` — re-rank the latest run + rebuild the digest after editing a profile (no re-fetch).
- `export_daily_jobs [--evaluate]` — print the digest; `--evaluate` pushes items marked `evaluate` to `data/pipeline.md`.
- `seed_discovery` — idempotent catalogue of France sources + a `default` profile.

### Connectors (V1)

All plan-recommended connectors are implemented and offline-testable (inject a
`fetch` to stub the network). Every French jobboard ships **disabled / opt-in**
to respect each platform's TOS; enable it once you've configured access.

| Connector | Source | Strategy | Default | Activation |
|-----------|--------|----------|---------|------------|
| `greenhouse` / `lever` / `ashby` | ATS boards | `ats_api` | enabled | add board tokens/slugs to `config` |
| `apec` | APEC | `api` (public webservice) | opt-in | set `enabled=True` |
| `france_travail` | France Travail | `api` (OAuth) | opt-in | set `config.access_token`, `enabled=True` |
| `wttj` | Welcome to the Jungle | `api` (Algolia) | opt-in | set `config.app_id`/`api_key`, `enabled=True` |
| `hellowork` | HelloWork | `html_public` (JSON-LD) | opt-in | set `enabled=True` (strict rate limit) |
| `linkedin_manual` | LinkedIn | `manual_import` | opt-in | paste offers into `config.items`/`config.urls` |
| `indeed_manual` | Indeed | `manual_import` | opt-in | paste offers into `config.items`/`config.urls` |
| `fake` | fixtures | — | test-only | inline `config.jobs` |

LinkedIn and Indeed are **never** auto-scraped — they only read offers the user
pastes/exports (`config.items` = full dicts, `config.urls` = bare URLs).

### API

- `GET /api/discovery/sources`
- `GET/POST /api/discovery/profile`
- `POST /api/discovery/run`
- `GET /api/discovery/runs`
- `GET /api/discovery/digest/today`
- `POST /api/discovery/items/{id}/decision` — `pending|evaluate|skip|blacklist_company|save_for_later|already_applied`
- `POST /api/discovery/items/{id}/export-pipeline`

### Nightly scheduling (V1 = cron)

```cron
0 22 * * * cd /path/to/career-ops && backend/.venv/bin/python backend/manage.py discover_jobs --profile default
```
