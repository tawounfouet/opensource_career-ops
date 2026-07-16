# Plan: Migration des scripts JS → Python

## Contexte

Le dossier `scripts/js/` contient 85 fichiers `.mjs` (37 624 lignes) qui constituent le noyau CLI de career-ops. L'objectif est de créer des équivalents Python dans `scripts/python/` pour :

1. **Éliminer la dépendance Node.js** pour les scripts non-web
2. **Unifier le stack** — le backend Django est déjà en Python 3.12+
3. **Meilleure intégration** avec le backend Django (imports directs, pas de `child_process`)
4. **Tests natifs** via `pytest` (déjà en place dans `backend/`)

## Architecture existante

### Fichiers partagés critiques (les 3 piliers)

Tous les scripts CLI reposent sur 3 modules partagés :

| Module | Lignes | Importé par | Rôle |
|--------|--------|-------------|------|
| `tracker-parse.mjs` | 177 | 14+ scripts | Mapping colonnes header-aware du tracker markdown |
| `tracker-utils.mjs` | 404 | 6 scripts | Row-rewrite, locking, atomic write, company normalization |
| `role-matcher.mjs` | ~150 | 4 scripts | Fuzzy role-title matching pour dedup/merge |

### Mapping des colonnes du tracker

Le tracker `data/applications.md` est un tableau markdown. Le header est personnalisable (ex: colonne Location insérée). `tracker-parse` mappe les headers par nom canonique, pas par position fixe.

```javascript
// tracker-parse.mjs — LEGACY_COLMAP (fallback)
{ num: 1, date: 2, company: 3, role: 4, score: 5, status: 6, pdf: 7, report: 8, notes: 9 }
```

Les alias de headers sont dans `scripts/js/tracker-aliases.json` (table partagée avec le frontend web).

### Verrouillage concurrentiel

`tracker-utils.mjs` implémente un verrou fichier-based :
- Lockfile : `{tracker}.lock` avec PID + UUID
- Timeout : 30s, stale après 4h
- Write atomique : tmp → rename

### Types de données en entrée/sortie

| Format | Usage |
|--------|-------|
| Markdown table (`data/applications.md`) | Tracker principal |
| TSV (`batch/tracker-additions/*.tsv`) | Entrées batch à merger |
| YAML (`config/portals.yml`, `config/profile.yml`, `templates/states.yml`) | Config |
| JSON (stdout) | Sortie structurée pour le frontend |
| Markdown (`reports/*.md`) | Rapports d'évaluation |
| HTML (`templates/cv-template.html`) | Templates CV |
| LaTeX (`templates/cv-template.tex`) | Templates CV LaTeX |

---

## Structure cible

```
scripts/python/
├── __init__.py
├── pyproject.toml              # dépendances Python dédiées
├── README.md                   # usage et examples
│
├── tracker/                    # === TRACKER (18 scripts) ===
│   ├── __init__.py
│   ├── parse.py                # ← tracker-parse.mjs (177 lignes)
│   ├── utils.py                # ← tracker-utils.mjs (404 lignes)
│   ├── links.py                # ← tracker-links.mjs
│   ├── role_matcher.py         # ← role-matcher.mjs
│   ├── set_status.py           # ← set-status.mjs
│   ├── merge_tracker.py        # ← merge-tracker.mjs (709 lignes)
│   ├── dedup_tracker.py        # ← dedup-tracker.mjs
│   ├── normalize_statuses.py   # ← normalize-statuses.mjs
│   ├── verify_pipeline.py      # ← verify-pipeline.mjs
│   ├── find.py                 # ← find.mjs
│   ├── reserve_report_num.py   # ← reserve-report-num.mjs
│   ├── add_entry.py            # ← add-entry.mjs
│   ├── followup_cadence.py     # ← followup-cadence.mjs
│   ├── followup_seed.py        # ← followup-seed.mjs
│   ├── invite_match.py         # ← invite-match.mjs
│   ├── process_quality.py      # ← process-quality.mjs
│   ├── detect_reposts.py       # ← detect-reposts.mjs
│   └── reconcile_pipeline.py   # ← reconcile-pipeline.mjs
│
├── scanner/                    # === SCANNER (4 scripts) ===
│   ├── __init__.py
│   ├── scan.py                 # ← scan.mjs (1786 lignes)
│   ├── scan_ats_full.py        # ← scan-ats-full.mjs (614 lignes)
│   ├── check_liveness.py       # ← check-liveness.mjs
│   └── classify_tier.py        # ← classify-tier.mjs
│
├── evaluation/                 # === EVALUATION (6 scripts) ===
│   ├── __init__.py
│   ├── gemini_eval.py          # ← gemini-eval.mjs
│   ├── ollama_eval.py          # ← ollama-eval.mjs
│   ├── openai_eval.py          # ← openai-eval.mjs
│   ├── eval_golden.py          # ← eval-golden.mjs
│   ├── jd_skill_gap.py         # ← jd-skill-gap.mjs
│   └── openai_tailor.py        # ← openai-tailor.mjs
│
├── pipeline/                   # === PIPELINE (5 scripts) ===
│   ├── __init__.py
│   ├── liveness_core.py        # ← liveness-core.mjs
│   ├── liveness_api.py         # ← liveness-api.mjs
│   ├── liveness_browser.py     # ← liveness-browser.mjs
│   ├── browser_extract.py      # ← browser-extract.mjs
│   └── agent_inbox.py          # ← agent-inbox.mjs
│
├── cv/                         # === CV (9 scripts) ===
│   ├── __init__.py
│   ├── templates.py            # ← cv-templates.mjs
│   ├── build_html.py           # ← build-cv-html.mjs (431 lignes)
│   ├── build_latex.py          # ← build-cv-latex.mjs
│   ├── generate_pdf.py         # ← generate-pdf.mjs (515 lignes)
│   ├── generate_latex.py       # ← generate-latex.mjs
│   ├── generate_cover_letter.py # ← generate-cover-letter.mjs
│   ├── extract_latex_content.py # ← extract-latex-content.mjs
│   ├── patch_latex_content.py  # ← patch-latex-content.mjs
│   └── verify_cv_facts.py      # ← verify-cv-facts.mjs
│
├── interview/                  # === INTERVIEW (1 script) ===
│   ├── __init__.py
│   └── match_star.py           # ← match-star.mjs
│
├── plugins/                    # === PLUGINS (4 scripts) ===
│   ├── __init__.py
│   ├── engine.py               # ← plugins/_engine.mjs
│   ├── cli.py                  # ← plugins.mjs
│   ├── audit.py                # ← plugin-audit.mjs
│   ├── install.py              # ← plugin-install.mjs
│   └── validate_registry.py    # ← validate-plugin-registry.mjs
│
├── admin/                      # === ADMIN (10 scripts) ===
│   ├── __init__.py
│   ├── doctor.py               # ← doctor.mjs (430 lignes)
│   ├── update_system.py        # ← update-system.mjs (1108 lignes)
│   ├── test_all.py             # ← test-all.mjs (8091 lignes)
│   ├── validate_portals.py     # ← validate-portals.mjs
│   ├── verify_portals.py       # ← verify-portals.mjs
│   ├── cv_sync_check.py        # ← cv-sync-check.mjs
│   ├── validate_paths.py       # ← validate-system-paths-coverage.mjs
│   ├── manifesto.py            # ← manifesto.mjs
│   ├── upskill.py              # ← upskill.mjs (663 lignes)
│   └── stats.py                # ← stats.mjs (438 lignes)
│
├── export/                     # === EXPORT (1 script) ===
│   ├── __init__.py
│   └── build_dashboard.py      # ← build-dashboard.mjs
│
├── reply/                      # === REPLY (3 scripts) ===
│   ├── __init__.py
│   ├── reply_matcher.py        # ← reply-matcher.mjs
│   ├── reply_watch.py          # ← reply-watch.mjs
│   └── paste_reply.py          # ← paste-reply.mjs
│
├── salary/                     # === SALARY (1 script) ===
│   ├── __init__.py
│   └── salary_gap.py           # ← salary-gap.mjs
│
├── other/                      # === OTHER (7 scripts) ===
│   ├── __init__.py
│   ├── application_answers.py  # ← application-answers.mjs
│   ├── fingerprint_core.py     # ← fingerprint-core.mjs
│   ├── prepare_application.py  # ← prepare-application.mjs
│   ├── img_to_pdf.py           # ← img-to-pdf.mjs
│   ├── openrouter_runner.py    # ← openrouter-runner.mjs
│   ├── funnel_velocity.py      # ← funnel-velocity.mjs
│   └── assessment_log.py       # ← assessment-log.mjs
│
└── tests/                      # === TESTS (12 fichiers) ===
    ├── conftest.py
    ├── test_set_status.py
    ├── test_tracker_columns.py
    ├── test_followup_seed.py
    ├── test_followup_cadence.py
    ├── test_invite_match.py
    ├── test_detect_reposts.py
    ├── test_process_quality.py
    ├── test_reply_matcher.py
    ├── test_paste_reply.py
    ├── test_agent_inbox.py
    ├── test_salary_filter.py
    ├── test_trust_validator.py
    └── test_updater_migration.py
```

---

## Mapping JS → Python : correspondances par catégorie

### Tracker (18 scripts → 18 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `tracker-parse.mjs` | `tracker/parse.py` | 177 | Moyenne | Header-aware column mapping. Utilise `tracker-aliases.json`. **Priorité haute** — importé par 14+ scripts. |
| `tracker-utils.mjs` | `tracker/utils.py` | 404 | Élevée | Row-rewrite, locking (flock), atomic write (tmp+rename), company normalization. **Priorité haute** — importé par 6 scripts. |
| `tracker-links.mjs` | `tracker/links.py` | ~50 | Faible | Normalisation des liens report root-relative vs dir-relative. |
| `role-matcher.mjs` | `tracker/role_matcher.py` | ~150 | Moyenne | Fuzzy matching de titres de postes (Levenshtein + tokens). Importé par 4 scripts. |
| `set-status.mjs` | `tracker/set_status.py` | ~200 | Moyenne | CLI canonical pour update status/note. Lock + validation states.yml. |
| `merge-tracker.mjs` | `tracker/merge_tracker.py` | 709 | Élevée | Merge TSV → applications.md. Column swap, Via field, dedup guard, link normalization. |
| `dedup-tracker.mjs` | `tracker/dedup_tracker.py` | 395 | Moyenne | Suppression doublons (company+role fuzzy). |
| `normalize-statuses.mjs` | `tracker/normalize_statuses.py` | ~100 | Faible | Map non-canonical → canonical statuses via states.yml. |
| `verify-pipeline.mjs` | `tracker/verify_pipeline.py` | 423 | Moyenne | Health check complet (statuses, dupes, scores, links, sentinels). |
| `find.mjs` | `tracker/find.py` | ~150 | Faible | Résolution query → identity (company/role/number). |
| `reserve-report-num.mjs` | `tracker/reserve_report_num.py` | ~80 | Faible | Atomic report number reservation (lockfile). |
| `add-entry.mjs` | `tracker/add_entry.py` | ~120 | Faible | Dedup + insertion dans cv.md / article-digest.md. |
| `followup-cadence.mjs` | `tracker/followup_cadence.py` | 452 | Moyenne | Cadence parser, overdue flagger. Importe tracker-parse. |
| `followup-seed.mjs` | `tracker/followup_seed.py` | 648 | Moyenne | Seed follow-ups.md avec date pinned au status Applied. |
| `invite-match.mjs` | `tracker/invite_match.py` | 464 | Moyenne | Fuzzy-match email interview-invite → entries tracker. |
| `process-quality.mjs` | `tracker/process_quality.py` | ~150 | Faible | Aggrégateur friction recruiting (tags `[process-friction]`). |
| `detect-reposts.mjs` | `tracker/detect_reposts.py` | ~200 | Moyenne | Flag roles repostés 2+ fois en 90 jours. Utilise fingerprint-core. |
| `reconcile-pipeline.mjs` | `tracker/reconcile_pipeline.py` | ~100 | Faible | Sync pipeline.md "Pendientes" avec batch-state.tsv. |

### Scanner (4 scripts → 4 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `scan.mjs` | `scanner/scan.py` | 1786 | Très élevée | Scanner principal. Plugin provider layer, rate limiting, dedup, portals.yml parsing. **Le plus gros script.** |
| `scan-ats-full.mjs` | `scanner/scan_ats_full.py` | 614 | Élevée | Reverse ATS discovery — walk public job-board-aggregator dataset. |
| `check-liveness.mjs` | `scanner/check_liveness.py` | ~200 | Moyenne | Playwright liveness checker (ATS API + browser fallback). |
| `classify-tier.mjs` | `scanner/classify_tier.py` | ~80 | Faible | Seniority-tier classifier (intern/entry/mid/senior). |

### Evaluation (6 scripts → 6 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `gemini-eval.mjs` | `evaluation/gemini_eval.py` | 439 | Élevée | Gemini-powered evaluator (free tier). Appels HTTP directs à l'API. |
| `ollama-eval.mjs` | `evaluation/ollama_eval.py` | ~200 | Moyenne | Ollama local evaluator. HTTP vers localhost. |
| `openai-eval.mjs` | `evaluation/openai_eval.py` | 393 | Élevée | OpenAI-compatible evaluator. JSON schema, retries. |
| `eval-golden.mjs` | `evaluation/eval_golden.py` | ~150 | Moyenne | Golden-set eval harness. |
| `jd-skill-gap.mjs` | `evaluation/jd_skill_gap.py` | ~250 | Moyenne | Zero-LLM skill-gap checker (regex/keyword). |
| `openai-tailor.mjs` | `evaluation/openai_tailor.py` | ~300 | Élevée | OpenAI CV tailoring (headless companion). |

### Pipeline (5 scripts → 5 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `liveness-core.mjs` | `pipeline/liveness_core.py` | ~100 | Faible | Shared expired/listing regex classification. |
| `liveness-api.mjs` | `pipeline/liveness_api.py` | ~150 | Faible | Zero-token ATS-API liveness (Greenhouse/Lever/Ashby). |
| `liveness-browser.mjs` | `pipeline/liveness_browser.py` | ~100 | Faible | Playwright liveness for single URL. |
| `browser-extract.mjs` | `pipeline/browser_extract.py` | ~200 | Moyenne | Headless Playwright reader. |
| `agent-inbox.mjs` | `pipeline/agent_inbox.py` | ~100 | Faible | Append-only request queue. |

### CV (9 scripts → 9 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `cv-templates.mjs` | `cv/templates.py` | ~150 | Moyenne | Template discovery/resolution. Importé par 5 scripts. |
| `build-cv-html.mjs` | `cv/build_html.py` | 431 | Élevée | Deterministic HTML CV renderer. Template substitution. |
| `build-cv-latex.mjs` | `cv/build_latex.py` | ~200 | Moyenne | LaTeX CV renderer. |
| `generate-pdf.mjs` | `cv/generate_pdf.py` | 515 | Élevée | HTML → PDF via Playwright Chromium. |
| `generate-latex.mjs` | `cv/generate_latex.py` | ~150 | Moyenne | .tex → PDF (tectonic/pdflatex subprocess). |
| `generate-cover-letter.mjs` | `cv/generate_cover_letter.py` | ~200 | Moyenne | Cover letter → PDF via Playwright. |
| `extract-latex-content.mjs` | `cv/extract_latex_content.py` | ~100 | Faible | Detect LaTeX CV family, list editable slots. |
| `patch-latex-content.mjs` | `cv/patch_latex_content.py` | ~100 | Faible | Apply prose patches to user-owned LaTeX CV. |
| `verify-cv-facts.mjs` | `cv/verify_cv_facts.py` | ~100 | Faible | Guard against invented metrics. |

### Interview (1 script → 1 module)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `match-star.mjs` | `interview/match_star.py` | ~200 | Moyenne | Zero-LLM ATS behavioural question → STAR story matcher. |

### Plugins (4 scripts → 5 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `plugins/_engine.mjs` | `plugins/engine.py` | ~300 | Élevée | Plugin discovery, lifecycle, hook dispatch. Core du système plugins. |
| `plugins.mjs` | `plugins/cli.py` | ~150 | Moyenne | CLI host for non-provider plugin hooks. |
| `plugin-audit.mjs` | `plugins/audit.py` | ~100 | Faible | Static safety scan. |
| `plugin-install.mjs` | `plugins/install.py` | ~150 | Moyenne | Clone/scaffold/validate community plugins. |
| `validate-plugin-registry.mjs` | `plugins/validate_registry.py` | ~100 | Faible | Shape gate for registry. |

### Admin (10 scripts → 10 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `doctor.mjs` | `admin/doctor.py` | 430 | Élevée | Setup validation, prerequisite checklist, auto-copy templates. |
| `update-system.mjs` | `admin/update_system.py` | 1108 | Très élevée | Safe auto-updater — system layer only. Le 2e plus gros script. |
| `test-all.mjs` | `admin/test_all.py` | 8091 | Très élevée | Comprehensive test suite (63+ checks). Peut rester en JS comme test runner. |
| `validate-portals.mjs` | `admin/validate_portals.py` | ~150 | Faible | Schema validator for portals.yml. |
| `verify-portals.mjs` | `admin/verify_portals.py` | 571 | Moyenne | ATS slug validator — probes live endpoints. |
| `cv-sync-check.mjs` | `admin/cv_sync_check.py` | ~100 | Faible | Validates career-ops setup consistency. |
| `validate-system-paths-coverage.mjs` | `admin/validate_paths.py` | ~100 | Faible | Structural coverage check for updater. |
| `manifesto.mjs` | `admin/manifesto.py` | ~50 | Faible | Open manifesto signing page. |
| `upskill.mjs` | `admin/upskill.py` | 663 | Élevée | Aggregate skill-gap analyzer — weighted gap map. |
| `stats.mjs` | `admin/stats.py` | 438 | Élevée | Lifetime pipeline stats aggregator. |

### Export (1 script → 1 module)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `build-dashboard.mjs` | `export/build_dashboard.py` | ~100 | Faible | Cross-platform build for Go TUI dashboard. |

### Reply (3 scripts → 3 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `reply-matcher.mjs` | `reply/reply_matcher.py` | ~200 | Moyenne | Deterministic email → tracker matcher. |
| `reply-watch.mjs` | `reply/reply_watch.py` | ~250 | Moyenne | Classify employer replies + digest. |
| `paste-reply.mjs` | `reply/paste_reply.py` | ~100 | Faible | Manual input path for reply-watch. |

### Salary (1 script → 1 module)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `salary-gap.mjs` | `salary/salary_gap.py` | 634 | Élevée | Desired vs advertised vs actual comp gap. |

### Other (7 scripts → 7 modules)

| JS | Python | Lignes JS | Complexité | Notes |
|----|--------|-----------|------------|-------|
| `application-answers.mjs` | `other/application_answers.py` | ~100 | Faible | Application answer drafts management. |
| `fingerprint-core.mjs` | `other/fingerprint_core.py` | ~150 | Moyenne | JD-content fingerprinting via SimHash (64-bit). |
| `prepare-application.mjs` | `other/prepare_application.py` | ~150 | Faible | ATS auto-fill prefill summary. |
| `img-to-pdf.mjs` | `other/img_to_pdf.py` | ~80 | Faible | Screenshot/image → PDF via Playwright. |
| `openrouter-runner.mjs` | `other/openrouter_runner.py` | 795 | Élevée | OpenRouter free-model runner with fallback. |
| `funnel-velocity.mjs` | `other/funnel_velocity.py` | 661 | Élevée | Funnel calibration vs market benchmarks. |
| `assessment-log.mjs` | `other/assessment_log.py` | ~100 | Faible | Skills-assessment event logger. |

---

## Dépendances Python requises

### Existantes (dans `backend/pyproject.toml`)

```toml
Django>=5.1,<6
djangorestframework>=3.15,<4
django-cors-headers>=4.4,<5
playwright>=1.49,<2        # ← pour generate-pdf, check-liveness, browser-extract
PyYAML>=6,<7               # ← pour tous les scripts lisant du YAML
python-dotenv>=1.0,<2      # ← pour openai-eval, openai-tailor
```

### Nouvelles (à ajouter dans `scripts/python/pyproject.toml`)

```toml
[project]
name = "career-ops-scripts"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  # Core
  "pyyaml>=6,<7",
  "python-dotenv>=1.0,<2",

  # HTTP (pour scanners, evaluators, portails)
  "httpx>=0.27,<1",           # async HTTP client (remplace fetch)

  # Playwright (pour PDF, liveness, browser-extract)
  "playwright>=1.49,<2",

  # LLM providers
  "openai>=1.50,<2",          # OpenAI-compatible APIs
  "google-genai>=1.0,<2",     # Gemini API

  # Text processing
  "rapidfuzz>=3.10,<4",       # fuzzy matching (remplace Levenshtein custom)
  "difflib"                   # stdlib — pour role matching

  # Fingerprinting
  # hashlib + struct — stdlib suffit pour SimHash

  # PDF generation
  # Playwright suffit pour HTML→PDF
  # reportlab>=4.2,<5        # optionnel pour PDF natif sans browser

  # TSV/CSV parsing
  # csv + re — stdlib suffit

  # CLI
  "click>=8.1,<9",            # CLI framework (optionnel, argparse stdlib aussi)
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.24,<1",
  "pytest-django>=4.9,<5",
  "ruff>=0.6,<1",             # linter
]
```

---

## Stratégie de migration

### Phase 1 — Fondations (Priorité haute)

**Objectif :** Les 3 modules partagés + utilitaires de base. Sans eux, rien d'autre ne compile.

| # | Module | Lignes JS | Estimé Python | Notes |
|---|--------|-----------|---------------|-------|
| 1 | `tracker/parse.py` | 177 | ~200 | Mapping colonnes, alias JSON, header detection. Import `tracker-aliases.json` via `pathlib`. |
| 2 | `tracker/utils.py` | 404 | ~450 | Row rebuild, locking (fcntl.flock), atomic write (tempfile + os.rename), company normalization. |
| 3 | `tracker/links.py` | ~50 | ~60 | Path normalization (root-relative ↔ dir-relative). |
| 4 | `tracker/role_matcher.py` | ~150 | ~120 | `rapidfuzz.fuzz.ratio` remplace Levenshtein custom. Token set matching. |
| 5 | `other/fingerprint_core.py` | ~150 | ~130 | SimHash via `hashlib` + `struct`. 64-bit, hamming distance. |

**Pyproject.toml** + **`__init__.py`** files.

### Phase 2 — Tracker CLI (Priorité haute)

**Objectif :** Tous les outils tracker fonctionnent en Python.

| # | Module | Lignes JS | Estimé Python | Dépend de |
|---|--------|-----------|---------------|-----------|
| 6 | `tracker/set_status.py` | ~200 | ~220 | parse, utils |
| 7 | `tracker/merge_tracker.py` | 709 | ~750 | parse, utils, links, role_matcher |
| 8 | `tracker/dedup_tracker.py` | 395 | ~350 | parse, utils, role_matcher |
| 9 | `tracker/normalize_statuses.py` | ~100 | ~90 | utils |
| 10 | `tracker/verify_pipeline.py` | 423 | ~400 | parse, utils |
| 11 | `tracker/find.py` | ~150 | ~130 | parse |
| 12 | `tracker/reserve_report_num.py` | ~80 | ~70 | — |
| 13 | `tracker/add_entry.py` | ~120 | ~100 | — |
| 14 | `tracker/followup_cadence.py` | 452 | ~420 | parse |
| 15 | `tracker/followup_seed.py` | 648 | ~600 | followup_cadence |
| 16 | `tracker/invite_match.py` | 464 | ~430 | parse, role_matcher |
| 17 | `tracker/process_quality.py` | ~150 | ~130 | parse |
| 18 | `tracker/detect_reposts.py` | ~200 | ~180 | role_matcher, fingerprint_core |
| 19 | `tracker/reconcile_pipeline.py` | ~100 | ~90 | — |

### Phase 3 — Scanner + Pipeline (Priorité moyenne)

| # | Module | Lignes JS | Estimé Python | Dépend de |
|---|--------|-----------|---------------|-----------|
| 20 | `scanner/classify_tier.py` | ~80 | ~70 | — |
| 21 | `pipeline/liveness_core.py` | ~100 | ~90 | — |
| 22 | `pipeline/liveness_api.py` | ~150 | ~140 | liveness_core, httpx |
| 23 | `pipeline/liveness_browser.py` | ~100 | ~90 | liveness_core, playwright |
| 24 | `pipeline/browser_extract.py` | ~200 | ~180 | playwright |
| 25 | `pipeline/agent_inbox.py` | ~100 | ~90 | — |
| 26 | `scanner/scan.py` | 1786 | ~1800 | httpx, yaml, plugins/engine |
| 27 | `scanner/scan_ats_full.py` | 614 | ~600 | httpx, plugins/engine |
| 28 | `scanner/check_liveness.py` | ~200 | ~180 | pipeline/liveness_*, playwright |

### Phase 4 — CV Generation (Priorité moyenne)

| # | Module | Lignes JS | Estimé Python | Dépend de |
|---|--------|-----------|---------------|-----------|
| 29 | `cv/templates.py` | ~150 | ~140 | yaml |
| 30 | `cv/build_html.py` | 431 | ~400 | cv/templates |
| 31 | `cv/build_latex.py` | ~200 | ~180 | cv/templates |
| 32 | `cv/generate_pdf.py` | 515 | ~480 | playwright, cv/templates |
| 33 | `cv/generate_latex.py` | ~150 | ~130 | subprocess (tectonic/pdflatex) |
| 34 | `cv/generate_cover_letter.py` | ~200 | ~180 | playwright, cv/templates |
| 35 | `cv/extract_latex_content.py` | ~100 | ~90 | re |
| 36 | `cv/patch_latex_content.py` | ~100 | ~90 | re |
| 37 | `cv/verify_cv_facts.py` | ~100 | ~90 | — |

### Phase 5 — Evaluation + Reply + Salary (Priorité moyenne)

| # | Module | Lignes JS | Estimé Python | Dépend de |
|---|--------|-----------|---------------|-----------|
| 38 | `other/openrouter_runner.py` | 795 | ~750 | httpx, yaml |
| 39 | `evaluation/gemini_eval.py` | 439 | ~400 | google-genai, yaml |
| 40 | `evaluation/ollama_eval.py` | ~200 | ~180 | httpx, yaml |
| 41 | `evaluation/openai_eval.py` | 393 | ~360 | openai, yaml, openrouter_runner |
| 42 | `evaluation/eval_golden.py` | ~150 | ~130 | openai_eval |
| 43 | `evaluation/jd_skill_gap.py` | ~250 | ~230 | re |
| 44 | `evaluation/openai_tailor.py` | ~300 | ~270 | openai, yaml, cv/build_html, cv/templates |
| 45 | `reply/reply_matcher.py` | ~200 | ~180 | parse |
| 46 | `reply/reply_watch.py` | ~250 | ~220 | reply_matcher, parse, utils |
| 47 | `reply/paste_reply.py` | ~100 | ~90 | reply_watch |
| 48 | `salary/salary_gap.py` | 634 | ~580 | parse, yaml |
| 49 | `interview/match_star.py` | ~200 | ~180 | — |
| 50 | `other/funnel_velocity.py` | 661 | ~600 | parse, yaml |

### Phase 6 — Plugins + Admin + Export (Priorité basse)

| # | Module | Lignes JS | Estimé Python | Dépend de |
|---|--------|-----------|---------------|-----------|
| 51 | `plugins/engine.py` | ~300 | ~280 | yaml, importlib |
| 52 | `plugins/cli.py` | ~150 | ~130 | plugins/engine |
| 53 | `plugins/audit.py` | ~100 | ~90 | — |
| 54 | `plugins/install.py` | ~150 | ~130 | plugins/engine, plugins/audit |
| 55 | `plugins/validate_registry.py` | ~100 | ~90 | plugins/engine |
| 56 | `admin/doctor.py` | 430 | ~400 | plugins/engine, cv/templates |
| 57 | `admin/update_system.py` | 1108 | ~1050 | httpx, yaml |
| 58 | `admin/validate_portals.py` | ~150 | ~130 | yaml |
| 59 | `admin/verify_portals.py` | 571 | ~530 | httpx, yaml |
| 60 | `admin/cv_sync_check.py` | ~100 | ~90 | — |
| 61 | `admin/validate_paths.py` | ~100 | ~90 | update_system |
| 62 | `admin/manifesto.py` | ~50 | ~40 | webbrowser |
| 63 | `admin/upskill.py` | 663 | ~600 | parse, yaml |
| 64 | `admin/stats.py` | 438 | ~400 | parse, yaml |
| 65 | `admin/test_all.py` | 8091 | ~7500 | subprocess (peut rester en JS) |
| 66 | `export/build_dashboard.py` | ~100 | ~90 | subprocess (go build) |
| 67 | `other/application_answers.py` | ~100 | ~90 | — |
| 68 | `other/prepare_application.py` | ~150 | ~130 | — |
| 69 | `other/img_to_pdf.py` | ~80 | ~70 | playwright |
| 70 | `other/assessment_log.py` | ~100 | ~90 | yaml |

### Phase 7 — Tests (Priorité haute, parallèle)

| # | Module | Lignes JS | Estimé Python | Test de |
|---|--------|-----------|---------------|---------|
| 71 | `tests/conftest.py` | — | ~80 | Fixtures partagées (tracker fixture, tmp_path) |
| 72 | `tests/test_set_status.py` | 559 | ~500 | tracker/set_status |
| 73 | `tests/test_tracker_columns.py` | 573 | ~500 | tracker/parse + merge_tracker + verify_pipeline |
| 74 | `tests/test_followup_seed.py` | ~150 | ~130 | tracker/followup_seed + followup_cadence |
| 75 | `tests/test_followup_cadence.py` | ~100 | ~90 | tracker/followup_cadence |
| 76 | `tests/test_invite_match.py` | ~150 | ~130 | tracker/invite_match |
| 77 | `tests/test_detect_reposts.py` | 881 | ~800 | tracker/detect_reposts |
| 78 | `tests/test_process_quality.py` | ~150 | ~130 | tracker/process_quality |
| 79 | `tests/test_reply_matcher.py` | ~200 | ~180 | reply/reply_matcher |
| 80 | `tests/test_paste_reply.py` | ~100 | ~90 | reply/paste_reply |
| 81 | `tests/test_agent_inbox.py` | ~100 | ~90 | pipeline/agent_inbox |
| 82 | `tests/test_salary_filter.py` | 593 | ~540 | scanner/scan + scanner/ashby provider |
| 83 | `tests/test_trust_validator.py` | 409 | ~370 | scanner providers trust validation |
| 84 | `tests/test_updater_migration.py` | ~100 | ~90 | admin/update_system |

### Phase 8 — Bridge Django (priorité haute, peut démarrer tôt)

**Objectif :** Intégrer les scripts Python dans le backend Django via management commands.

| Commande Django | Script Python | Description |
|-----------------|---------------|-------------|
| `python manage.py scan_portals` | `scanner/scan.py` | Scanner les portails |
| `python manage.py merge_tracker` | `tracker/merge_tracker.py` | Merger les TSV batch |
| `python manage.py dedup_tracker` | `tracker/dedup_tracker.py` | Dedup le tracker |
| `python manage.py doctor` | `admin/doctor.py` | Vérifier le setup |
| `python manage.py set_status` | `tracker/set_status.py` | Update status |
| `python manage.py update_system` | `admin/update_system.py` | Update career-ops |

Les management commands existants dans `backend/apps/core/management/commands/` appellent déjà les scripts JS via `run_node_script()`. La migration consiste à remplacer ces appels par des imports Python directs.

---

## Conventions Python

### Structure d'un script

Chaque script suit ce pattern :

```python
#!/usr/bin/env python3
"""
module_name.py — description (mirrors the JS header)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Imports locaux
from .parse import load_tracker, column_map
from .utils import read_tracker, write_tracker, lock_tracker


def main() -> None:
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("company", help="Company name or report number")
    parser.add_argument("state", help="New canonical status")
    parser.add_argument("--note", help="Optional note")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # ... logic ...

    if args.json:
        print(json.dumps(result))
    else:
        print(result)


if __name__ == "__main__":
    main()
```

### Résolution du project root

```python
# scripts/python/__init__.py ou chaque module
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/python/ → project root
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
```

### Locking (concurrent writes)

```python
import fcntl
import tempfile
from pathlib import Path

class TrackerLock:
    """File-based lock for tracker writes (mirrors tracker-utils.mjs)."""
    def __init__(self, tracker_path: Path):
        self.lock_path = tracker_path.with_suffix(".lock")
        self._fd = None

    def __enter__(self):
        self._fd = open(self.lock_path, "w")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("ERROR: Tracker is locked by another process", file=sys.stderr)
            sys.exit(1)
        self._fd.write(f"{os.getpid()}\n")
        self._fd.flush()
        return self

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()
        self.lock_path.unlink(missing_ok=True)
```

### YAML loading

```python
import yaml
from pathlib import Path

def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
```

### HTTP client (remplace fetch)

```python
import httpx

async def fetch_json(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
```

### JSON output (pour le frontend)

```python
def output_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
```

### Fuzzy matching (remplace Levenshtein custom)

```python
from rapidfuzz import fuzz

def role_similarity(a: str, b: str) -> float:
    """Token set ratio — mirrors role-matcher.mjs behavior."""
    return fuzz.token_set_ratio(a.lower(), b.lower())
```

### SimHash fingerprinting

```python
import hashlib
import struct

def simhash(text: str, hashbits: int = 64) -> int:
    """64-bit SimHash — mirrors fingerprint-core.mjs."""
    tokens = text.lower().split()
    v = [0] * hashbits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(hashbits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint

def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
```

---

## Estimation totale

| Phase | Modules | Lignes JS | Estimé Python | Priorité |
|-------|---------|-----------|---------------|----------|
| 1 — Fondations | 5 | ~680 | ~660 | Haute |
| 2 — Tracker CLI | 14 | ~3,590 | ~3,290 | Haute |
| 3 — Scanner + Pipeline | 9 | ~3,188 | ~3,040 | Moyenne |
| 4 — CV Generation | 9 | ~1,896 | ~1,700 | Moyenne |
| 5 — Eval + Reply + Salary | 13 | ~4,532 | ~4,100 | Moyenne |
| 6 — Plugins + Admin + Export | 16 | ~4,262 | ~3,910 | Basse |
| 7 — Tests | 14 | ~3,366 | ~3,000 | Haute |
| 8 — Bridge Django | — | — | ~200 | Haute |
| **TOTAL** | **80** | **~21,514** | **~19,900** | — |

**Ratio JS→Python estimé : ~0.92x** (Python est légèrement plus verbeux mais les stdlib réduisent le code).

---

## Priorité d'exécution recommandée

```
Phase 1 (fondations)     ██████████░░░░░░░░░░░░░░░░  2 semaines
Phase 2 (tracker CLI)    ████████████████░░░░░░░░░░  3 semaines
Phase 7 (tests)          ░░░░████████████████░░░░░░  3 semaines (parallèle)
Phase 8 (bridge Django)  ░░░░░░░░████████░░░░░░░░░░  2 semaines
Phase 3 (scanner)        ░░░░░░░░░░░░████████████░░  3 semaines
Phase 4 (cv)             ░░░░░░░░░░░░░░░░████████░░  2 semaines
Phase 5 (eval/reply)     ░░░░░░░░░░░░░░░░░░░░██████  3 semaines
Phase 6 (admin)          ░░░░░░░░░░░░░░░░░░░░░░░░██  2 semaines
```

**Total estimé : ~14 semaines** (1 développeur full-time, parallélisable).

---

## Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| `tracker-aliases.json` drift entre JS et Python | Élevé | Partager le fichier JSON (pas de copie). Import via `pathlib` depuis `scripts/js/`. |
| Playwright behavior différent en Python | Moyen | `playwright` Python est le même driver Chromium. Tests E2E pour PDF generation. |
| Locking différent (flock vs Windows) | Faible | Darwin/Linux uniquement (déjà le cas pour les scripts JS). |
| `test-all.mjs` (8091 lignes) | Élevé | Garder en JS comme test runner, ou migrer en dernier. |
| `update-system.mjs` (1108 lignes) | Moyen | Migrer en dernier, c'est le script le plus risqué (auto-modification). |
| Async patterns Python vs JS | Faible | Python asyncio ≈ JS async/await. `httpx` supporte les deux. |
