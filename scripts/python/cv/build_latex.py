#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.python.cv.templates import resolve_template


PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")


def escape_latex(text: Any, mode: str = "text") -> str:
    if not isinstance(text, str):
        return ""
    if mode == "url":
        return text
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
        "_": r"\_",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "±": r"$\pm$",
        "→": r"$\rightarrow$",
    }
    return "".join(replacements.get(char, char) for char in text)


def sanitize_url(url: Any) -> str:
    if not isinstance(url, str):
        return ""
    value = url.strip()
    if not value:
        return ""
    lower = value.lower()
    if not lower.startswith(("mailto:", "http:", "https:")):
        value = f"mailto:{value}" if "@" in value and "/" not in value else f"https://{value}"
    return re.sub(r"[{}%$#\\~^]", "", value)


def build_education(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        block = (
            "    \\resumeSubheading\n"
            f"      {{{escape_latex(item.get('institution', ''))}}}{{{escape_latex(item.get('location', ''))}}}\n"
            f"      {{{escape_latex(item.get('degree', ''))}}}{{{escape_latex(item.get('dates', ''))}}}"
        )
        if isinstance(item.get("coursework"), list) and item["coursework"]:
            courses = ", ".join(escape_latex(str(course)) for course in item["coursework"])
            block += f"\n        \\resumeItemListStart\n            \\resumeItem{{\\textbf{{Coursework:}} {courses}}}\n        \\resumeItemListEnd"
        blocks.append(block)
    return "\n\n".join(blocks)


def build_experience(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        bullets = "\n".join(f"            \\resumeItem{{{escape_latex(str(bullet))}}}" for bullet in item.get("bullets", []) if bullet) if isinstance(item.get("bullets"), list) else ""
        blocks.append(
            "    \\resumeSubheading\n"
            f"      {{{escape_latex(item.get('company', ''))}}}{{{escape_latex(item.get('dates', ''))}}}\n"
            f"      {{{escape_latex(item.get('role', ''))}}}{{{escape_latex(item.get('location', ''))}}}\n"
            "      \\resumeItemListStart\n"
            f"{bullets}\n"
            "      \\resumeItemListEnd"
        )
    return "\n\n".join(blocks)


def build_projects(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        context = f" \\emph{{$|$ {escape_latex(item.get('context', ''))}}}" if item.get("context") else ""
        bullets = "\n".join(f"            \\resumeItem{{{escape_latex(str(bullet))}}}" for bullet in item.get("bullets", []) if bullet) if isinstance(item.get("bullets"), list) else ""
        blocks.append(
            "    \\resumeProjectHeading\n"
            f"      {{\\textbf{{{escape_latex(item.get('name', ''))}}}{context}}}{{{escape_latex(item.get('dates', ''))}}}\n"
            "      \\resumeItemListStart\n"
            f"{bullets}\n"
            "      \\resumeItemListEnd"
        )
    return "\n\n".join(blocks)


def build_skills(categories: Any) -> str:
    if not isinstance(categories, list):
        return ""
    lines = []
    for item in categories:
        if not item:
            continue
        items = ", ".join(str(entry) for entry in item.get("items", [])) if isinstance(item.get("items"), list) else item.get("items", "")
        lines.append(f"        \\textbf{{{escape_latex(item.get('category', ''))}}}{{: {escape_latex(items)}}} \\\\")
    return "\n".join(line for line in lines if line)


def render_latex(template: str, payload: dict[str, Any]) -> str:
    email_url = sanitize_url(payload.get("email", {}).get("url", "") if isinstance(payload.get("email"), dict) else "")
    email_display = payload.get("email", {}).get("display") if isinstance(payload.get("email"), dict) else ""
    linkedin_url = sanitize_url(payload.get("linkedin", {}).get("url", "") if isinstance(payload.get("linkedin"), dict) else "")
    linkedin_display = payload.get("linkedin", {}).get("display") if isinstance(payload.get("linkedin"), dict) else ""
    github_url = sanitize_url(payload.get("github", {}).get("url", "") if isinstance(payload.get("github"), dict) else "")
    github_display = payload.get("github", {}).get("display") if isinstance(payload.get("github"), dict) else ""
    substitutions = {
        "NAME": escape_latex(payload.get("name", "")),
        "CONTACT_LINE": escape_latex(payload.get("contact_line", "")),
        "EMAIL_URL": email_url,
        "EMAIL_DISPLAY": escape_latex(email_display or email_url),
        "LINKEDIN_URL": linkedin_url,
        "LINKEDIN_DISPLAY": escape_latex(linkedin_display),
        "GITHUB_URL": github_url,
        "GITHUB_DISPLAY": escape_latex(github_display),
        "EDUCATION": build_education(payload.get("education")),
        "EXPERIENCE": build_experience(payload.get("experience")),
        "PROJECTS": build_projects(payload.get("projects")),
        "SKILLS": build_skills(payload.get("skills")),
    }
    output = template
    for key, value in substitutions.items():
        output = output.replace(f"{{{{{key}}}}}", value)
    unresolved = sorted(set(PLACEHOLDER_RE.findall(output)))
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {', '.join(unresolved)}")
    return output


def total_bullets(payload: dict[str, Any]) -> int:
    total = 0
    for section in ("experience", "projects"):
        total += sum(len(item.get("bullets", [])) for item in payload.get(section, []) if isinstance(item, dict) and isinstance(item.get("bullets"), list))
    return total


def render_file(input_path: str | Path, output_path: str | Path, *, template_name: str | None = None, template_path: str | Path | None = None) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    path = Path(template_path) if template_path else resolve_template("cv", template_name, format="tex", fallback=True)
    rendered = render_latex(path.read_text(encoding="utf-8"), payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return {
        "file": output.name,
        "path": str(output.resolve(strict=False)),
        "sizeKB": round(output.stat().st_size / 1024, 1),
        "counts": {
            "educationEntries": len(payload.get("education", [])),
            "experienceEntries": len(payload.get("experience", [])),
            "projectEntries": len(payload.get("projects", [])),
            "skillCategories": len(payload.get("skills", [])),
            "totalBullets": total_bullets(payload),
        },
        "valid": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render structured CV JSON to LaTeX.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--template")
    args = parser.parse_args(argv)
    print(json.dumps(render_file(args.input, args.output, template_name=args.template), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
