#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from html import escape as html_escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.python import TEMPLATES_DIR


TEMPLATE_PATH = TEMPLATES_DIR / "cv-template.html"
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")
CONTACT_ROW_RE = re.compile(r'<div class="contact-row">[\s\S]*?</div>')
PAGE_WIDTHS = {"letter": "8.5in", "a4": "210mm"}
DEFAULT_SECTION_TITLES = {
    "summary": "Professional Summary",
    "competencies": "Core Competencies",
    "experience": "Work Experience",
    "projects": "Projects",
    "education": "Education",
    "certifications": "Certifications",
    "skills": "Skills",
}


def escape_html(text: Any) -> str:
    return html_escape(text if isinstance(text, str) else "", quote=True).replace("&#x27;", "&#39;")


def sanitize_url(url: Any) -> str:
    if not isinstance(url, str):
        return ""
    value = url.strip()
    if not value:
        return ""
    lower = value.lower()
    allowed = ("mailto:", "tel:", "http:", "https:")
    if not lower.startswith(allowed):
        if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I):
            return ""
        value = f"mailto:{value}" if "@" in value and "/" not in value else f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme not in {"mailto", "tel", "http", "https"}:
        return ""
    return escape_html(value)


def join_items(items: Any) -> str:
    if isinstance(items, list):
        return ", ".join(str(item) for item in items)
    return items if isinstance(items, str) else ""


def build_competencies(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    return "\n      ".join(f'<span class="competency-tag">{escape_html(str(tag))}</span>' for tag in entries if tag)


def build_experience(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        bullets = "\n".join(f"        <li>{escape_html(str(bullet))}</li>" for bullet in item.get("bullets", []) if bullet) if isinstance(item.get("bullets"), list) else ""
        location = f'\n    <div class="job-location">{escape_html(item.get("location", ""))}</div>' if item.get("location") else ""
        blocks.append(
            f"""<div class="job">
    <div class="job-header">
      <span class="job-company">{escape_html(item.get("company", ""))}</span>
      <span class="job-period">{escape_html(item.get("dates") or item.get("period") or "")}</span>
    </div>
    <div class="job-role">{escape_html(item.get("role", ""))}</div>{location}
    <ul>
{bullets}
    </ul>
  </div>"""
        )
    return "\n  ".join(blocks)


def build_projects(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        badge = f'<span class="project-badge">{escape_html(item.get("badge", ""))}</span>' if item.get("badge") else ""
        desc_text = item.get("description") or (" ".join(str(b) for b in item.get("bullets", []) if b) if isinstance(item.get("bullets"), list) else "")
        desc = f'\n    <div class="project-desc">{escape_html(desc_text)}</div>' if desc_text else ""
        tech = f'\n    <div class="project-tech">{escape_html(item.get("tech", ""))}</div>' if item.get("tech") else ""
        blocks.append(f"""<div class="project">
    <div class="project-title">{escape_html(item.get("name", ""))}{badge}</div>{desc}{tech}
  </div>""")
    return "\n  ".join(blocks)


def build_education(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        org = f' <span class="edu-org">{escape_html(item.get("org", ""))}</span>' if item.get("org") else ""
        desc = f'\n    <div class="edu-desc">{escape_html(item.get("description", ""))}</div>' if item.get("description") else ""
        blocks.append(f"""<div class="edu-item">
    <div class="edu-header">
      <div class="edu-title">{escape_html(item.get("title", ""))}{org}</div>
      <div class="edu-year">{escape_html(item.get("year", ""))}</div>
    </div>{desc}
  </div>""")
    return "\n  ".join(blocks)


def build_certifications(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    blocks = []
    for item in entries:
        if not item:
            continue
        org = f'<span class="cert-org">{escape_html(item.get("org", ""))}</span>' if item.get("org") else '<span class="cert-org"></span>'
        year = f'<span class="cert-year">{escape_html(item.get("year", ""))}</span>' if item.get("year") else '<span class="cert-year"></span>'
        blocks.append(f"""<div class="cert-item">
      <span class="cert-title">{escape_html(item.get("title", ""))}</span>
      {org}
      {year}
    </div>""")
    return "\n    ".join(blocks)


def build_skills(categories: Any) -> str:
    if not isinstance(categories, list):
        return ""
    items = []
    for category in categories:
        if not category:
            continue
        label = f'<span class="skill-category">{escape_html(category.get("category", ""))}:</span> ' if category.get("category") else ""
        items.append(f'    <div class="skill-item">{label}{escape_html(join_items(category.get("items")))}</div>')
    return f"""<div class="skills-grid">
{chr(10).join(items)}
  </div>""" if items else ""


def build_contact_row(candidate: dict[str, Any] | None) -> str:
    c = candidate or {}
    items = []
    if c.get("phone"):
        tel = sanitize_url("tel:" + re.sub(r"\s+", "", str(c["phone"])))
        items.append(f'<a href="{tel}">{escape_html(c["phone"])}</a>')
    if c.get("email"):
        items.append(f'<a href="{sanitize_url("mailto:" + str(c["email"]))}">{escape_html(c["email"])}</a>')
    if isinstance(c.get("linkedin"), dict) and c["linkedin"].get("url"):
        items.append(f'<a href="{sanitize_url(c["linkedin"]["url"])}">{escape_html(c["linkedin"].get("display") or c["linkedin"]["url"])}</a>')
    if isinstance(c.get("portfolio"), dict) and c["portfolio"].get("url"):
        items.append(f'<a href="{sanitize_url(c["portfolio"]["url"])}">{escape_html(c["portfolio"].get("display") or c["portfolio"]["url"])}</a>')
    if c.get("location"):
        items.append(f"<span>{escape_html(c['location'])}</span>")
    sep = '\n      <span class="separator">|</span>\n      '
    return f'<div class="contact-row">\n      {sep.join(items)}\n    </div>'


def build_photo(candidate: dict[str, Any] | None, name: str = "") -> str:
    photo = (candidate or {}).get("photo")
    return f'<img class="cv-photo" src="{sanitize_url(photo)}" alt="{escape_html(name)}">' if photo else ""


def render_report(payload: dict[str, Any]) -> dict[str, Any]:
    section_titles = {**DEFAULT_SECTION_TITLES, **(payload.get("sections") if isinstance(payload.get("sections"), dict) else {})}
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    substitutions = {
        "LANG": escape_html(payload.get("lang") or "en"),
        "PAGE_WIDTH": PAGE_WIDTHS.get(payload.get("page_format"), PAGE_WIDTHS["letter"]),
        "NAME": escape_html(candidate.get("name", "")),
        "SECTION_SUMMARY": escape_html(section_titles["summary"]),
        "SUMMARY_TEXT": escape_html(payload.get("summary", "")),
        "SECTION_COMPETENCIES": escape_html(section_titles["competencies"]),
        "COMPETENCIES": build_competencies(payload.get("competencies")),
        "SECTION_EXPERIENCE": escape_html(section_titles["experience"]),
        "EXPERIENCE": build_experience(payload.get("experience")),
        "SECTION_PROJECTS": escape_html(section_titles["projects"]),
        "PROJECTS": build_projects(payload.get("projects")),
        "SECTION_EDUCATION": escape_html(section_titles["education"]),
        "EDUCATION": build_education(payload.get("education")),
        "SECTION_CERTIFICATIONS": escape_html(section_titles["certifications"]),
        "CERTIFICATIONS": build_certifications(payload.get("certifications")),
        "SECTION_SKILLS": escape_html(section_titles["skills"]),
        "SKILLS": build_skills(payload.get("skills")),
    }
    return {"substitutions": substitutions, "candidate": candidate}


def render_html(template: str, payload: dict[str, Any]) -> str:
    report = render_report(payload)
    candidate = report["candidate"]
    html = CONTACT_ROW_RE.sub(lambda _m: build_contact_row(candidate), template)
    html = html.replace("{{PHOTO}}", build_photo(candidate, candidate.get("name", "")))
    for key, value in report["substitutions"].items():
        html = html.replace(f"{{{{{key}}}}}", value)
    unresolved = sorted(set(PLACEHOLDER_RE.findall(html)))
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {', '.join(unresolved)}")
    return html


def count_bullets(payload: dict[str, Any]) -> int:
    return sum(len(item.get("bullets", [])) for item in payload.get("experience", []) if isinstance(item, dict) and isinstance(item.get("bullets"), list))


def render_file(input_path: str | Path, output_path: str | Path, template_path: str | Path = TEMPLATE_PATH) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    html = render_html(Path(template_path).read_text(encoding="utf-8"), payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return {
        "file": output.name,
        "path": str(output.resolve(strict=False)),
        "sizeKB": round(output.stat().st_size / 1024, 1),
        "counts": {
            "competencies": len(payload.get("competencies", [])),
            "experienceEntries": len(payload.get("experience", [])),
            "projectEntries": len(payload.get("projects", [])),
            "educationEntries": len(payload.get("education", [])),
            "certificationEntries": len(payload.get("certifications", [])),
            "skillCategories": len(payload.get("skills", [])),
            "totalBullets": count_bullets(payload),
        },
        "valid": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render structured CV JSON to HTML.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("template", nargs="?", default=str(TEMPLATE_PATH))
    args = parser.parse_args(argv)
    print(json.dumps(render_file(args.input, args.output, args.template), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
