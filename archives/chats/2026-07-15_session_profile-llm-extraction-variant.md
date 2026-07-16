# Session: Profile LLM Extraction + Variant UX Polish

**Date**: 2026-07-15
**Duration**: ~2 hours
**Agent**: opencode/big-pickle
**Phase**: build

---

## Intent

Add LLM-powered profile extraction from free text (CV, transcript, career description) to the profile editor sidebar, then polish the variant UX across the profile and variant list pages.

## Outcome

- Backend: prompt, extraction function, endpoint, and proxy route for profile extraction from text
- Frontend: "Extraction LLM" panel in profile sidebar with textarea, extract button, and result display
- Variant persistence: active variant now survives page refresh via localStorage
- Variant list page: shows override chips with dot indicators for each overridden field
- Profile editor: shows "variante" badge only on sections where values actually differ from base profile

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | Profile extraction merges into YAML directly | Consistent with how profile is stored; no DB needed | DB-based profile (rejected earlier in architecture phase) |
| 2 | Use localStorage for active variant persistence | Simple, no backend changes needed; variant is UI state not data | Cookie, URL param, server-side session |
| 3 | Compare actual values (JSON.stringify) to determine overridden sections | Variant files contain ALL sections even if identical to base; checking key existence alone was inaccurate | Check if key exists in overrides object |
| 4 | Chips with dot indicators for override display | More visual than plain text; scannable at a glance | Plain text list, checkbox icons |

## Files Created

| File | Purpose |
|---|---|
| `archives/chats/2026-07-15_session_profile-llm-extraction-variant.md` | This session archive |

## Files Modified

| File | Change summary |
|---|---|
| `backend/apps/skills_portfolio/services/prompts.py` | Added `PROFILE_EXTRACTION_SYSTEM` + `PROFILE_EXTRACTION_USER` prompts |
| `backend/apps/skills_portfolio/services/extraction.py` | Added `extract_profile_from_text()` function |
| `backend/apps/skills_portfolio/views.py` | Added `ExtractProfileView` class with merge-to-YAML logic |
| `backend/apps/skills_portfolio/urls.py` | Added route `llm/extract-profile` |
| `web/src/app/api/skills/[...path]/route.ts` | Added local fallback proxy for `llm/extract-profile` |
| `web/src/components/profile-editor.tsx` | Added LLM extraction panel, localStorage persistence, override section badges |
| `web/src/components/profile-list-view.tsx` | Added active variant detection from localStorage, override chips with dot indicators |

---

## Key Context

- Profile YAML is at `config/profile.yml`, variants at `config/profiles/{name}.yml`
- Variant files from LLM extraction contain ALL sections (full copy), not just overrides
- `SECTION_TO_OVERRIDES` mapping links UI section names to YAML keys
- `computeOverriddenSections()` does deep comparison between base and variant profiles
- LLM extraction endpoint accepts `persist: true` + optional `variant` name
- Extraction covers: candidate info, narrative, languages, interests, regulations, compensation, location

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `npx tsc --noEmit` | TypeScript check | Clean (multiple times) |
| `pytest tests/ -x -q` | Backend tests | 159 passed |

## Patterns Established

- LLM extraction panels follow same pattern: textarea + button + result display + error handling
- Variant persistence: localStorage key `profile_active_variant`
- Override detection: fetch base + variant, `JSON.stringify` compare per section
- Badge: `● variante` chip with `brand` dot on overridden section headers

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| Variant not persisting across page refresh | Added localStorage read/write for `profile_active_variant` | resolved |
| Badge showing on all sections even when unchanged | Changed from checking key existence to deep-comparing actual values | resolved |
| Profile list page not reflecting active variant | Read localStorage on mount, highlight matching card | resolved |

---

## Action Items

- [ ] Test extraction with actual CV text to verify field parsing quality
- [ ] Consider adding per-field override indicators (not just per-section)
- [ ] Consider adding a "Reset to base" button per section in variant mode

---

## Full Conversation Summary

1. User asked to add LLM profile extraction to the sidebar, similar to experiences/education extraction
2. Added `PROFILE_EXTRACTION_SYSTEM`/`PROFILE_EXTRACTION_USER` prompts in `prompts.py`
3. Added `extract_profile_from_text()` in `extraction.py`
4. Added `ExtractProfileView` endpoint with YAML merge logic (supports base + variant)
5. Added `llm/extract-profile` route and proxy fallback
6. Added "Extraction LLM" panel in profile sidebar with textarea, extract button, and result chips
7. User reported variant not persisting across refresh — fixed with localStorage
8. User reported variant list page always showing "Principal" as active — fixed by reading localStorage
9. User wanted override indicators on variant list page — added chips with dot indicators
10. User wanted override indicators on profile editor sections — added "variante" badge
11. User reported badges showing on all sections even when unchanged — fixed by deep-comparing actual values instead of checking key existence
