from django.core.management.base import BaseCommand, CommandError
from evaluar.content_pipeline import load_bundle
from evaluar.courses.services import publish_bundle


class Command(BaseCommand):
    help = "Verify and atomically publish a deterministic content bundle."

    def add_arguments(self, parser):
        parser.add_argument("bundle")

    def handle(self, *args, **options):
        try:
            bundle = load_bundle(options["bundle"])
            publications = publish_bundle(bundle)
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Published {len(publications)} course release(s) from {bundle.manifest_checksum}."
            )
        )
