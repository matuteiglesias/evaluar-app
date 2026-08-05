import json

from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline.schema import ValidationIssue
from evaluar.content_pipeline.collection import (
    compile_manifest_course,
    load_manifest,
    manifest_path,
    compatibility_index_current,
    generated_index_path,
    manifest_is_publication_eligible,
    validate_manifest,
    governance_findings,
    validation_summary,
    write_compatibility_index,
)


class Command(BaseCommand):
    help = "Validate one course collection manifest and its compiler-compatible content."

    def add_arguments(self, parser):
        parser.add_argument("course_slug")
        parser.add_argument("--root", default=".")
        parser.add_argument("--source-commit", default="unknown")
        parser.add_argument("--check-publication-eligibility", action="store_true")
        parser.add_argument(
            "--json", action="store_true", help="emit machine-readable validation output"
        )
        parser.add_argument("--write-index", action="store_true")
        parser.add_argument(
            "--check",
            action="store_true",
            help="verify generated compatibility index.csv is current",
        )

    def handle(self, *args, **options):
        manifest = load_manifest(manifest_path(options["root"], options["course_slug"]))
        issues = list(validate_manifest(manifest))
        if options["write_index"] and not any(item.severity == "error" for item in issues):
            path = write_compatibility_index(manifest)
            self.stderr.write(self.style.SUCCESS(f"Wrote generated compatibility index {path}"))
        if options["check"] and not compatibility_index_current(manifest):
            issues.append(
                ValidationIssue(
                    "generated_index_stale",
                    generated_index_path(manifest).as_posix(),
                    "generated index.csv is missing or not current; run validate_course_collection --write-index",
                )
            )
        if not any(item.severity == "error" for item in issues):
            bundle = compile_manifest_course(manifest, source_commit=options["source_commit"])
            issues.extend(bundle.issues)
        issues.extend(governance_findings(manifest))
        issues = sorted(set(issues))
        if options["json"]:
            self.stdout.write(
                json.dumps(
                    {
                        "course": manifest.course_slug,
                        "manifest": manifest.path.as_posix(),
                        "summary": validation_summary(issues),
                        "technical_valid": not any(item.severity == "error" for item in issues),
                        "issues": [item.__dict__ for item in issues],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            for issue in issues:
                self.stdout.write(f"{issue.severity}: {issue.code}: {issue.path}: {issue.detail}")
        if options["check_publication_eligibility"]:
            eligible, failures = manifest_is_publication_eligible(manifest)
            for failure in failures:
                self.stderr.write(f"error: publication_gate: {manifest.path}: {failure}")
            if not eligible:
                raise CommandError("Publication eligibility gates failed.")
        errors = [item for item in issues if item.severity == "error"]
        if errors:
            raise CommandError(f"Course collection validation failed with {len(errors)} error(s).")
        if not options["json"]:
            self.stdout.write(self.style.SUCCESS("Course collection is technically valid."))
