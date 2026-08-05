import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline.collection import (
    load_manifest,
    manifest_is_publication_eligible,
    manifest_path,
    validate_manifest,
    write_manifest_bundle,
)


class Command(BaseCommand):
    help = "Build a deterministic publishable bundle for one approved course collection."

    def add_arguments(self, parser):
        parser.add_argument("course_slug")
        parser.add_argument("--root", default=".")
        parser.add_argument("--output", required=True)
        parser.add_argument("--source-commit")
        parser.add_argument("--allow-unapproved", action="store_true")

    def handle(self, *args, **options):
        root = Path(options["root"]).resolve()
        manifest = load_manifest(manifest_path(root, options["course_slug"]))
        issues = validate_manifest(manifest)
        errors = [item for item in issues if item.severity == "error"]
        if errors:
            for issue in errors:
                self.stderr.write(f"{issue.code}: {issue.path}: {issue.detail}")
            raise CommandError("Manifest validation failed; bundle was not written.")
        eligible, failures = manifest_is_publication_eligible(manifest)
        if not eligible and not options["allow_unapproved"]:
            for failure in failures:
                self.stderr.write(f"publication gate: {failure}")
            raise CommandError("Publication eligibility gates failed; bundle was not written.")
        commit = (
            options["source_commit"]
            or subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
            ).stdout.strip()
            or "unknown"
        )
        try:
            output = write_manifest_bundle(manifest, options["output"], source_commit=commit)
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Wrote {output}"))
