from __future__ import annotations

import base64
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup


class Renderer:
    """Moteur de rendu : Jinja2 → HTML → PDF."""

    def __init__(
        self,
        templates_dir: str | Path = "templates",
        static_dir: str | Path = "static",
        themes_dir: str | Path = "themes",
    ):
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.themes_dir = Path(themes_dir)

        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )

    def load_theme(self, theme_name: str) -> dict:
        theme_path = self.themes_dir / f"{theme_name}.json"
        if not theme_path.exists():
            raise FileNotFoundError(f"Thème introuvable : {theme_path}")
        return json.loads(theme_path.read_text(encoding="utf-8"))

    def load_css(self) -> str:
        css_path = self.static_dir / "css" / "cv.css"
        if not css_path.exists():
            raise FileNotFoundError(f"CSS introuvable : {css_path}")
        return css_path.read_text(encoding="utf-8")

    def load_image_as_data_uri(self, relative_path: str) -> str:
        img_path = self.static_dir / relative_path
        if not img_path.exists():
            return ""
        suffix = img_path.suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml"}
        mime = mime_map.get(suffix, "image/png")
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def render_html(
        self,
        cv_data: dict,
        theme_name: str = "biomedical",
    ) -> str:
        template = self.env.get_template("cv.html.jinja")
        theme = self.load_theme(theme_name)
        css_inline = self.load_css()

        qr_rel = cv_data.get("identity", {}).get("linkedin_qr", "")
        qr_data_uri = self.load_image_as_data_uri(qr_rel) if qr_rel else ""

        context = {
            **cv_data,
            "lang": cv_data.get("meta", {}).get("lang", "fr"),
            "css_inline": Markup(css_inline),
            "qr_data_uri": qr_data_uri,
            "theme": theme,
        }
        return template.render(**context)

    def render_pdf(
        self,
        html_content: str,
        output_path: str | Path,
        css_paths: list[str | Path] | None = None,
    ) -> Path:
        """Convertit le HTML en PDF via Playwright."""
        from playwright.sync_api import sync_playwright

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")

            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()

        return output_path
