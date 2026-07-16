# Plan : Module Éducation dans Skills Portfolio

**Date** : 2026-07-14
**Statut** : En attente de validation

---

## Contexte

Le Skills Portfolio gère actuellement les **expériences**, **compétences** et **preuves**. L'utilisateur souhaite y ajouter la dimension **éducation** : formations, certifications, titres RNCP, formations professionnelles, MOOCs.

## Décision : étendre `skills_portfolio` (pas d'app séparée)

### Pourquoi pas un app séparée ?

| Critère | App séparée | Dans `skills_portfolio` |
|---|---|---|
| Relation certification → compétence | Cross-app, plus complexe | Même app, FK directe |
| Services LLM réutilisables | Duplication ou dépendance circulaire | Même package `services/` |
| Dashboard unique | Deux dashboards à agréger | Un seul `/api/skills/dashboard` |
| Boilerplate | Nouveau app, urls, admin, migrations | Ajout de modèles existants |
| Déploiement | Deux apps à installer | Un seul `INSTALLED_APPS` |

**Verdict** : étendre `skills_portfolio`. La relation éducation ↔ compétence est trop étroite pour séparer.

---

## Modèle de données

### `Education`

```python
class Education(models.Model):
    class EducationType(models.TextChoices):
        FORMATION = "formation"          # Formation académique (BTS, Licence, Master...)
        CERTIFICATION = "certification"  # Certif professionnelle (AWS, PMP, Scrum...)
        RNCP = "rncp"                    # Titre RNCP (niveau 3 à 8)
        PROFESSIONAL = "professional"    # Formation professionnelle (DAST, habilitations...)
        MOOC = "mooc"                    # MOOC / e-learning (Coursera, Udemy, OpenClassrooms...)

    class Status(models.TextChoices):
        PLANNED = "planned"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        EXPIRED = "expired"              # Pour les certifications à durée limitée

    title = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True)
    education_type = models.CharField(max_length=20, choices=EducationType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    credential_url = models.URLField(blank=True)         # Lien vers le certificat
    credential_id = models.CharField(max_length=255, blank=True)  # Numéro de certificat
    hours = models.PositiveIntegerField(null=True, blank=True)    # Volume horaire
    description = models.TextField(blank=True)
    competencies = models.ManyToManyField("SkillCompetency", through="EducationCompetency", blank=True)
    experience = models.ForeignKey(SkillExperience, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### `EducationCompetency` (table de liaison)

```python
class EducationCompetency(models.Model):
    education = models.ForeignKey(Education, on_delete=models.CASCADE)
    competency = models.ForeignKey("SkillCompetency", on_delete=models.CASCADE)
    relevance = models.CharField(max_length=20, choices=[
        ("validated", "Validée par cette formation"),
        ("acquired", "Acquise pendant cette formation"),
        ("targeted", "Objectif de cette formation"),
    ], default="acquired")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("education", "competency")
```

---

## API Endpoints

### Endpoints existants (inchangés)

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/skills/dashboard` | GET | Dashboard agrégé — **ajouter `educations` au compteur** |
| `/api/skills/competencies` | GET/POST | CRUD compétences |
| `/api/skills/experiences` | GET/POST | CRUD expériences |
| `/api/skills/evidence` | GET/POST | CRUD preuves |

### Nouveaux endpoints

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/skills/educations` | GET | Liste des formations |
| `/api/skills/educations` | POST | Créer une formation |
| `/api/skills/educations/{id}` | GET/PUT/PATCH/DELETE | CRUD individuel |
| `/api/skills/educations/{id}/attach-competency` | POST | Attacher une compétence |
| `/api/skills/educations/{id}/detach-competency` | POST | Détacher une compétence |
| `/api/skills/llm/extract-education` | POST | Extraire des formations depuis un texte |

### Dashboard modifié

```json
{
  "experiences": 3,
  "competencies": 12,
  "evidence": 8,
  "educations": 5,           // NOUVEAU
  "validated": 9,
  "draft": 3,
  "without_evidence": 2,
  "by_status": { "validated": 9, "draft": 3 },
  "by_category": { "knowledge": 4, "hard_skill": 6, "soft_skill": 2 }
}
```

---

## Frontend

### Pages

| Route | Composant | Description |
|---|---|---|
| `/skills` | `skills-portfolio-view.tsx` | Page principale — **ajouter formulaire education dans sidebar** |
| `/skills/education` | `skills-education-view.tsx` | **NOUVEAU** — Listing des formations |
| `/skills/list` | `skills-list-view.tsx` | Compétences (existant) |
| `/skills/experiences` | `skills-experiences-view.tsx` | Expériences (existant) |

### Sidebar `/skills` — ajout formulaire

```
┌─────────────────────┐
│ Ajouter une formation│
│ Titre    [________] │
│ Type     [Formation]│
│ École    [________] │
│ Statut   [Complété] │
│ Dates    [__/__/__] │
│ URL      [________] │
│ Compétence [______] │  ← select multi ou single
│ [Créer la formation]│
└─────────────────────┘
```

### Page `/skills/education`

Même pattern que `/skills/experiences` :
- 6 KPI cards : Total, Complétées, En cours, Certifications, RNCP, Sans compétence
- Filtres : type, statut
- Cards expandables avec détails
- Attacher/détacher des compétences
- Extraction LLM depuis un texte

---

## Services LLM

### Extraction depuis texte

```python
# POST /api/skills/llm/extract-education
{
  "text": "Master IA à Université Paris-Saclay (2022-2024), 
           certif AWS SAA (2023), Formation React Udemy (40h)",
  "persist": true
}

# Réponse
{
  "extracted": [
    {
      "title": "Master Intelligence Artificielle",
      "institution": "Université Paris-Saclay",
      "education_type": "formation",
      "status": "completed",
      "start_date": "2022-09",
      "end_date": "2024-06",
      "competencies": ["Concevoir des modèles ML", "Déployer des pipelines IA"]
    },
    ...
  ],
  "created": [...],
  "count": 3
}
```

### Prompt

```
Tu es un expert RH. Analyse le texte suivant et extrais toutes les formations,
certifications, titres et parcours éducatifs.

Pour chaque élément trouvé, retourne :
- title : nom exact de la formation/certification
- institution : organisme délivrant
- education_type : formation | certification | rncp | professional | mooc
- status : completed | in_progress | planned
- start_date : YYYY-MM ou YYYY-MM-DD si disponible
- end_date : YYYY-MM ou YYYY-MM-DD si disponible
- credential_url : lien si mentionné
- credential_id : numéro si mentionné
- hours : volume horaire si mentionné
- competencies : liste de compétences que cette formation developpe/valide

Texte :
{input_text}
```

---

## Fichiers à créer/modifier

### Nouveaux fichiers

| Fichier | Type |
|---|---|
| `backend/apps/skills_portfolio/models.py` | **Modifier** — ajouter Education + EducationCompetency |
| `backend/apps/skills_portfolio/serializers.py` | **Modifier** — ajouter EducationSerializer |
| `backend/apps/skills_portfolio/views.py` | **Modifier** — ajouter EducationViewSet |
| `backend/apps/skills_portfolio/urls.py` | **Modifier** — ajouter routes educations |
| `backend/apps/skills_portfolio/services/prompts.py` | **Modifier** — ajouter prompt extraction education |
| `backend/apps/skills_portfolio/services/extraction.py` | **Modifier** — ajouter extract_education_from_text() |
| `backend/apps/skills_portfolio/migrations/0002_education.py` | **Créer** — migration |
| `backend/tests/test_skills_education_api.py` | **Créer** — tests education |
| `web/src/app/skills/education/page.tsx` | **Créer** — route |
| `web/src/components/skills/skills-education-view.tsx` | **Créer** — listing education |
| `web/src/components/skills/skills-portfolio-view.tsx` | **Modifier** — ajouter formulaire education dans sidebar |
| `web/src/lib/nav-items.ts` | **Modifier** — ajouter lien education |
| `web/src/app/api/skills/[...path]/route.ts` | **Modifier** — ajouter fallback education |

---

## Estimation

| Tâche | Complexité | Durée estimée |
|---|---|---|
| Modèles Django + migration | Faible | 15 min |
| Sérialiseurs + vues + URLs | Moyenne | 20 min |
| Service extraction LLM | Moyenne | 15 min |
| Tests backend (education) | Faible | 10 min |
| Frontend: formulaire sidebar | Faible | 10 min |
| Frontend: page listing education | Moyenne | 20 min |
| Frontend: nav + routes + proxy | Faible | 5 min |
| **Total** | | **~95 min** |

---

## Questions à valider

1. **Champs optionnels** : `credential_id` et `credential_url` sont-ils suffisants, ou tu veux un champ "organisme de certification" séparé de `institution` ?
2. **Expiration** : les certifications ont-elles une date d'expiration à gérer (statut `expired` automatique) ?
3. **Priorité** : on fait le backend complet d'abord, ou on bidouille le frontend avec des données mockées en parallèle ?
