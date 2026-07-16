# Plan : Restructuration des fichiers .md dans `docs/`

## État des lieux

### Racine du projet (50 fichiers .md)

| Catégorie | Fichiers | Action proposée |
|-----------|----------|-----------------|
| **README translations** (15) | `README.{ar,cn,da,de,es,fr,hi,ja,ko-KR,pl,pt-BR,ru,ua,zh-TW}.md` | **Garder à la racine** — convention GitHub, les translations doivent être à la racine pour être détectées |
| **AI CLI configs** (6) | `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `OPENCODE.md`, `GEMINI.md`, `KIMI.md` | **Garder à la racine** — les outils AI lisent ces fichiers par convention depuis la racine |
| **Community** (6) | `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, `SUPPORT.md`, `TRADEMARK.md` | **Garder à la racine** — convention GitHub community health |
| **Meta** (4) | `CHANGELOG.md`, `CONTRIBUTORS.md`, `LEGAL_DISCLAIMER.md`, `MANIFESTO.md` | **Garder à la racine** — convention open source |
| **Data contracts** (1) | `DATA_CONTRACT.md` | **Garder à la racine** — crucial pour les AI agents |
| **User config** (1) | `voice-dna.md` | **Garder à la racine** — fichier utilisateur, pas doc |
| **Plans** (13) | `PLAN-*.md` + `ANALYSE-PROJET.md` | **Déplacer** → `docs/plans/` |
| **Django migration** (4) | `DJANGO-REMAINING-IMPLEMENTATION.md`, `NEXT-STEPS-DJANGO.md`, `DISCOVERY-FRANCE-STATUS-AND-NEXT-STEPS.md`, `PLAN-ACTION-DJANGO.md` | **Déplacer** → `docs/plans/` |
| **FastAPI plans** (2) | `PLAN-ACTION-FASTAPI.md`, `PLAN-ACTION-FASTAPI copy.md` | **Supprimer** le copy, **déplacer** l'original → `docs/plans/` |

### `docs/` existant (16 fichiers + sous-dossiers vides)

| Fichier | Taille | Action |
|---------|--------|--------|
| `APPLY_AUTOFILL.md` | 4K | Garder, renommer en minuscules |
| `ARCHITECTURE.md` | 5K | **Fusionner** avec la version root (110 lignes vs 93) |
| `CODEX.md` | 2K | **Redondant** avec root `CODEX.md` → supprimer |
| `CUSTOMIZATION.md` | 3K | Garder |
| `FAQ.md` | 5K | Garder |
| `FREE_TIER.md` | 3K | Garder |
| `local-parser-cookbook.md` | 4K | Garder |
| `PLUGIN_REVIEW.md` | 5K | Garder |
| `PLUGINS.md` | 8K | Garder |
| `RUNNING_ON_A_BUDGET.md` | 14K | Garder |
| `SCRIPTS.md` | 31K | Garder — le plus gros fichier doc |
| `SETUP.md` | 4K | Garder |
| `SUPPORTED_CLIS.md` | 1K | Garder |
| `SUPPORTED_JOB_BOARDS.md` | 12K | Garder |
| `demo.gif` | 8.7M | **Déplacer** → `docs/assets/` |
| `hero-banner.jpg` | 687K | **Déplacer** → `docs/assets/` |
| `og-image.jpg` | 6M | **Déplacer** → `docs/assets/` |
| `roadmap-phases.jpg` | 6.9M | **Déplacer** → `docs/assets/` |
| `vision-banner.jpg` | 7M | **Déplacer** → `docs/assets/` |
| `analysis/` | vide | **Supprimer** ou remplir |
| `plan/` | vide | **Supprimer** (les plans iront dans `docs/plans/`) |
| `summary/` | 2 fichiers | **Déplacer** → `docs/` (flatten) |
| `press/` | 5 SVGs | **Déplacer** → `docs/assets/press/` |

---

## Architecture cible

```
docs/
├── README.md                        # ← index de la doc (nouveau)
│
├── getting-started/
│   ├── setup.md                     # ← docs/SETUP.md
│   ├── customization.md             # ← docs/CUSTOMIZATION.md
│   ├── free-tier.md                 # ← docs/FREE_TIER.md
│   └── budget.md                    # ← docs/RUNNING_ON_A_BUDGET.md
│
├── architecture/
│   ├── README.md                    # ← fusion ARCHITECTURE.md (root + docs)
│   ├── data-contract.md             # ← DATA_CONTRACT.md (copie symlink ou ref)
│   └── cv-pipeline.md               # ← PLAN-CV-PIPELINE.md (archivé)
│
├── guides/
│   ├── scripts.md                   # ← docs/SCRIPTS.md
│   ├── plugins.md                   # ← docs/PLUGINS.md
│   ├── plugin-review.md             # ← docs/PLUGIN_REVIEW.md
│   ├── supported-clis.md            # ← docs/SUPPORTED_CLIS.md
│   ├── supported-job-boards.md      # ← docs/SUPPORTED_JOB_BOARDS.md
│   ├── apply-autofill.md            # ← docs/APPLY_AUTOFILL.md
│   ├── local-parser-cookbook.md     # ← docs/local-parser-cookbook.md
│   └── faq.md                       # ← docs/FAQ.md
│
├── plans/                           # ← tous les PLAN-*.md déplacés ici
│   ├── README.md                    # ← index des plans avec statut
│   ├── _archive/                    # ← plans terminés ou supersédés
│   │   ├── action-django.md         # ← PLAN-ACTION-DJANGO.md
│   │   ├── action-fastapi.md        # ← PLAN-ACTION-FASTAPI.md
│   │   ├── action-france-jobboards.md # ← PLAN-ACTION-FRANCE-JOBOARDS-DJANGO.md
│   │   ├── action-skills-portfolio.md # ← PLAN-ACTION-SKILLS-PORTFOLIO-DJANGO.md
│   │   ├── scripts-migration.md     # ← PLAN-SCRIPTS-MIGRATION.md (✅ terminé)
│   │   ├── portals-db-sync.md       # ← PLAN-PORTALS-DB-SYNC.md (✅ terminé)
│   │   ├── suite-skills-portfolio.md # ← PLAN-SUITE-SKILLS-PORTFOLIO.md
│   │   ├── education-portfolio.md   # ← PLAN-EDUCATION-PORTFOLIO.md
│   │   └── analyse-projet.md        # ← ANALYSE-PROJET.md
│   ├── python-migration.md          # ← PLAN-PYTHON-MIGRATION.md (en cours)
│   ├── profile-architecture.md      # ← PLAN-PROFILE-ARCHITECTURE.md (en cours)
│   └── django-remaining.md          # ← DJANGO-REMAINING-IMPLEMENTATION.md
│
├── django/
│   ├── next-steps.md                # ← NEXT-STEPS-DJANGO.md
│   ├── discovery-france.md          # ← DISCOVERY-FRANCE-STATUS-AND-NEXT-STEPS.md
│   └── remaining.md                 # ← DJANGO-REMAINING-IMPLEMENTATION.md
│
├── cli/
│   ├── codex.md                     # ← docs/CODEX.md (ou ref root)
│   └── apply-autofill.md            # ← docs/APPLY_AUTOFILL.md
│
├── assets/
│   ├── demo.gif                     # ← docs/demo.gif
│   ├── hero-banner.jpg              # ← docs/hero-banner.jpg
│   ├── og-image.jpg                 # ← docs/og-image.jpg
│   ├── roadmap-phases.jpg           # ← docs/roadmap-phases.jpg
│   ├── vision-banner.jpg            # ← docs/vision-banner.jpg
│   └── press/                       # ← docs/press/
│       ├── business-insider.svg
│       ├── business-insider-dark.svg
│       ├── producthunt.svg
│       ├── wired.svg
│       └── wired-dark.svg
│
└── summary/
    ├── summary.md                   # ← docs/summary/summary.md
    └── summary-v2.md                # ← docs/summary/summary-v2.md
```

---

## Fichiers qui RESTENT à la racine (non déplacés)

Ces fichiers doivent rester à la racine pour des raisons de convention ou de découvrabilité :

### Convention GitHub (community health)
- `README.md` + 14 translations `README.*.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `GOVERNANCE.md`
- `SECURITY.md`
- `SUPPORT.md`
- `TRADEMARK.md`
- `CHANGELOG.md`
- `CONTRIBUTORS.md`
- `LEGAL_DISCLAIMER.md`
- `MANIFESTO.md`
- `SIGNATURES.md`

### Convention AI CLI (découvrabilité automatique)
- `AGENTS.md` (OpenCode, Claude Code)
- `CLAUDE.md` (Claude Code)
- `CODEX.md` (OpenAI Codex)
- `OPENCODE.md` (OpenCode)
- `GEMINI.md` (Google Gemini CLI)
- `KIMI.md` (Kimi CLI)

### Data / Config utilisateur
- `DATA_CONTRACT.md` (crucial pour les agents AI)
- `voice-dna.md` (config utilisateur, pas doc)
- `GETTING-STARTED.md` (point d'entrée, peut rester à la racine ou aller dans `docs/getting-started/`)
- `DOCKER.md` (docker-compose reference)
- `ARCHITECTURE.md` → **symlink** vers `docs/architecture/README.md`

---

## Fichiers à supprimer

| Fichier | Raison |
|---------|--------|
| `PLAN-ACTION-FASTAPI copy.md` | Copie accidentelle |
| `docs/CODEX.md` | Redondant avec root `CODEX.md` |
| `docs/analysis/` | Vide |
| `docs/plan/` | Vide (remplacé par `docs/plans/`) |

---

## Fichiers à créer

| Fichier | Purpose |
|---------|---------|
| `docs/README.md` | Index de toute la documentation avec navigation |
| `docs/plans/README.md` | Index des plans avec statut (en cours / terminé / archivé) |
| `docs/architecture/README.md` | Fusion des deux ARCHITECTURE.md |

---

## Table de mapping complète

### Déplacements vers `docs/`

| Source | Destination | Action |
|--------|-------------|--------|
| `docs/SETUP.md` | `docs/getting-started/setup.md` | move |
| `docs/CUSTOMIZATION.md` | `docs/getting-started/customization.md` | move |
| `docs/FREE_TIER.md` | `docs/getting-started/free-tier.md` | move |
| `docs/RUNNING_ON_A_BUDGET.md` | `docs/getting-started/budget.md` | move |
| `docs/SCRIPTS.md` | `docs/guides/scripts.md` | move |
| `docs/PLUGINS.md` | `docs/guides/plugins.md` | move |
| `docs/PLUGIN_REVIEW.md` | `docs/guides/plugin-review.md` | move |
| `docs/SUPPORTED_CLIS.md` | `docs/guides/supported-clis.md` | move |
| `docs/SUPPORTED_JOB_BOARDS.md` | `docs/guides/supported-job-boards.md` | move |
| `docs/APPLY_AUTOFILL.md` | `docs/guides/apply-autofill.md` | move |
| `docs/local-parser-cookbook.md` | `docs/guides/local-parser-cookbook.md` | move |
| `docs/FAQ.md` | `docs/guides/faq.md` | move |
| `docs/CODEX.md` | — | delete (redondant) |
| `docs/demo.gif` | `docs/assets/demo.gif` | move |
| `docs/hero-banner.jpg` | `docs/assets/hero-banner.jpg` | move |
| `docs/og-image.jpg` | `docs/assets/og-image.jpg` | move |
| `docs/roadmap-phases.jpg` | `docs/assets/roadmap-phases.jpg` | move |
| `docs/vision-banner.jpg` | `docs/assets/vision-banner.jpg` | move |
| `docs/press/*` | `docs/assets/press/` | move |
| `docs/summary/*` | `docs/summary/` | keep (flatten si besoin) |

### Déplacements depuis la racine vers `docs/plans/`

| Source | Destination | Statut |
|--------|-------------|--------|
| `PLAN-ACTION-DJANGO.md` | `docs/plans/_archive/action-django.md` | archivé |
| `PLAN-ACTION-FASTAPI.md` | `docs/plans/_archive/action-fastapi.md` | archivé |
| `PLAN-ACTION-FASTAPI copy.md` | — | **supprimer** |
| `PLAN-ACTION-FRANCE-JOBOARDS-DJANGO.md` | `docs/plans/_archive/action-france-jobboards.md` | archivé |
| `PLAN-ACTION-SKILLS-PORTFOLIO-DJANGO.md` | `docs/plans/_archive/action-skills-portfolio.md` | archivé |
| `PLAN-SCRIPTS-MIGRATION.md` | `docs/plans/_archive/scripts-migration.md` | ✅ terminé |
| `PLAN-PORTALS-DB-SYNC.md` | `docs/plans/_archive/portals-db-sync.md` | ✅ terminé |
| `PLAN-SUITE-SKILLS-PORTFOLIO.md` | `docs/plans/_archive/suite-skills-portfolio.md` | archivé |
| `PLAN-EDUCATION-PORTFOLIO.md` | `docs/plans/_archive/education-portfolio.md` | archivé |
| `ANALYSE-PROJET.md` | `docs/plans/_archive/analyse-projet.md` | archivé |
| `PLAN-CV-PIPELINE.md` | `docs/architecture/cv-pipeline.md` | archivé (architecture) |
| `PLAN-PYTHON-MIGRATION.md` | `docs/plans/python-migration.md` | en cours |
| `PLAN-PROFILE-ARCHITECTURE.md` | `docs/plans/profile-architecture.md` | en cours |
| `DJANGO-REMAINING-IMPLEMENTATION.md` | `docs/plans/django-remaining.md` | en cours |

### Déplacements depuis la racine vers `docs/django/`

| Source | Destination |
|--------|-------------|
| `NEXT-STEPS-DJANGO.md` | `docs/django/next-steps.md` |
| `DISCOVERY-FRANCE-STATUS-AND-NEXT-STEPS.md` | `docs/django/discovery-france.md` |

---

## Steps d'implémentation

### Step 1 — Créer la structure de dossiers
```bash
mkdir -p docs/{getting-started,architecture,guides,plans/_archive,django,assets/press}
```

### Step 2 — Déplacer les médias
```bash
git mv docs/demo.gif docs/assets/
git mv docs/hero-banner.jpg docs/assets/
git mv docs/og-image.jpg docs/assets/
git mv docs/roadmap-phases.jpg docs/assets/
git mv docs/vision-banner.jpg docs/assets/
git mv docs/press/* docs/assets/press/
rmdir docs/press
```

### Step 3 — Déplacer les guides existants
```bash
git mv docs/SETUP.md docs/getting-started/setup.md
git mv docs/CUSTOMIZATION.md docs/getting-started/customization.md
git mv docs/FREE_TIER.md docs/getting-started/free-tier.md
git mv docs/RUNNING_ON_A_BUDGET.md docs/getting-started/budget.md
git mv docs/SCRIPTS.md docs/guides/scripts.md
git mv docs/PLUGINS.md docs/guides/plugins.md
git mv docs/PLUGIN_REVIEW.md docs/guides/plugin-review.md
git mv docs/SUPPORTED_CLIS.md docs/guides/supported-clis.md
git mv docs/SUPPORTED_JOB_BOARDS.md docs/guides/supported-job-boards.md
git mv docs/APPLY_AUTOFILL.md docs/guides/apply-autofill.md
git mv docs/local-parser-cookbook.md docs/guides/local-parser-cookbook.md
git mv docs/FAQ.md docs/guides/faq.md
```

### Step 4 — Déplacer les plans depuis la racine
```bash
git mv PLAN-ACTION-DJANGO.md docs/plans/_archive/action-django.md
git mv PLAN-ACTION-FASTAPI.md docs/plans/_archive/action-fastapi.md
git mv PLAN-ACTION-FRANCE-JOBOARDS-DJANGO.md docs/plans/_archive/action-france-jobboards.md
git mv PLAN-ACTION-SKILLS-PORTFOLIO-DJANGO.md docs/plans/_archive/action-skills-portfolio.md
git mv PLAN-SCRIPTS-MIGRATION.md docs/plans/_archive/scripts-migration.md
git mv PLAN-PORTALS-DB-SYNC.md docs/plans/_archive/portals-db-sync.md
git mv PLAN-SUITE-SKILLS-PORTFOLIO.md docs/plans/_archive/suite-skills-portfolio.md
git mv PLAN-EDUCATION-PORTFOLIO.md docs/plans/_archive/education-portfolio.md
git mv ANALYSE-PROJET.md docs/plans/_archive/analyse-projet.md
git mv PLAN-CV-PIPELINE.md docs/architecture/cv-pipeline.md
git mv PLAN-PYTHON-MIGRATION.md docs/plans/python-migration.md
git mv PLAN-PROFILE-ARCHITECTURE.md docs/plans/profile-architecture.md
git mv DJANGO-REMAINING-IMPLEMENTATION.md docs/plans/django-remaining.md
git mv NEXT-STEPS-DJANGO.md docs/django/next-steps.md
git mv DISCOVERY-FRANCE-STATUS-AND-NEXT-STEPS.md docs/django/discovery-france.md
rm "PLAN-ACTION-FASTAPI copy.md"
```

### Step 5 — Fusionner les ARCHITECTURE.md
- Lire les deux versions
- Fusionner le contenu (la version docs/ a 110 lignes, la root en a 93)
- Écrire `docs/architecture/README.md`
- Remplacer root `ARCHITECTURE.md` par un **symlink** : `ln -s docs/architecture/README.md ARCHITECTURE.md`

### Step 6 — Supprimer les fichiers redondants
```bash
rm docs/CODEX.md          # redondant avec root CODEX.md
rmdir docs/analysis       # vide
rmdir docs/plan           # vide
```

### Step 7 — Créer les index
- `docs/README.md` — table des matières de toute la doc
- `docs/plans/README.md` — index des plans avec statut

### Step 8 — Mettre à jour les références
- `README.md` : vérifier les liens vers `docs/` (SETUP.md, FAQ.md, etc.)
- `AGENTS.md` / `CLAUDE.md` : vérifier les références
- Tous les fichiers qui linkent vers `docs/ARCHITECTURE.md` → `docs/architecture/README.md`
- Tous les fichiers qui linkent vers `docs/SCRIPTS.md` → `docs/guides/scripts.md`

### Step 9 — Vérification
```bash
# Vérifier qu'aucun lien cassé
rg "\]\(.*\.md\)" docs/ --include "*.md" | grep -v "http" | while read line; do
  # extraire le chemin relatif et vérifier qu'il existe
done

# Vérifier qu'il reste les bons fichiers à la racine
ls *.md | grep -v README | grep -v AGENTS | grep -v CLAUDE | grep -v CODEX | grep -v OPENCODE
```

---

## Impact sur les liens existants

### Liens dans `README.md` (root)

Le README root link probablement vers :
- `docs/SETUP.md` → `docs/getting-started/setup.md`
- `docs/FAQ.md` → `docs/guides/faq.md`
- `docs/SCRIPTS.md` → `docs/guides/scripts.md`
- `docs/SUPPORTED_JOB_BOARDS.md` → `docs/guides/supported-job-boards.md`

### Liens dans `AGENTS.md`

AGENTS.md référence `docs/FREE_TIER.md` → `docs/getting-started/free-tier.md`

### Liens dans les modes `modes/*.md`

Les modes peuvent référence `docs/` — à vérifier avec `rg`.

### Liens dans `docs/` existants

Les docs internes se referment entre eux — à mettre à jour après le move.

---

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Liens cassés dans README.md | Élevé | Step 8 — recherche exhaustive des liens |
| GitHub Pages / Jekyll cassé | Moyen | Vérifier `_config.yml` si existant |
| AI CLI ne trouve plus les docs | Faible | Les CLI configs (AGENTS.md etc.) restent à la racine |
| `docs/` trop profond | Faible | Max 2 niveaux de profondeur |
| Perte de visibilité des plans | Moyen | `docs/plans/README.md` avec index et statut |

---

## Résumé des mouvements

| Opération | Count |
|-----------|-------|
| Fichiers déplacés vers `docs/` | ~28 |
| Fichiers supprimés | 3 (copy + redondant + empty dirs) |
| Fichiers créés | 3 (index + fusion) |
| Symlinks créés | 1 (ARCHITECTURE.md) |
| Références à mettre à jour | ~15-20 fichiers |
| **Fichiers restant à la racine** | **~35** (README×15, AI×6, Community×6, Meta×4, Data×2, Docker×1, Getting-Started×1) |
