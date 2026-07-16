# Analyse Approfondie — opensource_career-ops

> **Date d'analyse :** 14 juillet 2026
> **Version analysée :** v1.19.0
> **Auteur original :** Santiago Fernandez de Valderrama ([santifer.io](https://santifer.io))

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Architecture et design](#2-architecture-et-design)
3. [Structure du projet](#3-structure-du-projet)
4. [Composants principaux](#4-composants-principaux)
5. [Scripts (.mjs)](#5-scripts-mjs)
6. [Modes (fichiers de prompt IA)](#6-modes-fichiers-de-prompt-ia)
7. [Connecteurs ATS (providers/)](#7-connecteurs-ats-providers)
8. [Application web (Next.js)](#8-application-web-nextjs)
9. [Dashboard Go (TUI)](#9-dashboard-go-tui)
10. [Système de test](#10-système-de-test)
11. [CI/CD et infrastructure](#11-cicd-et-infrastructure)
12. [Dépendances](#12-dépendances)
13. [Data Contract (contrat de données)](#13-data-contract)
14. [Patterns et conventions notables](#14-patterns-et-conventions-notables)
15. [Multilinguisme](#15-multilinguisme)
16. [Sécurité et éthique](#16-sécurité-et-éthique)
17. [Points forts etaxes d'amélioration](#17-points-forts-et-axes-damélioration)
18. [Métriques clés](#18-métriques-clés)

---

## 1. Résumé exécutif

**career-ops** est une plateforme d'automatisation de recherche d'emploi propulsée par l'IA, conçue pour fonctionner avec n'importe quel assistant de code CLI (Claude Code, OpenCode, Codex, Qwen, Copilot, Grok, Antigravity CLI). Le système a été utilisé par son auteur pour évaluer **740+ offres d'emploi**, générer **100+ CV sur mesure** et décrocher un poste de **Head of Applied AI**.

### Trois principes fondamentaux

| Principe | Description |
|----------|-------------|
| **Local-first** | Tourne sur votre machine, pas de serveur requis |
| **IA-agnostique** | La logique vit dans des fichiers Markdown, exécutée par n'importe quel CLI IA |
| **Human-in-the-loop** | Prépare et évalue ; l'humain révise et clique sur « Soumettre » |

### Capacités principales

- Scan de portails d'emploi (ATS Greenhouse, Lever, Ashby, Workday, etc.)
- Évaluation structurée des offres (blocs A à G)
- Génération de CV PDF optimisés ATS
- Remplissage de formulaires de candidature
- Suivi des candidatures (tracker)
- Gestion des relances
- Préparation aux entretiens
- Analyse des refus et des patterns
- Détection de doublons et de reposts

---

## 2. Architecture et design

### Flux de données global

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   scan.mjs       │────▶│  data/pipeline.md │────▶│  Evaluation (oferta)│
│  (60 providers)  │     │  (inbox URLs)     │     │  + CV tailor        │
└─────────────────┘     └──────────────────┘     └─────────┬───────────┘
                                                           │
                          ┌────────────────────────────────┤
                          ▼                                ▼
               ┌──────────────────┐            ┌──────────────────┐
               │ reports/NNN-*.md │            │ applications.md  │
               │ (évaluations)    │            │ (tracker)        │
               └──────────────────┘            └────────┬─────────┘
                                                        │
                                                        ▼
                                              ┌──────────────────┐
                                              │  apply (humain   │
                                              │  révise + submit)│
                                              └──────────────────┘
```

### Architecture en couches

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACE UTILISATEUR                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  CLI IA       │  │  Web (Next)  │  │  Dashboard (Go)  │  │
│  │  modes/*.md   │  │  web/        │  │  dashboard/       │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
├─────────┼──────────────────┼───────────────────┼────────────┤
│                    MOTEUR DE LOGIQUE                         │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌────────┴─────────┐  │
│  │  84 scripts  │  │  API routes  │  │  Go internals    │  │
│  │  .mjs        │  │  (33 routes) │  │  (data/model/ui) │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
├─────────┼──────────────────┼───────────────────┼────────────┤
│                    COUCHE DONNÉES                            │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌────────┴─────────┐  │
│  │  data/       │  │  reports/    │  │  templates/      │  │
│  │  cv.md       │  │  output/     │  │  config/         │  │
│  │  portals.yml │  │  batch/      │  │  providers/      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Contract (règle critique)

Le projet applique une **séparation stricte** entre deux couches :

| Couche | Fichiers | Règle |
|--------|----------|-------|
| **Utilisateur** (jamais auto-mis à jour) | `cv.md`, `config/profile.yml`, `modes/_profile.md`, `data/*`, `reports/*` | Les mises à jour système ne touchent JAMAIS ces fichiers |
| **Système** (auto-mis à jour) | `modes/_shared.md`, `modes/oferta.md`, tous les scripts, templates | Peuvent être mis à jour par `update-system.mjs` |

---

## 3. Structure du projet

### Répartition des fichiers

| Répertoire | Fichiers | Rôle |
|------------|----------|------|
| Racine (`/`) | 173 entrées | 84 scripts .mjs, 35 .md, configs, infra |
| `modes/` | 135 fichiers .md | Fichiers de prompt IA (évaluation, candidature, scan...) |
| `providers/` | 61 fichiers .mjs | Connecteurs ATS (Greenhouse, Lever, Ashby...) |
| `web/` | 133 fichiers source | App Next.js 16 (TypeScript/React 19/Tailwind) |
| `dashboard/` | 32 fichiers | Dashboard Go TUI (BubbleTea) |
| `templates/` | 9 fichiers | Templates CV HTML/LaTeX, états, benchmarks |
| `config/` | 3 fichiers | Profile, plugins, cv-facts (exemples) |
| `data/` | 2 sous-répertoires | Données utilisateur (offers/, parser-output/) |
| `reports/` | 1 fichier | .gitkeep (rapports d'évaluation) |
| `test/` | 2 fichiers | Tests unitaires |
| `tests/` | 61 entrées | Helpers + 57 tests de providers |
| `plugins/` | 10 entrées | Moteur plugins + intégrations gmail/notion/apify |
| `plugins-registry/` | 10 fichiers .json | Registre communautaire de plugins |
| `evals/` | 3 entrées | Fixtures golden test (10 cas JSON) |
| `batch/` | 5 entrées | Traitement par lot : runner, prompt, logs |
| `docs/` | 20 fichiers | Setup, architecture, FAQ, docs plugins |
| `interview-prep/` | 2 entrées | Story bank, sessions |
| `seeds/` | 2 fichiers | Données seed portfolio VC |
| `scaffolder/` | 3 entrées | Outil de scaffolding de projet |
| `examples/` | 8 fichiers | CVs, rapports, profils exemples |
| `lib/` | 2 fichiers .mjs | Utilitaires LaTeX |
| `fonts/` | 4 fichiers .woff2 | Polices DM Sans + Space Grotesk |
| `.opencode/` | 6 entrées | Plugin + commandes + skills OpenCode |
| `.claude/` | 1 répertoire | Skills Claude Code |
| `.github/` | 9 entrées | Workflows CI/CD, templates d'issues |

**Total : ~734 fichiers** (hors .git/node_modules)

---

## 4. Composants principaux

### 4.1 Scan (découverte d'emplois)

`scan.mjs` est le scanner zéro-token qui interroge directement les API ATS. Il suit une **stratégie de découverte à 4 niveaux** :

1. **Niveau 1** — API endpoint directe (Greenhouse `/jobs`, Ashby `/job-postings`, Lever `/listings`)
2. **Niveau 2** — RSS/Atom feeds
3. **Niveau 3** — HTML scraping ciblé
4. **Niveau 4** — Parser local (`local-parser.mjs`)

### 4.2 Évaluation (blocs A–G)

Le mode `oferta.md` évalue chaque offre en 7 blocs :

| Bloc | Contenu |
|------|---------|
| **A** | Résumé du poste |
| **B** | Adéquation avec le profil |
| **C** | Analyse du marché et de la rémunération |
| **D** | Culture et valeurs |
| **E** | Risques et signaux d'alerte |
| **F** | Verdict et score |
| **G** | Légitimité de l'offre |

**Budget de recherche borné :** max 5 requêtes WebSearch par évaluation (anti-investigation-drift).

### 4.3 Génération de CV

Pipeline à double sortie :
- **HTML → PDF** via Playwright (`generate-pdf.mjs`, 515 lignes)
- **LaTeX → PDF** via pdflatex (`generate-latex.mjs`, 254 lignes)
- **Builder HTML** déterministe (`build-cv-html.mjs`, 431 lignes)
- **Builder LaTeX** déterministe (`build-cv-latex.mjs`, 309 lignes)

### 4.4 Tracker (suivi des candidatures)

Le fichier `data/applications.md` est la **source de vérité**. Écriture encanalisée :
- **Ajouts** → TSV dans `batch/tracker-additions/` → `merge-tracker.mjs`
- **Mises à jour** → `set-status.mjs` (verrouillage atomique, validation states.yml)
- **Nettoyage** → `normalize-statuses.mjs`, `dedup-tracker.mjs`
- **Vérification** → `verify-pipeline.mjs` (12 checks d'intégrité)

### 4.5 Plugins

Architecture fail-open : un plugin malformé est **ignoré**, ne plante jamais le noyau.

| Plugin | Rôle |
|--------|------|
| `gmail` | Intégration email (lecture/classification) |
| `notion` | Synchronisation Notion |
| `apify` | Scraping web avancé |
| `_engine.mjs` | Moteur de chargement/validation |
| `_lock.mjs` | Intégrité des plugins |
| `_net.mjs` | Validation réseau |

---

## 5. Scripts (.mjs)

### 5.1 Scripts core pipeline

| Script | Lignes | Rôle |
|--------|--------|------|
| `scan.mjs` | 1 786 | Scanner zéro-token (60 providers ATS) |
| `scan-ats-full.mjs` | 614 | Scanner inverse — découvre les entreprises par ATS |
| `gemini-eval.mjs` | 439 | Évaluateur Gemini (gratuit) |
| `ollama-eval.mjs` | 376 | Évaluateur Ollama (100% local, privé) |
| `openai-eval.mjs` | 393 | Évaluateur compatible OpenAI |
| `openai-tailor.mjs` | 312 | Tailoring CV compatible OpenAI (headless) |
| `openrouter-runner.mjs` | 795 | Runner OpenRouter (modèles gratuits) |
| `browser-extract.mjs` | 251 | Extraction JD via Playwright headless |
| `prepare-application.mjs` | 241 | Préparation auto-fill ATS |

### 5.2 Tracker et gestion de données

| Script | Lignes | Rôle |
|--------|--------|------|
| `tracker.mjs` | 546 | Index SQLite dérivé pour applications.md |
| `merge-tracker.mjs` | 709 | Fusion TSV batch → applications.md |
| `set-status.mjs` | 343 | CLI canonical pour mise à jour de statut |
| `dedup-tracker.mjs` | 395 | Suppression des doublons |
| `normalize-statuses.mjs` | 169 | Normalisation des statuts |
| `verify-pipeline.mjs` | 423 | Health check (12 vérifications) |
| `reconcile-pipeline.mjs` | 297 | Synchronisation pipeline ↔ batch-state |
| `find.mjs` | 178 | Résolution de requête entreprise/rôle |
| `reserve-report-num.mjs` | 245 | Réservation atomique de numéro de rapport |
| `add-entry.mjs` | 251 | Insertion déterministe dans cv.md |

### 5.3 Analytics et intelligence

| Script | Lignes | Rôle |
|--------|--------|------|
| `analyze-patterns.mjs` | 1 057 | Détecteur de patterns de refus + analyse ATS |
| `stats.mjs` | 438 | Agrégateur de stats pipeline (zéro-token) |
| `upskill.mjs` | 640 | Analyse de gaps de compétences |
| `funnel-velocity.mjs` | 661 | Calibrage funnel vs benchmarks marché |
| `salary-gap.mjs` | 634 | Analyse écart salarial désiré/affiché/réel |
| `followup-cadence.mjs` | 452 | Calcul de cadence de relance |
| `followup-seed.mjs` | 648 | Seed des relances quand status = Applied |
| `detect-reposts.mjs` | 349 | Détection de reposts (2+ fois en 90j) |
| `process-quality.mjs` | 330 | Agrégateur de friction processus recrutement |
| `invite-match.mjs` | 464 | Matching email invitation → ligne tracker |
| `jd-skill-gap.mjs` | 347 | Vérification gaps compétences (sans LLM) |
| `match-star.mjs` | 257 | Matching questions comportementales (stories STAR) |
| `classify-tier.mjs` | 160 | Classification séniorité par titre de poste |
| `role-matcher.mjs` | 132 | Matching fuzzy de titres de rôles |
| `fingerprint-core.mjs` | 146 | Fingerprinting JD via SimHash (64-bit) |

### 5.4 Communication et réponses

| Script | Lignes | Rôle |
|--------|--------|------|
| `reply-watch.mjs` | 266 | Classification des réponses employeurs |
| `reply-matcher.mjs` | 384 | Matching email → tracker (déterministe) |
| `paste-reply.mjs` | 254 | Saisie manuelle dans le pipeline reply-watch |
| `generate-cover-letter.mjs` | 224 | Générateur de lettre de motivation (HTML → PDF) |
| `application-answers.mjs` | 224 | Persistance des réponses candidature |

### 5.5 PDF et génération de documents

| Script | Lignes | Rôle |
|--------|--------|------|
| `generate-pdf.mjs` | 515 | HTML → PDF via Playwright (Chromium headless) |
| `generate-latex.mjs` | 254 | Validation et compilation .tex → PDF |
| `build-cv-html.mjs` | 431 | Render CV HTML déterministe (JSON → HTML) |
| `build-cv-latex.mjs` | 309 | Builder CV LaTeX (JSON → LaTeX) |
| `cv-templates.mjs` | 191 | Découverte et validation de templates |
| `img-to-pdf.mjs` | 259 | Screenshot/image → PDF mono-page |
| `archive-posting.mjs` | 348 | Archivage d'offre en PDF avant disparition |

### 5.6 Liveness et vérification

| Script | Lignes | Rôle |
|--------|--------|------|
| `check-liveness.mjs` | 115 | Vérificateur de liens (CLI) |
| `liveness-core.mjs` | 140 | Logique de classification shared |
| `liveness-browser.mjs` | 253 | Vérification via Playwright |
| `liveness-api.mjs` | 188 | Vérification API ATS (zéro-token) |

### 5.7 Infrastructure et système

| Script | Lignes | Rôle |
|--------|--------|------|
| `doctor.mjs` | 429 | Validation de setup (checklist prérequis) |
| `update-system.mjs` | 1 100 | Auto-updater sécurisé (système uniquement) |
| `test-all.mjs` | 8 089 | Suite de tests complète (63+ checks) |
| `plugins.mjs` | 366 | CLI plugins (list, run, install, audit) |
| `plugin-install.mjs` | 133 | Clone/scaffold/validate plugins communautaires |
| `eval-golden.mjs` | 264 | Harness d'évaluation golden-set |
| `agent-inbox.mjs` | 144 | File d'attente append-only entre sessions |

---

## 6. Modes (fichiers de prompt IA)

### 6.1 Modes principaux (anglais)

| Fichier | Mode | Rôle |
|---------|------|------|
| `_shared.md` | — | Contexte système : scoring, règles, source de vérité |
| `_profile.template.md` | — | Template pour archétypes, narrative, négociation |
| `_custom.template.md` | — | Template pour règles maison personnalisées |
| `oferta.md` | `job` | Évaluation complète A-G (7 blocs) |
| `ofertas.md` | `jobs` | Comparaison multi-offres |
| `auto-pipeline.md` | `auto` | Pipeline automatique complet |
| `pipeline.md` | `pipeline` | Traitement de la file d'URLs |
| `scan.md` | `scan` | Scanner de portails (4 niveaux) |
| `batch.md` | `batch` | Traitement par lot (workers headless) |
| `apply.md` | `apply` | Assistant de candidature live |
| `pdf.md` | `pdf` | Génération PDF optimisée ATS |
| `latex.md` | `latex` | Export CV LaTeX/Overleaf |
| `cover.md` | `cover` | Générateur de lettre de motivation |
| `email.md` | `email` | Brouillon email de candidature |
| `contacto.md` | `contacto` | Messages LinkedIn (recruteur/HM/peer) |
| `deep.md` | `deep` | Recherche entreprise (6 axes) |
| `interview-prep.md` | `interview-prep` | Intelligence d'entretien par entreprise |
| `interview-redflag.md` | `interview-redflag` | Détecteur de red flags entreprise |
| `offer-prep.md` | `offer-prep` | Compagnon de lecture de contrat |
| `followup.md` | `followup` | Gestionnaire de relances |
| `reply-watch.md` | `reply-watch` | Classification des réponses employeurs |
| `tracker.md` | `tracker` | Vue d'ensemble du tracker |
| `patterns.md` | `patterns` | Détecteur de patterns de refus |
| `titles.md` | `titles` | Suggestions de titres adjacents |
| `upskill.md` | `upskill` | Analyse de gaps de compétences |

### 6.2 Sous-modes interview

| Fichier | Rôle |
|---------|------|
| `interview/plan.md` | Plan de préparation planifié par blocs de temps |
| `interview/practice.md` | Questions d'entretien simulées avec feedback |
| `interview/debrief.md` | Débrief post-entretien et fermeture des gaps |

### 6.3 Modes régionaux et linguistiques

Le projet supporte **17+ langues** avec vocabulaire spécifique au marché local :

| Langue | Répertoire | Marché cible | Vocabulaire spécifique |
|--------|-----------|--------------|----------------------|
| **Allemand** | `modes/de/` | DACH (Allemagne/Autriche/Suisse) | 13. Monatsgehalt, Probezeit, Kündigungsfrist, AGG, Tarifvertrag |
| **Français** | `modes/fr/` | Francophonie (France/Belgie/Suisse/Luxembourg/Québec) | CDI/CDD, convention collective SYNTEC, RTT, mutuelle, 13e mois, intéressement |
| **Arabe** | `modes/ar/` | Moyen-Orient / Monde arabe | مكافأة نهاية الخدمة, التأمينات الاجتماعية, فترة التجربة |
| **Japonais** | `modes/ja/` | Japon | 正社員, 業務委託, 賞与, 退職金, みなし残業, 36協定 |
| **Turc** | `modes/tr/` | Turquie | SGK, kıdem tazminatı, ihbar süresi, brüt/net maaş |
| **Hindi** | `modes/hi/` | Inde | CTC vs in-hand, PF/EPF, Gratuity, Bond clause, ESOPs |
| **Espagnol** | `modes/es/` | Marché hispanophone | — |
| **Russe** | `modes/ru/` | Marché russophone | — |
| **Chinois** | `modes/zh/`, `modes/zh-TW/` | Chine continentale / Taïwan | — |
| **Coréen** | `modes/ko/` | Corée du Sud | — |
| **Portugais** | `modes/pt/` | Brésil/Portugal | — |
| **Polonais** | `modes/pl/` | Pologne | — |
| **Italien** | `modes/it/` | Italie | — |
| **Ukrainien** | `modes/ua/` | Ukraine | — |
| **Danois** | `modes/da/` | Danemark | — |
| **Hébreu** | `modes/he/` | Israël | — |
| **Indonésien** | `modes/id/` | Indonésie | — |

### 6.4 Séparation output/modes

```yaml
language:
  output: en      # Langue de la prose humaine (rapports, CV, emails)
  modes_dir: modes/de  # Vocabulaire marché (terminologie locale)
```

---

## 7. Connecteurs ATS (providers/)

**60 connecteurs** pour les principaux ATS et job boards :

### Plateformes ATS majeures
Greenhouse, Ashby, Lever, Workday, BambooHR, Personio, SmartRecruiters, SuccessFactors, Recruitee, Teamtailor, Workable, Phenom, Radancy, Avature, Rippling, Pinpoint, Beesite, JibeApply, CSOD, Softgarden

### Job Boards spécialisés/régionaux
HackerNews, RemoteOK, Remotive, WeWorkRemotely, JustJoin, JobStreet, Glints, Himalayas, NoFluffJobs, SolidJobs, ArbeitNow, ArbeitsAgentur, Amazon, IBM, Tencent, Meituan, DeutscheBahn, Rheinmetall, HecklerKoch, Dassault, TKMS

### Agrégateurs
EchoJobs, TheMuse, 4DayWeek, Jobicy, Jobspresso, LaraJobs, NoDesk, GetOnBd, LandingJobs, WorkingNomads, TheHub

### Chaque provider exporte

```javascript
{ id, detect(entry), fetch(entry, ctx) }
```

---

## 8. Application web (Next.js)

### Stack technique

| Technologie | Version |
|-------------|---------|
| Next.js | 16.2.10 |
| React / React DOM | 19.2.5 |
| TypeScript | 6.x |
| Tailwind CSS | 4.x |
| Playwright-core | 1.61.0 |

### Architecture

```
web/
├── src/
│   ├── app/           # Pages (App Router)
│   │   ├── page.tsx         # Home
│   │   ├── jobs/            # Offres d'emploi
│   │   ├── pipeline/        # Pipeline
│   │   ├── portals/         # Portails
│   │   ├── config/          # Configuration
│   │   ├── cv/              # CV
│   │   ├── explore/         # Exploration
│   │   ├── apply/           # Candidature
│   │   └── analytics/       # Statistiques
│   ├── components/    # 40+ composants React
│   └── lib/           # Modules utilitaires
│       ├── career-ops.ts
│       ├── core/      # States, pipeline, scan, portals
│       ├── apply/     # Session, greenhouse, drive, extract
│       ├── report/
│       ├── explore/
│       ├── inbox/
│       └── cv/        # Quality checks
└── API routes/        # 33 routes API
```

### Routes API (33)

tracker, CV, pipeline, portals, apply, explore, followups, profile, run, usage, doctor, version, assistant, memory, et plus.

---

## 9. Dashboard Go (TUI)

Dashboard terminal autonome construit avec **Charmbracelet BubbleTea** :

```
dashboard/
├── main.go                    # App shell (308 lignes) — 3 vues
├── internal/
│   ├── data/                  # Parser career-ops, métriques, index PDF
│   ├── model/                 # Modèles de données
│   ├── theme/                 # Catppuccin (dark + latte)
│   ├── ui/screens/            # Pipeline, Viewer, Progress
│   └── i18n/                  # Catalogue d'internationalisation
├── go.mod / go.sum
└── *darwin/linux/windows.go    # Commandes platform-specific
```

**Vues disponibles :** Pipeline, Report viewer, Progress tracker

---

## 10. Système de test

### Approche

- **Runner custom** (sans framework : pas de jest/mocha/vitest)
- Tests **co-localisés** avec les scripts (`*.test.mjs` ou `*-tests.mjs`)
- **72 fichiers de test** au total

### Composants de test

| Composant | Fichiers | Description |
|-----------|----------|-------------|
| Suite core | `test-all.mjs` (8 089 lignes) | 63+ checks : syntaxe, imports, data contract, fuites personnelles, couverture chemins |
| Tests providers | `tests/providers/` | 57 fichiers (1 par ATS) + html-entities + SSRF hardening |
| Tests unitaires | `test/`, racine | cv-templates, cover-resolver, browser-extract, stats, detect-reposts, etc. |
| Golden eval | `evals/golden/` | 10 fixtures JSON pour évaluation de précision |
| Tests Go | `dashboard/internal/` | 7 fichiers de test |
| Tests Web | `web/` | test-clean-chips.mjs |

### Pattern de test

```
# Chaque script peut s'auto-valider
node scripts/js/detect-reposts.mjs --self-test

# Suite complète (CI)
node scripts/js/test-all.mjs --quick  # Skip Playwright + dashboard build
```

---

## 11. CI/CD et infrastructure

### GitHub Actions (12 workflows)

| Workflow | Rôle |
|----------|------|
| `test.yml` | Tests PR : Node 24, Go 1.26, `test-all.mjs --quick` + `go test ./...` |
| `web-ci.yml` | CI web app (build + typecheck + tests) |
| `release.yml` | Automatisation de release |
| `labeler.yml` | Auto-labeling PR (risque : core-architecture, agent-behavior, docs) |
| `welcome.yml` | Bot d'accueil pour premiers contributeurs |
| `auto-triage-scan-output.yml` | Tri automatique des issues scan |
| `codeql.yml` | Analyse de sécurité du code |
| `dependency-review.yml` | Revue de dépendances sur PR |
| `no-user-data.yml` | Empêche les données utilisateur dans CI |
| `plugin-registry-validate.yml` | Validation des entrées registre plugins |
| `sbom.yml` | Génération Software Bill of Materials |
| `stale.yml` | Gestion des issues/PR inactives |

### Autres outils CI/CD

| Outil | Rôle |
|-------|------|
| Dependabot | Surveillance npm, Go modules, GitHub Actions |
| Renovate | Gestion des dépendances |
| Release Please | Automatisation de versioning |
| CodeQL | Analyse de sécurité |
| SBOM | Traçabilité des dépendances |

### Gouvernance

- **Modèle BDFL** avec échelle de contributeurs : Participant → Contributor → Triager → Reviewer → Maintainer
- **Code of Conduct** : Contributor Covenant 2.1
- **Security** : signalement privé par email
- **Support** : Discord/Discussions

---

## 12. Dépendances

### Racine (npm)

| Package | Version | Usage |
|---------|---------|-------|
| `@google/generative-ai` | ^0.24.1 | Client API Gemini |
| `dotenv` | ^17.0.0 | Chargement .env |
| `js-yaml` | ^4.1.1 | Parsing YAML |
| `playwright` | 1.61.1 | Automatisation navigateur (PDF, scraping, liveness) |

### Web (Next.js)

| Package | Version | Usage |
|---------|---------|-------|
| `next` | 16.2.10 | Framework React |
| `react` / `react-dom` | ^19.2.5 | UI framework |
| `js-yaml` | ^4.2.0 | Parsing YAML |
| `playwright-core` | ^1.61.0 | Automatisation navigateur |
| `lucide-react` | ^1.8.0 | Icônes |
| `react-markdown` | ^9.0.1 | Rendu Markdown |
| `remark-gfm` | ^4.0.0 | GitHub Flavored Markdown |
| `tailwind-merge` | ^3.5.0 | Fusion classes Tailwind |
| `class-variance-authority` | ^0.7.1 | Variants de composants |
| `clsx` | ^2.1.1 | Utilitaire de classes |

### Dashboard (Go)

- `github.com/charmbracelet/bubbletea` — Framework TUI

### OpenCode Plugin

- `@opencode-ai/plugin` 1.17.18

**Philosophie dépendances :** minimaliste. Le noyau ne dépend que de 4 packages npm. Pas de frameworks lourds côté Node.

---

## 13. Data Contract

Le Data Contract est **la règle architecturale la plus critique** du projet.

### Règle fondamentale

> Les fichiers système (modes/, scripts/, templates/) sont auto-mis à jour.
> Les fichiers utilisateur (cv.md, profile.yml, data/, reports/) ne sont **JAMAIS** touchés par les mises à jour.

### Où vivent les règles

| Type de donnée | Fichier cible |
|----------------|---------------|
| Archétypes, narrative, négociation, cibles salariales | `modes/_profile.md` ou `config/profile.yml` |
| Règles procédurales, workflows, préférences de sortie | `modes/_custom.md` |
| Contenu du CV | `cv.md` |
| Preuves / proof points | `article-digest.md` |
| Préférences utilisateur (style, ton) | Auto-mémoire comportementale |

### Source de vérité pour la génération de contenu

Le contenu généré (CV, lettres de motivation, emails, formulaires) provient **exclusivement** de :
- `cv.md`
- `article-digest.md`
- `config/profile.yml`
- `modes/_profile.md`
- `modes/_custom.md` (style uniquement)
- `writing-samples/`
- `voice-dna.md`
- `interview-prep/story-bank.md`

**Règle absolue :** *« Keywords get reformulated, never fabricated. »* — Réordonner, reformuler, accentuer — mais **jamais inventer**.

---

## 14. Patterns et conventions notables

### 14.1 Structure plate à la racine (#1386)

~50 scripts à la racine par **design délibéré** : stabilité des chemins pour les plugins communautaires, docs, et muscle memory des utilisateurs.

### 14.2 Philosophie zéro-token

De nombreux outils core n'utilisent **aucun token LLM** : scan, liveness, stats, patterns, upskill, salary-gap, match-star, jd-skill-gap, detect-reposts. HTTP + JSON + regex uniquement.

### 14.3 Écritures canoniques

- `set-status.mjs` : **seul** chemin d'écriture pour les changements de statut
- `merge-tracker.mjs` : **seul** chemin pour les ajouts
- Verrouillage de fichier atomique via `tracker-utils.mjs`

### 14.4 Mapping colonnes-aware des headers

`tracker-parse.mjs` mappe les colonnes **par nom de header** (pas par position), tolérant les insertions custom (Location, Via).

### 14.5 Plugins fail-open

Un plugin malformé → log warning → **SKIP**, jamais de crash du noyau. Zéro side-effects au niveau module.

### 14.6 Anti-fabrication

- Métriques CV **jamais** en dur — toujours lues depuis cv.md + article-digest.md
- `verify-cv-facts.mjs` protège contre les métriques inventées
- Budget de recherche borné (5 WebSearch max par évaluation)

### 14.7 Spend tiers

3 niveaux de coût modèle :

| Tier | Usage |
|------|-------|
| **economy** | Le moins cher, idéal pour scanner beaucoup d'offres |
| **standard** | Équilibré coût/qualité (défaut) |
| **premium** | Plus capable, pour les offres importantes |

### 14.8 SimHash fingerprinting

Fingerprinting de contenu JD via **SimHash 64-bit** pour détecter les cross-listings (même poste publié par différentes entités) que l'URL dedup et le dedup entreprise+rôle ne catchent pas.

### 14.9 Numérotation atomique des rapports

`reserve-report-num.mjs` utilise `O_CREAT|O_EXCL` pour une numérotation sans collision en workers parallèles.

### 14.10 Liveness ladder

Vérification en cascade :
1. **API** d'abord (zéro coût)
2. **Playwright headless** ensuite
3. **Navigateur headed** en dernier recours

Patterns d'expiration multilingues (EN, DE, FR).

---

## 15. Multilinguisme

Le projet supporte **17 langues** avec :
- Traductions natives complètes
- Vocabulaire spécifique au marché local
- Séparation output (langue humaine) / modes (contexte marché)
- Règle de composition : `language.output` est authoritaire pour la prose

### Exemples de vocabulaire marché

| Marché | Terme local | Signification |
|--------|-------------|---------------|
| DACH | 13. Monatsgehalt | 13ème mois de salaire |
| DACH | Probezeit | Période d'essai |
| France | CDI | Contrat à durée indéterminée |
| France | RTT | Réduction du temps de travail |
| Japon | 正社員 | Salariat permanent |
| Japon | みなし残業 | Heures sup. forfaitaires |
| Turquie | kıdem tazminatı | Indemnité d'ancienneté |
| Inde | CTC | Coût to company (vs in-hand) |
| Inde | ESOPs | Employee Stock Option Plans |

---

## 16. Sécurité et éthique

### Sécurité

- **Plugin audit** (`plugin-audit.mjs`) — validation d'intégrité des plugins
- **SSRF hardening** (`_trust-validator.mjs`) — validation URL de confiance
- **CodeQL** — analyse statique dans CI
- **Dependabot** — surveillance des vulnérabilités
- **no-user-data.yml** — empêche les données perso dans CI
- **SBOM** — Software Bill of Materials
- **Verrouillage de fichier** — écritures atomiques pour tracker
- **Plugins fail-open** — isolation des erreurs plugin

### Éthique

> *« This system is designed for quality, not quantity. »*

- **Jamais** de soumission automatique — l'humain valide toujours
- **Fortement déconseillé** les candidatures à faible score (< 4.0/5)
- **Respect** du temps des recruteurs
- **Anti-fabrication** — jamais de métriques inventées
- **Budget de recherche borné** — anti-investigation-drift

---

## 17. Points forts et axes d'amélioration

### Points forts

| Aspect | Évaluation |
|--------|------------|
| **Architecture** | Excellente — séparation claire système/utilisateur, data contract strict |
| **Couverture ATS** | 60+ connecteurs, probablement la plus grande collection open-source |
| **Multilinguisme** | 17 langues avec vocabulaire marché natif — unique |
| **Zéro-token philosophy** | Nombreux outils sans coût LLM — ingénieux |
| **Sécurité plugins** | Fail-open + audit — design résilient |
| **CI/CD** | 12 workflows, CodeQL, SBOM, dependabot — mature |
| **Documentation** | 20+ fichiers docs, examples, templates |
| **Tests** | 72 fichiers de test, golden evals, self-test pattern |
| **Flexibilité** | Fonctionne avec 8+ CLI IA différents |
| **Anti-fabrication** | Garde-fous solides contre les métriques inventées |

### Axes d'amélioration potentiels

| Aspect | Suggestion |
|--------|------------|
| **Taille du codebase** | 734 fichiers — pourrait bénéficier d'un monorepo tool (Turborepo/Nx) pour la gestion |
| **Tests** | Runner custom sans framework — migrer vers vitest pour DX meilleure |
| **Types** | Pas de TypeScript dans les scripts .mjs — ajouter des JSDoc types ou migrer en .mts |
| **Documentation API** | Web app a 33 routes mais pas de OpenAPI/Swagger |
| **Monitoring** | Pas de métriques d'usage runtime (analytics, error tracking) |
| **Plugin SDK** | Le système plugin est puissant mais documenté via README uniquement |
| **Performance** | scan.mjs fait 1 786 lignes — candidat au découpage modulaire |
| **i18n dashboard** | Le Go dashboard a un catalogue i18n mais limited aux modes UI |

---

## 18. Métriques clés

| Métrique | Valeur |
|----------|--------|
| Version | 1.19.0 |
| Fichiers totaux | ~734 |
| Scripts .mjs | 84 |
| Fichiers modes | 135 |
| Providers ATS | 60+ |
| Langues supportées | 17 |
| Workflows CI/CD | 12 |
| Fichiers de test | 72 |
| Routes API (web) | 33 |
| Composants React | 40+ |
| Plugins | 6 (gmail, notion, apify, engine, lock, net) |
| Taille test-all.mjs | 8 089 lignes |
| Taille scan.mjs | 1 786 lignes |
| Taille update-system.mjs | 1 100 lignes |
| Dépendances npm root | 4 |
| Dépendances Go | 1 (bubbletea) |

---

*Document généré automatiquement par analyse du code source. Dernière mise à jour : 14 juillet 2026.*
