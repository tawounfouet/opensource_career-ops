from django.urls import path

from .views import (
    DigestTodayView,
    ItemDecisionView,
    ItemExportView,
    ProfileView,
    RunView,
    RunsView,
    SourcesView,
)

urlpatterns = [
    path("sources", SourcesView.as_view(), name="discovery-sources"),
    path("profile", ProfileView.as_view(), name="discovery-profile"),
    path("run", RunView.as_view(), name="discovery-run"),
    path("runs", RunsView.as_view(), name="discovery-runs"),
    path("digest/today", DigestTodayView.as_view(), name="discovery-digest-today"),
    path("items/<int:pk>/decision", ItemDecisionView.as_view(), name="discovery-item-decision"),
    path("items/<int:pk>/export-pipeline", ItemExportView.as_view(), name="discovery-item-export"),
]
