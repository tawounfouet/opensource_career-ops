# Session: Portals DB + YAML Sync

**Date**: 2026-07-15
**Duration**: ~45 minutes
**Agent**: opencode/big-pickle
**Phase**: build

---

## Intent

User asked to move `portals.yml` from project root to `config/` (aligning with `config/profile.yml`), then synchronize the portals configuration into a PostgreSQL database with bidirectional YAML↔DB sync — creating a hybrid architecture where the DB serves the admin/API and the YAML serves the CLI scripts.

## Outcome

Fully implemented. `portals.yml` moved to `config/portals.yml`, 5 Django models enriched/created, 3 migrations applied, sync service with roundtrip verification, admin with custom actions, views reading from DB, 159 tests passing, TypeScript clean.

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | Move `portals.yml` → `config/portals.yml` | Align with `config/profile.yml` directory convention | Keep at root (rejected — inconsistent) |
| 2 | Hybrid DB+YAML (not DB-only) | CLI scripts (`scan.mjs`, providers) consume YAML directly — rewriting them is a huge scope | Full DB migration (rejected — too many files to change), YAML-only (rejected — no admin/atomic writes) |
| 3 | `extra_config` JSONField for provider-specific blocks | `job_boards` have arbitrary fields (`siteKey`, `searchKeywords`, `pageSize`) that don't map to relational schema | Normalize every provider field (rejected — unmaintainable) |
| 4 | `TitleFilter` and `LocationFilter` as singletons (pk=1) | These are global config sections, not per-record entities | Separate model per keyword (over-engineered) |
| 5 | Drop `greenhouse_token`, `ashby_slug`, `lever_slug` from Portal model | Redundant with `api_endpoint` — the YAML uses `api` for the full URL, not individual slugs | Keep them (rejected — confusing dual representation) |
| 6 | Import uses `update_or_create` (upsert), no auto-delete | Safe — never destroys data on import; export overwrites YAML from DB state | Delete missing rows on import (too aggressive) |

## Files Created

| File | Purpose |
|---|---|
| `backend/apps/portals/services.py` | Bidirectional sync: `import_yaml_to_db()`, `export_db_to_yaml()`, helpers |
| `backend/apps/portals/migrations/0002_portals_enrich.py` | Schema enrichment + RunPython data import from YAML |
| `backend/apps/portals/migrations/0003_location_filter.py` | LocationFilter singleton model |
| `PLAN-PORTALS-DB-SYNC.md` | Full implementation plan document |

## Files Modified

| File | Change summary |
|---|---|
| `config/portals.yml` | Moved from root (git mv) |
| `backend/apps/portals/models.py` | Enriched `Portal` (+8 fields), `SearchQuery` (+name), added `TitleFilter`, `LocationFilter`, `JobBoard` |
| `backend/apps/portals/admin.py` | `PortalAdmin` with `ats_badge()`, `list_editable`, export/verify actions; `SearchQueryAdmin`, `JobBoardAdmin` |
| `backend/apps/portals/views.py` | `PortalsView.get` reads DB, `_post_portals` writes DB + exports YAML, added `_portal_to_dict`/`_job_board_to_dict` helpers |
| `backend/apps/skills_portfolio/views.py` | `ExtractPortalView` now creates in DB + exports YAML (was appending YAML directly) |
| `web/src/app/api/portals/route.ts` | Path updated to `config/portals.yml` |
| `web/src/app/api/skills/[...path]/route.ts` | Path updated to `config/portals.yml` |
| `web/src/lib/career-ops.ts` | Doctor prereq updated to `config/portals.yml` |
| `web/src/lib/core/portals.ts` | `loadYaml("config/portals.yml")` |
| `doctor.mjs` | All references updated to `config/portals.yml` |
| `.npmignore` | `portals.yml` → `config/portals.yml` |
| `scan.mjs` | `PORTALS_PATH` default updated |
| `stats.mjs` | `PORTALS_FILE` path updated |
| `verify-portals.mjs` | `DEFAULT_PORTALS_PATH` updated |
| `validate-portals.mjs` | `DEFAULT_PORTALS_PATH` updated |
| `openrouter-runner.mjs` | `readFile('config/portals.yml')` |

## Key Context

- DB now holds: 115 portals, 45 search queries, 12 job boards, 37 positive title keywords, 20 negative
- `LocationFilter` was added mid-implementation when `_post_portals` referenced it — required an extra migration (0003)
- The old `greenhouse_token`/`ashby_slug`/`lever_slug` fields were never populated by any code path — data was always in YAML under `api` — so no data was lost on removal
- `career-ops/scan.mjs` and `career-ops/plugins.mjs` are npm-shipped copies — NOT updated (they ship with the package, users get the updated version on next publish)

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `mv portals.yml config/portals.yml` | Move file to config/ | Success |
| `npx tsc --noEmit` | TypeScript compile check | Clean |
| `python manage.py makemigrations portals --name portals_enrich` | Generate schema migration | Generated 0002 |
| `python manage.py migrate portals` | Apply migrations + import data | Applied 0002 + 0003 |
| `python -c "..."` (multiple) | Verify DB counts, roundtrip sync | All matched |
| `pytest tests/ -v` | Run all backend tests | 159 passed |
| `node doctor.mjs --json` | Verify doctor recognizes new path | ✅ `config/portals.yml` found |

## Patterns Established

- **DB+YAML hybrid**: DB for admin/API, YAML for CLI. `export_db_to_yaml()` is the bridge.
- **Singleton models**: `TitleFilter.load()` / `LocationFilter.load()` pattern with `pk=1`
- **`extra_config` JSONField**: Catch-all for provider-specific fields that don't fit the relational schema
- **Migration RunPython import**: `import_portals_from_yaml()` seeds DB from YAML on first migration

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| `apps.get_app_config("portals")` returns `AppConfigStub` in migrations | Use `settings.CAREER_OPS_ROOT` instead of navigating from AppConfig | resolved |
| `LocationFilter` referenced in views but not created mid-implementation | Added model + migration 0003 | resolved |
| `career-ops/` directory has copies of scripts (scan.mjs, plugins.mjs) | Skipped — these are npm-shipped copies, not the source of truth | resolved |

## Action Items

- [ ] Consider adding a `POST /api/portals/sync` endpoint to manually trigger `import_yaml_to_db()` from the admin UI
- [ ] Consider adding `LocationFilter` import from YAML (currently only imports if `location_filter` key exists in YAML — which is commented out in the template)
- [ ] The `career-ops/` directory copies (scan.mjs, plugins.mjs, doctor.mjs) still reference old paths — these ship with npm and will be updated on next publish

## Related Sessions

- `archives/chats/2026-07-15_session_portals-kpi-hero-list-toggle.md` — Previous portals UI work (hero, KPIs, list/grid toggle, localStorage cache)
- `archives/chats/2026-07-15_session_profile-llm-extraction-variant.md` — Profile LLM extraction + variant system

---

## Full Conversation Summary

1. User asked to move `portals.yml` to `config/portals.yml` — done, 11 files updated
2. User asked whether to synchronize portals into the database — analyzed trade-offs, proposed hybrid model
3. User approved hybrid DB+YAML approach
4. Created `PLAN-PORTALS-DB-SYNC.md` with full 6-phase plan
5. User asked to create the plan as a .md file first — done
6. User approved execution — all 6 phases implemented:
   - Phase 1: Enriched 5 models, 3 migrations with RunPython data import
   - Phase 2: `services.py` with bidirectional sync, roundtrip verified
   - Phase 3: Admin with custom actions, ats_badge, list_editable
   - Phase 4: Views reading DB, writing DB + exporting YAML
   - Phase 5: 159 tests passing, TypeScript clean
   - Phase 6: doctor.mjs, .npmignore cleanup
7. Session archived
