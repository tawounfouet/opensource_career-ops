from __future__ import annotations

import json
from dataclasses import dataclass

from .paths import root_path


LEGACY_COLMAP = {
    "num": 1,
    "date": 2,
    "company": 3,
    "role": 4,
    "score": 5,
    "status": 6,
    "pdf": 7,
    "report": 8,
    "notes": 9,
}


def header_aliases() -> dict[str, str]:
    try:
        return json.loads(root_path("tracker-aliases.json").read_text(encoding="utf-8"))
    except Exception:
        return {"#": "num", "date": "date", "company": "company", "role": "role", "score": "score", "status": "status", "pdf": "pdf", "report": "report", "notes": "notes"}


def resolve_columns(lines: list[str]) -> dict[str, int]:
    aliases = header_aliases()
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.split("|")]
        if "company" not in cells or "role" not in cells:
            continue
        colmap = {}
        for i, cell in enumerate(cells):
            if cell in aliases:
                colmap[aliases[cell]] = i
        if all(k in colmap for k in ["num", "company", "role", "score", "status"]):
            return colmap
    return dict(LEGACY_COLMAP)


@dataclass
class TrackerRow:
    num: int
    date: str
    company: str
    role: str
    score: str
    status: str
    pdf: str
    report: str
    notes: str
    raw: str
    via: str = ""
    location: str = ""


def parse_tracker_row(line: str, colmap: dict[str, int]) -> TrackerRow | None:
    if not line.startswith("|"):
        return None
    parts = [p.strip() for p in line.split("|")]
    try:
        num = int(parts[colmap["num"]])
    except Exception:
        return None

    def at(key: str) -> str:
        idx = colmap.get(key)
        return parts[idx] if idx is not None and idx < len(parts) else ""

    return TrackerRow(
        num=num,
        date=at("date"),
        company=at("company"),
        role=at("role"),
        score=at("score"),
        status=at("status"),
        pdf=at("pdf"),
        report=at("report"),
        notes=at("notes"),
        via=at("via"),
        location=at("location"),
        raw=line,
    )


def parse_applications(markdown: str) -> list[TrackerRow]:
    lines = markdown.splitlines()
    colmap = resolve_columns(lines)
    rows = []
    for line in lines:
        row = parse_tracker_row(line, colmap)
        if row:
            rows.append(row)
    return rows
