#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.python import CONFIG_DIR, PROJECT_ROOT


DEFAULT_SOURCES = ["cv.md", "article-digest.md"]
DEFAULT_CONFIG = CONFIG_DIR / "cv-facts.json"


def read_if_exists(path: str | Path) -> str:
    file = Path(path)
    return file.read_text(encoding="utf-8") if file.exists() else ""


def strip_markup(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>[\s\S]*?</script\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<style\b[^>]*>[\s\S]*?</style\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^}]*)\})?", r" \1 ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def normalize_claim(claim: str) -> str:
    return re.sub(r"[,\s]+", " ", claim.lower()).strip()


def metric_claims(text: str) -> set[str]:
    clean = strip_markup(text)
    patterns = [
        re.compile(r"\b\d+(?:\.\d+)?\s?%"),
        re.compile(r"\b[$€£]\s?\d[\d,.]*(?:\s?[kKmMbB])?"),
        re.compile(r"\b\d+(?:\.\d+)?\s?x\b", re.I),
        re.compile(
            r"\b\d[\d,.]*\+?\s?(?:users|customers|clients|employees|engineers|teams|companies|hours|days|weeks|months|years|minutes|seconds|requests|tokens|documents|workflows|pipelines|agents|interviews|applications|offers|reports|cvs|resumes)\b",
            re.I,
        ),
    ]
    claims: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(clean):
            claims.add(normalize_claim(match.group(0)))
    return claims


def load_config(path: str | Path) -> dict[str, list[str]]:
    file = Path(path)
    if not file.exists():
        return {"allow_metrics": [], "forbidden_phrases": []}
    config = json.loads(file.read_text(encoding="utf-8"))
    for key in ["allow_metrics", "forbidden_phrases"]:
        if config.get(key) is None:
            config[key] = []
        elif not isinstance(config.get(key), list):
            raise ValueError(f"{key} must be an array in {file}")
    return config


def resolve_input_path(path: str | Path, *, cwd: str | Path = PROJECT_ROOT) -> Path:
    file = Path(path)
    return file if file.is_absolute() else Path(cwd) / file


def verify_cv_facts(
    target: str | Path,
    *,
    sources: list[str | Path] | None = None,
    config_path: str | Path = DEFAULT_CONFIG,
    cwd: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    target_path = resolve_input_path(target, cwd=cwd)
    if not target_path.exists():
        raise FileNotFoundError(f"target file not found: {target}")
    source_paths = sources if sources else DEFAULT_SOURCES
    source_text = "\n".join(read_if_exists(resolve_input_path(path, cwd=cwd)) for path in source_paths)
    target_text = target_path.read_text(encoding="utf-8")
    config = load_config(resolve_input_path(config_path, cwd=cwd))
    allowed = {
        *metric_claims(source_text),
        *(normalize_claim(str(item)) for item in config.get("allow_metrics", [])),
    }
    target_claims = metric_claims(target_text)
    invented = sorted(claim for claim in target_claims if claim not in allowed)
    clean_target = strip_markup(target_text).lower()
    forbidden = [str(phrase) for phrase in config.get("forbidden_phrases", []) if phrase and str(phrase).lower() in clean_target]
    return {"ok": not invented and not forbidden, "target": target_path.name, "invented": invented, "forbidden": forbidden}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard generated CVs against invented metrics.")
    parser.add_argument("target")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify_cv_facts(args.target, sources=args.source or None, config_path=args.config, cwd=Path.cwd())
    except Exception as error:
        print(f"ERROR: {error}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print(f"CV fact check passed: {result['target']}")
    else:
        print(f"CV fact check failed: {result['target']}")
        if result["invented"]:
            print("\nMetric-like claims absent from sources:")
            for claim in result["invented"]:
                print(f"  - {claim}")
        if result["forbidden"]:
            print("\nForbidden phrases found:")
            for phrase in result["forbidden"]:
                print(f"  - {phrase}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
