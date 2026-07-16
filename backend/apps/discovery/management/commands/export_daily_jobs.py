"""Export today's digest as JSON, or push chosen items to the career-ops pipeline.

    python manage.py export_daily_jobs --profile default            # print JSON
    python manage.py export_daily_jobs --profile default --evaluate  # push 'evaluate' items to pipeline.md
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.discovery.models import DailyJobDigest, SearchProfile
from apps.discovery.services.exporters import export_item_to_pipeline


class Command(BaseCommand):
    help = "Print or export today's digest for a profile."

    def add_arguments(self, parser):
        parser.add_argument("--profile", default="default")
        parser.add_argument("--evaluate", action="store_true", help="Export items marked 'evaluate' to pipeline.md")

    def handle(self, *args, **options):
        try:
            profile = SearchProfile.objects.get(name=options["profile"])
        except SearchProfile.DoesNotExist as exc:
            raise CommandError(f"No SearchProfile named '{options['profile']}'.") from exc

        digest = (
            DailyJobDigest.objects.filter(profile=profile, date=timezone.localdate())
            .order_by("-created_at")
            .first()
        )
        if digest is None:
            raise CommandError("No digest for today; run discover_jobs first.")

        exported = []
        if options["evaluate"]:
            for item in digest.items.filter(decision="evaluate", exported_to_pipeline_at__isnull=True):
                result = export_item_to_pipeline(item)
                exported.append({"job": item.job.title, "company": item.job.company, **result})

        items = [
            {
                "rank": item.rank,
                "title": item.job.title,
                "company": item.job.company,
                "location": item.job.location,
                "remote": item.job.remote_type,
                "contract": item.job.contract_type,
                "score": item.ranking.score if item.ranking else None,
                "decision": item.decision,
                "url": item.job.apply_url or item.job.source_url,
            }
            for item in digest.items.select_related("job", "ranking")
        ]
        self.stdout.write(
            json.dumps(
                {"date": digest.date.isoformat(), "items": items, "exported": exported},
                ensure_ascii=False,
                indent=2,
            )
        )
