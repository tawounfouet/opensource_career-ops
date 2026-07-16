#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from html import escape as html_escape
from pathlib import Path
from typing import Any, Callable

from scripts.python import OUTPUT_DIR, PROJECT_ROOT, TEMPLATES_DIR
from scripts.python.cv.generate_pdf import render_html_to_pdf
from scripts.python.cv.templates import resolve_template


OUTPUT_ROOT = OUTPUT_DIR
TOKEN_RE = re.compile(r"\{\{[A-Z_]+\}\}")


def safe_output_path(raw: str, *, output_root: str | Path = OUTPUT_ROOT) -> Path:
    filename = Path(str(raw)).name
    filename = re.sub(r"[^a-zA-Z0-9._-]", "-", filename)
    filename = re.sub(r"\.{2,}", "-", filename)
    return Path(output_root) / filename


def require_fields(obj: Any, keys: list[str], context: str) -> None:
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            raise ValueError(f"Missing required field: {context}.{key}")


def escape_html(text: Any) -> str:
    return html_escape(str(text) if text else "", quote=True).replace("&#x27;", "&#39;")


def as_url(value: str) -> str:
    return value if re.match(r"^https?://", value, flags=re.I) else f"https://{value}"


def build_contact_line(candidate: dict[str, Any]) -> str:
    parts: list[str] = []
    if candidate.get("location"):
        parts.append(escape_html(candidate["location"]))
    if candidate.get("email"):
        email = escape_html(candidate["email"])
        parts.append(f'<a href="mailto:{email}">{email}</a>')
    if candidate.get("phone"):
        parts.append(escape_html(candidate["phone"]))
    if candidate.get("linkedin"):
        parts.append(f'<a href="{escape_html(as_url(str(candidate["linkedin"])))}">LinkedIn</a>')
    if candidate.get("github"):
        display = re.sub(r"^https?://", "", str(candidate["github"]))
        parts.append(f'<a href="{escape_html(as_url(str(candidate["github"])))}">{escape_html(display)}</a>')
    return " &nbsp;|&nbsp; ".join(parts)


def build_credentials_block(candidate: dict[str, Any]) -> str:
    credentials = candidate.get("credentials")
    if not isinstance(credentials, list) or not credentials:
        return ""
    return '<div class="credentials">' + " &nbsp;|&nbsp; ".join(escape_html(item) for item in credentials) + "</div>"


def build_dateline(letter: dict[str, Any]) -> str:
    return " &nbsp;&nbsp; ".join(escape_html(item) for item in [letter.get("company"), letter.get("city"), letter.get("date")] if item)


def build_achievements_block(achievements: Any) -> str:
    if not isinstance(achievements, list) or not achievements:
        return ""
    items = []
    for achievement in achievements:
        achievement = achievement if isinstance(achievement, dict) else {}
        lead = escape_html(achievement.get("lead", ""))
        impact = escape_html(achievement.get("impact", ""))
        items.append(f"    <li><b>{lead},</b> {impact}</li>")
    return "<ul class=\"achievements\">\n" + "\n".join(items) + "\n  </ul>"


def build_footnotes_block(footnotes: Any) -> str:
    if not isinstance(footnotes, list) or not footnotes:
        return ""
    lines = []
    for footnote in footnotes:
        if isinstance(footnote, dict):
            marker = escape_html(footnote.get("marker", ""))
            text = escape_html(footnote.get("text", ""))
            url = f' <a href="{escape_html(footnote["url"])}">{escape_html(footnote["url"])}</a>' if footnote.get("url") else ""
            lines.append(f"    <p>{marker} {text}{url}</p>")
        else:
            lines.append(f"    <p>{escape_html(footnote)}</p>")
    return "<div class=\"footnotes\">\n" + "\n".join(lines) + "\n  </div>"


def resolve_cover_template_path(payload: dict[str, Any] | None = None, **opts: Any) -> Path:
    payload = payload or {}
    base = TEMPLATES_DIR / "cover-letter-template.html"
    try:
        return resolve_template("cover", payload.get("template"), format="html", fallback=True, **opts)
    except Exception:
        return base


def build_html(payload: dict[str, Any], template_path: str | Path | None = None) -> str:
    require_fields(payload, ["candidate", "letter"], "payload")
    candidate = payload["candidate"]
    letter = payload["letter"]
    require_fields(candidate, ["name"], "candidate")
    require_fields(letter, ["role_title", "opening", "profile_intro"], "letter")
    resolved = Path(template_path) if template_path else resolve_cover_template_path(payload)
    html = resolved.read_text(encoding="utf-8")

    greeting = f'<p class="greeting">{escape_html(letter["greeting"])}</p>' if letter.get("greeting") else ""
    closing = f"<p>{escape_html(letter['closing'])}</p>" if letter.get("closing") else ""
    language_closing = f'<p class="language-closing">{escape_html(letter["language_closing"])}</p>' if letter.get("language_closing") else ""
    problems = f"<p>{escape_html(letter['problems_section'])}</p>" if letter.get("problems_section") else ""
    replacements = {
        "{{NAME}}": escape_html(candidate["name"]),
        "{{CONTACT_LINE}}": build_contact_line(candidate),
        "{{CREDENTIALS_BLOCK}}": build_credentials_block(candidate),
        "{{ROLE_TITLE}}": escape_html(letter["role_title"]),
        "{{DATELINE}}": build_dateline(letter),
        "{{GREETING_BLOCK}}": greeting,
        "{{OPENING}}": escape_html(letter["opening"]),
        "{{PROFILE_INTRO}}": escape_html(letter["profile_intro"]),
        "{{ACHIEVEMENTS_BLOCK}}": build_achievements_block(letter.get("achievements")),
        "{{PROBLEMS_BLOCK}}": problems,
        "{{CLOSING_BLOCK}}": closing,
        "{{LANGUAGE_CLOSING_BLOCK}}": language_closing,
        "{{FOOTNOTES_BLOCK}}": build_footnotes_block(letter.get("footnotes")),
    }
    return TOKEN_RE.sub(lambda match: replacements.get(match.group(0), match.group(0)), html)


def default_output_path(payload: dict[str, Any], *, output_root: str | Path = OUTPUT_ROOT) -> Path:
    letter = payload.get("letter") if isinstance(payload.get("letter"), dict) else {}
    company = re.sub(r"[^a-z0-9]+", "-", str(letter.get("company") or "company").lower()).strip("-")
    role = re.sub(r"[^a-z0-9]+", "-", str(letter.get("role_title") or "role").lower()).strip("-")[:30]
    return Path(output_root) / f"{company or 'company'}-{role or 'role'}-cover.pdf"


def generate_cover_letter_pdf(
    payload: dict[str, Any],
    *,
    out: str | Path | None = None,
    template_path: str | Path | None = None,
    renderer: Callable[..., dict[str, Any]] = render_html_to_pdf,
    root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    if out:
        output_path = safe_output_path(str(out), output_root=Path(root) / "output")
    elif payload.get("output_path"):
        output_path = safe_output_path(str(payload["output_path"]), output_root=Path(root) / "output")
    else:
        output_path = default_output_path(payload, output_root=Path(root) / "output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(payload, template_path=template_path)
    result = renderer(html, output_path.resolve(strict=False), format="a4", root=root)
    return {"output_path": str(output_path), "render": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a cover letter payload to PDF.")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    payload_path = Path(args.payload)
    if not payload_path.exists():
        print(f"ERROR: payload file not found: {payload_path.resolve(strict=False)}")
        return 1
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        result = generate_cover_letter_pdf(payload, out=args.out)
    except Exception as error:
        print("ERROR generating cover letter PDF:")
        print(error)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
