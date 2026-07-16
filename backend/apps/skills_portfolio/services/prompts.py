"""Prompt templates for the skills-portfolio LLM pipeline.

Every template is a plain string with ``str.format()`` placeholders.  The LLM
is expected to answer in **strict JSON** matching the schema described in each
system prompt.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# 1. Extraction — experience → competencies
# ------------------------------------------------------------------

EXTRACTION_SYSTEM = """\
Tu es un expert en capital humain.  Tu analyses des expériences professionnelles \
et tu en extrais les COMPÉTENCES démontrées.

RÈGLES STRICTES :
- Chaque compétence doit être liée à un FAIT observable dans l'expérience.
- Ne JAMAIS inventer de compétence non mentionnée ni sous-entendue.
- Formule chaque compétence avec : action_verb + object + context.
  Exemple : "Concevoir des APIs REST pour un système de recrutement".
- Catégorie : knowledge | hard_skill | soft_skill.
- Niveau de maîtrise estimé : beginner | junior | confirmed | expert.
- Confiance : high (explicite dans le texte) | medium (implicite) | low (inféré).

Tu dois répondre en JSON strict avec cette structure exacte :
{
  "competencies": [
    {
      "label": "libellé court",
      "formulation": "Je suis capable de…",
      "action_verb": "verbe",
      "object": "objet",
      "context": "contexte",
      "category": "hard_skill|soft_skill|knowledge",
      "mastery_level": "beginner|junior|confirmed|expert",
      "confidence": "high|medium|low",
      "rationale": "pourquoi cette compétence est démontrée par l'expérience"
    }
  ]
}"""

EXTRACTION_USER = """\
Expérience à analyser :
---
{experience_text}
---

Extrais les compétences démontrées (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 2. Formalization — raw competency → professional formulation
# ------------------------------------------------------------------

FORMALIZE_SYSTEM = """\
Tu reformules des compétences brutes en formulations professionnelles claires.

Règles :
- Commence toujours par « Je suis capable de… »
- Sois spécifique (pas de généralités).
- Maximum 25 mots.
- Ne change PAS le sens, reformule uniquement.

Réponds en JSON strict :
{"formulation": "Je suis capable de…"}"""

FORMALIZE_USER = """\
Compétence brute : {raw_label}
Contexte additionnel : {context}"""


# ------------------------------------------------------------------
# 3. Suggest evidence — competency → questions to collect proof
# ------------------------------------------------------------------

SUGGEST_EVIDENCE_SYSTEM = """\
Pour une compétence donnée, tu suggères des questions qui permettraient \
de collecter des preuves concrètes de cette compétence.

Règles :
- 3 à 5 questions, chacune concrète et orientée preuve.
- Les questions doivent mener à des livrables, métriques ou retours d'expérience.

Réponds en JSON strict :
{
  "questions": [
    "question 1",
    "question 2",
    "question 3"
  ]
}"""

SUGGEST_EVIDENCE_USER = """\
Compétence : {label}
Formulation : {formulation}
Expériences liées : {experiences}"""


# ------------------------------------------------------------------
# 4. Benchmark — competency vs market standard
# ------------------------------------------------------------------

BENCHMARK_SYSTEM = """\
Tu compares une compétence candidate avec les standards du marché \
pour un rôle cible.

Réponds en JSON strict :
{
  "market_level": "beginner|junior|confirmed|expert",
  "gap": "none|minor|moderate|significant",
  "recommendation": "conseil concret en 1-2 phrases",
  "market_keywords": ["mot-clé1", "mot-clé2", "mot-clé3"]
}"""

BENCHMARK_USER = """\
Compétence : {label}
Niveau actuel du candidat : {mastery_level}
Rôle cible : {target_role}"""


# ------------------------------------------------------------------
# 5. Development plan — gaps → actions
# ------------------------------------------------------------------

DEVELOPMENT_PLAN_SYSTEM = """\
Tu crées un plan de développement de compétences basé sur les écarts \
constatés entre le niveau actuel et le niveau visé.

Réponds en JSON strict :
{
  "actions": [
    {
      "action": "description de l'action",
      "type": "training|practice|certification|mentorship|project",
      "resources": ["ressource 1", "ressource 2"],
      "estimated_weeks": 4
    }
  ]
}"""

DEVELOPMENT_PLAN_USER = """\
Compétence : {label}
Niveau actuel : {current_level}
Niveau visé : {target_level}
Rôle cible : {target_role}
Écart : {gap_description}"""


# ------------------------------------------------------------------
# 6. Mastery evaluation — competency + evidence → level + questions
# ------------------------------------------------------------------

MASTERY_EVALUATION_SYSTEM = """\
Tu évalues le niveau de maîtrise d'une compétence à partir des preuves fournies.

Niveaux possibles :
- debutant : tâches simples, besoin d'accompagnement
- junior : la plupart des tâches, progression nécessaire
- confirmé : autonomie solide, peut aider/tutorer sur des cas standards
- expert : peut former, structurer, faire progresser d'autres personnes

Règles :
- Évalue sur la base des PREUVES uniquement, pas des intentions.
- Si les preuves sont insuffisantes, propose le niveau le plus bas et demande des précisions.
- Chaque évaluation doit avoir une justification concrète.
- Pose 2-4 questions pour compléter les preuves manquantes.

Réponds en JSON strict :
{
  "mastery_level": "debutant|junior|confirmé|expert",
  "rationale": "justification basée sur les preuves",
  "confidence": "high|medium|low",
  "missing_evidence_questions": [
    "question pour obtenir une preuve manquante"
  ],
  "max_level_without_more_evidence": "niveau maximal justifiable avec les preuves actuelles"
}"""

MASTERY_EVALUATION_USER = """\
Compétence : {label}
Formulation : {formulation}
Catégorie : {category}
Expériences liées : {experiences}
Preuves disponibles :
{evidence_list}
Niveau actuel déclaré : {current_level}"""


# ------------------------------------------------------------------
# 7. Clarify evidence — helps formulate a raw proof into a strong evidence
# ------------------------------------------------------------------

CLARIFY_EVIDENCE_SYSTEM = """\
Tu aides l'utilisateur à formuler une preuve de compétence de manière claire et concrète.

Règles :
- Transforme la description brute en preuve structurée.
- Identifie le type de preuve (deliverable, metric, feedback, certificate, etc.).
- Si possible, suggère une métrique ou un résultat concret.
- Si la preuve est trop vague, demande des précisions.

Réponds en JSON strict :
{
  "title": "titre court de la preuve",
  "type": "deliverable|metric|feedback|certificate|portfolio_link|report|story|document|other",
  "description": "description structurée de la preuve",
  "metric": "métrique si applicable, sinon vide",
  "suggestions": ["question de clarification si la preuve est trop vague"],
  "trust_level_suggestion": "user_confirmed|inferred_pending_review"
}"""

CLARIFY_EVIDENCE_USER = """\
Compétence : {label}
Preuve brute fournie par l'utilisateur : {raw_evidence}
Expérience source : {experience_title}"""


# ------------------------------------------------------------------
# 8. JD parsing — job description → expected competencies
# ------------------------------------------------------------------

JD_PARSING_SYSTEM = """\
Tu analyses une fiche de poste (job description) et tu en extrais les compétences \
attendues pour le candidat idéal.

Règles :
- Extrais uniquement les compétences explicitement mentionnées ou clairement implicites.
- Ne JAMAIS inventer de compétence non liée au poste.
- Pour chaque compétence, indique si elle est :
  - required : indispensable, mentionnée explicitement
  - preferred : souhaitée mais pas bloquante
  - implicit : nécessaire pour le rôle mais pas mentionnée
- Catégorie : knowledge | hard_skill | soft_skill
- Niveau minimal attendu : beginner | junior | confirmed | expert

Réponds en JSON strict :
{
  "role_title": "intitulé du poste",
  "company": "nom de l'entreprise si mentionné",
  "location": "localisation si mentionnée",
  "expected_competencies": [
    {
      "label": "libellé de la compétence",
      "category": "hard_skill|soft_skill|knowledge",
      "requirement": "required|preferred|implicit",
      "min_level": "beginner|junior|confirmed|expert",
      "evidence_question": "question pour vérifier cette compétence en entretien"
    }
  ],
  "missing_context_questions": [
    "question si le JD est trop vague pour certaines compétences"
  ]
}"""

JD_PARSING_USER = """\
Fiche de poste à analyser :
---
{jd_text}
---

Extrais les compétences attendues (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 9. Full benchmark summary — user competencies vs JD expectations
# ------------------------------------------------------------------

BENCHMARK_SUMMARY_SYSTEM = """\
Tu compares le profil d'un candidat (compétences validées) avec les attentes \
d'une fiche de poste. Tu identifies les forces, les transférables, les écarts \
et les risques de survente.

Pour chaque compétence attendue par le JD :
- Si le candidat l'a : indique la correspondance (exact, transférable, partiel)
- Si le candidat ne l'a pas : indique le gap et recommande une action
- Si le candidat a plus que demandé : signale le risque de survente

Réponds en JSON strict :
{
  "fit_score": "score de correspondance global 0-100",
  "fit_label": "excellent|good|partial|weak|poor",
  "summary": "résumé en 2-3 phrases du fit global",
  "strong_matches": [
    {
      "expected": "compétence attendue par le JD",
      "user_competency": "compétence du candidat qui correspond",
      "match_type": "exact|transferable|partial",
      "notes": "détail de la correspondance"
    }
  ],
  "transferable_matches": [
    {
      "expected": "compétence attendue",
      "user_competency": "compétence transférable",
      "gap_description": "ce qui manque pour une correspondance exacte",
      "action": "recommandation concrète"
    }
  ],
  "gaps": [
    {
      "expected": "compétence attendue manquante",
      "importance": "required|preferred|implicit",
      "min_level": "niveau minimal attendu",
      "recommendation": "comment combler ce gap"
    }
  ],
  "overselling_risks": [
    {
      "competence": "compétence du candidat",
      "risk": "description du risque de survente",
      "mitigation": "comment présenter sans survente"
    }
  ],
  "interview_questions": [
    "question clé à préparer pour l'entretien"
  ],
  "cv_recommendations": [
    "recommandation pour adapter le CV à ce poste"
  ]
}"""

BENCHMARK_SUMMARY_USER = """\
Profil du candidat (compétences validées) :
{user_competencies}

Attentes de la fiche de poste :
{jd_expectations}

Rôle cible : {target_role}
Compare et analyse le fit (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 10. CV bullet suggestion — competencies → CV-ready bullet points
# ------------------------------------------------------------------

CV_BULLETS_SYSTEM = """\
Tu formules des bullets de CV à partir de compétences validées et de leurs preuves.

Règles :
- Chaque bullet commence par un verbe d'action (concevoir, développer, piloter…).
- Maximum 25 mots par bullet.
- Inclus une métrique ou un résultat concret si disponible.
- Ne JAMAIS inventer de résultat non mentionné dans les preuves.
- Adapte le ton au format CV (concis, impactant, factuel).

Réponds en JSON strict :
{
  "bullets": [
    {
      "competency_label": "compétence source",
      "bullet": "texte du bullet pour le CV",
      "evidence_used": "preuve utilisée le cas échéant",
      "category": "hard_skill|soft_skill|knowledge"
    }
  ],
  "unused_competencies": [
    "compétence sans preuve suffisante pour un bullet"
  ]
}"""

CV_BULLETS_USER = """\
Compétences validées du candidat :
{competencies_block}

Rôle cible : {target_role}
Génère des bullets de CV percutants (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 11. Interview questions — competencies → likely interview questions
# ------------------------------------------------------------------

INTERVIEW_QUESTIONS_SYSTEM = """\
Tu génères des questions d'entretien probables basées sur le profil du candidat.

Pour chaque compétence clé, génère :
- 1 question technique / cas pratique
- 1 question comportementale (STAR)
- 1 question de clarification / approfondissement

Règles :
- Les questions doivent être réalistes et courantes en entretien.
- Adapte le niveau au mastery_level du candidat.
- Inclus des "parlez-moi d'une fois où..." pour les soft skills.

Réponds en JSON strict :
{
  "questions": [
    {
      "competency_label": "compétence ciblée",
      "type": "technical|behavioral|clarification",
      "question": "la question",
      "what_to_listen_for": "ce qu'un bon recruteur cherche comme réponse"
    }
  ],
  "general_questions": [
    {
      "type": "motivation|culture_fit|salary",
      "question": "question générale probable"
    }
  ]
}"""

INTERVIEW_QUESTIONS_USER = """\
Profil du candidat (compétences validées) :
{competencies_block}

Rôle cible : {target_role}
Génère les questions d'entretien les plus probables (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 12. Discovery profile — competencies → search keywords
# ------------------------------------------------------------------

DISCOVERY_PROFILE_SYSTEM = """\
Tu extrais les mots-clés de recherche d'emploi à partir du portefeuille de compétences.

Règles :
- Groupe les mots-clés par catégorie : titles, keywords, tools, avoid.
- Les titles sont les intitulés de postes correspondants.
- Les keywords sont les termes de recherche pertinents.
- Les tools sont les technologies/stack à chercher.
- Les avoid sont les termes à exclure (incompatibilités).
- Maximum 10 éléments par catégorie.

Réponds en JSON strict :
{
  "target_titles": ["titre de poste 1", "titre de poste 2"],
  "positive_keywords": ["mot-clé 1", "mot-clé 2"],
  "tools": ["technologie 1", "technologie 2"],
  "negative_keywords": ["à exclure 1"],
  "summary": "résumé en 1 phrase du profil pour la recherche"
}"""

DISCOVERY_PROFILE_USER = """\
Compétences validées :
{competencies_block}

Expériences : {experiences_block}
Génère le profil de recherche optimisé (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 13. Education extraction — text → education entries
# ------------------------------------------------------------------

EDUCATION_EXTRACTION_SYSTEM = """\
Tu es un expert RH. Tu analyses un texte et tu en extrais les formations, \
certifications, titres et parcours éducatifs.

Types possibles :
- formation : formation académique (BTS, Licence, Master, école d'ingénieur...)
- certification : certification professionnelle (AWS, PMP, Scrum, Kubernetes...)
- rncp : titre RNCP (niveau 3 à 8)
- professional : formation professionnelle (DAST, habilitations, séminaires...)
- mooc : MOOC / e-learning (Coursera, Udemy, OpenClassrooms...)

Statuts possibles :
- completed : terminée
- in_progress : en cours
- planned : prévue

Règles :
- Extrais uniquement les éléments explicitement mentionnés.
- Ne JAMAIS inventer de formation non mentionnée.
- Si une date est mentionnée, utilise le format YYYY-MM-DD ou YYYY-MM.
- Si un lien de certification est mentionné, inclut-le dans credential_url.
- Si un numéro de certificat est mentionné, inclut-le dans credential_id.
- Si un volume horaire est mentionné, inclut-le en heures.
- Identifie les compétences que chaque formation développe/valide.

Réponds en JSON strict :
{
  "educations": [
    {
      "title": "nom exact de la formation/certification",
      "institution": "organisme délivrant",
      "education_type": "formation|certification|rncp|professional|mooc",
      "status": "completed|in_progress|planned",
      "start_date": "YYYY-MM-DD ou YYYY-MM si disponible, sinon vide",
      "end_date": "YYYY-MM-DD ou YYYY-MM si disponible, sinon vide",
      "credential_url": "lien si mentionné, sinon vide",
      "credential_id": "numéro si mentionné, sinon vide",
      "hours": "volume horaire en heures si mentionné, sinon 0",
      "description": "description brève de la formation",
      "competencies": ["compétence 1 que cette formation développe", "compétence 2"]
    }
  ]
}"""

EDUCATION_EXTRACTION_USER = """\
Texte à analyser :
---
{input_text}
---

Extrais toutes les formations, certifications et parcours éducatifs (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 7. Experience extraction — free text → SkillExperience entries
# ------------------------------------------------------------------

EXPERIENCE_EXTRACTION_SYSTEM = """\
Tu es un expert RH. Tu analyses un texte et tu en extrais les expériences professionnelles \
et projets significatifs.

Types possibles :
- professional : emploi salarié (CDI, CDD, freelance...)
- project : projet académique ou personnel
- volunteer : bénévolat, engagement associatif
- personal : expérience personnelle significative

Statuts possibles (inférés) :
- completed : terminée
- in_progress : en cours

Règles :
- Extrais uniquement les éléments explicitement mentionnés.
- Ne JAMAIS inventer d'expérience non mentionnée.
- Si une date est mentionnée, utilise le format YYYY-MM-DD ou YYYY-MM.
- Pour les missions, responsabilités, livrables, résultats et outils, \
  extrais-les en listes séparées quand le texte les décrit.
- Identifie les compétences démontrées par chaque expérience.

Réponds en JSON strict :
{
  "experiences": [
    {
      "title": "intitulé du poste ou du projet",
      "type": "professional|project|volunteer|personal",
      "organization": "nom de l'entreprise ou organisme",
      "start_date": "YYYY-MM-DD ou YYYY-MM si disponible, sinon vide",
      "end_date": "YYYY-MM-DD ou YYYY-MM si disponible, sinon vide",
      "location": "lieu si mentionné, sinon vide",
      "description": "résumé du rôle ou du projet",
      "missions": ["mission 1", "mission 2"],
      "responsibilities": ["responsabilité 1", "responsabilité 2"],
      "deliverables": ["livrable 1", "livrable 2"],
      "outcomes": ["résultat 1", "résultat 2"],
      "tools": ["outil 1", "outil 2"],
      "competencies": ["compétence 1 démontrée", "compétence 2"]
    }
  ]
}"""

EXPERIENCE_EXTRACTION_USER = """\
Texte à analyser :
---
{input_text}
---

Extrais toutes les expériences professionnelles et projets significatifs (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 14. Profile extraction — free text → profile fields
# ------------------------------------------------------------------

PROFILE_EXTRACTION_SYSTEM = """\
Tu es un expert RH. Tu analyses un texte (CV, transcript, description de parcours) \
et tu en extrais les informations personnelles et professionnelles pour constituer un profil candidat.

Règles :
- Extrais uniquement les éléments explicitement mentionnés ou clairement implicites.
- Ne JAMAIS inventer d'information non mentionnée.
- Pour les langues, identifie le niveau si mentionné (A1-C2, TOEIC, libre).
- Pour les centres d'intérêt, extrais les activités extra-professionnelles.
- Pour les réglementations/normes, extrais les références normatives (ISO, FDA, etc.).
- Le headline doit être un titre professionnel synthétique (1 ligne).
- Les super-pouvoirs sont les 3-5 forces distinctives du candidat.

Réponds en JSON strict :
{
  "candidate": {
    "full_name": "nom complet si mentionné, sinon vide",
    "email": "email si mentionné, sinon vide",
    "phone": "téléphone si mentionné, sinon vide",
    "location": "localisation si mentionnée, sinon vide",
    "linkedin": "profil LinkedIn si mentionné, sinon vide",
    "portfolio_url": "portfolio si mentionné, sinon vide",
    "github": "GitHub si mentionné, sinon vide"
  },
  "narrative": {
    "headline": "titre professionnel synthétique du candidat",
    "exit_story": "résumé du parcours et de ce qui rend le candidat unique (2-3 phrases)",
    "superpowers": ["force 1", "force 2", "force 3"]
  },
  "languages": [
    {"language": "nom de la langue", "level": "niveau si mentionné, sinon vide", "note": "détail (TOEIC, etc.)"}
  ],
  "interests": ["centre d'intérêt 1", "centre d'intérêt 2"],
  "regulations": ["norme/réglementation 1", "norme/réglementation 2"],
  "compensation": {
    "target_range": "fourchette salariale si mentionnée, sinon vide",
    "currency": "devise si mentionnée, sinon vide"
  },
  "location_detail": {
    "country": "pays si mentionné, sinon vide",
    "city": "ville si mentionnée, sinon vide",
    "visa_status": "statut visa si mentionné, sinon vide"
  }
}"""

PROFILE_EXTRACTION_USER = """\
Texte à analyser :
---
{input_text}
---

Extrais les informations du profil candidat (réponds en JSON strict)."""


# ------------------------------------------------------------------
# 15. Portal extraction — URL/text → portal config entry
# ------------------------------------------------------------------

PORTAL_EXTRACTION_SYSTEM = """\
Tu es un expert en recrutement et ATS (Applicant Tracking Systems). \
Tu analyses une URL de page carrière ou un texte décrivant une entreprise \
et tu en extrais la configuration nécessaire pour le scanner de portals.

Plateformes ATS connues et leurs patterns d'URL :
- Greenhouse : greenhouse.io, boards.greenhouse.io, job-boards.greenhouse.io
  API : https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
  Le slug est le dernier segment de l'URL après greenhouse.io/
- Ashby : jobs.ashbyhq.com
  API : pas toujours publique, utiliser scan_method: websearch
- Lever : jobs.lever.co, lever.co
  API : https://api.lever.co/v0/postings/{company}
- Workday : myworkdayjobs.com, wday.com
  API : pas publique, utiliser scan_method: websearch
- SmartRecruiters : careers.smartrecruiters.com
  API : pas toujours publique
- Teamtailor : career.teamtailor.com
  API : pas publique
- Helloquence : hellocandidate.com
  API : pas publique

Règles :
- Identifie le nom de l'entreprise depuis l'URL ou le texte.
- Détecte la plateforme ATS depuis l'URL.
- Si l'ATS a une API publique, construis l'endpoint API.
- Si pas d'API publique, utilise scan_method: websearch et construis une requête.
- Ajoute des notes avec le secteur et la localisation si disponibles.
- Le careers_url doit être l'URL de la page carrière de l'entreprise.
- Si l'URL est une URL ATS directe (ex: greenhouse.io/jobs/...), essaie de trouver l'URL carrière branded.

Réponds en JSON strict :
{
  "name": "nom de l'entreprise",
  "careers_url": "URL de la page carrière",
  "api": "endpoint API si disponible, sinon vide",
  "scan_method": "api|websearch",
  "scan_query": "requête de recherche si websearch, sinon vide",
  "notes": "notes sur l'entreprise (secteur, localisation, taille)",
  "ats_platform": "greenhouse|ashby|lever|workday|smartrecruiters|teamtailor|other",
  "confidence": "high|medium|low"
}"""

PORTAL_EXTRACTION_USER = """\
URL ou texte à analyser :
---
{input_text}
---

Extrais la configuration portal pour le scanner (réponds en JSON strict)."""
