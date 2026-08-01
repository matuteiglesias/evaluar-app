from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from evaluar.tutoring.models import PromptDraft
from evaluar.tutoring.operations import publish_prompt
from evaluar.tutoring.services import InvalidTransition


class Command(BaseCommand):
    help = "Publish an immutable tutoring prompt from a validated draft."

    def add_arguments(self, parser):
        parser.add_argument("--public-id", required=True)
        parser.add_argument("--prompt-version", required=True, type=int)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--note", required=True)

    def handle(self, *args, **options):
        try:
            prompt = publish_prompt(
                public_id=options["public_id"],
                version=options["prompt_version"],
                actor=options["actor"],
                note=options["note"],
            )
        except (PromptDraft.DoesNotExist, InvalidTransition, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Published prompt {prompt.public_id} version {prompt.version}; not activated."
            )
        )
