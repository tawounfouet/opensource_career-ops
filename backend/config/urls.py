from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core.views import (
    ClisView,
    ApplyCloseView,
    ApplyDriveView,
    ApplyFillView,
    ApplyPrefillView,
    ApplySessionView,
    DoctorView,
    ExploreAddView,
    ExploreAiView,
    ExploreKnownView,
    ExploreView,
    FollowupsLogView,
    FollowupsView,
    MemoryView,
    ReportShapeView,
    RunStreamView,
    UsageView,
    VersionView,
    WhatsNewView,
)
from apps.cv.views import CvPdfView, CvViewSet
from apps.portals.views import PortalVerifyView, PortalsView, ProfileView, ProfileVariantView
from apps.runner.views import AssistantView, RunsSaveView
from apps.tracker.views import PipelineView, StatusView, TrackerDeleteView


router = DefaultRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/pipeline", PipelineView.as_view(), name="api-pipeline"),
    path("api/cv", CvViewSet.as_view(), name="api-cv"),
    path("api/cv-pdf", CvPdfView.as_view(), name="api-cv-pdf"),
    path("api/profile", ProfileView.as_view(), name="api-profile"),
    path("api/profile/variants", ProfileVariantView.as_view(), name="api-profile-variants"),
    path("api/profile/variants/<str:name>", ProfileVariantView.as_view(), name="api-profile-variant-detail"),
    path("api/portals", PortalsView.as_view(kind="portals"), name="api-portals"),
    path("api/portals/verify", PortalVerifyView.as_view(), name="api-portals-verify"),
    path("api/tracker/delete", TrackerDeleteView.as_view(), name="api-tracker-delete"),
    path("api/status", StatusView.as_view(), name="api-status"),
    path("api/doctor", DoctorView.as_view(), name="api-doctor"),
    path("api/version", VersionView.as_view(), name="api-version"),
    path("api/whats-new", WhatsNewView.as_view(), name="api-whats-new"),
    path("api/followups", FollowupsView.as_view(), name="api-followups"),
    path("api/followups/log", FollowupsLogView.as_view(), name="api-followups-log"),
    path("api/usage", UsageView.as_view(), name="api-usage"),
    path("api/report/shape", ReportShapeView.as_view(), name="api-report-shape"),
    path("api/memory", MemoryView.as_view(), name="api-memory"),
    path("api/explore", ExploreView.as_view(), name="api-explore"),
    path("api/explore/add", ExploreAddView.as_view(), name="api-explore-add"),
    path("api/explore/ai", ExploreAiView.as_view(), name="api-explore-ai"),
    path("api/explore/ai/known", ExploreKnownView.as_view(), name="api-explore-known"),
    path("api/run", RunStreamView.as_view(), name="api-run"),
    path("api/apply/session", ApplySessionView.as_view(), name="api-apply-session"),
    path("api/apply/close", ApplyCloseView.as_view(), name="api-apply-close"),
    path("api/apply/prefill", ApplyPrefillView.as_view(), name="api-apply-prefill"),
    path("api/apply/fill", ApplyFillView.as_view(), name="api-apply-fill"),
    path("api/apply/drive", ApplyDriveView.as_view(), name="api-apply-drive"),
    path("api/assistant", AssistantView.as_view(), name="api-assistant"),
    path("api/runs/save", RunsSaveView.as_view(), name="api-runs-save"),
    path("api/clis", ClisView.as_view(), name="api-clis"),
    path("api/discovery/", include("apps.discovery.urls")),
    path("api/skills/", include("apps.skills_portfolio.urls")),
    path("api/", include(router.urls)),
]
