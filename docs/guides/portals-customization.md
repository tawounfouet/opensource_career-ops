# Guide : Personnaliser portals.yml pour son secteur

Ce guide explique comment adapter `portals.yml` a votre secteur, pas a pas.

---

## Étape 0 — Comprendre la structure

`portals.yml` a 4 sections cles :

```
portals.yml
├── title_filter       → Quels mots-cles dans le titre du poste
│   ├── positive       →   Mots a inclure (OBLIGATOIRE)
│   └── negative       →   Mots a exclure (optionnel)
├── location_filter    → Quelles localisations accepter/bloquer
│   ├── always_allow   →   Prioritaire (ex: "France")
│   ├── allow          →   Acceptees
│   └── block          →   Rejetees
├── tracked_companies  → Liste des entreprises a scanner
│   ├── name           →   Nom court
│   ├── careers_url    →   URL page carriere (OBLIGATOIRE)
│   ├── api            →   URL API Greenhouse/Lever/Ashby (optionnel)
│   ├── parser         →   Script local de parsing (avance)
│   └── enabled        →   true/false
└── job_boards         → Sites d'offres (Indeed, APEC, etc.)
```

---

## Étape 1 — Sauvegarder l'existant

```bash
cp portals.yml portals.yml.backup-$(date +%Y%m%d)
```

Pour restaurer : `cp portals.yml.backup-* portals.yml`

---

## Étape 2 — Definir les mots-cles de votre secteur

**Regle :** le `title_filter.positive` est un `OR` insensible a la casse.  
Un job est accepte si son titre contient **au moins un** des mots-cles.

### Exemple — Secteur biomedical/qualite/reglementaire

```yaml
title_filter:
  positive:
    # Mots-cles metier
    - "Qualite"
    - "Quality"
    - "Reglementaire"
    - "Regulatory"
    - "Affaires Reglementaires"
    - "Regulatory Affairs"
    - "Biomedical"
    - "Biomedicale"
    - "Dispositif Medical"
    - "Medical Device"
    - "Assurance Qualite"
    - "Quality Assurance"
    - "Pharmacovigilance"
    - "MDR"
    - "IVDR"
    - "ISO 13485"
    - "ISO 14971"
    - "Validation"
    - "Conformite"
    - "Compliance"
    # Cibles plus larges (captent aussi du bruit)
    - "QA"
    - "RA"
    - "DM"
    - "DIV"
  negative:
    # Exclure les faux positifs
    - "AI"
    - "Agent"
    - "Software"
    - "ML"
    - "Data"
    - "DevOps"
    - "Fullstack"
    - "Frontend"
    - "Backend"
    - "Junior"
    - "Stage"
    - "Intern"
```

**Piege :** les mots courts ("QA", "RA", "DM") captent beaucoup de bruit.  
Si trop de faux positifs, supprimez-les et gardez les mots longs.

---

## Étape 3 — Configurer le filtre de localisation

```yaml
location_filter:
  always_allow:
    - "France"
    - "Marseille"
  allow:
    - "France"
    - "Remote"
    - "Paris"
    - "Lyon"
    - "Marseille"
    - "Europe"
    - "EU"
    - "Ile-de-France"
    - "PACA"
  block:
    - "India"
    - "Bengaluru"
    - "Singapore"
    - "Japan"
    - "Brazil"
    - "Australia"
    - "US"
    - "United States"
    - "Canada"
    - "China"
```

**Ordre de priorite :**
1. `always_allow` passe toujours (ex: "Remote, France or India" → France gagne)
2. `block` rejette
3. `allow` doit matcher

---

## Étape 4 — Remplacer les entreprises

C'est l'etape la plus longue. Pour chaque entreprise, il faut :

1. Son **nom** (court)
2. Son **careers_url** (page carriere — obligatoire)
3. Optionnel : son **api** Greenhouse/Lever/Ashby

### Comment trouver les URLs

La plupart des entreprises utilisent un ATS :

| ATS | URL pattern |
|-----|-------------|
| Greenhouse | `https://job-boards.greenhouse.io/<slug>` |
| Lever | `https://jobs.lever.co/<slug>` |
| Ashby | `https://jobs.ashbyhq.com/<slug>` |
| Workday | `https://<company>.wd1.myworkdayjobs.com/<career-site>` |

**Methode :** Google `"<entreprise> careers greenhouse"` ou `"<entreprise> jobs lever"`.

Pour les entreprises qui ont `careers_url: https://<entreprise>.com/careers`  
sans API, le scanner utilisera Playwright (methode L1).

### Exemple pour le biomedical

```yaml
tracked_companies:
  - name: bioMerieux
    careers_url: https://careers.biomerieux.com
    api: https://boards-api.greenhouse.io/v1/boards/biomerieux/jobs
    enabled: true

  - name: Medtronic
    careers_url: https://medtronic.eightfold.ai/careers
    enabled: true

  - name: Siemens Healthineers
    careers_url: https://jobs.siemens-healthineers.com
    enabled: true

  - name: Sanofi
    careers_url: https://jobs.sanofi.com
    enabled: true

  - name: Stryker
    careers_url: https://careers.stryker.com
    enabled: true
```

> **IMPORTANT :** Les entreprises du secteur biomedical utilisent rarement Greenhouse/Lever.  
> Le scanner utilisera alors la methode L1 (Playwright) ou L0 (parser local).

---

## Étape 5 — Ajouter des job boards francais

```yaml
job_boards:
  - name: APEC
    url: https://www.apec.fr
    enabled: true

  - name: Indeed France
    url: https://fr.indeed.com
    enabled: true

  - name: HelloWork
    url: https://www.hellowork.com
    enabled: true
```

---

## Étape 6 — Tester en dry-run

```bash
# Test rapide sur une seule entreprise
npm run scan -- --company bioMerieux --dry-run

# Test complet sans ecrire
npm run scan -- --dry-run

# Analyser les resultats
grep "Filtered by title"    # Combien de filtres titre
grep "Filtered by location" # Combien de filtres localisation
```

---

## Étape 7 — Iterer

1. Si **trop d'offres non pertinentes** → ajouter des mots en `title_filter.negative`
2. Si **trop peu d'offres** → ajouter des mots en `title_filter.positive`
3. Si **mauvaises localisations** → renforcer `location_filter.block`
4. Si **entreprises sans offres** → verifier leur `careers_url` ou passer `enabled: false`

---

## Étape 8 — Lancer le vrai scan

```bash
npm run scan
```

Les resultats sont ecrits dans `data/pipeline.md`.

---

## Restauration

Pour revenir a l'ancien `portals.yml` :

```bash
cp portals.yml.backup-* portals.yml
```

---

## Checklist recapitulative

- [ ] Sauvegarde creee (`portals.yml.backup-*`)
- [ ] `title_filter.positive` avec les mots-cles de votre metier
- [ ] `title_filter.negative` avec les mots a exclure
- [ ] `location_filter` adapte a votre zone geographique
- [ ] `tracked_companies` avec des entreprises de votre secteur
- [ ] Chaque entreprise a un `careers_url` valide
- [ ] `enabled: false` sur les entreprises non pertinentes
- [ ] Test dry-run OK
- [ ] Scan complet OK
