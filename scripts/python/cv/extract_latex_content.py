#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.python.cv.latex_content import build_manifest


def extract_latex_content(source_path: str | Path) -> dict:
    path = Path(source_path)
    return build_manifest(path.name, path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect LaTeX CV family and list editable prose slots.")
    parser.add_argument("source")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    path = Path(args.source)
    if not path.exists():
        print(f"Source not found: {path.resolve(strict=False)}")
        return 1
    manifest = extract_latex_content(path)
    payload = json.dumps(manifest, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if manifest["supported"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
