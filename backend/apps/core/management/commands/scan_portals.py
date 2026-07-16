from django.core.management.base import BaseCommand, CommandError

from apps.core.services import run_node_script


class Command(BaseCommand):
    help = "Run career-ops scan.mjs"

    def add_arguments(self, parser):
        parser.add_argument("args", nargs="*")

    def handle(self, *args, **options):
        result = run_node_script("scan", *options["args"], timeout=900)
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode:
            raise CommandError(f"scan failed with exit code {result.returncode}")
