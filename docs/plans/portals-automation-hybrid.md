# Plan — Approche Hybride d'Automatisation portals.yml

**Date :** 2026-07-16  
**Statut :** Plan d'architecture

---

## Principe

Les 4 approches analysees (Django Command, Agent Skill, API REST, Job Board Scraper) ne sont pas concurrentes — ce sont des **couches complementaires** d'un pipeline de decouverte. L'hybride les combine en un workflow unique.

---

## Architecture en 5 couches

```
+====================================================================+
|                     PIPELINE DE DECOUVERTE                         |
|                                                                    |
|  COUCHE 1 — SOURCE            D'ou viennent les entreprises ?      |
|  +------------------+  +------------------+  +------------------+  |
|  | LLM Discovery    |  | Job Board Scrape |  | Entree Manuelle  |  |
|  | (Approche A)     |  | (Approche D)     |  | (Utilisateur)    |  |
|  | "Top 30 pharma   |  | APEC/Indeed      |  | "Ajoute X,Y,Z"   |  |
|  |  en France"      |  | offres actives   |  |                  |  |
|  +--------+---------+  +--------+---------+  +--------+---------+  |
|           |                    |                    |               |
|           +--------------------+--------------------+              |
|                                |                                   |
|  COUCHE 2 — ENRICHMENT        Trouver careers_url + ATS           |
|  +-----------------------------------------------------------+    |
|  |                    Enrichment Engine                       |    |
|  |                                                           |    |
|  |  1. LLM: "Quelle est la page carriere officielle de X ?"  |    |
|  |  2. Agent Playwright: navigue, confirme l'URL (Approche B)|    |
|  |  3. ATS Detector: Greenhouse/Lever/Ashby/Workday/SR       |    |
|  |  4. Fallback: scan_method = websearch                     |    |
|  +-----------------------------------------------------------+    |
|                                |                                   |
|  COUCHE 3 — VALIDATION        Verifier la qualite                 |
|  +-----------------------------------------------------------+    |
|  |  +------------------+  +------------------+  +----------+  |    |
|  |  | verify-portals   |  | HTTP HEAD check  |  | Dedup    |  |    |
|  |  | (slug ATS valide) |  | (URL vivante)   |  | (existant|  |    |
|  |  +------------------+  +------------------+  +----------+  |    |
|  +-----------------------------------------------------------+    |
|                                |                                   |
|  COUCHE 4 — CONFIRMATION      L'utilisateur valide (Approche B)   |
|  +-----------------------------------------------------------+    |
|  |  Agent affiche le diff YAML                                |    |
|  |  [x] Sanofi       — greenhouse — ✅ valide                 |    |
|  |  [x] bioMerieux   — custom     — ⚠️ pas d'API (websearch)  |    |
|  |  [ ] Medtronic    — workday    — ❌ slug invalide           |    |
|  |                                                           |    |
|  |  "Ajouter 24/30 entreprises ? [y/N]"                      |    |
|  +-----------------------------------------------------------+    |
|                                |                                   |
|  COUCHE 5 — INTEGRATION       Ecrire dans le systeme              |
|  +-----------------------------------------------------------+    |
|  |  +------------------+  +------------------+  +----------+  |    |
|  |  | import_yaml_to_db|  | export_db_to_yaml|  | API POST  |  |    |
|  |  | Django DB        |  | portals.yml      |  | (Approche |  |    |
|  |  |                  |  |                  |  |  C)       |  |    |
|  |  +------------------+  +------------------+  +----------+  |    |
|  +-----------------------------------------------------------+    |
+====================================================================+
```

---

## Workflow complet

```
$ python manage.py discover_portals \
    --sector "dispositifs medicaux" \
    --country "France" \
    --sources llm,apsc,indeed \
    --max 30 \
    --interactive

 ┌─ SOURCE ─────────────────────────────────────────────┐
 │  LLM:       30 companies discovered                  │
 │  APEC:       12 companies hiring "affaires rég."     │
 │  Indeed:     8 companies hiring "quality engineer"   │
 │  Manual:     0 (--add not used)                      │
 │  ─────────────────────────────────────────────────── │
 │  Unique:     42 companies (dedup cross-source)       │
 └──────────────────────────────────────────────────────┘

 ┌─ ENRICHMENT ─────────────────────────────────────────┐
 │  42/42    careers_url found (LLM + web search)       │
 │  38/42    URL confirmed live (HTTP HEAD)             │
 │  4/42     URL dead, retrying with Playwright...      │
 │  3/4      recovered via Playwright navigation        │
 │  1/42     unreachable, skipped                       │
 │  ─────────────────────────────────────────────────── │
 │  41/42    enriched with ATS info                     │
 │    • 12   Greenhouse                                 │
 │    • 8    Lever                                      │
 │    • 5    Workday                                    │
 │    • 2    SmartRecruiters                            │
 │    • 1    Ashby                                      │
 │    • 13   custom (websearch fallback)                │
 └──────────────────────────────────────────────────────┘

 ┌─ VALIDATION ─────────────────────────────────────────┐
 │  28/28   ATS slugs valid (API responds 200)          │
 │  2/28    slugs invalid (404) → fallback websearch    │
 │  13/13   websearch entries: URL confirmed            │
 │  ─────────────────────────────────────────────────── │
 │  41/42   passed validation                           │
 │  • 26    API-ready (Greenhouse/Lever/...)            │
 │  • 15    websearch (no API, but URL confirmed)       │
 └──────────────────────────────────────────────────────┘

 ┌─ CONFIRMATION ───────────────────────────────────────┐
 │  Ready to add 41 companies to portals.yml.           │
 │                                                      │
 │  API companies (26):  [████████████████████████]     │
 │  Websearch (15):      [███████████████ ]             │
 │  Rejected (1):        [ ] unreachable                │
 │                                                      │
 │  Review diff? [y/N/diff]                             │
 └──────────────────────────────────────────────────────┘

 ┌─ INTEGRATION ────────────────────────────────────────┐
 │  Backup: config/portals.yml → .backup-20260716       │
 │  DB:     41 companies imported to Django             │
 │  YAML:   41 companies written to config/portals.yml  │
 │  API:    POST /api/portals refreshed                 │
 │                                                      │
 │  Done. 41 companies added.                           │
 │  Run: npm run verify:portals to double-check         │
 └──────────────────────────────────────────────────────┘
```

---

## Implementation

### Structure des fichiers

```
backend/apps/portals/
├── management/
│   └── commands/
│       └── discover_portals.py       ← Point d'entree unique
├── services/
│   ├── discovery.py                  ← Nouveau : logique source
│   │   ├── llm_discovery()           ← Approche A
│   │   ├── apec_scrape()             ← Approche D
│   │   └── indeed_scrape()           ← Approche D
│   ├── enrichment.py                 ← Nouveau : logique enrichment
│   │   ├── find_careers_url()        ← LLM
│   │   ├── verify_url_playwright()   ← Approche B (via subprocess)
│   │   └── detect_ats()              ← Extrait du scanner
│   ├── validation.py                 ← Existant + nouveau
│   │   ├── verify_portals()          ← Deja dans services.py
│   │   └── dedup_companies()         ← Nouveau
│   └── integration.py                ← Nouveau
│       ├── backup_portals()          ← Backup avant ecriture
│       ├── merge_into_portals()      ← Merge avec l'existant
│       └── sync_db_yaml()            ← import → DB → export

.opencode/skills/
└── portal-discovery/
    └── SKILL.md                      ← Approche B : fallback manuel

backend/apps/portals/
├── views.py                          ← + DiscoverPortalView (Approche C)
└── urls.py                           ← + /api/portals/discover
```

### Commande unifiee

```bash
# Usage de base
python manage.py discover_portals --sector "pharma" --country "France"

# Multi-source
python manage.py discover_portals \
  --sector "medical devices" \
  --sources llm,apsc,indeed \
  --roles "quality,regulatory" \
  --max 30

# Mode interactif (confirmation avant ecriture)
python manage.py discover_portals --sector "biotech" --interactive

# Dry-run (preview only)
python manage.py discover_portals --sector "pharma" --dry-run

# Ajout manuel + decouverte
python manage.py discover_portals \
  --add "Sanofi,bioMerieux,Medtronic" \
  --sector "pharma"

# Export JSON (pour agent ou API)
python manage.py discover_portals --sector "pharma" --json
```

---

## Orchestration Agent (Approche B integree)

Le skill agent n'est pas une alternative — c'est le **mode interactif** du pipeline :

```markdown
# Mode 1: Commande rapide (CLI)
python manage.py discover_portals --sector pharma --max 30 --interactive

# Mode 2: Via agent (conversationnel)
"Decouvre 20 entreprises de dispositifs medicaux en France"

# Mode 3: Via web UI (futur)
POST /api/portals/discover { "sector": "pharma", "max": 30 }
```

L'agent peut aussi etre utilise en **fallback** : si le pipeline automatique echoue sur une entreprise (URL introuvable, ATS non detecte), l'agent prend le relais avec Playwright pour une resolution manuelle.

---

## Cas d'usage : biomedical pour Audrey

```bash
python manage.py discover_portals \
  --sector "pharmaceutique et dispositifs medicaux" \
  --country "France" \
  --roles "qualite, affaires reglementaires, biomedical, pharmacovigilance" \
  --sources llm \
  --max 30 \
  --interactive
```

### Resultat attendu

| Entreprise | ATS | API | Statut |
|-----------|-----|-----|--------|
| Sanofi | Workday | ✅ valide | Ajoute |
| bioMerieux | Custom | ⚠️ websearch | Ajoute |
| Medtronic | Workday | ✅ valide | Ajoute |
| Stryker | Workday | ✅ valide | Ajoute |
| Siemens Healthineers | Workday | ✅ valide | Ajoute |
| Roche | Workday | ✅ valide | Ajoute |
| B.Braun | Custom | ⚠️ websearch | Ajoute |
| ... | ... | ... | ... |
| Thermo Fisher | Workday | ✅ valide | Ajoute |
| Eurofins | SmartRecruiters | ✅ valide | Ajoute |

**Note :** Meme les entrees `websearch` (sans API) sont utiles — elles documentent la cible et permettent au scanner de les traiter si un provider websearch est implemente plus tard.

---

## Points forts de l'hybride

| Avantage | Source |
|----------|--------|
| Multi-source (LLM + job boards + manuel) | A + D |
| URLs verifiees en temps reel (HTTP + Playwright) | B |
| Detection ATS automatique (6 patterns) | Scanner existant |
| Validation des slugs API | verify-portals existant |
| Confirmation utilisateur avant ecriture | B |
| Sync DB + YAML bidirectionnelle | Services existants |
| Backup automatique | Nouveau |
| API REST pour UI web | C |
| Fallback manuel via agent | B |
| Reexecutable, idempotent, schedulable | A |

---

## Comparaison avec les approches isolees

| Critere | A seule | B seule | Hybride |
|---------|:---:|:---:|:---:|
| Sources de donnees | 1 (LLM) | 1 (agent web) | 3 (LLM + scrape + manuel) |
| Verification URLs | HTTP HEAD | Playwright | HTTP HEAD + Playwright fallback |
| Detection ATS | Oui | Manuelle | Oui (auto) |
| Confirmation user | Non | Oui | Oui |
| Reproductible | Oui | Non | Oui |
| Schedulable (cron) | Oui | Non | Oui |
| API/web UI | Non | Non | Oui |
| Fallback manuel | Non | Oui | Oui |

---

## Roadmap

```
Phase 1 — Core pipeline (4-5h)
  ├── discovery.py (LLM source)
  ├── enrichment.py (careers_url + ATS detection)
  ├── validation.py (dedup + verify)
  ├── integration.py (backup + merge + sync)
  └── discover_portals.py (management command)

Phase 2 — Multi-source (2-3h)
  ├── apec_scrape() (Approche D)
  ├── indeed_scrape() (Approche D)
  └── --sources llm,apec,indeed

Phase 3 — Agent skill (30 min)
  ├── .opencode/skills/portal-discovery/SKILL.md
  └── Mode interactif + fallback Playwright

Phase 4 — API endpoint (2-3h, future)
  ├── DiscoverPortalView
  └── Frontend UI integration
```
