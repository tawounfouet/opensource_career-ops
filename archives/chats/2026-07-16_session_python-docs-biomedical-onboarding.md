# Session: Python Docs + Biomedical Onboarding + Portals Automation

**Date**: 2026-07-16
**Agent(s)**: opencode/deepseek-v4-pro
**Phase**: build + docs

---

## Intent

1. Documenter exhaustivement `scripts/python/` (docs + diagrammes)
2. Archiver `scripts/js/` en `scripts/archived-js/` avec refs critiques mises a jour
3. Completer l'onboarding d'Audrey Kwekeu — profil biomedical/qualite/reglementaire
4. Analyser les limites du scanner pour le secteur biomedical et proposer des alternatives
5. Concevoir un plan d'automatisation de `portals.yml`

## Outcome

17 fichiers de documentation Python crees avec diagrammes ASCII, onboarding biomedical termine (cv.md, profile.yml, portals.yml biomedical), diagnostic complet du secteur biomedical, et plan d'automatisation hybride de portals.yml (4 approches combinees en pipeline 5 couches).

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|----------|-----------|------------------------|
| 1 | Archivage JS via `git mv scripts/js → scripts/archived-js` plutot que suppression | Conserver la reference, historique git preserve | Supprimer, garder en place avec ARCHIVED.md |
| 2 | Mots-cles `title_filter.positive` biomedical au lieu de AI/ML | Profil d'Audrey = Qualite/Reglementaire, pas AI | Laisser AI/ML, mixer les deux secteurs |
| 3 | `scan_method: websearch` pour les boites pharma/DM | Les pharma/DM n'utilisent pas Greenhouse/Lever | Ajouter des parsers locaux (trop de travail) |
| 4 | Workflow recommande : curation manuelle APEC/Indeed → evaluation auto | Scanner inadapte au biomedical, evaluation reste pertinente | Forcer le scanner (inefficace), abandonner career-ops (trop radical) |
| 5 | Approche hybride A+B+C+D pour automatiser portals.yml | Les approches sont complementaires, pas concurrentes | Choisir une seule approche |
| 6 | Diagrammes ASCII (box-drawing) plutot que Unicode | Unicode causait des erreurs d'ecriture JSON | Mermaid, PlantUML (dependances externes) |

## Files Created

| File | Purpose |
|------|---------|
| `scripts/python/docs/admin.md` | Doc package admin (doctor, update, validation) |
| `scripts/python/docs/cv.md` | Doc package CV generation |
| `scripts/python/docs/evaluation.md` | Doc package evaluation LLM |
| `scripts/python/docs/export.md` | Doc package export/dashboard |
| `scripts/python/docs/interview.md` | Doc package interview (STAR matching) |
| `scripts/python/docs/other.md` | Doc package utilities diverses |
| `scripts/python/docs/pipeline.md` | Doc package pipeline (extraction, liveness) |
| `scripts/python/docs/plugins.md` | Doc package plugins |
| `scripts/python/docs/reply.md` | Doc package reply classification |
| `scripts/python/docs/salary.md` | Doc package salary gap |
| `scripts/python/docs/scanner.md` | Doc package scanner |
| `scripts/python/docs/testing.md` | Doc structure de tests (28 files, 237 tests) |
| `scripts/python/docs/tracker.md` | Doc package tracker |
| `scripts/python/docs/cli-bridge.md` | Doc CLI bridge (npm → python -m) |
| `scripts/python/ARCHITECTURE.md` | 4 diagrammes ASCII (system, workflow, CLI, data stores) |
| `scripts/python/INDEX.md` | Index rapide de tous les packages |
| `scripts/python/README.md` | Overview + quick start (mise a jour) |
| `docs/guides/biomedical-diagnostic.md` | Diagnostic scanner pour le biomedical |
| `docs/guides/portals-customization.md` | Guide etape par etape de personnalisation portals.yml |
| `docs/guides/portals-management-analysis.md` | Analyse de l'alimentation de portals.yml |
| `docs/plans/portals-automation.md` | Plan d'automatisation (4 approches) |
| `docs/plans/portals-automation-hybrid.md` | Architecture hybride (pipeline 5 couches) |
| `scripts/archived-js/ARCHIVED.md` | README d'archivage JS |
| `cv.md` | CV d'Audrey Kwekeu (4 experiences, 3 projets, 4 formations) |
| `portals.yml.backup-ai-tech` | Backup du portals AI/tech original |
| `config/portals.yml.backup-ai-tech` | Backup config du portals AI/tech original |

## Files Modified

| File | Change summary |
|------|----------------|
| `config/profile.yml` | Archetypes biomedical (Quality/Regulatory au lieu de AI/ML), narrative, proof points, objectif |
| `config/portals.yml` | 24 entreprises pharma/DM + mots-cles biomedical + scan_method: websearch |
| `portals.yml` | Sync avec config/ (copie racine) |
| `AGENTS.md` | Stack Python primaire, JS fallback, refs en python -m |
| `package.json` | 42 scripts npm → python -m |
| `batch/batch-runner.sh` | node → python -m |
| `.gitignore` | `/cv.md` (scope root only) |
| `scripts/python/README.md` | Rewrite complet (Python primary runtime, docs links) |
| `CONTRIBUTING.md` | scripts/js → scripts/archived-js, ajout pytest |
| `.github/workflows/test.yml` | scripts/js → scripts/archived-js |
| `.github/workflows/plugin-registry-validate.yml` | scripts/js → scripts/archived-js |
| `.github/PULL_REQUEST_TEMPLATE.md` | scripts/js → scripts/archived-js |
| `DOCKER.md` | scripts/js → scripts/archived-js |

## Files Renamed

| From | To |
|------|-----|
| `scripts/js/` (85 fichiers) | `scripts/archived-js/` |

## Key Context

- **Scanner biomedical inefficace** : 28 746 entreprises scannees sur Workday → 0 offre biomedicale. Les pharma/DM n'utilisent pas Greenhouse/Lever.
- **portals.yml 100% manuel** : Aucune automatisation. Template AI/tech. 5 methodes semi-manuelles existent (Django admin, LLM extraction, discovery bridge) mais aucune n'est entierement automatique.
- **SSL macOS corrige** : `Install Certificates.command` execute, plus besoin de `SSL_CERT_FILE`.
- **Profil Audrey** : Ingenieure Qualite & Affaires Reglementaires, pas AI Engineer. Le `config/profile.yml` original etait configure pour un profil AI/ML (copie du template santifer).
- **Pipeline hybride** : 5 couches (Source → Enrichment → Validation → Confirmation → Integration) combinant Django command + Agent Playwright + API REST + Job board scraping.
- **237 tests** : Tous les tests Python passent (`pytest scripts/python/tests -q`).

## Commands Run

| Command | Purpose | Result |
|---------|---------|--------|
| `python -m scripts.python.scanner.scan --company Anthropic --dry-run` | Test scanner | 417 offres, 59 retenues |
| `npm run scan` | Scan complet biomedical | 5306 offres, 0 biomedical |
| `python -m scripts.python.scanner.scan_ats_full --ats workday` | Test ATS discovery | 28746 companies, 0 offre |
| `python -m scripts.python.admin.doctor --json` | Verification setup | onboardingNeeded: false |
| `python -m pytest scripts/python/tests -q` | Suite de tests | 237 passed |
| `/Applications/Python\ 3.12/Install\ Certificates.command` | Fix SSL macOS | Certificats installes |
| `python -c "verify greenhouse/lever slugs"` | Test APIs pharma | 0/16 sur Greenhouse/Lever |
| `git mv scripts/js scripts/archived-js` | Archivage JS | 85 fichiers deplaces |
| `git push origin main` | Push commits | 4 pushes, tous OK |

## Patterns Established

- **Documentation exhaustive** : 17 fichiers .md dans `scripts/python/docs/` + 3 fichiers racine (ARCHITECTURE, INDEX, README)
- **Diagrammes ASCII** : Box-drawing characters (+, -, |) pour la compatibilite JSON, pas d'Unicode
- **Guide biomedical** : Workflow curation manuelle + evaluation auto recommande pour secteurs hors-tech
- **Plan hybride** : Pipeline 5 couches pour automatiser portals.yml, pret a implementer
- **Archivage JS** : `scripts/archived-js/` avec ARCHIVED.md, refs critiques mises a jour, docs non modifiees

## Issues & Workarounds

| Issue | Workaround | Status |
|-------|------------|--------|
| SSL macOS: CERTIFICATE_VERIFY_FAILED | `Install Certificates.command` | resolved |
| Scanner lit `config/portals.yml`, pas `portals.yml` racine | Sync manuelle (`cp portals.yml config/portals.yml`) | resolved |
| Pharma/DM: 0 entreprise sur Greenhouse/Lever | `scan_method: websearch` (non implemente) → curation manuelle recommandee | open |
| `scan_ats_full --since 14` non respecte (toujours --since 3) | Bug dans scan_ats_full.py (argument parsing) | open |
| JSON write error avec caracteres Unicode | ASCII box-drawing (+, -, |) au lieu de Unicode | resolved |
| `cv.md` bloque par `.gitignore` global | `/cv.md` (scope root only) | resolved |

## Action Items

- [ ] Implementer Phase 1 de l'approche hybride portals (`discover_portals` management command)
- [ ] Fix `scan_ats_full --since` argument parsing bug
- [ ] Implementer `scan_method: websearch` provider pour le scanner
- [ ] Alimenter `pipeline.md` avec des offres APEC/Indeed pour Audrey
- [ ] Evaluer la premiere offre biomedicale avec `npm run openai:eval`
- [ ] Generer le premier CV adapte avec `npm run pdf`

## Related Sessions

- `archives/2026-07-15_session-ses_09f1_scripts-migration-python.md` — Migration JS→Python (85 scripts)
- `archives/chats/2026-07-15_session_python-migration-scan-parity.md` — Scanner Python parity
- `archives/chats/2026-07-15_session_scripts-migration-python.md` — Scripts migration archive
- `docs/plans/python-migration-remaining.md` — Plan de migration complet

---

## Full Conversation Summary

1. Creation de la doc exhaustive `scripts/python/` — 14 fichiers par package + INDEX + ARCHITECTURE + README
2. Ajout de 4 diagrammes ASCII au fichier ARCHITECTURE.md
3. Ajout de diagrammes ASCII aux 14 fichiers de doc par package
4. Archivage de `scripts/js/` → `scripts/archived-js/` (85 fichiers) + mise a jour des refs critiques
5. Onboarding d'Audrey Kwekeu :
   - Tentative d'extraction LinkedIn → bloque (auth required)
   - Creation de `cv.md` a partir du CV fourni (JSON + Markdown)
   - Mise a jour `config/profile.yml` (biomedical au lieu de AI)
   - Mise a jour `portals.yml` (entreprises pharma/DM, mots-cles biomedical)
6. Test du scanner biomedical → 0 offre pertinente sur 5306 resultats
7. Verification des APIs Greenhouse/Lever pour 16 boites pharma → 0/16
8. Diagnostic : le scanner est concu pour la tech, inadapte au biomedical
9. Creation du guide de personnalisation portals.yml + diagnostic biomedical
10. Analyse de l'alimentation de portals.yml (5 methodes, toutes manuelles)
11. Plan d'automatisation : 4 approches (Django command, Agent skill, API REST, scraper)
12. Architecture hybride : pipeline 5 couches combinant les 4 approches
13. Archivage de session
