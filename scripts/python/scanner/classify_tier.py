#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from typing import Literal


Tier = Literal["intern", "entry", "mid", "senior"]


def classify_tier(title: object) -> Tier:
    if not isinstance(title, str):
        return "mid"
    clean = title
    replacements = [
        (r"\bA\.I\.", "AI"),
        (r"\bA\.I\b", "AI"),
        (r"\bA\.\s+I\b", "AI"),
        (r"\bI\.T\.", "IT"),
        (r"\bI\.T\b", "IT"),
        (r"\bI\.\s+T\b", "IT"),
        (r"\bi/o\b", "IO"),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)

    matchers: list[tuple[object, Tier, int]] = [
        (r"\bchief\b", "senior", 4),
        (r"\bvp\b", "senior", 4),
        (r"\bvice\s+president\b", "senior", 4),
        (r"\bdirector\b", "senior", 4),
        (r"\bprincipal\b", "senior", 4),
        (r"\bstaff\b", "senior", 4),
        (r"\blead\b", "senior", 4),
        (r"\bsenior\b", "senior", 4),
        (r"\bsr\b", "senior", 4),
        (r"\bsr\.", "senior", 4),
        (r"\bhead\s+of\b", "senior", 4),
        (r"\b[a-z]{2,}[\s-](iii|iv|v)\b", "senior", 4),
        (r"\bmid-level\b", "mid", 3),
        (r"\bmid\b", "mid", 3),
        (r"\b[a-z]{2,}[\s-](ii)\b", "mid", 3),
        (r"\b(l4|l5)\b", "mid", 3),
        (r"\bentry-level\b", "entry", 2),
        (r"\bentry\b", "entry", 2),
        (r"\bassociate\b", "entry", 2),
        (r"\bjunior\b", "entry", 2),
        (r"\b[a-z]{2,}[\s-](i)\b", "entry", 2),
        (r"\b(l1|l2)\b", "entry", 2),
        (r"\binternship\b", "intern", 1),
        (r"\bintern\b", "intern", 1),
        (r"\btrainee\b", "intern", 1),
        (r"\bco-op\b", "intern", 1),
        (lambda text: re.search(r"\bgraduate\b", text, re.IGNORECASE) and re.search(r"\b(program|scheme)\b", text, re.IGNORECASE), "intern", 1),
    ]
    best: tuple[Tier, int] | None = None
    for pattern, tier, weight in matchers:
        matched = bool(pattern(clean)) if callable(pattern) else bool(re.search(pattern, clean, re.IGNORECASE))
        if matched and (best is None or weight > best[1]):
            best = (tier, weight)
    return best[0] if best else "mid"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a job title seniority tier.")
    parser.add_argument("title", nargs="?")
    args = parser.parse_args(argv)
    if not args.title:
        parser.print_usage()
        return 0
    print(classify_tier(args.title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

