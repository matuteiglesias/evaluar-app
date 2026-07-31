from django.core.management.base import BaseCommand, CommandError
from content_pipeline import compile_content


class Command(BaseCommand):
    help = "Validate a source content tree without publishing it."

    def add_arguments(self, parser):
        parser.add_argument("content_root")

    def handle(self, *args, **options):
        bundle = compile_content(options["content_root"])
        for issue in bundle.issues:
            self.stdout.write(f"{issue.severity}: {issue.code}: {issue.path}: {issue.detail}")
        if not bundle.valid:
            raise CommandError("Content validation failed.")
        self.stdout.write(self.style.SUCCESS(f"Content is valid ({bundle.manifest_checksum})."))
