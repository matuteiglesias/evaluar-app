import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline.bundle import with_course_names
from evaluar.content_pipeline.collection import (
    compile_manifest_course,
    load_manifest,
    manifest_is_publication_eligible,
    manifest_path,
    validate_manifest,
)
from evaluar.content_pipeline.io import write_bundle


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
        bundle = compile_manifest_course(manifest, source_commit=commit)
        if not bundle.valid:
            details = "; ".join(
                f"{item.code}: {item.path}: {item.detail}"
                for item in bundle.issues
                if item.severity == "error"
            )
            raise CommandError(f"Content validation failed; bundle was not written. {details}")
        bundle = with_course_names(bundle, {manifest.course_slug: manifest.course_name})
        output = write_bundle(bundle, options["output"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {output}"))
