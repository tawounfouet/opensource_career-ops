#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FORBIDDEN_MODULES = {
    "child_process",
    "node:child_process",
    "playwright",
    "worker_threads",
    "node:worker_threads",
    "vm",
    "node:vm",
    "node:http",
    "node:https",
    "node:net",
    "node:dns",
    "node:dns/promises",
    "node:tls",
    "node:dgram",
    "http",
    "https",
    "net",
    "dns",
    "tls",
    "dgram",
    "node:cluster",
    "node:v8",
    "node:inspector",
    "node:repl",
}
ALLOWED_NODE = {
    "node:crypto",
    "node:url",
    "node:path",
    "node:buffer",
    "node:util",
    "node:querystring",
    "node:string_decoder",
    "node:assert",
    "node:events",
    "node:fs",
    "node:fs/promises",
    "node:os",
    "node:zlib",
    "node:stream",
}
IMPORT_RE = re.compile(r"\bimport\s+(?:[\s\S]*?\s+from\s+)?[\"']([^\"']+)[\"']")
DYN_IMPORT_RE = re.compile(r"\bimport\s*\(\s*[\"']([^\"']+)[\"']\s*\)")
REQUIRE_RE = re.compile(r"\brequire\s*\(\s*[\"']([^\"']+)[\"']\s*\)")
FIREWALL_RE = re.compile(r"\b(revenue|pricing|paywall|monetiz\w*|moat)\b", re.IGNORECASE)


def collect_specifiers(source: str) -> list[str]:
    specs: list[str] = []
    for regex in (IMPORT_RE, DYN_IMPORT_RE, REQUIRE_RE):
        specs.extend(match.group(1) for match in regex.finditer(source))
    return specs


def list_js_files(directory: str | Path) -> list[Path]:
    root = Path(directory)
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".mjs", ".js", ".cjs"} and "node_modules" not in path.parts and ".git" not in path.parts)


def audit_plugin(directory: str | Path) -> dict[str, object]:
    root = Path(directory)
    findings: list[dict[str, str]] = []
    for path in list_js_files(root):
        rel = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        for spec in collect_specifiers(source):
            is_relative = spec.startswith("./") or spec.startswith("../")
            is_node = spec.startswith("node:") or spec in {"crypto", "url", "path", "buffer", "util", "fs", "os", "zlib", "stream", "events", "assert", "querystring"}
            if spec in FORBIDDEN_MODULES:
                findings.append({"file": rel, "issue": f'forbidden import "{spec}" — community plugins egress only through ctx.fetch and may not spawn/raw-socket'})
            elif is_node and spec not in ALLOWED_NODE and f"node:{spec}" not in ALLOWED_NODE:
                findings.append({"file": rel, "issue": f'node builtin "{spec}" is not on the plugin allowlist'})
            elif not is_relative and not is_node:
                findings.append({"file": rel, "issue": f'bare-specifier import "{spec}" — registry plugins must be dependency-free (relative + allowlisted node: builtins only)'})
        if re.search(r"(?<![.\w$])fetch\s*\(", source):
            findings.append({"file": rel, "issue": "direct global fetch() — use ctx.fetch so the egress allowlist applies"})
        if re.search(r"\bXMLHttpRequest\b|\bWebSocket\b", source):
            findings.append({"file": rel, "issue": "XMLHttpRequest/WebSocket egress — use ctx.fetch"})
        if re.search(r"\beval\s*\(|new\s+Function\s*\(", source):
            findings.append({"file": rel, "issue": "eval/new Function — dynamic code execution is not allowed"})
        if re.search(r"process\s*\.\s*(binding|dlopen)\b", source):
            findings.append({"file": rel, "issue": "process.binding/dlopen — native escape hatch not allowed"})
        if FIREWALL_RE.search(source):
            findings.append({"file": rel, "issue": "commercial/monetization wording in a shipped community plugin (keep it mission-framed)"})
    return {"ok": not findings, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static safety scan for community plugins.")
    parser.add_argument("directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = audit_plugin(args.directory)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print("audit clean")
    else:
        for finding in result["findings"]:
            print(f"{finding['file']}: {finding['issue']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
