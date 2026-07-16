# Session: CV Generator — Création du pipeline complet

**Date**: 2026-07-14
**Duration**: ~45 minutes
**Agent(s)**: opencode (big-pickle)
**Phase**: build

---

## Intent

Créer un générateur de CV Python complet capable de transformer des données JSON structurées en HTML et PDF avec un design biomédical professionnel, basé sur un CV Canva existant (Audrey Kwekeu).

## Outcome

Pipeline fonctionnel : `data/audrey.json` → `renderer.py` (Jinja2 + Playwright) → `output/cv-audrey-kwekeu.html` + `.pdf`. Design system complet avec sidebar cyan, gradient banner, icônes SVG inline, timeline accent, et QR code base64.

---

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| 1 | CSS inline dans le HTML au lieu de `<link>` | Playwright `set_content()` ne résout pas les chemins fichiers relatifs | `<link href="static/css/cv.css">` (échoué) |
| 2 | `Markup()` pour le CSS inline | Jinja2 `autoescape=True` convertissait `"` en `&#34;` cassant `content: "•"` des puces | `| safe` seul (insuffisant sans Markup côté renderer) |
| 3 | QR code en base64 data URI | Même problème que le CSS — Playwright ne résout pas les images fichiers | `<img src="static/images/...">` (échoué) |
| 4 | `linkedin_qr: "images/linkedin-qr.png"` (relatif à static/) | `load_image_as_data_uri()` préfixe déjà avec `self.static_dir` — `static/images/...` doublait en `static/static/images/...` | Chemin absolu depuis la racine |
| 5 | Icônes SVG inline au lieu d'emoji | Rendu PDF constant quel OS, meilleure scalabilité | Unicode emoji `✉ ☎ ● ⚑ 🚗` (variable) |
| 6 | Border-left + dot accent sur les expériences | Hiérarchie visuelle plus forte pour le scan rapide du recruteur | Séparateurs horizontaux simples |
| 7 | Gradient sur le bandeau identité | Impact visuel immédiat, look premium | Fond uni `#B2D5E8` |

## Files Created

| File | Purpose |
|---|---|
| `packages/cv-generator/data/audrey.json` | Données structurées du CV Audrey Kwekeu (identité, 4 expériences, 4 formations, 3 projets, langues, skills, réglementations) |
| `packages/cv-generator/themes/biomedical.json` | Design system complet (palette, typo Inter 4 weights, spacing, composants, rules) |
| `packages/cv-generator/templates/cv.html.jinja` | Template Jinja2 — layout 2 colonnes, icônes SVG, QR wrapper |
| `packages/cv-generator/static/css/cv.css` | CSS fidèle au design Canva original + améliorations (gradient, border-left, accent dots, SVG icons, print optimize) |
| `packages/cv-generator/static/images/linkedin-qr.png` | QR code LinkedIn (base64 inline au rendu) |
| `packages/cv-generator/models.py` | Dataclasses Pydantic : CVData, Identity, Experience, Education, Project, Language |
| `packages/cv-generator/renderer.py` | Moteur : Jinja2 → HTML (CSS inline, images base64) → PDF (Playwright Chromium) |
| `packages/cv-generator/main.py` | CLI : `python main.py --data data/audrey.json --theme biomedical` |
| `packages/cv-generator/requirements.txt` | pydantic>=2.0, jinja2>=3.1, playwright>=1.40 |
| `packages/cv-generator/output/cv-audrey-kwekeu.html` | HTML final auto-contenu (36K) |
| `packages/cv-generator/output/cv-audrey-kwekeu.pdf` | PDF final (234K) |

## Files Modified

| File | Change summary |
|---|---|
| `packages/cv-generator/static/css/cv.css` | Réécrit 3 fois : (1) CSS initial, (2) fix puces, (3) redesign complet avec gradients, border-left, SVG icons, accent dots, print optimize |
| `packages/cv-generator/templates/cv.html.jinja` | Réécrit 2 fois : (1) inline CSS, (2) SVG icons + QR wrapper + sidebar-bullet class |
| `packages/cv-generator/renderer.py` | Ajout `load_image_as_data_uri()`, `Markup()` pour CSS, import `base64` + `markupsafe` |
| `packages/cv-generator/data/audrey.json` | Missions corrigées avec textes complets fournis par l'utilisateur |
| `packages/cv-generator/themes/biomedical.json` | Étendu : 4 weights, accent colors, component tokens, icon rules |

---

## Key Context

- Le CV de référence est un Canva PDF avec sidebar cyan `#0CC0DF`, bandeau bleu clair `#B2D5E8`, police Inter
- Layout : sidebar 29% / main 71%, A4 portrait
- L'utilisateur a fourni les textes exacts des 4 expériences professionnelles
- Le JSON `audrey.json` est la source de vérité pour les données
- Le thème `biomedical.json` est interchangeable avec d'autres thèmes futurs
- Le pipeline supporte HTML-only (`--html-only`) ou HTML+PDF

## Commands Run

| Command | Purpose | Result |
|---|---|---|
| `python3 -m venv .venv` | Créer un venv Python (Homebrew interdit pip system-wide) | Succès |
| `pip install -r requirements.txt` | Installer pydantic, jinja2, playwright | Succès |
| `playwright install chromium` | Installer Chromium pour le rendu PDF | Succès |
| `python main.py --data data/audrey.json --theme biomedical` | Générer HTML + PDF | Succès à chaque itération |

## Patterns Established

- **CSS inline** : toujours `Markup(css_inline)` + `{{ css_inline | safe }}` pour éviter l'autoescape Jinja2
- **Images inline** : toujours `data:image/{mime};base64,...` pour les PDF Playwright
- **Chemins dans JSON** : relatifs au dossier `static/` (ex: `images/linkedin-qr.png` pas `static/images/...`)
- **CLI** : argparse avec `--data`, `--theme`, `--html-only`, `-o` (output prefix)
- **Structure** : `data/` pour JSON input, `themes/` pour design tokens, `templates/` pour Jinja2, `static/` pour CSS/images/fonts, `output/` pour résultats

## Issues & Workarounds

| Issue | Workaround | Status |
|---|---|---|
| `pip install` échoue — externally-managed-environment (PEP 668) | `python3 -m venv .venv` | resolved |
| CSS non appliqué dans le HTML/PDF | CSS inline via `Markup()` dans renderer.py | resolved |
| Puces `•` invisibles | Jinja2 autoescape convertissait `"` → `&#34;` dans `content: "•"`. Fix : `Markup(css_inline)` | resolved |
| QR code invisible | Playwright ne résout pas les chemins fichiers. Fix : base64 data URI | resolved |
| `ImportError: cannot import name 'Markup' from 'jinja2'` | Markup déplacé dans `markupsafe` en Jinja2 récent. Fix : `from markupsafe import Markup` | resolved |
| `static/static/images/...` (double prefix) | Le JSON avait `static/images/linkedin-qr.png` mais le renderer préfixe déjà `static/`. Fix : chemin `images/linkedin-qr.png` | resolved |
| CSS grid invalide `80px 1px ffr` | Supprimé lors du redesign, remplacé par bloc simple | resolved |

---

## Action Items

- [ ] Tester le rendu PDF dans un vrai navigateur pour valider les couleurs et le QR code
- [ ] Ajouter d'autres thèmes (ex: `corporate.json`, `creative.json`)
- [ ] Supporter les langues multiples (i18n des labels de sections)
- [ ] Ajouter un mode `--watch` pour régénérer automatiquement
- [ ] Créer un thème dark mode pour le HTML web
- [ ] Ajouter des barres de progression pour les niveaux de langues
- [ ] Optimiser le PDF pour ATS (balises sémantiques)

---

## Full Conversation Summary

1. L'utilisateur a demandé de créer la structure `cv-generator/` dans `packages/` — tous les dossiers et fichiers vides créés
2. L'utilisateur a fourni le contenu structuré du CV (JSON + markdown) et la structure ASCII du PDF Canva original
3. L'utilisateur a fourni le design system complet (palette, typo, spacing, composants) extrait du Canva
4. Les fichiers de données et de thème ont été peuplés (`audrey.json`, `biomedical.json`)
5. Le CSS et le template Jinja2 ont été écrits pour reproduire le layout 2 colonnes
6. `models.py`, `renderer.py`, `main.py`, `requirements.txt` ont été créés
7. Le workflow complet a été exécuté avec succès (venv + pip + playwright + main.py)
8. **Bug CSS** : le CSS n'était pas appliqué → cause : autoescape Jinja2. Fix : `Markup()`
9. **Bug QR code** : image non visible → cause : chemin relatif + Playwright. Fix : base64 data URI
10. Les missions de `audrey.json` ont été mises à jour avec les textes exacts fournis par l'utilisateur
11. L'utilisateur a demandé des améliorations visuelles → redesign complet du CSS (gradients, border-left, accent dots, SVG icons, print optimize)
12. Session archivée

---

## Related Sessions

- Aucune session connexe pour l'instant
