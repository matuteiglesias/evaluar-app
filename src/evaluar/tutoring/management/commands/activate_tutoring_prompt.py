from django.core.management.base import BaseCommand, CommandError

from evaluar.tutoring.models import PromptVersion
from evaluar.tutoring.operations import activate_prompt


class Command(BaseCommand):
    help = "Activate or roll back to an immutable published tutoring prompt version."

    def add_arguments(self, parser):
        parser.add_argument("--public-id", required=True)
        parser.add_argument("--prompt-version", required=True, type=int)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--note", required=True)

    def handle(self, *args, **options):
        try:
            active = activate_prompt(
                public_id=options["public_id"],
                version=options["prompt_version"],
                actor=options["actor"],
                note=options["note"],
            )
        except PromptVersion.DoesNotExist as exc:
            raise CommandError("Prompt version does not exist.") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Active prompt {active.public_id} is version {active.prompt_version.version}."
            )
        )
