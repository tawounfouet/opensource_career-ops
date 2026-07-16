from django.core.management.base import BaseCommand, CommandError

from apps.core.services import run_node_script


class Command(BaseCommand):
    help = "Run career-ops dedup-tracker.mjs"

    def handle(self, *args, **options):
        result = run_node_script("dedup-tracker")
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode:
            raise CommandError(f"dedup-tracker failed with exit code {result.returncode}")
