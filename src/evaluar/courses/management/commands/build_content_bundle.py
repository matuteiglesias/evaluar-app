import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline import compile_content, write_bundle


class Command(BaseCommand):
    help = "Validate content and emit a deterministic publishable bundle."

    def add_arguments(self, parser):
        parser.add_argument("content_root")
        parser.add_argument("--output", required=True)
        parser.add_argument("--source-commit")

    def handle(self, *args, **options):
        root = Path(options["content_root"]).resolve()
        commit = (
            options["source_commit"]
            or subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
            ).stdout.strip()
            or "unknown"
        )
        bundle = compile_content(root, source_commit=commit)
        if not bundle.valid:
            for issue in bundle.issues:
                if issue.severity == "error":
                    self.stderr.write(f"{issue.code}: {issue.path}: {issue.detail}")
            raise CommandError("Content validation failed; bundle was not written.")
        output = write_bundle(bundle, options["output"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {output} ({bundle.manifest_checksum})."))
