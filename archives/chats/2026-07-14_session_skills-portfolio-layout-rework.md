# Session: Skills Portfolio — Backend + Frontend Build

**Date**: 2026-07-14
**Agent(s)**: opencode
**Phase**: build

---

## Intent

Build a complete Skills Portfolio feature for the career-ops Django backend + Next.js frontend: models, serializers, views, URLs, LLM services (extraction, mastery evaluation, benchmark, CV bullets, interview questions, discovery profile), CRUD UI, separate listing pages for competencies and experiences, and a reorganized main `/skills` page layout.

## Outcome

Fully functional skills portfolio with:
- Backend: 4 models (SkillExperience, SkillCompetency, SkillEvidence, SkillExtractionRun), 70 passing tests, 7 service modules (LLM client, prompts, extraction, matching, integration, exports, validation)
- Frontend: 3 pages (`/skills`, `/skills/list`, `/skills/experiences`), LLM integration via OpenAI `gpt-4o-mini` with `localFallback` proxy
- Final layout: sidebar (create forms + LLM extraction) + main (KPI cards, compact competency list, evidence tags, collapsible benchmark accordion)

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | Move evidence creation form to sidebar, replace full competency cards with compact list | User reported main page cluttered with forms + full list + benchmark | Keep current layout, or separate into 4 pages |
| 2 | Make benchmark section collapsible (`<details>`) | Heavy LLM tools should be hidden by default, expandable on demand | Modal, separate page, or always-visible panel |
| 3 | Remove `CompetencyRow`, `Pill` components, unused state/functions | Dead code from previous layout — cleaner bundle, fewer variables to track | Keep for future use |
| 4 | Use `fetchJsonSafe` for all LLM endpoints | LLM providers return `{error: ...}` with HTTP 200; regular `fetchJson` throws on these | Modify base `fetchJson` (would break non-LLM calls) |
| 5 | `localFallback` in Next.js proxy for all LLM routes | Allows LLM features to work without Django running (uses OpenAI directly) | Require Django server for everything |

---

## Files Created

| File | Purpose |
|---|---|
| `backend/apps/skills_portfolio/__init__.py` | App init |
| `backend/apps/skills_portfolio/admin.py` | Django admin registration |
| `backend/apps/skills_portfolio/apps.py` | App config |
| `backend/apps/skills_portfolio/models.py` | SkillExperience, SkillCompetency, SkillEvidence, SkillExtractionRun |
| `backend/apps/skills_portfolio/serializers.py` | DRF serializers |
| `backend/apps/skills_portfolio/views.py` | DRF viewsets + custom actions (validate, reject, dashboard, bulk_create) |
| `backend/apps/skills_portfolio/urls.py` | URL patterns |
| `backend/apps/skills_portfolio/services/__init__.py` | Services package |
| `backend/apps/skills_portfolio/services/llm_client.py` | OpenAI client with env-based config |
| `backend/apps/skills_portfolio/services/prompts.py` | LLM prompt templates |
| `backend/apps/skills_portfolio/services/extraction.py` | Experience → competency extraction |
| `backend/apps/skills_portfolio/services/matching.py` | JD ↔ competency matching |
| `backend/apps/skills_portfolio/services/integration.py` | CV bullets, interview questions, discovery profile |
| `backend/apps/skills_portfolio/services/exports.py` | Export competencies to various formats |
| `backend/apps/skills_portfolio/services/validation.py` | Competency validation logic |
| `backend/apps/skills_portfolio/migrations/0001_initial.py` | Initial migration |
| `backend/tests/test_skills_portfolio_api.py` | API tests (CRUD, dashboard, bulk) |
| `backend/tests/test_skills_llm_services.py` | LLM service tests (extraction, matching, integration) |
| `web/src/app/skills/page.tsx` | Route for `/skills` |
| `web/src/app/skills/list/page.tsx` | Route for `/skills/list` |
| `web/src/app/skills/experiences/page.tsx` | Route for `/skills/experiences` |
| `web/src/components/skills/skills-portfolio-view.tsx` | Main portfolio page (sidebar + summary) |
| `web/src/components/skills/skills-list-view.tsx` | Competency listing with KPI cards, filters, expandable rows, attach/detach |
| `web/src/components/skills/skills-experiences-view.tsx` | Experience listing with KPI cards, type breakdown, filters, expandable cards |
| `web/src/app/api/skills/[...path]/route.ts` | Next.js proxy with `localFallback` for LLM endpoints |

---

## Files Modified

| File | Change summary |
|---|---|
| `web/src/components/skills/skills-portfolio-view.tsx` | Major rework: sidebar layout, removed CompetencyRow/Pill/unused state, collapsible benchmark, evidence form in sidebar |

---

## Key Context

- LLM provider: OpenAI `gpt-4o-mini` via `backend/.env` (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`)
- DB seeded with 1 experience, 8 competencies (1 validated with evidence, 1 rejected)
- `fetchJson` throws on `{error: ...}` bodies even with HTTP 200; `fetchJsonSafe` handles this gracefully
- Evidence model requires at least one evidence item before validation passes
- French UI throughout (labels, placeholders, status names)
- `python-dotenv` loaded in `manage.py` for env access

---

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `cd backend && python manage.py test tests.test_skills_portfolio_api` | Verify API tests | 70 tests passed |
| `cd web && npx tsc --noEmit` | TypeScript type check | Clean, no errors |

---

## Patterns Established

- LLM errors display inline (not in global `error` state) via `fetchJsonSafe`
- All LLM endpoints use `localFallback` in proxy route — no Django required for LLM features
- KPI cards use `Stat` component with `instrumentSerif` font for numbers
- Listing pages: 6 KPI cards at top → filters → table/cards with expand
- Sidebar forms: compact, stacked, with loading states on buttons

---

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| Accidentally removed `extractFromExperience` during dead-code cleanup | Re-added it immediately after noticing | resolved |
| `BenchmarkPanel` referenced but not defined | Inlined as `<details>` collapsible section | resolved |

---

## Action Items

- [ ] Attach evidence to competencies from the competency listing page (attach/detach UI exists in `skills-list-view.tsx` but was removed from main page)
- [ ] Add `rejectCompetency` button back to competency listing page (currently only validate is available)
- [ ] Consider adding mastery evaluation UI back to competency listing page
- [ ] DB seed script or management command for fresh installs

---

## Related Sessions

- `archives/chats/2026-07-14_session_cv-generator-creation.md` — CV generator creation (earlier session same day)

---

## Full Conversation Summary

1. User asked to continue with next steps on the Skills Portfolio feature
2. Identified that the `/skills` main page was cluttered (forms + full competency cards + benchmark all visible)
3. Reorganized layout: sidebar for all creation forms + LLM extraction, main area for KPI cards, compact competency list, evidence tags, and collapsible benchmark
4. Referenced a non-existent `BenchmarkPanel` component — replaced with inline `<details>` accordion
5. Removed dead code: `CompetencyRow`, `Pill`, 6 unused state variables, 5 unused functions, 3 unused icon imports
6. Accidentally removed `extractFromExperience` during cleanup — re-added immediately
7. TypeScript check passed cleanly
8. Session archived
