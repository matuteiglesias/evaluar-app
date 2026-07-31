from django.core.management.base import BaseCommand

from evaluar.tutoring.models import TutoringAttempt


class Command(BaseCommand):
    help = "List attempts that may have completed at the provider without a persisted response."

    def handle(self, *args, **options):
        attempts = TutoringAttempt.objects.filter(
            status=TutoringAttempt.Status.PROVIDER_SUCCEEDED,
            submission__response__isnull=True,
        ).select_related("submission")
        for attempt in attempts.order_by("created_at"):
            self.stdout.write(
                f"{attempt.id} submission={attempt.submission_id} "
                f"provider_request_id={attempt.provider_request_id or '-'}"
            )
        self.stdout.write(f"Ambiguous attempts: {attempts.count()}")
