# Guide de Démarrage — career-ops

> Démarrage rapide en 5 minutes. Pour une analyse complète du projet, voir [ANALYSE-PROJET.md](docs/plans/_archive/analyse-projet.md).

---

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Installation](#2-installation)
3. [Configuration initiale (onboarding)](#3-configuration-initiale)
4. [Première évaluation](#4-première-évaluation)
5. [Scanner des offres](#5-scanner-des-offres)
6. [Web app (optionnel)](#6-web-app)
7. [Dashboard TUI (optionnel)](#7-dashboard-tui)
8. [Chemin gratuit (zéro coût)](#8-chemin-gratuit)
9. [Commandes npm essentielles](#9-commandes-npm-essentielles)
10. [Fichiers de configuration](#10-fichiers-de-configuration)
11. [Pièges courants](#11-pièges-courants)

---

## 1. Prérequis

### Indispensable

| Prérequis | Version | Installation |
|-----------|---------|-------------|
| **Node.js** | >= 18 (>= 20 recommandé) | [nodejs.org](https://nodejs.org) |
| **git** | Toute version récente | `brew install git` (macOS) |
| **Un CLI IA** | Voir ci-dessous | Selon votre choix |

### CLI IA supportés

| CLI | Commande | Installation |
|-----|----------|-------------|
| Claude Code | `claude` | `npm i -g @anthropic-ai/claude-code` |
| OpenCode | `opencode` | `npm i -g @opencode-ai/opencode` |
| Antigravity CLI | `agy` | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` |
| Codex | `codex` | `npm i -g @openai/codex` |
| Qwen Code | `qwen` | Selon documentation officielle |
| GitHub Copilot | `copilot` | `npm i -g @github/copilot` |
| Grok Build | `grok` | Selon documentation officielle |

### Optionnel

| Prérequis | Version | Usage |
|-----------|---------|-------|
| **Go** | >= 1.24.2 | Dashboard TUI |
| **Gemini API key** | Gratuit | Évaluation standalone (`node scripts/js/gemini-eval.mjs`) |
| **OpenRouter API key** | Gratuit | Runner OpenRouter (`node scripts/js/openrouter-runner.mjs`) |

---

## 2. Installation

### Option A : Installation one-click (recommandé)

```bash
npx @santifer/career-ops init
cd career-ops
```

Puis ouvrez votre CLI IA dans le dossier :
```bash
claude      # ou opencode / agy / codex / qwen / grok
```

### Option B : Clone manuel

```bash
git clone https://github.com/santifer/career-ops.git
cd career-ops
npm install
```

> `npm install` lance automatiquement `npx playwright install chromium` (PDF + scraping). Si ça échoue, relancez manuellement.

### Option C : Depuis ce répertoire (déjà cloné)

```bash
npm install
```

### Vérification du setup

```bash
npm run doctor
```

Valide automatiquement toutes les prérequis (Node, Playwright, Git, etc.).

---

## 3. Configuration initiale

Au premier lancement, votre CLI IA détecte les fichiers manquants et lance un **onboarding conversationnel** en 6 étapes :

### Étape 0 — Vérification tarif

Si vous mentionnez le coût, le système vous guide vers le **parcours gratuit** (Antigravity CLI free tier). Sinon, passe à l'étape suivante.

### Étape 1 — CV (obligatoire)

Le système vous demande votre CV via :
1. **Coller** votre CV ici
2. **Coller** votre URL LinkedIn
3. **Décrire** votre expérience (le système rédige pour vous)

→ Crée `cv.md` à la racine.

### Étape 2 — Profil (obligatoire)

Copie `config/profile.example.yml` → `config/profile.yml` et demande :

```yaml
# Extrait de ce qui sera rempli :
name: "Votre Nom"
email: "vous@email.com"
location: "Paris, France"
timezone: "Europe/Paris"
target_roles:
  - "Senior AI Engineer"
  - "Head of Applied AI"
salary_target: "80k-120k EUR"
spend_tier: standard    # economy | standard | premium
```

### Étape 3 — Portals (recommandé)

Copie `templates/portals.example.yml` → `portals.yml` avec **45+ entreprises pré-configurées** (Greenhouse, Lever, Ashby...). Personnalise les mots-clés de recherche.

### Étape 4 — Tracker

Crée `data/applications.md` avec l'en-tête du tableau de suivi.

### Étape 5 — En apprendre plus sur vous

Le système pose des questions approfondies :
- Votre « superpower » unique
- Ce qui vous motive / ce qui vous draine
- Deal-breakers (pas de remote ? pas de startups < 20 personnes ?)
- Votre meilleure réalisation professionnelle
- Projets, articles, études de cas publiés

→ Stocké dans `config/profile.yml`, `modes/_profile.md`, `article-digest.md`.

### Étape 6 — Prêt

Confirmation + suggestions de scan automatique récurrent.

---

## 4. Première évaluation

### Via votre CLI IA (recommandé)

Ouvrez votre CLI et collez une URL ou un JD :

```
https://company.com/jobs/123
```

Le système lance automatiquement le **full auto-pipeline** :
1. Classification du rôle
2. Évaluation sur 10 dimensions pondérées (blocs A–G)
3. Rapport → `reports/{###}-{company}-{date}.md`
4. PDF sur mesure → `output/`
5. Entrée tracker → `data/applications.md`

### Via slash commands

```
/career-ops https://company.com/jobs/123    # Pipeline complet
/career-ops "Nous recherchons un Senior..."  # Collez le texte du JD
/career-ops oferta                            # Évaluation seule (pas de PDF)
/career-ops ofertas                           # Comparer plusieurs offres
```

### Via scripts standalone (sans CLI IA)

```bash
cp .env.example .env
# Éditez .env avec votre clé API

node scripts/js/gemini-eval.mjs "Nous recherchons un Senior AI Engineer..."
node scripts/js/gemini-eval.mjs --file ./jds/mon-offre.txt
npm run or:eval -- "Texte du JD ici"
```

### Via traitement par lot

```bash
# Ajoutez des URLs dans data/pipeline.md :
# - [ ] https://company1.com/jobs/1
# - [ ] https://company2.com/jobs/2

/career-ops pipeline     # Traite la file
/career-ops batch        # Parallélise avec des sub-agents
```

---

## 5. Scanner des offres

### Scan basique (zéro token, zéro coût)

```bash
npm run scan
```

Interroge directement les API ATS (Greenhouse, Ashby, Lever, Wellfound) sans utiliser de LLM. Les résultats vont dans `data/pipeline.md`.

### Scan avec vérification de liveness

```bash
node scripts/js/scan.mjs --verify
```

Ajoute une vérification Playwright pour filtrer les offres expirées.

### Scan étendu

```bash
npm run scan:full             # Tous les portails configurés
npm run scan:yc               # Entreprises YC uniquement
npm run scan:seeds yc,a16z    # Portefeuilles VC spécifiques
```

### Configuration du scan

Éditez `portals.yml` :

```yaml
title_filter:
  positive:
    - "AI Engineer"
    - "ML Engineer"
    - "Head of AI"
  negative:
    - "Intern"
    - "Junior"

tracked_companies:
  - name: Stripe
    greenhouse_token: xxxxx
    enabled: true
  - name: Notion
    ashby_slug: notion
    enabled: true
```

---

## 6. Web app

> **Statut :** Alpha — lecture seule des mêmes fichiers que le CLI. Ne modifie rien tant que vous ne lancez pas explicitement.

### Lancement

```bash
cd web
npm ci
npm run dev
```

Ouvrez http://localhost:3000 (Node 20+ requis).

### Fonctionnalités

| Page | Rôle |
|------|------|
| **Pipeline** | Tableau triable/filtrable des candidatures |
| **Explore** | Scan ATS inversé gratuit + découverte IA |
| **Apply** | Pré-remplissage de formulaires (ne soumet jamais) |
| **Analytics** | Funnel, vélocité, métriques |
| **CV** | Édition CV avec preview |
| **Config** | Paramètres du système |

### Variables d'environnement web

```bash
# web/.env.local
CAREER_OPS_ROOT=/Users/awf/workspace/playground/opensource_career-ops
```

---

## 7. Dashboard TUI

> **Prérequis :** Go >= 1.24.2

```bash
npm run serve:dashboard        # Lancer le dashboard
npm run build:dashboard        # Compiler le binaire standalone
```

Dashboard terminal avec thème Catppuccin Mocha :
- 6 onglets de filtrage
- 4 modes de tri
- Vue groupée/plate
- Aperçus lazy-loaded
- Changements de statut inline

---

## 8. Chemin gratuit

Quatre options pour utiliser career-ops sans rien payer :

### Option 1 : Antigravity CLI (recommandé)

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
agy              # Authentification Google OAuth
agy -p "..."     # Mode headless
```

**Quota :** ~1 000 requêtes/jour, ~1M tokens entrée, ~100K tokens sortie.

### Option 2 : Gemini API (gratuit)

```bash
# Clé gratuite : https://aistudio.google.com/apikey
# .env → GEMINI_API_KEY=xxxxx
node scripts/js/gemini-eval.mjs "Texte du JD"
```

15 requêtes/min, 1M tokens/jour avec `gemini-2.5-flash`.

### Option 3 : OpenRouter (gratuit)

```bash
# Clé gratuite : https://openrouter.ai
# .env → OPENROUTER_API_KEY=xxxxx
npm run or:eval -- "Texte du JD"
```

Centaines de modèles à $0.

### Option 4 : Ollama (100% local)

```bash
npm run ollama:eval -- "Texte du JD"
```

Aucune clé API, aucun coût, tourne sur votre machine.

### Niveaux de dépense

Dans `config/profile.yml` :

| Tier | Coût | Usage |
|------|------|-------|
| `economy` | Le moins cher | Scanner beaucoup d'offres rapidement |
| `standard` | Équilibré | Usage général (défaut) |
| `premium` | Plus cher | Offres importantes, meilleure analyse |

---

## 9. Commandes npm essentielles

### Santé et setup

```bash
npm run doctor                # Valider le setup
npm run update:check          # Vérifier les mises à jour
npm run update                # Appliquer une mise à jour
npm run rollback              # Annuler la dernière mise à jour
```

### Scan et pipeline

```bash
npm run scan                  # Scanner (zéro token)
npm run scan:full             # Scan étendu
npm run liveness              # Vérifier si les offres sont actives
npm run extract               # Extraire un JD via Playwright
npm run validate:portals      # Valider portals.yml
```

### Tracker et intégrité

```bash
npm run tracker               # Consulter le tracker
npm run verify                # Health check pipeline (12 checks)
npm run normalize             # Normaliser les statuts
npm run dedup                 # Supprimer les doublons
npm run merge                 # Fusionner les ajouts batch
npm run find                  # Rechercher dans le tracker
```

### Évaluation et PDF

```bash
npm run gemini:eval           # Évaluer via Gemini
npm run ollama:eval           # Évaluer via Ollama (local)
npm run openai:eval           # Évaluer via OpenAI-compatible
npm run or                    # Runner OpenRouter
npm run pdf                   # Générer le CV PDF
npm run cover-letter          # Générer la lettre de motivation
```

### Analytics

```bash
npm run patterns              # Analyser les patterns de refus
npm run upskill               # Analyser les gaps de compétences
npm run reposts               # Détecter les reposts
npm run invite-match          # Matcher les invitations d'entretien
npm run star                  # Matcher les stories STAR
```

---

## 10. Fichiers de configuration

### Fichiers obligatoires (couche utilisateur — JAMAIS auto-mis à jour)

| Fichier | Création | Rôle |
|---------|----------|------|
| `cv.md` | Onboarding | Votre CV (source de vérité canonical) |
| `config/profile.yml` | Copie depuis `config/profile.example.yml` | Identité, cibles, rémunération, langue, tier |
| `modes/_profile.md` | Auto-copié depuis `modes/_profile.template.md` | Archétypes, narrative, négociation |
| `portals.yml` | Copie depuis `templates/portals.example.yml` | Config scanner — entreprises et requêtes |
| `data/applications.md` | Onboarding | Tracker des candidatures |

### Fichiers optionnels (couche utilisateur)

| Fichier | Rôle |
|---------|------|
| `modes/_custom.md` | Règles procédurales, workflows custom, préférences de sortie |
| `article-digest.md` | Proof points de votre portfolio (améliore les évaluations) |
| `voice-dna.md` garde-fou d'écriture — mots bannis, ton |
| `config/cv-facts.json` | Liste blanche de vérification du CV |
| `data/blacklist.md` | Liste d'entreprises à ne pas cibler |
| `data/salary-observations.tsv` | Log d'observations salariales |
| `interview-prep/story-bank.md` | Stories STAR accumulées |
| `writing-samples/` | Échantillons d'écriture personnels |

### Fichiers système (auto-mis à jour — NE PAS ÉDITER MANUELLEMENT)

| Fichier | Rôle |
|---------|------|
| `modes/_shared.md` | Système de scoring, règles globales |
| `modes/*.md` | Instructions des 30+ modes |
| `AGENTS.md` | Instructions agent (canonical) |
| `*.mjs` | Tous les scripts utilitaires |
| `templates/*` | Templates CV, états, benchmarks |
| `providers/*` | Connecteurs ATS |

---

## 11. Pièges courants

### 1. Playwright pas installé

```
⚠ Playwright MCP not detected
```

**Fix :** `npx playwright install chromium`

### 2. Premières évaluations imparfaites

Le système ne vous connaît pas encore. Plus vous lui donnez de contexte (CV, proof points, préférences, deal-breakers), meilleures sont les évaluations. Il s'améliore à chaque interaction.

### 3. Jamais de soumission automatique

Le système se **stoppe toujours** avant Submit/Send/Apply. Si le score est < 4.0/5, il déconseille fortement de postuler. C'est par design.

### 4. Data Contract : ne pas confondre couches

- **Couche utilisateur** (`cv.md`, `profile.yml`, `data/`) → vous éditez
- **Couche système** (`modes/_shared.md`, `AGENTS.md`, scripts) → auto-mis à jour

Ne jamais mettre de données personnelles dans la couche système.

### 5. Ne pas éditer le tracker manuellement

```bash
# AJOUTS → TSV dans batch/tracker-additions/ puis :
node scripts/js/merge-tracker.mjs

# MISES À JOUR → toujours via :
node scripts/js/set-status.mjs <report#|company> <State> [--note]
```

### 6. Numérotation des rapports en parallèle

Ne **jamais** calculer `max+1` dans des workers parallèles :

```bash
node scripts/js/reserve-report-num.mjs --count 5    # Réserve 042-046
# ... spawn workers ...
node scripts/js/reserve-report-num.mjs --release 042-046  # Libère si annulé
```

### 7. iCloud / OneDrive

Si le projet est dans un dossier cloud, `git status` peut bloquer. Timeout configurable : `CAREER_OPS_GIT_TIMEOUT_MS` (défaut 120s).

### 8. Scanner ≠ Évaluateur

- **`scan.mjs`** = zéro token (interroge les API ATS directement)
- **Évaluation** = c'est là que le coût LLM intervient

### 9. Langue output vs. modes marché

```yaml
language:
  output: en              # Langue de la prose (rapports, CV, emails)
  modes_dir: modes/de     # Vocabulaire marché (terminologie locale)
```

Deux axes séparés. Vous pouvez avoir une sortie en anglais avec du vocabulaire marché allemand.

### 10. Web app en alpha

Elle lit les mêmes fichiers que le CLI mais est **expérimentale**. Ne la lancez que si vous l'explicitez explicitement.

---

## Prochaines étapes

| Action | Commande |
|--------|----------|
| Évaluer une offre | Collez une URL dans votre CLI IA |
| Scanner les portails | `npm run scan` |
| Voir le funnel | `npm run patterns` |
| Analyser les gaps | `npm run upskill` |
| Lancer le dashboard | `npm run serve:dashboard` |
| Lancer la web app | `cd web && npm run dev` |
| Personnaliser les modes | Éditez `modes/_profile.md` |
| Ajouter des entreprises | Éditez `portals.yml` |
| Vérifier la santé | `npm run verify` |
| Documentation complète | `docs/` |

---

*Pour une analyse détaillée de l'architecture et du code, voir [ANALYSE-PROJET.md](docs/plans/_archive/analyse-projet.md).*
