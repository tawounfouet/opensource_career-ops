#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from scripts.python import PROJECT_ROOT
from scripts.python.plugins.engine import HOOK_KINDS, RUNNABLE_HOOKS, discover_plugins, load_plugins, plugin_roots, plugin_status, run_hook, load_dotenv
from scripts.python.plugins.install import hash_plugin_tree, install_from_repo, parse_repo_arg, safe_clone, validate_install, scaffold_new
from scripts.python.plugins.validate_registry import load_registry, load_registry_files


APPLICATIONS_PATH = PROJECT_ROOT / "data" / "applications.md"
PIPELINE_PATH = PROJECT_ROOT / "data" / "pipeline.md"


def sanitize_job(job: Any) -> dict[str, Any] | None:
    if not isinstance(job, dict):
        return None
    title = job.get("title").strip() if isinstance(job.get("title"), str) else ""
    url = job.get("url").strip() if isinstance(job.get("url"), str) else ""
    parsed = urlparse(url)
    if not title or parsed.scheme not in {"http", "https"}:
        return None
    output: dict[str, Any] = {"title": title, "url": url}
    for key in ("company", "location"):
        if isinstance(job.get(key), str):
            output[key] = job[key].strip()
    if "salary" in job:
        output["salary"] = job["salary"]
    return output


def parse_markdown_table(markdown: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    headers = [item.strip().lower() for item in lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if all(char in "| :-" for char in line):
            continue
        cells = [item.strip() for item in line.split("|")[1:-1]]
        if not cells:
            continue
        rows.append({header: cells[index] if index < len(cells) else "" for index, header in enumerate(headers)})
    return rows


def existing_pipeline_urls(path: str | Path = PIPELINE_PATH) -> set[str]:
    import re

    file = Path(path)
    if not file.exists():
        return set()
    return {match.group(1) for match in re.finditer(r"- \[[ xX]\]\s+(\S+)", file.read_text(encoding="utf-8"))}


def build_snapshot(root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    project = Path(root)
    applications = project / "data" / "applications.md"
    pipeline = project / "data" / "pipeline.md"
    return {
        "applications": parse_markdown_table(applications.read_text(encoding="utf-8")) if applications.exists() else [],
        "pipeline": parse_markdown_table(pipeline.read_text(encoding="utf-8")) if pipeline.exists() else [],
    }


def load_plugin_config(root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    file = Path(root) / "config" / "plugins.yml"
    if not file.exists():
        return {}
    try:
        parsed = yaml.safe_load(file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def set_enabled(root: str | Path, plugin_id: str, enabled: bool, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    project = Path(root)
    file = project / "config" / "plugins.yml"
    cfg = load_plugin_config(project)
    plugins = cfg.get("plugins") if isinstance(cfg.get("plugins"), dict) else {}
    previous = plugins.get(plugin_id) if isinstance(plugins.get(plugin_id), dict) else {}
    plugins[plugin_id] = {**previous, **(settings or {}), "enabled": enabled}
    cfg["plugins"] = plugins
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        "# career-ops plugin activation — see config/plugins.example.yml\n"
        + yaml.safe_dump(cfg, sort_keys=True),
        encoding="utf-8",
    )
    return cfg


def read_lock(root: str | Path) -> dict[str, Any]:
    file = Path(root) / "plugins.lock"
    if not file.exists():
        return {"lockfileVersion": 1, "plugins": {}}
    try:
        parsed = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return {"lockfileVersion": 1, "plugins": {}}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("plugins"), dict):
        return {"lockfileVersion": 1, "plugins": {}}
    return parsed


def write_lock_entry(root: str | Path, plugin_id: str, entry: dict[str, Any]) -> None:
    project = Path(root)
    lock = read_lock(project)
    lock["lockfileVersion"] = 1
    lock.setdefault("plugins", {})[plugin_id] = entry
    (project / "plugins.lock").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def remove_lock_entry(root: str | Path, plugin_id: str) -> None:
    project = Path(root)
    lock = read_lock(project)
    if plugin_id in lock.get("plugins", {}):
        del lock["plugins"][plugin_id]
        (project / "plugins.lock").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def consent_surface(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "hooks": list(manifest.get("hooks", [])),
        "requiredEnv": list(manifest.get("requiredEnv", [])),
        "allowedHosts": list(manifest.get("allowedHosts", [])),
        "skill": bool(manifest.get("skill")),
        "allowsLocalhost": manifest.get("allowsLocalhost") is True,
    }


def classify_source(manifest: dict[str, Any], root: str | Path, lock_entry: dict[str, Any] | None = None) -> str:
    project = Path(root).resolve()
    directory = Path(manifest["dir"]).resolve()
    try:
        directory.relative_to(project / "plugins")
        return "bundled"
    except ValueError:
        pass
    registry_entry = next((item for item in load_registry(project)["plugins"] if item.get("id") == manifest["id"]), None)
    if not registry_entry:
        return "unverified"
    if lock_entry and lock_entry.get("sha") and registry_entry.get("sha") and lock_entry["sha"] != registry_entry["sha"]:
        return "off-registry"
    return "approved"


def source_badge(source: str) -> str:
    return {
        "bundled": "bundled",
        "approved": "approved",
        "off-registry": "off-registry",
        "unverified": "community-unverified",
    }.get(source, source)


def capability_card(manifest: dict[str, Any], source: str) -> str:
    return "\n".join(
        [
            f"  Plugin:        {manifest['id']}  ({source_badge(source)})",
            f"  Does:          {manifest['description']}",
            f"  Hooks:         {', '.join(manifest['hooks'])}",
            "  Reads keys:    "
            + (", ".join(manifest.get("requiredEnv", [])) + "  (you provide these in .env)" if manifest.get("requiredEnv") else "none"),
            "  Network:       "
            + (
                ", ".join(manifest.get("allowedHosts", []))
                if manifest.get("allowedHosts")
                else "(none declared)"
            )
            + ("  + localhost" if manifest.get("allowsLocalhost") is True else ""),
            "  Ships a skill: "
            + ("yes" if manifest.get("skill") else "no"),
        ]
    )


def find_manifest(root: str | Path, plugin_id: str) -> dict[str, Any] | None:
    manifests = discover_plugins(plugin_roots(root))
    return next((manifest for manifest in manifests if manifest["id"] == plugin_id), None)


def load_skill(manifest: dict[str, Any]) -> dict[str, Any] | None:
    skill = manifest.get("skill")
    if not skill:
        return None
    path = Path(manifest["dir"]) / skill
    if not path.exists():
        return None
    return {"body": path.read_text(encoding="utf-8"), "source": "bundled" if "/plugins/" in str(path) else "local", "flags": []}


def list_plugins(root: str | Path = PROJECT_ROOT, env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    cfg = load_plugin_config(root)
    rows = []
    for manifest in discover_plugins(plugin_roots(root)):
        status = plugin_status(manifest, cfg, env=env)
        rows.append({"manifest": manifest, "status": status})
    return rows


def enable_plugin(root: str | Path, plugin_id: str, confirm: bool = False) -> dict[str, Any]:
    manifest = find_manifest(root, plugin_id)
    if not manifest:
        raise ValueError(f'Unknown plugin "{plugin_id}".')
    lock_entry = read_lock(root).get("plugins", {}).get(plugin_id)
    source = classify_source(manifest, root, lock_entry)
    if not confirm:
        return {"confirmed": False, "card": capability_card(manifest, source), "source": source}
    tree = hash_plugin_tree(manifest["dir"])
    write_lock_entry(
        root,
        plugin_id,
        {
            "source": "bundled" if source == "bundled" else "local",
            "repo": lock_entry.get("repo") if lock_entry else None,
            "sha": lock_entry.get("sha") if lock_entry else None,
            "version": manifest.get("version") or "0.0.0",
            "integrity": tree["integrity"],
            "files": tree["files"],
            "consent": consent_surface(manifest),
        },
    )
    set_enabled(root, plugin_id, True)
    return {"confirmed": True, "manifest": manifest}


def remove_plugin(root: str | Path, plugin_id: str) -> None:
    project = Path(root)
    local_dir = project / "plugins.local" / plugin_id
    if local_dir.exists():
        import shutil

        shutil.rmtree(local_dir)
    remove_lock_entry(project, plugin_id)
    set_enabled(project, plugin_id, False)


def find_in_registry(root: str | Path, target: str) -> dict[str, Any] | None:
    registry = load_registry(root)
    for entry in registry.get("plugins", []):
        if entry.get("id") == target or entry.get("name") == target:
            return entry
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="career-ops plugin CLI host.")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list")
    skill = sub.add_parser("skill")
    skill.add_argument("id", nargs="?")
    new = sub.add_parser("new")
    new.add_argument("name")
    enable = sub.add_parser("enable")
    enable.add_argument("id")
    enable.add_argument("--confirm", action="store_true")
    remove = sub.add_parser("remove")
    remove.add_argument("id")
    run = sub.add_parser("run")
    run.add_argument("id")
    run.add_argument("hook", nargs="?")
    run.add_argument("query", nargs="*")
    run.add_argument("--dry-run", action="store_true")
    available = sub.add_parser("available")
    add = sub.add_parser("add")
    add.add_argument("target")
    add.add_argument("--sha")
    add.add_argument("--confirm", action="store_true")
    trust = sub.add_parser("trust")
    trust.add_argument("id")
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.command in {None, "list"}:
        rows = list_plugins(root, env=os.environ)
        if not rows:
            print("No plugins discovered.")
        for row in rows:
            manifest = row["manifest"]
            status = row["status"]
            state = "enabled" if status["enabled"] else "disabled" if not status["configured"] else "missing env: " + ", ".join(status["missingEnv"])
            print(f"{manifest['id']} [{', '.join(manifest['hooks'])}] — {state}")
        return 0
    if args.command == "skill":
        if not args.id:
            ids = [row["manifest"]["id"] for row in list_plugins(root) if row["manifest"].get("skill")]
            print("\n".join(ids) if ids else "No installed plugin ships a skill.")
            return 0
        manifest = find_manifest(root, args.id)
        if not manifest:
            print(f'Unknown plugin "{args.id}".')
            return 1
        skill_doc = load_skill(manifest)
        if not skill_doc:
            print(f'Plugin "{args.id}" ships no skill.')
            return 1
        print(skill_doc["body"])
        return 0
    if args.command == "new":
        print(scaffold_new(root, args.name))
        return 0
    if args.command == "enable":
        result = enable_plugin(root, args.id, confirm=args.confirm)
        print(f"Enabled {args.id}." if result["confirmed"] else result["card"])
        return 0
    if args.command == "remove":
        remove_plugin(root, args.id)
        print(f"Removed {args.id}.")
        return 0
    if args.command == "run":
        manifest = find_manifest(root, args.id)
        if not manifest:
            print(f'Unknown plugin "{args.id}".')
            return 1
        cfg = load_plugin_config(root)
        status = plugin_status(manifest, cfg, env=os.environ)
        if not status["configured"]:
            print(f'Plugin "{args.id}" is not enabled. Run: node plugins.mjs enable {args.id} --confirm')
            return 1
        if status["missingEnv"]:
            print(f'Plugin "{args.id}" is missing env: {", ".join(status["missingEnv"])}')
            return 1
        hooks = [h for h in manifest.get("hooks", []) if h in RUNNABLE_HOOKS]
        if args.hook and args.hook in RUNNABLE_HOOKS:
            hook_kind = args.hook
        elif len(hooks) == 1:
            hook_kind = hooks[0]
        else:
            print(f"Specify a hook: {', '.join(hooks)}")
            return 1
        if hook_kind not in manifest.get("hooks", []):
            print(f'Plugin "{args.id}" does not expose hook "{hook_kind}". Available: {", ".join(manifest.get("hooks", []))}')
            return 1
        load_dotenv(root)
        payload: Any = None
        if hook_kind == "search":
            payload = " ".join(args.query) if args.query else ""
        elif hook_kind in ("export", "notify"):
            payload = build_snapshot(root) if hook_kind == "export" else {"message": " ".join(args.query) if args.query else ""}
        import asyncio
        results = asyncio.run(run_hook(hook_kind, payload, root=root, dry_run=args.dry_run))
        if not results:
            print(f"No plugins exposed hook \"{hook_kind}\".")
            return 0
        ok_count = sum(1 for r in results if r.get("ok"))
        fail_count = len(results) - ok_count
        if hook_kind == "ingest":
            jobs = []
            for r in results:
                if r.get("ok") and isinstance(r.get("result"), list):
                    for job in r["result"]:
                        sanitized = sanitize_job(job)
                        if sanitized:
                            jobs.append(sanitized)
            urls = existing_pipeline_urls(root)
            new_jobs = [job for job in jobs if job["url"] not in urls]
            if not args.dry_run and new_jobs:
                pipeline_file = root / "data" / "pipeline.md"
                lines = []
                if pipeline_file.exists():
                    content = pipeline_file.read_text(encoding="utf-8").rstrip()
                    if content:
                        lines = content.splitlines()
                if not lines or not lines[0].startswith("# Pipeline"):
                    lines.insert(0, "# Pipeline")
                for job in new_jobs:
                    lines.append(f"- [ ] {job['url']}  {job.get('title', '')}  {job.get('company', '')}")
                pipeline_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"ingested {len(new_jobs)} new jobs ({len(results)} plugins, {fail_count} failed)")
        elif hook_kind == "search":
            jobs = []
            for r in results:
                if r.get("ok") and isinstance(r.get("result"), list):
                    for job in r["result"]:
                        sanitized = sanitize_job(job)
                        if sanitized:
                            jobs.append(sanitized)
            urls = existing_pipeline_urls(root)
            new_jobs = [job for job in jobs if job["url"] not in urls]
            if not args.dry_run and new_jobs:
                pipeline_file = root / "data" / "pipeline.md"
                lines = []
                if pipeline_file.exists():
                    content = pipeline_file.read_text(encoding="utf-8").rstrip()
                    if content:
                        lines = content.splitlines()
                if not lines or not lines[0].startswith("# Pipeline"):
                    lines.insert(0, "# Pipeline")
                for job in new_jobs:
                    lines.append(f"- [ ] {job['url']}  {job.get('title', '')}  {job.get('company', '')}")
                pipeline_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"found {len(new_jobs)} new jobs ({len(results)} plugins, {fail_count} failed)")
        elif hook_kind == "export":
            pushed = sum(1 for r in results if r.get("ok"))
            print(f"exported to {pushed} plugins ({fail_count} failed)")
        elif hook_kind == "notify":
            sent = sum(1 for r in results if r.get("ok"))
            print(f"sent {sent} notifications ({fail_count} failed)")
        for r in results:
            if not r.get("ok"):
                print(f"  {r['id']}: {r.get('error', 'unknown error')}")
        return 0
    if args.command == "available":
        registry = load_registry(root)
        entries = registry.get("plugins", [])
        if not entries:
            print("No plugins in registry.")
            return 0
        installed = {m["id"] for m in discover_plugins(plugin_roots(root))}
        for entry in entries:
            pid = entry.get("id", "?")
            status_tag = "installed" if pid in installed else "available"
            hooks = ", ".join(entry.get("hooks", []))
            print(f"{pid} [{hooks}] — {status_tag} (v{entry.get('version', '?')})")
        return 0
    if args.command == "add":
        target = args.target
        registry_entry = find_in_registry(root, target)
        if registry_entry and "/" not in target:
            url = registry_entry.get("repo", "")
            sha = args.sha or registry_entry.get("sha", "")
            approved = True
        else:
            parsed = parse_repo_arg(target)
            url = parsed["url"]
            sha = args.sha
            if not sha:
                print("--sha is required for non-registry repos")
                return 1
            approved = False
        if not sha:
            print("No SHA available. Provide --sha or use a registry name.")
            return 1
        try:
            result = install_from_repo(root, url, sha)
        except Exception as exc:
            print(f"install failed: {exc}")
            return 1
        consent = consent_surface(result["manifest"])
        consent["acceptedAt"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        write_lock_entry(root, result["id"], {
            "source": "local",
            "repo": result["repo"],
            "sha": result["sha"],
            "version": result["manifest"].get("version") or "0.0.0",
            "integrity": result["integrity"],
            "files": result["files"],
            "consent": consent,
        })
        lock_entry = read_lock(root).get("plugins", {}).get(result["id"])
        source = classify_source(result["manifest"], root, lock_entry)
        print(capability_card(result["manifest"], source))
        if approved:
            print("  Trust badge:    registry-approved")
        if args.confirm:
            set_enabled(root, result["id"], True)
            print(f"  Enabled:        yes")
        return 0
    if args.command == "trust":
        manifest = find_manifest(root, args.id)
        if not manifest:
            print(f'Unknown plugin "{args.id}".')
            return 1
        tree = hash_plugin_tree(manifest["dir"])
        lock_entry = read_lock(root).get("plugins", {}).get(args.id)
        source = classify_source(manifest, root, lock_entry)
        write_lock_entry(root, args.id, {
            "source": "bundled" if source == "bundled" else "local",
            "repo": lock_entry.get("repo") if lock_entry else None,
            "sha": lock_entry.get("sha") if lock_entry else None,
            "version": manifest.get("version") or "0.0.0",
            "integrity": tree["integrity"],
            "files": tree["files"],
            "consent": consent_surface(manifest),
        })
        print(f"Re-pinned {args.id} (integrity: {tree['integrity'][:20]}…)")
        return 0
    parser.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
