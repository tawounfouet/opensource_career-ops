# Session: Scripts Migration JS→Python + Root Cleanup

**Date**: 2026-07-15
**Agent(s)**: opencode/big-pickle
**Phase**: build

---

## Intent

Déplacer les 85 fichiers `.mjs` de la racine vers `scripts/js/` pour dégorger le root du projet, puis créer un plan de migration complet vers Python pour éliminer la dépendance Node.js pour les scripts CLI.

## Outcome

Terminé. Les 85 scripts sont en `scripts/js/`, tous les chemins cassés ont été corrigés (imports relatifs, root resolution, documentation), et `PLAN-PYTHON-MIGRATION.md` (732 lignes) documente la migration complète vers Python.

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|----------|-----------|------------------------|
| 1 | `scripts/js/` comme dossier cible (pas `scripts/` seul) | Laisser de l'espace pour `scripts/python/` et d'autres langages | `scripts/cli/`, `tools/` |
| 2 | Garder `test-all.mjs` en JS | 8091 lignes, test runner, pas critique pour l'élimination de Node | Le migrer en Python aussi |
| 3 | `dirname(import.meta.url)` → `join(dirname(...), '..', '..')` partout | Pattern uniforme pour résoudre la racine depuis `scripts/js/` | Utiliser `PROJECT_ROOT` comme variable d'env |
| 4 | Pas de `--target` flag ajouté aux scripts | Le pattern `join(dirname(...), '..', '..')` suffit | Chaque script accepte `--target` |
| 5 | Python migration en 8 phases | Dépendances critiques (tracker-parse/utils) en priorité | Tout d'un coup, par catégorie |

## Files Created

| File | Purpose |
|------|---------|
| `PLAN-PYTHON-MIGRATION.md` | Plan complet de migration JS→Python (732 lignes, 80 modules, 8 phases) |
| `PLAN-SCRIPTS-MIGRATION.md` | Analyse de la migration JS (577+ références, 6 phases) — créé en session précédente |

## Files Modified

| File | Change summary |
|------|----------------|
| `scripts/js/*.mjs` (85 files) | `git mv` depuis la racine. Imports `../plugins/` → `../../plugins/`, `../providers/` → `../../providers/`. Root resolution `dirname(import.meta.url)` → `join(dirname(...), '..', '..')` dans 54 fichiers. |
| `scripts/js/doctor.mjs` | +`join` import + `projectRoot` fix pour résoudre `scripts/js/../..` |
| `backend/apps/core/paths.py` | `root_script()` → `join("scripts", "js", f"{name}.mjs")` |
| `web/src/lib/career-ops.ts` | `rootScript()` → `join(careerOpsRoot(), "scripts", "js", ...)` + doctor prereq |
| `package.json` | 48 scripts `"node X.mjs"` → `"node scripts/js/X.mjs"` |
| `AGENTS.md` | 13+83 références node invocations → `scripts/js/` |
| `.npmignore` | `portals.yml` → `config/portals.yml` (les 2 occurrences) |
| `docs/*.md` (6 files) | 41+16+12+5+3+3 références mises à jour |
| `.github/workflows/test.yml` | `node test-all.mjs` → `node scripts/js/test-all.mjs` |
| `.github/workflows/plugin-registry-validate.yml` | `node validate-plugin-registry.mjs` → `node scripts/js/validate-plugin-registry.mjs` |
| `.github/PULL_REQUEST_TEMPLATE.md` | `node test-all.mjs` → `node scripts/js/test-all.mjs` |
| `README*.md` (11 files) | Toutes les références CLI mises à jour |
| `modes/**/*.md` (72 files) | Toutes les références CLI mises à jour |
| `plugins/**/*.md` (6 files) | Toutes les références CLI mises à jour |
| `CONTRIBUTING.md, GETTING-STARTED.md, DATA_CONTRACT.md, DOCKER.md, ARCHITECTURE.md` | Références mises à jour |
| `batch/batch-prompt.md, config/*.yml, templates/*.md, examples/*.md` | Références mises à jour |

---

## Key Context

- **Root resolution critique** : 54 scripts utilisaient `dirname(import.meta.url)` comme racine. Avant le move, c'était le projet root. Après, c'était `scripts/js/`. Patch `join(dirname(...), '..', '..')` appliqué à tous sauf `doctor.mjs` (corrigé séparément).
- **Relative imports cassés** : `../plugins/` depuis `scripts/js/` résolvait vers `scripts/plugins/` au lieu de `plugins/`. 11 fichiers corrigés en `../../plugins/` et `../../providers/`.
- **`doctor.mjs`** avait un root resolution spécifique (`projectRoot = __dirname`) qui devait être patché séparément.
- **TypeScript compile clean** après toutes les modifications.
- **283 fichiers** modifiés/créés/renommés au total.

## Commands Run

| Command | Purpose | Result |
|---------|---------|--------|
| `node scripts/js/doctor.mjs --json` | Vérifier que doctor fonctionne depuis le nouveau chemin | ✅ `{"onboardingNeeded":true,"missing":["cv.md"]}` |
| `npx tsc --noEmit` | Vérifier que TypeScript compile | ✅ Clean |
| `ls *.mjs 2>/dev/null` | Vérifier qu'il reste des .mjs à la racine | ✅ Aucun |
| `rg -l "'../plugins/" scripts/js/*.mjs` | Trouver les imports relatifs cassés | 6 fichiers trouvés, corrigés |
| `rg -l "'../providers/" scripts/js/*.mjs` | Trouver les imports relatifs cassés | 5 fichiers trouvés, corrigés |
| `rg "dirname(fileURLToPath(import.meta.url))" scripts/js/*.mjs` | Trouver les root resolution cassées | 54 fichiers trouvés, corrigés |

## Patterns Established

- **Root resolution** : `join(dirname(fileURLToPath(import.meta.url)), '..', '..')` pour tous les scripts en `scripts/js/`
- **Relative imports** : Toujours `../../` pour atteindre la racine depuis `scripts/js/`
- **Python migration** : 8 phases, fondations d'abord (tracker-parse + tracker-utils + role-matcher), tests en parallèle
- **Python conventions** : `pathlib.Path`, `fcntl.flock` pour le locking, `httpx` pour HTTP, `rapidfuzz` pour fuzzy matching

## Issues & Workarounds

| Issue | Workaround | Status |
|-------|------------|--------|
| `doctor.mjs` root resolution cassée après move | Patch `projectRoot = join(__dirname, '..', '..')` | resolved |
| 54 scripts avec `dirname(import.meta.url)` pointant vers `scripts/js/` au lieu de la racine | Batch sed replacement pour ajouter `join(..., '..', '..')` | resolved |
| 12 scripts sans import `join` de `'path'` | Ajout `join` à l'import destructuring existant | resolved |
| `../plugins/` résolvait vers `scripts/plugins/` | `../../plugins/` dans tous les fichiers concernés | resolved |

---

## Action Items

- [ ] Commit les changements (283 fichiers)
- [ ] Vérifier que le serveur Django fonctionne toujours avec les nouveaux chemins
- [ ] Commencer Phase 1 de la migration Python (tracker-parse, tracker-utils, role-matcher, fingerprint-core)
- [ ] Créer `scripts/python/pyproject.toml` avec les dépendances

## Related Sessions

- `archives/chats/2026-07-15_session_portals-db-yaml-sync.md` — Migration portals.yml vers config/ + sync DB
- `archives/chats/2026-07-15_session_portals-kpi-hero-list-toggle.md` — KPI panel, hero, list/grid toggle
- `archives/chats/2026-07-15_session_profile-llm-extraction-variant.md` — Profile LLM extraction + variants

---

## Full Conversation Summary

1. L'utilisateur a demandé "What did we do so far?" — résumé de la session précédente (portals DB sync + portals UI + profile LLM extraction)
2. L'utilisateur a demandé de créer un plan de migration des scripts JS vers Python
3. Un task agent a catalogué les 85 scripts par catégorie (tracker: 18, scanner: 4, evaluation: 6, pipeline: 5, cv: 9, interview: 1, plugins: 4, admin: 10, export: 1, reply: 3, salary: 1, other: 7, tests: 12)
4. `PLAN-PYTHON-MIGRATION.md` créé (732 lignes) avec mapping un-à-un, structure de dossiers, patterns de code, estimation (14 semaines, 19 900 lignes Python)
5. L'utilisateur a demandé d'archiver la session
6. Vérification : doctor ✅, TypeScript ✅, zéro .mjs à la racine ✅
7. 283 fichiers modifiés/créés/renommés au total
