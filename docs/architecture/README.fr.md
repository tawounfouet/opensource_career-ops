# Architecture — career-ops

Carte complète de la construction de career-ops, des principes au déploiement. Pour la frontière précise entre fichiers système et utilisateur, voir [DATA_CONTRACT.md](../../DATA_CONTRACT.md).

---

## Principes

Career-ops repose sur trois engagements :

- **Local en premier.** Tout s'exécute sur votre machine contre vos fichiers. Aucun compte, aucun serveur pour l'outil de base.
- **Indépendant de l'IA.** La logique vit dans des fichiers de prompts Markdown (`modes/`), exécutés par le CLI de votre choix. Aucun modèle n'est imposé.
- **Humain dans la boucle.** L'outil prépare et évalue ; l'humain review et clique. Il ne soumet jamais de candidatures de manière autonome.

## Source de vérité canonique

**Les fichiers sont canoniques, les bases de données sont dérivées.** Les fichiers lisibles par l'homme et diffables via git (`data/applications.md`, `reports/`, `data/pipeline.md`, `cv.md`, `config/profile.yml`) sont la source de vérité permanente. SQLite n'existe que comme index dérivé pour les requêtes rapides et ne deviendra jamais un magasin principal. L'interface web, le dashboard Go, les plugins communautaires et les scripts CLI lisent tous les mêmes fichiers.

---

## Architecture haute niveau

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INTERFACES UTILISATEUR                          │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  CLI IA       │  │  Next.js Web │  │  Go TUI      │             │
│  │  (Claude,     │  │  UI          │  │  Dashboard   │             │
│  │   Codex,      │  │  (React 19)  │  │  (optionnel) │             │
│  │   OpenCode)   │  │              │  │              │             │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘             │
│         │                  │                                        │
│         │ prompts          │ HTTP/JSON                              │
│         ▼                  ▼                                        │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │  modes/*.md  │  │  API Django  │                                │
│  │  (le "cerveau")│  │  (REST)      │                                │
│  └──────────────┘  └──────┬───────┘                                │
│                           │                                         │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                  SERVICES BACKEND                                   │
│                           │                                         │
│  ┌────────────────────────┼────────────────────────────────────┐   │
│  │                   Django 5.x                                │   │
│  │                                                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐  │   │
│  │  │ tracker │ │ portals │ │   cv    │ │ skills_portfolio │  │   │
│  │  │ (index  │ │ (YAML↔  │ │ (CRUD   │ │ (compétences,   │  │   │
│  │  │  DB)    │ │  DB)    │ │  CV)    │ │  extraction LLM,│  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ │  éducation)     │  │   │
│  │                                       └─────────────────┘  │   │
│  │  ┌─────────────┐ ┌──────────┐ ┌──────────────────────┐   │   │
│  │  │  discovery  │ │  runner  │ │       core            │   │   │
│  │  │  (scan      │ │ (logs    │ │ (doctor, version,     │   │   │
│  │  │   emplois   │ │  scripts)│ │  followups, apply)    │   │   │
│  │  │   France)   │ │          │ │                       │   │   │
│  │  └─────────────┘ └──────────┘ └──────────────────────┘   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Scripts CLI                             │   │
│  │                                                           │   │
│  │  scripts/js/ (85 .mjs)    scripts/python/ (10 packages)  │   │
│  │  ─────────────────────    ────────────────────────────    │   │
│  │  • tracker (18)           • tracker (14)                   │   │
│  │  • scanner (5)            • scanner (2)                    │   │
│  │  • évaluation (7)         • évaluation (1)                 │   │
│  │  • cv (9)                 • cv (10)                        │   │
│  │  • plugins (5)            • plugins (6)                    │   │
│  │  • admin (10)             • admin (8)                      │   │
│  │  • réponses (3)           • réponses (3)                   │   │
│  │  • autre (18)             • autre (16)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Les trois niveaux

career-ops fonctionne en trois configurations, de la plus simple à la complète :

### Niveau 1 — CLI uniquement (sans serveur)

```
CLI IA  ──►  modes/*.md  ──►  scripts/js/*.mjs  ──►  data/ + reports/
```

L'architecture d'origine. Le CLI IA lit les fichiers de prompts, exécute les scripts, lit/écrit les fichiers markdown directement. Zéro infrastructure requise.

### Niveau 2 — Interface web + Django

```
Navigateur  ──►  Next.js (port 3000)  ──►  Django (port 8000)  ──►  SQLite + fichiers
```

Ajoute une interface web. Django fournit une API REST sur les mêmes fichiers que le CLI. SQLite est un **index dérivé** pour les requêtes rapides — jamais canonique.

### Niveau 3 — Stack complète avec Docker

```
Navigateur  ──►  docker-compose  ──►  Next.js + Django + SQLite
```

Configuration conteneurisée via le wrapper bash `cops`. Même architecture, simplement orchestrée.

---

## Backend Django — 8 applications

### `core` — Infrastructure partagée

| Endpoint | Rôle |
|----------|------|
| `GET /api/doctor` | Vérification santé système (prérequis, plugins, config) |
| `GET /api/version` | Version + canal + SHA |
| `GET /api/whats-new` | Extrait du changelog |
| `GET /api/clis` | CLIs IA disponibles sur cette machine |
| `GET /api/usage` | Utilisation de tokens (fenêtres 5h + 7j) |
| `GET /api/report/shape` | Forme des données de rapport pour le frontend |
| `GET/POST /api/memory` | Mémoire persistante (lecture/écriture) |
| `GET /api/followups` | Cadence de relances |
| `POST /api/followups/log` | Enregistrer une relance |
| `POST /api/run` | Exécuter évaluation/PDF/recherche (streaming NDJSON) |
| `POST /api/runs/save` | Enregistrer un log d'exécution |

### `tracker` — Suivi des candidatures

| Endpoint | Rôle |
|----------|------|
| `GET /api/pipeline` | Résumé pipeline (inbox + tracker) |
| `POST /api/status` | Mettre à jour le statut d'une ligne (atomique, verrouillé) |
| `POST /api/tracker/delete` | Supprimer une ligne du tracker |

Modèles : `Application` (miroir de `data/applications.md`), `PipelineJob`, `ScanHistory`.

### `portals` — Configuration des portails

| Endpoint | Rôle |
|----------|------|
| `GET/POST /api/portals` | Config portails (DB + sync YAML) |
| `POST /api/portals/verify` | Vérifier la disponibilité d'un portail |
| `GET/PATCH /api/profile` | Lire/mettre à jour `config/profile.yml` |
| `GET/POST/DELETE /api/profile/variants/{name}` | Variantes de profil |

Modèles : `Portal`, `SearchQuery`, `TitleFilter` (singleton), `LocationFilter` (singleton), `JobBoard`.

**Sync hybride DB+YAML :** `import_yaml_to_db()` et `export_db_to_yaml()` maintiennent la base de données et `config/portals.yml` synchronisés. La DB gagne en cas de conflit. Les scripts CLI lisent le YAML ; l'API web lit la DB.

### `cv` — Gestion du CV

| Endpoint | Rôle |
|----------|------|
| `GET/POST /api/cv` | Lire/écrire `cv.md` |
| `GET /api/cv-pdf?company=X` | Télécharger le CV PDF sur mesure |

Modèles : `CvDocument`, `CvVersion` (historique des versions).

### `skills_portfolio` — Framework de compétences

La plus grande application — 44 routes API, 7 modèles, 8 modules de services.

**Modèles :**
- `SkillExperience` — expériences sources (pro, perso, académique)
- `SkillEvidence` — éléments de preuve (projets, articles, métriques)
- `SkillCompetency` — compétences documentées avec niveaux de maîtrise
- `SkillDevelopmentAction` — plans de formation pour les écarts de compétences
- `Education` — formations, certifications, cours
- `EducationCompetency` — liens éducation-compétence
- `SkillExtractionRun` — piste d'audit de l'extraction LLM

**Modules de services :**

| Module | Rôle |
|--------|------|
| `extraction.py` | Extraction LLM à partir de texte libre (compétences, expériences, éducation, profils, portails) |
| `llm_client.py` | Wrapper LLM compatible OpenAI (URL de base, modèle, clé API configurables) |
| `matching.py` | Benchmark des compétences contre les postes cibles |
| `integration.py` | Intégration déterministe (sans LLM) : export de compétences validées, calcul des écarts |
| `exports.py` | Export vers JSON, Markdown, CVData et CV Markdown complet |
| `prompts.py` | Modèles de prompts pour toutes les opérations LLM |
| `validation.py` | Logique de validation des compétences |

**Endpoints clés :**
- CRUD : `/api/skills/experiences`, `/api/skills/competencies`, `/api/skills/evidence`, `/api/skills/educations`
- Assistés par LLM : `/api/skills/llm/extract-from-experience`, `formalize`, `evaluate-mastery`, `benchmark`, `parse-jd`, `suggest-cv-bullets`, `suggest-interview-questions`
- Intégration : `/api/skills/integration/validated`, `skill-gaps`, `discovery-keywords`
- Export : `/api/skills/export/json`, `markdown`, `cvdata`, `cv-markdown`

### `discovery` — Découverte d'emplois France

Moteur de découverte déterministe (V1, sans LLM) centré sur le marché français.

**Modèles :**
- `JobSource` — définitions des sources scrapables (10 connecteurs)
- `SearchProfile` — critères de recherche (titres, mots-clés, localisation, salaire, séniorité)
- `DiscoveryRun` — enregistrement d'un scan
- `RawJobPosting` — captures brutes des connecteurs
- `JobPosting` — offres normalisées, dédupliquées
- `JobRanking` — scoring multi-factoriel déterministe
- `DailyJobDigest` / `DailyJobDigestItem` — digest quotidien avec décisions utilisateur

**Connecteurs :**

| Connecteur | Source |
|------------|--------|
| `apec.py` | APEC France |
| `france_travail.py` | API France Travail (Pôle Emploi) |
| `hellowork.py` | HelloWork |
| `welcometothejungle.py` | Welcome to the Jungle |
| `ats_ashby.py` | ATS Ashby |
| `ats_greenhouse.py` | ATS Greenhouse |
| `ats_lever.py` | ATS Lever |
| `manual.py` | Import manuel |
| `fake.py` | Connecteur de test |

### `runner` — Exécution de scripts

| Endpoint | Rôle |
|----------|------|
| `POST /api/run` | Exécuter un script avec logging |

Modèles : `RunLog` (enregistrement d'exécution), `RunEvent` (événements individuels).

### `accounts` — Gestion des utilisateurs

Modèle `User` personnalisé avec des champs spécifiques à la carrière : `target_roles`, `salary_min/max`, `spend_tier`, `preferred_cli`.

---

## Frontend Next.js — 20 routes

| Route | Page | Rôle |
|-------|------|------|
| `/` | Accueil | Vue d'ensemble du dashboard |
| `/pipeline` | Pipeline | Inbox des URLs en attente |
| `/pipeline/[id]` | Détail pipeline | Élément individuel du pipeline |
| `/jobs` | Offres | Liste des offres |
| `/jobs/[id]` | Détail offre | Offre individuelle |
| `/cv` | Éditeur CV | Éditer `cv.md` |
| `/profile` | Éditeur profil | Éditer `config/profile.yml` |
| `/profile/list` | Liste profils | Profil de base + variantes |
| `/skills` | Vue compétences | Dashboard du portefeuille |
| `/skills/list` | Liste compétences | Toutes les compétences |
| `/skills/experiences` | Expériences | Gestion des expériences |
| `/skills/education` | Éducation | Gestion de l'éducation |
| `/portals` | Portails | Gestion des portails |
| `/portals/list` | Liste portails | Tous les portails configurés |
| `/explore` | Explorer | Découverte d'emplois |
| `/discovery` | Découverte | Dashboard découverte France |
| `/discovery/profile` | Profil de recherche | Critères de découverte |
| `/config` | Config | Configuration système |
| `/analytics` | Analytiques | Statistiques pipeline |
| `/apply` | Postuler | Remplissage de formulaires |

### Architecture proxy API

Next.js agit comme un **proxy avec fallback** :

1. **Niveau 1 :** Si `CAREER_OPS_API_URL` est défini, proxy vers Django via HTTP
2. **Niveau 2 :** Si Django est down, exécute `manage.py shell -c <python-inline>` directement
3. **Niveau 3 :** Retourne 503 avec un indice pour démarrer Django

Cela permet à l'interface web de fonctionner même sans Django en tant que serveur.

---

## Scripts CLI — 85 JS + packages Python

### `scripts/js/` — 85 fichiers

| Catégorie | Nombre | Scripts clés |
|-----------|--------|--------------|
| Tracker & Pipeline | 18 | `tracker-parse.mjs`, `tracker-utils.mjs`, `merge-tracker.mjs`, `set-status.mjs`, `dedup-tracker.mjs` |
| Scanner & Découverte | 5 | `scan.mjs`, `scan-ats-full.mjs`, `check-liveness.mjs`, `verify-portals.mjs` |
| Évaluation & LLM | 7 | `gemini-eval.mjs`, `openai-eval.mjs`, `ollama-eval.mjs`, `openrouter-runner.mjs` |
| CV & Génération PDF | 9 | `generate-pdf.mjs`, `build-cv-html.mjs`, `build-cv-latex.mjs`, `cv-templates.mjs` |
| Relances & Réponses | 5 | `followup-cadence.mjs`, `reply-watch.mjs`, `reply-matcher.mjs` |
| Analyse & Stats | 6 | `analyze-patterns.mjs`, `stats.mjs`, `upskill.mjs`, `salary-gap.mjs` |
| Plugins | 5 | `plugins.mjs`, `plugin-install.mjs`, `validate-plugin-registry.mjs` |
| Admin & Système | 10 | `doctor.mjs`, `update-system.mjs`, `test-all.mjs`, `verify-pipeline.mjs` |
| Candidature & Entretien | 5 | `prepare-application.mjs`, `invite-match.mjs`, `match-star.mjs` |
| Autre | 15 | `fingerprint-core.mjs`, `browser-extract.mjs`, `build-dashboard.mjs`, etc. |

### `scripts/python/` — 10 packages (en cours)

Équivalents Python en cours de portage depuis le JS. Voir `docs/plans/python-migration.md` pour le plan complet.

### Modules partagés (les 3 piliers)

| Module | Importé par | Rôle |
|--------|-------------|------|
| `tracker-parse.mjs` | 14+ scripts | Mapping des colonnes par header pour le tableau markdown du tracker |
| `tracker-utils.mjs` | 6 scripts | Réécriture de lignes, verrouillage, écriture atomique, normalisation |
| `role-matcher.mjs` | 4 scripts | Matching flou des titres de postes pour dedup/merge |

---

## Le « cerveau » IA — modes/

`modes/*.md` sont des fichiers de prompts qui définissent le comportement de career-ops. Le CLI IA les lit et suit leurs instructions.

### Modes principaux

| Mode | Rôle |
|------|------|
| `_shared.md` | Système de scoring, détection d'archétypes, règles globales (le « noyau ») |
| `_profile.md` | Surcharges de personnalisation utilisateur |
| `_custom.md` | Règles de workflow personnalisées |
| `oferta.md` | Évaluation d'offre (7 blocs : A–G) |
| `auto-pipeline.md` | Pipeline automatique (évaluation + rapport + PDF + tracker) |
| `apply.md` | Remplissage de formulaires de candidature |
| `scan.md` | Scan des portails |
| `batch.md` | Traitement par lot |
| `interview.md` | Préparation aux entretiens |
| `deep.md` | Recherche d'entreprise |
| `contacto.md` | Messagerie LinkedIn/outreach |
| `email.md` | Rédaction d'email de candidature |
| `offer-prep.md` | Analyse des clauses de contrat |
| `patterns.md` | Analyse des motifs de rejet |
| `upskill.md` | Analyse des écarts de compétences |

### Variantes linguistiques — 17 marchés

Arabe, Chinois (simplifié + traditionnel), Danois, Néerlandais, Français, Allemand, Hindi, Indonésien, Italien, Japonais, Coréen, Polonais, Portugais, Russe, Turc, Ukrainien. Chacun fournit des modes d'évaluation, de candidature et de pipeline localisés avec un vocabulaire spécifique au marché (ex. allemand : `13. Monatsgehalt`, `Probezeit` ; français : `CDI/CDD`, `convention collective SYNTEC`).

---

## Flux de données

### Évaluation unitaire

```
Utilisateur colle une JD  ──►  Extraction (Playwright/WebFetch)
                                    │
                               Classification archétype
                                    │
                               Évaluation (blocs A–G)
                               ├── A : Résumé du poste
                               ├── B : Adéquation CV + écarts
                               ├── C : Stratégie de niveau
                               ├── D : Recherche rémunération (WebSearch)
                               ├── E : Plan de personnalisation CV
                               ├── F : Préparation entretien (STAR)
                               └── G : Légitimité de l'offre
                                    │
                               Score (10 dimensions, 1–5)
                                    │
                               ┌────┴────┐
                               ▼         ▼
                         Report.md    PDF (optimisé ATS)
                                    │
                                    ▼
                         data/applications.md (tracker)
```

### Traitement par lot

```
batch-input.tsv  ──►  batch-runner.sh  ──►  N × workers CLI headless
                                                │
                                           ┌────┴────┐
                                           ▼         ▼
                                      Report.md    PDF
                                           │
                                           ▼
                                   Ligne TSV tracker
                                           │
                                   merge-tracker.mjs
                                           │
                                   data/applications.md
```

### Flux de découverte (France)

```
SearchProfile  ──►  scheduler.py  ──►  10 connecteurs (APEC, FT, HelloWork, ...)
                                              │
                                         RawJobPosting
                                              │
                                         normalize.py + dedup.py
                                              │
                                         JobPosting (canonique)
                                              │
                                         scoring.py (déterministe)
                                              │
                                         JobRanking
                                              │
                                         DailyJobDigest
                                              │
                                    Utilisateur décide (accepter/refuser)
                                              │
                                         exporters.py  ──►  data/pipeline.md
```

### Portefeuille compétences → pipeline CV

```
Expériences + Preuves  ──►  SkillsCompetency (validé)
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                    skill-gaps         discovery-keywords
                    (manquants)        (pour scan.mjs)
                         │
                    development-plan
                    (assisté par LLM)
                         │
                    exports.py  ──►  CVData JSON  ──►  cv.md  ──►  PDF
```

---

## Gestion de l'état — où vit quoi

| Stockage | Format | Canonique ? | Rôle |
|----------|--------|-------------|------|
| `cv.md` | Markdown | **Oui** | CV de l'utilisateur — source unique de vérité |
| `config/profile.yml` | YAML | **Oui** | Identité candidat, ciblage, rémunération |
| `config/profiles/*.yml` | YAML | Superposition | Variantes de profil (overlays par rôle) |
| `config/portals.yml` | YAML | **Oui** | Config portails/entreprises, filtres titre/localisation |
| `data/applications.md` | Tableau markdown | **Oui** | Tracker de candidatures — enregistrement permanent |
| `data/pipeline.md` | Checklist markdown | **Yes** | URLs d'offres en attente d'évaluation |
| `reports/*.md` | Markdown | **Oui** | Évaluation A–G complète par offre |
| `modes/_profile.md` | Markdown | Personnel | Mapping d'archétypes, préférences de scoring |
| `modes/_custom.md` | Markdown | Personnel | Règles de workflow personnalisées |
| `voice-dna.md` | Markdown | Personnel | Référence de voix/style |
| `article-digest.md` | Markdown | Personnel | Points de preuve pour le CV |
| `output/*.pdf` | PDF | Généré | CVs sur mesure optimisés ATS |
| `batch/tracker-additions/*.tsv` | TSV | Transitoire | Ajouts batch (fusionnés puis supprimés) |
| `SQLite (db.sqlite3)` | SQLite | **Dérivé** | Index de requêtes rapides sur données markdown |

---

## Motifs d'intégration

### CLI ↔ Django

- **`run_node_script()`** — Django lance des scripts Node via `subprocess.run(["node", script, ...])`
- **I/O fichiers directe** — Django lit/écrit les mêmes fichiers que le CLI (`cv.md`, `portals.yml`, `applications.md`)
- **`root_path()`** dans `core/paths.py` résout les chemins relativement à `CAREER_OPS_ROOT`

### Next.js ↔ Django

- **Proxy HTTP** — Quand `CAREER_OPS_API_URL` est défini, Next.js transmet les requêtes à Django
- **Fallback `manage.py shell`** — Quand le serveur Django est down, Next.js exécute du Python inline via subprocess
- **CORS** — Django autorise `http://localhost:3000`

### Sync YAML ↔ DB (portals)

- **`import_yaml_to_db()`** — lit `config/portals.yml`, met à jour la DB Django
- **`export_db_to_yaml()`** — écrit l'état de la DB dans `config/portals.yml`
- La DB gagne en cas de conflit. Les scripts CLI lisent le YAML ; l'API web lit la DB.

---

## Conventions de nommage

- Rapports : `{###}-{company-slug}-{YYYY-MM-DD}.md` (3 chiffres, zéros padding)
- PDFs : `cv-candidate-{company-slug}-{YYYY-MM-DD}.pdf`
- TSV tracker : `batch/tracker-additions/{num}-{company-slug}.tsv`
- Variantes profil : `config/profiles/{variant-name}.yml`

---

## Tests

| Emplacement | Type | Nombre | Couverture |
|-------------|------|--------|------------|
| `tests/providers/*.test.mjs` | JS | 39 | Un par provider ATS/board |
| `scripts/js/*.test.mjs` | JS | 5 | Co-localisés : reposts, quality, invite, cadence, matcher |
| `scripts/python/tests/*.py` | Python | 25 | Fondations, tracker, admin, CV, plugins, scanner |
| `backend/tests/*.py` | pytest-django | 8 | API, discovery, skills, connecteurs, services LLM |
| `evals/golden/*.json` | Golden LLM | 10 | Précision d'évaluation sur des JDs connues |
| `scripts/js/test-all.mjs` | Harness principal | 1 | 63+ sections de vérification, exécuté en CI |

**CI/CD :** GitHub Actions exécute `test-all.mjs` sur chaque PR. CodeQL pour la sécurité. CodeRabbit pour les reviews. Renovate pour les mises à jour de dépendances.

---

## Portes qualité

- `test-all.mjs` — la suite complète (500+ vérifications)
- `updater-migration-tests.mjs` — application de la frontière système/utilisateur
- `verify-pipeline.mjs` — vérification santé du tracker
- `validate-plugin-registry.mjs` — validation forme des plugins
- `verify-portals.mjs` — vérification des slugs ATS
- CI : les vérifications de statut doivent passer avant le merge. Pas de push direct sur `main`.

---

## Structure du projet

```
career-ops/
├── backend/                    # Django 5.x (Python 3.12+)
│   ├── apps/                   # 8 applications Django
│   │   ├── core/               # Infrastructure partagée
│   │   ├── tracker/            # Suivi des candidatures
│   │   ├── portals/            # Config portails (YAML↔DB)
│   │   ├── cv/                 # Gestion du CV
│   │   ├── skills_portfolio/   # Framework de compétences
│   │   ├── discovery/          # Découverte d'emplois France
│   │   ├── runner/             # Exécution de scripts
│   │   └── accounts/           # Gestion des utilisateurs
│   ├── config/                 # Paramètres Django
│   └── db.sqlite3              # Index dérivé (non canonique)
│
├── web/                        # Next.js 16 (React 19)
│   └── src/
│       ├── app/                # App Router (20 routes + 35 routes API)
│       ├── components/         # 37 répertoires de composants
│       └── lib/                # 18 modules de bibliothèque
│
├── scripts/
│   ├── js/                     # 85 scripts CLI (.mjs)
│   └── python/                 # Équivalents Python (en cours)
│
├── modes/                      # Fichiers de prompts IA (le « cerveau »)
│   ├── _shared.md              # Système de scoring principal
│   ├── _profile.md             # Personnalisation utilisateur
│   ├── oferta.md               # Évaluation d'offre
│   ├── apply.md                # Remplissage de formulaires
│   └── {ar,de,fr,ja,...}/     # 17 variantes linguistiques
│
├── config/                     # Configuration utilisateur
│   ├── profile.yml             # Profil candidat
│   ├── profiles/               # Variantes de profil
│   └── portals.yml             # Config portails/entreprises
│
├── data/                       # Données utilisateur (canoniques)
│   ├── applications.md         # Tracker de candidatures
│   ├── pipeline.md             # URLs en attente
│   └── scan-history.tsv        # Historique dédup URLs
│
├── templates/                  # Templates CV/couverture + templates config
├── reports/                    # Rapports d'évaluation
├── output/                     # PDFs générés (gitignorés)
├── providers/                  # 61 modules scanner ATS/board
├── plugins/                    # Moteur plugins + plugins intégrés
├── packages/cv-generator/      # Générateur CV Python
├── dashboard/                  # Go TUI (optionnel)
├── evals/                      # Fixtures d'évaluation golden
├── docs/                       # Documentation
├── modes/                      # Fichiers de prompts IA
├── scripts/                    # Scripts CLI (JS + Python)
├── batch/                      # État du traitement par lot
├── archives/                   # Archives de sessions
└── .github/                    # CI/CD (Actions, Dependabot)
```

---

## Par où commencer la lecture

| Vous voulez... | Lisez ceci |
|----------------|------------|
| Comprendre la frontière | `DATA_CONTRACT.md` |
| Comprendre le scoring | `modes/_shared.md` + `modes/oferta.md` |
| Ajouter une source d'emploi | Un module existant dans `providers/` (le dupliquer) |
| Comprendre l'updater | `scripts/js/update-system.mjs` |
| Ajouter un endpoint Django | `backend/apps/{app}/views.py` + `urls.py` |
| Ajouter une page web | `web/src/app/{route}/page.tsx` |
| Comprendre le portefeuille compétences | `backend/apps/skills_portfolio/services/` |
| Porter un script vers Python | `docs/plans/python-migration.md` |
| Comprendre la sync portals | `backend/apps/portals/services.py` |
