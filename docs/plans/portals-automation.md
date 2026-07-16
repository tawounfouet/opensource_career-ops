# Plan — Automatisation de portals.yml

**Date :** 2026-07-16  
**Statut :** Analyse + propositions

> **Voir aussi :** [Approche Hybride](portals-automation-hybrid.md) — combine les 4 approches en un pipeline unifie.

---

## Etat des lieux

`portals.yml` est 100% manuel aujourd'hui. Le template contient ~100 entreprises AI/tech, et l'utilisateur doit :
1. Copier le template
2. Ajouter/supprimer des entreprises a la main
3. Trouver les `careers_url` et `api` de chaque entreprise
4. Valider les slugs ATS

**Aucun** scraper, crawler, ou moteur de decouverte n'existe.

---

## Ce qui existe deja (a reutiliser)

| Brique | Localisation | Reutilisable ? |
|--------|-------------|:---:|
| Modeles Django (Portal, SearchQuery, TitleFilter) | `backend/apps/portals/models.py` | Oui |
| Sync YAML ↔ DB (`import_yaml_to_db`, `export_db_to_yaml`) | `backend/apps/portals/services.py:48:215` | Oui |
| Validation slugs ATS (`verify-portals`) | `backend/apps/portals/services.py` | Oui |
| Extraction LLM d'une entree (`extract_portal_from_text`) | `backend/apps/skills_portfolio/services/extraction.py:686` | Oui |
| Detection ATS automatique (Greenhouse/Lever/Ashby/Workday/SmartRecruiters) | `scripts/python/scanner/scan.py` | Oui (a extraire) |
| Discovery bridge (`apply_discovery_to_portals`) | `backend/apps/skills_portfolio/services/integration.py:180` | Partiel (mots-cles uniquement) |

---

## Approches proposees

### Approche A — Django Management Command (recommande)

**Principe :** Un `manage.py` command qui automatise la decouverte d'entreprises pour un secteur donne.

```bash
python manage.py discover_portals \
  --sector "pharmaceutique" \
  --country "France" \
  --roles "qualite,affaires reglementaires,biomedical" \
  --max-companies 30 \
  --dry-run
```

#### Workflow

```
1. Entree utilisateur : secteur + pays + roles
        │
        ▼
2. Discovery (LLM) : genere une liste d'entreprises du secteur
   Prompt : "Liste les 30 plus grandes entreprises pharmaceutiques
            et de dispositifs medicaux en France avec leur page
            carriere officielle."
        │
        ▼
3. Pour chaque entreprise :
   ├── Resoudre la careers_url (LLM ou web search)
   ├── Auto-detecter l'ATS (Greenhouse/Lever/Ashby/Workday/SmartRecruiters)
   ├── Verifier que l'URL est valide (HTTP HEAD)
   └── Si ATS detecte → extraire le slug API
        │
        ▼
4. Generer les entrees portals.yml
        │
        ▼
5. Validation :
   ├── verify-portals (slugs ATS)
   ├── Dedup avec l'existant
   └── Rapport : combien ajoutees, combien rejetees
        │
        ▼
6. Integration :
   ├── import_yaml_to_db()  → Django DB
   ├── export_db_to_yaml()  → config/portals.yml
   └── Backup automatique
```

#### Implementation

| Fichier | Role |
|---------|------|
| `backend/apps/portals/management/commands/discover_portals.py` | Commande Django |
| `backend/apps/portals/services/discovery.py` | Logique de decouverte (nouveau) |
| `backend/apps/portals/services/ats_detector.py` | Detection ATS (extrait du scanner) |

#### Avantages
- Integre a l'architecture existante (Django, YAML sync)
- Peut etre schedule (cron, Celery)
- Dry-run avant ecriture
- Backup automatique
- Reutilise `verify-portals` et la sync DB

#### Inconvenients
- Necessite Django (`python manage.py`)
- Couteux en tokens LLM (~30 appels pour 30 entreprises)
- Les URLs generees par LLM peuvent etre hallucinees (→ contremesure : HTTP HEAD verification)

---

### Approche B — OpenCode Skill

**Principe :** Un skill OpenCode (`.opencode/skills/portal-discovery/SKILL.md`) qui donne a l'agent les instructions pour decouvrir des entreprises.

```bash
# L'utilisateur dit a l'agent :
"Decouvre 20 entreprises de dispositifs medicaux en France et ajoute-les a portals.yml"

# L'agent :
1. Web search : "top medical device companies France careers page"
2. Pour chaque entreprise, navigue sur la page carriere (Playwright)
3. Detecte l'ATS (pattern matching dans le HTML)
4. Verifie l'API
5. Ajoute a portals.yml
6. Commit
```

#### Avantages
- Zero code a ecrire (juste un fichier .md)
- L'agent a acces a Playwright, web search, et edition de fichiers
- Validation temps reel (l'agent peut naviguer et verifier)
- Fonctionne sans Django

#### Inconvenients
- Manuel (l'utilisateur doit declencher)
- Lent (navigation Playwright pour chaque entreprise)
- Moins reproductible qu'un script

#### Livrable
`scripts/python/skills/portal-discovery/SKILL.md` — instructions agent

---

### Approche C — API REST Enrichment

**Principe :** Etendre `POST /api/skills/llm/extract-portal` avec un mode batch.

```bash
POST /api/portals/discover
{
  "sector": "medical devices",
  "country": "France",
  "max_companies": 20,
  "dry_run": true
}
```

Retourne :
```json
{
  "discovered": 20,
  "validated": 18,
  "rejected": 2,
  "entries": [...],
  "dry_run": true
}
```

#### Avantages
- API REST, utilisable depuis le frontend web
- Peut etre appellee par un agent
- Meme logique que l'approche A

#### Inconvenients
- Necessite le serveur Django
- Plus complexe a orchestrer

---

### Approche D — Job Board Scraper

**Principe :** Scraper APEC/Indeed/LinkedIn pour extraire les entreprises qui recrutent dans un secteur.

```bash
python manage.py scrape_job_boards \
  --source apec \
  --keywords "affaires reglementaires,qualite,biomedical"
```

#### Workflow

```
1. Scraper APEC avec les mots-cles
        │
        ▼
2. Extraire les noms d'entreprises des offres
        │
        ▼
3. Dedup + ranking (frequence d'apparition)
        │
        ▼
4. Pour chaque entreprise :
   └── Chercher la careers_url (Google "site:linkedin.com/company/{name}")
        │
        ▼
5. Detection ATS + validation
        │
        ▼
6. Ajout a portals.yml
```

#### Avantages
- Base sur des donnees reelles (entreprises qui recrutent vraiment)
- Decouvre des PME/ETI pas dans le top 30 des classements

#### Inconvenients
- Lent (scraping + recherche pour chaque entreprise)
- Fragile (les sites changent leur HTML)
- Risque legal (ToS des job boards)

---

## Comparaison

| Critere | A - Django Command | B - Skill Agent | C - API REST | D - Scraper |
|---------|:---:|:---:|:---:|:---:|
| Temps d'implementation | 3-4h | 30 min | 4-6h | 6-8h |
| Cout LLM | Moyen (~30 appels) | Faible (agent) | Moyen | Faible |
| Qualite des resultats | Bonne (LLM) | Excellente (Playwright) | Bonne (LLM) | Excellente (donnees reelles) |
| Maintenance | Faible | Nulle (skill) | Moyenne | Elevee (scraping) |
| Reproductible | Oui (script) | Non (manuel) | Oui (API) | Oui (script) |
| Sans Django | Non | Oui | Non | Non |

---

## Recommandation

**Approche A (Django Management Command) en priorite**, completee par **l'Approche B (Skill Agent) en fallback**.

### Pourquoi

1. **A est le plus equilibre** — rapide a implementer (3-4h), base solide (Django + sync existants), reproductible (cron), bonne qualite (LLM).
2. **B est le filet de securite** — si la commande Django echoue sur une entreprise, l'agent peut la resoudre manuellement via Playwright.
3. **C est l'evolution naturelle** de A — exposer la commande via API pour le frontend web.
4. **D est overkill** pour le besoin actuel — scraping complexe, fragile, risque legal.

### Roadmap

```
Phase 1 (3-4h) : Approche A
  ├── management/commands/discover_portals.py
  ├── services/discovery.py (LLM discovery)
  ├── services/ats_detector.py (extraction du scanner)
  └── Tests

Phase 2 (30 min) : Approche B
  └── .opencode/skills/portal-discovery/SKILL.md

Phase 3 (future) : Approche C
  └── API endpoint + frontend UI
```

---

## Prototype rapide — Approche A

### `discover_portals.py` (pseudo-code)

```python
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--sector", required=True)
        parser.add_argument("--country", default="France")
        parser.add_argument("--roles", default="")
        parser.add_argument("--max-companies", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, **options):
        # 1. LLM Discovery
        companies = discover_companies_via_llm(
            sector=options["sector"],
            country=options["country"],
            roles=options["roles"],
            max_companies=options["max_companies"],
        )
        # 2. Enrich: find careers_url + detect ATS
        enriched = []
        for company in companies:
            entry = enrich_company(company["name"])
            if entry:
                enriched.append(entry)
        # 3. Validate ATS slugs
        validated = validate_portals(enriched)
        # 4. Show report
        self.stdout.write(f"Discovered: {len(companies)}")
        self.stdout.write(f"Enriched:   {len(enriched)}")
        self.stdout.write(f"Validated:  {len(validated)}")
        # 5. Apply if not dry-run
        if not options["dry_run"]:
            backup_portals()
            merge_into_portals(validated)
            import_yaml_to_db()
```

### `discovery.py` (logique LLM)

```python
def discover_companies_via_llm(sector, country, roles, max_companies):
    prompt = f"""List the top {max_companies} {sector} companies in {country}.
Focus on roles: {roles}.
For each company, provide:
1. Company name
2. Official careers page URL
3. Brief description

Return JSON array."""
    response = call_openai(prompt)
    return parse_json(response)
```

### `ats_detector.py` (extrait du scanner)

```python
def detect_ats(careers_url):
    # Patterns existants dans le scanner Python
    if "greenhouse.io" in careers_url:
        return "greenhouse", extract_greenhouse_slug(careers_url)
    if "lever.co" in careers_url:
        return "lever", extract_lever_slug(careers_url)
    if "ashbyhq.com" in careers_url:
        return "ashby", extract_ashby_slug(careers_url)
    if "myworkdayjobs.com" in careers_url:
        return "workday", extract_workday_endpoint(careers_url)
    if "smartrecruiters.com" in careers_url:
        return "smartrecruiters", extract_smartrecruiters_slug(careers_url)
    return None, None  # Custom portal, needs Playwright
```

---

## Approche B — Skill Agent (detail)

### `portal-discovery/SKILL.md`

```markdown
# Portal Discovery Skill

Automatically discover companies and add them to portals.yml.

## When to use
When the user asks to:
- "Find companies in sector X"
- "Add pharma companies to portals"
- "Discover medical device companies in France"

## Workflow

1. Ask user: sector, country, max companies
2. Web search: "top {sector} companies {country} careers page"
3. For each company (max {max_companies}):
   a. browser_navigate to careers_url
   b. browser_snapshot to detect ATS
   c. If Greenhouse/Lever/Ashby detected:
      - Extract API URL
      - HTTP HEAD verify
   d. If custom portal:
      - Note as "scan_method: websearch"
4. Build YAML entries
5. Show diff to user for confirmation
6. Append to config/portals.yml
7. Run `verify:portals` to validate
```

---

## Prochaines etapes

- [ ] Decision : quelle(s) approche(s) implementer ?
- [ ] Phase 1 : `discover_portals` management command
- [ ] Phase 1 : `ats_detector.py` (extraction du scanner)
- [ ] Phase 2 : Skill portal-discovery
- [ ] Phase 3 : API endpoint
