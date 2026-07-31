from django.core.management.base import BaseCommand, CommandError

from evaluar.tutoring.operations import resolve_ambiguous_attempt
from evaluar.tutoring.services import InvalidTransition


class Command(BaseCommand):
    help = "Apply an explicit audited decision to one ambiguous tutoring attempt."

    def add_arguments(self, parser):
        parser.add_argument("--attempt", required=True)
        parser.add_argument(
            "--decision", required=True, choices=("terminal", "retry", "attach-evidence")
        )
        parser.add_argument("--actor", required=True)
        parser.add_argument("--note", required=True)
        parser.add_argument("--provider-request-id", default="")

    def handle(self, *args, **options):
        try:
            attempt = resolve_ambiguous_attempt(
                attempt_id=options["attempt"],
                decision=options["decision"],
                actor=options["actor"],
                note=options["note"],
                provider_request_id=options["provider_request_id"],
            )
        except (InvalidTransition, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Attempt {attempt.id} is now {attempt.status}."))
