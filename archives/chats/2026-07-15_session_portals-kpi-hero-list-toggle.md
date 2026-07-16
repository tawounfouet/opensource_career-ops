# Session: Portals UI Rework + KPI Fix + Profile Overrides

**Date**: 2026-07-15
**Duration**: ~90 minutes
**Agent(s)**: opencode
**Phase**: build

---

## Intent

Fix the portals dashboard KPIs showing 0/0/0/0 on first load, deduplicate Mistral entries in portals.yml, add per-field override indicators in the profile editor, and rework the portals list page layout to match the discovery/skills hero style with a grid/list view toggle.

## Outcome

All tasks completed. KPIs now correctly display health data (71 Live, 3 Empty, 12 Broken, 14 No ATS). The verify route was rewritten to capture output despite Node.js piped-stdout buffering. Both portals pages (`/portals` and `/portals/list`) now use the same hero pattern as discovery/skills. The list page has a grid/list view toggle. Profile editor shows per-field override chips.

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | Use `bash -c "node script > tmpfile 2>&1"` for verify route | Node.js fully-buffers piped stdout for non-TTY; execFile/spawn both lose output on timeout. File I/O bypasses this entirely. | Spawn with streaming (still buffered), increasing timeout (still loses output on kill) |
| 2 | Treat health data with 0 companies as "no data" | Cache could contain `{companies:[]}` from timed-out verify; showing 0 is misleading | Auto-run health check on mount (slow ~90s) |
| 3 | Merge Mistral entries: keep "Mistral AI" as single entry with both careers_url and api | Lever API is the reliable source; mistral.ai/careers is the public page | Keep two separate entries |
| 4 | Per-field overrides via `computeOverriddenFields()` returning `Map<section, fieldLabels[]>` | More granular than section-level "variante" badge; shows exactly which fields differ | Keep only section-level badges |
| 5 | Move hero into view components (not page wrappers) | Matches discovery/skills convention; pages just render `<View />` | Keep page-level headers |
| 6 | List view as compact table | Shows more companies on screen, easier to scan for broken entries | Alternative: horizontal card layout |

## Files Created

| File | Purpose |
|---|---|
| `web/src/components/portals-list-view.tsx` | Full portals list page with hero, stats, search, filters, grid/list toggle |
| `web/src/components/profile-editor.tsx` | Full-width profile editor with sidebar, LLM extraction, per-field override chips |
| `web/src/components/profile-list-view.tsx` | Profile/variant list page with cards, override indicators |
| `web/src/app/portals/list/page.tsx` | Route for `/portals/list` |
| `web/src/app/profile/page.tsx` | Route for `/profile` |
| `web/src/app/profile/list/page.tsx` | Route for `/profile/list` |
| `web/src/app/api/profile/variants/route.ts` | Variant list/create API |
| `web/src/app/api/profile/variants/[name]/route.ts` | Variant delete API |
| `config/profiles/` | Directory for profile YAML variants |

## Files Modified

| File | Change summary |
|---|---|
| `web/src/app/api/portals/verify/route.ts` | Rewritten: uses `bash -c` + file redirect to capture verify output despite Node.js piped-stdout buffering. Timeout 118s. |
| `web/src/components/portals-view.tsx` | Added hero section (dot-bg, blur blob, instrumentSerif title, badge chip, action buttons). Empty health data shows "—" instead of 0. Button label "Check portal health" when no data. |
| `web/src/components/portals-list-view.tsx` | Full rewrite: hero section matching discovery/skills style, grid/list view toggle, stats cards show "—" when no health data, per-field health label in hero badge |
| `web/src/app/portals/page.tsx` | Simplified to `<PortalsView />` (hero moved into component) |
| `web/src/app/portals/list/page.tsx` | Simplified to `<PortalsListView />` (hero moved into component) |
| `web/src/components/profile-editor.tsx` | Added `computeOverriddenFields()`, `FIELD_LABELS` mapping, per-field override chips on CollapsiblePanel headers, localStorage variant persistence |
| `portals.yml` | Merged Mistral entries: single "Mistral AI" with both careers_url and api. Removed duplicate "Mistral" entry. |

## Key Context

- **Node.js piped-stdout buffering**: When stdout is piped (not a TTY), Node.js uses full buffering. `console.log` output sits in a buffer that only flushes when full or process exits. If the process is killed by timeout before the buffer fills, all output is lost. Workaround: redirect to a temp file via `bash -c`.
- **Verify script performance**: `verify-portals.mjs` takes 60-90s for 115 companies (HTTP requests per company). The serverless function has a 120s `maxDuration` limit.
- **Health cache format**: `{ data: { available, configured, companies: [...] }, ts: number }` stored in localStorage key `portals_health_cache` with 1-hour TTL.
- **Hero pattern**: `section.relative.isolate.overflow-hidden` with `dot-bg` background, brand blur blob (`-right-32 -top-40 h-96 w-96`), `instrumentSerif` title (`text-5xl md:text-7xl`), badge chip, right-aligned action buttons.
- **career-ops update**: v1.19.0 → v1.20.0 applied (223 system paths, includes CareerOps Manifesto).

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `node update-system.mjs apply` | Apply career-ops update | v1.19.0 → v1.20.0, 223 paths updated |
| `node verify-portals.mjs` | Test verify script directly | Works (102 lines output) |
| `execFile('node', ['verify-portals.mjs'])` | Test via Node child process | 0 output (buffering issue) |
| `bash -c "node script > tmpfile"` | Test file redirect approach | Works (102 lines captured) |
| `npx tsc --noEmit` | TypeScript check | Clean throughout |

## Patterns Established

- **Hero pattern**: All major pages use the same hero: `section` with `dot-bg`, blur blob, `instrumentSerif` title, badge chip, description, right-aligned actions
- **Page convention**: Pages render `<View />` directly; view components handle their own layout/hero
- **Health data empty state**: Show "—" in stat cards when health data has 0 companies; show "Check portal health" button instead of "Re-check"
- **Verify output capture**: Use `bash -c "node script > tmpfile 2>&1"` + `fs.readFileSync` for scripts that produce heavy stdout via piped child processes

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| KPIs all showing 0 despite cached health data | Root cause: execFile couldn't capture verify output (Node.js pipe buffering). Fixed with file redirect. | resolved |
| `portals.yml` had duplicate Mistral entries | Merged into single "Mistral AI" entry with both careers_url and api | resolved |
| Profile editor only showed section-level "variante" badge | Added `computeOverriddenFields()` with per-field labels; shows "● Nom", "● Email" etc. | resolved |
| Django tests failing (test_discovery_api.py, etc.) | Pre-existing `DJANGO_SETTINGS_MODULE` issue, unrelated to frontend changes | known |

## Action Items

- [ ] Consider running health check automatically on first visit (currently user must click)
- [ ] Investigate Django test configuration issues (multiple test files fail with `ImproperlyConfigured`)
- [ ] Consider adding per-field override indicators to the profile list page (variant cards)

## Related Sessions

- `archives/chats/2026-07-15_session_profile-llm-extraction-variant.md` — Profile LLM extraction, variant system, override badges
- `archives/chats/2026-07-14_session_skills-portfolio-layout-rework.md` — Skills portfolio layout and navigation

---

## Full Conversation Summary

1. User asked "What did we do so far?" — summarized all previous work (skills portfolio, profile system, portal extraction, health check caching)
2. User said "Continue if you have next steps" — identified 3 open items: KPIs at 0, Mistral dedup, per-field overrides
3. Applied career-ops update v1.19.0 → v1.20.0
4. Fixed KPIs: stat cards show "—" when no health data; empty health data treated as "no data" state
5. Deduplicated Mistral entries in portals.yml (merged into single "Mistral AI" entry)
6. Added per-field override indicators in profile editor (FIELD_LABELS mapping, computeOverriddenFields, chips on CollapsiblePanel)
7. User reported "tout est toujours à 0" — KPIs still showing 0 despite cached data
8. Root cause: execFile couldn't capture verify-portals.mjs output (Node.js piped-stdout buffering); verify route was getting `{companies:[]}`
9. Rewrote verify route: `bash -c "node script > tmpfile 2>&1"` + `fs.readFileSync` bypasses pipe buffering entirely
10. User confirmed KPIs now work: 71 Live, 3 Empty, 12 Broken, 14 No ATS
11. User asked for 3-column grid on portals list — changed `sm:grid-cols-2` to `sm:grid-cols-2 xl:grid-cols-3`
12. User asked portals list to match hero style of discovery/skills — moved header into view component, added full hero pattern
13. User asked for grid/list view toggle — added `viewMode` state, toggle buttons, compact table list view
14. User asked to archive session
