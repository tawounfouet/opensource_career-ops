from __future__ import annotations

import re
from typing import Any

from scripts.python.cv.build_latex import escape_latex


SUPPORTED_FAMILIES = ["resumeSubheading", "tabularx-itemize"]
UNSUPPORTED_HINT = (
    "Unsupported LaTeX CV layout. v1 supports \\resumeSubheading + \\resumeItem macros, "
    "or tabularx + itemize without resume macros. Use /career-ops latex (cv.md → career-ops template) instead."
)


def find_matching_brace(tex: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(tex) or tex[open_idx] != "{":
        return -1
    depth = 0
    escaped = False
    for idx in range(open_idx, len(tex)):
        ch = tex[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def detect_family(tex: str) -> str | None:
    if not isinstance(tex, str) or not tex.strip():
        return None
    if re.search(r"\\resumeSubheading\b", tex) and re.search(r"\\resumeItem\b", tex):
        return "resumeSubheading"
    has_tabularx = bool(re.search(r"\\usepackage\{[^}]*tabularx[^}]*\}", tex) or re.search(r"\\begin\{tabularx\}", tex))
    has_itemize = bool(re.search(r"\\begin\{itemize\}", tex))
    if has_tabularx and has_itemize and not re.search(r"\\resumeSubheading\b", tex):
        return "tabularx-itemize"
    return None


def extract_macro_bodies(tex: str, macro_name: str, kind: str) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    needle = f"\\{macro_name}{{"
    search_from = 0
    while search_from < len(tex):
        idx = tex.find(needle, search_from)
        if idx == -1:
            break
        open_brace = idx + len(needle) - 1
        close_brace = find_matching_brace(tex, open_brace)
        if close_brace == -1:
            break
        inner_start = open_brace + 1
        inner_end = close_brace
        slots.append(
            {
                "id": f"{kind}-{len(slots)}",
                "kind": kind,
                "text": tex[inner_start:inner_end],
                "span": {"start": inner_start, "end": inner_end},
            }
        )
        search_from = close_brace + 1
    return slots


def extract_skill_values(tex: str) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    search_from = 0
    while search_from < len(tex):
        idx = tex.find(r"\textbf{", search_from)
        if idx == -1:
            break
        open_cat = tex.find("{", idx)
        close_cat = find_matching_brace(tex, open_cat)
        if close_cat == -1:
            break
        cursor = close_cat + 1
        while cursor < len(tex) and tex[cursor].isspace():
            cursor += 1
        if cursor >= len(tex) or tex[cursor] != "{":
            search_from = close_cat + 1
            continue
        open_val = cursor
        close_val = find_matching_brace(tex, open_val)
        if close_val == -1:
            break
        raw_value = tex[open_val + 1 : close_val]
        colon = re.match(r"^:\s*", raw_value)
        if not colon:
            search_from = close_val + 1
            continue
        items_start = open_val + 1 + len(colon.group(0))
        slots.append(
            {
                "id": f"skill-{len(slots)}",
                "kind": "skill",
                "text": tex[items_start:close_val],
                "span": {"start": items_start, "end": close_val},
            }
        )
        search_from = close_val + 1
    return slots


def extract_itemize_items(tex: str) -> list[dict[str, Any]]:
    doc_start = tex.find(r"\begin{document}")
    body = tex if doc_start == -1 else tex[doc_start:]
    offset = 0 if doc_start == -1 else doc_start
    slots: list[dict[str, Any]] = []
    for match in re.finditer(r"\\item\b", body):
        idx = match.end()
        while idx < len(body) and body[idx].isspace():
            idx += 1
        if idx < len(body) and body[idx] == "{":
            close = find_matching_brace(body, idx)
            if close == -1:
                continue
            slots.append(
                {
                    "id": f"item-{len(slots)}",
                    "kind": "item",
                    "text": body[idx + 1 : close],
                    "span": {"start": offset + idx + 1, "end": offset + close},
                }
            )
            continue
        line_end = body.find("\n", idx)
        end = len(body) if line_end == -1 else line_end
        text = body[idx:end].strip()
        if not text:
            continue
        slots.append(
            {
                "id": f"item-{len(slots)}",
                "kind": "item",
                "text": text,
                "span": {"start": offset + idx, "end": offset + end},
            }
        )
    return slots


def extract_slots(tex: str, family: str | None) -> list[dict[str, Any]]:
    if family == "resumeSubheading":
        return [*extract_macro_bodies(tex, "resumeItem", "bullet"), *extract_skill_values(tex)]
    if family == "tabularx-itemize":
        return extract_itemize_items(tex)
    return []


def build_manifest(tex_path: str, tex: str) -> dict[str, Any]:
    family = detect_family(tex)
    if not family:
        return {
            "supported": False,
            "family": None,
            "source": tex_path,
            "slots": [],
            "error": UNSUPPORTED_HINT,
            "hint": "Place resume.tex in the project root or set latex.source in config/profile.yml.",
        }
    return {"supported": True, "family": family, "source": tex_path, "slots": extract_slots(tex, family)}


def apply_patches(tex: str, patches: list[dict[str, Any]], slots: list[dict[str, Any]], *, escape: bool = True) -> str:
    slot_by_id = {slot.get("id"): slot for slot in slots}
    ordered = []
    for patch in patches:
        slot = slot_by_id.get(patch.get("id"))
        if slot:
            ordered.append({"slot": slot, "text": patch.get("text", "")})
    ordered.sort(key=lambda item: item["slot"]["span"]["start"], reverse=True)
    output = tex
    for item in ordered:
        slot = item["slot"]
        replacement = escape_latex(str(item["text"])) if escape else str(item["text"])
        output = output[: slot["span"]["start"]] + replacement + output[slot["span"]["end"] :]
    return output
