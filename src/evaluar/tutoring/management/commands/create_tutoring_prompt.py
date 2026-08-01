import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from evaluar.tutoring.operations import create_prompt_draft


class Command(BaseCommand):
    help = "Create a validated tutoring prompt draft from operator-controlled files."

    def add_arguments(self, parser):
        parser.add_argument("--public-id", required=True)
        parser.add_argument("--instructions-file", required=True)
        parser.add_argument("--model-policy-file", required=True)
        parser.add_argument("--actor", required=True)

    def handle(self, *args, **options):
        try:
            instructions = Path(options["instructions_file"]).read_text(encoding="utf-8")
            policy = json.loads(Path(options["model_policy_file"]).read_text(encoding="utf-8"))
            draft = create_prompt_draft(
                public_id=options["public_id"],
                instructions=instructions,
                model_policy=policy,
                actor=options["actor"],
            )
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise CommandError(f"Could not create prompt draft: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(f"Created prompt draft {draft.public_id} version {draft.version}.")
        )
