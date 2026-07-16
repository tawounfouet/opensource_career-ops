# Next Steps — Migration Django

Objectif : migrer vers le backend Django par paliers, sans casser le frontend Next.js ni remplacer les scripts `.mjs` avant d'avoir une équivalence vérifiée.

## 1. Brancher Next.js sur Django avec fallback

- Statut : implémenté pour les routes JSON principales, les streams agent, le PDF inline et la tranche `apply/session` + `apply/prefill` + `apply/fill` + `apply/drive` minimal.
- `CAREER_OPS_API_URL=http://localhost:8000` est documenté dans `web/.env.example`.
- Les routes suivantes essaient Django d'abord, puis retombent sur l'implémentation Next.js locale :
  - `GET /api/pipeline`
  - `GET/POST /api/cv`
  - `GET/POST /api/profile`
  - `GET/POST /api/portals`
  - `POST /api/status`
  - `GET /api/doctor`
  - `GET /api/clis`
  - `GET /api/version`
  - `POST /api/tracker/delete` avec `dryRun`
  - `GET /api/followups`
  - `GET /api/usage`
  - `POST /api/followups/log`
  - `GET /api/report/shape`
  - `GET/POST /api/memory`
  - `POST /api/explore`
  - `POST /api/explore/add`
  - `GET /api/explore/ai/known`
  - `GET /api/cv-pdf`
  - `POST /api/explore/ai`
  - `POST /api/run`
  - `POST /api/apply/session` avec fallback Next si Django ne peut pas ouvrir la page.
  - `POST /api/apply/prefill` pour les sessions créées par Django, avec fallback Next pour les sessions Next.
  - `POST /api/apply/fill` pour les sessions créées par Django, avec fallback Next pour les sessions Next.
  - `POST /api/apply/drive` en mode Django minimal `reach` pour sessions Django, avec fallback Next pour les sessions Next.
  - `POST /api/apply/close` pour fermer les sessions Django ou Next selon leur origine.
- Non migré volontairement dans cette tranche :
  - `POST /api/apply/drive` en mode `full` agentique côté Django : refusé explicitement pour éviter tout risque d'automatisation de soumission.

## 2. Compléter les routes API manquantes

Priorité de couverture :

- `POST /api/apply/session`
- `POST /api/apply/prefill`
- `POST /api/apply/fill`
- `POST /api/apply/drive`
- `POST /api/apply/close`
- `POST /api/assistant`

Approche recommandée : commencer par des wrappers Django autour du comportement Node existant, puis remplacer par du Python seulement quand le comportement est testé.

## 3. Remplacer progressivement les scripts `.mjs`

Ordre recommandé :

1. Scripts simples et déterministes :
   - `doctor.mjs`
   - parsing tracker
   - status writer
   - portals/profile writers
2. Scripts de lecture/analyse :
   - `followup-cadence.mjs`
   - `stats.mjs`
   - `analyze-patterns.mjs`
3. Workflows lourds à garder en orchestration Node au début :
   - `scan.mjs`
   - `scan-ats-full.mjs`
   - `pipeline`
   - `apply`
   - génération PDF

Ne supprimer un script Node que lorsqu'un test de compatibilité prouve que la sortie Django est équivalente.

## Recommandation actuelle

Statut : `GET /api/cv-pdf`, CI backend, `POST /api/explore/ai`, `POST /api/run`, `POST /api/apply/session`, `POST /api/apply/prefill`, `POST /api/apply/fill` et `POST /api/apply/drive` minimal sont implémentés.

Ce qui a été ajouté :

- Django sert maintenant le PDF inline depuis `output/`, comme Next.
- Tests backend : PDF trouvé, `Content-Type: application/pdf`, PDF absent.
- Workflow GitHub Actions backend : install, `manage.py check`, migrations dry-run, pytest.
- `apply/session` Django ouvre une page via Playwright Python, inspecte les frames accessibles, choisit le frame le plus riche, filtre les formulaires listing/search, retourne des diagnostics et des screenshots best-effort.
- `apply/prefill` Django streame le même contrat NDJSON que Next (`log`, `error`, `done`) et lit les champs de la session Django.
- `apply/fill` Django remplit les sessions Django simples sans jamais cliquer Submit/Send/Apply, ignore les uploads non maîtrisés et laisse les consentements légaux à l'utilisateur.
- `apply/drive` Django en mode `reach` détecte un formulaire déjà présent ou clique uniquement un CTA Apply/Postuler/Candidater non-submit, puis ré-extrait les champs.
- Next marque les sessions créées par Django pour router `prefill`, `fill`, `drive` et `close` vers Django, tout en gardant le fallback Next pour les sessions Next.

Prochaine tranche recommandée : enrichir les ATS connus ou activer Chromium en CI pour rendre les tests Playwright obligatoires.

Raison :

- `run` est maintenant migré avec streaming NDJSON et tests de contrat.
- `session/prefill/fill/drive` couvrent maintenant le chemin simple Django.
- La version Django reste volontairement conservative : pas de planner LLM browser-driving côté Django, pas de mode `full`.
- Le gain suivant vient soit de la compatibilité ATS (Greenhouse/Ashby/Lever), soit de la validation CI avec navigateur réel.

Ordre conseillé :

1. Lire toutes les routes `web/src/app/api/apply/*`.
2. Distinguer routes de session browser, diagnostic, prefill et drive/fill.
3. Migrer d'abord les routes read-only/diagnostic.
4. Garder les actions browser mutantes derrière des tests explicites et fallback Next.
5. Ne jamais automatiser le submit final.

## Audit `apply/*`

État actuel :

- `apply/session` peut ouvrir une session Django via Playwright Python. Si Django échoue ou est absent, Next garde son ancien moteur.
- `apply/prefill` lit les sessions Django et streame le même NDJSON que Next. Les sessions Next restent préremplies par le fallback Next.
- `apply/close` ferme la session du bon côté grâce au marqueur de session Django côté Next.
- `apply/fill` écrit dans les sessions Django simples ou dans les sessions Next selon l'origine. Aucun chemin ne soumet l'application.
- `apply/drive` côté Django est minimal `reach-only`. Côté Next, le moteur agentique complet reste disponible pour les sessions Next.

Décision de migration :

- Garder le marqueur de session Django côté Next tant que toutes les routes `apply/*` ne sont pas migrées.
- Garder `POST /api/apply/drive` Django en mode conservative `reach-only` tant que l'équivalent agentique Python n'est pas testé avec Playwright réel.
- Ne jamais automatiser le submit final : `fill` peut préremplir et handoff, mais pas cliquer Submit/Send/Apply.
- Garder le fallback Next pour les sessions complexes créées par l'ancien moteur Next.

Prochaine étape apply :

1. Décider si la CI backend installe Chromium pour rendre les tests Playwright non-skippés.
2. Enrichir progressivement les ATS connus (Greenhouse/Ashby/Lever) sans retirer le fallback Next.
3. Ajouter diagnostics plus fins par frame si des cas réels échouent.
4. Garder `drive` Django en `reach-only` tant que le mode agentique complet n'a pas de tests navigateur fiables.

## 4. Durcir auth, permissions et admin

- Créer et tester un superuser Django.
- Vérifier l'admin pour :
  - applications
  - pipeline jobs
  - portals
  - search queries
  - run logs
  - users
- Ajouter des permissions/API auth avant toute exposition réseau réelle.
- Garder le mode local simple pendant la phase de migration.

## 5. Ajouter la CI backend

Ajouter un job CI dédié :

```bash
cd backend
python -m pip install -e ".[dev]"
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
pytest -q
```

## 6. Critères de passage à l'étape suivante

- Le frontend fonctionne avec Django lancé.
- Le frontend fonctionne encore sans Django grâce au fallback Next.js.
- Les writes user-layer restent atomiques et ne créent pas de données inventées.
- Les tests backend passent.
- Les routes migrées ont une réponse JSON compatible avec les routes Next.js existantes.
