#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from scripts.python import CONFIG_DIR, TEMPLATES_DIR


DEFAULT_PROFILE_PATH = Path(os.environ.get("CAREER_OPS_PROFILE", CONFIG_DIR / "profile.yml"))
VALID_FORMATS = {"html", "tex"}
KINDS = {
    "cv": {
        "prefix": "cv-template",
        "profile_key": ["cv", "template"],
        "required": ["NAME", "EXPERIENCE", "EDUCATION"],
    },
    "cover": {
        "prefix": "cover-letter-template",
        "profile_key": ["cover_letter", "template"],
        "required": ["NAME", "ROLE_TITLE", "OPENING"],
    },
}


def prettify(name: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in name.split("-") if word)


def kebab(display: Any) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", str(display).strip().lower()))


def assert_format(format: str) -> None:
    if format not in VALID_FORMATS:
        raise ValueError(f"Unsupported template format: {format} (expected html or tex)")


def parse_filename(prefix: str, file_name: str) -> dict[str, str] | None:
    match = re.match(rf"^{re.escape(prefix)}(?:\.([a-z0-9-]+))?\.(html|tex)$", file_name)
    if not match:
        return None
    return {"name": match.group(1) or "standard", "format": match.group(2)}


def parse_meta(path: str | Path) -> dict[str, str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception:
        return {}
    block = re.search(r"<!--\s*career-ops-template\s*([\s\S]*?)-->", text)
    if not block:
        return {}
    meta: dict[str, str] = {}
    for line in block.group(1).splitlines():
        match = re.match(r"\s*([a-zA-Z_]+)\s*:\s*(.+?)\s*$", line)
        if match:
            meta[match.group(1).lower()] = match.group(2)
    return meta


def list_templates(kind: str, *, directory: str | Path = TEMPLATES_DIR, format: str = "html") -> list[dict[str, Any]]:
    cfg = KINDS.get(kind)
    if not cfg:
        raise ValueError(f"Unknown template kind: {kind}")
    assert_format(format)
    root = Path(directory)
    if not root.exists():
        return []
    output: list[dict[str, Any]] = []
    for path in root.iterdir():
        parsed = parse_filename(cfg["prefix"], path.name)
        if not parsed or parsed["format"] != format:
            continue
        meta = parse_meta(path)
        output.append(
            {
                "name": parsed["name"],
                "displayName": meta.get("name") or prettify(parsed["name"]),
                "path": str(path.resolve(strict=False)),
                "format": parsed["format"],
                "meta": meta,
            }
        )
    return sorted(output, key=lambda item: item["name"])


def validate_template(path: str | Path, kind: str) -> dict[str, Any]:
    cfg = KINDS.get(kind)
    if not cfg:
        raise ValueError(f"Unknown template kind: {kind}")
    text = Path(path).read_text(encoding="utf-8")
    missing = [placeholder for placeholder in cfg["required"] if f"{{{{{placeholder}}}}}" not in text]
    return {"ok": not missing, "missing": missing}


def load_profile_default(kind: str, *, profile_path: str | Path = DEFAULT_PROFILE_PATH) -> str | None:
    cfg = KINDS.get(kind)
    if not cfg:
        raise ValueError(f"Unknown template kind: {kind}")
    path = Path(profile_path)
    if not path.exists():
        return None
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    node: Any = doc
    for key in cfg["profile_key"]:
        node = node.get(key) if isinstance(node, dict) else None
    return node.strip() if isinstance(node, str) and node.strip() else None


def resolve_template(
    kind: str,
    name: str | None = None,
    *,
    directory: str | Path = TEMPLATES_DIR,
    format: str = "html",
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
    fallback: bool = False,
) -> Path:
    cfg = KINDS.get(kind)
    if not cfg:
        raise ValueError(f"Unknown template kind: {kind}")
    assert_format(format)
    explicit = bool(str(name or "").strip())
    chosen = kebab(name if explicit else load_profile_default(kind, profile_path=profile_path) or "standard")

    def file_for(template_name: str) -> str:
        return f"{cfg['prefix']}.{format}" if template_name == "standard" else f"{cfg['prefix']}.{template_name}.{format}"

    path = Path(directory) / file_for(chosen)
    if not path.exists():
        if fallback and chosen != "standard":
            chosen = "standard"
            path = Path(directory) / file_for(chosen)
        if not path.exists():
            raise FileNotFoundError(f"Template not found for kind={kind} name={chosen} ({file_for(chosen)})")
    if format == "html":
        validation = validate_template(path, kind)
        if not validation["ok"]:
            placeholders = ", ".join(f"{{{{{item}}}}}" for item in validation["missing"])
            raise ValueError(f"Template {file_for(chosen)} missing required placeholders: {placeholders}")
    return path.resolve(strict=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover and resolve CV templates.")
    sub = parser.add_subparsers(dest="command")
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("kind", choices=sorted(KINDS))
    list_cmd.add_argument("--format", default="html")
    resolve_cmd = sub.add_parser("resolve")
    resolve_cmd.add_argument("kind", choices=sorted(KINDS))
    resolve_cmd.add_argument("name", nargs="?")
    resolve_cmd.add_argument("--format", default="html")
    resolve_cmd.add_argument("--fallback", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "list":
        print(json.dumps([{"name": item["name"], "displayName": item["displayName"]} for item in list_templates(args.kind, format=args.format)], indent=2))
        return 0
    if args.command == "resolve":
        print(resolve_template(args.kind, args.name, format=args.format, fallback=args.fallback))
        return 0
    parser.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
