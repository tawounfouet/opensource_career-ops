# Django Remaining Implementation

Objectif : lister ce qu'il reste à implémenter pour que career-ops fonctionne à 100% avec Django, sans dépendre du backend Next.js pour les routes applicatives, et sans casser les garanties du système actuel.

Ce document complète `../django/next-steps.md`. Il ne remplace pas le plan d'action initial ; il sert de checklist exhaustive de migration restante.

## État Actuel

Le backend Django existe et couvre déjà une grande partie de l'API web.

Routes Django déjà implémentées ou bridgées :

- `GET /api/pipeline`
- `GET/POST /api/cv`
- `GET /api/cv-pdf`
- `GET/POST /api/profile`
- `GET/POST /api/portals`
- `POST /api/portals/verify`
- `POST /api/status`
- `POST /api/tracker/delete`
- `GET /api/doctor`
- `GET /api/version`
- `GET /api/whats-new`
- `GET /api/clis`
- `GET /api/followups`
- `POST /api/followups/log`
- `GET /api/usage`
- `GET /api/report/shape`
- `GET/POST /api/memory`
- `POST /api/explore`
- `POST /api/explore/add`
- `POST /api/explore/ai`
- `GET /api/explore/ai/known`
- `POST /api/run`
- `POST /api/apply/session`
- `POST /api/apply/prefill`
- `POST /api/apply/fill`
- `POST /api/apply/drive`
- `POST /api/apply/close`

Important : beaucoup de routes restent compatibles grâce au fallback Next.js. Le système n'est donc pas encore "100% Django" tant que le frontend dépend de ce fallback pour les cas complexes.

## Principes Non Négociables

- Ne jamais soumettre une candidature automatiquement.
- Ne jamais cliquer `Submit`, `Send application`, `Apply and submit`, ou équivalent final.
- Garder le fallback Next.js tant que l'équivalent Django n'a pas de tests de contrat et, pour Playwright, des tests navigateur réels.
- Ne jamais inventer de contenu candidat : CV, réponses, emails et formulaires restent bornés par les fichiers source autorisés.
- Ne pas supprimer les scripts `.mjs` tant qu'un test de compatibilité ne prouve pas l'équivalence Django.
- Garder les writes user-layer atomiques et compatibles avec le contrat de données.

## Définition De "100% Fonctionnel Avec Django"

Le système sera considéré comme 100% fonctionnel avec Django quand :

- Le frontend peut pointer vers Django avec `CAREER_OPS_API_URL` et utiliser toutes les fonctionnalités sans fallback Next.js obligatoire.
- Les routes Next.js deviennent de simples proxies ou peuvent être supprimées/remplacées par un frontend statique/API Django.
- Les workflows apply, scan, pipeline, tracker, CV/PDF, explore, run et assistant ont des tests Django couvrant les contrats principaux.
- Les tests Playwright réels sont exécutés en CI, pas seulement skippés.
- Les scripts Node restants sont soit explicitement conservés comme moteurs CLI, soit remplacés par une implémentation Python testée.
- Les opérations mutantes critiques ont des garde-fous : dry-run, locks, atomic writes, validation stricte des états.

## Gaps Bloquants

### 1. Dépendance Au Fallback Next.js

État :

- Les routes Next.js gardent encore une logique locale importante.
- Les sessions `apply` sont séparées entre sessions Django et sessions Next.
- Le fallback reste nécessaire pour les cas complexes, surtout `apply/drive` agentique complet.

À faire :

- Identifier toutes les routes Next qui contiennent encore une logique métier non couverte par Django.
- Ajouter une matrice route par route : `Django complete`, `Django partial`, `Next fallback required`, `Node script wrapper`.
- Une fois une route Django stable, réduire la route Next à un proxy strict.
- À terme, supprimer le stockage de sessions Playwright côté Next.

Critère de sortie :

- Aucune fonctionnalité utilisateur principale ne dépend d'une implémentation Next locale.

### 2. Playwright Django Pas Encore Validé En CI Réelle

État :

- Python Playwright est une dépendance backend.
- Les tests Playwright fixtures existent mais sont skippés si Chromium/Chrome manque.
- Chromium n'est pas encore installé dans le workflow backend CI.

À faire :

- Modifier `.github/workflows/backend-ci.yml` pour installer les navigateurs Playwright.
- Lancer `python -m playwright install chromium --with-deps` ou équivalent compatible GitHub Actions.
- Rendre les tests Playwright non-skippés en CI officielle.
- Garder le skip local si le navigateur manque sur la machine du développeur.

Critère de sortie :

- Les tests fixtures `direct-form`, `iframe-form`, `listing-search` passent en CI avec navigateur réel.

### 3. `apply/drive` Django Est Conservatif

État :

- Django supporte `drive` en mode `reach` minimal.
- Django refuse explicitement `goal=full`.
- Le moteur agentique complet reste côté Next pour les sessions Next.

À faire :

- Décider si Django doit vraiment porter le `drive full` ou si ce mode doit rester hors périmètre.
- Si oui, porter la boucle agentique côté Python :
  - snapshot des éléments interactifs avec références stables ;
  - appel planner CLI ;
  - parsing JSON d'action ;
  - exécution d'actions autorisées uniquement ;
  - refus structurel des submit controls ;
  - budget de tours ;
  - streaming NDJSON `step`, `done`, `error`.
- Ajouter tests sans navigateur pour :
  - parse action ;
  - refus submit ;
  - budget exhausted ;
  - session missing ;
  - mode full disabled/enabled selon flag.
- Ajouter tests Playwright fixtures pour :
  - Apply CTA ;
  - multi-step non-submit ;
  - blocage submit.

Critère de sortie :

- Soit `drive full` est explicitement abandonné/documenté, soit il existe côté Django avec tests de sécurité.

## Apply : Reste À Faire

### 4. Enrichir `apply/session` Pour Les ATS Connus

État :

- Django extrait `input`, `textarea`, `select`.
- Django inspecte les frames accessibles.
- Django filtre listing/search.
- Django retourne diagnostics et screenshots best-effort.
- Next a encore des enrichissements plus avancés, notamment Greenhouse schema.

À faire :

- Porter ou réimplémenter l'enrichissement Greenhouse :
  - détecter les URLs Greenhouse ;
  - récupérer le schema public si disponible ;
  - améliorer labels, types, required, options ;
  - détecter file upload CV/résumé.
- Ajouter Ashby :
  - détecter les pages Ashby ;
  - repérer les champs d'application ;
  - gérer options/select custom si possible.
- Ajouter Lever :
  - détecter formulaires Lever ;
  - enrichir labels/options ;
  - vérifier file fields.
- Gérer les champs custom non natifs :
  - `[role=combobox]`
  - `[role=radio]`
  - `[role=checkbox]`
  - `[contenteditable=true]`
  - composants React Select.

Critère de sortie :

- Les principaux ATS produisent des champs propres et préremplissables sans passer par le fallback Next.

### 5. Améliorer `apply/fill`

État :

- Django remplit les champs simples.
- Django utilise le frame choisi.
- Django évite les uploads non maîtrisés.
- Django bloque les consentements légaux.
- Django détecte la navigation après fill.

À faire :

- Supporter les combobox custom sans presser `Enter` si risque de submit.
- Supporter radios groupés avec mapping option.
- Supporter checkboxes custom stylées.
- Ajouter vérification post-fill :
  - relire les valeurs ;
  - signaler divergences ;
  - signaler validations visibles ;
  - signaler champs requis non remplis.
- Ajouter attachement CV sécurisé :
  - résoudre le PDF côté serveur uniquement ;
  - attacher uniquement aux champs identifiés resume/CV ;
  - ne jamais attacher cover letter/portfolio automatiquement sans confirmation.
- Ajouter screenshots par étape si activé.

Critère de sortie :

- `apply/fill` Django atteint la robustesse actuelle de Next sur les formulaires simples et ATS majeurs.

### 6. Gestion Des Sessions Browser

État :

- Sessions Django en mémoire process.
- Pas de persistance.
- Pas de support multi-process robuste.

À faire :

- Ajouter un gestionnaire de sessions plus explicite :
  - TTL configurable ;
  - fermeture idle ;
  - fermeture browser global quand plus aucune session ;
  - endpoint admin/debug local pour compter les sessions ouvertes.
- Gérer multi-worker :
  - documenter que Playwright sessions nécessitent sticky process ;
  - ou limiter le backend local à un seul worker ;
  - ou implémenter un broker de session, si vraiment nécessaire.
- Ajouter cleanup sur shutdown si possible.

Critère de sortie :

- Pas de fuite durable de contextes navigateur.
- Le comportement est documenté pour dev/local/prod.

## Pipeline, Scan, Explore

### 7. Remplacer Les Wrappers Node Par Services Python

État :

- Certaines routes Django orchestrent encore des scripts Node.
- C'est acceptable temporairement, mais pas "100% Django".

À faire :

- Lister tous les appels `run_node_script` et `subprocess ["node", ...]`.
- Classer :
  - garder comme moteur officiel ;
  - wrapper temporaire ;
  - remplacer par Python.
- Remplacer progressivement :
  - `followup-cadence.mjs`
  - `stats.mjs`
  - `analyze-patterns.mjs`
  - `scan-ats-full.mjs`
  - `scan.mjs`
  - `merge-tracker.mjs`
  - `verify-pipeline.mjs`
  - `normalize-statuses.mjs`
  - `dedup-tracker.mjs`

Critère de sortie :

- Les scripts Node ne sont plus nécessaires pour les routes Django principales, ou sont explicitement documentés comme moteurs CLI conservés.

### 8. Scanner ATS En Django

État :

- Django peut wrapper scanner existant.
- Scanner complet reste Node.

À faire :

- Implémenter clients Python pour :
  - Greenhouse job boards ;
  - Lever postings ;
  - Ashby postings ;
  - Workday si raisonnable ;
  - source registries depuis `portals.yml`.
- Dédupliquer URLs avec la même logique canonique.
- Respecter `data/blacklist.md`.
- Respecter filtres `portals.yml`.
- Écrire scan history de manière atomique.
- Exposer stream NDJSON compatible frontend.

Critère de sortie :

- `POST /api/explore` ne dépend plus de `scan-ats-full.mjs`.

### 9. Pipeline Batch Django

État :

- `POST /api/run` existe avec streaming.
- Batch/headless complet reste surtout script/CLI.

À faire :

- Porter réservation report numbers en Python.
- Porter merge tracker additions.
- Gérer batch worker orchestration :
  - range reservation ;
  - one worker per URL ;
  - cleanup stale reservations ;
  - merge final ;
  - failure report.
- Ajouter endpoints :
  - start batch ;
  - stream batch progress ;
  - list batch runs ;
  - cancel batch.

Critère de sortie :

- Un batch d'évaluations peut être lancé et suivi via Django sans orchestration Next/Node.

## Tracker Et Données

### 10. Tracker Markdown Vers Service Canonique

État :

- Django lit et modifie déjà certaines données.
- Le markdown reste source de vérité.

À faire :

- Centraliser toutes les opérations tracker dans un service Python :
  - parse ;
  - validate ;
  - update status ;
  - delete dry-run ;
  - delete real ;
  - dedup ;
  - normalize states ;
  - merge additions.
- Garder compatibilité exacte markdown.
- Ajouter lock fichier partagé.
- Ajouter tests golden avec tables markdown réelles.

Critère de sortie :

- Aucun script Node n'est nécessaire pour modifier `data/applications.md`.

### 11. Atomic Writes Et Locks

État :

- Certaines écritures Django sont atomiques.
- Toutes les écritures ne sont pas encore auditées.

À faire :

- Auditer toutes les écritures Django.
- Utiliser systématiquement `atomic_write`.
- Ajouter locks pour fichiers concurrents :
  - `data/applications.md`
  - `data/pipeline.md`
  - `data/scan-history.tsv`
  - `data/follow-ups.md`
  - `modes/_profile.md`
  - `portals.yml`
  - `config/profile.yml`
- Ajouter tests de non-corruption basiques.

Critère de sortie :

- Les writes critiques sont atomiques et protégés contre les collisions évidentes.

## CV, PDF, Documents

### 12. Génération PDF Django

État :

- Django sert les PDFs existants depuis `output/`.
- La génération reste Node/Playwright.

À faire :

- Décider si la génération reste Node ou passe Python.
- Si Python :
  - renderer HTML ;
  - templates compatibles ;
  - génération PDF ;
  - validation taille/pages ;
  - stockage dans `output/`.
- Si Node conservé :
  - documenter que `generate-pdf.mjs` reste moteur officiel ;
  - exposer wrapper Django robuste ;
  - streamer logs.

Critère de sortie :

- Le bouton génération CV/PDF fonctionne via Django avec logs et erreurs propres.

### 13. Tailoring CV Et Cover Letter

État :

- Source de vérité disponible.
- Certains workflows restent CLI/script.

À faire :

- Exposer un endpoint Django clair pour :
  - tailor CV draft ;
  - generate cover letter draft ;
  - verify facts ;
  - generate PDF.
- Ajouter garde-fous anti-fabrication.
- Ajouter tests de contrat sur prompts/outputs structurés.

Critère de sortie :

- Le frontend peut générer, vérifier et servir un CV/PDF via Django.

## Assistant Et Agents

### 14. `/api/assistant`

État :

- Route présente côté Django via app runner, mais couverture fonctionnelle à auditer.

À faire :

- Auditer le contrat frontend attendu.
- Ajouter tests de contrat :
  - bad JSON ;
  - CLI missing ;
  - stream text ;
  - error handling ;
  - no write mode if read-only.
- Vérifier persistance éventuelle des runs.

Critère de sortie :

- Assistant web fonctionne intégralement via Django.

### 15. Runs Save / Historique

État :

- `POST /api/runs/save` existe.
- Le modèle runner existe.

À faire :

- Vérifier que toutes les données nécessaires sont sauvegardées.
- Ajouter list/detail endpoints si le frontend en a besoin.
- Ajouter migration/test admin.
- Ajouter stratégie de purge locale si les logs grossissent.

Critère de sortie :

- Les runs importants sont consultables et testés côté Django.

## Auth, Sécurité, Local-First

### 16. Auth Locale Et Permissions

État :

- Backend local de migration.
- Pas encore de modèle sécurité complet.

À faire :

- Décider mode officiel :
  - local-only sans auth ;
  - token local ;
  - Django session auth ;
  - user accounts.
- Si exposable réseau :
  - CSRF/CORS stricts ;
  - auth obligatoire ;
  - no public bind par défaut ;
  - secret key safe ;
  - debug off.
- Ajouter endpoints mutatifs derrière permissions si nécessaire.

Critère de sortie :

- Le backend est sûr pour l'usage local prévu, et impossible à exposer accidentellement sans garde-fous.

### 17. Admin Django

État :

- Models/admin existent pour plusieurs apps.

À faire :

- Créer et documenter superuser.
- Vérifier admin pour :
  - accounts ;
  - tracker ;
  - portals ;
  - cv ;
  - runner.
- Ajouter search fields/list filters utiles.
- Ajouter read-only fields pour logs.

Critère de sortie :

- Admin Django utile pour inspection/debug local.

## CI, Qualité, Packaging

### 18. CI Backend Complète

État :

- Workflow backend CI existe.
- Playwright navigateur non obligatoire.

À faire :

- Installer Chromium en CI.
- Exécuter tests Playwright non-skippés.
- Ajouter lint/format Python si souhaité :
  - ruff ;
  - black ou ruff format ;
  - mypy optionnel.
- Ajouter coverage minimal si utile.
- Vérifier `manage.py migrate --noinput` en CI.

Critère de sortie :

- CI prouve Django + Playwright + migrations + tests.

### 19. Packaging Backend

État :

- `backend/pyproject.toml` existe.
- `.venv` local utilisé.

À faire :

- Documenter installation :
  - Python version ;
  - venv ;
  - `pip install -e "backend[dev]"` ;
  - Playwright install.
- Ajouter scripts Makefile ou npm wrappers :
  - `backend:test`
  - `backend:run`
  - `backend:migrate`
  - `backend:playwright-install`
- Vérifier compatibilité Python officielle.

Critère de sortie :

- Un nouveau contributeur peut lancer Django et les tests depuis README.

### 20. Observabilité

État :

- Certains logs existent.
- Apply prefill écrit un log.

À faire :

- Standardiser logs :
  - request id ;
  - route ;
  - duration ;
  - error code ;
  - CLI used ;
  - tokens/cost when available.
- Ajouter debug logs locaux dans `.career-ops-web/`.
- Ne jamais logger secrets, CV complet inutilement, réponses sensibles de formulaires.

Critère de sortie :

- Les échecs utilisateur sont diagnostiquables sans exposer de données sensibles.

## Frontend Cleanup

### 21. Réduire Les Routes Next

État :

- Le frontend contient encore beaucoup de logique API locale.

À faire :

- Transformer progressivement les routes Next en proxies minces.
- Supprimer les duplications de parsing.
- Supprimer les sessions Playwright Next quand Django couvre le chemin complet.
- Garder un fallback volontairement documenté uniquement pendant la migration.

Critère de sortie :

- Le frontend devient une UI, pas un second backend.

### 22. UX Des États Django/Fallback

État :

- Le fallback est transparent.

À faire :

- Ajouter indicateur debug optionnel :
  - backend utilisé : Django ou Next fallback ;
  - diagnostics apply/session ;
  - reason fallback.
- Ne pas polluer l'UX normale.

Critère de sortie :

- En debug, on sait quelle couche a traité une action.

## Tests À Ajouter

Tests unitaires Django :

- Parsing tracker golden files.
- Status validation.
- Atomic writes.
- Follow-up logging.
- Profile/portals patch.
- Apply field classification.
- Apply fill guards.
- Apply drive guards.
- CLI resolver.
- Run stream contracts.

Tests intégration Django :

- Pipeline read/write.
- Tracker delete dry-run/real.
- Explore scan wrapper.
- Run stream with fake CLI.
- Apply session with fixtures.
- Apply prefill with fake CLI.
- Apply fill with fake page.

Tests Playwright réels :

- Direct form.
- Iframe form.
- Listing/search form.
- Apply CTA reveals form.
- Submit button refused.
- Consent checkbox not auto-ticked.
- File upload only for resume/CV when PDF exists.

Tests frontend :

- Django proxy success.
- Django unavailable fallback.
- Stream proxy preserves NDJSON.
- Binary PDF proxy.
- Apply session ownership routing.

## Migration Suggested Order

1. Activer Chromium en CI backend.
2. Rendre les tests Playwright fixtures fiables.
3. Enrichir `apply/session` pour Greenhouse/Ashby/Lever.
4. Renforcer `apply/fill` pour combobox/radio/custom widgets.
5. Décider le sort de `apply/drive full`.
6. Centraliser tracker writes en Python.
7. Remplacer ou officialiser les scripts Node restants.
8. Porter scanner ATS en Python ou documenter Node comme moteur officiel.
9. Porter génération PDF ou documenter Node comme moteur officiel.
10. Réduire les routes Next à des proxies minces.
11. Durcir auth/admin/packaging.
12. Mettre à jour README et docs de contribution.

## Definition Of Done Finale

- `backend/.venv/bin/pytest backend -q` passe sans skip obligatoire en CI.
- `npm run typecheck` dans `web/` passe.
- `npm test` dans `web/` passe.
- `backend/manage.py check` passe.
- `backend/manage.py makemigrations --check --dry-run` passe.
- Les tests Playwright Django passent en CI.
- Le frontend fonctionne avec Django actif.
- Le frontend reste utilisable si Django est absent uniquement dans un mode fallback explicitement supporté.
- Aucune candidature ne peut être soumise automatiquement.
- Les routes mutantes ont tests d'erreur et de succès.
- Les scripts Node restants sont soit supprimés, soit documentés comme moteurs conservés.
