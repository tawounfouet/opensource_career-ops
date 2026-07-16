# Plan d'action - Module portefeuille de competences avec LLM

## Objectif

Construire un module Django + Next.js permettant a l'utilisateur de piloter son portefeuille de competences a partir de ses experiences professionnelles, personnelles, scolaires, associatives et projets.

Le module doit aider l'utilisateur a :

- lister ses experiences ;
- extraire les savoirs, savoir-faire et savoir-etre associes ;
- formuler les competences avec une phrase claire ;
- associer chaque competence a une preuve concrete ;
- evaluer le niveau de maitrise ;
- identifier les ecarts par rapport aux metiers cibles ;
- definir un plan d'action pour progresser ;
- reutiliser ce portefeuille dans le CV, les candidatures, les entretiens et le matching d'offres.

Le LLM intervient comme assistant de structuration, reformulation et questionnement. Il ne doit jamais inventer une competence, un resultat ou une preuve qui n'est pas rattache a une experience fournie par l'utilisateur ou deja presente dans les sources autorisees.

## Principe directeur

Le systeme doit rester fidele a la regle existante de career-ops :

> Keywords get reformulated, never fabricated.

Pour ce module, la variante devient :

> Les competences sont formalisees, jamais inventees.

Une competence ne peut etre consideree comme exploitable dans un CV, une lettre, un entretien ou une reponse de formulaire que si elle est reliee a :

- une experience source ;
- une situation precise ;
- une action observable ;
- un contexte ;
- une preuve ou un resultat ;
- un niveau de maitrise justifie.

## Positionnement produit

Ce module n'est pas seulement une liste de skills. C'est un outil de clarification professionnelle.

Il doit repondre a quatre besoins :

- Introspection : aider l'utilisateur a retrouver ce qu'il sait faire a partir de son parcours.
- Structuration : transformer des experiences brutes en competences formulables.
- Preuve : rattacher chaque competence a une realisation, un livrable, un feedback ou un resultat.
- Activation : reutiliser les competences dans discovery, evaluation d'offres, CV, entretien et plans d'upskilling.

## Perimetre V1

La V1 doit couvrir un workflow complet mais minimal :

1. L'utilisateur ajoute ou importe ses experiences.
2. Le systeme propose des competences candidates via LLM.
3. L'utilisateur valide, modifie ou rejette chaque competence.
4. Le systeme classe les competences en savoirs, savoir-faire, savoir-etre.
5. L'utilisateur attribue un niveau de maitrise.
6. Le systeme demande ou propose des preuves.
7. Le portefeuille devient consultable et exportable.
8. Les competences validees deviennent disponibles pour le matching d'offres et la preparation d'entretien.

## Hors perimetre V1

- Pas de certification automatique d'un niveau expert.
- Pas d'enrichissement depuis LinkedIn sans import explicite de l'utilisateur.
- Pas d'ecriture automatique dans `cv.md`.
- Pas de claims publics sans validation utilisateur.
- Pas de multi-user/auth tant que l'application reste locale ou mono-utilisateur.
- Pas de scraping de donnees personnelles externes.
- Pas de scoring psychometrique opaque.

## Donnees utilisateur et data contract

Les donnees du portefeuille sont des donnees personnelles. Elles doivent etre traitees comme User Layer.

Emplacement recommande :

```text
data/skills-portfolio/
  experiences.json
  competencies.json
  evidence.json
  development-plan.json
  snapshots/
```

Alternative francophone :

```text
data/competences/
```

Recommandation : utiliser `data/skills-portfolio/` pour rester compatible avec le vocabulaire technique du code, tout en affichant "Portefeuille de competences" dans l'UI.

A ajouter au `DATA_CONTRACT.md` lors de l'implementation :

```markdown
| `data/skills-portfolio/*` | Portefeuille de competences utilisateur : experiences, competences validees, preuves, niveaux de maitrise, plans d'action. Donnees personnelles, jamais auto-updated. |
```

## Sources autorisees pour generer des competences

Le LLM peut s'appuyer uniquement sur :

- les experiences saisies dans le module ;
- `cv.md` ;
- `article-digest.md` ;
- `config/profile.yml` ;
- `modes/_profile.md` ;
- `interview-prep/story-bank.md` ;
- `interview-prep/{company}-{role}.md` ;
- `reports/*` uniquement pour extraire les competences observees dans des evaluations deja produites ;
- statements explicites de l'utilisateur dans la conversation courante.

Le LLM ne doit pas utiliser :

- memoires implicites ;
- dossiers hors repo ;
- suppositions sur les metiers ;
- extrapolations du type "a utilise X donc maitrise Y" ;
- claims d'auteur ou de ownership non prouves.

## Modele conceptuel

### Experience

Une experience est un evenement ou une periode significative du parcours.

Champs V1 :

- `id`
- `title`
- `type` : professional, project, education, volunteer, personal, travel, cultural, other
- `organization`
- `start_date`
- `end_date`
- `location`
- `description`
- `missions`
- `responsibilities`
- `deliverables`
- `outcomes`
- `tools`
- `people_context`
- `source_refs`
- `created_at`
- `updated_at`

### Competence

Une competence est une capacite actionnable, contextualisee et prouvable.

Champs V1 :

- `id`
- `label`
- `formulation`
- `category` : knowledge, hard_skill, soft_skill
- `action_verb`
- `object`
- `context`
- `experience_ids`
- `evidence_ids`
- `mastery_level` : beginner, junior, confirmed, expert
- `mastery_rationale`
- `confidence` : low, medium, high
- `status` : draft, validated, rejected, archived
- `tags`
- `market_keywords`
- `created_by` : user, llm, import
- `created_at`
- `updated_at`

Formulation cible :

```text
Je suis capable de {verbe d'action} {objet} dans {contexte}, comme le montre {preuve}.
```

### Preuve

Une preuve justifie une competence.

Champs V1 :

- `id`
- `type` : deliverable, metric, feedback, certificate, portfolio_link, report, story, document, other
- `title`
- `description`
- `url`
- `file_path`
- `metric`
- `source_experience_id`
- `trust_level` : user_confirmed, imported, inferred_pending_review
- `created_at`

### Plan d'action

Un plan d'action sert a developper une competence.

Champs V1 :

- `id`
- `competency_id`
- `target_level`
- `reason`
- `actions`
- `resources`
- `deadline`
- `status`
- `review_notes`

## Niveaux de maitrise

Utiliser quatre niveaux lisibles et compatibles avec la methode fournie :

- Debutant : maitrise des taches simples, besoin d'accompagnement.
- Junior : maitrise de la plupart des taches, progression necessaire.
- Confirme : autonomie solide, capable d'aider ou tutorer sur des cas standards.
- Expert : capable de former, structurer, faire progresser d'autres personnes, traiter des cas complexes.

Le niveau doit toujours avoir une justification :

- preuve ;
- livrable ;
- resultat ;
- repetition dans plusieurs contextes ;
- feedback ;
- autonomie observee.

## Architecture Django

Nouvelle app recommandee :

```text
backend/apps/skills_portfolio/
  __init__.py
  apps.py
  models.py
  serializers.py
  urls.py
  views.py
  admin.py
  services/
    extraction.py
    prompting.py
    validation.py
    matching.py
    exports.py
    llm_client.py
  management/commands/
    seed_skills_portfolio.py
    import_cv_experiences.py
    export_skills_portfolio.py
```

### Modeles Django

Modeles V1 :

- `SkillExperience`
- `SkillCompetency`
- `SkillEvidence`
- `SkillDevelopmentAction`
- `SkillExtractionRun`

Relations :

- une experience peut produire plusieurs competences ;
- une competence peut etre rattachee a plusieurs experiences ;
- une competence doit avoir zero ou plusieurs preuves en draft, au moins une preuve pour passer en validated ;
- une competence peut avoir plusieurs actions de developpement ;
- chaque run LLM doit etre trace pour audit.

### Audit LLM

Chaque appel LLM doit creer une trace :

- prompt template utilise ;
- model ;
- provider ;
- input hash ;
- output JSON brut ;
- cout estime ;
- statut ;
- erreurs ;
- date.

Ne pas stocker les API keys.

## API Django V1

Endpoints proposes :

```text
GET    /api/skills/experiences
POST   /api/skills/experiences
GET    /api/skills/experiences/{id}
PATCH  /api/skills/experiences/{id}
DELETE /api/skills/experiences/{id}

GET    /api/skills/competencies
POST   /api/skills/competencies
GET    /api/skills/competencies/{id}
PATCH  /api/skills/competencies/{id}
POST   /api/skills/competencies/{id}/validate
POST   /api/skills/competencies/{id}/reject

GET    /api/skills/evidence
POST   /api/skills/evidence
PATCH  /api/skills/evidence/{id}

POST   /api/skills/llm/extract-from-experience
POST   /api/skills/llm/formalize-competency
POST   /api/skills/llm/suggest-evidence-questions
POST   /api/skills/llm/benchmark-role
POST   /api/skills/llm/development-plan

GET    /api/skills/dashboard
GET    /api/skills/export/json
GET    /api/skills/export/markdown
```

## API Next.js

Ajouter un proxy :

```text
web/src/app/api/skills/[...path]/route.ts
```

Meme strategie que discovery :

- proxy Django si `CAREER_OPS_API_URL` est defini ;
- fallback local via `backend/manage.py shell` pour les routes essentielles en local ;
- erreurs JSON lisibles ;
- timeout plus long pour LLM.

## Integration LLM

### Providers

Supporter une API compatible OpenAI en priorite :

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_TIMEOUT_MS`

Le systeme doit pouvoir utiliser :

- OpenAI ;
- OpenRouter ;
- Mistral via endpoint compatible si configure ;
- modele local compatible OpenAI ;
- autre endpoint compatible.

### Service Django

Creer un service :

```text
backend/apps/skills_portfolio/services/llm_client.py
```

Responsabilites :

- construire l'endpoint ;
- verifier HTTPS hors localhost ;
- refuser un provider distant sans API key ;
- appliquer timeout ;
- parser JSON ;
- retourner une erreur actionnable ;
- tracer le cout si disponible.

### Reponse structuree obligatoire

Tous les appels LLM doivent demander une sortie JSON stricte.

Exemple schema extraction :

```json
{
  "competencies": [
    {
      "label": "Concevoir une API Django",
      "category": "hard_skill",
      "formulation": "Je suis capable de concevoir une API Django pour exposer des donnees metier dans un produit web.",
      "action_verb": "concevoir",
      "object": "une API Django",
      "context": "dans un produit web",
      "evidence_questions": [
        "Quel endpoint avez-vous livre ?",
        "Quel utilisateur ou systeme consommait cette API ?",
        "Quel resultat concret peut le prouver ?"
      ],
      "source_fragments": [
        "..."
      ],
      "confidence": "medium"
    }
  ],
  "missing_context_questions": []
}
```

### Guardrails prompts

Chaque prompt LLM doit inclure :

```text
Tu aides l'utilisateur a formaliser ses competences.
Tu ne dois jamais inventer une experience, un resultat, une preuve, une metrique ou une responsabilite.
Si une competence semble probable mais non prouvee, marque-la en confidence=low et pose une question.
Chaque competence doit etre reliee a un fragment source.
Reformule uniquement ce qui est soutenu par les donnees fournies.
Retourne uniquement du JSON valide.
```

## Workflows utilisateur

### Workflow 1 - Onboarding portefeuille

1. L'utilisateur ouvre `/skills`.
2. Le systeme explique la methode : experiences -> competences -> preuves -> niveau -> plan d'action.
3. L'utilisateur choisit une source :
   - importer depuis `cv.md` ;
   - saisir une experience ;
   - partir d'un projet ;
   - partir d'un entretien/story-bank ;
   - partir d'un rapport existant.
4. Le LLM propose des experiences ou competences candidates.
5. L'utilisateur valide ou corrige.

### Workflow 2 - Extraction depuis une experience

1. L'utilisateur decrit une experience librement.
2. Le LLM extrait :
   - missions ;
   - actions ;
   - livrables ;
   - resultats ;
   - savoirs ;
   - savoir-faire ;
   - savoir-etre ;
   - questions manquantes.
3. L'utilisateur complete les trous.
4. Le systeme cree les competences en draft.

### Workflow 3 - Validation d'une competence

1. L'utilisateur ouvre une competence draft.
2. Le systeme affiche :
   - formulation ;
   - categorie ;
   - experience source ;
   - preuve associee ;
   - niveau propose ;
   - niveau de confiance.
3. L'utilisateur peut :
   - valider ;
   - modifier ;
   - rejeter ;
   - demander une reformulation ;
   - ajouter une preuve.

### Workflow 4 - Evaluation du niveau

1. Le systeme propose un niveau initial.
2. Il affiche la justification.
3. Il pose les questions manquantes :
   - avez-vous travaille seul ?
   - combien de fois avez-vous realise cette action ?
   - avez-vous forme quelqu'un ?
   - quel resultat concret ?
   - avez-vous un livrable ?
4. L'utilisateur confirme.

### Workflow 5 - Benchmark metier

1. L'utilisateur choisit un role cible.
2. Le systeme compare les competences validees aux competences attendues du role.
3. Le LLM peut aider a normaliser les intitules, mais les ecarts restent deterministes.
4. Sortie :
   - competences fortes ;
   - competences transferables ;
   - competences a prouver ;
   - competences a developper ;
   - plan d'action.

### Workflow 6 - Activation candidature

Le portefeuille alimente :

- evaluation d'offres ;
- CV tailoring ;
- preparation d'entretien ;
- reponses de formulaire ;
- lettres de motivation ;
- outreach recruteur.

Regle stricte :

- seules les competences `validated` peuvent etre utilisees comme claims forts ;
- les competences `draft` peuvent seulement generer des questions ou etre proposees pour validation ;
- les competences `low confidence` ne doivent jamais etre injectees dans un CV sans confirmation.

## UI Next.js

Pages proposees :

```text
/skills
/skills/experiences
/skills/experiences/new
/skills/experiences/[id]
/skills/competencies
/skills/competencies/[id]
/skills/benchmark
/skills/action-plan
```

### `/skills`

Dashboard :

- nombre d'experiences ;
- nombre de competences draft/validated ;
- repartition savoirs/savoir-faire/savoir-etre ;
- couverture par role cible ;
- competences sans preuve ;
- actions de developpement en cours.

### `/skills/experiences`

Vue liste :

- titre ;
- type ;
- periode ;
- competences associees ;
- preuves ;
- statut d'analyse.

### `/skills/experiences/new`

Assistant guide :

- champ libre ;
- type d'experience ;
- contexte ;
- missions ;
- resultats ;
- bouton "Analyser avec l'IA" ;
- preview des competences candidates.

### `/skills/competencies`

Kanban ou table :

- Draft ;
- A prouver ;
- Validees ;
- A developper ;
- Archivees.

Filtres :

- categorie ;
- niveau ;
- role cible ;
- preuve manquante ;
- source ;
- statut.

### `/skills/competencies/[id]`

Detail :

- formulation ;
- source ;
- preuves ;
- niveau ;
- historique ;
- reformulations LLM ;
- bouton "utilisable CV" seulement si validated.

### `/skills/benchmark`

Vue comparaison role cible :

- role vise ;
- competences attendues ;
- competences presentes ;
- ecarts ;
- preuves insuffisantes ;
- plan d'action propose.

## Experience utilisateur attendue

Le ton doit etre celui d'un coach exigeant, pas d'un generateur de buzzwords.

Exemples de microcopy :

- "Cette competence est plausible, mais pas encore prouvee."
- "Ajoute un livrable, un resultat ou une situation precise avant de l'utiliser dans ton CV."
- "La formulation est trop generale. Precise le contexte."
- "Cette preuve justifie un niveau confirme, pas expert."
- "Ce savoir-etre doit etre illustre par une situation vecue."

## Taxonomie V1

### Savoirs

Connaissances :

- domaines ;
- methodes ;
- frameworks conceptuels ;
- normes ;
- regulations ;
- marche ;
- architecture ;
- metiers.

### Savoir-faire

Capacites operationnelles :

- concevoir ;
- developper ;
- analyser ;
- automatiser ;
- piloter ;
- documenter ;
- tester ;
- deployer ;
- mesurer ;
- optimiser ;
- former ;
- negocier.

### Savoir-etre

Comportements en situation :

- rigueur ;
- autonomie ;
- communication ;
- collaboration ;
- adaptabilite ;
- pedagogie ;
- leadership ;
- esprit critique ;
- resilience ;
- sens de l'organisation ;
- responsabilite ;
- curiosite.

## Verbes d'action

Prevoir une liste systeme de verbes par domaine :

- analyser ;
- concevoir ;
- developper ;
- automatiser ;
- structurer ;
- piloter ;
- coordonner ;
- prioriser ;
- presenter ;
- documenter ;
- former ;
- negocier ;
- diagnostiquer ;
- optimiser ;
- securiser ;
- deployer ;
- mesurer ;
- accompagner ;
- faciliter ;
- arbitrer.

Fichier recommande :

```text
backend/apps/skills_portfolio/data/action_verbs.json
```

## Matching avec offres d'emploi

Le module doit permettre d'enrichir discovery et evaluation d'offres.

### Input

- competences validees ;
- competences a developper ;
- role cible ;
- job description.

### Output

- competences correspondantes ;
- competences transferables ;
- preuves utilisables ;
- gaps ;
- risques de survente ;
- questions a poser au recruteur ;
- arguments CV/interview.

### Regle

Le matching peut reformuler une competence pour coller au vocabulaire de l'offre, mais ne peut pas ajouter une nouvelle competence non presente dans le portefeuille.

## Integration avec modules existants

### CV

Le module peut proposer des ajouts a `cv.md`, mais jamais les appliquer sans validation explicite.

Workflow :

1. competence validated ;
2. preuve solide ;
3. proposition de bullet CV ;
4. preview diff ;
5. validation utilisateur ;
6. modification de `cv.md`.

### Discovery

Utiliser le portefeuille pour ameliorer :

- `positive_keywords` du `SearchProfile` ;
- `target_titles` ;
- filtres de rejet ;
- explications de fit.

Ne pas synchroniser automatiquement. Proposer des suggestions.

### Evaluation d'offres

Ajouter une section :

```text
Competences prouvees mobilisables
Competences transferables
Competences manquantes ou faibles
Risques de survente
```

### Interview

Alimenter :

- STAR stories ;
- exemples comportementaux ;
- "parlez-moi d'une fois ou..." ;
- questions de clarification.

### Upskill

Relier les gaps identifies dans `upskill.mjs` aux competences du portefeuille.

## Mode agent propose

Ajouter un mode :

```text
modes/skills.md
modes/fr/competences.md
```

Route career-ops :

```text
/career-ops skills
/career-ops competences
```

Le mode doit :

- charger les sources autorisees ;
- aider a formaliser ;
- poser des questions ;
- produire JSON/Markdown ;
- ne jamais modifier `cv.md` sans validation.

## Prompt templates V1

### Extraction depuis experience

Input :

- description libre ;
- type d'experience ;
- contexte ;
- sources existantes.

Output JSON :

- experience normalisee ;
- competences candidates ;
- preuves candidates ;
- questions manquantes.

### Reformulation competence

Input :

- competence brute ;
- experience ;
- preuve ;
- niveau.

Output JSON :

- formulation courte ;
- formulation CV ;
- formulation entretien ;
- formulation LinkedIn ;
- risques de survente.

### Questions de preuve

Input :

- competence candidate.

Output JSON :

- questions pour verifier ;
- types de preuves possibles ;
- niveau maximal justifiable sans preuve supplementaire.

### Plan de developpement

Input :

- competence ;
- niveau actuel ;
- niveau cible ;
- role cible.

Output JSON :

- actions ;
- ressources ;
- mini-projets ;
- criteres de validation ;
- delai recommande.

## Securite, confidentialite et couts

### Donnees envoyees au LLM

Afficher clairement :

- quelles donnees sont envoyees ;
- a quel provider ;
- quel modele ;
- quelle finalite.

Pour la V1 locale, une mention dans l'UI suffit :

```text
Cette action envoie le texte de l'experience et les sources selectionnees au modele configure.
```

### Mode local/private

Permettre :

- endpoint local compatible OpenAI ;
- desactivation complete du LLM ;
- fallback manuel.

### Cout

Tracer :

- tokens input/output si disponibles ;
- nombre d'appels ;
- cout estime ;
- modele utilise.

## Qualite et tests

### Tests backend

- creation experience ;
- creation competence ;
- validation impossible sans preuve ;
- extraction LLM mockee ;
- parsing JSON robuste ;
- refus de sortie non JSON ;
- provider distant sans HTTPS refuse ;
- provider distant sans API key refuse ;
- export markdown ;
- permissions mono-user/local.

### Tests frontend

- chargement dashboard ;
- creation experience ;
- affichage competences candidates ;
- validation/rejet ;
- edition niveau ;
- message d'erreur LLM ;
- sauvegarde sans LLM.

### Golden tests prompts

Creer des fixtures :

```text
backend/tests/fixtures/skills_portfolio/
  experience_backend_project.json
  llm_extraction_response.json
  invalid_llm_response.txt
```

Verifier que :

- le LLM ne peut pas produire une competence sans source fragment ;
- une competence sans preuve reste draft ;
- les categories sont normalisees.

## Migration progressive

### Phase 0 - Cadrage documentaire

- Creer ce plan.
- Ajouter `data/skills-portfolio/*` au Data Contract.
- Ajouter le mode `skills` dans la roadmap.

### Phase 1 - Backend deterministe

- Creer app Django `skills_portfolio`.
- Ajouter modeles.
- Ajouter serializers.
- Ajouter API CRUD.
- Ajouter admin.
- Ajouter tests.
- Ajouter exports JSON/Markdown.

Livrable attendu :

- l'utilisateur peut saisir experiences, competences, preuves sans LLM.

### Phase 2 - UI CRUD

- Ajouter nav item `Skills` ou `Competences`.
- Ajouter dashboard `/skills`.
- Ajouter creation/edition experiences.
- Ajouter liste competences.
- Ajouter validation/rejet.

Livrable attendu :

- portefeuille pilotable manuellement depuis Next.

### Phase 3 - LLM extraction assistee

- Ajouter `llm_client.py`.
- Ajouter prompts JSON.
- Ajouter endpoint extraction.
- Ajouter preview avant sauvegarde.
- Ajouter audit run.
- Ajouter tests avec LLM mocke.

Livrable attendu :

- l'utilisateur decrit une experience et recoit des competences candidates modifiables.

### Phase 4 - Preuves et niveaux

- Ajouter workflow de preuve.
- Ajouter evaluation de niveau.
- Ajouter questions manquantes.
- Bloquer `validated` sans preuve.

Livrable attendu :

- competences fiables, defendables en entretien.

### Phase 5 - Benchmark role cible

- Ajouter saisie role cible.
- Importer attentes depuis une JD ou un titre.
- Comparer competences validees vs attendues.
- Generer plan d'action.

Livrable attendu :

- l'utilisateur sait quelles competences mettre en avant et lesquelles developper.

### Phase 6 - Integration career-ops

- Brancher avec evaluation d'offres.
- Brancher avec CV tailoring.
- Brancher avec interview-prep.
- Brancher avec upskill.
- Proposer des updates de `SearchProfile` discovery.

Livrable attendu :

- le portefeuille devient une source centrale du job-search pipeline.

### Phase 7 - Auth plus tard

Seulement si l'application devient multi-utilisateur :

- ajouter relation `owner`;
- isoler les portfolios ;
- permissions API ;
- chiffrement optionnel ;
- export/suppression des donnees.

## Definition of Done V1

Le module est considere fonctionnel en V1 si :

- l'utilisateur peut creer au moins 5 experiences ;
- chaque experience peut produire des competences candidates ;
- chaque competence a une categorie ;
- chaque competence peut avoir une preuve ;
- une competence ne peut etre validee sans preuve ;
- le niveau de maitrise est stocke et justifie ;
- le portefeuille peut etre exporte en Markdown ;
- les appels LLM sont audites ;
- le systeme fonctionne sans LLM en mode manuel ;
- aucune competence non validee n'est injectee automatiquement dans le CV.

## Risques principaux

### Survente du profil

Risque : le LLM transforme une experience simple en competence trop senior.

Mitigation :

- source fragments obligatoires ;
- confidence ;
- validation utilisateur ;
- preuve obligatoire ;
- niveau maximal justifie.

### Competences trop generiques

Risque : produire "communication", "leadership", "teamwork" sans contexte.

Mitigation :

- formulation avec action + objet + contexte ;
- rejet automatique des formulations sans verbe d'action ;
- questions de clarification.

### Cout LLM

Risque : appels trop frequents.

Mitigation :

- preview locale ;
- batch extraction ;
- cache input hash ;
- model configurable ;
- mode manuel.

### Confidentialite

Risque : envoyer trop de donnees personnelles au provider.

Mitigation :

- selection explicite des sources ;
- avertissement UI ;
- endpoint local possible ;
- minimisation du contexte.

## Recommandation d'implementation immediate

Commencer par une tranche minimale :

1. Ajouter `DATA_CONTRACT.md` pour `data/skills-portfolio/*`.
2. Creer app Django `skills_portfolio`.
3. Implementer `SkillExperience`, `SkillCompetency`, `SkillEvidence`.
4. Ajouter CRUD API.
5. Ajouter page `/skills` + `/skills/experiences/new`.
6. Ajouter endpoint LLM mockable `extract-from-experience`.
7. Ajouter un premier prompt JSON strict.
8. Bloquer la validation sans preuve.

Ne pas commencer par le benchmark role cible. La valeur de base vient d'abord de la formalisation fiable des experiences.

## Exemple de sortie Markdown exportee

```markdown
# Portefeuille de competences

## Experience - Projet Django Discovery

Contexte : implementation d'un module de collecte et scoring d'offres.

### Competences validees

- Je suis capable de concevoir une API Django REST pour exposer un digest d'offres classees, dans un contexte de produit web local.
  - Categorie : savoir-faire
  - Niveau : confirme
  - Preuve : endpoints discovery + tests API

- Je suis capable de structurer un workflow deterministe de decision utilisateur avant toute automatisation IA.
  - Categorie : savoir-faire
  - Niveau : confirme
  - Preuve : workflow digest, decisions, export pipeline

### Competences a prouver

- Je suis capable de piloter une strategie multi-source de collecte jobboards en respectant les CGU.
  - Preuve manquante : documentation d'activation et logs de run sur sources reelles
```

## Questions a trancher avant implementation

- Nom public : `Skills`, `Competences`, ou `Portefeuille` ?
- Dossier donnees : `data/skills-portfolio/` ou `data/competences/` ?
- Provider LLM par defaut : OpenAI-compatible uniquement ou integration providers existants Node ?
- Le portefeuille doit-il rester fichier-first, DB-first, ou hybride DB + export user-layer ?
- Les experiences doivent-elles etre importees depuis `cv.md` automatiquement ou seulement sur action utilisateur ?

