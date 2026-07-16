"""API contracts for the skills portfolio module."""

import pytest

from apps.skills_portfolio.models import Education, EducationCompetency, SkillCompetency, SkillEvidence, SkillExperience


@pytest.mark.django_db
def test_dashboard_empty(client):
    response = client.get("/api/skills/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["experiences"] == 0
    assert data["competencies"] == 0
    assert data["evidence"] == 0
    assert data["by_status"] == {}
    assert data["by_category"] == {}
    assert data["without_evidence"] == 0
    assert data["with_evidence"] == 0
    assert data["with_mastery_rationale"] == 0
    assert data["ready_to_validate"] == 0


@pytest.mark.django_db
def test_create_experience_and_competency_draft(client):
    exp = client.post(
        "/api/skills/experiences",
        {
            "title": "Projet Django discovery",
            "type": "project",
            "description": "Construction d'un module de collecte et scoring d'offres.",
            "deliverables": ["API digest", "UI revue matinale"],
            "outcomes": ["20 offres classees dans un digest"],
            "tools": ["Django", "Next.js"],
        },
        content_type="application/json",
    )
    assert exp.status_code == 201

    comp = client.post(
        "/api/skills/competencies",
        {
            "label": "Concevoir une API Django",
            "formulation": "Je suis capable de concevoir une API Django pour exposer un digest d'offres classees.",
            "category": "hard_skill",
            "action_verb": "concevoir",
            "object": "une API Django",
            "context": "dans un produit web local",
            "experience_ids": [exp.json()["id"]],
            "mastery_level": "confirmed",
            "confidence": "high",
            "status": "draft",
        },
        content_type="application/json",
    )
    assert comp.status_code == 201
    body = comp.json()
    assert body["status"] == "draft"
    assert body["experiences_detail"][0]["title"] == "Projet Django discovery"


@pytest.mark.django_db
def test_validate_requires_evidence(client):
    competency = SkillCompetency.objects.create(
        label="Structurer un workflow",
        formulation="Je suis capable de structurer un workflow deterministe de decision utilisateur.",
        category="hard_skill",
    )
    response = client.post(f"/api/skills/competencies/{competency.id}/validate", {}, content_type="application/json")
    assert response.status_code == 400
    assert "evidence" in response.json()["error"]
    competency.refresh_from_db()
    assert competency.status == "draft"


@pytest.mark.django_db
def test_validate_with_evidence(client):
    experience = SkillExperience.objects.create(title="Projet discovery", type="project")
    evidence = SkillEvidence.objects.create(
        title="Endpoints discovery testes",
        type="deliverable",
        source_experience=experience,
        trust_level="user_confirmed",
    )
    competency = SkillCompetency.objects.create(
        label="Concevoir une API Django",
        formulation="Je suis capable de concevoir une API Django pour exposer des donnees metier.",
        category="hard_skill",
        mastery_level="confirmed",
    )
    competency.experiences.add(experience)
    competency.evidence.add(evidence)

    response = client.post(f"/api/skills/competencies/{competency.id}/validate", {}, content_type="application/json")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["validated_at"]
    competency.refresh_from_db()
    assert competency.status == "validated"


@pytest.mark.django_db
def test_reject_competency(client):
    competency = SkillCompetency.objects.create(
        label="Competence trop vague",
        formulation="Je suis bon en communication.",
        category="soft_skill",
    )
    response = client.post(f"/api/skills/competencies/{competency.id}/reject", {}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


# ------------------------------------------------------------------
# Education tests
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_includes_education(client):
    response = client.get("/api/skills/dashboard")
    assert response.status_code == 200
    assert "educations" in response.json()
    assert response.json()["educations"] == 0


@pytest.mark.django_db
def test_create_education(client):
    response = client.post(
        "/api/skills/educations",
        {
            "title": "Master Intelligence Artificielle",
            "institution": "Universite Paris-Saclay",
            "education_type": "formation",
            "status": "completed",
            "start_date": "2022-09-01",
            "end_date": "2024-06-30",
            "hours": 600,
            "description": "M2 IA et decisionnel",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Master Intelligence Artificielle"
    assert body["education_type"] == "formation"
    assert body["competencies_count"] == 0


@pytest.mark.django_db
def test_list_educations(client):
    Education.objects.create(title="AWS SAA", education_type="certification", status="completed")
    Education.objects.create(title="BTS SIO", education_type="formation", status="completed")
    response = client.get("/api/skills/educations")
    assert response.status_code == 200
    assert len(response.json()["educations"]) == 2


@pytest.mark.django_db
def test_education_filter_by_type(client):
    Education.objects.create(title="AWS SAA", education_type="certification")
    Education.objects.create(title="BTS SIO", education_type="formation")
    response = client.get("/api/skills/educations?type=certification")
    assert response.status_code == 200
    assert len(response.json()["educations"]) == 1
    assert response.json()["educations"][0]["title"] == "AWS SAA"


@pytest.mark.django_db
def test_education_detail(client):
    edu = Education.objects.create(title="PMP", education_type="certification", status="completed")
    response = client.get(f"/api/skills/educations/{edu.id}")
    assert response.status_code == 200
    assert response.json()["title"] == "PMP"


@pytest.mark.django_db
def test_education_patch(client):
    edu = Education.objects.create(title="PMP", education_type="certification", status="planned")
    response = client.patch(
        f"/api/skills/educations/{edu.id}",
        {"status": "completed"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


@pytest.mark.django_db
def test_education_delete(client):
    edu = Education.objects.create(title="PMP", education_type="certification")
    response = client.delete(f"/api/skills/educations/{edu.id}")
    assert response.status_code == 204
    assert Education.objects.count() == 0


@pytest.mark.django_db
def test_education_attach_competency(client):
    edu = Education.objects.create(title="AWS SAA", education_type="certification")
    comp = SkillCompetency.objects.create(
        label="Concevoir une architecture cloud",
        formulation="Je suis capable de concevoir une architecture AWS.",
        category="hard_skill",
    )
    response = client.post(
        f"/api/skills/educations/{edu.id}/attach-competency",
        {"competency_id": comp.id, "relevance": "validated"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["competencies_count"] == 1
    link = EducationCompetency.objects.get(education=edu, competency=comp)
    assert link.relevance == "validated"


@pytest.mark.django_db
def test_education_detach_competency(client):
    edu = Education.objects.create(title="AWS SAA", education_type="certification")
    comp = SkillCompetency.objects.create(
        label="Concevoir une architecture cloud",
        formulation="Je suis capable de concevoir une architecture AWS.",
        category="hard_skill",
    )
    EducationCompetency.objects.create(education=edu, competency=comp, relevance="validated")
    response = client.post(
        f"/api/skills/educations/{edu.id}/detach-competency",
        {"competency_id": comp.id},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["competencies_count"] == 0
    assert not EducationCompetency.objects.filter(education=edu, competency=comp).exists()
