from django.core.management.base import BaseCommand, CommandError

from apps.core.services import run_node_script


class Command(BaseCommand):
    help = "Run career-ops update-system.mjs"

    def add_arguments(self, parser):
        parser.add_argument("action", nargs="?", default="check", choices=["check", "apply", "dismiss", "rollback"])

    def handle(self, *args, **options):
        result = run_node_script("update-system", options["action"], timeout=600)
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode:
            raise CommandError(f"update-system {options['action']} failed with exit code {result.returncode}")
