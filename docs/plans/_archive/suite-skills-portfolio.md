# Suite à implémenter — Skills Portfolio (après Codex V1)

> - **État actuel :** Phase 1 + partielle Phase 2 terminées. Modèles, API CRUD, admin, dashboard, validation avec gate preuve — tout fonctionne.
>
> - **Ce manque :** LLM, exports, pages dédiées, management commands, intégration career-ops, tests étendus.

---

## Table des matières

1. [Ce qui fonctionne déjà](#1-ce-qui-fonctionne-déjà)
2. [Phase 3 — Services LLM (priorité haute)](#2-phase-3--services-llm)
3. [Phase 2 complémentaire — UI avancée](#3-phase-2-complémentaire--ui-avancée)
4. [Phase 1 complémentaire — Export + Management commands](#4-phase-1-complémentaire--export--management-commands)
5. [Phase 5 — Benchmark + Development Plan](#5-phase-5--benchmark--development-plan)
6. [Phase 6 — Intégration career-ops](#6-phase-6--intégration-career-ops)
7. [Phase 7 — Multi-user + production](#7-phase-7--multi-user--production)
8. [Tests à ajouter](#8-tests-à-ajouter)
9. [Plan d'action par priorité](#9-plan-daction-par-priorité)

---

## 1. Ce qui fonctionne déjà

| Composant | Status |
|-----------|--------|
| 5 modèles Django (Experience, Competency, Evidence, DevelopmentAction, ExtractionRun) | ✅ |
| API CRUD complète (experiences, competencies, evidence) | ✅ |
| Dashboard API (counts, by_status, by_category) | ✅ |
| Validation avec gate preuve (reject sans preuve, accept avec preuve) | ✅ |
| Admin Django customisé (5 ModelAdmin) | ✅ |
| Proxy Next.js → Django (catch-all `/api/skills/[...path]`) | ✅ |
| Page `/skills` avec formulaire création inline | ✅ |
| Navigation sidebar avec badge "Beta" | ✅ |
| DATA_CONTRACT.md mis à jour | ✅ |
| Tests : 4 tests passent (dashboard, create, validate-gate, validate-ok, reject) | ✅ |

---

## 2. Phase 3 — Services LLM

**Priorité : HAUTE** — C'est le cœur de la valeur ajoutée du module.

### 2.1 `backend/apps/skills_portfolio/services/__init__.py`

Créer le package services :

```
backend/apps/skills_portfolio/services/
├── __init__.py
├── llm_client.py          # Client LLM unifié (OpenAI-compatible)
├── extraction.py           # Extraction de compétences depuis une expérience
├── prompting.py            # Templates de prompts JSON strict
├── validation.py           # Validation structurelle des réponses LLM
├── matching.py             # Benchmark compétences vs marché
└── exports.py              # Export JSON/Markdown
```

### 2.2 `llm_client.py` — Client LLM

```python
import os, httpx
from typing import AsyncGenerator

class LLMClient:
    """Client OpenAI-compatible — fonctionne avec OpenAI, Ollama, OpenRouter, Gemini."""

    def __init__(self):
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream(self, system: str, user: str) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": True,
                },
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
```

### 2.3 `extraction.py` — Extraction de compétences

```python
import json, hashlib
from apps.skills_portfolio.models import SkillCompetency, SkillExtractionRun

EXTRACTION_PROMPT = """Tu es un expert en capital humain. Analyse cette expérience professionnelle et extrais les COMPÉTENCES démontrées.

RÈGLES STRICTES:
- Chaque compétence doit être liée à un FAIT observable dans l'expérience
- Ne JAMAIS inventer de compétence non mentionnée
- Formule chaque compétence avec: action_verb + object + context (ex: "Concevoir des APIs REST pour un système de recrutement")
- Catégorie: hard_skill | soft_skill | domain_knowledge
- Niveau de maîtrise estimé: beginner | intermediate | advanced | expert
- Confiance: high (explicite) | medium (implicite) | low (inféré)

Retourne un JSON strict:
{
  "competencies": [
    {
      "label": "...",
      "formulation": "Je suis capable de...",
      "action_verb": "...",
      "object": "...",
      "context": "...",
      "category": "hard_skill|soft_skill|domain_knowledge",
      "mastery_level": "beginner|intermediate|advanced|expert",
      "confidence": "high|medium|low",
      "rationale": "pourquoi cette compétence est démontrée"
    }
  ]
}"""

async def extract_from_experience(client, experience) -> dict:
    """Extrait les compétences d'une expérience via LLM."""
    input_text = _format_experience(experience)
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()

    output_text = await client.complete(EXTRACTION_PROMPT, input_text)
    output = json.loads(output_text)

    # Audit trail
    SkillExtractionRun.objects.create(
        experience=experience,
        provider="openai",
        model=client.model,
        prompt_template=EXTRACTION_PROMPT[:500],
        input_hash=input_hash,
        output_json=output,
        status="completed",
        input_tokens=len(input_text.split()) * 2,
        output_tokens=len(output_text.split()) * 2,
    )

    return output

def _format_experience(exp) -> str:
    lines = [f"Expérience: {exp.title}"]
    if exp.organization:
        lines.append(f"Organisation: {exp.organization}")
    if exp.description:
        lines.append(f"Description: {exp.description}")
    if exp.missions:
        lines.append(f"Missions: {', '.join(exp.missions)}")
    if exp.deliverables:
        lines.append(f"Livrables: {', '.join(exp.deliverables)}")
    if exp.tools:
        lines.append(f"Outils: {', '.join(exp.tools)}")
    if exp.responsibilities:
        lines.append(f"Responsabilités: {', '.join(exp.responsibilities)}")
    if exp.outcomes:
        lines.append(f"Résultats: {', '.join(exp.outcomes)}")
    return "\n".join(lines)
```

### 2.4 `prompting.py` — Templates de prompts

```python
FORMALIZE_PROMPT = """Formalisée cette compétence brute en une formulation professionnelle claire.

Règles:
- Commence par "Je suis capable de..."
- Sois spécifique (pas de généralités)
- Max 25aines mots
- Ne change PAS le sens, reformule juste

Compétence brute: {raw_label}
Contexte: {context}"""

SUGGEST_EVIDENCE_PROMPT = """Pour cette compétence, suggère 3 questions qui permettraient de collecter des preuves.

Compétence: {label}
Formulation: {formulation}
Expériences liées: {experiences}

Retourne un JSON:
{"questions": ["question 1", "question 2", "question 3"]}"""

BENCHMARK_PROMPT = """Compare cette compétence avec les standards du marché pour le rôle cible.

Compétence: {label}
Niveau actuel: {mastery_level}
Rôle cible: {target_role}

Retourne un JSON:
{
  "market_level": "beginner|intermediate|advanced|expert",
  "gap": "none|minor|moderate|significant",
  "recommendation": "...",
  "market_keywords": ["keyword1", "keyword2"]
}"""
```

### 2.5 `validation.py` — Validation structurelle

```python
REQUIRED_FIELDS = {"label", "formulation", "category", "mastery_level", "confidence"}

def validate_extraction_output(output: dict) -> list[str]:
    """Valide la structure de la réponse LLM. Retourne la liste des erreurs."""
    errors = []
    if "competencies" not in output:
        return ["Missing 'competencies' key"]
    if not isinstance(output["competencies"], list):
        return ["'competencies' must be a list"]
    for i, comp in enumerate(output["competencies"]):
        missing = REQUIRED_FIELDS - set(comp.keys())
        if missing:
            errors.append(f"Competency #{i}: missing fields {missing}")
        if comp.get("category") not in ("hard_skill", "soft_skill", "domain_knowledge"):
            errors.append(f"Competency #{i}: invalid category '{comp.get('category')}'")
    return errors
```

### 2.6 `exports.py` — Export JSON/Markdown

```python
def export_to_json(experiences, competencies, evidence) -> dict:
    return {
        "exported_at": datetime.now().isoformat(),
        "experiences": [ExperienceSerializer(e).data for e in experiences],
        "competencies": [CompetencySerializer(c).data for c in competencies],
        "evidence": [EvidenceSerializer(e).data for e in evidence],
    }

def export_to_markdown(competencies) -> str:
    lines = ["# Portefeuille de compétences\n"]
    for cat in ("hard_skill", "soft_skill", "domain_knowledge"):
        items = [c for c in competencies if c.category == cat]
        if not items:
            continue
        lines.append(f"\n## {cat.replace('_', ' ').title()}\n")
        for c in items:
            status_icon = {"validated": "✅", "draft": "📝", "rejected": "❌"}.get(c.status, "")
            lines.append(f"- {status_icon} **{c.label}** — {c.mastery_level}")
            if c.evidence.exists():
                lines.append(f"  - Preuves: {', '.join(e.title for e in c.evidence.all())}")
    return "\n".join(lines)
```

### 2.7 Endpoints LLM dans `views.py`

```python
class ExtractFromExperienceView(APIView):
    """POST /api/skills/llm/extract-from-experience"""
    async def post(self, request):
        experience_id = request.data.get("experience_id")
        experience = get_object_or_404(SkillExperience, pk=experience_id)
        client = LLMClient()
        output = await extract_from_experience(client, experience)
        errors = validate_extraction_output(output)
        if errors:
            return Response({"errors": errors}, status=422)
        # Créer les compétences (draft)
        created = []
        for comp in output["competencies"]:
            c = SkillCompetency.objects.create(
                label=comp["label"],
                formulation=comp["formulation"],
                category=comp["category"],
                action_verb=comp.get("action_verb", ""),
                object=comp.get("object", ""),
                context=comp.get("context", ""),
                mastery_level=comp.get("mastery_level", "beginner"),
                confidence=comp.get("confidence", "medium"),
                mastery_rationale=comp.get("rationale", ""),
                status="draft",
                created_by="llm",
            )
            c.experiences.add(experience)
            created.append(SkillCompetencySerializer(c).data)
        return Response({"created": created, "count": len(created)})
```

---

## 3. Phase 2 complémentaire — UI avancée

### 3.1 Séparer le monolithe en pages dédiées

Le composant `skills-portfolio-view.tsx` (456 lignes) doit être découpé :

```
web/src/app/skills/
├── page.tsx                     # Dashboard (existe)
├── experiences/
│   ├── page.tsx                 # Liste des expériences
│   └── [id]/page.tsx            # Détail édition expérience
├── competencies/
│   ├── page.tsx                 # Liste/Kanban des compétences
│   └── [id]/page.tsx            # Détail édition compétence
├── evidence/
│   └── page.tsx                 # Liste des preuves
├── benchmark/
│   └── page.tsx                 # Benchmark vs marché
└── action-plan/
    └── page.tsx                 # Plan de développement
```

### 3.2 Composants à créer

```
web/src/components/skills/
├── skills-portfolio-view.tsx      # Existe (à simplifier → dashboard only)
├── experience-card.tsx            # Carte expérience
├── experience-form.tsx            # Formulaire création/édition
├── competency-card.tsx            # Carte compétence
├── competency-form.tsx            # Formulaire création/édition
├── competency-kanban.tsx          # Vue Kanban (Draft → To Prove → Validated)
├── evidence-card.tsx              # Carte preuve
├── evidence-form.tsx              # Formulaire création/édition
├── validation-gate.tsx            # Composant validation avec gate preuve
├── llm-extract-button.tsx         # Bouton "Analyser avec l'IA"
├── export-menu.tsx                # Menu export JSON/Markdown
└── stats-bar.tsx                  # Barre de stats dashboard
```

### 3.3 Compétences manquantes dans l'UI

| Fonctionnalité | Status | Priorité |
|----------------|--------|----------|
| Édition expérience (PATCH) | ❌ | Haute |
| Suppression expérience (DELETE) | ❌ | Moyenne |
| Édition compétence (PATCH) | ❌ | Haute |
| Filtrage compétences (status, category) | ❌ | Haute |
| Vue Kanban | ❌ | Moyenne |
| Bouton "Analyser avec l'IA" | ❌ | Haute |
| Détail preuve | ❌ | Moyenne |
| Export JSON/Markdown | ❌ | Moyenne |

---

## 4. Phase 1 complémentaire — Export + Management commands

### 4.1 Endpoints export dans `views.py`

```python
class ExportJsonView(APIView):
    """GET /api/skills/export/json"""
    def get(self, request):
        data = export_to_json(
            SkillExperience.objects.all(),
            SkillCompetency.objects.all(),
            SkillEvidence.objects.all(),
        )
        return Response(data)

class ExportMarkdownView(APIView):
    """GET /api/skills/export/markdown"""
    def get(self, request):
        md = export_to_markdown(SkillCompetency.objects.all())
        return HttpResponse(md, content_type="text/markdown")
```

### 4.2 Management commands

```
backend/apps/skills_portfolio/management/commands/
├── seed_skills_portfolio.py     # Génère des données de test
├── import_cv_experiences.py     # Importe depuis cv.md → SkillExperience
└── export_skills_portfolio.py   # Exporte en JSON/Markdown via CLI
```

**`seed_skills_portfolio.py` :**
```python
from django.core.management.base import BaseCommand
from apps.skills_portfolio.models import SkillExperience, SkillCompetency, SkillEvidence

class Command(BaseCommand):
    help = "Seed the skills portfolio with sample data"

    def handle(self, *args, **options):
        exp = SkillExperience.objects.create(
            title="Career-Ops System",
            type="project",
            description="AI-powered job search automation",
            deliverables=["CLI tool", "Web dashboard", "60+ ATS connectors"],
            tools=["Python", "Django", "Next.js", "TypeScript"],
        )
        comp = SkillCompetency.objects.create(
            label="Concevoir des systèmes multi-services",
            formulation="Je suis capable de concevoir des systèmes multi-services avec sync bidirectionnelle DB/fichiers",
            category="hard_skill",
            mastery_level="advanced",
            status="draft",
        )
        comp.experiences.add(exp)
        self.stdout.write(self.style.SUCCESS("Seeded 1 experience, 1 competency"))
```

**`import_cv_experiences.py` :**
```python
class Command(BaseCommand):
    help = "Import experiences from cv.md into SkillExperience"

    def handle(self, *args, **options):
        cv_path = settings.CAREER_OPS_ROOT / "cv.md"
        content = cv_path.read_text()
        # Parser les sections Experience du CV
        # Créer des SkillExperience pour chaque bloc
        # Lier les outils/technologies comme tags
        ...
```

---

## 5. Phase 5 — Benchmark + Development Plan

### 5.1 Endpoint benchmark

```python
class BenchmarkView(APIView):
    """POST /api/skills/benchmark — compare compétences vs marché"""
    async def post(self, request):
        target_role = request.data.get("target_role", "")
        competencies = SkillCompetency.objects.filter(status="validated")
        client = LLMClient()
        results = []
        for comp in competencies:
            output = await client.complete(
                BENCHMARK_PROMPT.format(
                    label=comp.label,
                    mastery_level=comp.mastery_level,
                    target_role=target_role,
                )
            )
            result = json.loads(output)
            results.append({
                "competency": SkillCompetencySerializer(comp).data,
                "benchmark": result,
            })
        return Response({"results": results, "target_role": target_role})
```

### 5.2 Endpoint development plan

```python
class DevelopmentPlanView(APIView):
    """POST /api/skills/development-plan — génère un plan de progression"""
    async def post(self, request):
        target_role = request.data.get("target_role", "")
        # Récupérer les gaps du benchmark
        # Pour chaque gap, générer des actions de développement
        # Créer des SkillDevelopmentAction
        ...
```

### 5.3 Frontend

- Page `/skills/benchmark` : tableau comparatif compétences vs marché
- Page `/skills/action-plan` : liste d'actions de développement avec priorités

---

## 6. Phase 6 — Intégration career-ops

### 6.1 Agent mode `modes/skills.md`

```markdown
# Skills Portfolio Mode

You are managing the user's skills portfolio. When invoked:

1. READ their cv.md, config/profile.yml, and modes/_profile.md
2. ANALYZE their experiences and extract competencies
3. SUGGEST evidence they could collect
4. BENCHMARK their skills against market standards
5. RECOMMEND development actions

RULES:
- Skills are formalized, NEVER fabricated
- Every competency must be traceable to an experience
- Validation requires evidence
- Use the canonical career-ops data contract
```

### 6.2 Intégration avec les modes existants

| Mode career-ops | Intégration skills |
|-----------------|-------------------|
| `oferta.md` (évaluation) | Lire les compétences validées pour scorer l'adéquation |
| `pdf.md` (CV) | Injecter les compétences validées dans le CV |
| `upskill.md` | Utiliser les gaps du benchmark |
| `interview-prep.md` | Générer des questions STAR basées sur les compétences |
| `patterns.md` | Analyser les patterns de refus vs compétences |

### 6.3 Sync avec `cv.md`

```python
# Management command : export_skills_to_cv.py
def handle(self, *args, **options):
    """Ajoute les compétences validées à cv.md"""
    competencies = SkillCompetency.objects.filter(status="validated")
    cv_path = settings.CAREER_OPS_ROOT / "cv.md"
    # Ajouter/update la section Skills du CV
    ...
```

---

## 7. Phase 7 — Multi-user + production

### 7.1 Multi-user

```python
# Ajouter owner aux modèles
class SkillExperience(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    ...

# Filtrer par owner dans les vues
class ExperiencesView(APIView):
    def get(self, request):
        experiences = SkillExperience.objects.filter(owner=request.user)
        ...
```

### 7.2 Permissions

```python
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user
```

### 7.3 Production

- PostgreSQL en remplacement de SQLite
- Redis pour le cache
- Gunicorn + Nginx
- Sentry pour le monitoring
- Backup automatisé de la DB

---

## 8. Tests à ajouter

### 8.1 Backend

```python
# Tests CRUD détail
def test_get_experience_detail():
def test_update_experience():
def test_delete_experience():
def test_get_competency_detail():
def test_update_competency():
def test_get_evidence_detail():
def test_update_evidence():
def test_delete_evidence():

# Tests filtrage
def test_filter_competencies_by_status():
def test_filter_competencies_by_category():
def test_dashboard_with_data():

# Tests LLM (mockés)
def test_extract_from_experience():
def test_extract_validates_output():
def test_extract_handles_llm_error():
def test_formalize_competency():
def test_suggest_evidence_questions():

# Tests export
def test_export_json():
def test_export_markdown():

# Tests edge cases
def test_validate_already_validated():
def test_reject_already_rejected():
def test_create_competency_without_experience():
def test_evidence_without_source():
```

### 8.2 Frontend

```typescript
// web/src/components/skills/__tests__/
testExperienceForm.tsx
testCompetencyCard.tsx
testValidationGate.tsx
testLlmExtractButton.tsx
```

---

## 9. Plan d'action par priorité

### 🔴 Priorité 1 — Cette semaine (3-4 jours)

| Tâche | Jours | Fichiers |
|-------|-------|----------|
| `services/llm_client.py` | 0.5 | Créer le client LLM |
| `services/extraction.py` | 1 | Extraction + audit trail |
| `services/prompting.py` | 0.5 | Templates de prompts |
| `services/validation.py` | 0.5 | Validation structurelle |
| Endpoint `POST /api/skills/llm/extract-from-experience` | 0.5 | Vue + URL |
| Tests LLM mockés | 1 | 4-5 tests |

### 🟠 Priorité 2 — Semaine prochaine (3-4 jours)

| Tâche | Jours | Fichiers |
|-------|-------|----------|
| Découpage du monolithe → pages dédiées | 1.5 | 5+ pages |
| Composants UI (cards, forms, kanban) | 2 | 8+ composants |
| Édition compétence + expérience | 0.5 | Forms + API |
| Filtrage compétences | 0.5 | UI + API |

### 🟡 Priorité 3 — Dans 2 semaines (2-3 jours)

| Tâche | Jours | Fichiers |
|-------|-------|----------|
| Export JSON/Markdown (API + UI) | 1 | Vue + composant |
| Management commands (seed, import_cv, export) | 1 | 3 commands |
| Benchmark endpoint + page | 1 | Vue + page |
| Development plan endpoint + page | 1 | Vue + page |

### 🟢 Priorité 4 — Mois prochain (3-4 jours)

| Tâche | Jours | Fichiers |
|-------|-------|----------|
| Agent mode `modes/skills.md` | 0.5 | Mode |
| Intégration career-ops (oferta, pdf, upskill) | 2 | 4 modes |
| Multi-user (owner FK, permissions) | 1 | Models + vues |
| Production (PG, Gunicorn, Sentry) | 1 | Config |

### Total : ~12-15 jours de développement

---

*Document généré le 14 juillet 2026. Voir aussi [action-django.md](action-django.md) et [analyse-projet.md](analyse-projet.md).*
