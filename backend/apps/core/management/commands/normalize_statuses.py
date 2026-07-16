from django.core.management.base import BaseCommand, CommandError

from apps.core.services import run_node_script


class Command(BaseCommand):
    help = "Run career-ops normalize-statuses.mjs"

    def handle(self, *args, **options):
        result = run_node_script("normalize-statuses")
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode:
            raise CommandError(f"normalize-statuses failed with exit code {result.returncode}")
