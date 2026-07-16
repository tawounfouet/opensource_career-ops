# Plan d'Action -- France Job Discovery Django

Objectif : ajouter un module Django déterministe qui collecte chaque soir les offres récentes sur les jobboards du marché français, les normalise, les déduplique, les classe selon les critères utilisateur, puis prépare une liste matinale d'offres que l'utilisateur choisira d'évaluer ou de postuler.

Ce plan vise volontairement une V1 sans IA. L'IA pourra être ajoutée plus tard pour enrichir, résumer, scorer finement ou personnaliser, mais la recherche, la collecte, la déduplication et le ranking initial doivent être explicables et testables.

## Résultat Attendu

Chaque soir :

1. Le système lit les critères utilisateur.
2. Il interroge les sources configurées.
3. Il récupère uniquement les offres nouvelles ou récemment mises à jour.
4. Il normalise les données dans une base Django.
5. Il déduplique les offres multi-sources.
6. Il applique des filtres déterministes.
7. Il calcule un score de priorité déterministe.
8. Il prépare une short-list ordonnée pour le lendemain matin.

Chaque matin :

1. L'utilisateur ouvre une vue "Offres du jour".
2. Il voit les offres classées par priorité.
3. Il peut accepter, ignorer, blacklister, archiver ou envoyer une offre vers le pipeline d'évaluation.
4. Aucune candidature n'est envoyée automatiquement.

## Principes

- Déterministe d'abord : pas de LLM dans la collecte V1.
- Transparent : chaque score doit être justifiable par des règles.
- Respect des plateformes : préférer APIs publiques, flux RSS, endpoints documentés, pages publiques autorisées, ou import manuel si scraping interdit.
- Qualité plutôt que volume : l'objectif est une short-list actionnable, pas un dump massif.
- Local-first : la base Django stocke les offres, runs, sources, critères et décisions utilisateur.
- Compatible career-ops : les offres retenues doivent pouvoir aller vers `data/pipeline.md`, `/api/run`, `modes/fr/offre.md`, puis `apply`.

## Sources Ciblées France

### Tier 1 -- Prioritaires

- APEC : cadres, tech, product, management, marché français.
- Welcome to the Jungle : startups, scaleups, tech, product, culture entreprise.
- HelloWork : généraliste France, régional, CDI/CDD/alternance.
- France Travail : généraliste/public, volume élevé.
- Indeed France : agrégateur généraliste.
- LinkedIn Jobs : très utile, mais fortement contraint côté scraping.

### Tier 2 -- Importants Selon Profil

- Cadremploi : cadres, management, tech senior.
- Meteojob : généraliste.
- JobTeaser : junior, alternance, graduate, mais peut être utile selon profil.
- ChooseYourBoss : tech/digital, à vérifier selon disponibilité.
- LesJeudis : IT/tech, à vérifier selon disponibilité.
- Talent.io / Hired-like platforms : souvent nécessitent compte, plutôt sourcing inversé.
- WeLoveDevs : développeurs/tech.
- RemixJobs : digital/product/tech.
- Free-Work : freelance, tech, portage, ESN.
- Malt / Comet / LeHibou : freelance, plutôt marketplace que jobboard.

### Tier 3 -- Sources Complémentaires

- Sites carrières directs d'entreprises cibles.
- ATS directs :
  - Greenhouse
  - Lever
  - Ashby
  - Workday
  - SmartRecruiters
  - Teamtailor
  - Recruitee
- Agrégateurs spécialisés :
  - Station F jobs
  - La French Tech jobs
  - Welcome Hiring Suite sources si exposées publiquement
- Newsletters ou pages publiques de communautés tech françaises, si import manuel ou flux disponible.

## Contraintes Légales Et Techniques

Certaines plateformes limitent ou interdisent le scraping automatisé. Le module doit donc gérer plusieurs stratégies.

Stratégies autorisées par connecteur :

- `api` : endpoint public ou partenaire.
- `rss` : flux RSS ou Atom.
- `ats_api` : endpoint d'ATS public utilisé par les pages carrières.
- `html_public` : parsing HTML léger si autorisé et stable.
- `browser_public` : Playwright uniquement si nécessaire, rate limited.
- `manual_import` : l'utilisateur colle/exporte les offres.
- `disabled` : source listée mais non automatisée.

Règles :

- Ne pas contourner login, CAPTCHA, paywall, anti-bot ou restrictions techniques.
- Ne pas utiliser de compte utilisateur pour scraper sans opt-in explicite.
- Respecter `robots.txt` quand applicable.
- Respecter un rate limit par domaine.
- Identifier clairement les sources qui nécessitent une approche manuelle ou officielle.
- Stocker la raison quand une source est désactivée.

Recommandation V1 :

- Ne pas scraper LinkedIn en navigateur automatisé.
- Pour LinkedIn, commencer par `manual_import` ou ouverture de liens sauvegardés par l'utilisateur.
- Pour Indeed, vérifier d'abord s'il existe une voie autorisée ou se limiter à une intégration désactivée/import.
- Prioriser APEC, France Travail, WTTJ, HelloWork, ATS directs et sites carrières quand l'accès public est stable.

## Architecture Django Proposée

Créer une app Django dédiée :

```text
backend/apps/discovery/
  __init__.py
  apps.py
  models.py
  admin.py
  services/
    criteria.py
    scoring.py
    dedup.py
    normalize.py
    scheduler.py
    exporters.py
  connectors/
    base.py
    apec.py
    france_travail.py
    welcometothejungle.py
    hellowork.py
    indeed.py
    linkedin.py
    cadremploi.py
    meteojob.py
    ats_greenhouse.py
    ats_lever.py
    ats_ashby.py
  management/
    commands/
      discover_jobs.py
      rank_daily_jobs.py
      export_daily_jobs.py
  tests/
```

## Modèle De Données

### `JobSource`

Représente une plateforme ou source.

Champs :

- `id`
- `name`
- `slug`
- `kind` : `jobboard`, `ats`, `company_site`, `manual`
- `strategy` : `api`, `rss`, `ats_api`, `html_public`, `browser_public`, `manual_import`, `disabled`
- `base_url`
- `enabled`
- `country`
- `market` : `france`, `francophone`, `remote_eu`
- `rate_limit_per_hour`
- `requires_login`
- `tos_notes`
- `robots_policy`
- `last_checked_at`
- `last_success_at`
- `last_error`

### `SearchProfile`

Critères utilisateur configurables.

Champs :

- `name`
- `enabled`
- `target_titles`
- `positive_keywords`
- `negative_keywords`
- `required_keywords`
- `locations`
- `remote_policy` : `remote`, `hybrid`, `onsite`, `any`
- `contract_types` : CDI, CDD, freelance, portage, alternance, stage
- `seniority_min`
- `seniority_max`
- `salary_min`
- `salary_target`
- `industries_allow`
- `industries_block`
- `companies_allow`
- `companies_block`
- `ats_allow`
- `sources_enabled`
- `freshness_days`
- `max_results_per_run`
- `language`
- `created_at`
- `updated_at`

Source de vérité utilisateur :

- Les critères peuvent aussi être synchronisés depuis `config/profile.yml` ou `modes/_profile.md`.
- Ne pas écrire de faits utilisateur dans les modes système.
- Les préférences de recherche appartiennent à `config/profile.yml` ou à la DB Django locale.

### `DiscoveryRun`

Un run de collecte nocturne.

Champs :

- `id`
- `profile`
- `started_at`
- `finished_at`
- `status` : `running`, `success`, `partial`, `failed`
- `trigger` : `scheduled`, `manual`, `cli`
- `sources_requested`
- `sources_success`
- `sources_failed`
- `offers_seen`
- `offers_new`
- `offers_updated`
- `offers_deduped`
- `errors`
- `duration_ms`

### `RawJobPosting`

Capture brute par source.

Champs :

- `id`
- `run`
- `source`
- `source_job_id`
- `url`
- `canonical_url`
- `raw_title`
- `raw_company`
- `raw_location`
- `raw_payload`
- `raw_html_hash`
- `first_seen_at`
- `seen_at`
- `posted_at`
- `expires_at`
- `status` : `new`, `seen`, `expired`, `error`

### `JobPosting`

Offre normalisée et dédupliquée.

Champs :

- `id`
- `canonical_key`
- `title`
- `company`
- `company_slug`
- `location`
- `remote_type`
- `contract_type`
- `salary_min`
- `salary_max`
- `salary_currency`
- `seniority`
- `description_text`
- `requirements_text`
- `benefits_text`
- `apply_url`
- `source_url`
- `primary_source`
- `all_sources`
- `posted_at`
- `first_seen_at`
- `last_seen_at`
- `is_active`
- `dedup_confidence`
- `content_hash`
- `language`
- `market`

### `JobRanking`

Score déterministe pour un profil.

Champs :

- `id`
- `job`
- `profile`
- `run`
- `score`
- `freshness_score`
- `title_score`
- `keyword_score`
- `location_score`
- `remote_score`
- `contract_score`
- `salary_score`
- `company_score`
- `negative_penalty`
- `explanations`
- `rank`
- `created_at`

### `DailyJobDigest`

Short-list du matin.

Champs :

- `id`
- `profile`
- `date`
- `run`
- `status` : `prepared`, `reviewed`, `archived`
- `total_candidates`
- `items_count`
- `created_at`

### `DailyJobDigestItem`

Une offre dans la short-list.

Champs :

- `digest`
- `job`
- `ranking`
- `rank`
- `decision` : `pending`, `evaluate`, `skip`, `blacklist_company`, `save_for_later`, `already_applied`
- `decision_note`
- `decided_at`
- `exported_to_pipeline_at`

## Scoring Déterministe V1

Score total sur 100.

Exemple :

- Fraîcheur : 20 points
- Titre ciblé : 20 points
- Mots-clés positifs : 15 points
- Mots-clés requis : 15 points
- Localisation/remote : 10 points
- Type de contrat : 10 points
- Salaire : 5 points
- Entreprise allow/block : 5 points
- Pénalités : jusqu'à -50

### Fraîcheur

- Publiée aujourd'hui : 20
- Publiée hier : 16
- 2-3 jours : 12
- 4-7 jours : 8
- Plus ancien : 2
- Date inconnue : 5

### Titre

- Match exact titre cible : 20
- Match titre normalisé : 15
- Match synonyme : 10
- Match vague : 5
- Titre bloqué : rejet

### Keywords

Règles :

- Chaque required keyword manquant peut bloquer ou pénaliser fortement.
- Chaque positive keyword ajoute un poids.
- Chaque negative keyword applique une pénalité.
- Les mots-clés sont matchés sur titre + description + requirements.

### Remote / Localisation

Exemples :

- Profil veut full remote, offre full remote : +10
- Profil veut full remote, offre hybride IDF : +3
- Profil bloque onsite, offre onsite : rejet
- Localisation inconnue : neutre ou pénalité légère

### Contrat

Exemples :

- CDI demandé + CDI : +10
- Freelance demandé + freelance : +10
- CDI demandé + freelance : +2 ou rejet selon profil
- Stage/alternance si non demandé : rejet

### Salaire

Règles :

- Si salaire explicite et >= minimum : bonus.
- Si salaire explicite sous minimum : pénalité ou rejet.
- Si salaire absent : neutre ou pénalité légère.
- Ne jamais inventer un salaire.

## Workflow Nocturne

Commande :

```bash
backend/.venv/bin/python backend/manage.py discover_jobs --profile default --market france
```

Étapes :

1. Charger `SearchProfile`.
2. Charger sources actives.
3. Créer `DiscoveryRun`.
4. Pour chaque source :
   - vérifier rate limit ;
   - exécuter le connecteur ;
   - stocker `RawJobPosting` ;
   - normaliser vers `JobPosting` ;
   - journaliser erreurs.
5. Dédupliquer.
6. Calculer ranking.
7. Créer `DailyJobDigest`.
8. Exporter un résumé local.

Sortie JSON :

```json
{
  "runId": 123,
  "status": "success",
  "sources": {
    "apec": {"seen": 42, "new": 8, "errors": []},
    "wttj": {"seen": 25, "new": 5, "errors": []}
  },
  "digest": {
    "date": "2026-07-14",
    "items": 20
  }
}
```

## Revue Matinale

Endpoint Django :

- `GET /api/discovery/digest/today`
- `POST /api/discovery/digest/{id}/decision`
- `POST /api/discovery/digest/{id}/export`

Actions utilisateur :

- `evaluate` : envoyer vers `data/pipeline.md` ou déclencher `/api/run`.
- `skip` : ignorer cette offre.
- `save_for_later` : garder sans évaluer.
- `blacklist_company` : ajouter à une blacklist locale après confirmation.
- `already_applied` : marquer comme déjà traité.

Important :

- `evaluate` ne postule pas.
- `export` ajoute seulement une ligne pipeline.
- La vraie évaluation utilise ensuite `modes/fr/offre.md`.

## API Django V1

### `GET /api/discovery/sources`

Retourne sources disponibles, statut, stratégie, dernière erreur.

### `GET/POST /api/discovery/profile`

Lit ou modifie les critères de recherche.

### `POST /api/discovery/run`

Déclenche un run manuel.

### `GET /api/discovery/runs`

Liste historique des runs.

### `GET /api/discovery/digest/today`

Retourne la short-list du jour.

### `POST /api/discovery/items/{id}/decision`

Met à jour décision utilisateur.

### `POST /api/discovery/items/{id}/export-pipeline`

Ajoute l'offre au pipeline career-ops.

## Connecteurs : Design

Interface commune :

```python
class JobConnector:
    slug: str
    strategy: str

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        ...
```

Chaque connecteur doit :

- recevoir des critères normalisés ;
- retourner des objets bruts structurés ;
- ne pas écrire directement en DB ;
- gérer ses erreurs localement ;
- exposer sa capacité : keywords, location, remote, freshness, pagination.

## Connecteurs V1 Recommandés

### APEC

Priorité haute.

À faire :

- Vérifier endpoints publics ou pages accessibles.
- Implémenter recherche par titre/localisation.
- Extraire :
  - titre ;
  - entreprise ;
  - localisation ;
  - type contrat ;
  - salaire si présent ;
  - date publication ;
  - URL.

### France Travail

Priorité haute si API disponible/configurable.

À faire :

- Étudier API officielle.
- Gérer éventuelles clés/config.
- Mapper contrats et localisation.

### Welcome To The Jungle

Priorité haute.

À faire :

- Vérifier endpoints publics utilisés par la recherche.
- Ne pas contourner protections.
- Extraire entreprise, culture metadata, remote si disponible.

### HelloWork

Priorité haute.

À faire :

- Vérifier structure de recherche.
- Parser résultats publics si autorisé.
- Rate limit strict.

### LinkedIn

Priorité spéciale.

V1 recommandée :

- `manual_import`.
- Import depuis URL sauvegardée ou export utilisateur.
- Pas de browser scraping automatisé par défaut.

Raison :

- Plateforme fortement protégée.
- Risque CGU/anti-bot élevé.

### Indeed

Priorité spéciale.

V1 recommandée :

- Étudier voie officielle/partenaire.
- Sinon `disabled` ou `manual_import`.
- Éviter scraping agressif.

### ATS Directs

Très utile car beaucoup plus stable.

À faire :

- Greenhouse board API.
- Lever postings JSON.
- Ashby public postings.
- Teamtailor/Recruitee si simple.

## Normalisation

Fonction `normalize_job(raw)` :

- Nettoyer titre.
- Normaliser entreprise.
- Normaliser localisation.
- Détecter remote :
  - full remote ;
  - hybrid ;
  - onsite ;
  - unknown.
- Détecter contrat :
  - CDI ;
  - CDD ;
  - freelance ;
  - portage ;
  - alternance ;
  - stage ;
  - internship.
- Extraire salaire :
  - min ;
  - max ;
  - devise ;
  - période.
- Détecter langue.
- Générer `canonical_key`.

## Déduplication

Déduplication par paliers :

1. URL canonique identique.
2. Source job id identique.
3. Même entreprise + titre normalisé + localisation proche.
4. Même apply URL.
5. Hash description proche.

Sortie :

- `dedup_confidence` entre 0 et 1.
- `all_sources` garde toutes les sources où l'offre apparaît.

## Stockage Et Rétention

Recommandation :

- Garder `RawJobPosting` 90 jours.
- Garder `JobPosting` tant que vu dans les 180 derniers jours.
- Marquer `expired` si absent plusieurs runs ou liveness échoue.
- Ne pas supprimer immédiatement les offres ignorées : garder pour éviter re-proposition.

## Scheduling

Options :

### Option A -- Management Command + Cron

Simple pour V1.

```cron
0 22 * * * cd /path/to/career-ops && backend/.venv/bin/python backend/manage.py discover_jobs --profile default
```

### Option B -- Django-Q/Celery

Plus robuste mais plus lourd.

À garder pour V2 si besoin :

- retries ;
- dashboard ;
- concurrency ;
- distributed scheduling.

Recommandation V1 :

- Management command + cron/documentation.
- Pas de Celery tant que le besoin n'est pas prouvé.

## Frontend

Pages à ajouter :

- `/discovery`
- `/discovery/settings`
- `/discovery/runs`
- `/discovery/sources`

Vue principale "Offres du jour" :

- Rang.
- Score déterministe.
- Titre.
- Entreprise.
- Source.
- Date publication.
- Localisation/remote.
- Salaire si connu.
- Raisons du score.
- Boutons :
  - Evaluer ;
  - Ignorer ;
  - Plus tard ;
  - Blacklister entreprise ;
  - Ouvrir source.

## Intégration Avec `modes/fr/offre.md`

Le module discovery ne remplace pas l'évaluation.

Flux :

1. Discovery trouve une offre.
2. Utilisateur choisit `Evaluer`.
3. Offre exportée vers `data/pipeline.md` ou passée à `/api/run`.
4. Le mode `modes/fr/offre.md` produit l'évaluation A-F.
5. Si score suffisant, l'utilisateur décide de postuler.

À faire :

- Ajouter un champ `market_mode = modes/fr`.
- Injecter dans le prompt :
  - "Write output in configured `language.output`."
  - "Use French market mode from `modes/fr/offre.md`."
- Stocker le lien entre `JobPosting` et report généré.

## Tests

### Unit Tests

- Normalisation titre.
- Normalisation contrat.
- Normalisation remote.
- Extraction salaire.
- Canonical URL.
- Déduplication.
- Scoring déterministe.
- Filtres required/negative.
- Blacklist.

### Connector Tests

Utiliser fixtures HTML/JSON locales.

- APEC fixture.
- WTTJ fixture.
- HelloWork fixture.
- France Travail fixture/API mock.
- ATS Greenhouse fixture.
- ATS Lever fixture.
- ATS Ashby fixture.
- LinkedIn manual import fixture.
- Indeed disabled/manual behavior.

### Integration Tests

- Run discovery complet avec 2 sources fake.
- Création `DiscoveryRun`.
- Création `RawJobPosting`.
- Normalisation `JobPosting`.
- Déduplication multi-source.
- Création `DailyJobDigest`.
- Décision utilisateur.
- Export pipeline.

### E2E Plus Tard

- Scheduler nocturne.
- UI morning review.
- Export vers évaluation.

## Sécurité Et Robustesse

- Rate limit par source.
- User-agent clair si scraping public autorisé.
- Timeout par requête.
- Retry limité.
- Circuit breaker par source.
- Logs par source.
- Pas de secrets dans logs.
- Respect blacklist.
- Pas de candidature automatique.

## Phases D'Implémentation

### Phase 0 -- Décision Produit

Livrables :

- Valider que V1 est déterministe sans IA.
- Valider sources prioritaires.
- Valider critères utilisateur initiaux.
- Valider comportement LinkedIn/Indeed : manual/import ou disabled.

### Phase 1 -- Modèles Et Admin

Livrables :

- App `discovery`.
- Models DB.
- Migrations.
- Admin Django.
- Tests models.

### Phase 2 -- Critères Et Scoring

Livrables :

- `SearchProfile`.
- Normalisation critères.
- Scoring déterministe.
- Explications de score.
- Tests scoring.

### Phase 3 -- Connecteurs Fake + Pipeline DB

Livrables :

- Interface `JobConnector`.
- Connecteur fake fixture.
- Management command `discover_jobs`.
- `DiscoveryRun`.
- `DailyJobDigest`.
- Tests intégration sans réseau.

### Phase 4 -- Connecteurs France Prioritaires

Livrables :

- APEC.
- France Travail si API disponible.
- WTTJ.
- HelloWork.
- ATS directs Greenhouse/Lever/Ashby.
- Indeed/LinkedIn en disabled/manual import.

### Phase 5 -- API Django

Livrables :

- Sources.
- Profile.
- Run manual.
- Digest today.
- Decisions.
- Export pipeline.
- Tests API.

### Phase 6 -- UI Matinale

Livrables :

- Page offres du jour.
- Page critères.
- Page sources/runs.
- Actions utilisateur.
- Export pipeline.

### Phase 7 -- Scheduling

Livrables :

- Commande nocturne.
- Documentation cron.
- Run logs.
- Notification locale optionnelle.

### Phase 8 -- Intégration IA Plus Tard

L'IA peut intervenir après la collecte déterministe :

- Résumé court de l'offre.
- Classification archetype.
- Explication qualitative.
- Pré-score fit CV.
- Détection red flags.
- Génération du rapport complet via `modes/fr/offre.md`.

Non inclus en V1 :

- Recherche web agentique.
- Scoring LLM.
- Candidature automatique.
- Remplissage automatique depuis discovery.

## Critères De Sortie V1

- Un run nocturne peut préparer une short-list sans IA.
- Les offres sont stockées en DB.
- Les doublons évidents sont fusionnés.
- L'utilisateur voit une liste ordonnée le matin.
- Chaque score a une explication déterministe.
- L'utilisateur peut exporter une offre vers le pipeline.
- LinkedIn/Indeed ne sont pas scrapés agressivement.
- Les tests unitaires et intégration passent sans réseau.

## Critères De Sortie V2

- Connecteurs réels robustes sur au moins 4 sources France.
- Tests fixtures pour chaque connecteur.
- Scheduler documenté.
- UI utilisable.
- Export vers `modes/fr/offre.md`.
- Historique de décisions utilisé pour améliorer les règles déterministes.

## Questions À Trancher Avant Implémentation

- Le profil cible principal est-il cadre tech, product, AI, freelance, ou généraliste ?
- Faut-il inclure freelance/portage dans la même short-list que CDI ?
- Quels sites sont prioritaires pour le premier run réel ?
- Quelle zone géographique : France entière, IDF, Europe remote, francophone ?
- Combien d'offres maximum par matin ?
- Quelle politique LinkedIn/Indeed : manual import uniquement ou recherche d'intégration officielle ?
- Faut-il notifier le matin ou seulement afficher dans l'UI ?

## Recommandation De Démarrage

Commencer par une V1 très contrôlée :

1. Créer app Django `discovery`.
2. Ajouter modèles DB + admin.
3. Ajouter critères utilisateur.
4. Ajouter connecteur fake avec fixtures.
5. Ajouter scoring déterministe.
6. Ajouter digest quotidien.
7. Ajouter API digest/decision/export.
8. Ajouter UI "Offres du jour".
9. Ajouter un premier connecteur réel à faible risque.

Premier connecteur réel recommandé :

- ATS directs Greenhouse/Lever/Ashby ou APEC/France Travail si API/accès stable.

À éviter en premier :

- LinkedIn browser scraping.
- Indeed scraping agressif.
- Playwright massif multi-source.
