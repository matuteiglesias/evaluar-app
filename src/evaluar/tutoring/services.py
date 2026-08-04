import html
from dataclasses import asdict

import bleach  # type: ignore[import-untyped]
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import (
    OutboxEvent,
    CourseTutoringQuotaUsage,
    PromptVersion,
    StudentFeedback,
    TutoringAttempt,
    TutoringQuotaUsage,
    TutoringResponse,
    TutoringSubmission,
)
from .ports import RetryableModelError, TerminalModelError, TutoringModel, TutoringModelRequest


class QuotaExceeded(Exception):
    pass


class InvalidTransition(Exception):
    pass


class AmbiguousAttemptRequiresManualResolution(Exception):
    """An automatic action tried to overwrite an ambiguous provider success."""


@transaction.atomic
def submit_answer(
    *,
    user,
    exercise_version,
    prompt_version: PromptVersion,
    student_answer: str,
    idempotency_key: str,
    response_language: str = "es",
) -> TutoringSubmission:
    if not settings.TUTORING_ENABLED:
        raise PermissionDenied("Tutoring is disabled.")
    existing = TutoringSubmission.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing:
        return existing

    if prompt_version.status != PromptVersion.Status.PUBLISHED:
        raise InvalidTransition("Submissions require a published prompt version.")
    try:
        with transaction.atomic():
            submission = TutoringSubmission.objects.create(
                user=user,
                exercise_version=exercise_version,
                prompt_version=prompt_version,
                student_answer=student_answer,
                response_language=response_language,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        return TutoringSubmission.objects.get(user=user, idempotency_key=idempotency_key)

    course = exercise_version.exercise.course
    # The course row is the stable lock even before daily usage rows exist.
    type(course).objects.select_for_update().get(pk=course.pk)
    try:
        with transaction.atomic():
            usage, _ = TutoringQuotaUsage.objects.get_or_create(
                user=user, course=course, day=timezone.localdate()
            )
    except IntegrityError:
        usage = TutoringQuotaUsage.objects.get(user=user, course=course, day=timezone.localdate())
    usage = TutoringQuotaUsage.objects.select_for_update().get(pk=usage.pk)
    daily_limit = getattr(settings, "TUTORING_DAILY_QUOTA", 20)
    if usage.reserved_count >= daily_limit:
        raise QuotaExceeded("Daily tutoring quota exceeded.")
    usage.reserved_count = F("reserved_count") + 1
    usage.save(update_fields=("reserved_count",))

    course_usage, _ = CourseTutoringQuotaUsage.objects.select_for_update().get_or_create(
        course=course, day=timezone.localdate()
    )
    course_daily_limit = getattr(settings, "TUTORING_COURSE_DAILY_QUOTA", 2000)
    if course_usage.reserved_count >= course_daily_limit:
        raise QuotaExceeded("Daily course tutoring quota exceeded.")
    course_usage.reserved_count = F("reserved_count") + 1
    course_usage.save(update_fields=("reserved_count",))

    OutboxEvent.objects.create(
        topic="tutoring.submission.accepted",
        aggregate_id=submission.id,
        payload={"submission_id": str(submission.id)},
    )
    return submission


@transaction.atomic
def claim_submission(submission_id) -> TutoringAttempt | None:
    submission = TutoringSubmission.objects.select_for_update().get(pk=submission_id)
    if submission.status in (
        TutoringSubmission.Status.SUCCEEDED,
        TutoringSubmission.Status.CANCELLED,
    ):
        return None
    active = (
        submission.attempts.filter(
            status__in=(
                TutoringAttempt.Status.CREATED,
                TutoringAttempt.Status.STARTED,
                TutoringAttempt.Status.PROVIDER_SUCCEEDED,
            )
        )
        .order_by("-number")
        .first()
    )
    if active:
        if active.status == TutoringAttempt.Status.PROVIDER_SUCCEEDED:
            # Provider completion without a persisted response is ambiguous. Only an audited
            # operator decision may authorize another billable call.
            return None
        lease_seconds = getattr(settings, "TUTORING_ATTEMPT_LEASE_SECONDS", 900)
        lease_started = active.started_at or active.created_at
        if lease_started > timezone.now() - timezone.timedelta(seconds=lease_seconds):
            return None
        active.status = TutoringAttempt.Status.RETRYABLE_FAILED
        active.error_category = "worker_lease_expired"
        active.error_detail = "The worker did not finish before its lease expired."
        active.finished_at = timezone.now()
        active.save(update_fields=("status", "error_category", "error_detail", "finished_at"))
    last_number = submission.attempts.aggregate(value=Max("number"))["value"] or 0
    attempt = TutoringAttempt.objects.create(
        submission=submission,
        number=last_number + 1,
        status=TutoringAttempt.Status.STARTED,
        prompt_checksum=submission.prompt_version.checksum,
        response_schema_version=submission.prompt_version.response_schema_version,
        started_at=timezone.now(),
    )
    submission.status = TutoringSubmission.Status.RUNNING
    submission.save(update_fields=("status", "updated_at"))
    return attempt


def _validate_result(result) -> None:
    if not result.summary.strip() or not result.diagnosis or not result.next_steps:
        raise ValueError("The tutoring result is missing required guidance.")
    if result.confidence not in {"low", "medium", "high"}:
        raise ValueError("The tutoring result has an invalid confidence value.")


def _render(result) -> str:
    sections = [f"<p>{html.escape(result.summary)}</p>"]
    for title, values in (
        ("Diagnóstico", result.diagnosis),
        ("Próximos pasos", result.next_steps),
        ("Pistas", result.hints),
    ):
        if values:
            items = "".join(f"<li>{html.escape(value)}</li>" for value in values)
            sections.append(f"<h3>{title}</h3><ul>{items}</ul>")
    return bleach.clean("".join(sections), tags={"p", "h3", "ul", "li"}, strip=True)


def run_submission(submission_id, model: TutoringModel) -> TutoringResponse | None:
    attempt = claim_submission(submission_id)
    if attempt is None:
        submission = TutoringSubmission.objects.get(pk=submission_id)
        return getattr(submission, "response", None)
    submission = attempt.submission
    request = TutoringModelRequest(
        exercise_title=submission.exercise_version.title,
        exercise_body=submission.exercise_version.source_text,
        student_answer=submission.student_answer,
        pedagogical_policy=submission.prompt_version.system_instructions,
        response_language=submission.response_language,
    )
    try:
        result = async_to_sync(model.generate)(request)
        _validate_result(result)
    except RetryableModelError as exc:
        _record_failure(attempt.id, TutoringAttempt.Status.RETRYABLE_FAILED, exc.category, exc)
        return None
    except (TerminalModelError, ValueError) as exc:
        category = "validation" if isinstance(exc, ValueError) else exc.category
        status = (
            TutoringAttempt.Status.VALIDATION_FAILED
            if isinstance(exc, ValueError)
            else TutoringAttempt.Status.TERMINAL_FAILED
        )
        _record_failure(attempt.id, status, category, exc, fail_submission=True)
        return None
    except Exception as exc:
        _record_failure(attempt.id, TutoringAttempt.Status.RETRYABLE_FAILED, "unexpected", exc)
        return None

    TutoringAttempt.objects.filter(pk=attempt.id).update(
        status=TutoringAttempt.Status.PROVIDER_SUCCEEDED,
        provider=result.provider,
        requested_model=result.requested_model,
        served_model=result.served_model or "",
        provider_request_id=result.provider_request_id or "",
    )

    with transaction.atomic():
        locked_attempt = TutoringAttempt.objects.select_for_update().get(pk=attempt.id)
        locked_submission = TutoringSubmission.objects.select_for_update().get(pk=submission.id)
        content = asdict(result)
        response, _ = TutoringResponse.objects.get_or_create(
            submission=locked_submission,
            defaults={
                "attempt": locked_attempt,
                "status": TutoringResponse.Status.PUBLISHED,
                "structured_content": content,
                "rendered_html": _render(result),
                "published_at": timezone.now(),
            },
        )
        for field in (
            "framework_name",
            "framework_version",
            "provider",
            "requested_model",
            "served_model",
            "provider_request_id",
            "input_tokens",
            "output_tokens",
            "latency_ms",
        ):
            value = getattr(result, field)
            setattr(
                locked_attempt,
                field,
                value
                if value is not None
                else ""
                if field
                in {
                    "framework_name",
                    "framework_version",
                    "provider",
                    "requested_model",
                    "served_model",
                    "provider_request_id",
                }
                else None,
            )
        locked_attempt.status = TutoringAttempt.Status.PERSISTED
        locked_attempt.finished_at = timezone.now()
        locked_attempt.save()
        locked_submission.status = TutoringSubmission.Status.SUCCEEDED
        locked_submission.save(update_fields=("status", "updated_at"))
        return response


@transaction.atomic
def _record_failure(attempt_id, status, category, exc, *, fail_submission=False):
    attempt = (
        TutoringAttempt.objects.select_for_update().select_related("submission").get(pk=attempt_id)
    )
    attempt.status = status
    attempt.error_category = category
    attempt.error_detail = str(exc)[:2000]
    attempt.finished_at = timezone.now()
    attempt.save(update_fields=("status", "error_category", "error_detail", "finished_at"))
    submission = attempt.submission
    submission.status = (
        TutoringSubmission.Status.FAILED if fail_submission else TutoringSubmission.Status.QUEUED
    )
    submission.save(update_fields=("status", "updated_at"))


@transaction.atomic
def mark_terminal_failure(submission_id, *, category="retries_exhausted") -> None:
    submission = TutoringSubmission.objects.select_for_update().get(pk=submission_id)
    if submission.status == TutoringSubmission.Status.SUCCEEDED:
        return
    active = submission.attempts.order_by("-number").first()
    if active:
        if active.status == TutoringAttempt.Status.PROVIDER_SUCCEEDED:
            raise AmbiguousAttemptRequiresManualResolution(
                "Provider succeeded; an audited operator decision is required."
            )
        active.status = TutoringAttempt.Status.TERMINAL_FAILED
        active.error_category = category
        active.finished_at = timezone.now()
        active.save(update_fields=("status", "error_category", "finished_at"))
    submission.status = TutoringSubmission.Status.FAILED
    submission.save(update_fields=("status", "updated_at"))


@transaction.atomic
def requeue_submission(submission_id) -> TutoringSubmission:
    submission = TutoringSubmission.objects.select_for_update().get(pk=submission_id)
    if submission.status not in (
        TutoringSubmission.Status.FAILED,
        TutoringSubmission.Status.QUEUED,
    ):
        raise InvalidTransition(f"Cannot requeue a {submission.status} submission.")
    if submission.attempts.filter(
        status__in=(
            TutoringAttempt.Status.CREATED,
            TutoringAttempt.Status.STARTED,
            TutoringAttempt.Status.PROVIDER_SUCCEEDED,
        )
    ).exists():
        raise InvalidTransition("Cannot requeue a submission with an active attempt.")
    submission.status = TutoringSubmission.Status.QUEUED
    submission.save(update_fields=("status", "updated_at"))
    OutboxEvent.objects.get_or_create(
        topic="tutoring.submission.requeued",
        aggregate_id=submission.id,
        dispatched_at=None,
        defaults={"payload": {"submission_id": str(submission.id)}},
    )
    return submission


@transaction.atomic
def submit_feedback(
    *, user, response: TutoringResponse, helpful: bool, comment: str = ""
) -> StudentFeedback:
    if response.submission.user_id != user.id:
        raise PermissionError("Feedback can only be submitted by the response owner.")
    feedback, _ = StudentFeedback.objects.update_or_create(
        response=response,
        user=user,
        defaults={"helpful": helpful, "comment": comment},
    )
    return feedback
