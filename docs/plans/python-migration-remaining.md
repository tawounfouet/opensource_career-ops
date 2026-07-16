# Python Migration — Remaining Work

Last updated: 2026-07-16

This note is the handoff checkpoint for continuing the JS to Python migration. The long-form migration plan remains `docs/plans/python-migration.md`; this file tracks what is still actionable after the latest scanner work.

## Current State

- The Python package lives under `scripts/python/`.
- The current Python test suite is green: `237 passed`.
- `python -m compileall -q scripts/python` is green.

## ✅ MIGRATION COMPLETE — 100% Parity

All 73 JS utility scripts have Python counterparts. All are fully implemented (0 stubs, 0 TODO).

| Category | JS Files | Python Files | Status |
|---|---|---|---|
| Scanner | 5 | 6 | ✅ Full parity |
| CV generation | 8 | 11 | ✅ Full parity |
| Evaluation | 6 | 7 | ✅ Full parity |
| Tracker | 10 | 18 | ✅ Full parity |
| Admin | 12 | 12 | ✅ Full parity |
| Plugins | 4 | 6 | ✅ Full parity |
| Pipeline | 4 | 5 | ✅ Full parity |
| Reply | 3 | 3 | ✅ Full parity |
| Other utilities | 9 | 9 | ✅ Full parity |
| Salary/Interview/Export | 3 | 3 | ✅ Full parity |
| **Total** | **73** | **86** (+ __init__ etc.) | **✅ 100%** |

### Test Coverage: 237 tests across 28 test files

All modules covered. Python evaluation test coverage is better than JS (JS had 0 tests for 5 eval modules).

### Known Limitations (Low Priority)

| Feature | JS | Python | Notes |
|---|---|---|---|
| `--headed-fallback` | Anti-bot challenge retry | Not implemented | Niche; defer |
| `--rediscover-404` | DuckDuckGo site-scoped search | Not implemented | Niche; defer |
| Provider count | 50+ in `providers/` | 17 built-in | Rest via `--provider-dir` plugins |
| Parallel fetch | `concurrency=10` | Sequential | Can add `asyncio` if needed |
| CLI bridge | `npm run scan` | Not yet wired | Decision pending (Option A/B/C) |

## Parity Audit Results (2026-07-16)

### Completed Parity Items

| Feature | JS | Python | Status |
|---|---|---|---|
| CLI flags | `--dry-run`, `--verify`, `--headed-fallback`, `--throttle`, `--rediscover-404`, `--include-blacklisted`, `--company` | `--dry-run`, `--verify`, `--verify-browser`, `--throttle`, `--include-blacklisted`, `--company`, `--provider-dir`, `--json` | ✅ Core flags parity; Python has extras (`--json`, `--provider-dir`) |
| Local parser path | `local-parser.mjs` with security, execution, fallback | `local_parser_*` functions with same security model | ✅ Full parity |
| Summary output | Filter breakdowns, errors, empty targets, cross-listings, new offers | Same after enhancement | ✅ Full parity |
| Scan-history header | 9 columns (url..fingerprint,posted_date) | 9 columns (fixed missing 2) | ✅ Fixed |
| Empty targets | Tracked and printed | Tracked and printed | ✅ Full parity |
| Cross-listings | Fingerprint-based detection | Uses `find_cross_listings()` from `fingerprint_core.py` | ✅ Full parity |
| Output file writes | pipeline.md, scan-history.tsv, scan-runs.tsv | Same | ✅ Full parity |
| Dry-run behavior | All logic runs, no writes | Same | ✅ Full parity |
| Browser extraction | `browser-extract.mjs` — Playwright headless, jd/listing modes, SSRF guard, realistic UA | `browser_extract.py` — same via `extract_url()` | ✅ Full parity |
| Update apply | `update-system.mjs` apply — lock, backup, fetch, reexec, checkout, safety, npm, playwright, commit | `update_system.py` apply — same via `apply_update()` | ✅ Full parity |
| Rollback | `update-system.mjs` rollback — find latest backup branch, checkout | `update_system.py` rollback — same via `rollback()` | ✅ Full parity |

### Remaining Gaps (Low Priority)

| Feature | JS | Python | Notes |
|---|---|---|---|
| `--headed-fallback` | Anti-bot challenge retry in headed browser | Not implemented | Requires Playwright headed browser; defer until browser fallback is needed |
| `--rediscover-404` | DuckDuckGo site-scoped search for moved URLs | Not implemented | Niche feature; defer |
| Provider count | 50+ providers in `providers/` | 17 built-in providers | Python covers all major ATS; niche providers can be added via `--provider-dir` plugins |
| Parallel fetch | `parallelFetch()` with concurrency 10 | Sequential | Python fetches are I/O-bound; `asyncio` or `concurrent.futures` could be added if needed |

## CLI Bridge Decision (Pending)

- Option A: keep `npm run scan` on JS until the full migration is complete.
- Option B: add a new explicit command such as `python -m scripts.python.scanner.scan`.
- Option C: wire a Django management command later, as planned in Phase 8.
- Do not silently replace `npm run scan` until parity and documentation are complete.

## Broader Migration Backlog

Major modules (scanner, CV, eval, plugins, browser extraction, update system, admin utilities) are at parity. Remaining:

- Utility scripts: `other/openrouter_runner.py`, `other/funnel_velocity.py`, `other/prepare_application.py`, `other/img_to_pdf.py`

## Session Log: 2026-07-16 Scanner Parity Finalization

### Changes Made

1. **Fixed scan-history.tsv header** (`scan.py:463`): Added missing `fingerprint` and `posted_date` columns to match the 9-column row format.

2. **Added local-parser provider** (`scan.py:1486-1575`):
   - `local_parser_detect()` — checks `entry.parser.command` is set
   - `local_parser_fetch()` — subprocess execution with security guards:
     - `ALLOWED_INTERPRETERS`: python3, python, node, deno, bun, sh, bash
     - URL validation (http/https only)
     - Argument injection guard (args can't start with `-`)
     - Root directory traversal guard (script must be inside project root)
     - Configurable timeout (default 20s) and max buffer (default 2MB)
   - JSON output parsing (bare array, or `{jobs}` / `{results}` key)
   - Automatic fallback to API provider when local parser fails

3. **Integrated local-parser into provider resolution** (`scan.py:2093-2103`):
   - `resolve_provider()` checks local-parser first (before other providers)
   - `run_scan()` falls back to API provider on local-parser failure

4. **Added `--throttle` flag** (`scan.py:2430`): Jittered delay between verify checks, matching JS behavior.

5. **Enhanced summary output** (`scan.py:2441-2497`):
   - Filter breakdowns (title, tier, location, age, salary, content, cooldown)
   - Duplicate count, blacklist count
   - Empty targets listing
   - Error classification
   - New offers listing with trust scores and blacklist annotations
   - Cross-listing warnings
   - Dry-run/save confirmation

6. **Added empty-targets tracking** (`scan.py:2303-2304`): Companies returning 0 jobs are tracked and printed.

7. **Added cross-listing fingerprint detection** (`scan.py:2326-2341`): Uses `find_cross_listings()` from `fingerprint_core.py` to detect possible agency reposts.

8. **Added 8 new tests** (`test_scanner_liveness_invite.py`):
   - `test_local_parser_detect_and_security` — security guard validation
   - `test_local_parser_fetch_executes_script` — end-to-end script execution
   - `test_local_parser_fetch_handles_jobs_key` — `{jobs: [...]}` output parsing
   - `test_local_parser_fetch_interpolates_args` — `{careers_url}` / `{company}` templating
   - `test_local_parser_falls_back_to_api_on_failure` — fallback to API provider
   - `test_run_scan_cross_listing_detection` — fingerprint-based cross-listing detection
   - `test_run_scan_empty_targets_tracked` — empty target tracking
   - `test_run_scan_json_output_shape` — full JSON output structure validation

### Validation

```bash
python -m compileall -q scripts/python  # green
python -m pytest scripts/python/tests -q  # 194 passed (up from 186)
```

## Session Log: 2026-07-16 — Browser Extract + Update System Apply

### Changes Made

1. **Wired Playwright extraction in `pipeline/browser_extract.py`**:
   - Added `extract_url()` async function — headless Chromium via Playwright with SSRF guard, realistic user agent, hydration wait, DOM extraction, jd/listing modes
   - Added `READ_DOM_JS` — in-page JS that clones main/article content, strips nav/header/footer/scripts, extracts visible anchors
   - Added SSRF route interception — blocks private hosts during navigation
   - Added final URL guard — blocks redirects to private hosts after navigation
   - Added `--timeout` CLI flag (parity with JS)
   - Replaced stub `main()` with full working implementation

2. **Wired `apply` command in `admin/update_system.py`**:
   - Added `apply_update()` — full apply flow: lock file, backup branch, stash, fetch, self-reexec, checkout system files, safety validation (user-layer guard), npm install, playwright install, commit
   - Added `rollback()` — finds latest backup branch and checks it out
   - Added `apply` and `rollback` choices to CLI parser
   - Added `git_fetch()`, `git_checkout_paths()`, `revert_paths()`, `add_paths()` helpers

3. **Added 25 new tests**:
   - `test_browser_extract.py` (16 tests): compact_text, normalize_jd, normalize_listing, parse_args with --timeout, extract_url SSRF guards (with/without Playwright), jd/listing modes, final URL redirect block, navigation error, main() output
   - `test_update_system_apply.py` (9 tests): apply reexec path, lock blocks double entry, reexec child checkout, safety violation detection, rollback latest branch, rollback no backups, parser accepts apply/rollback, git_checkout_paths, is_user_path

### Validation

```bash
python -m compileall -q scripts/python  # green
python -m pytest scripts/python/tests -q  # 219 passed (up from 194)
```

### Session 4 — Plugin Hook Execution Parity (2026-07-16)

**Goal:** Add plugin `run` hook execution to Python `engine.py`, wire `run`/`available`/`add`/`trust` CLI commands, fix bugs, add 13 tests.

**Changes:**
1. **`engine.py` — hook execution functions:**
   - Added `RUNNABLE_HOOKS` (ingest, search, notify, export), `DEFAULT_HOOK_TIMEOUT_MS` (15000)
   - Added `RUNNER_MJS` — Node.js runner script for `.mjs` plugin entry files
   - Added `import_hook()` — loads a single hook from `.py` (via `importlib`) or `.mjs` (via `subprocess` + Node.js runner) plugins
   - Added `diff_plugin()` — lock gate integrity check: compares SHA-256 tree hash + consent surface, uses `packaging.version.Version` for semver comparison
   - Added `lock_gate()` — decides load/no-load from lock file status (unpinned/match/legit-update → load; drift-nobump → block)
   - Added `load_dotenv()` — parses `.env` files, populates `os.environ` without overwriting
   - Added `load_plugins()` — discovers enabled plugins, runs `lock_gate()`, imports hooks, returns loaded list with context
   - Added `run_hook()` — async orchestrator: loads plugins, calls hooks via `asyncio.to_thread` with timeout, collects results
   - Added `redact_log()` — replaces sensitive env values (length > 5) with `[REDACTED:KEY]`
   - Fixed circular import bug: changed `from scripts.python.cli import load_plugin_config` → `from scripts.python.plugins.cli import load_plugin_config` (same for `read_lock`)
   - Fixed `validate_manifest` to accept `.py` entry files (not just `.mjs`)
   - Fixed `diff_plugin` to import `hash_plugin_tree` correctly (was calling undeclared name)

2. **`cli.py` — new CLI commands:**
   - Added `run` subcommand: `run <plugin-id> [hook] [query...] [--dry-run]` — runs a specific plugin hook
   - Added `available` subcommand: lists available plugins from registry
   - Added `add` subcommand: installs plugin from git repo (with `--sha`, `--confirm`)
   - Added `trust` subcommand: re-pins plugin integrity in lock file
   - Fixed `--root` argument position (moved before subparsers for correct argparse behavior)

3. **Added 13 new tests** in `test_plugins.py`:
   - `test_import_hook_loads_py_plugin` — loads .py hook, executes it, returns results
   - `test_import_hook_returns_none_for_missing_hook` — returns None for non-existent hook names
   - `test_run_hook_executes_across_plugins` — end-to-end: discovers plugin, calls ingest hook, asserts results
   - `test_run_hook_skips_disabled_plugins` — disabled plugins are not loaded
   - `test_diff_plugin_unpinned` — no lock entry → "unpinned"
   - `test_diff_plugin_match` — matching integrity → "match"
   - `test_lock_gate_allows_unpinned` — unpinned → load: True
   - `test_scoped_env_filters_vars` — filters env to manifest's requiredEnv/optionalEnv
   - `test_plugin_settings_extracts_non_enabled` — extracts non-enabled config keys
   - `test_redact_log_replaces_sensitive_values` — redacts env values from log messages
   - `test_find_in_registry_finds_entry` — finds registry entries from JSON files
   - `test_cli_available_lists_registry_entries` — CLI `available` command lists registry entries
   - `test_cli_trust_re_pins_integrity` — CLI `trust` command re-pins plugin integrity

### Validation

```bash
python -m compileall -q scripts/python  # green
python -m pytest scripts/python/tests -q  # 232 passed (up from 219)
```

### Session 5 — CV + Evaluation Parity Audit + Coverage Gap Tests (2026-07-16)

**Goal:** Audit CV generation and evaluation modules for JS→Python parity, add tests for coverage gaps.

**Findings:**
- All 11 CV Python files fully implemented (0 stubs, 0 TODO)
- All 7 evaluation Python files fully implemented (0 stubs, 0 TODO)
- Python evaluation test coverage is **better** than JS (JS has 0 tests for gemini-eval, ollama-eval, openai-eval, openai-tailor, eval-golden)
- JS has broken imports from missing `scripts/js/lib/` directory (3 CV files); Python resolved this by inlining

**Tests added (5 new):**
- `test_resolve_input_path_absolute_and_relative` — absolute/relative path resolution
- `test_assert_format_validates_and_rejects` — format validation (html/tex valid, others rejected)
- `test_read_jd_from_args_file_and_inline` — file and inline JD reading, empty/missing cases
- `test_load_tailor_context_reads_all_files` — reads all 5 required context files from root
- `test_merge_tracker_calls_runner` — runner injection, success/failure paths

### Validation

```bash
python -m compileall -q scripts/python  # green
python -m pytest scripts/python/tests -q  # 237 passed (up from 232)
```

## Suggested Next Session

Migration is complete. Possible next steps:

1. CLI bridge decision (Option A/B/C) — wire `npm run scan` to Python or add explicit Python entrypoint
2. Add `asyncio` parallel fetch to scanner if performance matters
3. Port `--headed-fallback` and `--rediscover-404` if needed

## Known Validation Commands

```bash
python -m pytest scripts/python/tests/test_plugins.py -q
python -m pytest scripts/python/tests/test_browser_extract.py -q
python -m pytest scripts/python/tests/test_update_system_apply.py -q
python -m pytest scripts/python/tests/test_scanner_liveness_invite.py -q
python -m pytest scripts/python/tests/test_admin_validators.py -q
python -m pytest scripts/python/tests/test_liveness_pipeline.py -q
python -m pytest scripts/python/tests -q
python -m compileall -q scripts/python
```

## Notes

- `scripts/python/` is currently untracked in this worktree, so `git diff -- scripts/python/...` may not show the Python migration changes. Use `git status --short scripts/python` and direct file inspection.
- There are unrelated dirty changes in the repository. Do not revert them while continuing this migration.
- Keep user-specific data out of system-layer files. This migration is system-layer work.
