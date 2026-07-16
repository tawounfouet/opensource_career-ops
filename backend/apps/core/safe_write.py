from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{uuid4().hex}")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def backup(path: Path) -> Path | None:
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    if not current.strip():
        return None
    ts = datetime.now(timezone.utc).isoformat().replace(":", "-").replace(".", "-")
    bak = path.with_name(f"{path.name}.bak-{ts}")
    bak.write_text(current, encoding="utf-8")
    return bak


def atomic_write_with_backup(path: Path, content: str) -> Path | None:
    bak = backup(path)
    atomic_write(path, content)
    return bak
