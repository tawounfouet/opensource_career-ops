from django.core.management.base import BaseCommand, CommandError

from apps.core.services import run_node_script


class Command(BaseCommand):
    help = "Run career-ops doctor.mjs"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        script_args = ["--json"] if options["json"] else []
        result = run_node_script("doctor", *script_args)
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode:
            raise CommandError(f"doctor failed with exit code {result.returncode}")
