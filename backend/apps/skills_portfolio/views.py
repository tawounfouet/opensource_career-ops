"""DRF endpoints for the skills portfolio module."""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Education, EducationCompetency, SkillCompetency, SkillEvidence, SkillExperience
from .serializers import EducationSerializer, SkillCompetencySerializer, SkillEvidenceSerializer, SkillExperienceSerializer
from .services.extraction import (
    benchmark_summary,
    clarify_evidence,
    evaluate_mastery,
    extract_from_experience,
    extract_education_from_text,
    extract_experiences_from_text,
    formalize_competency,
    generate_discovery_profile,
    parse_jd,
    persist_extracted_competencies,
    persist_extracted_educations,
    persist_extracted_experiences,
    suggest_cv_bullets,
    suggest_evidence_questions,
    suggest_interview_questions,
)
from .services.integration import compute_skill_gaps, extract_discovery_keywords, get_validated_competencies
from .services.exports import export_to_cvdata, export_to_json, export_to_json_string, export_to_markdown, generate_cv_markdown
from .services.llm_client import LLMClient
from .services.matching import benchmark_all_validated, generate_plan_for_gaps

logger = logging.getLogger(__name__)


def _get_llm_client() -> LLMClient:
    """Build an LLM client from the current environment."""
    return LLMClient()


class DashboardView(APIView):
    def get(self, request):
        competencies = SkillCompetency.objects.all()
        by_status = dict(competencies.values_list("status").annotate(total=Count("id")))
        by_category = dict(competencies.values_list("category").annotate(total=Count("id")))
        evidence_stats = competencies.annotate(evidence_total=Count("evidence"))
        without_evidence = evidence_stats.filter(evidence_total=0).count()
        with_evidence = evidence_stats.filter(evidence_total__gte=1).count()

        with_rationale = competencies.exclude(mastery_rationale="").count()
        draft = competencies.filter(status="draft")
        ready_to_validate = draft.annotate(evidence_total=Count("evidence")).filter(
            evidence_total__gte=1
        ).exclude(mastery_rationale="").count()

        return Response(
            {
                "experiences": SkillExperience.objects.count(),
                "competencies": competencies.count(),
                "evidence": SkillEvidence.objects.count(),
                "educations": Education.objects.count(),
                "by_status": by_status,
                "by_category": by_category,
                "without_evidence": without_evidence,
                "with_evidence": with_evidence,
                "with_mastery_rationale": with_rationale,
                "ready_to_validate": ready_to_validate,
            }
        )


class ExperiencesView(APIView):
    def get(self, request):
        qs = SkillExperience.objects.all()
        return Response({"experiences": SkillExperienceSerializer(qs, many=True).data})

    def post(self, request):
        serializer = SkillExperienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExperienceDetailView(APIView):
    def get_object(self, pk: int) -> SkillExperience | None:
        return SkillExperience.objects.filter(pk=pk).first()

    def get(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "experience not found"}, status=404)
        return Response(SkillExperienceSerializer(obj).data)

    def patch(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "experience not found"}, status=404)
        serializer = SkillExperienceSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "experience not found"}, status=404)
        obj.delete()
        return Response(status=204)


class EvidenceView(APIView):
    def get(self, request):
        qs = SkillEvidence.objects.select_related("source_experience")
        return Response({"evidence": SkillEvidenceSerializer(qs, many=True).data})

    def post(self, request):
        serializer = SkillEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EvidenceDetailView(APIView):
    def patch(self, request, pk: int):
        obj = SkillEvidence.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"error": "evidence not found"}, status=404)
        serializer = SkillEvidenceSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CompetenciesView(APIView):
    def get(self, request):
        qs = SkillCompetency.objects.prefetch_related("experiences", "evidence")
        status_filter = request.query_params.get("status")
        category = request.query_params.get("category")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if category:
            qs = qs.filter(category=category)
        return Response({"competencies": SkillCompetencySerializer(qs, many=True).data})

    def post(self, request):
        serializer = SkillCompetencySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CompetencyDetailView(APIView):
    def get_object(self, pk: int) -> SkillCompetency | None:
        return SkillCompetency.objects.prefetch_related("experiences", "evidence").filter(pk=pk).first()

    def get(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "competency not found"}, status=404)
        return Response(SkillCompetencySerializer(obj).data)

    def patch(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "competency not found"}, status=404)
        serializer = SkillCompetencySerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CompetencyValidateView(APIView):
    def post(self, request, pk: int):
        obj = SkillCompetency.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"error": "competency not found"}, status=404)
        try:
            obj.validate()
        except ValidationError as exc:
            return Response({"error": exc.message}, status=400)
        return Response(SkillCompetencySerializer(obj).data)


class CompetencyRejectView(APIView):
    def post(self, request, pk: int):
        obj = SkillCompetency.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"error": "competency not found"}, status=404)
        obj.reject()
        return Response(SkillCompetencySerializer(obj).data)


# ------------------------------------------------------------------
# LLM-assisted endpoints
# ------------------------------------------------------------------


class ExtractFromExperienceView(APIView):
    """POST /api/skills/llm/extract-from-experience

    Body: {"experience_id": int, "persist": bool}
    If persist=True, draft competencies are created in the DB.
    """

    def post(self, request):
        experience_id = request.data.get("experience_id")
        if not experience_id:
            return Response({"error": "experience_id is required"}, status=400)

        experience = SkillExperience.objects.filter(pk=experience_id).first()
        if experience is None:
            return Response({"error": "experience not found"}, status=404)

        client = _get_llm_client()
        output = extract_from_experience(client, experience)

        if "error" in output:
            return Response(output, status=422)

        persist = request.data.get("persist", False)
        created = []
        if persist:
            objs = persist_extracted_competencies(output, experience)
            created = SkillCompetencySerializer(objs, many=True).data

        return Response({
            "extracted": output.get("competencies", []),
            "created": created,
            "count": len(created) if persist else len(output.get("competencies", [])),
        })


class FormalizeCompetencyView(APIView):
    """POST /api/skills/llm/formalize

    Body: {"raw_label": str, "context": str (optional)}
    """

    def post(self, request):
        raw_label = request.data.get("raw_label", "").strip()
        if not raw_label:
            return Response({"error": "raw_label is required"}, status=400)

        client = _get_llm_client()
        output = formalize_competency(client, raw_label, request.data.get("context", ""))

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class SuggestEvidenceView(APIView):
    """POST /api/skills/llm/suggest-evidence

    Body: {"competency_id": int}
    """

    def post(self, request):
        competency_id = request.data.get("competency_id")
        if not competency_id:
            return Response({"error": "competency_id is required"}, status=400)

        competency = SkillCompetency.objects.prefetch_related("experiences").filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        client = _get_llm_client()
        output = suggest_evidence_questions(client, competency)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class BenchmarkView(APIView):
    """POST /api/skills/llm/benchmark

    Body: {"target_role": str}
    Benchmarks all validated competencies against the target role.
    """

    def post(self, request):
        target_role = request.data.get("target_role", "").strip()
        if not target_role:
            return Response({"error": "target_role is required"}, status=400)

        client = _get_llm_client()
        output = benchmark_all_validated(client, target_role)
        return Response(output)


class DevelopmentPlanView(APIView):
    """POST /api/skills/llm/development-plan

    Body: {"target_role": str, "create_actions": bool}
    If create_actions=True, SkillDevelopmentAction objects are persisted.
    """

    def post(self, request):
        target_role = request.data.get("target_role", "").strip()
        if not target_role:
            return Response({"error": "target_role is required"}, status=400)

        create_actions = request.data.get("create_actions", False)
        client = _get_llm_client()
        output = generate_plan_for_gaps(client, target_role, create_actions=create_actions)
        return Response(output)


# ------------------------------------------------------------------
# Phase 4 — Evidence & mastery evaluation
# ------------------------------------------------------------------


class MasteryEvaluationView(APIView):
    """POST /api/skills/llm/evaluate-mastery

    Body: {"competency_id": int}
    Returns LLM-evaluated mastery level, rationale, and clarifying questions.
    """

    def post(self, request):
        competency_id = request.data.get("competency_id")
        if not competency_id:
            return Response({"error": "competency_id is required"}, status=400)

        competency = SkillCompetency.objects.prefetch_related("experiences", "evidence").filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        client = _get_llm_client()
        output = evaluate_mastery(client, competency)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class ClarifyEvidenceView(APIView):
    """POST /api/skills/llm/clarify-evidence

    Body: {"competency_id": int, "raw_evidence": str}
    Helps the user formulate a raw proof into a structured evidence.
    """

    def post(self, request):
        competency_id = request.data.get("competency_id")
        raw_evidence = request.data.get("raw_evidence", "").strip()
        if not competency_id:
            return Response({"error": "competency_id is required"}, status=400)
        if not raw_evidence:
            return Response({"error": "raw_evidence is required"}, status=400)

        competency = SkillCompetency.objects.prefetch_related("experiences").filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        client = _get_llm_client()
        output = clarify_evidence(client, competency, raw_evidence)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class EvidenceAttachView(APIView):
    """POST /api/skills/evidence/attach

    Body: {"competency_id": int, "evidence_id": int}
    Links an existing evidence to a competency.
    """

    def post(self, request):
        competency_id = request.data.get("competency_id")
        evidence_id = request.data.get("evidence_id")
        if not competency_id or not evidence_id:
            return Response({"error": "competency_id and evidence_id are required"}, status=400)

        competency = SkillCompetency.objects.filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        evidence = SkillEvidence.objects.filter(pk=evidence_id).first()
        if evidence is None:
            return Response({"error": "evidence not found"}, status=404)

        competency.evidence.add(evidence)
        return Response(SkillCompetencySerializer(competency).data)


class EvidenceDetachView(APIView):
    """POST /api/skills/evidence/detach

    Body: {"competency_id": int, "evidence_id": int}
    Unlinks an evidence from a competency.
    """

    def post(self, request):
        competency_id = request.data.get("competency_id")
        evidence_id = request.data.get("evidence_id")
        if not competency_id or not evidence_id:
            return Response({"error": "competency_id and evidence_id are required"}, status=400)

        competency = SkillCompetency.objects.filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        evidence = SkillEvidence.objects.filter(pk=evidence_id).first()
        if evidence is None:
            return Response({"error": "evidence not found"}, status=404)

        competency.evidence.remove(evidence)
        return Response(SkillCompetencySerializer(competency).data)


# ------------------------------------------------------------------
# Education CRUD
# ------------------------------------------------------------------


class EducationsView(APIView):
    def get(self, request):
        qs = Education.objects.prefetch_related("competencies", "education_links")
        education_type = request.query_params.get("type")
        edu_status = request.query_params.get("status")
        if education_type:
            qs = qs.filter(education_type=education_type)
        if edu_status:
            qs = qs.filter(status=edu_status)
        return Response({"educations": EducationSerializer(qs, many=True).data})

    def post(self, request):
        serializer = EducationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EducationDetailView(APIView):
    def get_object(self, pk: int) -> Education | None:
        return Education.objects.prefetch_related("competencies", "education_links").filter(pk=pk).first()

    def get(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "education not found"}, status=404)
        return Response(EducationSerializer(obj).data)

    def patch(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "education not found"}, status=404)
        serializer = EducationSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk: int):
        obj = self.get_object(pk)
        if obj is None:
            return Response({"error": "education not found"}, status=404)
        obj.delete()
        return Response(status=204)


class EducationAttachCompetencyView(APIView):
    """POST /api/skills/educations/{id}/attach-competency

    Body: {"competency_id": int, "relevance": str (optional)}
    """

    def post(self, request, pk: int):
        education = Education.objects.filter(pk=pk).first()
        if education is None:
            return Response({"error": "education not found"}, status=404)

        competency_id = request.data.get("competency_id")
        if not competency_id:
            return Response({"error": "competency_id is required"}, status=400)

        competency = SkillCompetency.objects.filter(pk=competency_id).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        relevance = request.data.get("relevance", "acquired")
        link, created = EducationCompetency.objects.get_or_create(
            education=education, competency=competency, defaults={"relevance": relevance}
        )
        if not created:
            link.relevance = relevance
            link.save(update_fields=["relevance"])

        return Response(EducationSerializer(education).data)


class EducationDetachCompetencyView(APIView):
    """POST /api/skills/educations/{id}/detach-competency

    Body: {"competency_id": int}
    """

    def post(self, request, pk: int):
        education = Education.objects.filter(pk=pk).first()
        if education is None:
            return Response({"error": "education not found"}, status=404)

        competency_id = request.data.get("competency_id")
        if not competency_id:
            return Response({"error": "competency_id is required"}, status=400)

        deleted, _ = EducationCompetency.objects.filter(
            education=education, competency_id=competency_id
        ).delete()

        if deleted == 0:
            return Response({"error": "link not found"}, status=404)

        return Response(EducationSerializer(education).data)


class ExtractEducationView(APIView):
    """POST /api/skills/llm/extract-education

    Body: {"text": str, "experience_id": int (optional), "persist": bool}
    Extracts education entries from free text.
    """

    def post(self, request):
        input_text = request.data.get("text", "").strip()
        if not input_text:
            return Response({"error": "text is required"}, status=400)

        experience_id = request.data.get("experience_id")
        experience = None
        if experience_id:
            experience = SkillExperience.objects.filter(pk=experience_id).first()
            if experience is None:
                return Response({"error": "experience not found"}, status=404)

        client = _get_llm_client()
        output = extract_education_from_text(client, input_text)

        if "error" in output:
            return Response(output, status=422)

        persist = request.data.get("persist", False)
        created = []
        if persist:
            objs = persist_extracted_educations(output, experience)
            created = EducationSerializer(objs, many=True).data

        return Response({
            "extracted": output.get("educations", []),
            "created": created,
            "count": len(created) if persist else len(output.get("educations", [])),
        })


class ExtractExperienceView(APIView):
    """POST /api/skills/llm/extract-experience

    Body: {"text": str, "persist": bool}
    Extracts experience entries from free text.
    """

    def post(self, request):
        input_text = request.data.get("text", "").strip()
        if not input_text:
            return Response({"error": "text is required"}, status=400)

        client = _get_llm_client()
        output = extract_experiences_from_text(client, input_text)

        if "error" in output:
            return Response(output, status=422)

        persist = request.data.get("persist", False)
        created = []
        if persist:
            objs = persist_extracted_experiences(output)
            created = SkillExperienceSerializer(objs, many=True).data

        return Response({
            "extracted": output.get("experiences", []),
            "created": created,
            "count": len(created) if persist else len(output.get("experiences", [])),
        })


class ExtractProfileView(APIView):
    """POST /api/skills/llm/extract-profile

    Body: {"text": str, "persist": bool, "variant": str?}
    Extracts profile fields from free text (CV, transcript, career description).
    If persist=True, merges extracted fields into the profile YAML.
    If variant is provided, merges into that variant file.
    """

    def post(self, request):
        from .services.extraction import extract_profile_from_text

        input_text = request.data.get("text", "").strip()
        if not input_text:
            return Response({"error": "text is required"}, status=400)

        client = _get_llm_client()
        output = extract_profile_from_text(client, input_text)

        if "error" in output:
            return Response(output, status=422)

        persist = request.data.get("persist", False)
        variant = request.data.get("variant")
        applied = {}

        if persist:
            import yaml
            from pathlib import Path

            if variant:
                profile_path = Path("config/profiles") / f"{variant}.yml"
            else:
                profile_path = Path("config/profile.yml")

            if not profile_path.exists():
                return Response({"error": f"Profile file not found: {profile_path}"}, status=404)

            with open(profile_path) as f:
                doc = yaml.safe_load(f) or {}

            candidate = output.get("candidate", {})
            narrative = output.get("narrative", {})
            languages = output.get("languages", [])
            interests = output.get("interests", [])
            regulations = output.get("regulations", [])
            compensation = output.get("compensation", {})
            location_detail = output.get("location_detail", {})

            # Merge candidate fields
            if candidate.get("full_name"):
                doc.setdefault("candidate", {})["full_name"] = candidate["full_name"]
                applied["full_name"] = candidate["full_name"]
            if candidate.get("email"):
                doc.setdefault("candidate", {})["email"] = candidate["email"]
                applied["email"] = candidate["email"]
            if candidate.get("phone"):
                doc.setdefault("candidate", {})["phone"] = candidate["phone"]
                applied["phone"] = candidate["phone"]
            if candidate.get("location"):
                doc.setdefault("candidate", {})["location"] = candidate["location"]
                applied["location"] = candidate["location"]
            if candidate.get("linkedin"):
                doc.setdefault("candidate", {})["linkedin"] = candidate["linkedin"]
                applied["linkedin"] = candidate["linkedin"]
            if candidate.get("portfolio_url"):
                doc.setdefault("candidate", {})["portfolio_url"] = candidate["portfolio_url"]
                applied["portfolio_url"] = candidate["portfolio_url"]
            if candidate.get("github"):
                doc.setdefault("candidate", {})["github"] = candidate["github"]
                applied["github"] = candidate["github"]

            # Merge narrative
            if narrative.get("headline"):
                doc.setdefault("narrative", {})["headline"] = narrative["headline"]
                applied["headline"] = narrative["headline"]
            if narrative.get("exit_story"):
                doc.setdefault("narrative", {})["exit_story"] = narrative["exit_story"]
                applied["exit_story"] = narrative["exit_story"]
            if narrative.get("superpowers"):
                doc.setdefault("narrative", {})["superpowers"] = narrative["superpowers"]
                applied["superpowers"] = narrative["superpowers"]

            # Merge languages
            if languages:
                doc["languages"] = languages
                applied["languages"] = languages

            # Merge interests
            if interests:
                existing_interests = doc.get("interests", [])
                merged = list(set(existing_interests + interests))
                doc["interests"] = merged
                applied["interests"] = merged

            # Merge regulations
            if regulations:
                existing_regs = doc.get("regulations", [])
                merged = list(set(existing_regs + regulations))
                doc["regulations"] = merged
                applied["regulations"] = merged

            # Merge compensation
            if compensation.get("target_range"):
                doc.setdefault("compensation", {})["target_range"] = compensation["target_range"]
                applied["comp_target"] = compensation["target_range"]
            if compensation.get("currency"):
                doc.setdefault("compensation", {})["currency"] = compensation["currency"]
                applied["comp_currency"] = compensation["currency"]

            # Merge location
            if location_detail.get("country"):
                doc.setdefault("location", {})["country"] = location_detail["country"]
                applied["country"] = location_detail["country"]
            if location_detail.get("city"):
                doc.setdefault("location", {})["city"] = location_detail["city"]
                applied["city"] = location_detail["city"]
            if location_detail.get("visa_status"):
                doc.setdefault("location", {})["visa_status"] = location_detail["visa_status"]
                applied["visa_status"] = location_detail["visa_status"]

            with open(profile_path, "w") as f:
                yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return Response({
            "extracted": output,
            "applied": applied,
            "count": len(applied),
        })


class ExtractPortalView(APIView):
    """POST /api/skills/llm/extract-portal

    Body: {"text": str, "persist": bool}
    Extracts portal configuration from a URL or text description of a company.
    If persist=True, creates the portal in DB and exports to portals.yml.
    """

    def post(self, request):
        from .services.extraction import extract_portal_from_text

        input_text = request.data.get("text", "").strip()
        if not input_text:
            return Response({"error": "text is required"}, status=400)

        client = _get_llm_client()
        output = extract_portal_from_text(client, input_text)

        if "error" in output:
            return Response(output, status=422)

        persist = request.data.get("persist", False)
        appended = False

        if persist:
            from apps.portals.models import Portal
            from apps.portals.services import export_db_to_yaml

            name = output["name"]

            if Portal.objects.filter(name__iexact=name).exists():
                return Response({
                    "extracted": output,
                    "appended": False,
                    "error": f"Company '{name}' already exists in portals",
                })

            Portal.objects.create(
                name=name,
                careers_url=output.get("careers_url", ""),
                api_endpoint=output.get("api", ""),
                scan_method=output.get("scan_method", "auto"),
                scan_query=output.get("scan_query", ""),
                notes=output.get("notes", ""),
                enabled=True,
            )

            export_db_to_yaml()
            appended = True

        return Response({
            "extracted": output,
            "appended": appended,
        })


class CompetencyReadinessView(APIView):
    """GET /api/skills/competencies/{id}/readiness

    Returns a readiness assessment for a competency:
    - has_evidence: bool
    - has_mastery_rationale: bool
    - can_validate: bool (has evidence + mastery rationale)
    - evidence_count: int
    """

    def get(self, request, pk: int):
        competency = SkillCompetency.objects.prefetch_related("evidence").filter(pk=pk).first()
        if competency is None:
            return Response({"error": "competency not found"}, status=404)

        evidence_count = competency.evidence.count()
        has_evidence = evidence_count > 0
        has_mastery_rationale = bool(competency.mastery_rationale.strip())
        can_validate = has_evidence and has_mastery_rationale

        return Response({
            "competency_id": competency.id,
            "status": competency.status,
            "has_evidence": has_evidence,
            "evidence_count": evidence_count,
            "has_mastery_rationale": has_mastery_rationale,
            "mastery_level": competency.mastery_level,
            "confidence": competency.confidence,
            "can_validate": can_validate,
            "blockers": [] if can_validate else [
                "evidence required" if not has_evidence else "",
                "mastery rationale required" if not has_mastery_rationale else "",
            ],
        })


# ------------------------------------------------------------------
# Phase 5 — JD parsing & benchmark summary
# ------------------------------------------------------------------


class ParseJDView(APIView):
    """POST /api/skills/llm/parse-jd

    Body: {"jd_text": str}
    Parses a job description and returns expected competencies.
    """

    def post(self, request):
        jd_text = request.data.get("jd_text", "").strip()
        if not jd_text:
            return Response({"error": "jd_text is required"}, status=400)

        client = _get_llm_client()
        output = parse_jd(client, jd_text)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class BenchmarkSummaryView(APIView):
    """POST /api/skills/llm/benchmark-summary

    Body: {"target_role": str, "jd_text": str}
    Full comparison of validated competencies vs JD expectations.
    """

    def post(self, request):
        target_role = request.data.get("target_role", "").strip()
        jd_text = request.data.get("jd_text", "").strip()
        if not target_role:
            return Response({"error": "target_role is required"}, status=400)
        if not jd_text:
            return Response({"error": "jd_text is required"}, status=400)

        client = _get_llm_client()
        output = benchmark_summary(client, target_role, jd_text)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


# ------------------------------------------------------------------
# Phase 6 — Integration with career-ops modules
# ------------------------------------------------------------------


class ValidatedCompetenciesView(APIView):
    """GET /api/skills/integration/validated

    Returns all validated competencies formatted for consumption by
    other career-ops modules (evaluation, CV, interview, discovery).
    Deterministic — no LLM.
    """

    def get(self, request):
        return Response(get_validated_competencies())


class SkillGapsView(APIView):
    """POST /api/skills/integration/skill-gaps

    Body: {"expected_labels": [str], "expected_categories": {str: str} (optional)}
    Deterministic gap analysis — no LLM.
    """

    def post(self, request):
        expected_labels = request.data.get("expected_labels", [])
        if not expected_labels:
            return Response({"error": "expected_labels is required"}, status=400)

        expected_categories = request.data.get("expected_categories", {})
        output = compute_skill_gaps(expected_labels, expected_categories)
        return Response(output)


class DiscoveryKeywordsView(APIView):
    """GET /api/skills/integration/discovery-keywords

    Extracts search keywords from validated competencies for the
    discovery module's SearchProfile. Deterministic — no LLM.
    """

    def get(self, request):
        return Response(extract_discovery_keywords())


class CVBulletsView(APIView):
    """POST /api/skills/llm/suggest-cv-bullets

    Body: {"target_role": str}
    LLM generates CV bullet points from validated competencies.
    """

    def post(self, request):
        target_role = request.data.get("target_role", "").strip()
        if not target_role:
            return Response({"error": "target_role is required"}, status=400)

        client = _get_llm_client()
        output = suggest_cv_bullets(client, target_role)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class InterviewQuestionsView(APIView):
    """POST /api/skills/llm/suggest-interview-questions

    Body: {"target_role": str}
    LLM generates likely interview questions from the portfolio.
    """

    def post(self, request):
        target_role = request.data.get("target_role", "").strip()
        if not target_role:
            return Response({"error": "target_role is required"}, status=400)

        client = _get_llm_client()
        output = suggest_interview_questions(client, target_role)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


class DiscoveryProfileView(APIView):
    """POST /api/skills/llm/discovery-profile

    LLM generates optimized search keywords for the discovery module.
    """

    def post(self, request):
        client = _get_llm_client()
        output = generate_discovery_profile(client)

        if "error" in output:
            return Response(output, status=422)
        return Response(output)


# ------------------------------------------------------------------
# Export endpoints
# ------------------------------------------------------------------


class ExportJsonView(APIView):
    """GET /api/skills/export/json"""

    def get(self, request):
        return Response(export_to_json())


class ExportMarkdownView(APIView):
    """GET /api/skills/export/markdown"""

    def get(self, request):
        md = export_to_markdown()
        return HttpResponse(md, content_type="text/markdown; charset=utf-8")


class ExportCvDataView(APIView):
    """GET /api/skills/export/cvdata — portfolio + profile as CVData JSON."""

    def get(self, request):
        return Response(export_to_cvdata())


class ExportCvMarkdownView(APIView):
    """GET /api/skills/export/cv-markdown — full CV as Markdown."""

    def get(self, request):
        md = generate_cv_markdown()
        return HttpResponse(md, content_type="text/markdown; charset=utf-8")

