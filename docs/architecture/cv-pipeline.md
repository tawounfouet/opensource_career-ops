# Plan — Pipeline Skills Portfolio → CV Parfait

## État des lieux

### Modèles de données existants (7)

| Modèle | Champs clés | Statut CV |
|--------|-------------|-----------|
| `SkillExperience` | title, type, organization, start/end_date, location, description, missions[], responsibilities[], deliverables[], outcomes[], tools[] | ✅ Données riches, pas de rendu CV |
| `SkillCompetency` | label, formulation, category, mastery_level, confidence, status, market_keywords[], tags[], evidence M2M, experiences M2M | ✅ Prêt, pas d'assemblage sections |
| `SkillEvidence` | type, title, description, url, metric, source_experience FK | ✅ Preuves liées, pas de formatage CV |
| `Education` | title, institution, education_type, status, start/end_date, credential_url, hours, competencies M2M | ✅ Données complètes, pas de rendu CV |
| `EducationCompetency` | education FK, competency FK, relevance | ✅ Lien éducation-compétence |
| `SkillDevelopmentAction` | competency FK, target_level, actions[], resources[], deadline | ⚠️ Pourrait alimenter section "Formation continue" |
| `SkillExtractionRun` | audit LLM | ℹ️ Métadonnées, pas de CV |

### Services LLM existants (14)

| Service | Retourne | Utilisé pour CV ? |
|---------|----------|-------------------|
| `extract_from_experience` | competences[] | ✅ Alimente le pipeline |
| `formalize_competency` | formulation | ✅ Texte CV-ready |
| `suggest_cv_bullets` | bullets[{competency_label, bullet, evidence_used}] | ⚠️ Retourne du JSON, jamais injecté dans un CV |
| `suggest_interview_questions` | questions[] | ❌ Pas directement CV |
| `benchmark_summary` | fit_score, gaps, cv_recommendations | ⚠️ Recommandations CV non appliquées |
| `generate_discovery_profile` | target_titles, keywords | ❌ Pour le scan, pas le CV |
| `extract_education_from_text` | educations[] | ✅ Données CV |
| `extract_experiences_from_text` | experiences[] | ✅ Données CV |

### Export existant

| Format | Fonction | Couverture |
|--------|----------|------------|
| JSON portfolio | `export_to_json()` | Expériences + compétences + preuves (pas education) |
| Markdown skills | `export_to_markdown()` | Compétences groupées par catégorie (pas experiences/education) |
| Integration validated | `get_validated_competencies()` | Compétences validées formatées pour modules externes |

### CV Generator existant (`packages/cv-generator/`)

Modèle Pydantic `CVData` attendu :
```
CVData
├── identity: {name, title, objective, email, phone, location, mobility, linkedin, ...}
├── experiences: [{start, end, role, organization, location, missions[]}]
├── education: [{year, institution, location, degree, field}]
├── projects: [{year, title}]
├── languages: [{language, level, note}]
├── regulations: [str]
├── hard_skills: [str]
├── soft_skills: [str]
└── interests: [str]
```

---

## Ce qui manque — 6 gaps prioritaires

### Gap 1 : Pont Skills → CVData (CRITIQUE)

**Problème :** Aucune fonction ne convertit les modèles portfolio en `CVData` pour le cv-generator.

**Solution :** Service `export_to_cvdata()` dans `exports.py` qui :
- Mappe `SkillExperience` → `CVData.experiences` (start/end → dates, title → role, missions+deliverables+outcomes → missions[])
- Mappe `Education` → `CVData.education` (title → degree+field, institution → institution, dates → year)
- Mappe `SkillCompetency(status=validated)` → `CVData.hard_skills` + `CVData.soft_skills` (label ou formulation)
- Mappe les compétences `soft_skill` → `CVData.soft_skills`
- Mappe les compétences `knowledge` → `CVData.hard_skills` (ou section séparée)
- Laisse `identity`, `languages`, `interests`, `regulations` à compléter via `config/profile.yml` ou entrée manuelle

**Fichier :** `backend/apps/skills_portfolio/services/exports.py`
**Endpoint :** `GET /api/skills/export/cvdata` → retourne le JSON `CVData`
**Proxy :** Ajouter dans `route.ts`

### Gap 2 : Sections CV formatées (Education + Experience)

**Problème :** Les modèles Education et Experience ont les données mais rien ne les formate en sections CV markdown.

**Solution :** Fonctions dans `exports.py` :

```python
def format_experience_section(experiences) -> str:
    """Render experiences as CV markdown section.
    Format: **Role** — Organization
    *Start → End* · Location
    - Mission 1
    - Mission 2
    """

def format_education_section(educations) -> str:
    """Render education as CV markdown section.
    Format: **Degree — Field**
    Institution · Year
    """

def format_skills_section(competencies) -> str:
    """Render validated competencies grouped by category.
    Format: ## Savoir-faire
    - Label (Mastery)
    """
```

**Fichier :** `backend/apps/skills_portfolio/services/exports.py`

### Gap 3 : Génération cv.md complet depuis le portfolio

**Problème :** Pas de fonction qui assemble tout en un `cv.md` markdown structuré.

**Solution :** Fonction `generate_cv_markdown()` qui assemble :
1. En-tête (identité depuis `config/profile.yml`)
2. Summary (depuis les compétences validées + narrative)
3. Expériences (formatées avec bullets)
4. Education (formatée)
5. Compétences (groupées par catégorie)
6. Centres d'intérêts (depuis `config/profile.yml` ou saisie manuelle)
7. Langues (depuis `config/profile.yml`)

**Endpoint :** `GET /api/skills/export/cv-markdown` → retourne le markdown
**Action frontend :** Bouton "Générer cv.md" qui écrit le fichier

### Gap 4 : Bouton "Générer CV" frontend

**Problème :** Pas de flow UI "compétences validées → CV PDF".

**Solution :** Sur `skills-portfolio-view.tsx`, ajouter un panneau "Génération CV" avec :
- Bouton "Générer cv.md" → appelle `/api/skills/export/cv-markdown`, propose le téléchargement
- Bouton "Générer PDF" → appelle `/api/skills/export/cvdata`, puis lance le cv-generator
- Preview du CV en temps réel

**Fichier :** `web/src/components/skills/skills-portfolio-view.tsx`

### Gap 5 : Pont Discovery → portals.yml

**Problème :** Les keywords discovery restent dans le JSON, jamais injectés dans `portals.yml`.

**Solution :** Endpoint `POST /api/skills/integration/apply-discovery` qui :
1. Lit le profil discovery existant
2. Merge les `positive_keywords` + `tools` dans `portals.yml` → `title_filter.positive`
3. Retourne le diff

**Fichier :** `backend/apps/skills_portfolio/services/integration.py`
**Endpoint :** `POST /api/skills/integration/apply-discovery`

### Gap 6 : Modèles manquants pour CV parfait

**Champs à ajouter au modèle ou à `config/profile.yml` :**

| Champ | Où | Priorité |
|-------|-----|----------|
| `interests[]` | `config/profile.yml` ou nouveau modèle | Haute — CV demande centres d'intérêt |
| `languages[]` | `config/profile.yml` ou nouveau modèle | Haute — CV demande langues |
| `regulations[]` | `config/profile.yml` | Moyenne — utile pour CV réglementaire |
| `objective` (headline) | `config/profile.yml` → `narrative.headline` | Haute — résumé du CV |
| `photo` | `config/profile.yml` | Basse — optionnel |

---

## Ordre d'implémentation recommandé

1. **Gap 6** — Ajouter `interests`, `languages`, `objective` à `config/profile.yml` (5 min)
2. **Gap 2** — Fonctions de formatage sections CV dans `exports.py` (30 min)
3. **Gap 1** — Service `export_to_cvdata()` + endpoint (30 min)
4. **Gap 3** — Fonction `generate_cv_markdown()` + endpoint (30 min)
5. **Gap 4** — Bouton frontend "Générer CV" (30 min)
6. **Gap 5** — Pont Discovery → portals.yml (15 min)

**Total estimé : ~2.5h**

---

## Architecture cible

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                 │
│                                                     │
│  skills-portfolio-view.tsx                           │
│  ├── [Générer cv.md] → /api/skills/export/cv-markdown│
│  ├── [Générer PDF]   → /api/skills/export/cvdata     │
│  └── [Apply Discovery] → /api/skills/integration/... │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Django API (skills_portfolio)            │
│                                                     │
│  exports.py                                          │
│  ├── export_to_cvdata() → CVData JSON                │
│  ├── generate_cv_markdown() → cv.md string           │
│  ├── format_experience_section() → markdown          │
│  ├── format_education_section() → markdown           │
│  └── format_skills_section() → markdown              │
│                                                     │
│  integration.py                                      │
│  └── apply_discovery_to_portals() → diff             │
│                                                     │
│  config/profile.yml (read-only)                      │
│  ├── identity, languages, interests, objective       │
│  └── narrative.headline                              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│            packages/cv-generator/                     │
│                                                     │
│  CVData → Jinja2 template → HTML → Playwright → PDF │
└─────────────────────────────────────────────────────┘
```

---

## Notes d'implémentation

### Centres d'intérêts
Le CV generator a déjà un champ `interests: list[str]`. Il faut :
- Soit un champ `interests` dans `config/profile.yml`
- Soit un modèle `SkillInterest` dans le portfolio
- Recommandation : `config/profile.yml` (c'est du data personnelle, pas du system)

### Langues
Le CV generator a `languages: [{language, level, note}]`. Même logique :
- Champ `languages` dans `config/profile.yml`
- Le format existant dans le CV d'Audrey : "Français : langue maternelle", "Anglais : B2"

### Soft skills vs Hard skills
Le modèle `SkillCompetency` a déjà `category: knowledge|hard_skill|soft_skill`. Le mapping est direct :
- `hard_skill` + `knowledge` → `CVData.hard_skills`
- `soft_skill` → `CVData.soft_skills`

### Réglementations
Le CV d'Audrey liste des normes (ISO 13485, MDSAP, etc.). Ces données peuvent venir :
- D'un champ `regulations` dans `config/profile.yml`
- Ou être extraites des compétences de type `knowledge` liées à la réglementation
