from datetime import date

from django.core.management.base import BaseCommand

from apps.core.services import read_applications
from apps.tracker.models import Application


class Command(BaseCommand):
    help = "Import data/applications.md rows into the Django ORM index"

    def handle(self, *args, **options):
        count = 0
        for row in read_applications():
            parsed_date = None
            try:
                parsed_date = date.fromisoformat(row["date"])
            except Exception:
                pass
            Application.objects.update_or_create(
                number=int(row["n"]),
                defaults={
                    "date": parsed_date,
                    "company": row["company"],
                    "role": row["role"],
                    "via": row["via"],
                    "score": row["score"],
                    "status": row["status"],
                    "has_pdf": row["pdf"] == "✅",
                    "report_file": row["report"],
                    "notes": row["notes"],
                    "synced_to_file": True,
                },
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {count} tracker rows"))
