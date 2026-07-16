"""DRF endpoints for the discovery module (V1, deterministic, no auto-apply)."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DECISION,
    DailyJobDigest,
    DailyJobDigestItem,
    DiscoveryRun,
    JobSource,
    SearchProfile,
)
from .serializers import (
    DailyJobDigestSerializer,
    DiscoveryRunSerializer,
    JobSourceSerializer,
    SearchProfileSerializer,
)
from .services.exporters import apply_decision, export_item_to_pipeline
from .services.scheduler import run_discovery

DECISION_VALUES = {value for value, _ in DECISION}


def _profile_name(request) -> str:
    return str(request.query_params.get("profile") or request.data.get("profile") or "default")


def _get_or_create_profile(name: str) -> SearchProfile:
    profile, _ = SearchProfile.objects.get_or_create(name=name)
    return profile


class SourcesView(APIView):
    def get(self, request):
        sources = JobSource.objects.all()
        return Response({"sources": JobSourceSerializer(sources, many=True).data})


class ProfileView(APIView):
    def get(self, request):
        profile = _get_or_create_profile(_profile_name(request))
        return Response(SearchProfileSerializer(profile).data)

    def post(self, request):
        profile = _get_or_create_profile(_profile_name(request))
        data = {k: v for k, v in request.data.items() if k != "profile"}
        serializer = SearchProfileSerializer(profile, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RunView(APIView):
    def post(self, request):
        profile = _get_or_create_profile(_profile_name(request))
        source_slugs = request.data.get("sources") or []
        sources = None
        if source_slugs:
            sources = [s for s in JobSource.objects.filter(slug__in=source_slugs, enabled=True) if s.is_automatable]
        summary = run_discovery(profile, sources=sources, trigger="manual")
        return Response(summary)


class RunsView(APIView):
    def get(self, request):
        profile_name = request.query_params.get("profile")
        qs = DiscoveryRun.objects.all()
        if profile_name:
            qs = qs.filter(profile__name=profile_name)
        return Response({"runs": DiscoveryRunSerializer(qs[:50], many=True).data})


class DigestTodayView(APIView):
    def get(self, request):
        profile = _get_or_create_profile(_profile_name(request))
        digest = (
            DailyJobDigest.objects.filter(profile=profile, date=timezone.localdate())
            .order_by("-created_at")
            .first()
        )
        if digest is None:
            return Response({"date": timezone.localdate().isoformat(), "items": [], "empty": True})
        return Response(DailyJobDigestSerializer(digest).data)


class ItemDecisionView(APIView):
    def post(self, request, pk: int):
        try:
            item = DailyJobDigestItem.objects.get(pk=pk)
        except DailyJobDigestItem.DoesNotExist:
            return Response({"error": "digest item not found"}, status=404)
        decision = str(request.data.get("decision") or "").strip()
        if decision not in DECISION_VALUES:
            return Response({"error": f"invalid decision '{decision}'", "allowed": sorted(DECISION_VALUES)}, status=400)
        item = apply_decision(item, decision, str(request.data.get("note") or ""))
        return Response({"ok": True, "id": item.id, "decision": item.decision})


class ItemExportView(APIView):
    def post(self, request, pk: int):
        try:
            item = DailyJobDigestItem.objects.get(pk=pk)
        except DailyJobDigestItem.DoesNotExist:
            return Response({"error": "digest item not found"}, status=404)
        result = export_item_to_pipeline(item)
        return Response({"ok": True, **result})
