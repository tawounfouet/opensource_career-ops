# Plan : Migration des scripts .mjs vers scripts/js/

## Contexte

La racine du projet contient **85 fichiers .mjs** (scripts CLI, libraries partagées, tests, outils). L'objectif est de les déplacer dans `scripts/js/` pour désencombrer la racine et mieux séparer les concerns.

---

## Inventaire

### 85 fichiers .mjs à la racine

| Catégorie | Nombre | Exemples |
|-----------|--------|----------|
| Entry points CLI (invoqués par `node scripts/js/X.mjs`) | ~30 | `scan.mjs`, `doctor.mjs`, `set-status.mjs`, `merge-tracker.mjs` |
| Libraries pures (importées, jamais invoquées directement) | ~20 | `tracker-parse.mjs`, `tracker-utils.mjs`, `role-matcher.mjs` |
| Tests (`*.test.mjs`, `*-tests.mjs`) | ~10 | `detect-reposts.test.mjs`, `followup-cadence.test.mjs` |
| Build/génération | ~8 | `generate-pdf.mjs`, `generate-latex.mjs`, `build-cv-html.mjs` |
| Évaluation LLM | ~5 | `gemini-eval.mjs`, `openai-eval.mjs`, `openrouter-runner.mjs` |
| Divers outils | ~12 | `plugins.mjs`, `update-system.mjs`, `validate-portals.mjs` |

---

## Analyse des références

### 577+ références à mettre à jour

| Type de référence | Nombre | Impact |
|-------------------|--------|--------|
| ES imports (`from './X.mjs'`) | ~100+ | Les imports relatifs entre .mjs cassent |
| ES dynamic imports (`await import('./X.mjs')`) | ~14 | Idem |
| `package.json` scripts (`"node scripts/js/X.mjs"`) | 48 | `npm run scan`, `npm run doctor`, etc. cassent |
| AGENTS.md CLI invocations (`node scripts/js/X.mjs`) | 13 | Les instructions AI agents cassent |
| Documentation (README, modes/, docs/) | ~388 | Toutes les instructions CLI dans les docs cassent |
| Web app `rootScript()` | 11 call sites | Le proxy Next.js ne trouve plus les scripts |
| Django `run_node_script()` | 11 call sites | Le backend Django ne trouve plus les scripts |
| Django `root_path()` direct | 2 | `scan-ats-full.mjs`, `verify-portals.mjs` |
| GitHub Actions | 3 | CI cassent |

### Les deux chokepoints critiques

Tout le runtime dépend de **deux functions** qui résolvent les paths :

```python
# backend/apps/core/paths.py:14-15
def root_script(name_no_ext: str) -> Path:
    return root_path(f"{name_no_ext}.mjs")
```

```typescript
// web/src/lib/career-ops.ts
export function rootScript(nameNoExt: string) {
  return path.join(careerOpsRoot(), `${nameNoExt}.mjs`);
}
```

**Si on change ces deux fichiers, tous les appels runtime (Django + Next.js) se résolvent automatiquement.** Il reste les imports ES entre .mjs et la documentation.

### Top 10 des fichiers les plus importés

| Fichier | Importé par | Rôle |
|---------|-------------|------|
| `tracker-parse.mjs` | 26 fichiers | Parsing des lignes tracker |
| `tracker-utils.mjs` | 14 fichiers | Lock, atomic write, paths |
| `role-matcher.mjs` | 10 fichiers | Fuzzy matching entreprise/role |
| `followup-cadence.mjs` | 10 fichiers | Calcul dates de relance |
| `scan.mjs` | 6 fichiers | Scanner portails (+ library) |
| `tracker-links.mjs` | 4 fichiers | Normalisation liens rapports |
| `reply-matcher.mjs` | 4 fichiers | Classification réponses |
| `cv-templates.mjs` | 4 fichiers | Résolution templates CV |
| `liveness-browser.mjs` | 4 fichiers | Contexte Playwright liveness |
| `verify-portals.mjs` | 7 fichiers | Vérification slugs ATS |

---

## Stratégie de migration

### Phase 1 — Créer la structure

```
scripts/
  js/
    scan.mjs
    doctor.mjs
    tracker-parse.mjs
    ... (85 fichiers)
```

### Phase 2 — Mettre à jour les chokepoints (couvre le runtime)

**2a. `backend/apps/core/paths.py`**
```python
def root_script(name_no_ext: str) -> Path:
    return root_path("scripts", "js", f"{name_no_ext}.mjs")
```

**2b. `web/src/lib/career-ops.ts`**
```typescript
export function rootScript(nameNoExt: string) {
  return path.join(careerOpsRoot(), "scripts", "js", `${nameNoExt}.mjs`);
}
```

**2c. `web/src/lib/career-ops.ts` — doctor prerequisites**
```typescript
// Mettre à jour le path du check doctor
["scripts/js/doctor.mjs", "doctor.mjs"],
```

Ces 3 changements fixent automatiquement :
- Tous les appels Django (`run_node_script`)
- Tous les appels Next.js (`execFile` via `rootScript`)
- Le check doctor

### Phase 3 — `package.json` (48 scripts)

Transformer toutes les entries :
```json
"scan": "node scripts/js/scan.mjs"        →  "scan": "node scripts/js/scan.mjs"
"doctor": "node scripts/js/doctor.mjs"    →  "doctor": "node scripts/js/doctor.mjs"
```

### Phase 4 — ES imports entre .mjs (~100+ imports)

Chaque `from './X.mjs'` ou `await import('./X.mjs')` dans les 85 fichiers doit être mis à jour. Comme tous les fichiers sont dans le même dossier source (`scripts/js/`), les imports entre eux restent au même niveau — **aucun changement nécessaire pour les imports entre .mjs**.

**Exception** : les imports qui sortent du dossier (ex: `./plugins/_engine.mjs` → doit devenir `../plugins/_engine.mjs` ou similaire).

### Phase 5 — Documentation (~388 références)

| Fichier | Références | Priorité |
|---------|------------|----------|
| `AGENTS.md` | 13 invocations + ~83 prose | Haute |
| `README.md` (8 langues) | 24 | Moyenne |
| `docs/SCRIPTS.md` | 41 | Haute |
| `docs/RUNNING_ON_A_BUDGET.md` | 16 | Moyenne |
| `docs/PLUGINS.md` | 12 | Moyenne |
| `modes/**/*.md` (62+ fichiers) | ~205 | Basse (beaucoup de doublons) |
| `seeds/README.md`, `batch/README.md`, etc. | ~30 | Basse |
| `plugins/README.md` | 12 | Basse |
| `.github/workflows/*.yml` | 3 | Haute |
| `.github/PULL_REQUEST_TEMPLATE.md` | 1 | Haute |

### Phase 6 — Nettoyage

- Vérifier qu'aucun `.mjs` ne reste à la racine
- Vérifier que `doctor.mjs --json` fonctionne
- Vérifier que `npm run scan` fonctionne
- Vérifier TypeScript compile clean
- Vérifier les tests passent

---

## Risques

| Risque | Mitigation |
|--------|------------|
| Imports cassés entre .mjs | Tous dans le même dossier → imports restent relatifs au même niveau |
| `plugins/` imports relatifs | Vérifier les imports vers `plugins/_engine.mjs` depuis `plugins.mjs` et `plugin-install.mjs` |
| Symlinks Windows | Pas de symlinks — migration complète d'un coup |
| Documentation oubliée | Script `grep` de vérification post-migration |
| CI cassée | Mettre à jour les 3 GitHub Actions en même temps |

---

## Fichiers touchés

| Fichier | Action |
|---------|--------|
| `scripts/js/` (nouveau dossier) | Déplacer les 85 .mjs |
| `backend/apps/core/paths.py` | `root_script()` → `scripts/js/` |
| `web/src/lib/career-ops.ts` | `rootScript()` → `scripts/js/` + doctor prereq |
| `package.json` | 48 scripts mis à jour |
| `AGENTS.md` | 13+83 références |
| `README*.md` (8 fichiers) | 24 références |
| `docs/*.md` | 69 références |
| `modes/**/*.md` | ~205 références |
| `.github/workflows/*.yml` | 3 workflows |
| `.github/PULL_REQUEST_TEMPLATE.md` | 1 référence |
| Tous les .mjs déplacés | Imports internes vérifiés |

## Vérification post-migration

```bash
# 1. Aucun .mjs à la racine
ls *.mjs 2>/dev/null  # should be empty

# 2. Doctor fonctionne
node scripts/js/doctor.mjs --json

# 3. TypeScript compile
cd web && npx tsc --noEmit

# 4. Tests passent
cd backend && python -m pytest tests/ -v

# 5. Aucun import cassé
rg "from '\./" scripts/js/*.mjs  # vérifier les paths
rg "from '\.\./" scripts/js/*.mjs  # vérifier les paths vers plugins/

# 6. package.json
npm run scan -- --help
npm run doctor -- --json
```
