"""Tests for the skills portfolio LLM services and export endpoints.

All LLM calls are mocked — no real API requests are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.skills_portfolio.models import SkillCompetency, SkillEvidence, SkillExtractionRun, SkillExperience
from apps.skills_portfolio.services.llm_client import LLMClient
from apps.skills_portfolio.services.validation import (
    validate_benchmark_output,
    validate_development_plan_output,
    validate_extraction_output,
    validate_formalize_output,
    validate_suggest_evidence_output,
)


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------


class TestValidateExtractionOutput:
    def test_valid_output(self):
        output = {
            "competencies": [
                {
                    "label": "Concevoir des APIs",
                    "formulation": "Je suis capable de concevoir des APIs REST.",
                    "category": "hard_skill",
                    "mastery_level": "confirmed",
                    "confidence": "high",
                }
            ]
        }
        assert validate_extraction_output(output) == []

    def test_missing_competencies_key(self):
        assert "Missing" in validate_extraction_output({"wrong": []})[0]

    def test_empty_list(self):
        errors = validate_extraction_output({"competencies": []})
        assert any("No competencies" in e for e in errors)

    def test_invalid_category(self):
        output = {
            "competencies": [
                {
                    "label": "X",
                    "formulation": "Y",
                    "category": "magic_skill",
                    "mastery_level": "junior",
                    "confidence": "medium",
                }
            ]
        }
        errors = validate_extraction_output(output)
        assert any("category" in e for e in errors)

    def test_missing_fields(self):
        output = {"competencies": [{"label": "only-label"}]}
        errors = validate_extraction_output(output)
        assert any("missing fields" in e for e in errors)


class TestValidateFormalizeOutput:
    def test_valid(self):
        assert validate_formalize_output({"formulation": "Je suis capable de coder."}) == []

    def test_empty(self):
        assert len(validate_formalize_output({"formulation": ""})) > 0

    def test_too_long(self):
        assert len(validate_formalize_output({"formulation": "x" * 400})) > 0


class TestValidateBenchmarkOutput:
    def test_valid(self):
        assert validate_benchmark_output({"gap": "minor", "recommendation": "ok"}) == []

    def test_invalid_gap(self):
        errors = validate_benchmark_output({"gap": "huge", "recommendation": "ok"})
        assert any("gap" in e for e in errors)


class TestValidateDevelopmentPlan:
    def test_valid(self):
        output = {"actions": [{"action": "do stuff", "type": "training", "resources": []}]}
        assert validate_development_plan_output(output) == []

    def test_empty_actions(self):
        assert len(validate_development_plan_output({"actions": []})) > 0


# ------------------------------------------------------------------
# LLM Client (unit tests without network)
# ------------------------------------------------------------------


class TestLLMClient:
    def test_default_values(self):
        client = LLMClient()
        assert "openai" in client.base_url or client.base_url == "https://api.openai.com/v1"
        assert client.model == "gpt-4o-mini"

    def test_custom_values(self):
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama3")
        assert client.base_url == "http://localhost:11434/v1"
        assert client.model == "llama3"

    @patch("apps.skills_portfolio.services.llm_client.httpx.Client")
    def test_complete_mocked(self, mock_httpx_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_httpx_cls.return_value)
        mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_httpx_cls.return_value.post.return_value = mock_resp

        client = LLMClient(base_url="http://test", api_key="sk-test", model="test")
        result = client.complete("system", "user")
        assert result == "test response"


# ------------------------------------------------------------------
# Extraction service (mocked)
# ------------------------------------------------------------------


class TestExtraction:
    @pytest.mark.django_db
    def test_extract_and_persist(self, client):
        experience = SkillExperience.objects.create(
            title="Projet API",
            type="project",
            description="Construire une API REST",
            deliverables=["API endpoints"],
            tools=["Python", "Django"],
        )

        mock_llm_response = {
            "competencies": [
                {
                    "label": "Concevoir des APIs REST",
                    "formulation": "Je suis capable de concevoir des APIs REST.",
                    "action_verb": "concevoir",
                    "object": "des APIs REST",
                    "context": "pour un produit web",
                    "category": "hard_skill",
                    "mastery_level": "confirmed",
                    "confidence": "high",
                    "rationale": "Démontré par la création de l'API",
                }
            ]
        }

        # extract_from_experience calls client.complete() then json.loads()
        with patch.object(LLMClient, "complete", return_value=json.dumps(mock_llm_response)):
            from apps.skills_portfolio.services.extraction import extract_from_experience, persist_extracted_competencies

            output = extract_from_experience(LLMClient(), experience)
            assert "competencies" in output
            assert len(output["competencies"]) == 1

            created = persist_extracted_competencies(output, experience)
            assert len(created) == 1
            assert created[0].label == "Concevoir des APIs REST"
            assert created[0].status == "draft"
            assert created[0].created_by == "llm"
            assert experience in created[0].experiences.all()

            # Audit trail
            runs = SkillExtractionRun.objects.filter(experience=experience)
            assert runs.count() == 1
            assert runs.first().status == "success"

    @pytest.mark.django_db
    def test_extract_handles_llm_error(self, client):
        experience = SkillExperience.objects.create(title="Test", type="project")

        with patch.object(LLMClient, "complete", side_effect=Exception("API timeout")):
            from apps.skills_portfolio.services.extraction import extract_from_experience

            output = extract_from_experience(LLMClient(), experience)
            assert "error" in output

            # Audit trail records the failure
            runs = SkillExtractionRun.objects.filter(experience=experience)
            assert runs.count() == 1
            assert runs.first().status == "failed"

    @pytest.mark.django_db
    def test_extract_rejects_invalid_output(self, client):
        experience = SkillExperience.objects.create(title="Test", type="project")

        with patch.object(LLMClient, "complete", return_value=json.dumps({"competencies": []})):
            from apps.skills_portfolio.services.extraction import extract_from_experience

            output = extract_from_experience(LLMClient(), experience)
            assert "error" in output


# ------------------------------------------------------------------
# Export endpoints
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_export_json_empty(client):
    response = client.get("/api/skills/export/json")
    assert response.status_code == 200
    data = response.json()
    assert "exported_at" in data
    assert data["counts"]["experiences"] == 0
    assert data["counts"]["competencies"] == 0


@pytest.mark.django_db
def test_export_json_with_data(client):
    SkillExperience.objects.create(title="Exp 1", type="project")
    SkillCompetency.objects.create(label="Comp 1", formulation="F1", category="hard_skill")
    SkillEvidence.objects.create(title="Evidence 1", type="deliverable")

    response = client.get("/api/skills/export/json")
    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["experiences"] == 1
    assert data["counts"]["competencies"] == 1
    assert data["counts"]["evidence"] == 1
    assert len(data["experiences"]) == 1
    assert len(data["competencies"]) == 1


@pytest.mark.django_db
def test_export_markdown(client):
    SkillCompetency.objects.create(
        label="Concevoir des APIs",
        formulation="Je suis capable de concevoir des APIs.",
        category="hard_skill",
        status="validated",
    )
    SkillCompetency.objects.create(
        label="Communiquer clairement",
        formulation="Je suis capable de communiquer clairement.",
        category="soft_skill",
        status="draft",
    )

    response = client.get("/api/skills/export/markdown")
    assert response.status_code == 200
    content = response.content.decode()
    assert "# Portefeuille de compétences" in content
    assert "Savoir-faire" in content
    assert "Savoir-être" in content
    assert "Concevoir des APIs" in content
    assert "✅" in content  # validated icon
    assert "📝" in content  # draft icon


# ------------------------------------------------------------------
# Phase 4 — Mastery evaluation
# ------------------------------------------------------------------


class TestMasteryEvaluation:
    @pytest.mark.django_db
    def test_evaluate_mastery_with_evidence(self, client):
        experience = SkillExperience.objects.create(title="Projet API", type="project")
        evidence = SkillEvidence.objects.create(
            title="API livrée", type="deliverable", source_experience=experience,
            description="API Django REST avec 12 endpoints", metric="12 endpoints",
        )
        competency = SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs Django.",
            category="hard_skill",
            mastery_level="junior",
        )
        competency.experiences.add(experience)
        competency.evidence.add(evidence)

        mock_response = {
            "mastery_level": "confirmé",
            "rationale": "L'utilisateur a livré 12 endpoints fonctionnels, ce qui démontre une autonomie solide.",
            "confidence": "high",
            "missing_evidence_questions": [
                "Avez-vous conçu l'architecture de l'API ou seulement implémenté des endpoints ?"
            ],
            "max_level_without_more_evidence": "junior",
        }

        # complete_json already parses JSON → mock returns a dict directly
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import evaluate_mastery
            output = evaluate_mastery(LLMClient(), competency)

            assert output["mastery_level"] == "confirmé"
            assert "rationale" in output
            assert len(output["missing_evidence_questions"]) == 1

    @pytest.mark.django_db
    def test_evaluate_mastery_without_evidence(self, client):
        competency = SkillCompetency.objects.create(
            label="Piloter un projet",
            formulation="Je suis capable de piloter un projet.",
            category="soft_skill",
        )

        mock_response = {
            "mastery_level": "debutant",
            "rationale": "Aucune preuve fournie, impossible d'évaluer un niveau supérieur.",
            "confidence": "low",
            "missing_evidence_questions": [
                "Quel projet avez-vous piloté ?",
                "Combien de personnes impliquées ?"
            ],
            "max_level_without_more_evidence": "debutant",
        }

        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import evaluate_mastery
            output = evaluate_mastery(LLMClient(), competency)

            assert output["mastery_level"] == "debutant"
            assert output["confidence"] == "low"

    @pytest.mark.django_db
    def test_evaluate_mastery_competency_not_found(self, client):
        response = client.post(
            "/api/skills/llm/evaluate-mastery",
            {"competency_id": 9999},
            content_type="application/json",
        )
        assert response.status_code == 404


# ------------------------------------------------------------------
# Phase 4 — Clarify evidence
# ------------------------------------------------------------------


class TestClarifyEvidence:
    @pytest.mark.django_db
    def test_clarify_evidence(self, client):
        competency = SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs Django.",
            category="hard_skill",
        )

        mock_response = {
            "title": "API Django livrée avec 12 endpoints",
            "type": "deliverable",
            "description": "Conception et implémentation d'une API Django REST avec 12 endpoints fonctionnels pour un produit web.",
            "metric": "12 endpoints",
            "suggestions": [],
            "trust_level_suggestion": "user_confirmed",
        }

        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import clarify_evidence
            output = clarify_evidence(LLMClient(), competency, "j'ai fait une API Django")

            assert output["type"] == "deliverable"
            assert "title" in output
            assert output["trust_level_suggestion"] == "user_confirmed"

    @pytest.mark.django_db
    def test_clarify_evidence_missing_fields(self, client):
        competency = SkillCompetency.objects.create(
            label="Communiquer", formulation="Je communique bien.", category="soft_skill",
        )

        mock_response = {
            "title": "",
            "type": "other",
            "description": "",
            "metric": "",
            "suggestions": ["Pouvez-vous donner un exemple concret ?"],
            "trust_level_suggestion": "inferred_pending_review",
        }

        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import clarify_evidence
            output = clarify_evidence(LLMClient(), competency, "je communique bien")
            # Validation should fail because title and description are empty
            assert "error" in output

    @pytest.mark.django_db
    def test_clarify_evidence_competency_not_found(self, client):
        response = client.post(
            "/api/skills/llm/clarify-evidence",
            {"competency_id": 9999, "raw_evidence": "quelque chose"},
            content_type="application/json",
        )
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_clarify_evidence_missing_raw(self, client):
        competency = SkillCompetency.objects.create(
            label="Test", formulation="Test.", category="hard_skill",
        )
        response = client.post(
            "/api/skills/llm/clarify-evidence",
            {"competency_id": competency.id, "raw_evidence": ""},
            content_type="application/json",
        )
        assert response.status_code == 400


# ------------------------------------------------------------------
# Phase 4 — Evidence attach/detach
# ------------------------------------------------------------------


class TestEvidenceAttachDetach:
    @pytest.mark.django_db
    def test_attach_evidence(self, client):
        competency = SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs.",
            category="hard_skill",
        )
        evidence = SkillEvidence.objects.create(title="Preuve 1", type="deliverable")

        response = client.post(
            "/api/skills/evidence/attach",
            {"competency_id": competency.id, "evidence_id": evidence.id},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert evidence.id in response.json()["evidence_ids"]

    @pytest.mark.django_db
    def test_detach_evidence(self, client):
        competency = SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs.",
            category="hard_skill",
        )
        evidence = SkillEvidence.objects.create(title="Preuve 1", type="deliverable")
        competency.evidence.add(evidence)

        response = client.post(
            "/api/skills/evidence/detach",
            {"competency_id": competency.id, "evidence_id": evidence.id},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert evidence.id not in response.json()["evidence_ids"]

    @pytest.mark.django_db
    def test_attach_missing_params(self, client):
        response = client.post(
            "/api/skills/evidence/attach",
            {"competency_id": 1},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_attach_competency_not_found(self, client):
        evidence = SkillEvidence.objects.create(title="Preuve", type="deliverable")
        response = client.post(
            "/api/skills/evidence/attach",
            {"competency_id": 9999, "evidence_id": evidence.id},
            content_type="application/json",
        )
        assert response.status_code == 404


# ------------------------------------------------------------------
# Phase 4 — Competency readiness
# ------------------------------------------------------------------


class TestCompetencyReadiness:
    @pytest.mark.django_db
    def test_readiness_no_evidence_no_rationale(self, client):
        competency = SkillCompetency.objects.create(
            label="Comp 1", formulation="F1", category="hard_skill",
        )
        response = client.get(f"/api/skills/competencies/{competency.id}/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["has_evidence"] is False
        assert data["has_mastery_rationale"] is False
        assert data["can_validate"] is False
        assert len(data["blockers"]) == 2

    @pytest.mark.django_db
    def test_readiness_with_evidence_no_rationale(self, client):
        competency = SkillCompetency.objects.create(
            label="Comp 1", formulation="F1", category="hard_skill",
        )
        evidence = SkillEvidence.objects.create(title="Preuve", type="deliverable")
        competency.evidence.add(evidence)

        response = client.get(f"/api/skills/competencies/{competency.id}/readiness")
        data = response.json()
        assert data["has_evidence"] is True
        assert data["evidence_count"] == 1
        assert data["has_mastery_rationale"] is False
        assert data["can_validate"] is False
        assert any("rationale" in b for b in data["blockers"])

    @pytest.mark.django_db
    def test_readiness_ready_to_validate(self, client):
        competency = SkillCompetency.objects.create(
            label="Comp 1", formulation="F1", category="hard_skill",
            mastery_rationale="Démontré par la livraison de l'API.",
        )
        evidence = SkillEvidence.objects.create(title="Preuve", type="deliverable")
        competency.evidence.add(evidence)

        response = client.get(f"/api/skills/competencies/{competency.id}/readiness")
        data = response.json()
        assert data["can_validate"] is True
        assert data["blockers"] == []

    @pytest.mark.django_db
    def test_readiness_not_found(self, client):
        response = client.get("/api/skills/competencies/9999/readiness")
        assert response.status_code == 404


# ------------------------------------------------------------------
# Phase 4 — Dashboard readiness
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_readiness_fields(client):
    response = client.get("/api/skills/dashboard")
    data = response.json()
    assert "with_evidence" in data
    assert "with_mastery_rationale" in data
    assert "ready_to_validate" in data
    assert data["with_evidence"] == 0
    assert data["with_mastery_rationale"] == 0
    assert data["ready_to_validate"] == 0


@pytest.mark.django_db
def test_dashboard_readiness_with_data(client):
    # Competency ready to validate
    c1 = SkillCompetency.objects.create(
        label="Ready", formulation="F", category="hard_skill",
        mastery_rationale="Justifié.",
    )
    e1 = SkillEvidence.objects.create(title="Preuve", type="deliverable")
    c1.evidence.add(e1)

    # Competency with evidence but no rationale
    c2 = SkillCompetency.objects.create(
        label="Not ready", formulation="F", category="hard_skill",
    )
    c2.evidence.add(e1)

    response = client.get("/api/skills/dashboard")
    data = response.json()
    assert data["with_evidence"] == 2
    assert data["with_mastery_rationale"] == 1
    assert data["ready_to_validate"] == 1


# ------------------------------------------------------------------
# Phase 5 — JD parsing
# ------------------------------------------------------------------


class TestParseJD:
    def test_parse_jd_valid(self):
        mock_response = {
            "role_title": "Senior Backend Engineer",
            "company": "Acme Corp",
            "location": "Paris",
            "expected_competencies": [
                {
                    "label": "Concevoir des APIs REST",
                    "category": "hard_skill",
                    "requirement": "required",
                    "min_level": "confirmed",
                    "evidence_question": "Avez-vous conçu une API exposant des données métier ?",
                },
                {
                    "label": "Communication claire",
                    "category": "soft_skill",
                    "requirement": "preferred",
                    "min_level": "junior",
                    "evidence_question": "",
                },
            ],
            "missing_context_questions": [],
        }

        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import parse_jd
            output = parse_jd(LLMClient(), "Nous recherchons un backend engineer...")

            assert output["role_title"] == "Senior Backend Engineer"
            assert len(output["expected_competencies"]) == 2
            assert output["expected_competencies"][0]["requirement"] == "required"

    def test_parse_jd_empty_competencies(self):
        mock_response = {"expected_competencies": []}
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import parse_jd
            output = parse_jd(LLMClient(), "JD vide")
            assert "error" in output

    def test_parse_jd_invalid_category(self):
        mock_response = {
            "expected_competencies": [
                {"label": "X", "category": "magic", "requirement": "required", "min_level": "junior"}
            ]
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import parse_jd
            output = parse_jd(LLMClient(), "JD")
            assert "error" in output


class TestParseJDView:
    @pytest.mark.django_db
    def test_missing_jd_text(self, client):
        response = client.post(
            "/api/skills/llm/parse-jd",
            {"jd_text": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_parse_jd_success(self, client):
        mock_response = {
            "role_title": "Dev",
            "expected_competencies": [
                {"label": "Python", "category": "hard_skill", "requirement": "required", "min_level": "confirmed"}
            ]
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            response = client.post(
                "/api/skills/llm/parse-jd",
                {"jd_text": "Nous cherchons un dev Python"},
                content_type="application/json",
            )
            assert response.status_code == 200
            assert response.json()["role_title"] == "Dev"


# ------------------------------------------------------------------
# Phase 5 — Benchmark summary
# ------------------------------------------------------------------


class TestBenchmarkSummary:
    @pytest.mark.django_db
    def test_benchmark_summary_no_validated(self, client):
        from apps.skills_portfolio.services.extraction import benchmark_summary
        output = benchmark_summary(LLMClient(), "Backend Engineer", "JD text")
        assert "error" in output
        assert "No validated" in output["error"]

    @pytest.mark.django_db
    def test_benchmark_summary_with_validated(self, client):
        SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs.",
            category="hard_skill",
            status="validated",
            mastery_level="confirmed",
            confidence="high",
        )

        mock_response = {
            "fit_score": "85",
            "fit_label": "good",
            "summary": "Bonne correspondance sur les compétences techniques.",
            "strong_matches": [
                {
                    "expected": "Concevoir des APIs REST",
                    "user_competency": "Concevoir des APIs",
                    "match_type": "exact",
                    "notes": "Correspondance directe",
                }
            ],
            "transferable_matches": [],
            "gaps": [],
            "overselling_risks": [],
            "interview_questions": ["Parlez-moi d'une API que vous avez conçue."],
            "cv_recommendations": ["Mettez en avant vos APIs dans la section expérience."],
        }

        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import benchmark_summary
            output = benchmark_summary(LLMClient(), "Backend Engineer", "Nous cherchons un backend...")

            assert output["fit_label"] == "good"
            assert len(output["strong_matches"]) == 1
            assert len(output["interview_questions"]) == 1

    @pytest.mark.django_db
    def test_benchmark_summary_empty_gaps(self, client):
        SkillCompetency.objects.create(
            label="Comp 1", formulation="F", category="hard_skill", status="validated",
        )

        mock_response = {
            "fit_score": "100",
            "fit_label": "excellent",
            "summary": "Parfait.",
            "strong_matches": [],
            "transferable_matches": [],
            "gaps": [],
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            from apps.skills_portfolio.services.extraction import benchmark_summary
            output = benchmark_summary(LLMClient(), "Dev", "JD")
            assert output["fit_label"] == "excellent"


class TestBenchmarkSummaryView:
    @pytest.mark.django_db
    def test_missing_target_role(self, client):
        response = client.post(
            "/api/skills/llm/benchmark-summary",
            {"target_role": "", "jd_text": "JD"},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_missing_jd_text(self, client):
        response = client.post(
            "/api/skills/llm/benchmark-summary",
            {"target_role": "Dev", "jd_text": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_benchmark_summary_no_validated_422(self, client):
        response = client.post(
            "/api/skills/llm/benchmark-summary",
            {"target_role": "Dev", "jd_text": "JD text"},
            content_type="application/json",
        )
        assert response.status_code == 422


# ------------------------------------------------------------------
# Phase 6 — Integration: deterministic endpoints
# ------------------------------------------------------------------


class TestValidatedCompetencies:
    @pytest.mark.django_db
    def test_empty(self, client):
        response = client.get("/api/skills/integration/validated")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["competencies"] == []

    @pytest.mark.django_db
    def test_returns_only_validated(self, client):
        SkillCompetency.objects.create(
            label="Validated", formulation="F", category="hard_skill", status="validated",
        )
        SkillCompetency.objects.create(
            label="Draft", formulation="F", category="hard_skill", status="draft",
        )
        response = client.get("/api/skills/integration/validated")
        data = response.json()
        assert data["count"] == 1
        assert data["competencies"][0]["label"] == "Validated"

    @pytest.mark.django_db
    def test_includes_evidence_and_experiences(self, client):
        exp = SkillExperience.objects.create(title="Projet", type="project")
        ev = SkillEvidence.objects.create(title="Preuve", type="deliverable")
        comp = SkillCompetency.objects.create(
            label="Comp", formulation="F", category="hard_skill", status="validated",
            market_keywords=["python", "django"],
        )
        comp.experiences.add(exp)
        comp.evidence.add(ev)

        response = client.get("/api/skills/integration/validated")
        data = response.json()
        c = data["competencies"][0]
        assert len(c["evidence"]) == 1
        assert c["evidence"][0]["title"] == "Preuve"
        assert c["experience_titles"] == ["Projet"]
        assert c["market_keywords"] == ["python", "django"]


class TestSkillGaps:
    @pytest.mark.django_db
    def test_all_matched(self, client):
        SkillCompetency.objects.create(
            label="Python", formulation="F", category="hard_skill", status="validated",
        )
        SkillCompetency.objects.create(
            label="Django", formulation="F", category="hard_skill", status="validated",
        )
        response = client.post(
            "/api/skills/integration/skill-gaps",
            {"expected_labels": ["Python", "Django"]},
            content_type="application/json",
        )
        data = response.json()
        assert data["matched_count"] == 2
        assert data["missing_count"] == 0

    @pytest.mark.django_db
    def test_some_missing(self, client):
        SkillCompetency.objects.create(
            label="Python", formulation="F", category="hard_skill", status="validated",
        )
        response = client.post(
            "/api/skills/integration/skill-gaps",
            {"expected_labels": ["Python", "Kubernetes"]},
            content_type="application/json",
        )
        data = response.json()
        assert data["matched_count"] == 1
        assert data["missing_count"] == 1
        assert data["missing"][0]["expected"] == "Kubernetes"

    @pytest.mark.django_db
    def test_empty_expected(self, client):
        response = client.post(
            "/api/skills/integration/skill-gaps",
            {"expected_labels": []},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestDiscoveryKeywords:
    @pytest.mark.django_db
    def test_empty(self, client):
        response = client.get("/api/skills/integration/discovery-keywords")
        data = response.json()
        assert data["competency_count"] == 0
        assert data["positive_keywords"] == []

    @pytest.mark.django_db
    def test_extracts_from_competencies(self, client):
        SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="F",
            category="hard_skill",
            status="validated",
            market_keywords=["REST", "API"],
            tags=["backend"],
        )
        response = client.get("/api/skills/integration/discovery-keywords")
        data = response.json()
        assert data["competency_count"] == 1
        assert "Concevoir des APIs" in data["positive_keywords"]
        assert "REST" in data["positive_keywords"]
        assert "backend" in data["positive_keywords"]


# ------------------------------------------------------------------
# Phase 6 — Integration: LLM-assisted endpoints
# ------------------------------------------------------------------


class TestCVBulletsView:
    @pytest.mark.django_db
    def test_missing_target_role(self, client):
        response = client.post(
            "/api/skills/llm/suggest-cv-bullets",
            {"target_role": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_no_validated_422(self, client):
        response = client.post(
            "/api/skills/llm/suggest-cv-bullets",
            {"target_role": "Dev"},
            content_type="application/json",
        )
        assert response.status_code == 422

    @pytest.mark.django_db
    def test_with_validated(self, client):
        SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="Je suis capable de concevoir des APIs.",
            category="hard_skill",
            status="validated",
        )

        mock_response = {
            "bullets": [
                {
                    "competency_label": "Concevoir des APIs",
                    "bullet": "Conçu 12 endpoints REST pour un produit web local",
                    "evidence_used": "",
                    "category": "hard_skill",
                }
            ],
            "unused_competencies": [],
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            response = client.post(
                "/api/skills/llm/suggest-cv-bullets",
                {"target_role": "Backend Engineer"},
                content_type="application/json",
            )
            assert response.status_code == 200
            assert len(response.json()["bullets"]) == 1


class TestInterviewQuestionsView:
    @pytest.mark.django_db
    def test_missing_target_role(self, client):
        response = client.post(
            "/api/skills/llm/suggest-interview-questions",
            {"target_role": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_no_validated_422(self, client):
        response = client.post(
            "/api/skills/llm/suggest-interview-questions",
            {"target_role": "Dev"},
            content_type="application/json",
        )
        assert response.status_code == 422

    @pytest.mark.django_db
    def test_with_validated(self, client):
        SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="F",
            category="hard_skill",
            status="validated",
        )

        mock_response = {
            "questions": [
                {
                    "competency_label": "Concevoir des APIs",
                    "type": "technical",
                    "question": "Comment concevez-vous une API REST ?",
                    "what_to_listen_for": "Architecture, choix de design",
                }
            ],
            "general_questions": [
                {"type": "motivation", "question": "Pourquoi ce poste ?"}
            ],
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            response = client.post(
                "/api/skills/llm/suggest-interview-questions",
                {"target_role": "Backend Engineer"},
                content_type="application/json",
            )
            assert response.status_code == 200
            assert len(response.json()["questions"]) == 1


class TestDiscoveryProfileView:
    @pytest.mark.django_db
    def test_no_validated_422(self, client):
        response = client.post(
            "/api/skills/llm/discovery-profile",
            {},
            content_type="application/json",
        )
        assert response.status_code == 422

    @pytest.mark.django_db
    def test_with_validated(self, client):
        SkillCompetency.objects.create(
            label="Concevoir des APIs",
            formulation="F",
            category="hard_skill",
            status="validated",
            market_keywords=["REST", "API"],
        )

        mock_response = {
            "target_titles": ["Backend Engineer", "API Developer"],
            "positive_keywords": ["API", "REST", "Concevoir des APIs"],
            "tools": [],
            "negative_keywords": [],
            "summary": "Profil backend orienté APIs.",
        }
        with patch.object(LLMClient, "complete_json", return_value=mock_response):
            response = client.post(
                "/api/skills/llm/discovery-profile",
                {},
                content_type="application/json",
            )
            assert response.status_code == 200
            assert "Backend Engineer" in response.json()["target_titles"]
