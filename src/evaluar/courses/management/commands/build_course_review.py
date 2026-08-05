from pathlib import Path
from django.core.management.base import BaseCommand
from evaluar.content_pipeline.collection import (
    compile_manifest_course,
    load_manifest,
    manifest_path,
    collection_inventory,
    review_html,
    review_markdown,
    validate_manifest,
)


class Command(BaseCommand):
    help = "Build a static instructor review packet for one course collection."

    def add_arguments(self, parser):
        parser.add_argument("course_slug")
        parser.add_argument("--root", default=".")
        parser.add_argument("--output", required=True)
        parser.add_argument("--source-commit", default="unknown")

    def handle(self, *args, **options):
        manifest = load_manifest(manifest_path(options["root"], options["course_slug"]))
        issues = validate_manifest(manifest)
        bundle = None
        if not any(item.severity == "error" for item in issues):
            bundle = compile_manifest_course(manifest, source_commit=options["source_commit"])
        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        index = output / "index.html"
        index.write_text(review_html(manifest, bundle), encoding="utf-8")
        inventory = output / "inventory.json"
        import json

        inventory.write_text(
            json.dumps(
                collection_inventory(manifest, bundle), ensure_ascii=False, indent=2, sort_keys=True
            ),
            encoding="utf-8",
        )
        review = output / "review.md"
        review.write_text(review_markdown(manifest, bundle), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {index}"))
