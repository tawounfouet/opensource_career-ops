"""Re-rank the latest run's postings and rebuild today's digest.

Useful after editing a SearchProfile without re-fetching from sources.

    python manage.py rank_daily_jobs --profile default
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.discovery.models import DiscoveryRun, SearchProfile
from apps.discovery.services.scheduler import _rank_and_digest


class Command(BaseCommand):
    help = "Recompute rankings + today's digest for a profile from its most recent run."

    def add_arguments(self, parser):
        parser.add_argument("--profile", default="default")

    def handle(self, *args, **options):
        try:
            profile = SearchProfile.objects.get(name=options["profile"])
        except SearchProfile.DoesNotExist as exc:
            raise CommandError(f"No SearchProfile named '{options['profile']}'.") from exc

        run = DiscoveryRun.objects.filter(profile=profile).order_by("-started_at").first()
        if run is None:
            raise CommandError("No run found for this profile; run discover_jobs first.")

        digest = _rank_and_digest(profile, run, timezone.localdate())
        self.stdout.write(
            json.dumps(
                {"runId": run.id, "digest": {"date": digest.date.isoformat(), "items": digest.items_count}},
                ensure_ascii=False,
                indent=2,
            )
        )
