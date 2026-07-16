from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


HOOK_KINDS = ["provider", "ingest", "search", "notify", "export"]
RUNNABLE_HOOKS = ["ingest", "search", "notify", "export"]
DEFAULT_HOOK_TIMEOUT_MS = 15_000
RESERVED_ENV = {
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "OPENROUTER_API_KEY",
    "CAREER_OPS_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "CAREER_OPS_PORTALS",
    "CAREER_OPS_PROFILE",
    "PATH",
    "HOME",
    "NODE_OPTIONS",
    "LD_PRELOAD",
    "NODE_EXTRA_CA_CERTS",
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def is_reserved_env(name: str) -> bool:
    return name in RESERVED_ENV or name.startswith("AWS_")


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def validate_manifest(manifest: Any, plugin_dir: str | Path, dir_name: str | None = None) -> dict[str, Any] | None:
    directory = Path(plugin_dir)
    name = dir_name or directory.name
    if not isinstance(manifest, dict):
        return None
    if not isinstance(manifest.get("id"), str) or not ID_RE.match(manifest["id"]):
        return None
    if manifest["id"] != name:
        return None
    if manifest.get("apiVersion") != 1:
        return None
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip() or "\n" in manifest["description"] or "\r" in manifest["description"]:
        return None
    if manifest.get("humanInTheLoop") is not True:
        return None
    hooks = manifest.get("hooks")
    if not isinstance(hooks, list) or not hooks or any(hook not in HOOK_KINDS for hook in hooks):
        return None
    required_env = manifest.get("requiredEnv", [])
    optional_env = manifest.get("optionalEnv", [])
    if not isinstance(required_env, list) or any(not isinstance(item, str) for item in required_env):
        return None
    if not isinstance(optional_env, list) or any(not isinstance(item, str) for item in optional_env):
        return None
    if any(is_reserved_env(item) for item in [*required_env, *optional_env]):
        return None
    allowed_hosts = manifest.get("allowedHosts", [])
    if not isinstance(allowed_hosts, list) or any(not isinstance(item, str) for item in allowed_hosts):
        return None
    if required_env and not allowed_hosts:
        return None
    allows_localhost = manifest.get("allowsLocalhost") is True
    if allows_localhost and not allowed_hosts:
        return None
    for host in allowed_hosts:
        is_loopback = bool(re.match(r"^(localhost|127\.\d+\.\d+\.\d+|::1|\[::1\])$", host, re.IGNORECASE))
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) and not (allows_localhost and is_loopback):
            return None
        if re.search(r"(^169\.254\.)|(^metadata\.google\.internal$)|(\.internal$)", host, re.IGNORECASE):
            return None
        if is_loopback and not allows_localhost:
            return None
    entry = manifest.get("entry") if isinstance(manifest.get("entry"), str) and manifest.get("entry", "").strip() else "index.mjs"
    if not (entry.endswith(".mjs") or entry.endswith(".py")) or not _inside(directory, directory / entry):
        return None
    skill = None
    if "skill" in manifest:
        skill_value = manifest["skill"]
        if not isinstance(skill_value, str) or not skill_value.endswith(".md") or not _inside(directory, directory / skill_value):
            return None
        if not (directory / skill_value).exists():
            return None
        skill = skill_value
    return {
        "id": manifest["id"],
        "apiVersion": 1,
        "description": manifest["description"].strip(),
        "hooks": list(hooks),
        "requiredEnv": list(required_env),
        "optionalEnv": list(optional_env),
        "allowedHosts": list(allowed_hosts),
        "allowsLocalhost": allows_localhost,
        "entry": entry,
        "skill": skill,
        "humanInTheLoop": True,
        "name": manifest.get("name") if isinstance(manifest.get("name"), str) else None,
        "version": manifest.get("version") if isinstance(manifest.get("version"), str) else None,
        "homepage": manifest.get("homepage") if isinstance(manifest.get("homepage"), str) else None,
        "dir": str(directory),
    }


def discover_plugins(roots: list[str | Path], override_ids: set[str] | None = None) -> list[dict[str, Any]]:
    override_ids = override_ids or set()
    found: dict[str, dict[str, Any]] = {}
    for root in [Path(item) for item in roots]:
        if not root.exists():
            continue
        for child in sorted([item for item in root.iterdir() if item.is_dir() and not item.name.startswith(("_", "."))], key=lambda p: p.name):
            manifest_file = child / "manifest.json"
            if not manifest_file.exists():
                continue
            try:
                parsed = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            manifest = validate_manifest(parsed, child, child.name)
            if not manifest:
                continue
            if manifest["id"] in found and manifest["id"] not in override_ids:
                continue
            found[manifest["id"]] = manifest
    return list(found.values())


def plugin_roots(root: str | Path) -> list[Path]:
    base = Path(root)
    return [base / "plugins", base / "plugins.local"]


def plugin_status(manifest: dict[str, Any], cfg: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env if env is not None else os.environ
    entry = ((cfg or {}).get("plugins") or {}).get(manifest["id"]) or {}
    configured = entry.get("enabled") is True
    missing = [name for name in manifest.get("requiredEnv", []) if not env.get(name)]
    return {"enabled": configured and not missing, "configured": configured, "missingEnv": missing}


def plugin_settings(manifest: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    entry = ((cfg or {}).get("plugins") or {}).get(manifest["id"]) or {}
    return {k: v for k, v in entry.items() if k != "enabled"}


def scoped_env(manifest: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, str]:
    full = env if env is not None else os.environ
    keys = manifest.get("requiredEnv", []) + manifest.get("optionalEnv", [])
    return {k: full[k] for k in keys if k in full}


def redact_log(msg: str, sensitive: list[str], env: dict[str, str] | None = None) -> str:
    _env = env if env is not None else os.environ
    result = msg
    for key in sensitive:
        val = _env.get(key, "")
        if len(val) > 5:
            result = result.replace(val, f"[REDACTED:{key}]")
    return result


RUNNER_MJS = r"""
import { pathToFileURL } from 'url';

async function main() {
    const entryPath = process.argv[2];
    const hookKind = process.argv[3];
    const payloadJson = process.argv[4] || 'null';
    const envJson = process.argv[5] || '{}';
    const settingsJson = process.argv[6] || '{}';
    const dryRun = process.argv[7] === 'true';

    const env = JSON.parse(envJson);
    const settings = JSON.parse(settingsJson);

    const ctx = {
        transport: 'http',
        env: Object.freeze(env),
        settings: Object.freeze(settings),
        dryRun,
        log: (...args) => {
            const msg = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ');
            const redacted = Object.entries(env).reduce((m, [k, v]) =>
                typeof v === 'string' && v.length > 5 ? m.replaceAll(v, `[REDACTED:${k}]`) : m, msg);
            process.stderr.write(redacted + '\n');
        },
        fetch: async (url, opts) => {
            const parsed = new URL(url);
            if (parsed.protocol !== 'https:') throw new Error(`blocked non-HTTPS fetch: ${url}`);
            return globalThis.fetch(url, opts);
        },
        fetchText: async (url, opts) => {
            const res = await ctx.fetch(url, opts);
            return res.text();
        },
        fetchJson: async (url, opts) => {
            const res = await ctx.fetch(url, opts);
            return res.json();
        },
    };

    try {
        const mod = await import(pathToFileURL(entryPath).href);
        const hooks = mod.default || mod.HOOKS || mod;
        const hook = typeof hooks === 'object' ? hooks[hookKind] : undefined;
        if (typeof hook !== 'function') {
            process.stdout.write(JSON.stringify({ ok: false, error: 'hook "' + hookKind + '" not found or not a function' }));
            return;
        }
        const payload = JSON.parse(payloadJson);
        const result = await hook(payload, ctx);
        process.stdout.write(JSON.stringify({ ok: true, result }));
    } catch (err) {
        process.stdout.write(JSON.stringify({ ok: false, error: String(err.message || err) }));
    }
}

main();
"""


def _import_hook_mjs(entry: Path, plugin_id: str, kind: str) -> Any | None:
    runner = entry.parent / ".career-ops-runner.mjs"
    try:
        runner.write_text(RUNNER_MJS, encoding="utf-8")

        def call_hook(payload: Any, ctx_env: dict[str, str], ctx_settings: dict[str, str], dry_run: bool) -> dict[str, Any]:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", f"import subprocess,sys; subprocess.run(['node','{runner}','{entry}','{kind}','{json.dumps(json.dumps(payload))}','{json.dumps(json.dumps(ctx_env))}','{json.dumps(json.dumps(ctx_settings))}','{str(dry_run).lower()}'],capture_output=True,text=True,timeout={DEFAULT_HOOK_TIMEOUT_MS // 1000 + 5})"],
                    capture_output=True,
                    text=True,
                    timeout=DEFAULT_HOOK_TIMEOUT_MS // 1000 + 5,
                )
                stdout = result.stdout.strip() or result.stderr.strip()
                if not stdout:
                    return {"ok": False, "error": "no output from runner"}
                return json.loads(stdout)
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"hook timed out after {DEFAULT_HOOK_TIMEOUT_MS}ms"}
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"invalid JSON from runner: {exc}"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        return call_hook
    except Exception:
        return None
    finally:
        try:
            runner.unlink(missing_ok=True)
        except Exception:
            pass


def _import_hook_py(entry: Path, plugin_id: str, kind: str) -> Any | None:
    try:
        module_name = f"_career_ops_plugin_{plugin_id}"
        spec = importlib.util.spec_from_file_location(module_name, entry)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        hooks = getattr(module, "HOOKS", None) or getattr(module, "default", None)
        if isinstance(hooks, dict):
            hook = hooks.get(kind)
        elif hasattr(module, kind):
            hook = getattr(module, kind)
        else:
            return None
        if not callable(hook):
            return None
        return hook
    except Exception:
        return None


def import_hook(manifest: dict[str, Any], kind: str) -> Any | None:
    entry = Path(manifest["dir"]) / manifest["entry"]
    if not entry.exists():
        return None
    if entry.suffix == ".py":
        return _import_hook_py(entry, manifest["id"], kind)
    if entry.suffix == ".mjs":
        return _import_hook_mjs(entry, manifest["id"], kind)
    return None


def diff_plugin(manifest: dict[str, Any], lock_entry: dict[str, Any] | None) -> str:
    if not lock_entry:
        return "unpinned"
    from scripts.python.plugins.install import hash_plugin_tree as _hpt
    tree = _hpt(manifest["dir"])
    if tree["integrity"] == lock_entry.get("integrity"):
        added_hosts = [h for h in manifest.get("allowedHosts", []) if h not in lock_entry.get("consent", {}).get("allowedHosts", [])]
        added_env = [e for e in manifest.get("requiredEnv", []) if e not in lock_entry.get("consent", {}).get("requiredEnv", [])]
        surface_widened = bool(added_hosts or added_env or (manifest.get("allowsLocalhost") and not lock_entry.get("consent", {}).get("allowsLocalhost")))
        return "surface-widened" if surface_widened else "match"
    added_hosts = [h for h in manifest.get("allowedHosts", []) if h not in lock_entry.get("consent", {}).get("allowedHosts", [])]
    added_env = [e for e in manifest.get("requiredEnv", []) if e not in lock_entry.get("consent", {}).get("requiredEnv", [])]
    surface_widened = bool(added_hosts or added_env or (manifest.get("allowsLocalhost") and not lock_entry.get("consent", {}).get("allowsLocalhost")))
    if surface_widened:
        return "surface-widened"
    from scripts.python.plugins.install import hash_plugin_tree as _hpt
    from packaging.version import Version
    try:
        bumped = Version(manifest.get("version") or "0.0.0") > Version(lock_entry.get("version") or "0.0.0")
    except Exception:
        bumped = False
    return "legit-update" if bumped else "drift-nobump"


def lock_gate(manifest: dict[str, Any], root: str | Path) -> dict[str, bool]:
    project = Path(root)
    is_bundled = Path(manifest["dir"]).resolve().relative_to((project / "plugins").resolve()) is not None if (project / "plugins").exists() else False
    try:
        Path(manifest["dir"]).resolve().relative_to((project / "plugins").resolve())
        is_bundled = True
    except (ValueError, OSError):
        is_bundled = False
    try:
        from scripts.python.plugins.cli import read_lock
        lock = read_lock(project)
    except Exception:
        return {"load": True}
    lock_entry = lock.get("plugins", {}).get(manifest["id"])
    status = diff_plugin(manifest, lock_entry)
    if status in ("unpinned", "match", "legit-update"):
        return {"load": True}
    if status == "drift-nobump" and not is_bundled:
        return {"load": False}
    return {"load": True}


def load_dotenv(root: str | Path) -> None:
    env_file = Path(root) / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


def load_plugins(kind: str, root: str | Path, dry_run: bool = False, env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    from scripts.python.plugins.cli import load_plugin_config
    project = Path(root)
    cfg = load_plugin_config(project)
    manifests = discover_plugins(plugin_roots(project))
    loaded: list[dict[str, Any]] = []
    for manifest in manifests:
        if kind not in manifest.get("hooks", []):
            continue
        status = plugin_status(manifest, cfg, env=env)
        if not status["enabled"]:
            continue
        gate = lock_gate(manifest, project)
        if not gate["load"]:
            continue
        hook = import_hook(manifest, kind)
        if hook is None:
            continue
        ctx_env = scoped_env(manifest, env)
        ctx_settings = plugin_settings(manifest, cfg)
        loaded.append({
            "id": manifest["id"],
            "manifest": manifest,
            "hook": hook,
            "ctx_env": ctx_env,
            "ctx_settings": ctx_settings,
        })
    return loaded


def _call_hook_sync(hook: Any, payload: Any, ctx_env: dict[str, str], ctx_settings: dict[str, str], dry_run: bool, plugin_id: str, kind: str) -> dict[str, Any]:
    if isinstance(hook, dict):
        return hook
    try:
        if kind == "ingest":
            result = hook({"transport": "http", "env": ctx_env, "settings": ctx_settings, "dryRun": dry_run, "log": lambda *a: None, "fetch": lambda *a, **kw: None, "fetchText": lambda *a, **kw: None, "fetchJson": lambda *a, **kw: None})
        else:
            result = hook(payload, {"transport": "http", "env": ctx_env, "settings": ctx_settings, "dryRun": dry_run, "log": lambda *a: None, "fetch": lambda *a, **kw: None, "fetchText": lambda *a, **kw: None, "fetchJson": lambda *a, **kw: None})
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def run_hook(kind: str, payload: Any, *, root: str | Path, dry_run: bool = False, timeout_ms: int = DEFAULT_HOOK_TIMEOUT_MS) -> list[dict[str, Any]]:
    load_dotenv(root)
    loaded = load_plugins(kind, root, dry_run=dry_run)
    results: list[dict[str, Any]] = []
    for item in loaded:
        plugin_id = item["id"]
        hook = item["hook"]
        ctx_env = item["ctx_env"]
        ctx_settings = item["ctx_settings"]
        if isinstance(hook, dict):
            result = {"ok": True, "result": hook}
        elif callable(hook) and not isinstance(hook, dict):
            try:
                if kind == "ingest":
                    coro = asyncio.to_thread(hook, {"transport": "http", "env": ctx_env, "settings": ctx_settings, "dryRun": dry_run, "log": lambda *a: None, "fetch": lambda *a, **kw: None, "fetchText": lambda *a, **kw: None, "fetchJson": lambda *a, **kw: None})
                else:
                    coro = asyncio.to_thread(hook, payload, {"transport": "http", "env": ctx_env, "settings": ctx_settings, "dryRun": dry_run, "log": lambda *a: None, "fetch": lambda *a, **kw: None, "fetchText": lambda *a, **kw: None, "fetchJson": lambda *a, **kw: None})
                result_data = await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
                result = {"ok": True, "result": result_data}
            except asyncio.TimeoutError:
                result = {"ok": False, "error": f"hook timed out after {timeout_ms}ms"}
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
        else:
            result = hook(payload, ctx_env, ctx_settings, dry_run) if callable(hook) else {"ok": False, "error": "hook is not callable"}
        results.append({"id": plugin_id, **result})
    return results
