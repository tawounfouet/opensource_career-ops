# Architecture — `scripts/python/`

## Package Tree

```
scripts/python/
├── admin/           (12 modules)   System admin, validation, diagnostics
├── cv/              (11 modules)   CV generation (HTML, LaTeX, PDF, cover letters)
├── evaluation/      (7 modules)    LLM-powered offer evaluation
├── export/          (2 modules)    Dashboard + data export
├── interview/       (2 modules)    Interview prep (STAR matching)
├── other/           (9 modules)    Miscellaneous utilities
├── pipeline/        (6 modules)    Browser extraction, liveness, agent inbox
├── plugins/         (6 modules)    External integrations (Gmail, Notion, Apify)
├── reply/           (4 modules)    Employer reply classification
├── salary/          (2 modules)    Compensation gap analysis
├── scanner/         (6 modules)    Job posting discovery
├── tracker/         (19 modules)   Pipeline tracking + data integrity
├── tests/           (28 files)     237 tests across all packages
├── docs/            (14 files)     Package documentation
├── ARCHITECTURE.md                 This file
├── INDEX.md                        Quick-reference index
├── README.md                       Project overview
└── pyproject.toml                  Python project config
```

---

## Diagram 1 — System Overview: Package Interactions

```
                          +-------------------------+
                          |        plugins/         |
                          |  +-------+------+-----+ |
                          |  | Gmail |Notion|Apify| |
                          |  +---+---+--+---+--+--+ |
                          |      | hooks |     |    |
                          +------+-------+-----+----+
                                 |       |     |
       +-------------------------+-------+-----+--------------------------+
       |                         |       |     |                          |
       v                         v       v     v                          v
+--------------+  +----------+  +-----------+  +---------------------------+
|     User     |  | scanner/ |  |  reply/   |  |          admin/           |
|  +--------+  |  |          |  |           |  |  +---------------------+  |
|  | cv.md  |  |  | scan     |  | reply     |  |  | doctor              |  |
|  +--------+  |  | ats-full |  | watch     |  |  | update_system       |  |
|  +--------+  |  | liveness |  | paste     |  |  | cv_sync_check       |  |
|  |profile |  |  | classify |  | reply     |  |  | validate_portals    |  |
|  |.yml    |  |  +----+-----+  | matcher   |  |  | analyze_patterns    |  |
|  +--------+  |       |        +-----+-----+  |  | upskill             |  |
+------+-------+       |              |        |  | stats               |  |
       |               v              |        |  | manifesto           |  |
       |         +-----------+        |        |  +---------------------+  |
       |         | pipeline  |        |        +---------------------------+
       |         | .md       |        |
       |         +-----+-----+        |
       |               |              |
       v               v              v
+--------------+  +---------------------------------------------------+
| evaluation/  |  |                    tracker/                       |
|              |  |  +----------+------------+---------------------+  |
| openai       |  |  | merge    | set        | verify              |  |
| gemini       |  |  | tracker  | status     | pipeline            |  |
| ollama       |  |  +----------+------------+---------------------+  |
| tailor       |  |  +----------+------------+---------------------+  |
| jd-skill-gap |  |  | dedup    | normalize  | reconcile           |  |
| eval-golden  |  |  +----------+------------+---------------------+  |
|              |  |  +----------+------------+---------------------+  |
+------+-------+  |  | find     | reposts    | invite-match        |  |
       |          |  +----------+------------+---------------------+  |
       v          |  +----------+------------+---------------------+  |
+--------------+  |  | reserve  | followup   | process-quality     |  |
|    cv/       |  |  | report   | cadence    | add-entry           |  |
|              |  |  +----------+------------+---------------------+  |
| generate_pdf |  +---------------------------------------------------+
| build_html   |                    |
| build_latex  |                    v
| cover-letter |            +---------------+
| verify-facts |            | applications  |
| templates    |            | .md           |
+------+-------+            +------+--------+
       |                           |
       v                           v
+--------------+           +---------------+
| output/*.pdf |           | data/         |
+--------------+           | follow-ups.md |
                           +---------------+

+--------------+     +---------------+      +---------------+
| interview/   |     |    other/     |      |   salary/     |
| match-star   +---->| openrouter    |      | salary-gap    |
+------+-------+     | assessment    |      +-------+-------+
       |             | funnel        |              |
       v             | prepare-app   |              v
+--------------+     | archive       |      +---------------+
| story-bank   |     | img-to-pdf    |      | salary-obs    |
| .md          |     | fingerprint   |      | .tsv          |
+--------------+     +---------------+      +---------------+
```

**Key interactions:**
- `scanner/` writes `pipeline.md`, feeds `tracker/`
- `evaluation/` reads `cv.md` + `profile.yml`, writes `reports/`, feeds `cv/` + `tracker/`
- `tracker/` is the central hub — merge, dedup, verify, status management
- `plugins/` injects hooks at scanner (provider), ingest (Gmail), export (Notion) points
- `reply/` ingests employer emails, feeds into `tracker/` via `set_status`

---

## Diagram 2 — Core Job Search Workflow: End-to-End Data Flow

```
  config/         +---+      portals.yml
  profile.yml ----+   |
                  |   |      +-------------------+
  cv.md ----------+   +----->|                   |
                              |     scanner/      |
  article ------------------->|                   |
  digest.md                   |  scan.py          |
                              |  scan_ats_full.py +---> data/scan-history.tsv
  portals.yml --------------->|  check_liveness   |     (dedup log)
                              |                   |
                              +--------+----------+
                                       |
                                       | new offers found
                                       v
                              +-------------------+
                              |                   |
                              |   data/           |
                              |   pipeline.md     |
                              |                   |
                              +--------+----------+
                                       |
                              +--------+----------+
                              |                   |
                              |  evaluation/      |
                              |                   |
                              |  openai_eval.py   |
                              |  gemini_eval.py   +---> reports/###
                              |  ollama_eval.py   |     -company-date.md
                              |  eval_golden.py   |     (Blocks A-F + G)
                              |  jd_skill_gap.py  |
                              +--------+----------+
                                       |
                        +--------------+--------------+
                        |                             |
                        v                             v
               +-----------------+           +-----------------+
               |                 |           |                 |
               |     cv/         |           |    tracker/     |
               |                 |           |                 |
               |  generate_pdf   |           |  merge_tracker  |
               |  build_html    +--+         |  set_status     |
               |  verify_facts   | |         |  verify_pipeline|
               |                 | |         +--------+--------+
               +-----------------+ |                  |
                        |          |                  v
                        v          |         +-----------------+
               +-----------------+ |         |  data/          |
               | output/         | |         |  applications   |
               | cv-*-*.pdf      | |         |  .md            |
               +-----------------+ |         +-----------------+
                                   |
                                   v
                          +-----------------+
                          |  interview/     |
                          |  match_star     |
                          +--------+--------+
                                   |
                                   v
                          +-----------------+
                          | interview-prep/ |
                          | story-bank.md   |
                          | {co}-{role}.md  |
                          +-----------------+

  Side channels:
  +------------------+          +------------------+
  | reply_watch.py   +--------->| set_status.py    |
  | paste_reply.py   |  email   | (status update)  |
  +------------------+  digest  +------------------+
```

**Walkthrough:**
1. **Discover** — `scanner/` reads `portals.yml`, hits ATS APIs, filters by title/location/salary, writes new URLs to `pipeline.md`
2. **Evaluate** — `evaluation/` reads each JD from `pipeline.md`, scores against candidate profile, writes `reports/###-company-date.md`
3. **Tailor** — `cv/` reads the evaluation report + `cv.md`, generates a tailored PDF → `output/`
4. **Track** — `tracker/merge_tracker` writes the evaluation to `applications.md`; `set_status` updates as pipeline progresses
5. **Reply** — `reply_watch` classifies employer emails, suggests `set_status` updates

---

## Diagram 3 — CLI Invocation Flow

```
  User input
      |
      |  npm run scan
      |  npm run doctor --json
      |  python -m scripts.python.scanner scan
      |  python -m scripts.python.tracker merge
      v
+---------------------+
|     package.json    |  npm scripts (42 Python, 2 JS fallback)
|  "scan": "python    |
|   -m scripts.python |
|   .scanner.scan"    |
+----------+----------+
           |
           | exec: python -m scripts.python.<pkg>.<module> [args...]
           v
+---------------------+
|  __main__.py        |  package dispatcher
|                     |
|  COMMANDS = {       |
|    "scan": "...     |
|    "ats-full": "..."|
|  }                  |
|                     |
|  cmd = sys.argv[1]  |
|  mod = __import__() |
|  mod.main(argv[2:]) |
+----------+----------+
           |
           | import + call main()
           v
+---------------------+
|  module.py          |  CLI module
|                     |
|  def main(argv):    |
|    parser =         |
|     argparse.Arg... |
|    args = parser    |
|     .parse_args()   |
|    # business logic |
|    return exit_code |
+----------+----------+
           |
           | read / write
           v
+---------------------+
|  data files         |
|  applications.md    |
|  pipeline.md        |
|  reports/*.md       |
|  scan-history.tsv   |
+---------------------+
```

**Key paths:**
- **package level:** `python -m scripts.python.scanner` → `__main__.py` dispatches to default module
- **module level:** `python -m scripts.python.scanner.scan` → direct module invocation
- **npm level:** `npm run scan` → `package.json` "scan" script → module invocation

---

## Diagram 4 — Data Stores: Read/Write Matrix

```
                      scanner  eval   cv     tracker  reply   admin   other   plugins
                      -------  ----   --     -------  -----   -----   -----   -------
cv.md ................. R ....  R .... RW .... . R .... . .... . R .... . .... .
config/profile.yml .... R ....  R .... R  .... . R .... . .... . R .... . .... .
article-digest.md ..... R ....  R .... R  .... . R .... . .... . R .... . .... .
portals.yml ........... RW ...  . .... .  .... . . .... . .... . R .... . .... .
pipeline.md ........... RW ...  R .... .  .... . W .... . .... . . .... . .... .
scan-history.tsv ...... RW ...  . .... .  .... . R .... . .... . . .... . .... .
reports/*.md .......... . ....  RW ... R  .... . R .... . .... . R .... . .... .
applications.md ....... . ....  . .... .  .... . RW ... . RW .. . R .... . .... .
follow-ups.md ......... . ....  . .... .  .... . RW ... . . .... . . .... . .... .
salary-observations.tsv. . ....  . .... .  .... . . .... . . .... . . .... . .... .
assessments.tsv ....... . ....  . .... .  .... . . .... . . .... . RW ... . .... .
story-bank.md ......... . ....  . .... .  .... . R .... . . .... . . .... . R ....
output/*.pdf .......... . ....  . .... .  W .... . . .... . . .... . . .... . .
scan-runs.tsv ......... . W .... . .... .  .... . . .... . . .... . . .... . .
reply-candidates.json . . ....  . .... .  .... . . .... . RW ... . . .... . .

R = read, W = write, . = no access
```

**Notes:**
- `scanner/` is the only writer of `pipeline.md` and `scan-history.tsv`
- `evaluation/` is the only writer of `reports/`
- `tracker/` is the only writer of `applications.md`
- `cv/` reads from `cv.md`, `profile.yml`, `article-digest.md` — validates all claims via `verify_facts`
- `plugins/` reads `story-bank.md` for Gmail-based interview matching (if enabled)

---

## Design Principles

### 1. One-to-one JS → Python parity
Every module in `scripts/archived-js/` has a Python equivalent. Same behavior, same CLI flags, same data files.

### 2. Canonical `main()` signature
All CLI modules expose:
```python
def main(argv: list[str] | None = None) -> int:
```
When `argv` is `None`, defaults to `sys.argv[1:]`. Returns exit code.

### 3. `python -m` invocation
No shebang scripts or wrapper files. Everything runs via `python -m scripts.python.<pkg>.<module>`.

### 4. `pathlib.Path` everywhere
No string concatenation for paths. `Path(__file__).resolve().parents[N]` for project-root resolution.

### 5. Argument parsing via `argparse`
Every CLI module uses `argparse` with identical flags to the JS originals.

---

## Cross-cutting Concerns

| Concern | Location |
|---------|----------|
| File locking | `fcntl.flock` in tracker/merge, tracker/set-status |
| SSL on macOS | Fixed via `Install Certificates.command` |
| Config loading | `config/profile.yml`, `portals.yml` via `yaml.safe_load` |
| Secrets | `dotenv` in `plugins/engine.py`, never in source |
| Path resolution | `Path(__file__).resolve().parents[...]` |

---

## Key Dependencies

```toml
[project]
dependencies = [
    "pyyaml",         # Config files
    "python-dotenv",  # Environment variables
    "certifi",        # SSL certificates
    "playwright",     # Browser automation (via subprocess)
    "rapidfuzz",      # Fuzzy matching (tracker/role_matcher)
    "httpx",          # HTTP client
]
```

---

## Test Architecture

- `pytest` with `tmp_path` fixtures for isolated file I/O
- No `__init__.py` in `tests/` (standard pytest auto-discovery)
- 28 test files, 237 tests, 12 packages covered
- CI: GitHub Actions runs `python -m pytest scripts/python/tests -q`

---

## Related Documentation

- `docs/plans/python-migration-remaining.md` — Migration plan and session log
- `docs/plans/cli-bridge.md` — CLI bridge implementation plan
- `docs/architecture/README.md` — Full project architecture
