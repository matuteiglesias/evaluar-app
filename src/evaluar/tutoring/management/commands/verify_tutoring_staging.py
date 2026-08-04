import json
import os
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string
from pydantic import ValidationError

from evaluar.courses.models import ExerciseVersion
from evaluar.identity.models import CourseMembership, User
from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.infrastructure.client_factory import ModelPolicy
from evaluar.tutoring.models import ActivePrompt, OutboxEvent, TutoringAttempt
from evaluar.tutoring.ports import TutoringModelResult
from evaluar.tutoring.queue import dispatch_pending
from evaluar.tutoring.services import run_submission, submit_answer


class _StagingDispatcher:
    def __init__(self):
        self.deliveries = []

    def dispatch(self, *, submission_id, dispatch_id):
        self.deliveries.append((submission_id, dispatch_id))
        return f"staging/{dispatch_id}"


class Command(BaseCommand):
    help = "Run a deterministic, machine-verifiable tutoring flow against persisted staging data."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True)
        parser.add_argument("--exercise-version-id", required=True)
        parser.add_argument("--idempotency-key", required=True)
        parser.add_argument("--answer", default="Deterministic staging verification answer.")
        parser.add_argument("--live", action="store_true")

    def handle(self, *args, **options):
        if not settings.TUTORING_ENABLED:
            self._fail("TUTORING_ENABLED=1 is required.")
        live = options["live"]
        if live and os.environ.get("TUTORING_LIVE_TEST") != "1":
            self._fail(
                "Live mode is not authorized. Required: TUTORING_LIVE_TEST=1, "
                "TUTORING_ENABLED=1, TUTORING_MODEL_FACTORY, and either "
                "TUTORING_OPENAI_API_KEY or TUTORING_AZURE_OPENAI_ENDPOINT plus "
                "TUTORING_AZURE_OPENAI_API_KEY. Rerun this exact command; expect status=passed, "
                "outbox_dispatched=true, duplicate_execution_prevented=true, and "
                "trace_complete=true."
            )
        try:
            user = User.objects.get(pk=UUID(options["user_id"]))
            version = ExerciseVersion.objects.select_related("exercise__course").get(
                pk=UUID(options["exercise_version_id"])
            )
        except (ValueError, User.DoesNotExist, ExerciseVersion.DoesNotExist):
            self._fail("The supplied persisted user or exercise version does not exist.")
        if not CourseMembership.objects.filter(
            user=user, course=version.exercise.course, status="active", role="student"
        ).exists():
            self._fail("The user needs an active student membership for the exercise course.")
        active = (
            ActivePrompt.objects.select_related("prompt_version")
            .filter(
                public_id=settings.TUTORING_PROMPT_PUBLIC_ID,
                prompt_version__status="published",
            )
            .first()
        )
        if not active:
            self._fail("An active published tutoring prompt is required.")
        try:
            policy = ModelPolicy.model_validate(active.prompt_version.model_policy)
        except ValidationError:
            self._fail("The active prompt model policy is invalid.")
        if live:
            factory = import_string(settings.TUTORING_MODEL_FACTORY)()
            model = factory.for_prompt(active.prompt_version)
            provider_mode = policy.provider
        else:
            model = FakeTutoringModel(
                TutoringModelResult(
                    summary="Deterministic staging guidance.",
                    diagnosis=("The verification diagnosis was captured.",),
                    next_steps=("Review the persisted trace.",),
                    hints=("No network provider was called.",),
                    confidence="high",
                    provider="fake",
                    requested_model="deterministic-staging-v1",
                    served_model="deterministic-staging-v1",
                    provider_request_id="fake-staging-request",
                    input_tokens=11,
                    output_tokens=13,
                    latency_ms=0,
                    framework_name="evaluar-fake",
                    framework_version="1",
                )
            )
            provider_mode = "fake"
        submission = submit_answer(
            user=user,
            exercise_version=version,
            prompt_version=active.prompt_version,
            student_answer=options["answer"],
            idempotency_key=options["idempotency_key"],
        )
        dispatcher = _StagingDispatcher()
        dispatched = dispatch_pending(dispatcher)
        response = run_submission(submission.id, model)
        duplicate = run_submission(submission.id, model)
        attempt = TutoringAttempt.objects.get(submission=submission, status="persisted")
        trace_fields = (
            "framework_name",
            "framework_version",
            "provider",
            "requested_model",
            "served_model",
            "provider_request_id",
            "input_tokens",
            "output_tokens",
            "latency_ms",
        )
        trace_complete = all(getattr(attempt, field) not in (None, "") for field in trace_fields)
        outbox_dispatched = (
            dispatched == 1
            or OutboxEvent.objects.filter(
                aggregate_id=submission.id, dispatched_at__isnull=False
            ).exists()
        )
        duplicate_prevented = (
            duplicate == response
            and TutoringAttempt.objects.filter(submission=submission).count() == 1
        )
        passed = bool(response and duplicate_prevented and trace_complete and outbox_dispatched)
        report = {
            "status": "passed" if passed else "failed",
            "provider_mode": provider_mode,
            "prompt_valid": True,
            "provider_configured": True,
            "submission_id": str(submission.id),
            "submission_accepted": True,
            "response_id": str(response.id) if response else None,
            "worker_processed": response is not None,
            "response_stored": bool(response and response.pk),
            "outbox_dispatched": outbox_dispatched,
            "duplicate_execution_prevented": duplicate_prevented,
            "trace_complete": trace_complete,
            "trace": {field: getattr(attempt, field) for field in trace_fields},
        }
        self.stdout.write(json.dumps(report, sort_keys=True))
        if not passed:
            raise CommandError("Tutoring staging verification failed.")

    def _fail(self, detail):
        self.stdout.write(json.dumps({"status": "failed", "detail": detail}, sort_keys=True))
        raise CommandError(detail)
