# Plan d'Action — Moteur Python (FastAPI) pour career-ops

> **Objectif :** Remplacer le backend Node.js (31 routes API Next.js) par un moteur Python FastAPI, tout en gardant le frontend Next.js existant (`web/`) comme client.

---

## Table des matières

1. [Architecture actuelle vs cible](#1-architecture-actuelle-vs-cible)
2. [Inventaire des 31 routes API](#2-inventaire-des-31-routes-api)
3. [Stratégie de migration](#3-stratégie-de-migration)
4. [Structure du projet Python](#4-structure-du-projet-python)
5. [Phase 1 — Fondations](#5-phase-1--fondations)
6. [Phase 2 — Core data (lectures)](#6-phase-2--core-data-lectures)
7. [Phase 3 — Écritures et intégrité](#7-phase-3--écritures-et-intégrité)
8. [Phase 4 — Orchestration CLI](#8-phase-4--orchestration-cli)
9. [Phase 5 — Streaming et temps réel](#9-phase-5--streaming-et-temps-réel)
10. [Phase 6 — Frontend adaptation](#10-phase-6--adaptation-du-frontend)
11. [Phase 7 — Tests et validation](#11-phase-7--tests-et-validation)
12. [Phase 8 — Déploiement](#12-phase-8--déploiement)
13. [Matrice de couverture](#13-matrice-de-couverture)
14. [Risques et mitigations](#14-risques-et-mitigations)
15. [Estimation temporelle](#15-estimation-temporelle)

---

## 1. Architecture actuelle vs cible

### Actuelle : Next.js API Routes → child_process → Node.js scripts

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend React (web/)                  │
│  app/page.tsx, components/, etc.                        │
└──────────────────────┬──────────────────────────────────┘
                       │ fetch("/api/...")
┌──────────────────────▼──────────────────────────────────┐
│              Next.js API Routes (31 routes)              │
│  src/app/api/*/route.ts                                 │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ File I/O direct  │  │ child_process.spawn(exec)    │  │
│  │ fs.readFileSync  │  │ → scan.mjs                   │  │
│  │ atomicWrite      │  │ → tracker.mjs                │  │
│  │ parseApplications│  │ → followup-cadence.mjs       │  │
│  └─────────────────┘  │ → verify-portals.mjs          │  │
│                        │ → Claude/Codex/OpenCode CLI   │  │
│  Bridge:               │   (assistant, evaluate, etc.) │  │
│  career-ops.ts         └──────────────────────────────┘  │
│  clis.ts                                                  │
│  core/*.ts                                               │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│           career-ops core (fichiers .mjs + données)     │
│  cv.md, data/applications.md, reports/, portals.yml...  │
└─────────────────────────────────────────────────────────┘
```

### Cible : FastAPI (Python) → child_process → Node.js scripts

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend React (web/)                  │
│  app/page.tsx, components/, etc.                        │
└──────────────────────┬──────────────────────────────────┘
                       │ fetch("http://localhost:8000/api/...")
┌──────────────────────▼──────────────────────────────────┐
│                 FastAPI Backend (Python)                  │
│  app/main.py                                            │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ File I/O direct  │  │ asyncio.create_subprocess_exec│  │
│  │ pathlib.Path     │  │ → scan.mjs                   │  │
│  │ atomic_write     │  │ → tracker.mjs                │  │
│  │ parse_tracker    │  │ → followup-cadence.mjs       │  │
│  └─────────────────┘  │ → Claude/Codex CLI            │  │
│                        └──────────────────────────────┘  │
│  Services:                                               │
│  tracker_service.py, scan_service.py, etc.              │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│           career-ops core (fichiers .mms + données)     │
│  cv.md, data/applications.md, reports/, portals.yml...  │
└─────────────────────────────────────────────────────────┘
```

### Ce qui change vs ce qui reste

| Composant | Changement | Impact |
|-----------|-----------|--------|
| **Frontend React** | Aucun changement majeur | URL de base : `/api/*` → `http://localhost:8000/api/*` |
| **API Routes Next.js** | **Supprimé** → remplacé par FastAPI | 31 routes à recréer |
| **lib/*.ts (bridge)** | **Réécrit** en Python | career-ops.ts, clis.ts, core/*.ts |
| **career-ops core (.mjs)** | **Aucun changement** | Les scripts Node.js restent intacts |
| **Données (cv.md, etc.)** | **Aucun changement** | Même format, même emplacement |

---

## 2. Inventaire des 31 routes API

### Catégorie A : Données pures (lecture/écriture fichiers)

| Route | Méthode | Logic Node | Port Python |
|-------|---------|-----------|-------------|
| `/api/pipeline` | GET | `pipelineSummary()` — lit applications.md + pipeline.md | `tracker_service.py` |
| `/api/cv` | GET/POST | Lit/écrit `cv.md` via `atomicWriteWithBackup` | `cv_service.py` |
| `/api/cv/ingest` | POST | Parse un CV uploadé | `cv_service.py` |
| `/api/cv-pdf` | GET | Génère le CV HTML (lit cv.md + template) | `cv_service.py` |
| `/api/profile` | GET/POST | Lit/écrit `config/profile.yml` | `profile_service.py` |
| `/api/portals` | GET/POST | Lit/écrit `portals.yml` | `portals_service.py` |
| `/api/portals/verify` | POST | Vérifie les slugs ATS | `portals_service.py` |
| `/api/tracker/delete` | POST | `tracker.mjs delete --num N` | `tracker_service.py` |
| `/api/status` | POST | Met à jour le statut d'une ligne tracker | `tracker_service.py` |
| `/api/memory` | GET/POST | Lit/écrit `modes/_profile.md` (section web-assistant) | `memory_service.py` |
| `/api/doctor` | GET | Vérifie les prérequis (file exists) | `doctor_service.py` |
| `/api/version` | GET | Lit `VERSION` file | `system_service.py` |
| `/api/whats-new` | GET | Lit changelog | `system_service.py` |
| `/api/logo` | GET | Sert le logo SVG | `static` |
| `/api/followups` | GET | Exécute `followup-cadence.mjs --json` | `followup_service.py` |
| `/api/followups/log` | POST | Ajoute une entrée dans `data/follow-ups.md` | `followup_service.py` |
| `/api/usage` | GET | Calcule les stats d'usage | `stats_service.py` |
| `/api/report/shape` | POST | Lit + shape un rapport | `report_service.py` |

### Catégorie B : Orchestration CLI (child_process)

| Route | Méthode | Logic Node | Port Python |
|-------|---------|-----------|-------------|
| `/api/run` | POST | Spawne Claude/Codex/OpenCode pour évaluation/PDF | `runner_service.py` |
| `/api/assistant` | POST | Spawne un CLI IA pour conversation | `assistant_service.py` |
| `/api/explore/ai` | POST | Spawne un CLI IA pour découverte IA | `explore_service.py` |

### Catégorie C : Scan (child_process + parsing)

| Route | Méthode | Logic Node | Port Python |
|-------|---------|-----------|-------------|
| `/api/explore` | POST | Exécute `scan-ats-full.mjs --dry-run` | `scan_service.py` |
| `/api/explore/ai/known` | GET | Assemble le contexte de dédup | `explore_service.py` |
| `/api/explore/add` | POST | Ajoute une offre découverte au pipeline | `pipeline_service.py` |

### Catégorie D : Apply (Playwright headless)

| Route | Méthode | Logic Node | Port Python |
|-------|---------|-----------|-------------|
| `/api/apply/session` | POST | Ouvre une session Playwright sur un formulaire | `apply_service.py` |
| `/api/apply/prefill` | POST | Pré-remplit un champ de formulaire | `apply_service.py` |
| `/api/apply/fill` | POST | Remplit plusieurs champs | `apply_service.py` |
| `/api/apply/drive` | POST | Extrait les champs d'un formulaire | `apply_service.py` |
| `/api/apply/close` | POST | Ferme la session Playwright | `apply_service.py` |

### Catégorie E : Autres

| Route | Méthode | Logic Node | Port Python |
|-------|---------|-----------|-------------|
| `/api/runs/save` | POST | Sauvegarde un log de run | `run_service.py` |
| `/api/clis` | GET | Détecte les CLIs installés | `cli_service.py` |

---

## 3. Stratégie de migration

### Principe : « Strangler Fig » — encapsuler, puis remplacer

```
Phase 1-2 : FastAPI lit les mêmes fichiers (aucun impact frontend)
Phase 3-4 : FastAPI gère les écritures + orchestration CLI
Phase 5   : Frontend pointe vers FastAPI (swap des URLs)
Phase 6-7 : Nettoyage, tests, déploiement
```

### Règles fondamentales

1. **Le frontend ne change PAS** — on change les URLs de base, pas la structure des requêtes
2. **Les scripts .mjs restent intacts** — FastAPI les appelle via `asyncio.create_subprocess_exec`
3. **Le Data Contract est préservé** — même séparation système/utilisateur
4. **Compatibilité binaire** — même format de réponse JSON, mêmes codes HTTP
5. **Migration incrémentale** — chaque phase est indépendante et testable

---

## 4. Structure du projet Python

```
backend/
├── pyproject.toml                    # Poetry/pdm config
├── README.md
├── .env.example
│
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app, CORS, lifespan
│   ├── config.py                     # Settings (CAREER_OPS_ROOT, etc.)
│   ├── deps.py                       # Dependency injection
│   │
│   ├── api/                          # Route handlers (31 routes)
│   │   ├── __init__.py
│   │   ├── pipeline.py               # GET /api/pipeline
│   │   ├── cv.py                     # GET/POST /api/cv
│   │   ├── cv_ingest.py              # POST /api/cv/ingest
│   │   ├── cv_pdf.py                 # GET /api/cv-pdf
│   │   ├── profile.py                # GET/POST /api/profile
│   │   ├── portals.py                # GET/POST /api/portals
│   │   ├── portals_verify.py         # POST /api/portals/verify
│   │   ├── tracker_delete.py         # POST /api/tracker/delete
│   │   ├── status.py                 # POST /api/status
│   │   ├── memory.py                 # GET/POST /api/memory
│   │   ├── doctor.py                 # GET /api/doctor
│   │   ├── version.py                # GET /api/version
│   │   ├── whats_new.py              # GET /api/whats-new
│   │   ├── followups.py              # GET /api/followups
│   │   ├── followups_log.py          # POST /api/followups/log
│   │   ├── usage.py                  # GET /api/usage
│   │   ├── report_shape.py           # POST /api/report/shape
│   │   ├── run.py                    # POST /api/run
│   │   ├── assistant.py              # POST /api/assistant
│   │   ├── explore.py                # POST /api/explore
│   │   ├── explore_ai.py             # POST /api/explore/ai
│   │   ├── explore_ai_known.py       # GET /api/explore/ai/known
│   │   ├── explore_add.py            # POST /api/explore/add
│   │   ├── apply_session.py          # POST /api/apply/session
│   │   ├── apply_prefill.py          # POST /api/apply/prefill
│   │   ├── apply_fill.py             # POST /api/apply/fill
│   │   ├── apply_drive.py            # POST /api/apply/drive
│   │   ├── apply_close.py            # POST /api/apply/close
│   │   ├── runs_save.py              # POST /api/runs/save
│   │   ├── clis.py                   # GET /api/clis
│   │   └── logo.py                   # GET /api/logo
│   │
│   ├── services/                     # Business logic
│   │   ├── __init__.py
│   │   ├── tracker_service.py        # Parse/écriture applications.md
│   │   ├── cv_service.py             # Lecture/écriture cv.md
│   │   ├── profile_service.py        # Lecture/écriture profile.yml
│   │   ├── portals_service.py        # Lecture/écriture portals.yml
│   │   ├── pipeline_service.py       # Parse pipeline.md
│   │   ├── report_service.py         # Lecture rapports
│   │   ├── memory_service.py         # Lecture/écriture _profile.md (notes)
│   │   ├── doctor_service.py         # Vérification prérequis
│   │   ├── stats_service.py          # Calcul stats usage
│   │   ├── followup_service.py       # Cadence de relance
│   │   ├── scan_service.py           # Orchestration scan-ats-full.mjs
│   │   ├── runner_service.py         # Orchestration CLI IA (evaluate/pdf)
│   │   ├── assistant_service.py      # Orchestration assistant IA
│   │   ├── explore_service.py        # Découverte IA + dédup
│   │   ├── apply_service.py          # Sessions Playwright
│   │   ├── cli_service.py            # Détection CLIs installés
│   │   └── system_service.py         # Version, changelog
│   │
│   ├── core/                         # Utilitaires fondamentaux
│   │   ├── __init__.py
│   │   ├── paths.py                  # careerOpsRoot(), rootScript()
│   │   ├── safe_write.py             # atomic_write, backup
│   │   ├── states.py                 # Canonical states (lecture states.yml)
│   │   ├── tracker_parse.py          # Header-aware column mapping
│   │   ├── run_registry.py           # In-memory write token registry
│   │   └── ndjson.py                 # Streaming NDJSON helpers
│   │
│   └── models/                       # Pydantic models
│       ├── __init__.py
│       ├── application.py            # Application, InboxJob, etc.
│       ├── pipeline.py               # PipelineSummary
│       ├── report.py                 # ReportData
│       ├── scan.py                   # DiscoveredOffer, ScanEvent
│       ├── states.py                 # CanonicalState
│       └── cli.py                    # CliSpec
│
├── tests/
│   ├── conftest.py                   # Fixtures (tmp CAREER_OPS_ROOT)
│   ├── test_tracker_service.py
│   ├── test_cv_service.py
│   ├── test_states.py
│   ├── test_scan_service.py
│   └── ...
│
└── scripts/
    └── dev.sh                        # lance uvicorn + next dev
```

---

## 5. Phase 1 — Fondations

**Durée estimée :** 2-3 jours

### 5.1 Initialiser le projet Python

```bash
cd backend/
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic pyyaml httpx python-multipart
pip install pytest pytest-asyncio httpx  # dev
```

### 5.2 `pyproject.toml`

```toml
[project]
name = "career-ops-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0",
    "httpx>=0.28.0",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.25.0", "httpx>=0.28.0"]
```

### 5.3 `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    career_ops_root: str = "../"  # relative to backend/
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_prefix = "CAREER_OPS_"
        env_file = ".env"
```

### 5.4 `app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate CAREER_OPS_ROOT exists
    yield
    # Shutdown: cleanup

app = FastAPI(title="career-ops", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)
```

### 5.5 `app/core/paths.py`

Port direct de `career-ops.ts` :

```python
from pathlib import Path
import os

def career_ops_root() -> Path:
    env = os.environ.get("CAREER_OPS_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent

def root_script(name_no_ext: str) -> Path:
    return career_ops_root() / f"{name_no_ext}.mjs"
```

### 5.6 `app/core/safe_write.py`

Port de `safe-write.ts` :

```python
import os
import uuid
from pathlib import Path

def atomic_write(file: Path, content: str) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{file}.tmp-{os.getpid()}-{uuid.uuid4()}"
    tmp_path = Path(tmp)
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(file)

def backup(file: Path) -> Path | None:
    try:
        cur = file.read_text(encoding="utf-8")
        if not cur.strip():
            return None
        ts = __import__("datetime").datetime.now().isoformat().replace(":", "-").replace(".", "-")
        bak = file.with_suffix(f".bak-{ts}")
        bak.write_text(cur, encoding="utf-8")
        return bak
    except FileNotFoundError:
        return None

def atomic_write_with_backup(file: Path, content: str) -> Path | None:
    bak = backup(file)
    atomic_write(file, content)
    return bak
```

---

## 6. Phase 2 — Core data (lectures)

**Durée estimée :** 3-4 jours

### 6.1 `app/core/tracker_parse.py`

Port de `tracker-table.mjs` + `tracker-parse.mjs` — le composant le plus critique :

```python
import re
from dataclasses import dataclass

@dataclass
class Application:
    n: str
    date: str
    company: str
    via: str
    role: str
    score: str
    status: str
    pdf: str
    report: str
    notes: str

def parse_applications(md: str, root: Path) -> list[Application]:
    """Parse data/applications.md — header-aware column mapping."""
    lines = md.split("\n")
    header_idx = {}
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.split("|")]
        if any(c in ("---", ":---:", "---:") for c in cells):
            break  # separator row
        for j, cell in enumerate(cells):
            if cell in ("#", "num", "number"):
                header_idx["n"] = j
            elif cell == "date":
                header_idx["date"] = j
            elif cell == "company":
                header_idx["company"] = j
            # ... etc

    apps = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 8:
            continue
        # Map cells to Application using header_idx
        apps.append(Application(...))
    return apps
```

### 6.2 `app/services/tracker_service.py`

```python
class TrackerService:
    def __init__(self, root: Path):
        self.root = root

    def read_applications(self) -> list[Application]:
        md = (self.root / "data" / "applications.md").read_text(encoding="utf-8")
        return parse_applications(md, self.root)

    def find_application(self, n: str) -> Application | None:
        return next((a for a in self.read_applications() if a.n == n), None)
```

### 6.3 `app/services/pipeline_service.py`

Port de `readInbox()` + `readScanDates()` + `pipelineSummary()` :

```python
@dataclass
class InboxJob:
    url: str
    company: str
    role: str
    location: str | None
    compensation: str | None
    done: bool
    posted_at: str | None

class PipelineService:
    def read_inbox(self) -> list[InboxJob]:
        # Parse data/pipeline.md
        ...

    def read_scan_dates(self) -> dict[str, str]:
        # Parse data/scan-history.tsv
        ...

    def summary(self) -> PipelineSummary:
        ...
```

### 6.4 Routes correspondantes

```python
# app/api/pipeline.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/api/pipeline")
async def get_pipeline(tracker: TrackerService = Depends()):
    return {
        "inbox": [asdict(j) for j in tracker.read_inbox()],
        "applications": [asdict(a) for a in tracker.read_applications()],
        "root": str(tracker.root),
        "rootExists": tracker.root.exists(),
    }
```

---

## 7. Phase 3 — Écritures et intégrité

**Durée estimée :** 2-3 jours

### 7.1 `app/core/states.py`

Port de `states.ts` — lecture de `templates/states.yml` :

```python
import yaml
from dataclasses import dataclass

@dataclass
class CanonicalState:
    id: str
    label: str
    aliases: list[str]
    description: str
    group: str

def read_canonical_states(root: Path) -> list[CanonicalState]:
    states_file = root / "templates" / "states.yml"
    with open(states_file) as f:
        doc = yaml.safe_load(f)
    return [CanonicalState(**s) for s in doc.get("states", [])]

def canonicalize_status(raw: str, states: list[CanonicalState]) -> str | None:
    q = raw.strip().lower().replace("**", "")
    for s in states:
        if q in (s.label.lower(), s.id.lower(), *(a.lower() for a in s.aliases)):
            return s.label
    return None
```

### 7.2 `app/core/run_registry.py`

Port de `run_registry.ts` — in-memory write token :

```python
import asyncio

class RunRegistry:
    def __init__(self):
        self._seq = 0
        self._writing: set[int] = set()
        self._lock = asyncio.Lock()

    async def acquire(self) -> int:
        async with self._lock:
            self._seq += 1
            self._writing.add(self._seq)
            return self._seq

    async def release(self, token: int):
        async with self._lock:
            self._writing.discard(token)

    @property
    def is_writing(self) -> bool:
        return len(self._writing) > 0
```

### 7.3 Routes d'écriture

```python
# app/api/status.py
@router.post("/api/status")
async def set_status(body: StatusRequest, tracker: TrackerService = Depends()):
    canon = canonicalize_status(body.status, read_canonical_states(tracker.root))
    if not canon:
        raise HTTPException(400, f"not a canonical status: {body.status}")
    tracker.update_status(body.n, canon)
    return {"ok": True, "status": canon}
```

---

## 8. Phase 4 — Orchestration CLI

**Durée estimée :** 4-5 jours (le plus complexe)

### 8.1 `app/services/cli_service.py`

Port de `clis.ts` :

```python
import shutil
from dataclasses import dataclass

KNOWN_CLIS = [
    {"id": "claude", "name": "Claude Code", "bin": "claude", "args": lambda p: ["-p", p]},
    {"id": "codex", "name": "Codex", "bin": "codex", "args": lambda p: ["exec", p]},
    {"id": "opencode", "name": "OpenCode", "bin": "opencode", "args": lambda p: ["run", p]},
    # ...
]

def resolve_cli(cli_id: str) -> dict | None:
    spec = next((c for c in KNOWN_CLIS if c["id"] == cli_id), None)
    if not spec:
        return None
    bin_path = shutil.which(spec["bin"])
    if not bin_path:
        return None
    return {"spec": spec, "bin_path": bin_path}
```

### 8.2 `app/services/runner_service.py`

Port de `/api/run` — le plus complexe (streaming NDJSON) :

```python
import asyncio
from fastapi.responses import StreamingResponse

class RunnerService:
    async def evaluate(self, url: str, cli_id: str):
        """Stream evaluation as NDJSON events."""
        resolved = resolve_cli(cli_id)
        if not resolved:
            raise ValueError(f"CLI '{cli_id}' not found")

        prompt = self._build_prompt("evaluate", url)
        args = resolved["spec"]["args"](prompt)

        async def stream():
            proc = await asyncio.create_subprocess_exec(
                resolved["bin_path"], *args,
                cwd=str(self.root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Parse stdout line by line, emit NDJSON events
            async for line in proc.stdout:
                # Parse Claude stream-json format or raw text
                yield json.dumps({"type": "text", "text": line.decode()}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"

        return StreamingResponse(stream(), media_type="text/plain")
```

### 8.3 `app/api/run.py`

```python
@router.post("/api/run")
async def run_worker(body: RunRequest, runner: RunnerService = Depends()):
    if body.kind == "evaluate":
        return await runner.evaluate(body.input, body.cli_id)
    elif body.kind == "pdf":
        return await runner.generate_pdf(body.input, body.cli_id)
    elif body.kind == "research":
        return await runner.research(body.input, body.cli_id)
```

### 8.4 `app/api/assistant.py`

```python
@router.post("/api/assistant")
async def assistant_chat(body: AssistantRequest, runner: RunnerService = Depends()):
    return await runner.assistant(body.message, body.cli_id, body.history, body.page_context)
```

---

## 9. Phase 5 — Streaming et temps réel

**Durée estimée :** 2-3 jours

### 9.1 `app/core/ndjson.py`

Helper pour streaming NDJSON (FastAPI SSE) :

```python
import json
from typing import AsyncGenerator

async def ndjson_stream(generator: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    async for event in generator:
        yield json.dumps(event) + "\n"
```

### 9.2 Patterns de streaming

Le frontend attend du NDJSON (newline-delimited JSON). Chaque event a un `type` :

| type | Payload | Usage |
|------|---------|-------|
| `text` | `{text: string}` | Texte de l'assistant |
| `tool` | `{name: string}` | Outil utilisé par le CLI |
| `status` | `{label: string}` | Status update |
| `error` | `{msg: string}` | Erreur |
| `done` | `{tokens: number, costUsd: number}` | Terminé |
| `offer` | `{DiscoveredOffer}` | Offre découverte (scan) |
| `progress` | `{ats, scanned, total, matches}` | Progression scan |

### 9.3 Streaming scan (explore)

```python
@router.post("/api/explore")
async def explore(body: ExploreRequest, scan: ScanService = Depends()):
    async def stream():
        async for event in scan.discover(body.filters):
            yield json.dumps(asdict(event)) + "\n"
    return StreamingResponse(stream(), media_type="application/x-ndjson")
```

---

## 10. Phase 6 — Adaptation du frontend

**Durée estimée :** 1-2 jours

### 10.1 Changer l'URL de base

Dans `web/src/lib/career-ops.ts` ou `web/next.config.ts` :

```typescript
// Option A : proxy Next.js → FastAPI
// next.config.ts
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' }
    ];
  }
};
```

```typescript
// Option B : variable d'environnement
// web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 10.2 Adapter les appels fetch

Si on garde le proxy (Option A), **aucun changement** dans le frontend. Les routes sont identiques.

Si on utilise l'URL directe (Option B), créer un wrapper :

```typescript
// web/src/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_URL || '';

export async function apiFetch(path: string, init?: RequestInit) {
  return fetch(`${BASE}${path}`, init);
}
```

### 10.3 Le bridge carrière-ops.ts disparaît

Les modules `web/src/lib/career-ops.ts`, `web/src/lib/clis.ts`, `web/src/lib/core/*.ts` ne sont plus nécessaires côté serveur Next.js. Le frontend devient un **pur client** qui appelle FastAPI.

**Simplification majeure :** Next.js n'est plus un serveur — il sert uniquement le bundle React statique.

---

## 11. Phase 7 — Tests et validation

**Durée estimée :** 2-3 jours

### 11.1 Tests unitaires

```python
# tests/test_tracker_service.py
def test_parse_applications(applications_md):
    apps = parse_applications(applications_md, fake_root)
    assert len(apps) == 3
    assert apps[0].n == "001"
    assert apps[0].status == "Evaluated"

def test_canonicalize_status():
    assert canonicalize_status("evaluada", states) == "Evaluated"
    assert canonicalize_status("UNKNOWN", states) is None

def test_atomic_write(tmp_path):
    f = tmp_path / "test.md"
    atomic_write(f, "content")
    assert f.read_text() == "content"
```

### 11.2 Tests d'intégration

```python
# tests/test_api.py
from httpx import AsyncClient

async def test_pipeline_endpoint(client, fake_root):
    response = await client.get("/api/pipeline")
    assert response.status_code == 200
    assert "inbox" in response.json()
    assert "applications" in response.json()

async def test_cv_roundtrip(client, fake_root):
    await client.post("/api/cv", json={"content": "# My CV"})
    response = await client.get("/api/cv")
    assert response.json()["content"] == "# My CV"
```

### 11.3 Tests de compatibilité

Vérifier que chaque réponse FastAPI a **exactement** le même format que la réponse Next.js correspondante :

```python
# tests/test_compat.py — comparaison avec les réponses Node.js
async def test_pipeline_compat(client, fake_root):
    fastapi_resp = (await client.get("/api/pipeline")).json()
    # Comparer structure avec la sortie attendue de pipelineSummary()
    assert set(fastapi_resp.keys()) == {"inbox", "applications", "root", "rootExists"}
```

### 11.4 Tests end-to-end

```bash
# Terminal 1 : FastAPI
cd backend && uvicorn app.main:app --reload

# Terminal 2 : Next.js
cd web && npm run dev

# Terminal 3 : Tests E2E
curl http://localhost:3000/api/pipeline  # via proxy → FastAPI
```

---

## 12. Phase 8 — Déploiement

**Durée estimée :** 1 jour

### 12.1 `scripts/dev.sh`

```bash
#!/bin/bash
# Lance les deux serveurs en parallèle
cd backend && uvicorn app.main:app --reload --port 8000 &
cd web && npm run dev &
wait
```

### 12.2 `docker-compose.yml` (optionnel)

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["..:/app"]
    environment:
      - CAREER_OPS_ROOT=/app

  frontend:
    build: ./web
    ports: ["3000:3000"]
    depends_on: [backend]
```

### 12.3 Procfile (Railway, Render, etc.)

```
backend: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
frontend: cd web && npm run build && npm start
```

---

## 13. Matrice de couverture

| Route | Phase | Priorité | Complexité | Notes |
|-------|-------|----------|------------|-------|
| `GET /api/pipeline` | 2 | P0 | Faible | Lit fichiers, pas de subprocess |
| `GET/POST /api/cv` | 2 | P0 | Faible | Read/Write cv.md |
| `GET /api/doctor` | 2 | P0 | Faible | File exists checks |
| `GET /api/version` | 2 | P0 | Très faible | Lit un fichier |
| `GET /api/portals` | 2 | P0 | Faible | Lit YAML |
| `POST /api/status` | 3 | P0 | Moyenne | Écriture atomique tracker |
| `GET/POST /api/memory` | 3 | P1 | Moyenne | managed block dans _profile.md |
| `GET/POST /api/profile` | 2 | P0 | Faible | Read/Write YAML |
| `GET /api/followups` | 4 | P1 | Moyenne | subprocess → followup-cadence.mjs |
| `POST /api/tracker/delete` | 3 | P1 | Moyenne | subprocess → tracker.mjs delete |
| `POST /api/explore` | 4 | P1 | Élevée | subprocess + streaming NDJSON |
| `POST /api/explore/ai` | 4 | P1 | Élevée | subprocess CLI IA + streaming |
| `POST /api/run` | 4 | P0 | Très élevée | subprocess CLI IA + NDJSON + auth gates |
| `POST /api/assistant` | 4 | P0 | Très élevée | subprocess CLI IA + NDJSON + actions |
| `POST /api/apply/*` | 4 | P2 | Très élevée | Playwright headless sessions |
| `GET /api/clis` | 2 | P1 | Faible | shutil.which() |
| `POST /api/report/shape` | 2 | P1 | Faible | Lit un fichier .md |
| `POST /api/cv/ingest` | 2 | P2 | Moyenne | Parse CV uploadé |
| `GET /api/cv-pdf` | 4 | P2 | Moyenne | Template + render |
| `POST /api/usage` | 2 | P2 | Faible | Calcul stats |
| `POST /api/explore/add` | 3 | P1 | Faible | Append à pipeline.md |
| `GET /api/explore/ai/known` | 2 | P1 | Faible | Assemble dedup context |
| `POST /api/followups/log` | 3 | P2 | Faible | Append à follow-ups.md |
| `POST /api/runs/save` | 2 | P2 | Faible | Write log file |
| `GET /api/whats-new` | 2 | P2 | Très faible | Lit changelog |
| `GET /api/logo` | 2 | P2 | Très faible | Static file |

---

## 14. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **Streaming NDJSON** — le frontend parse du NDJSON en temps réel | Élevé | FastAPI `StreamingResponse` avec `async generator` — même format |
| **child_process async** — les scripts .mjs sont synchrones | Moyen | `asyncio.create_subprocess_exec` avec timeout |
| **File locking** — concurrence écritures tracker | Élevé | `RunRegistry` async + file lock (fcntl/flock) |
| **Playwright Python** — les sessions apply utilisent Playwright Node | Moyen | Utiliser `playwright` package Python (API similaire) |
| **Claude CLI parsing** — parsing du stream-json de Claude | Élevé | Même logique de parsing, adaptée en Python |
| **Windows compat** — paths, process spawning | Faible | `pathlib.Path` partout, pas de shell=True |
| **Data Contract** — risque de casser la séparation système/utilisateur | Élevé | Tests qui vérifient que les writes vont aux bons fichiers |
| **Performance** — Python vs Node.js pour le file I/O | Faible | Le bottleneck est le CLI IA, pas le file I/O |

---

## 15. Estimation temporelle

| Phase | Jours | Dépend de |
|-------|-------|-----------|
| Phase 1 — Fondations | 2-3 | Rien |
| Phase 2 — Core data (lectures) | 3-4 | Phase 1 |
| Phase 3 — Écritures et intégrité | 2-3 | Phase 2 |
| Phase 4 — Orchestration CLI | 4-5 | Phase 3 |
| Phase 5 — Streaming et temps réel | 2-3 | Phase 4 |
| Phase 6 — Frontend adaptation | 1-2 | Phase 5 |
| Phase 7 — Tests et validation | 2-3 | Phase 6 |
| Phase 8 — Déploiement | 1 | Phase 7 |
| **Total** | **17-24 jours** | — |

### Ordre de recommandation

```
Semaine 1 : Phase 1 + 2 (fondations + lectures) → le backend lit les mêmes données
Semaine 2 : Phase 3 + 4 (écritures + orchestration) → le backend écrit + spawne des CLIs
Semaine 3 : Phase 5 + 6 (streaming + frontend) → le frontend pointe vers FastAPI
Semaine 4 : Phase 7 + 8 (tests + déploiement) → validé et prêt
```

---

## Annexe A : Démarrage rapide

```bash
# 1. Cloner le projet
git clone https://github.com/santifer/career-ops.git
cd career-ops

# 2. Installer les dépendances Node (pour les scripts .mjs)
npm install

# 3. Créer le backend
mkdir backend && cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn pydantic pyyaml httpx python-multipart

# 4. Créer app/main.py (hello world)
cat > app/main.py << 'EOF'
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/health")
async def health(): return {"status": "ok"}
EOF

# 5. Lancer
uvicorn app.main:app --reload --port 8000

# 6. Tester
curl http://localhost:8000/api/health
```

---

*Document généré le 14 juillet 2026. Pour l'analyse complète du projet, voir [analyse-projet.md](analyse-projet.md). Pour le guide de démarrage, voir [GETTING-STARTED.md](../../GETTING-STARTED.md).*
