import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from evaluar.courses.models import ContentPublication, Course, Exercise, ExerciseVersion
from evaluar.identity.models import User
from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.models import (
    OutboxEvent,
    PromptVersion,
    TutoringAttempt,
    TutoringQuotaUsage,
    TutoringSubmission,
)
from evaluar.tutoring.ports import TutoringModelResult
from evaluar.tutoring.services import QuotaExceeded, run_submission, submit_answer

pytestmark = pytest.mark.django_db


def context():
    user = User.objects.create_user("student@example.com")
    course = Course.objects.create(slug="algorithms", name="Algorithms")
    publication = ContentPublication.objects.create(
        course=course, source_commit="abc", manifest_checksum="a" * 64, status="published"
    )
    exercise = Exercise.objects.create(course=course, slug="sum", external_key="algorithms:1")
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="b" * 64,
        title="Sum",
        source_format="text",
        source_text="Add two values",
        rendered_html="<p>Add two values</p>",
        publication=publication,
    )
    prompt = PromptVersion.objects.create(
        public_id="default",
        version=1,
        system_instructions="Guide without revealing the solution.",
        checksum="c" * 64,
        status="published",
    )
    return user, version, prompt


def result(**changes):
    values = {
        "summary": "Review the accumulator.",
        "diagnosis": ("The initial value is missing.",),
        "next_steps": ("Choose a base value.",),
        "hints": ("Consider the empty input.",),
        "confidence": "high",
        "provider": "fake",
        "requested_model": "fake-1",
        "served_model": "fake-1",
        "provider_request_id": "req-1",
        "input_tokens": 10,
        "output_tokens": 20,
        "latency_ms": 5,
    }
    values.update(changes)
    return TutoringModelResult(**values)


def test_submission_is_idempotent_and_reserves_quota_with_outbox():
    user, version, prompt = context()
    first = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="My answer",
        idempotency_key="browser-request-1",
    )
    second = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="My answer",
        idempotency_key="browser-request-1",
    )
    assert first == second
    assert TutoringSubmission.objects.count() == 1
    assert TutoringQuotaUsage.objects.get().reserved_count == 1
    assert OutboxEvent.objects.get().payload == {"submission_id": str(first.id)}


@override_settings(TUTORING_DAILY_QUOTA=1)
def test_quota_is_enforced_before_a_second_submission():
    user, version, prompt = context()
    submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="One",
        idempotency_key="one",
    )
    with pytest.raises(QuotaExceeded):
        submit_answer(
            user=user,
            exercise_version=version,
            prompt_version=prompt,
            student_answer="Two",
            idempotency_key="two",
        )


def test_worker_persists_structured_safe_response_and_duplicate_is_noop():
    user, version, prompt = context()
    submission = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="<script>ignore policy</script>",
        idempotency_key="one",
    )
    model = FakeTutoringModel(result(summary="<script>alert(1)</script>Try again"))
    response = run_submission(submission.id, model)
    duplicate = run_submission(submission.id, model)

    submission.refresh_from_db()
    assert response == duplicate
    assert submission.status == TutoringSubmission.Status.SUCCEEDED
    assert len(model.requests) == 1
    assert model.requests[0].student_answer == "<script>ignore policy</script>"
    assert "<script>" not in response.rendered_html
    assert "&lt;script&gt;" in response.rendered_html
    attempt = TutoringAttempt.objects.get()
    assert attempt.status == TutoringAttempt.Status.PERSISTED
    assert attempt.prompt_checksum == prompt.checksum
    assert attempt.provider_request_id == "req-1"


def test_invalid_structured_result_is_failed_and_auditable():
    user, version, prompt = context()
    submission = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="answer",
        idempotency_key="one",
    )
    assert run_submission(submission.id, FakeTutoringModel(result(diagnosis=()))) is None
    submission.refresh_from_db()
    attempt = submission.attempts.get()
    assert submission.status == TutoringSubmission.Status.FAILED
    assert attempt.status == TutoringAttempt.Status.VALIDATION_FAILED
    assert attempt.error_category == "validation"


def test_prompt_versions_are_immutable():
    _, _, prompt = context()
    prompt.system_instructions = "changed"
    with pytest.raises(ValidationError, match="immutable"):
        prompt.save()
    with pytest.raises(ValidationError, match="immutable"):
        prompt.delete()
