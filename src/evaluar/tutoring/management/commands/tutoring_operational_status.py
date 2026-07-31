import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from evaluar.tutoring.models import OutboxEvent, TutoringAttempt, TutoringSubmission


class Command(BaseCommand):
    help = "Report the minimum Phase 3 operational signals from authoritative database state."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--normal-processing-seconds", type=int, default=120)

    def handle(self, *args, **options):
        now = timezone.now()
        queued = TutoringSubmission.objects.filter(
            status__in=(TutoringSubmission.Status.ACCEPTED, TutoringSubmission.Status.QUEUED)
        )
        oldest = queued.order_by("created_at").first()
        attempts = TutoringAttempt.objects.all()
        usage = attempts.aggregate(
            input_tokens=Sum("input_tokens"), output_tokens=Sum("output_tokens")
        )
        estimated_cost = 0.0
        for attempt in attempts.select_related("submission__prompt_version"):
            policy = attempt.submission.prompt_version.model_policy
            estimated_cost += (
                (attempt.input_tokens or 0) * float(policy.get("input_usd_per_million", 0))
                + (attempt.output_tokens or 0) * float(policy.get("output_usd_per_million", 0))
            ) / 1_000_000
        signals = {
            "oldest_queued_age_seconds": (
                round((now - oldest.created_at).total_seconds()) if oldest else None
            ),
            "queued_submissions": queued.count(),
            "retryable_failures": attempts.filter(status="retryable_failed").count(),
            "terminal_failures": attempts.filter(status="terminal_failed").count(),
            "ambiguous_attempts": attempts.filter(
                status="provider_succeeded", submission__response__isnull=True
            ).count(),
            "pending_outbox_events": OutboxEvent.objects.filter(dispatched_at__isnull=True).count(),
            "provider_timeouts": attempts.filter(error_category="provider_timeout").count(),
            "provider_rate_limits": attempts.filter(error_category="provider_rate_limited").count(),
            "schema_validation_failures": attempts.filter(error_category="validation").count(),
            "input_tokens": usage["input_tokens"] or 0,
            "output_tokens": usage["output_tokens"] or 0,
            "estimated_cost_usd": round(estimated_cost, 6),
            "overdue_submissions": TutoringSubmission.objects.filter(
                status__in=(
                    TutoringSubmission.Status.ACCEPTED,
                    TutoringSubmission.Status.QUEUED,
                    TutoringSubmission.Status.RUNNING,
                ),
                created_at__lt=now - timedelta(seconds=options["normal_processing_seconds"]),
            ).count(),
        }
        if options["json"]:
            self.stdout.write(json.dumps(signals, sort_keys=True))
        else:
            for name, value in signals.items():
                self.stdout.write(f"{name}: {value}")
