#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.python import PROJECT_ROOT


PDF_PAGE_MARGIN = "0.6in"
SECTION_ALIASES = {
    "summary": "summary",
    "professional summary": "summary",
    "competencies": "competencies",
    "core competencies": "competencies",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "projects": "projects",
    "selected projects": "projects",
    "personal projects": "projects",
    "education": "education",
    "education & certifications": "education",
    "certifications": "certifications",
    "skills": "skills",
    "technical skills": "skills",
}
FONT_MIME = {"woff2": "font/woff2", "woff": "font/woff", "otf": "font/otf", "ttf": "font/ttf"}


def normalize_text_for_ats(html: str) -> dict[str, Any]:
    replacements: dict[str, int] = {}

    def bump(key: str) -> None:
        replacements[key] = replacements.get(key, 0) + 1

    masks: list[str] = []

    def mask(match: re.Match[str]) -> str:
        token = f"\x00MASK{len(masks)}\x00"
        masks.append(match.group(0))
        return token

    masked = re.sub(r"<(style|script)\b[^>]*>[\s\S]*?</\1>", mask, html, flags=re.I)

    def sanitize_text(text: str) -> str:
        if not text:
            return text
        chars = {
            "\u2014": ("em-dash", "-"),
            "\u2013": ("en-dash", "-"),
            "\u2026": ("ellipsis", "..."),
            "\u00a0": ("nbsp", " "),
            "\u20ac": ("euro", "EUR "),
            "\u00a3": ("pound", "GBP "),
        }
        output = text
        for char, (key, value) in chars.items():
            output = re.sub(re.escape(char), lambda _m, k=key, v=value: lambda_value(k, v), output)
        output = re.sub(r"[\u201c\u201d\u201e\u201f]", lambda _m: lambda_value("smart-double-quote", '"'), output)
        output = re.sub(r"[\u2018\u2019\u201a\u201b]", lambda _m: lambda_value("smart-single-quote", "'"), output)
        output = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", lambda _m: lambda_value("zero-width", ""), output)
        output = re.sub(r"\s*\u2192\s*", lambda _m: lambda_value("right-arrow", " to "), output)
        output = re.sub(r"\s*\u2190\s*", lambda _m: lambda_value("left-arrow", " from "), output)
        output = re.sub(r"\s*[\u2191\u2193]\s*", lambda _m: lambda_value("vert-arrow", " "), output)
        output = re.sub(r"\s*\u00b7\s*", lambda _m: lambda_value("middot", " | "), output)
        output = re.sub(r"\s*\u2022\s*", lambda _m: lambda_value("bullet", " | "), output)
        output = re.sub(r"\*\*([^*]+?)\*\*", lambda m: lambda_value("markdown-bold", f"<strong>{m.group(1)}</strong>"), output)
        return output

    def lambda_value(key: str, value: str) -> str:
        bump(key)
        return value

    out = ""
    idx = 0
    while idx < len(masked):
        lt = masked.find("<", idx)
        if lt == -1:
            out += sanitize_text(masked[idx:])
            break
        out += sanitize_text(masked[idx:lt])
        gt = masked.find(">", lt)
        if gt == -1:
            out += masked[lt:]
            break
        out += masked[lt : gt + 1]
        idx = gt + 1

    def restore(match: re.Match[str]) -> str:
        return masks[int(match.group(1))]

    return {"html": re.sub(r"\x00MASK(\d+)\x00", restore, out), "replacements": replacements}


def normalize_section_title(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\{\{[^}]+\}\}", " ", text)
    text = text.replace("&amp;", "&")
    text = re.sub(r"[*_`~]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def section_key(text: str) -> str:
    normalized = normalize_section_title(text)
    return SECTION_ALIASES.get(normalized, normalized)


def extract_rendered_section_order(html: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    pattern = re.compile(r"class=[\"'][^\"']*\bsection-title\b[^\"']*[\"'][^>]*>([\s\S]*?)</[^>]+>", re.I)
    for match in pattern.finditer(html):
        title = normalize_section_title(match.group(1))
        if title:
            sections.append({"key": section_key(title), "title": title})
    return sections


def extract_source_section_order(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = normalize_section_title(match.group(2))
        if title:
            sections.append({"key": section_key(title), "title": title})
    return sections


def validate_cv_section_order(html: str, cv_markdown: str, *, allow_reorder: bool = False) -> None:
    rendered = extract_rendered_section_order(html)
    source = extract_source_section_order(cv_markdown)
    if len(rendered) < 2 or len(source) < 2:
        return
    positions = {section["key"]: idx for idx, section in enumerate(source)}
    comparable = [section for section in rendered if section["key"] in positions]
    if len(comparable) < 2:
        return
    for idx in range(1, len(comparable)):
        previous = comparable[idx - 1]
        current = comparable[idx]
        if positions[current["key"]] < positions[previous["key"]]:
            rendered_order = " -> ".join(section["title"] for section in comparable)
            source_order = " -> ".join(section["title"] for section in source if any(item["key"] == section["key"] for item in comparable))
            message = f"CV section order diverges from cv.md: rendered {rendered_order}; cv.md {source_order}"
            if allow_reorder:
                return
            raise ValueError(message)


def repo_relative_manifest_path(path_value: str | Path, *, root: str | Path = PROJECT_ROOT) -> str:
    if not path_value:
        return ""
    root_path = Path(root).resolve(strict=False)
    path = Path(path_value).resolve(strict=False)
    try:
        rel = path.relative_to(root_path)
    except ValueError:
        return ""
    return rel.as_posix()


def inject_print_page_css(html: str, format: str = "a4") -> str:
    page_size = "Letter" if str(format or "a4").lower() == "letter" else "A4"
    page_style = f'<style id="career-ops-page-setup">\n@page {{ size: {page_size}; margin: {PDF_PAGE_MARGIN}; }}\n</style>'
    if re.search(r"</head>", html, flags=re.I):
        return re.sub(r"</head>", page_style + "\n</head>", html, count=1, flags=re.I)
    if re.search(r"<html\b[^>]*>", html, flags=re.I):
        return re.sub(r"<html\b[^>]*>", lambda m: f"{m.group(0)}\n<head>\n{page_style}\n</head>", html, count=1, flags=re.I)
    return f"{page_style}\n{html}"


def update_pdf_manifest(
    report_num: str,
    pdf_path: str | Path,
    html_path: str | Path,
    format: str,
    *,
    root: str | Path = PROJECT_ROOT,
    today: str | None = None,
) -> str:
    project = Path(root).resolve(strict=False)
    manifest = project / "data" / "pdf-index.tsv"
    pdf = Path(pdf_path).resolve(strict=False)
    rel_pdf = pdf.relative_to(project).as_posix()
    rel_html = repo_relative_manifest_path(html_path, root=project)
    stamp = today or date.today().isoformat()

    def norm_key(value: str) -> str:
        return re.sub(r"^0+(?=\d)", "", (value or "").strip())

    lines: list[str] = []
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) > 1 and fields[1] == rel_pdf:
                continue
            if report_num and fields and norm_key(fields[0]) == norm_key(report_num):
                continue
            lines.append(line)
    lines.append("\t".join([report_num or "", rel_pdf, rel_html, format, stamp]))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "# report\tpdf\thtml\tformat\tdate — written by generate-pdf.py, do not edit\n"
        + "\n".join(lines)
        + "\n",
        encoding="utf-8",
    )
    return rel_pdf


def inline_local_fonts(html: str, *, fonts_dir: str | Path | None = None) -> str:
    root = Path(fonts_dir) if fonts_dir else PROJECT_ROOT / "fonts"
    pattern = re.compile(r"url\(\s*(['\"]?)\./fonts/([^'\")\s]+)\1\s*\)")
    data_urls: dict[str, str] = {}
    for name in sorted({match.group(2) for match in pattern.finditer(html)}):
        font_path = (root / name).resolve(strict=False)
        try:
            font_path.relative_to(root.resolve(strict=False))
        except ValueError:
            continue
        if not font_path.exists():
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        data = base64.b64encode(font_path.read_bytes()).decode("ascii")
        data_urls[name] = f"url('data:{FONT_MIME.get(ext, 'application/octet-stream')};base64,{data}')"
    return pattern.sub(lambda match: data_urls.get(match.group(2), match.group(0)), html)


def count_pdf_pages(pdf_bytes: bytes) -> int:
    text = pdf_bytes.decode("latin1", errors="ignore")
    return len(re.findall(r"/Type\s*/Page[^s]", text))


def default_launch_browser(_options: dict[str, Any]) -> Any:
    from playwright.sync_api import sync_playwright

    manager = sync_playwright().start()
    browser = manager.chromium.launch(headless=True)
    setattr(browser, "_career_ops_playwright_manager", manager)
    return browser


def render_html_to_pdf(
    html: str,
    output_path: str | Path,
    *,
    format: str = "a4",
    base_dir: str | Path | None = None,
    report_num: str = "",
    input_path: str | Path = "",
    launch_browser: Callable[[dict[str, Any]], Any] = default_launch_browser,
    root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    output = Path(output_path).resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir or Path.cwd()).resolve(strict=False)
    base.mkdir(parents=True, exist_ok=True)
    html = inject_print_page_css(html, format)
    html = inline_local_fonts(html, fonts_dir=Path(root) / "fonts")
    tmp = base / f".career-ops-render-{uuid.uuid4()}.html"
    browser = None
    try:
        tmp.write_text(html, encoding="utf-8")
        browser = launch_browser({"headless": True})
        page = browser.new_page() if hasattr(browser, "new_page") else browser.newPage()
        page.goto(tmp.as_uri(), wait_until="load")
        if hasattr(page, "evaluate"):
            page.evaluate("() => document.fonts.ready")
        pdf_bytes = page.pdf(print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}, prefer_css_page_size=True)
        output.write_bytes(pdf_bytes)
        page_count = count_pdf_pages(pdf_bytes)
        try:
            update_pdf_manifest(report_num, output, input_path, format, root=root)
        except Exception:
            pass
        return {"outputPath": str(output), "pageCount": page_count, "size": len(pdf_bytes)}
    finally:
        if browser is not None:
            try:
                browser.close()
            finally:
                manager = getattr(browser, "_career_ops_playwright_manager", None)
                if manager is not None:
                    manager.stop()
        tmp.unlink(missing_ok=True)


def generate_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    format: str = "a4",
    report_num: str = "",
    allow_reorder: bool = False,
    launch_browser: Callable[[dict[str, Any]], Any] = default_launch_browser,
    root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    if report_num and not re.match(r"^\d+$", report_num):
        raise ValueError(f'Invalid --report "{report_num}". Use the numeric tracker/report number, e.g. --report=018')
    normalized_format = format.lower()
    if normalized_format not in {"a4", "letter"}:
        raise ValueError(f'Invalid format "{format}". Use: a4, letter')
    project = Path(root).resolve(strict=False)
    output = Path(output_path).resolve(strict=False)
    try:
        output.relative_to(project)
    except ValueError as exc:
        raise ValueError(f"Refusing to write the PDF outside the project directory: {output}") from exc
    input_file = Path(input_path).resolve(strict=False)
    html = input_file.read_text(encoding="utf-8")
    cv_path = project / "cv.md"
    cv_markdown = cv_path.read_text(encoding="utf-8") if cv_path.exists() else ""
    validate_cv_section_order(html, cv_markdown, allow_reorder=allow_reorder)
    normalized = normalize_text_for_ats(html)
    return render_html_to_pdf(
        normalized["html"],
        output,
        format=normalized_format,
        base_dir=input_file.parent,
        report_num=report_num,
        input_path=input_file,
        launch_browser=launch_browser,
        root=project,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an HTML CV to PDF.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--format", default="a4", choices=["a4", "letter"])
    parser.add_argument("--report", default="")
    parser.add_argument("--allow-reorder", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = generate_pdf(args.input, args.output, format=args.format, report_num=args.report, allow_reorder=args.allow_reorder)
    except Exception as error:
        print(f"PDF generation failed: {error}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
