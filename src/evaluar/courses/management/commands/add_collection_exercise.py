import re
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline.collection import (
    load_manifest,
    manifest_path,
    validate_manifest,
    write_compatibility_index,
)

STATEMENT_TEMPLATE = """% Synthetic or instructor-authored public statement goes here.
% Complete learning objective, provenance, and review fields in collection.yaml.
"""


def _safe_filename(stable_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", stable_id).strip("-._") or "exercise"


class Command(BaseCommand):
    help = "Add a new public exercise statement and manifest entry to a collection workspace."

    def add_arguments(self, parser):
        parser.add_argument("course_slug")
        parser.add_argument("--stable-id", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--section", required=True)
        parser.add_argument("--root", default=".")
        parser.add_argument("--format", default="latex", choices=("latex", "markdown", "text"))
        parser.add_argument("--order", type=int)
        parser.add_argument("--no-write-index", action="store_true")

    def handle(self, *args, **options):
        manifest = load_manifest(manifest_path(options["root"], options["course_slug"]))
        payload = manifest.payload
        exercises = payload.setdefault("exercises", [])
        if not isinstance(exercises, list):
            raise CommandError("manifest exercises must be a list")
        stable_id = options["stable_id"]
        if any(isinstance(item, dict) and item.get("stable_id") == stable_id for item in exercises):
            raise CommandError(f"stable ID {stable_id!r} already exists")
        sections = payload.get("sections", [])
        section_ids = {item.get("id") for item in sections if isinstance(item, dict)}
        if options["section"] not in section_ids:
            raise CommandError(f"section {options['section']!r} is not declared in collection.yaml")
        section_orders = [
            int(item.get("order"))
            for item in exercises
            if isinstance(item, dict)
            and item.get("section") == options["section"]
            and isinstance(item.get("order"), int)
        ]
        order = (
            options["order"]
            if options["order"] is not None
            else (max(section_orders) + 10 if section_orders else 10)
        )
        if any(
            isinstance(item, dict)
            and item.get("section") == options["section"]
            and item.get("order") == order
            for item in exercises
        ):
            raise CommandError(f"order {order} already exists in section {options['section']!r}")
        suffix = {"latex": ".tex", "markdown": ".md", "text": ".txt"}[options["format"]]
        statement_path = Path("exercises") / f"{_safe_filename(stable_id)}{suffix}"
        full_statement_path = manifest.course_dir / statement_path
        if full_statement_path.exists():
            raise CommandError(f"statement file {full_statement_path} already exists")
        full_statement_path.parent.mkdir(parents=True, exist_ok=True)
        full_statement_path.write_text(STATEMENT_TEMPLATE, encoding="utf-8")
        exercises.append(
            {
                "stable_id": stable_id,
                "version": 1,
                "title": options["title"],
                "section": options["section"],
                "order": order,
                "statement": {"path": statement_path.as_posix(), "format": options["format"]},
                "learning_objective": "TODO: complete instructor-approved learning objective.",
                "prerequisites": [],
                "provenance": {
                    "status": "unknown",
                    "author": None,
                    "source": None,
                    "license_or_permission": None,
                },
                "review": {
                    "status": "draft",
                    "reviewer": None,
                    "reviewed_at": None,
                    "rendering_status": "pending",
                },
                "rendering": {"requirements": ["prose"]},
                "tutoring": {"eligible": False, "policy_review_status": "pending"},
            }
        )
        manifest.path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        reloaded = load_manifest(manifest.path)
        errors = [issue for issue in validate_manifest(reloaded) if issue.severity == "error"]
        if errors:
            details = "; ".join(f"{issue.code}: {issue.detail}" for issue in errors)
            raise CommandError(f"exercise was added but manifest now has errors: {details}")
        if not options["no_write_index"]:
            index_path = write_compatibility_index(reloaded)
            self.stdout.write(
                self.style.SUCCESS(f"Wrote generated compatibility index {index_path}")
            )
        self.stdout.write(self.style.SUCCESS(f"Added {stable_id} at {statement_path.as_posix()}"))
        self.stdout.write(
            "Reminder: complete learning_objective, provenance.license_or_permission, "
            "review.status, and review.rendering_status before publication."
        )
