# Session: Python Migration — Scanner Parity Handoff

**Date**: 2026-07-15
**Agent**: Codex
**Phase**: build / handoff

---

## Intent

Continue the Python migration plan, specifically the `scan.mjs` replacement work in `scripts/python/scanner/scan.py`, then leave a clear Markdown handoff for the next session.

## Outcome

The Python scanner reached a solid parity checkpoint. Dynamic provider loading, full `tracked_companies` / `job_boards` scanning, many provider implementations, optional browser liveness, and run counters are in place. The final provider added in this session was SuccessFactors, including RMK tile parsing and CSB fallback. A new handoff document was created at `docs/plans/python-migration-remaining.md` and linked from `docs/plans/README.md`.

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | Keep JS `npm run scan` as the public default for now | Python scanner is strong, but needs a formal parity audit before replacing the user-facing command | Silently switch package scripts to Python |
| 2 | Add SuccessFactors directly to Python built-in providers | It is part of the existing JS provider set and appears in portal templates | Defer SuccessFactors until after CLI bridge |
| 3 | Split liveness flags into API-only and browser fallback | Python can keep deterministic API checks while making Playwright opt-in | Make every `--verify` scan launch browser checks |
| 4 | Create a separate remaining-work document | The long plan is global; the next session needs a short operational checklist | Append a short note to the long migration plan only |

## Files Created

| File | Purpose |
|---|---|
| `docs/plans/python-migration-remaining.md` | Current handoff checklist for remaining Python migration work |
| `archives/chats/2026-07-15_session_python-migration-scan-parity.md` | Structured archive summary for this session |
| `archives/2026-07-15_session-codex_python-migration-scan-parity.md` | Transcript-style archive for this session |

## Files Modified

| File | Change summary |
|---|---|
| `scripts/python/scanner/scan.py` | Added provider plugin loading, scan orchestration parity work, many built-in providers, browser liveness wiring, and SuccessFactors RMK/CSB support |
| `scripts/python/scanner/check_liveness.py` | Added liveness checker builder that can route through API checks and optional browser fallback |
| `scripts/python/pipeline/liveness_browser.py` | Added Playwright/browser-backed liveness check helper |
| `scripts/python/admin/verify_portals.py` | Reused Python scanner providers for non-ATS provider verification |
| `scripts/python/tests/test_scanner_liveness_invite.py` | Added scanner/provider tests, including dynamic providers and SuccessFactors parser/fetch behavior |
| `scripts/python/tests/test_liveness_pipeline.py` | Added API/browser liveness routing tests |
| `scripts/python/tests/test_admin_validators.py` | Added provider-backed portal verification coverage |
| `docs/plans/README.md` | Linked the new Python migration remaining-work handoff |

---

## Key Context

- The original plan moved from `PLAN-PYTHON-MIGRATION.md` to `docs/plans/python-migration.md`.
- `scripts/python/` is untracked in the current worktree, so `git diff -- scripts/python/...` may not show the Python migration changes.
- The Python scanner now includes built-in providers for Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, Teamtailor, Personio, Recruitee, Pinpoint, BambooHR, Comeet, RemoteOK, Remotive, CSOD, Phenom, and SuccessFactors.
- SuccessFactors support mirrors the JS provider shape:
  - RMK tile endpoint: `/tile-search-results/?startrow=N`
  - CSB endpoint: `/services/recruiting/v1/jobs`
  - Locale discovery through `/search/`
  - Branded hosts require explicit `provider: successfactors`
- The scanner still needs a formal side-by-side parity audit before becoming the default CLI entrypoint.

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `node scripts/js/update-system.mjs check` | Session update check | Silent/offline-style non-blocking result |
| `node scripts/js/doctor.mjs --json` | Cold-start check | Reported missing `cv.md`; ignored because this was system-layer migration work |
| `python -m pytest scripts/python/tests/test_scanner_liveness_invite.py -q` | Scanner/provider focused tests | `15 passed` |
| `python -m pytest scripts/python/tests/test_admin_validators.py -q` | Admin/portal validator tests | `15 passed` |
| `python -m pytest scripts/python/tests/test_liveness_pipeline.py -q` | Liveness API/browser routing tests | `6 passed` |
| `python -m pytest scripts/python/tests -q` | Full Python script test suite | `186 passed` |
| `python -m compileall -q scripts/python` | Python syntax/import compilation check | Passed |

## Patterns Established

- Provider functions in Python follow the same contract as JS providers: `detect(entry)` plus `fetch(entry, ctx)`.
- Dynamic Python provider plugins are loaded through `--provider-dir`.
- Browser verification is explicit through `--verify-browser`.
- Handoff docs for long-running migration work should live in `docs/plans/` and be linked from `docs/plans/README.md`.

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| SuccessFactors RMK test failed on the second page request `startrow=1` | Updated the test mock to return an empty HTML fragment for `startrow=1`, matching pagination stop behavior | resolved |
| Original plan path was not at repo root anymore | Found canonical plan at `docs/plans/python-migration.md` and created a separate handoff file | resolved |
| `scripts/python/` shows as untracked | Noted explicitly in the handoff so future diffs use `git status` and direct inspection | open |

---

## Action Items

- [ ] Run a formal parity audit of `scripts/js/scan.mjs` versus `scripts/python/scanner/scan.py`
- [ ] Add end-to-end `run_scan()` tests with temporary `config/portals.yml`, `pipeline.md`, `scan-history.tsv`, and `scan-runs.tsv`
- [ ] Decide whether to implement local parser execution in Python or document it as a deferred gap
- [ ] Decide CLI bridge strategy before replacing `npm run scan`
- [ ] Update user-facing docs only after the CLI bridge decision

## Related Sessions

- `archives/chats/2026-07-15_session_scripts-migration-python.md` — Original scripts relocation and Python migration plan
- `docs/plans/python-migration.md` — Long-form migration plan
- `docs/plans/python-migration-remaining.md` — Current remaining-work checklist

---

## Full Conversation Summary

1. The user repeatedly asked to continue implementing `docs/plans/python-migration.md`.
2. The active focus narrowed to the Python replacement for `scan.mjs`.
3. The scanner gained dynamic provider loading, full tracked-company and job-board orchestration, provider plugins, API/browser liveness wiring, and full run counters.
4. Built-in provider coverage was expanded across major ATS and job-board sources.
5. SuccessFactors was added with RMK tile parsing and CSB fallback.
6. Targeted scanner, admin validator, and liveness tests passed.
7. The full Python test suite passed with `186 passed`, and `compileall` passed.
8. The user asked what remained; the answer was captured into `docs/plans/python-migration-remaining.md`.
9. The user asked to archive the session; this summary and the transcript-style archive were created.
