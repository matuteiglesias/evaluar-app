from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline.collection import SCHEMA, validate_course_slug

TEMPLATE_STATEMENT = r"""% Example public exercise statement.
% Replace this placeholder with an authoritative, reviewed exercise statement.
% Do not put private solutions, rubrics, or tutor-only guidance in this file.
"""

README_TEMPLATE = """# Course collection workspace

This directory is an instructor-maintained authoring workspace.

## Public material

- `collection.yaml` declares course identity, sections, reviewed exercises, provenance, review state, rendering requirements, and publication gates.
- `exercises/` contains public student-visible exercise statements.
- `assets/` contains public assets referenced by statements.
- `generated/index.csv` is generated from `collection.yaml` for compatibility with the existing compiler. Do not edit it by hand.

## Private material

- `private/solutions/`
- `private/rubrics/`
- `private/tutoring-guidance/`

Private files are for instructors only and are never copied into the student publication bundle by the onboarding commands. Keep answer-revealing material out of public statements and public assets.
"""


class Command(BaseCommand):
    help = "Scaffold a reviewable course collection workspace."

    def add_arguments(self, parser):
        parser.add_argument("course_slug")
        parser.add_argument("--subject", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--language", default="es-AR")
        parser.add_argument("--offering", default="")
        parser.add_argument("--root", default=".")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = Path(options["root"]).resolve()
        course = options["course_slug"]
        if not validate_course_slug(course):
            raise CommandError(
                "course slug must match ^[a-z0-9][a-z0-9_-]{0,63}$ for URL/database safety"
            )
        course_dir = root / "collections" / course
        manifest = course_dir / "collection.yaml"
        if course_dir.exists():
            raise CommandError(f"{course_dir} already exists")
        planned = [
            manifest,
            course_dir / "README.md",
            course_dir / "exercises" / "001.tex",
            course_dir / "assets" / ".gitkeep",
            course_dir / "private" / "solutions" / ".gitkeep",
            course_dir / "private" / "rubrics" / ".gitkeep",
            course_dir / "private" / "tutoring-guidance" / ".gitkeep",
            course_dir / "generated" / ".gitkeep",
        ]
        if options["dry_run"]:
            for path in planned:
                self.stdout.write(f"would create {path}")
            return
        offering = options["offering"] or course.removeprefix(options["subject"] + "-")
        for path in planned:
            path.parent.mkdir(parents=True, exist_ok=True)
        (course_dir / "README.md").write_text(README_TEMPLATE, encoding="utf-8")
        (course_dir / "exercises" / "001.tex").write_text(TEMPLATE_STATEMENT, encoding="utf-8")
        for keep in planned:
            if keep.name == ".gitkeep":
                keep.write_text("", encoding="utf-8")
        manifest.write_text(
            f"""schema: {SCHEMA}

collection:
  id: {options["subject"]}/practical-guide
  release: pilot-v0.1

subject:
  id: {options["subject"]}

course:
  slug: {course}
  name: {options["name"]!r}
  offering: {offering!r}
  language: {options["language"]}

governance:
  owners: []
  reviewers: []

sections:
  - id: pilot
    title: Pilot
    order: 10

exercises:
  - stable_id: {options["subject"]}.pilot.001
    version: 1
    title: Replace with reviewed title
    section: pilot
    order: 10
    statement:
      path: exercises/001.tex
      format: latex
    learning_objective: Replace with the instructor-approved learning objective.
    prerequisites: []
    provenance:
      status: unknown
      author: null
      source: null
      license_or_permission: null
    review:
      status: draft
      reviewer: null
      reviewed_at: null
      rendering_status: pending
    rendering:
      requirements:
        - prose
    tutoring:
      eligible: false
      policy_review_status: pending

assets: []

release:
  notes: []
  publication_eligibility:
    technical_validation: required
    instructor_review: required
    rendering_review: required
""",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Created {course_dir}"))
