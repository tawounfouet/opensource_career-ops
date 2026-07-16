#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.python.plugins.engine import HOOK_KINDS, RESERVED_ENV


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def registry_dir_path(root: str | Path) -> Path:
    return Path(root) / "plugins-registry"


def load_registry_files(root: str | Path) -> list[dict[str, Any]]:
    directory = registry_dir_path(root)
    if not directory.exists():
        return []
    output = []
    for path in sorted(directory.glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            entry = None
        output.append({"file": path.name, "entry": entry})
    return output


def load_registry(root: str | Path) -> dict[str, Any]:
    directory = registry_dir_path(root)
    if directory.exists():
        return {"registryVersion": 1, "plugins": [item["entry"] for item in load_registry_files(root) if isinstance(item["entry"], dict)]}
    legacy = Path(root) / "plugins-registry.json"
    if not legacy.exists():
        return {"registryVersion": 1, "plugins": []}
    try:
        parsed = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return {"registryVersion": 1, "plugins": []}
    return parsed if isinstance(parsed, dict) and isinstance(parsed.get("plugins"), list) else {"registryVersion": 1, "plugins": []}


def validate_registry_entry(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry.get("name"), str) or not entry["name"].startswith("career-ops-plugin-"):
        errors.append('name must start with "career-ops-plugin-"')
    if not isinstance(entry.get("id"), str) or not ID_RE.match(entry["id"]):
        errors.append("invalid id")
    if entry.get("name") and entry.get("id") and entry["name"] != f"career-ops-plugin-{entry['id']}":
        errors.append("name must equal career-ops-plugin-<id>")
    if not re.match(r"^https://github\.com/[^/]+/[^/]+$", str(entry.get("repo") or "")):
        errors.append("repo must be a https://github.com/<owner>/<repo> URL")
    if not re.match(r"^[0-9a-f]{40}$", str(entry.get("sha") or "")):
        errors.append("sha must be a 40-hex commit")
    hooks = entry.get("hooks")
    if not isinstance(hooks, list) or not hooks or any(hook not in HOOK_KINDS for hook in hooks):
        errors.append("hooks must be a non-empty subset of the hook kinds")
    required = entry.get("requiredEnv")
    if not isinstance(required, list):
        errors.append("requiredEnv must be an array")
    elif any(name in RESERVED_ENV or str(name).startswith("AWS_") for name in required):
        errors.append("requiredEnv declares a reserved/core-owned var")
    allowed = entry.get("allowedHosts")
    if not isinstance(allowed, list):
        errors.append("allowedHosts must be an array")
    elif isinstance(required, list) and required and not allowed:
        errors.append("a keyed plugin must declare allowedHosts")
    if not isinstance(entry.get("license"), str) or not entry.get("license"):
        errors.append("license is required")
    if not isinstance(entry.get("version"), str):
        errors.append("version is required")
    if "supersedesBundled" in entry and entry["supersedesBundled"] is not True:
        errors.append("supersedesBundled, if present, must be the boolean true")
    return errors


def validate_registry(root: str | Path) -> list[str]:
    registry = load_registry(root)
    problems: list[str] = []
    if registry.get("registryVersion") != 1:
        problems.append(f"unsupported registryVersion {json.dumps(registry.get('registryVersion'))}")
    for item in load_registry_files(root):
        file = item["file"]
        entry = item["entry"]
        if not isinstance(entry, dict):
            problems.append(f"{file}: not a JSON object")
            continue
        if entry.get("id") and f"{entry['id']}.json" != file:
            problems.append(f"{file}: filename must equal \"<id>.json\" (id is \"{entry['id']}\")")
    names: set[str] = set()
    ids: set[str] = set()
    for entry in registry["plugins"]:
        label = entry.get("name") or entry.get("id") or "?"
        for error in validate_registry_entry(entry):
            problems.append(f"{label}: {error}")
        if entry.get("name") in names:
            problems.append(f"duplicate name: {entry['name']}")
        if entry.get("id") in ids:
            problems.append(f"duplicate id: {entry['id']}")
        if entry.get("supersedesBundled") is True and entry.get("id") and not (Path(root) / "plugins" / entry["id"] / "manifest.json").exists():
            problems.append(f"{label}: supersedesBundled names \"{entry['id']}\" but no bundled plugin (plugins/{entry['id']}/) exists to supersede")
        names.add(entry.get("name"))
        ids.add(entry.get("id"))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate plugin registry shape.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    problems = validate_registry(args.root)
    if args.json:
        print(json.dumps({"problems": problems}, indent=2))
    elif problems:
        for problem in problems:
            print(problem)
    else:
        print("plugin registry is valid")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
