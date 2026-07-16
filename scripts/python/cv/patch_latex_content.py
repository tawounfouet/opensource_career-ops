#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.python.cv.latex_content import apply_patches


def patch_latex_content(source_path: str | Path, patches_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    source = Path(source_path)
    patches_file = Path(patches_path)
    output = Path(output_path)
    tex = source.read_text(encoding="utf-8")
    payload = json.loads(patches_file.read_text(encoding="utf-8"))
    patches = payload.get("patches") if isinstance(payload.get("patches"), list) else []
    slots = payload.get("slots") if isinstance(payload.get("slots"), list) else []
    if not slots:
        raise ValueError("patches.json must include a slots array from extract_latex_content.py")
    missing = [patch for patch in patches if not any(slot.get("id") == patch.get("id") for slot in slots)]
    if missing:
        raise ValueError("Unknown patch ids: " + ", ".join(str(patch.get("id")) for patch in missing))
    patched = apply_patches(tex, patches, slots)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(patched, encoding="utf-8")
    return {"source": str(source.resolve(strict=False)), "output": str(output.resolve(strict=False)), "patched": len(patches), "valid": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply prose patches to a user-owned LaTeX CV.")
    parser.add_argument("source")
    parser.add_argument("patches")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(patch_latex_content(args.source, args.patches, args.output), indent=2))
        return 0
    except Exception as error:
        print(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
