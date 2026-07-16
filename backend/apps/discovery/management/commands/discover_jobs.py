"""Nightly discovery run: collect → normalize → dedup → rank → digest.

    python manage.py discover_jobs --profile default --market france
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.discovery.models import JobSource, SearchProfile
from apps.discovery.services.scheduler import run_discovery


class Command(BaseCommand):
    help = "Run a deterministic France job-discovery collection + ranking pass."

    def add_arguments(self, parser):
        parser.add_argument("--profile", default="default", help="SearchProfile name")
        parser.add_argument("--market", default=None, help="Filter sources by market (france/francophone/remote_eu)")
        parser.add_argument("--source", action="append", default=[], help="Restrict to source slug(s); repeatable")
        parser.add_argument("--trigger", default="cli", choices=["scheduled", "manual", "cli"])

    def handle(self, *args, **options):
        try:
            profile = SearchProfile.objects.get(name=options["profile"])
        except SearchProfile.DoesNotExist as exc:
            raise CommandError(f"No SearchProfile named '{options['profile']}'. Create one first.") from exc

        sources = None
        if options["source"] or options["market"]:
            qs = JobSource.objects.filter(enabled=True)
            if options["source"]:
                qs = qs.filter(slug__in=options["source"])
            if options["market"]:
                qs = qs.filter(market=options["market"])
            sources = [s for s in qs if s.is_automatable]
            if not sources:
                self.stderr.write("No matching automatable sources; nothing to collect.")

        summary = run_discovery(profile, sources=sources, trigger=options["trigger"])
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
