"""Seed the France sources catalogue + a default SearchProfile (idempotent).

Follows the plan's legal posture: high-risk boards (LinkedIn, Indeed) ship as
manual_import/disabled; French jobboards without a stable public API ship
disabled with a reason; ATS connectors ship enabled but empty (add boards to
their config to activate).

    python manage.py seed_discovery
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.discovery.models import JobSource, SearchProfile

SOURCES = [
    # Tier 1 France jobboards — connectors implemented, opt-in (enabled=False) to
    # respect each platform's TOS until the user turns them on.
    dict(slug="apec", name="APEC", kind="jobboard", strategy="api", connector="apec",
         market="france", enabled=False, base_url="https://www.apec.fr",
         disabled_reason="Opt-in: uses APEC's public search webservice; enable to activate."),
    dict(slug="france-travail", name="France Travail", kind="jobboard", strategy="api",
         connector="france_travail", market="france", enabled=False,
         base_url="https://api.francetravail.io",
         disabled_reason="Enable after setting config.access_token (OAuth app)."),
    dict(slug="wttj", name="Welcome to the Jungle", kind="jobboard", strategy="api", connector="wttj",
         market="france", enabled=False, base_url="https://www.welcometothejungle.com",
         config={"app_id": "", "api_key": "", "index": "wk_prod_jobs_production_v2"},
         disabled_reason="Set config.app_id/api_key (public Algolia search keys), then enable."),
    dict(slug="hellowork", name="HelloWork", kind="jobboard", strategy="html_public", connector="hellowork",
         market="france", enabled=False, rate_limit_per_hour=30, base_url="https://www.hellowork.com",
         disabled_reason="Opt-in: parses public JSON-LD; keep a strict rate limit."),
    dict(slug="indeed-fr", name="Indeed France", kind="jobboard", strategy="manual_import",
         connector="indeed_manual", market="france", enabled=False, config={"items": [], "urls": []},
         disabled_reason="Manual import only; no aggressive scraping (official/partner path otherwise)."),
    dict(slug="linkedin", name="LinkedIn Jobs", kind="jobboard", strategy="manual_import",
         connector="linkedin_manual", market="france", enabled=False, requires_login=True,
         config={"items": [], "urls": []},
         disabled_reason="Manual import only; no automated browser scraping (CGU/anti-bot)."),
    # Tier 3 ATS — stable public JSON, enabled but need boards/slugs in config.
    dict(slug="greenhouse", name="Greenhouse boards", kind="ats", strategy="ats_api",
         connector="greenhouse", market="remote_eu", enabled=True,
         config={"boards": []}, base_url="https://boards-api.greenhouse.io",
         tos_notes="Add company board tokens to config.boards to activate."),
    dict(slug="lever", name="Lever postings", kind="ats", strategy="ats_api",
         connector="lever", market="remote_eu", enabled=True,
         config={"slugs": []}, base_url="https://api.lever.co",
         tos_notes="Add company slugs to config.slugs to activate."),
    dict(slug="ashby", name="Ashby job boards", kind="ats", strategy="ats_api",
         connector="ashby", market="remote_eu", enabled=True,
         config={"slugs": []}, base_url="https://api.ashbyhq.com",
         tos_notes="Add board slugs to config.slugs to activate."),
]


class Command(BaseCommand):
    help = "Seed default France job sources and a default SearchProfile (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for spec in SOURCES:
            _, was_created = JobSource.objects.update_or_create(
                slug=spec["slug"], defaults={k: v for k, v in spec.items() if k != "slug"}
            )
            created += int(was_created)

        profile, profile_created = SearchProfile.objects.get_or_create(
            name="default",
            defaults=dict(
                target_titles=["Data Engineer", "AI Engineer", "Machine Learning Engineer"],
                positive_keywords=["python", "django", "azure", "spark", "snowflake"],
                negative_keywords=["php", "wordpress"],
                required_keywords=[],
                locations=["Paris", "Île-de-France", "France"],
                remote_policy="hybrid",
                contract_types=["cdi", "freelance"],
                freshness_days=7,
                max_results_per_run=100,
                daily_digest_size=20,
                language="fr",
                market_mode="modes/fr",
            ),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sources: {JobSource.objects.count()} total ({created} new). "
                f"Profile 'default' {'created' if profile_created else 'already present'}."
            )
        )
