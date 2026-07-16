# Architecture — career-ops

A complete map of how career-ops is built, from principles to deployment. For the precise system/user file boundary, see [DATA_CONTRACT.md](../../DATA_CONTRACT.md).

---

## Principles

Career-ops is built on three commitments:

- **Local-first.** Everything runs on your machine against your files. No account, no server for the core tool.
- **AI-agnostic.** Logic lives in Markdown prompt files (`modes/`), executed by whatever AI coding CLI you use. No single model is hardcoded.
- **Human-in-the-loop.** The tool prepares and evaluates; the human reviews and clicks. It never submits applications autonomously.

## Canonical source of truth

**Files are canonical, databases are derived.** The human-readable, git-diffable files (`data/applications.md`, `reports/`, `data/pipeline.md`, `cv.md`, `config/profile.yml`) are the permanent source of truth. SQLite exists only as a derived index for fast queries and will never become a primary store. The web UI, Go dashboard, community plugins, and CLI scripts all read the same files.

---

## High-level architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                              │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  AI CLI       │  │  Next.js Web │  │  Go TUI      │             │
│  │  (Claude,     │  │  UI          │  │  Dashboard   │             │
│  │   Codex,      │  │  (React 19)  │  │  (optional)  │             │
│  │   OpenCode)   │  │              │  │              │             │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘             │
│         │                  │                                        │
│         │ prompts          │ HTTP/JSON                              │
│         ▼                  ▼                                        │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │  modes/*.md  │  │  Django API  │                                │
│  │  (the "brain")│  │  (REST)      │                                │
│  └──────────────┘  └──────┬───────┘                                │
│                           │                                         │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                     BACKEND SERVICES                                │
│                           │                                         │
│  ┌────────────────────────┼────────────────────────────────────┐   │
│  │                   Django 5.x                                │   │
│  │                                                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐  │   │
│  │  │ tracker │ │ portals │ │   cv    │ │ skills_portfolio │  │   │
│  │  │ (DB     │ │ (YAML↔  │ │ (CV     │ │ (competencies,  │  │   │
│  │  │  mirror)│ │  DB)    │ │  CRUD)  │ │  LLM extraction,│  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ │  education)     │  │   │
│  │                                       └─────────────────┘  │   │
│  │  ┌─────────────┐ ┌──────────┐ ┌──────────────────────┐   │   │
│  │  │  discovery  │ │  runner  │ │       core            │   │   │
│  │  │  (France    │ │ (script  │ │ (doctor, version,     │   │   │
│  │  │   job scan) │ │  logs)   │ │  followups, apply)    │   │   │
│  │  └─────────────┘ └──────────┘ └──────────────────────┘   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   CLI Scripts                             │   │
│  │                                                           │   │
│  │  scripts/js/ (85 .mjs)    scripts/python/ (10 packages)  │   │
│  │  ─────────────────────    ────────────────────────────    │   │
│  │  • tracker (18)           • tracker (14)                   │   │
│  │  • scanner (5)            • scanner (2)                    │   │
│  │  • evaluation (7)         • evaluation (1)                 │   │
│  │  • cv (9)                 • cv (10)                        │   │
│  │  • plugins (5)            • plugins (6)                    │   │
│  │  • admin (10)             • admin (8)                      │   │
│  │  • reply (3)              • reply (3)                      │   │
│  │  • other (18)             • other (16)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## The three tiers

career-ops runs in three configurations, from simplest to full:

### Tier 1 — CLI only (no server)

```
AI CLI  ──►  modes/*.md  ──►  scripts/js/*.mjs  ──►  data/ + reports/
```

The original architecture. The AI CLI reads prompt files, executes scripts, reads/writes markdown files directly. Zero infrastructure required.

### Tier 2 — Web UI + Django

```
Browser  ──►  Next.js (port 3000)  ──►  Django (port 8000)  ──►  SQLite + files
```

Adds a web interface. Django provides a REST API over the same files the CLI reads. SQLite is a **derived index** for fast queries — never canonical.

### Tier 3 — Full stack with Docker

```
Browser  ──►  docker-compose  ──►  Next.js + Django + SQLite
```

Containerized setup via the `cops` bash wrapper. Same architecture, just orchestrated.

---

## Django backend — 8 apps

### `core` — Shared infrastructure

| Endpoint | Purpose |
|----------|---------|
| `GET /api/doctor` | System health check (prerequisites, plugins, config) |
| `GET /api/version` | Version + channel + SHA |
| `GET /api/whats-new` | Changelog excerpt |
| `GET /api/clis` | Available AI CLIs on this machine |
| `GET /api/usage` | Token usage (5h + 7d windows) |
| `GET /api/report/shape` | Report data shape for frontend |
| `GET/POST /api/memory` | Persistent memory (read/write) |
| `GET /api/followups` | Follow-up cadence |
| `POST /api/followups/log` | Log a follow-up |
| `POST /api/run` | Run evaluation/PDF/research (streaming NDJSON) |
| `POST /api/runs/save` | Save a run record |

### `tracker` — Application tracker

| Endpoint | Purpose |
|----------|---------|
| `GET /api/pipeline` | Pipeline summary (inbox + tracker) |
| `POST /api/status` | Update tracker row status (atomic, locked) |
| `POST /api/tracker/delete` | Delete tracker row |

Models: `Application` (mirrors `data/applications.md`), `PipelineJob`, `ScanHistory`.

### `portals` — Portal configuration

| Endpoint | Purpose |
|----------|---------|
| `GET/POST /api/portals` | Portal config (DB-backed, YAML-synced) |
| `POST /api/portals/verify` | Verify portal liveness |
| `GET/PATCH /api/profile` | Read/update `config/profile.yml` |
| `GET/POST/DELETE /api/profile/variants/{name}` | Profile variants |

Models: `Portal`, `SearchQuery`, `TitleFilter` (singleton), `LocationFilter` (singleton), `JobBoard`.

**Hybrid DB+YAML sync:** `import_yaml_to_db()` and `export_db_to_yaml()` keep the database and `config/portals.yml` in sync. DB wins on conflicts. CLI scripts read the YAML; the web API reads the DB.

### `cv` — CV management

| Endpoint | Purpose |
|----------|---------|
| `GET/POST /api/cv` | Read/write `cv.md` |
| `GET /api/cv-pdf?company=X` | Download tailored CV PDF |

Models: `CvDocument`, `CvVersion` (version history).

### `skills_portfolio` — Competency framework

The largest app — 44 API routes, 7 models, 8 service modules.

**Models:**
- `SkillExperience` — source experiences (work, personal, academic)
- `SkillEvidence` — proof items (projects, articles, metrics)
- `SkillCompetency` — evidenced capabilities with mastery levels
- `SkillDevelopmentAction` — learning plans for skill gaps
- `Education` — training, certifications, courses
- `EducationCompetency` — education-competency links
- `SkillExtractionRun` — LLM extraction audit trail

**Service modules:**

| Module | Purpose |
|--------|---------|
| `extraction.py` | LLM-assisted extraction from free text (competencies, experiences, education, profiles, portals) |
| `llm_client.py` | OpenAI-compatible LLM wrapper (configurable base URL, model, API key) |
| `matching.py` | Benchmarking competencies against target roles |
| `integration.py` | Deterministic (no-LLM) integration: validated competency export, skill gap computation |
| `exports.py` | Export to JSON, Markdown, CVData, and full CV Markdown |
| `prompts.py` | Prompt templates for all LLM operations |
| `validation.py` | Competency validation logic |

**Key endpoints:**
- CRUD: `/api/skills/experiences`, `/api/skills/competencies`, `/api/skills/evidence`, `/api/skills/educations`
- LLM-assisted: `/api/skills/llm/extract-from-experience`, `formalize`, `evaluate-mastery`, `benchmark`, `parse-jd`, `suggest-cv-bullets`, `suggest-interview-questions`
- Integration: `/api/skills/integration/validated`, `skill-gaps`, `discovery-keywords`
- Export: `/api/skills/export/json`, `markdown`, `cvdata`, `cv-markdown`

### `discovery` — France job discovery

Deterministic (V1, no LLM) job discovery engine focused on the French market.

**Models:**
- `JobSource` — scrape-able source definitions (10 connectors)
- `SearchProfile` — user search criteria (titles, keywords, location, salary, seniority)
- `DiscoveryRun` — scan run record
- `RawJobPosting` — raw captures from connectors
- `JobPosting` — normalized, deduplicated postings
- `JobRanking` — deterministic multi-factor scoring
- `DailyJobDigest` / `DailyJobDigestItem` — daily digest with user decisions

**Connectors:**

| Connector | Source |
|-----------|--------|
| `apec.py` | APEC France |
| `france_travail.py` | France Travail (Pôle Emploi) API |
| `hellowork.py` | HelloWork |
| `welcometothejungle.py` | Welcome to the Jungle |
| `ats_ashby.py` | Ashby ATS |
| `ats_greenhouse.py` | Greenhouse ATS |
| `ats_lever.py` | Lever ATS |
| `manual.py` | Manual import |
| `fake.py` | Test connector |

### `runner` — Script execution

| Endpoint | Purpose |
|----------|---------|
| `POST /api/run` | Execute a script with logging |

Models: `RunLog` (execution record), `RunEvent` (individual events).

### `accounts` — User management

Custom `User` model with career-specific fields: `target_roles`, `salary_min/max`, `spend_tier`, `preferred_cli`.

---

## Next.js frontend — 20 routes

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Home | Dashboard overview |
| `/pipeline` | Pipeline | Pending URLs inbox |
| `/pipeline/[id]` | Pipeline detail | Individual pipeline item |
| `/jobs` | Jobs | Job listings |
| `/jobs/[id]` | Job detail | Individual job |
| `/cv` | CV editor | Edit `cv.md` |
| `/profile` | Profile editor | Edit `config/profile.yml` |
| `/profile/list` | Profile list | Base + variant profiles |
| `/skills` | Skills overview | Portfolio dashboard |
| `/skills/list` | Skills list | All competencies |
| `/skills/experiences` | Experiences | Experience management |
| `/skills/education` | Education | Education management |
| `/portals` | Portals | Portal management |
| `/portals/list` | Portal list | All configured portals |
| `/explore` | Explore | Job discovery |
| `/discovery` | Discovery | France discovery dashboard |
| `/discovery/profile` | Search profile | Discovery search criteria |
| `/config` | Config | System configuration |
| `/analytics` | Analytics | Pipeline analytics |
| `/apply` | Apply | Application form filling |

### API proxy architecture

Next.js acts as a **proxy with fallback**:

1. **Tier 1:** If `CAREER_OPS_API_URL` is set, proxy to Django via HTTP
2. **Tier 2:** If Django is down, run `manage.py shell -c <inline-python>` directly
3. **Tier 3:** Return 503 with hint to start Django

This allows the web UI to work even without Django running as a server.

---

## CLI scripts — 85 JS + Python packages

### `scripts/js/` — 85 files

| Category | Count | Key scripts |
|----------|-------|-------------|
| Tracker & Pipeline | 18 | `tracker-parse.mjs`, `tracker-utils.mjs`, `merge-tracker.mjs`, `set-status.mjs`, `dedup-tracker.mjs` |
| Scanner & Discovery | 5 | `scan.mjs`, `scan-ats-full.mjs`, `check-liveness.mjs`, `verify-portals.mjs` |
| Evaluation & LLM | 7 | `gemini-eval.mjs`, `openai-eval.mjs`, `ollama-eval.mjs`, `openrouter-runner.mjs` |
| CV & PDF Generation | 9 | `generate-pdf.mjs`, `build-cv-html.mjs`, `build-cv-latex.mjs`, `cv-templates.mjs` |
| Follow-up & Reply | 5 | `followup-cadence.mjs`, `reply-watch.mjs`, `reply-matcher.mjs` |
| Analysis & Stats | 6 | `analyze-patterns.mjs`, `stats.mjs`, `upskill.mjs`, `salary-gap.mjs` |
| Plugins | 5 | `plugins.mjs`, `plugin-install.mjs`, `validate-plugin-registry.mjs` |
| Admin & System | 10 | `doctor.mjs`, `update-system.mjs`, `test-all.mjs`, `verify-pipeline.mjs` |
| Apply & Interview | 5 | `prepare-application.mjs`, `invite-match.mjs`, `match-star.mjs` |
| Other | 15 | `fingerprint-core.mjs`, `browser-extract.mjs`, `build-dashboard.mjs`, etc. |

### `scripts/python/` — 10 packages (in progress)

Python equivalents being ported from JS. See `docs/plans/python-migration.md` for the full migration plan.

### Shared modules (the 3 pillars)

| Module | Imported by | Purpose |
|--------|-------------|---------|
| `tracker-parse.mjs` | 14+ scripts | Header-aware column mapping for the tracker markdown table |
| `tracker-utils.mjs` | 6 scripts | Row rewrite, locking, atomic write, company normalization |
| `role-matcher.mjs` | 4 scripts | Fuzzy role-title matching for dedup/merge |

---

## The AI "brain" — modes/

`modes/*.md` are prompt files that define career-ops' behavior. The AI CLI reads these and follows their instructions.

### Core modes

| Mode | Purpose |
|------|---------|
| `_shared.md` | Scoring system, archetype detection, global rules (the "kernel") |
| `_profile.md` | User personalization overrides |
| `_custom.md` | Custom workflow rules |
| `oferta.md` | Job evaluation (7 blocks: A–G) |
| `auto-pipeline.md` | Auto-pipeline (evaluate + report + PDF + tracker) |
| `apply.md` | Application form filling |
| `scan.md` | Portal scanning |
| `batch.md` | Batch processing |
| `interview.md` | Interview preparation |
| `deep.md` | Company research |
| `contacto.md` | LinkedIn/outreach messaging |
| `email.md` | Application email drafting |
| `offer-prep.md` | Contract clause analysis |
| `patterns.md` | Rejection patterns analysis |
| `upskill.md` | Skill-gap analysis |

### Language variants — 17 markets

Arabic, Chinese (Simplified + Traditional), Danish, Dutch, French, German, Hindi, Indonesian, Italian, Japanese, Korean, Polish, Portuguese, Russian, Turkish, Ukrainian. Each provides localized evaluation, apply, and pipeline modes with market-specific vocabulary (e.g., German: `13. Monatsgehalt`, `Probezeit`; French: `CDI/CDD`, `convention collective SYNTEC`).

---

## Data flow

### Single evaluation

```
User pastes JD  ──►  Extract (Playwright/WebFetch)
                         │
                    Classify archetype
                         │
                    Evaluate (A–G blocks)
                    ├── A: Role summary
                    ├── B: CV match + gaps
                    ├── C: Level strategy
                    ├── D: Comp research (WebSearch)
                    ├── E: CV personalization plan
                    ├── F: Interview prep (STAR)
                    └── G: Posting legitimacy
                         │
                    Score (10 dimensions, 1–5)
                         │
                    ┌────┴────┐
                    ▼         ▼
              Report.md    PDF (ATS-optimized)
                    │
                    ▼
           data/applications.md (tracker)
```

### Batch processing

```
batch-input.tsv  ──►  batch-runner.sh  ──►  N × headless CLI workers
                                                │
                                           ┌────┴────┐
                                           ▼         ▼
                                      Report.md    PDF
                                           │
                                           ▼
                                   Tracker TSV line
                                           │
                                   merge-tracker.mjs
                                           │
                                   data/applications.md
```

### Discovery flow (France)

```
SearchProfile  ──►  scheduler.py  ──►  10 connectors (APEC, FT, HelloWork, ...)
                                              │
                                         RawJobPosting
                                              │
                                         normalize.py + dedup.py
                                              │
                                         JobPosting (canonical)
                                              │
                                         scoring.py (deterministic)
                                              │
                                         JobRanking
                                              │
                                         DailyJobDigest
                                              │
                                    User decides (accept/reject)
                                              │
                                         exporters.py  ──►  data/pipeline.md
```

### Skills portfolio → CV pipeline

```
Experiences + Evidence  ──►  SkillsCompetency (validated)
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                    skill-gaps         discovery-keywords
                    (missing)          (for scan.mjs)
                         │
                    development-plan
                    (LLM-assisted)
                         │
                    exports.py  ──►  CVData JSON  ──►  cv.md  ──►  PDF
```

---

## State management — what lives where

| Storage | Format | Canonical? | Purpose |
|---------|--------|------------|---------|
| `cv.md` | Markdown | **Yes** | User's CV — single source of truth |
| `config/profile.yml` | YAML | **Yes** | Candidate identity, targeting, compensation |
| `config/profiles/*.yml` | YAML | Override | Profile variants (role-specific overlays) |
| `config/portals.yml` | YAML | **Yes** | Portal/company config, title/location filters |
| `data/applications.md` | Markdown table | **Yes** | Application tracker — permanent record |
| `data/pipeline.md` | Markdown checklist | **Yes** | Pending job URLs to evaluate |
| `reports/*.md` | Markdown | **Yes** | Full A–G evaluation per offer |
| `modes/_profile.md` | Markdown | Personal | Archetype mapping, scoring preferences |
| `modes/_custom.md` | Markdown | Personal | Custom workflow rules |
| `voice-dna.md` | Markdown | Personal | Voice/style reference |
| `article-digest.md` | Markdown | Personal | Proof points for CV |
| `output/*.pdf` | PDF | Generated | ATS-optimized tailored resumes |
| `batch/tracker-additions/*.tsv` | TSV | Transient | Batch additions (merged then deleted) |
| `SQLite (db.sqlite3)` | SQLite | **Derived** | Fast query index over markdown data |

---

## Integration patterns

### CLI ↔ Django

- **`run_node_script()`** — Django spawns Node scripts via `subprocess.run(["node", script, ...])`
- **Direct file I/O** — Django reads/writes the same files the CLI uses (`cv.md`, `portals.yml`, `applications.md`)
- **`root_path()`** in `core/paths.py` resolves paths relative to `CAREER_OPS_ROOT`

### Next.js ↔ Django

- **HTTP proxy** — When `CAREER_OPS_API_URL` is set, Next.js forwards requests to Django
- **`manage.py shell` fallback** — When Django server is down, Next.js runs inline Python via subprocess
- **CORS** — Django allows `http://localhost:3000`

### YAML ↔ DB sync (portals)

- **`import_yaml_to_db()`** — reads `config/portals.yml`, updates Django DB
- **`export_db_to_yaml()`** — writes DB state back to `config/portals.yml`
- DB wins on conflicts. CLI scripts read YAML; web API reads DB.

---

## File naming conventions

- Reports: `{###}-{company-slug}-{YYYY-MM-DD}.md` (3-digit zero-padded)
- PDFs: `cv-candidate-{company-slug}-{YYYY-MM-DD}.pdf`
- Tracker TSVs: `batch/tracker-additions/{num}-{company-slug}.tsv`
- Profile variants: `config/profiles/{variant-name}.yml`

---

## Testing

| Location | Type | Count | Coverage |
|----------|------|-------|----------|
| `tests/providers/*.test.mjs` | JS | 39 | One per ATS/board provider |
| `scripts/js/*.test.mjs` | JS | 5 | Co-located: reposts, quality, invite, cadence, matcher |
| `scripts/python/tests/*.py` | Python | 25 | Foundations, tracker, admin, CV, plugins, scanner |
| `backend/tests/*.py` | pytest-django | 8 | API, discovery, skills, connectors, LLM services |
| `evals/golden/*.json` | LLM golden | 10 | Evaluation accuracy against known JDs |
| `scripts/js/test-all.mjs` | Master harness | 1 | 63+ check sections, runs in CI |

**CI/CD:** GitHub Actions runs `test-all.mjs` on every PR. CodeQL for security. CodeRabbit for review. Renovate for dependency updates.

---

## Quality gates

- `test-all.mjs` — the full suite (500+ checks)
- `updater-migration-tests.mjs` — system/user boundary enforcement
- `verify-pipeline.mjs` — tracker health check
- `validate-plugin-registry.mjs` — plugin shape validation
- `verify-portals.mjs` — ATS slug verification
- CI: status checks must pass before merge. No direct pushes to `main`.

---

## Project structure

```
career-ops/
├── backend/                    # Django 5.x (Python 3.12+)
│   ├── apps/                   # 8 Django apps
│   │   ├── core/               # Shared infrastructure
│   │   ├── tracker/            # Application tracker
│   │   ├── portals/            # Portal config (YAML↔DB)
│   │   ├── cv/                 # CV management
│   │   ├── skills_portfolio/   # Competency framework
│   │   ├── discovery/          # France job discovery
│   │   ├── runner/             # Script execution
│   │   └── accounts/           # User management
│   ├── config/                 # Django settings
│   └── db.sqlite3              # Derived index (not canonical)
│
├── web/                        # Next.js 16 (React 19)
│   └── src/
│       ├── app/                # App Router (20 routes + 35 API routes)
│       ├── components/         # 37 component directories
│       └── lib/                # 18 library modules
│
├── scripts/
│   ├── js/                     # 85 CLI scripts (.mjs)
│   └── python/                 # Python equivalents (in progress)
│
├── modes/                      # AI prompt files (the "brain")
│   ├── _shared.md              # Core scoring system
│   ├── _profile.md             # User personalization
│   ├── oferta.md               # Job evaluation
│   ├── apply.md                # Application form filling
│   └── {ar,de,fr,ja,...}/     # 17 language variants
│
├── config/                     # User configuration
│   ├── profile.yml             # Candidate profile
│   ├── profiles/               # Profile variants
│   └── portals.yml             # Portal/company config
│
├── data/                       # User data (canonical)
│   ├── applications.md         # Application tracker
│   ├── pipeline.md             # Pending URLs
│   └── scan-history.tsv        # URL dedup history
│
├── templates/                  # CV/cover-letter templates + config templates
├── reports/                    # Evaluation reports
├── output/                     # Generated PDFs (gitignored)
├── providers/                  # 61 ATS/board scanner modules
├── plugins/                    # Plugin engine + bundled plugins
├── packages/cv-generator/      # Python CV generator
├── dashboard/                  # Go TUI (optional)
├── evals/                      # Golden evaluation fixtures
├── docs/                       # Documentation
├── modes/                      # AI prompt files
├── scripts/                    # CLI scripts (JS + Python)
├── batch/                      # Batch processing state
├── archives/                   # Session archives
└── .github/                    # CI/CD (Actions, Dependabot)
```

---

## Where to start reading

| Want to... | Read this |
|------------|-----------|
| Understand the boundary | `DATA_CONTRACT.md` |
| Understand scoring | `modes/_shared.md` + `modes/oferta.md` |
| Add a job source | An existing module in `providers/` (mirror it) |
| Understand the updater | `scripts/js/update-system.mjs` |
| Add a Django endpoint | `backend/apps/{app}/views.py` + `urls.py` |
| Add a web page | `web/src/app/{route}/page.tsx` |
| Understand the skills portfolio | `backend/apps/skills_portfolio/services/` |
| Port a script to Python | `docs/plans/python-migration.md` |
| Understand portal sync | `backend/apps/portals/services.py` |
