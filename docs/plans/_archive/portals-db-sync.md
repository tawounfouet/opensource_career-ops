# Plan : Portals DB + YAML Sync

## Contexte

`config/portals.yml` est la source de vérité pour ~100 entreprises, 35+ search queries, et les filtres title/location. Les modèles Django `Portal` et `SearchQuery` existent (migration 0001) mais sont **inutilisés** — toutes les vues lisent/écrivent le YAML directement. Le scanner CLI (`scan.mjs`, providers) consomme le YAML.

L'objectif est un **hybride** : la DB comme couche admin/API rapide, le YAML comme source pour les scripts CLI, avec sync bidirectionnelle.

---

## Phase 1 — Enrichir les modèles DB

**Fichier :** `backend/apps/portals/models.py`

### `Portal` — ajouter les champs manquants

| Champ YAML | Champ DB | Type | Notes |
|---|---|---|---|
| `name` | `name` | CharField(200) | ✅ existe |
| `careers_url` | `careers_url` | URLField | ✅ existe |
| `enabled` | `enabled` | BooleanField | ✅ existe |
| `api` | `api_endpoint` | URLField(blank=True) | **nouveau** — URL API ATS directe |
| `scan_method` | `scan_method` | CharField(20, choices) | **nouveau** — `auto`/`api`/`websearch`/`local_parser` |
| `scan_query` | `scan_query` | TextField(blank=True) | **nouveau** — requête Google pour mode websearch |
| `notes` | `notes` | TextField(blank=True) | **nouveau** |
| `provider` | `provider` | CharField(50, blank=True) | **nouveau** — forcer un provider spécifique |
| `parser` | `parser_config` | JSONField(null=True) | **nouveau** — `{command, script, format}` |
| `max_pages` | `max_pages` | PositiveIntegerField(null=True) | **nouveau** |
| — | `extra_config` | JSONField(default=dict) | **nouveau** — blocs provider-spécifiques (`amazon`, `arbeitsagentur`, `searchKeywords`…) |
| `ats` | `ats` | CharField(50) | ✅ existe — auto-détecté à l'import |
| `greenhouse_token` | — | — | **supprimé** — redondant avec `api_endpoint` |
| `ashby_slug` | — | — | **supprimé** — redondant avec `api_endpoint` |
| `lever_slug` | — | — | **supprimé** — redondant avec `api_endpoint` |
| `last_verified` | `last_verified` | DateTimeField | ✅ existe |
| `is_live` | `is_live` | BooleanField | ✅ existe |

### `SearchQuery` — ajouter `name`

| Champ | Type | Notes |
|---|---|---|
| `name` | CharField(200, blank=True) | **nouveau** — ex: "Ashby — AI PM" |
| `query` | CharField(300) | ✅ existe |
| `source` | CharField(100) | ✅ existe |
| `enabled` | BooleanField | ✅ existe |

### Nouveau modèle `TitleFilter`

| Champ | Type |
|---|---|
| `positive` | JSONField(default=list) — mots-clés inclusion |
| `negative` | JSONField(default=list) — mots-clés exclusion |
| `seniority_boost` | JSONField(default=list) — boost Senior/Staff/Lead… |

Singleton (une seule instance, id=1).

### Nouveau modèle `JobBoard`

| Champ | Type |
|---|---|
| `name` | CharField(200) — ex: "SolidJobs IT" |
| `careers_url` | URLField |
| `provider` | CharField(50) — ex: `solidjobs` |
| `enabled` | BooleanField |
| `notes` | TextField(blank=True) |
| `extra_config` | JSONField(default=dict) — `siteKey`, `searchKeywords`, `pageSize`… |

### Migration

Générer `0002_portals_enrich.py` qui :
- Ajoute les nouveaux champs à `Portal` (avec `default` pour les champs existants)
- Renomme `greenhouse_token`/`ashby_slug`/`lever_slug` → supprime (ou garde dans `extra_config`)
- Ajoute `name` à `SearchQuery`
- Crée `TitleFilter` et `JobBoard`

---

## Phase 2 — Service de sync (`services.py`)

**Fichier :** `backend/apps/portals/services.py` (nouveau)

### `import_yaml_to_db(yaml_path: Path) → dict`

```
1. Lire portals.yml
2. Upsert TitleFilter (singleton id=1)
3. Pour chaque company dans tracked_companies :
   - Chercher par `name` (unique)
   - Si trouvé : update tous les champs
   - Si absent : créer
   - Marquer les orphelins (DB mais pas dans YAML) pour suppression optionnel
4. Pour chaque query dans search_queries :
   - Upsert par (name + query) ou création
5. Pour chaque board dans job_boards :
   - Upsert par name
6. Supprimer les Portal/SearchQuery/JobBoard qui ne sont plus dans le YAML
7. Retourner {imported: N, updated: N, deleted: N, errors: [...]}
```

### `export_db_to_yaml(yaml_path: Path) → dict`

```
1. Lire le YAML existant (pour préserver comments, ordering, champs inconnus)
2. TitleFilter → title_filter (écraser)
3. Portal → tracked_companies (reconstruire les dicts YAML)
4. SearchQuery → search_queries
5. JobBoard → job_boards
6. Écrire via atomic_write_with_backup
7. Retourner {exported: N}
```

### Résolution des conflits

- **Import** : YAML est source → le YAML gagne sur les conflits
- **Export** : DB est source → la DB gagne sur les conflits
- **Champs inconnus** : les blocs provider-spécifiques dans `extra_config` sont préservés intacts (pas de parsing, juste JSON roundtrip)

---

## Phase 3 — Admin Django enrichi

**Fichier :** `backend/apps/portals/admin.py`

- `PortalAdmin` : `list_editable = ["enabled"]`, `list_display` avec badge ATS
- `SearchQueryAdmin` : `list_editable = ["enabled"]`
- `JobBoardAdmin` : `list_display = ["name", "provider", "enabled"]`
- Actions custom :
  - `import_from_yaml` : import depuis `config/portals.yml`
  - `export_to_yaml` : export vers `config/portals.yml`
  - `verify_selected` : lancer `verify-portals.mjs` sur les Portals sélectionnés

---

## Phase 4 — Mettre à jour les vues API

**Fichier :** `backend/apps/portals/views.py`

### `PortalsView.get` (GET /api/portals)

Avant : lit YAML, retourne `{content: yaml_dict}`

Après : lit la DB, reconstruit le même format de réponse :
```python
{
  "content": {
    "title_filter": {"positive": [...], "negative": [...], ...},
    "tracked_companies": [{"name": ..., "careers_url": ..., ...}],
    "search_queries": [{"name": ..., "query": ..., ...}],
    "job_boards": [...]
  },
  "exists": True
}
```

### `PortalsView.post` (POST /api/portals)

Avant : écrit `title_filter.positive` et `location_filter` dans le YAML

Après : écrit dans la DB **et** sync vers YAML :
1. Met à jour `TitleFilter.positive` / `TitleFilter` dans la DB
2. Appelle `export_db_to_yaml()` pour persister le changement dans le YAML

### `ExtractPortalView.post` (POST /api/skills/llm/extract-portal)

Avant : append dans le YAML

Après : crée dans la DB **et** exporte vers le YAML

---

## Phase 5 — Garder les scripts CLI intacts

**Aucun changement** pour :
- `scan.mjs` — continue de lire `config/portals.yml`
- Tous les providers — consomment le YAML
- `verify-portals.mjs` — lit le YAML
- `stats.mjs` — lit le YAML

Le workflow : Admin Django → DB → export → YAML → CLI scripts.

---

## Phase 6 — Nettoyage

- Supprimer les champs redondants (`greenhouse_token`, `ashby_slug`, `lever_slug`) du modèle ou les migrer dans `extra_config`
- Mettre à jour `.gitignore` si nécessaire
- Vérifier que `doctor.mjs` reconnaît `config/portals.yml`

---

## Fichiers touchés

| Fichier | Action |
|---|---|
| `backend/apps/portals/models.py` | Enrichir modèles |
| `backend/apps/portals/services.py` | **Nouveau** — sync service |
| `backend/apps/portals/admin.py` | Actions custom |
| `backend/apps/portals/views.py` | Lire DB au lieu de YAML |
| `backend/apps/portals/urls.py` | Pas de changement |
| `backend/apps/portals/migrations/0002_*.py` | **Nouveau** — migration |
| `backend/apps/skills_portfolio/views.py` | `ExtractPortalView` → DB + YAML |
| Tests | Mettre à jour les tests existants |

## Risques

- **Migration de données** : la migration 0002 doit pouvoir être remplie depuis le YAML existant (`import_yaml_to_db` en migration RunPython)
- **Compatibilité** : les scripts CLI continuent de lire le YAML — tant que l'export est fiable, pas de breaking change
- **Champs provider-spécifiques** : `extra_config` JSON est un good enough — pas besoin de modéliser chaque provider
