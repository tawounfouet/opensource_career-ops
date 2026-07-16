#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scripts.python.plugins.audit import audit_plugin
from scripts.python.plugins.engine import validate_manifest


GITHUB_URL_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(?:\.git)?$")
NAME_RE = re.compile(r"^career-ops-plugin-([a-z0-9][a-z0-9-]*)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MIN_FILES = ["manifest.json", "index.mjs", "README.md", "LICENSE"]


def parse_repo_arg(arg: str) -> dict[str, str]:
    url = arg
    if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", arg):
        url = f"https://github.com/{arg}"
    url = re.sub(r"\.git$", "", url)
    if not GITHUB_URL_RE.match(url):
        raise ValueError(
            f"refusing non-GitHub/unsafe repo URL: {arg} "
            "(expected https://github.com/<owner>/<repo>)"
        )
    repo_name = url.rsplit("/", 1)[-1]
    match = NAME_RE.match(repo_name)
    if not match:
        raise ValueError(f'repo must be named "career-ops-plugin-<name>" (got "{repo_name}")')
    return {"url": url, "id": match.group(1)}


def safe_clone(url: str, sha: str) -> Path:
    if not SHA_RE.match(sha or ""):
        raise ValueError(f"a 40-hex commit --sha is required (got {sha!r})")
    directory = Path(tempfile.mkdtemp(prefix="co-plugin-"))
    git_base = ["git", "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never"]
    try:
        subprocess.run([*git_base, "-C", str(directory), "init", "-q"], check=True, capture_output=True, text=True, timeout=120)
        subprocess.run([*git_base, "-C", str(directory), "remote", "add", "origin", "--", url], check=True, capture_output=True, text=True, timeout=120)
        subprocess.run([*git_base, "-C", str(directory), "fetch", "--depth", "1", "--no-tags", "-q", "origin", sha], check=True, capture_output=True, text=True, timeout=120)
        subprocess.run([*git_base, "-C", str(directory), "checkout", "-q", "FETCH_HEAD"], check=True, capture_output=True, text=True, timeout=120)
        shutil.rmtree(directory / ".git", ignore_errors=True)
        return directory
    except subprocess.CalledProcessError as error:
        shutil.rmtree(directory, ignore_errors=True)
        detail = (error.stderr or error.stdout or str(error))[:200]
        raise RuntimeError(f"clone of {url}@{sha[:10]} failed — {detail}") from error


def validate_install(directory: str | Path, expect_id: str) -> dict[str, Any]:
    plugin_dir = Path(directory)
    problems = [f"missing required file: {name}" for name in MIN_FILES if not (plugin_dir / name).exists()]
    if problems:
        return {"ok": False, "problems": problems, "manifest": None, "dir": str(plugin_dir)}
    try:
        parsed = json.loads((plugin_dir / "manifest.json").read_text(encoding="utf-8"))
    except Exception as error:
        return {
            "ok": False,
            "problems": [f"manifest.json invalid JSON: {error}"],
            "manifest": None,
            "dir": str(plugin_dir),
        }
    manifest = validate_manifest(parsed, plugin_dir, expect_id)
    if not manifest:
        return {
            "ok": False,
            "problems": ["manifest failed validation"],
            "manifest": None,
            "dir": str(plugin_dir),
        }
    audit = audit_plugin(plugin_dir)
    if not audit["ok"]:
        return {
            "ok": False,
            "problems": [f"{finding['file']}: {finding['issue']}" for finding in audit["findings"]],
            "manifest": manifest,
            "dir": str(plugin_dir),
        }
    return {"ok": True, "problems": [], "manifest": manifest, "dir": str(plugin_dir)}


def hash_plugin_tree(directory: str | Path) -> dict[str, Any]:
    import hashlib

    root = Path(directory)
    files: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        if path.is_symlink():
            raise ValueError(f"refusing to hash symlink: {path.relative_to(root).as_posix()}")
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[rel] = f"sha256-{digest}"
    aggregate = "\n".join(f"{name}:{files[name]}" for name in sorted(files))
    integrity = "sha256-" + hashlib.sha256(aggregate.encode("utf-8")).hexdigest()
    return {"files": files, "integrity": integrity}


def install_from_repo(root: str | Path, url: str, sha: str) -> dict[str, Any]:
    parsed = parse_repo_arg(url)
    project = Path(root)
    destination = project / "plugins.local" / parsed["id"]
    if destination.exists():
        raise FileExistsError(f"plugins.local/{parsed['id']} already exists")
    cloned = safe_clone(parsed["url"], sha)
    try:
        result = validate_install(cloned, parsed["id"])
        if not result["ok"]:
            raise ValueError("plugin rejected:\n  - " + "\n  - ".join(result["problems"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(result["dir"], destination)
        tree = hash_plugin_tree(destination)
        return {
            "id": parsed["id"],
            "manifest": {**result["manifest"], "dir": str(destination)},
            "integrity": tree["integrity"],
            "files": tree["files"],
            "repo": parsed["url"],
            "sha": sha,
        }
    finally:
        shutil.rmtree(cloned, ignore_errors=True)


def audit_registry_entry(url: str, sha: str, expect_id: str | None = None) -> list[str]:
    try:
        parsed = parse_repo_arg(url)
    except ValueError as error:
        return [str(error)]
    if expect_id and parsed["id"] != expect_id:
        return [f'repo "{url}" → id "{parsed["id"]}" but registry id is "{expect_id}"']
    try:
        directory = safe_clone(parsed["url"], sha)
    except Exception as error:
        return [str(error)]
    try:
        result = validate_install(directory, parsed["id"])
        return [] if result["ok"] else list(result["problems"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def scaffold_new(root: str | Path, name: str) -> Path:
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        raise ValueError(f'plugin name must match [a-z0-9-] (got "{name}")')
    project = Path(root)
    template = project / "plugins" / "_template"
    if not template.exists():
        raise FileNotFoundError("plugins/_template/ not found")
    destination = project / "plugins.local" / name
    if destination.exists():
        raise FileExistsError(f"plugins.local/{name} already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, destination)
    for path in [item for item in destination.rglob("*") if item.is_file()]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        path.write_text(text.replace("{{NAME}}", name), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or scaffold career-ops plugins.")
    sub = parser.add_subparsers(dest="command")
    parse_cmd = sub.add_parser("parse-repo")
    parse_cmd.add_argument("repo")
    scaffold_cmd = sub.add_parser("new")
    scaffold_cmd.add_argument("name")
    scaffold_cmd.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    if args.command == "parse-repo":
        print(json.dumps(parse_repo_arg(args.repo), indent=2))
        return 0
    if args.command == "new":
        print(scaffold_new(args.root, args.name))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
