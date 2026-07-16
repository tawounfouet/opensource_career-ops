#!/usr/bin/env python3
"""Générateur de CV — point d'entrée CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from models import CVData
from renderer import Renderer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Génère un CV HTML et PDF à partir de données structurées."
    )
    p.add_argument(
        "-d", "--data",
        default="data/audrey.json",
        help="Chemin vers le fichier JSON du CV (défaut : data/audrey.json)",
    )
    p.add_argument(
        "-t", "--theme",
        default="biomedical",
        help="Nom du thème à utiliser (défaut : biomedical)",
    )
    p.add_argument(
        "-o", "--output",
        default=None,
        help="Préfixe du fichier de sortie (défaut : output/cv-{name})",
    )
    p.add_argument(
        "--html-only",
        action="store_true",
        help="Ne générer que le HTML, pas le PDF",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Erreur : fichier introuvable — {data_path}", file=sys.stderr)
        sys.exit(1)

    cv = CVData.from_file(data_path)
    ctx = cv.to_template_context()

    base_dir = Path(__file__).parent
    renderer = Renderer(
        templates_dir=base_dir / "templates",
        static_dir=base_dir / "static",
        themes_dir=base_dir / "themes",
    )

    html = renderer.render_html(ctx, theme_name=args.theme)

    slug = cv.identity.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
    out_dir = base_dir / "output"
    out_dir.mkdir(exist_ok=True)

    html_path = out_dir / f"cv-{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"✓ HTML → {html_path}")

    if not args.html_only:
        pdf_path = out_dir / f"cv-{slug}.pdf"
        renderer.render_pdf(html, pdf_path)
        print(f"✓ PDF  → {pdf_path}")


if __name__ == "__main__":
    main()
