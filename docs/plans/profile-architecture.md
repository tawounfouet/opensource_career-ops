# Plan — Architecture Profil Candidat & Multi-Profiles

## Contexte

Après avoir bouclé le pipeline Skills Portfolio → CV (gaps 1-6), la question du **profil candidat** se pose :

- Le profil vit actuellement dans `config/profile.yml` — un fichier YAML éditable uniquement par le code
- Il n'existe **aucune UI** pour éditer ce profil (contrairement au Discovery Profile qui a `/discovery/profile`)
- Les utilisateurs non techniques ne peuvent pas remplir leurs informations ni gérer des variantes de profil

Ce document analyse les options architecturales et propose un plan d'action.

---

## État des lieux

### Ce qui existe

| Composant | Fichier | UI | Source de vérité |
|-----------|---------|-----|------------------|
| **Profil candidat** | `config/profile.yml` | ❌ Aucune | YAML |
| **Discovery Profile** | `data/search-profiles/*.yml` | ✅ `/discovery/profile` | YAML |
| **Compétences** | Django DB (`skills_portfolio`) | ✅ `/skills` | PostgreSQL |
| **Expériences** | Django DB (`skills_portfolio`) | ✅ `/skills/experiences` | PostgreSQL |
| **Formations** | Django DB (`skills_portfolio`) | ✅ `/skills/education` | PostgreSQL |
| **Portals** | `portals.yml` | ❌ Aucune | YAML |
| **CV Generator** | `packages/cv-generator/` | ✅ `/cv` | CVData Pydantic |

### Contenu de `config/profile.yml`

```yaml
candidate:
  first_name: Audrey
  last_name: KWEKEU
  email: kwekeuaudrey@gmail.com
  phone: "+33 7 44 73 70 96"
  city: Marseille
  country: France

narrative:
  headline: Ingénieure Qualité & Affaires Réglementaires
  summary: "Spécialiste en conformité réglementaire..."

compensation:
  desired: 45000
  currency: EUR
  period: year

location:
  policy: hybrid
  regions: [Marseille, Lyon, Paris, Remote]

languages:
  - language: Français
    level: Langue maternelle
  - language: Anglais
    level: B2
    note: TOEIC 865/990

interests:
  - Chant choral
  - Voyage
  - Photographie
  - Bénévolat

regulations:
  - ISO 13485
  - MDSAP
  - Marquage CE
```

### Ce qui manque

| Absence | Impact |
|---------|--------|
| UI d'édition du profil | Les utilisateurs non techniques ne peuvent pas remplir le profil |
| Multi-profils | Impossible de cibler plusieurs types de postes avec des profils différents |
| Profil selector dans le frontend | Pas de switch entre variantes |
| Intégration profil → scan/evaluation | Le profil n'est pas utilisé par le scanner ni l'évaluateur |

---

## Analyse des options architecturales

### Option A : YAML + UI (recommandée)

```
Frontend (UI forms)  →  API /api/profile  →  config/profile.yml
                              ↓
                    Le LLM peut aussi éditer directement
```

**Avantages :**
- Le LLM (Claude, Codex, etc.) peut éditer le profil en conversation
- Le fichier est versionnable (git)
- Pas de migration DB, pas de ORM
- Simple à backuper
- Compatible avec l'architecture existante (portals.yml, search-profiles.yml)

**Inconvénients :**
- Pas de validation DB stricte
- Pas de requêtes SQL sur les profils
- Concurrency limitée (un seul profil actif à la fois)

**Multi-profils :**
```
config/
  profile.yml                    ← actif par défaut
  profiles/
    data-engineer.yml            ← override partiel
    ml-engineer.yml
```

Chaque variante ne stocke que les **différences** par rapport au profil de base. L'API résout le merge au runtime.

### Option B : Modèle Django complet

```python
class Profile(models.Model):
    name = models.CharField(max_length=100)  # "data-engineer", "ml-engineer"
    is_default = models.BooleanField(default=False)
    # ... tous les champs du profil

class ProfileLanguage(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    language = models.CharField(max_length=50)
    level = models.CharField(max_length=50)
    note = models.TextField(blank=True)

class ProfileInterest(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    label = models.CharField(max_length=200)
```

**Avantages :**
- Validation DB stricte
- Requêtes SQL possibles
- Relations propres (M2M, FK)
- API REST classique

**Inconvénients :**
- Le LLM ne peut plus éditer directement (passe par API)
- Migration DB nécessaire
- Plus de complexité (serializers, views, URLs)
- Duplication avec le YAML existant
- Les données sont "cachées" dans la DB, pas visibles dans les fichiers

### Option C : Hybride (YAML comme backup, DB comme primary)

```
Frontend  →  API  →  PostgreSQL (primary)
                     ↕
              config/profile.yml (backup/export)
```

**Avantages :**
- Les deux mondes
- Export/import possible

**Inconvénients :**
- Deux sources de vérité = risque de divergence
- Complexité de synchronisation
- Over-engineering pour un profil candidat

---

## Recommandation : Option A (YAML + UI)

### Pourquoi YAML reste la source de vérité

1. **Philosophie career-ops** : local-first, données dans des fichiers, pas dans une DB opaque
2. **LLM-friendly** : l'IA peut éditer le profil directement en conversation ("ajoute(langues, Espagnol, B1)")
3. **Versionnable** : `git diff config/profile.yml` montre exactement ce qui a changé
4. **Simple** : pas de migration, pas de serializers, pas d'ORM
5. **Portable** : le profil voyage avec le projet, pas besoin de dump DB

### Pourquoi une UI est nécessaire

1. **Utilisateurs non techniques** : ne savent pas éditer du YAML
2. **Découverte** : l'UI montre quels champs existent et comment les remplir
3. **Validation** : l'UI peut valider le format avant sauvegarde
4. **Visualisation** : l'UI peut montrer un aperçu du CV généré
5. **Accessibilité** : formulaire > éditeur de texte pour la plupart des gens

---

## Architecture détaillée (Option A)

### Backend : API YAML

```python
# apps/portals/views.py (étendu)

class ProfileView(APIView):
    """Read/write config/profile.yml"""

    def get(self, request):
        """Retourne le profil courant (merged si variant actif)."""
        profile = _load_profile()
        variant = request.query_params.get("variant")
        if variant:
            profile = _merge_profile(profile, variant)
        return Response(profile)

    def patch(self, request):
        """Met à jour le profil (partiel)."""
        profile = _load_profile()
        patch = request.data
        # Merge intelligent (listes = remplacement, dicts = fusion récursive)
        _deep_merge(profile, patch)
        _save_profile(profile)
        return Response(profile)

    def delete(self, request, variant):
        """Supprime un variant."""
        ...

class ProfileVariantView(APIView):
    """List/create/delete profile variants"""

    def get(self, request):
        """Liste tous les variants disponibles."""
        variants = _list_variants()  # ["data-engineer", "ml-engineer"]
        return Response({"variants": variants})

    def post(self, request):
        """Crée un nouveau variant (override partiel)."""
        name = request.data["name"]
        overrides = request.data["overrides"]  # Champs à surcharger
        _save_variant(name, overrides)
        return Response({"name": name})
```

### Frontend : Éditeur de profil

```
/web/src/app/profile/page.tsx
/web/src/components/profile-editor.tsx
```

**Sections de l'UI :**

1. **Identité** — Nom, email, téléphone, ville, pays
2. **Narrative** — Titre cible, résumé professionnel
3. **Expérience** — Langues parlées + niveaux
4. **Intérêts** — Centres d'intérêt (liste libre)
5. **Réglementation** — Normes, certifications (si applicable)
6. **Rémunération** — Fourchette salariale cible
7. **Localisation** — Politique remote, régions acceptées
8. **Variantes** — Sélecteur + création de variants

**Comportement :**

- Chargement : `GET /api/profile` → affiche le profil courant
- Édition : modification locale (state React)
- Sauvegarde : `PATCH /api/profile` → écrit dans le YAML
- Aperçu CV : `GET /api/skills/export/cv-markdown` → affiche le CV généré

### Intégration avec les autres modules

| Module | Consomme le profil | Comment |
|--------|-------------------|---------|
| **CV Generator** | ✅ | `export_to_cvdata()` lit `config/profile.yml` pour identity, languages, interests, regulations |
| **Discovery** | ✅ | `generate_discovery_profile()` utilise narrative.headline + keywords |
| **Scan** | ✅ | `portals.yml` utilise title_filter basé sur le profil |
| **Evaluation** | ⚠️ | Pourrait utiliser compensation.target et location.policy |
| **Interview** | ⚠️ | Pourrait utiliser narrative.summary comme contexte |

### Multi-profils : fonctionnement

**Scénario :** Audrey cible à la fois "Data Engineer" et "Ingénieur Qualité"

```
config/
  profile.yml                    ← base (identité, narrative par défaut)
  profiles/
    data-engineer.yml            ← override: headline, keywords, regulations
    ingenieur-qualite.yml        ← override: headline, keywords, regulations
```

**Contenu de `data-engineer.yml` :**
```yaml
narrative:
  headline: Data Engineer
  summary: "Expérience en pipeline de données..."

regulations:
  - GDPR
  - SOC2
```

**Merge au runtime :**
```python
def resolve_profile(variant_name=None):
    base = load_yaml("config/profile.yml")
    if variant_name:
        override = load_yaml(f"config/profiles/{variant_name}.yml")
        return deep_merge(base, override)
    return base
```

**UI :**
- Header : sélecteur de profil actif
- Badge : "Data Engineer" ou "Ingénieur Qualite"
- Champs modifiés par rapport au base : highlight bleu
- Bouton "Créer un variant" → formulaire de nom + champs à surcharger
- Le variant actif est sauvegardé dans `localStorage` (pas dans le YAML)

---

## Impact sur les modules existants

### Changements nécessaires

| Fichier | Changement | Priorité |
|---------|-----------|----------|
| `apps/portals/views.py` | Ajouter `ProfileView` + `ProfileVariantView` | Haute |
| `apps/portals/urls.py` | Ajouter routes `/api/profile`, `/api/profile/variants` | Haute |
| `web/src/components/profile-editor.tsx` | **Nouveau** — éditeur complet | Haute |
| `web/src/app/profile/page.tsx` | **Nouveau** — page profil | Haute |
| `web/src/lib/nav-items.ts` | Ajouter "Profil" dans la navigation | Haute |
| `skills_portfolio/services/exports.py` | Lire le variant actif si spécifié | Moyenne |
| `config/profile.yml` | Documenter les champs disponibles | Moyenne |
| `templates/profile.example.yml` | Exemple avec tous les champs | Moyenne |

### Pas de changement

- Les modèles Django existants (competencies, experiences, education) restent en DB
- Le YAML reste la source de vérité pour le profil candidat
- Le CV generator continue de lire `CVData` (pas de changement)

---

## UX Flow

### Premier usage (onboarding)

```
1. L'utilisateur arrive sur /profile
2. L'UI détecte que le profil est vide/incomplet
3. Un formulaire guidé propose de remplir :
   - "Quel est ton nom complet ?"
   - "Quel type de poste vises-tu ?"
   - "Dans quelles langues es-tu à l'aise ?"
   - "Quelles normes connais-tu ?"
4. L'IA peut aussi remplir le profil via conversation :
   "Dis-moi ton nom, ton email et le type de poste que tu cibles"
5. L'utilisateur valide et sauvegarde
6. Le profil est écrit dans config/profile.yml
```

### Usage quotidien

```
1. L'utilisateur ouvre /profile
2. Il modifie un champ (ex: ajoute une langue)
3. Il clique "Sauvegarder"
4. Le YAML est mis à jour
5. Le CV généré reflète automatiquement le changement
```

### Multi-profils

```
1. L'utilisateur crée un variant "Data Engineer"
2. Il modifie le headline et les regulations
3. Il clique "Sauvegarder le variant"
4. Il bascule sur "Ingénieur Qualite" via le sélecteur
5. Le CV se regénère avec le nouveau profil
6. Le scan utilise les keywords du variant actif
```

---

## Ordre d'implémentation

| Étape | Tâche | Durée estimée |
|-------|-------|---------------|
| 1 | Créer `templates/profile.example.yml` avec tous les champs documentés | 15 min |
| 2 | Ajouter `ProfileView` + `ProfileVariantView` dans Django | 30 min |
| 3 | Ajouter les routes `/api/profile` et `/api/profile/variants` | 10 min |
| 4 | Créer `profile-editor.tsx` avec les sections UI | 45 min |
| 5 | Créer la page `/profile` | 10 min |
| 6 | Ajouter "Profil" dans la navigation | 5 min |
| 7 | Étendre `exports.py` pour lire le variant actif | 15 min |
| 8 | Tests backend + TypeScript check | 15 min |
| **Total** | | **~2.5h** |

---

## Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| YAML corrompu par une mauvaise sauvegarde | Élevé | Backup automatique avant écriture (`profile.yml.bak`) |
| Deux UI écrivent le même fichier | Moyen | Lock mutex sur l'écriture YAML |
| Variant merge cassé | Moyen | Tests unitaires pour `deep_merge` |
| LLM édite le profil pendant que l'UI l'affiche | Faible | Rafraîchissement au focus de la page |

---

## Décisions ouvertes

1. **Où stocker le variant actif ?** `localStorage` (persistance navigateur) vs `config/profile.yml` (persistant partout)
2. **Faut-il un champ `variant` dans le YAML ?** Ou le sélecteur suffit-il ?
3. **L'UI doit-elle montrer le YAML brut ?** Pour les utilisateurs avancés qui veulent voir ce qui change
4. **Faut-il un import/export du profil ?** Pour partager un profil entre machines

---

## Résumé

Le profil candidat doit être :
- **Éditable par l'humain** (UI forms)
- **Éditable par le LLM** (conversation)
- **Versionnable** (git)
- **Portable** (fichier, pas DB)
- **Multi-variant** (un profil actif, des variants override)

La solution est un **éditeur YAML avec UI** — pas une table Django. C'est plus simple, plus flexible, et compatible avec la philosophie local-first de career-ops.
