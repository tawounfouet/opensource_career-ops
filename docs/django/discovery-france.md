# Discovery France -- Statut Et Prochaines Étapes

Objectif : synthétiser ce qui a été implémenté pour le module de découverte déterministe d'offres France, ce qui reste à faire, et l'ordre recommandé pour rendre le système utile au quotidien.

Contexte : ce document fait suite à `../plans/_archive/action-france-jobboards.md`. L'implémentation backend V1 a été réalisée avec Claude Code : app Django `apps.discovery`, modèles, connecteurs, API, commandes, scoring, déduplication et tests hors-ligne.

## Résumé Exécutif

Le backend Discovery France est maintenant largement en place.

Ce qui est couvert :

- Modèles Django pour sources, profils, runs, offres brutes, offres normalisées, ranking, digest quotidien et décisions utilisateur.
- Pipeline déterministe : collecte, normalisation, déduplication, ranking, digest.
- Connecteurs V1 recommandés du plan.
- API Django pour sources, profil, run, digest, décisions et export pipeline.
- Commandes de management pour seed, run, rank et export.
- Tests hors-ligne des connecteurs et du pipeline.

Ce qui manque encore pour rendre le module pleinement quotidien :

- Brancher le scheduling nocturne.
- Ajuster le scoring/profil après quelques revues matinales.
- Ajouter une page sources/runs si le debugging devient nécessaire.
- Décider ensuite si on active France Travail/OAuth et si on ajoute l'IA.

Recommandation initiale : valider d'abord la chaîne avec 5-10 boards ATS réels (`greenhouse`, `lever`, `ashby`), puis construire l'UI.

Statut du premier run réel : validé le 2026-07-14 avec ATS publics Greenhouse, Lever et Ashby.

Statut UI matinale : `/discovery` implémentée côté Next.js.

## Ce Qui A Été Implémenté

### 1. App Django `apps.discovery`

Présente dans :

- `backend/apps/discovery/`
- `backend/apps/discovery/models.py`
- `backend/apps/discovery/views.py`
- `backend/apps/discovery/serializers.py`
- `backend/apps/discovery/urls.py`
- `backend/apps/discovery/services/`
- `backend/apps/discovery/connectors/`
- `backend/apps/discovery/management/commands/`

Le module est intégré dans Django :

- `backend/config/settings/base.py` inclut `apps.discovery`.
- `backend/config/urls.py` inclut `/api/discovery/`.

### 2. Modèles De Données

Modèles implémentés :

- `JobSource` : source/jobboard/ATS, stratégie, config, état, rate limit, notes TOS.
- `SearchProfile` : critères utilisateur déterministes.
- `DiscoveryRun` : run de collecte.
- `RawJobPosting` : capture brute par source.
- `JobPosting` : offre normalisée/dédupliquée.
- `JobRanking` : score déterministe et explications.
- `DailyJobDigest` : short-list quotidienne.
- `DailyJobDigestItem` : décision utilisateur par offre.

Couverture fonctionnelle :

- Sources activables/désactivables.
- Stratégies différenciées : `api`, `ats_api`, `html_public`, `manual_import`, `disabled`.
- Profil utilisateur local-first.
- Historique de runs.
- Digest quotidien prêt pour l'UI.

### 3. Services Déterministes

Services présents :

- `criteria.py`
- `normalize.py`
- `dedup.py`
- `scoring.py`
- `scheduler.py`
- `exporters.py`

Flux supporté :

1. Charger un `SearchProfile`.
2. Charger les `JobSource` activées.
3. Exécuter les connecteurs.
4. Stocker les offres brutes.
5. Normaliser vers `JobPosting`.
6. Dédupliquer.
7. Scorer/ranker.
8. Créer un `DailyJobDigest`.
9. Exporter vers `data/pipeline.md` si l'utilisateur choisit `evaluate`.

### 4. Connecteurs Implémentés

Connecteurs présents :

- `greenhouse`
- `lever`
- `ashby`
- `apec`
- `france_travail`
- `wttj`
- `hellowork`
- `linkedin_manual`
- `indeed_manual`
- `fake`

Tableau d'état :

| Connecteur | Source | Stratégie | Statut par défaut | Commentaire |
|---|---|---|---|---|
| `greenhouse` | ATS | `ats_api` | activable avec config | Recommandé pour premier run réel |
| `lever` | ATS | `ats_api` | activable avec config | Recommandé pour premier run réel |
| `ashby` | ATS | `ats_api` | activable avec config | Recommandé pour premier run réel |
| `apec` | APEC | `api` | opt-in | À valider sur vrai endpoint |
| `france_travail` | France Travail | `api` OAuth | opt-in | Nécessite credentials/token |
| `wttj` | Welcome to the Jungle | API Algolia | opt-in | Nécessite `app_id`/`api_key` |
| `hellowork` | HelloWork | `html_public` JSON-LD | opt-in | Rate limit strict |
| `linkedin_manual` | LinkedIn | `manual_import` | opt-in | Aucun scraping automatisé |
| `indeed_manual` | Indeed | `manual_import` | opt-in | Aucun scraping automatisé |
| `fake` | fixtures | test | test-only | Pour tests et démo locale |

Posture légale/technique :

- LinkedIn et Indeed ne sont pas scrapés automatiquement.
- Les jobboards France sont opt-in.
- Les connecteurs réseau sont testables hors-ligne via injection de `fetch`.
- Les ATS directs sont la voie la plus stable et la moins risquée.

### 5. API Django

Endpoints présents :

- `GET /api/discovery/sources`
- `GET /api/discovery/profile`
- `POST /api/discovery/profile`
- `POST /api/discovery/run`
- `GET /api/discovery/runs`
- `GET /api/discovery/digest/today`
- `POST /api/discovery/items/{id}/decision`
- `POST /api/discovery/items/{id}/export-pipeline`

Décisions supportées :

- `pending`
- `evaluate`
- `skip`
- `blacklist_company`
- `save_for_later`
- `already_applied`

### 6. Commandes Django

Commandes présentes :

```bash
python manage.py seed_discovery
python manage.py discover_jobs --profile default --market france
python manage.py rank_daily_jobs --profile default
python manage.py export_daily_jobs --profile default
python manage.py export_daily_jobs --profile default --evaluate
```

Utilisation prévue :

- `seed_discovery` : créer les sources France + profil `default`.
- `discover_jobs` : run complet collecte -> digest.
- `rank_daily_jobs` : recalculer ranking après modification du profil.
- `export_daily_jobs` : afficher la short-list.
- `export_daily_jobs --evaluate` : pousser les items marqués `evaluate` vers `data/pipeline.md`.

### 7. Tests

Tests identifiés :

- `backend/tests/test_discovery_connectors.py`
- `backend/tests/test_discovery_run.py`
- `backend/tests/test_discovery_normalize.py`
- `backend/tests/test_discovery_api.py`

Couverture actuelle :

- Connecteurs ATS.
- APEC.
- WTTJ.
- HelloWork JSON-LD.
- France Travail avec token fake.
- LinkedIn/Indeed manual sans réseau.
- Normalisation.
- Scoring.
- Run complet avec sources fake.
- API discovery.
- Export pipeline.

État annoncé par Claude Code :

- 80 tests passent.
- 15 tests connecteurs.
- `manage.py check` propre.

À refaire localement avant de considérer l'état figé :

```bash
backend/.venv/bin/pytest backend -q
backend/.venv/bin/python backend/manage.py check
backend/.venv/bin/python backend/manage.py makemigrations --check --dry-run
```

### 8. UI Matinale `/discovery`

Implémentée côté Next.js.

Fichiers :

- `web/src/app/discovery/page.tsx`
- `web/src/components/discovery/discovery-morning-view.tsx`
- `web/src/app/api/discovery/[...path]/route.ts`
- `web/src/lib/nav-items.ts`

Fonctionnalités :

- Charge `GET /api/discovery/digest/today`.
- Affiche le digest du jour avec score, raisons, source, date, localisation, contrat, remote et salaire si disponible.
- Permet les décisions `evaluate`, `skip`, `save_for_later`.
- Exporte un item vers le pipeline via `POST /api/discovery/items/{id}/export-pipeline`.
- Affiche les items déjà exportés.
- Propose un run manuel via `POST /api/discovery/run`.
- Ajoute `Discovery` dans la navigation principale.

Architecture :

- Le navigateur parle à Next.js.
- Next.js proxifie `/api/discovery/*` vers Django via `CAREER_OPS_API_URL`.
- Si Django est indisponible, le proxy retourne une erreur explicite.

Pré-requis en dev :

```bash
CAREER_OPS_API_URL=http://localhost:8000
backend/.venv/bin/python backend/manage.py runserver 8000
cd web && npm run dev
```

## Premier Run Réel -- 2026-07-14

Objectif : prouver que le backend Discovery peut collecter de vraies offres, construire un digest et exporter des décisions vers `data/pipeline.md`.

### Configuration Utilisée

Sources ATS activées :

- `greenhouse`
  - `datadog`
  - `huggingface`
  - `backmarket`
  - `doctolib`
- `lever`
  - `alan`
  - `contentsquare`
  - `qonto`
- `ashby`
  - `dust`
  - `mistral`
  - `cursor`

Profil `default` élargi pour validation :

- Titres : `AI Engineer`, `Data Engineer`, `Machine Learning Engineer`, `Software Engineer`, `Backend Engineer`, `Full Stack Engineer`, `Forward Deployed Engineer`, `Solutions Architect`, `AI Product Manager`.
- Mots-clés positifs : `python`, `django`, `ai`, `llm`, `agent`, `data`, `platform`, `product`, `backend`, `typescript`, `react`.
- Mots-clés négatifs : `php`, `wordpress`, `intern`, `stage`, `alternance`.
- Localisations : `Paris`, `France`, `Remote`, `Europe`.
- Contrats : `cdi`, `freelance`.
- Remote policy : `hybrid`.

Note : les sources ATS seedées ont `market=remote_eu`, donc le run utile doit utiliser `--market remote_eu`, pas `--market france`.

### Commandes Exécutées

```bash
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py seed_discovery
backend/.venv/bin/python backend/manage.py discover_jobs --profile default --market remote_eu
backend/.venv/bin/python backend/manage.py export_daily_jobs --profile default
```

Le premier run `--market france` a produit 0 source car les ATS sont classés `remote_eu`.

### Résultat Du Run

Run réel validé :

```json
{
  "runId": 3,
  "status": "success",
  "sources": {
    "ashby": {"seen": 75, "new": 75, "errors": []},
    "greenhouse": {"seen": 101, "new": 97, "errors": []},
    "lever": {"seen": 40, "new": 40, "errors": []}
  },
  "digest": {
    "date": "2026-07-14",
    "items": 20,
    "candidates": 85
  }
}
```

Le pipeline Discovery est donc validé :

- collecte réseau réelle ;
- normalisation ;
- scoring ;
- digest quotidien ;
- décisions utilisateur ;
- export vers `data/pipeline.md`.

### Offres Exportées Vers Pipeline

Trois offres ont été marquées `evaluate`, puis exportées :

- Qonto -- `Senior/Staff Backend Engineer - AI Compliance Tooling`
- Contentsquare -- `Security Automation Engineer`
- Datadog -- `AI Research Scientist - Datadog AI Research (DAIR)`

Lignes ajoutées dans `data/pipeline.md` :

```markdown
- [ ] https://jobs.lever.co/qonto/dc3bb55e-daf0-4d4c-b839-b65e43fd412c/apply | qonto | Senior/Staff Backend Engineer - AI Compliance Tooling | Paris
- [ ] https://jobs.lever.co/contentsquare/b83dfb6a-eaa7-45b0-8d00-3eb57eded62c/apply | contentsquare | Security Automation Engineer | Paris Area, France
- [ ] https://careers.datadoghq.com/detail/6652564/?gh_jid=6652564 | datadog | AI Research Scientist - Datadog AI Research (DAIR) | Paris, France
```

### Observations

Points positifs :

- Les endpoints ATS publics répondent correctement.
- Les connecteurs tolèrent les sources multiples.
- Le digest sort une liste exploitable.
- L'export pipeline fonctionne et marque les items exportés en DB.

Limites observées :

- Le scoring remonte encore des rôles sales/customer success/product ops trop haut.
- Certaines offres hors zone cible ou hors métier apparaissent dans le top 20.
- Le filtre `market` peut surprendre : les ATS sont `remote_eu`, pas `france`.
- Les titres élargis augmentent le rappel mais baissent la précision.

Recommandation après ce run :

- Passer à l'UI `/discovery`, mais prévoir rapidement des contrôles de filtre/scoring dans l'UI.
- Ajouter ensuite un ajustement du profil `default` pour réduire les rôles sales/customer success si non souhaités.
- Garder `--market remote_eu` pour les ATS ou changer le market des sources ATS si le produit doit les considérer comme partie du marché France.

## Ce Qui Reste À Faire

### 1. Valider Un Premier Run Réel

Le backend est prêt, mais il faut maintenant prouver la valeur avec de vraies données.

Actions :

1. Lancer les migrations.
2. Exécuter `seed_discovery`.
3. Configurer 5-10 boards ATS réels.
4. Lancer `discover_jobs`.
5. Vérifier que le digest contient des offres pertinentes.
6. Marquer quelques offres `evaluate`.
7. Exporter vers le pipeline.

Commandes de base :

```bash
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py seed_discovery
backend/.venv/bin/python backend/manage.py discover_jobs --profile default --market france
backend/.venv/bin/python backend/manage.py export_daily_jobs --profile default
```

Sources recommandées pour ce premier run :

- Greenhouse boards d'entreprises cibles.
- Lever slugs d'entreprises cibles.
- Ashby slugs d'entreprises cibles.

Pourquoi ATS d'abord :

- Endpoints publics stables.
- Peu de risque TOS.
- Données structurées.
- Bonne validation du pipeline sans dépendre de LinkedIn/Indeed.

### 2. Configurer Des Sources Réelles

À faire :

- Ajouter `config.boards` pour `greenhouse`.
- Ajouter `config.slugs` pour `lever`.
- Ajouter `config.slugs` pour `ashby`.
- Garder les jobboards France opt-in tant que non validés.

Exemples à adapter :

```python
JobSource.objects.filter(slug="greenhouse").update(
    enabled=True,
    config={"boards": ["example-company"]}
)

JobSource.objects.filter(slug="lever").update(
    enabled=True,
    config={"slugs": ["example-company"]}
)

JobSource.objects.filter(slug="ashby").update(
    enabled=True,
    config={"slugs": ["example-company"]}
)
```

À décider :

- Liste initiale d'entreprises françaises ou remote-friendly.
- Nombre maximum d'offres par matin.
- Critères du profil `default`.

### 3. Construire L'UI Matinale `/discovery`

C'est la plus grosse pièce manquante côté expérience utilisateur.

Objectif UI :

- Afficher les offres du jour.
- Montrer score + explications.
- Permettre les décisions utilisateur.
- Exporter vers le pipeline.

Page recommandée :

- `web/src/app/discovery/page.tsx`

Composants possibles :

- `DiscoveryDigestView`
- `DiscoveryJobCard`
- `DiscoveryScoreBreakdown`
- `DiscoveryDecisionButtons`
- `DiscoverySourceBadge`
- `DiscoveryRunStatus`

Données à afficher :

- Rang.
- Score.
- Titre.
- Entreprise.
- Source principale.
- Toutes sources détectées.
- Date de publication.
- Localisation.
- Remote/hybride/sur site.
- Type contrat.
- Salaire si disponible.
- Raisons du score.
- URL source.

Actions :

- `Évaluer`
- `Ignorer`
- `Plus tard`
- `Déjà postulé`
- `Blacklister entreprise`
- `Ouvrir l'offre`

Endpoints à utiliser :

- `GET /api/discovery/digest/today`
- `POST /api/discovery/items/{id}/decision`
- `POST /api/discovery/items/{id}/export-pipeline`

Critère de sortie :

- L'utilisateur peut traiter sa short-list du matin sans terminal.

### 4. Brancher Le Scheduling Nocturne

V1 recommandée : cron.

Commande :

```cron
0 22 * * * cd /path/to/opensource_career-ops && backend/.venv/bin/python backend/manage.py discover_jobs --profile default --market france
```

À faire :

- Documenter l'installation cron.
- Ajouter une commande de vérification.
- Écrire les logs dans un fichier local.
- Éviter les runs concurrents.

Critère de sortie :

- Le digest du jour est prêt chaque matin sans action manuelle.

### 5. Améliorer Le Profil De Recherche

Le profil `default` doit être personnalisé.

Critères à définir :

- Titres cibles.
- Mots-clés positifs.
- Mots-clés requis.
- Mots-clés négatifs.
- Localisations.
- Remote policy.
- Types de contrat.
- Salaire minimum.
- Entreprises bloquées.
- Secteurs préférés/bloqués.
- Taille du digest quotidien.

Recommandation :

- Commencer strict.
- Observer les résultats.
- Élargir progressivement.

### 6. Valider Les Connecteurs Jobboards France

Après les ATS :

Ordre recommandé :

1. APEC.
2. France Travail si credentials disponibles.
3. WTTJ si accès Algolia configuré.
4. HelloWork avec rate limit strict.
5. LinkedIn/Indeed uniquement manual import.

À vérifier pour chaque source :

- Qualité des titres.
- Qualité entreprise/localisation.
- Date publication fiable.
- Taux de doublons.
- Respect rate limits.
- Erreurs fréquentes.
- Pertinence du scoring.

### 7. Ajouter Une Vue Sources/Runs

Page utile :

- `/discovery/sources`
- `/discovery/runs`

But :

- Voir quelles sources sont actives.
- Voir dernière réussite/erreur.
- Lancer un run manuel.
- Comprendre pourquoi une source ne produit rien.

### 8. Refactoriser Les Warnings SonarQube

Claude Code a signalé :

- complexité cognitive ;
- regex backtracking potentiel.

Priorité :

- Non bloquant pour la V1.
- À faire avant PR propre ou si CI qualité bloque.

Recommandation :

- Refactoriser seulement après validation d'un run réel.
- Ne pas ralentir la validation produit pour des warnings non bloquants.

## Recommandation Priorisée

### Étape 1 -- Maintenant

Valider un run réel ATS.

Pourquoi :

- C'est le test de valeur le plus rapide.
- Ça vérifie modèles, connecteurs, normalisation, ranking, digest.
- Ça évite d'investir dans une UI avant d'avoir prouvé que les offres récupérées sont utiles.

Livrable :

- Un digest réel avec au moins 5 offres pertinentes. Fait le 2026-07-14.

### Étape 2 -- Ensuite

Construire `/discovery`.

Pourquoi :

- C'est ce qui rend le système utilisable chaque matin.
- L'API existe déjà.
- Le backend peut être consommé directement.

Livrable :

- Page "Offres du jour" avec décisions et export pipeline. Fait.

### Étape 3 -- Maintenant

Scheduling nocturne.

Pourquoi :

- Une fois le digest utile et l'UI utilisable, l'automatisation devient rentable.

Livrable :

- Run automatique chaque soir.

### Étape 4 -- Ensuite

Ajuster scoring et profil.

Pourquoi :

- Le premier digest remonte encore trop de rôles sales/customer success/product ops.
- Une UI utilisable rend maintenant les faux positifs plus visibles.

Livrable :

- Digest plus précis et moins bruité.

### Étape 5 -- Plus Tard

Activer les gros jobboards France.

Ordre :

1. APEC.
2. France Travail.
3. WTTJ.
4. HelloWork.
5. LinkedIn/Indeed manual import.

### Étape 6 -- Encore Plus Tard

Ajouter IA.

Cas d'usage IA :

- Résumé court de l'offre.
- Pré-classification archetype.
- Pré-score qualitatif.
- Red flags.
- Préparation automatique d'évaluation via `modes/fr/offre.md`.

À ne pas faire en premier :

- Scoring LLM dans le discovery initial.
- Auto-apply.
- Scraping LinkedIn/Indeed.

## Critères De Passage À L'UI

Avant de construire `/discovery`, vérifier :

- `seed_discovery` fonctionne.
- Au moins une source réelle activée.
- `discover_jobs` produit un digest.
- Les scores semblent explicables.
- Les doublons sont raisonnablement fusionnés.
- `export_daily_jobs` affiche une liste exploitable.
- `export-pipeline` fonctionne sur un item marqué `evaluate`.

Si ces critères ne sont pas validés, l'UI risque de masquer des problèmes de données.

## Critères De Passage Au Scheduling

Avant cron :

- Un run manuel complet passe.
- Le run est idempotent.
- Les doublons ne gonflent pas chaque jour.
- Les erreurs source sont visibles.
- Le digest du jour remplace/actualise proprement la short-list.
- Le temps d'exécution est acceptable.

## Risques Et Points D'Attention

### Risque 1 -- Sources Live Fragiles

Les jobboards peuvent changer leurs endpoints.

Mitigation :

- Tests fixtures.
- Connecteurs isolés.
- Sources opt-in.
- Logs par source.

### Risque 2 -- Trop De Bruit

Un digest de 50 offres médiocres ne sert à rien.

Mitigation :

- Profil strict.
- Taille digest limitée.
- Negative keywords.
- Company blacklist.
- Ajustement scoring après quelques matins.

### Risque 3 -- Doublons Multi-Sources

Une même offre peut apparaître sur WTTJ, LinkedIn, ATS direct, Indeed.

Mitigation :

- Canonical URL.
- Company + title normalized.
- Apply URL.
- Content hash.
- `all_sources` conservé.

### Risque 4 -- LinkedIn/Indeed

Très utiles mais risqués à automatiser.

Mitigation :

- Manual import uniquement.
- Ne pas browser-scraper.
- Ne pas utiliser compte utilisateur sans opt-in explicite.

### Risque 5 -- UI Trop Tôt

Construire une belle UI avant d'avoir une donnée utile peut faire perdre du temps.

Mitigation :

- Run réel ATS avant UI.
- UI minimale d'abord.

## Checklist Courte

À faire maintenant :

- [x] Rejouer les tests backend localement.
- [x] Lancer migrations.
- [x] Seed discovery.
- [x] Configurer 5-10 boards ATS.
- [x] Lancer `discover_jobs`.
- [x] Inspecter `export_daily_jobs`.
- [ ] Ajuster le profil `default`.
- [x] Valider export pipeline.

À faire ensuite :

- [x] Créer `/discovery`.
- [x] Ajouter actions décision.
- [x] Ajouter export pipeline depuis UI.
- [ ] Ajouter page runs/sources.
- [ ] Brancher cron.

À faire plus tard :

- [ ] Activer APEC.
- [ ] Activer France Travail OAuth.
- [ ] Activer WTTJ si clés disponibles.
- [ ] Activer HelloWork avec rate limit.
- [ ] Refactoriser warnings SonarQube.
- [ ] Ajouter IA post-discovery.

## Commandes Utiles

Tests :

```bash
backend/.venv/bin/pytest backend -q
backend/.venv/bin/python backend/manage.py check
backend/.venv/bin/python backend/manage.py makemigrations --check --dry-run
```

Initialisation :

```bash
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py seed_discovery
```

Run manuel :

```bash
backend/.venv/bin/python backend/manage.py discover_jobs --profile default --market france
backend/.venv/bin/python backend/manage.py export_daily_jobs --profile default
```

Re-ranking :

```bash
backend/.venv/bin/python backend/manage.py rank_daily_jobs --profile default
```

Export des items marqués `evaluate` :

```bash
backend/.venv/bin/python backend/manage.py export_daily_jobs --profile default --evaluate
```

## Décision Recommandée

Ne pas commencer par l'UI directement si aucun connecteur réel n'a encore produit de digest utile.

Ordre optimal :

1. Valider données réelles ATS.
2. Ajuster critères.
3. Créer UI `/discovery`.
4. Ajouter scheduling.
5. Étendre jobboards France.
6. Ajouter IA plus tard.

Cette séquence maximise la preuve de valeur et limite le risque de construire une interface autour d'un flux de données encore non validé.
