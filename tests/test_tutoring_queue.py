import json
from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse

from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.models import OutboxEvent, TutoringAttempt, TutoringSubmission
from evaluar.tutoring.ports import RetryableModelError
from evaluar.tutoring.queue import CloudTasksDispatcher, dispatch_pending
from evaluar.tutoring.services import (
    requeue_submission,
    run_submission,
    submit_answer,
    submit_feedback,
)
from test_tutoring import context, result

pytestmark = pytest.mark.django_db


class FakeDispatcher:
    def __init__(self, error=None):
        self.submission_ids = []
        self.error = error

    def dispatch(self, submission_id):
        if self.error:
            raise self.error
        self.submission_ids.append(submission_id)
        return f"tasks/{submission_id}"


class RetryableFakeModel:
    async def generate(self, request):
        raise RetryableModelError("temporary provider outage")


def accepted_submission():
    user, version, prompt = context()
    submission = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="answer",
        idempotency_key="queue-1",
    )
    return user, submission


def test_outbox_dispatches_only_submission_id_and_updates_authoritative_state():
    _, submission = accepted_submission()
    dispatcher = FakeDispatcher()
    assert dispatch_pending(dispatcher) == 1
    submission.refresh_from_db()
    event = OutboxEvent.objects.get()
    assert dispatcher.submission_ids == [submission.id]
    assert event.payload == {"submission_id": str(submission.id)}
    assert event.dispatched_at is not None
    assert submission.status == TutoringSubmission.Status.QUEUED


def test_failed_dispatch_remains_in_outbox_for_repair():
    _, submission = accepted_submission()
    assert dispatch_pending(FakeDispatcher(RuntimeError("queue unavailable"))) == 0
    event = OutboxEvent.objects.get()
    assert event.dispatched_at is None
    assert event.dispatch_attempts == 1
    assert event.last_error == "queue unavailable"
    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.ACCEPTED


def test_cloud_tasks_payload_is_minimal_and_task_name_is_deterministic():
    _, submission = accepted_submission()

    class Client:
        def create_task(self, *, parent, task):
            self.parent = parent
            self.task = task
            return SimpleNamespace(name=task["name"])

    client = Client()
    dispatcher = CloudTasksDispatcher(
        client=client,
        queue_path="projects/p/locations/l/queues/q",
        worker_url="https://worker/internal/tutoring/run",
        service_account_email="tasks@example.iam.gserviceaccount.com",
        audience="https://worker",
    )
    dispatcher.dispatch(submission.id)
    assert json.loads(client.task["http_request"]["body"]) == {"submission_id": str(submission.id)}
    assert str(submission.id) in client.task["name"]


@override_settings(
    TUTORING_TASK_AUDIENCE="https://worker",
    TUTORING_TASK_SERVICE_ACCOUNT="tasks@example.iam.gserviceaccount.com",
    TUTORING_MODEL_FACTORY="unused.factory",
    TUTORING_TASK_MAX_ATTEMPTS=2,
)
def test_authenticated_worker_retries_then_marks_terminal(client, monkeypatch):
    _, submission = accepted_submission()
    monkeypatch.setattr(
        "evaluar.tutoring.views._verify_oidc_token",
        lambda token: {
            "email": "tasks@example.iam.gserviceaccount.com",
            "email_verified": True,
        },
    )
    monkeypatch.setattr(
        "evaluar.tutoring.views.import_string",
        lambda path: lambda: SimpleNamespace(for_prompt=lambda prompt: RetryableFakeModel()),
    )
    url = reverse("tutoring-worker:run")
    headers = {"HTTP_AUTHORIZATION": "Bearer valid"}
    first = client.post(
        url, {"submission_id": str(submission.id)}, content_type="application/json", **headers
    )
    assert first.status_code == 503
    second = client.post(
        url,
        {"submission_id": str(submission.id)},
        content_type="application/json",
        HTTP_X_CLOUDTASKS_TASKRETRYCOUNT="1",
        **headers,
    )
    assert second.status_code == 204
    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.FAILED
    assert submission.attempts.order_by("-number").first().status == "terminal_failed"


@override_settings(
    TUTORING_TASK_AUDIENCE="https://worker",
    TUTORING_TASK_SERVICE_ACCOUNT="tasks@example.iam.gserviceaccount.com",
    TUTORING_MODEL_FACTORY="unused.factory",
)
def test_worker_rejects_unauthenticated_and_nonminimal_payloads(client, monkeypatch):
    _, submission = accepted_submission()
    url = reverse("tutoring-worker:run")
    assert (
        client.post(
            url, {"submission_id": str(submission.id)}, content_type="application/json"
        ).status_code
        == 401
    )
    monkeypatch.setattr(
        "evaluar.tutoring.views._verify_oidc_token",
        lambda token: {
            "email": "tasks@example.iam.gserviceaccount.com",
            "email_verified": True,
        },
    )
    response = client.post(
        url,
        {"submission_id": str(submission.id), "answer": "must-not-enter-task"},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer valid",
    )
    assert response.status_code == 400


def test_feedback_is_durably_linked_and_owner_only():
    user, submission = accepted_submission()
    response = run_submission(submission.id, FakeTutoringModel(result()))
    feedback = submit_feedback(user=user, response=response, helpful=True, comment="Useful")
    assert feedback.response == response
    assert feedback.response.submission == submission
    outsider = type(user).objects.create_user("outsider@example.com")
    with pytest.raises(PermissionError):
        submit_feedback(user=outsider, response=response, helpful=False)


@override_settings(TUTORING_ATTEMPT_LEASE_SECONDS=0)
def test_expired_worker_attempt_is_repairable_after_crash():
    _, submission = accepted_submission()
    TutoringAttempt.objects.create(
        submission=submission,
        number=1,
        status=TutoringAttempt.Status.STARTED,
        prompt_checksum=submission.prompt_version.checksum,
        response_schema_version="1",
    )
    response = run_submission(submission.id, FakeTutoringModel(result()))
    assert response is not None
    first = submission.attempts.get(number=1)
    assert first.status == TutoringAttempt.Status.RETRYABLE_FAILED
    assert first.error_category == "worker_lease_expired"


def test_terminal_submission_can_be_requeued_through_a_new_outbox_event():
    _, submission = accepted_submission()
    submission.status = TutoringSubmission.Status.FAILED
    submission.save(update_fields=("status",))
    original_event = OutboxEvent.objects.get()
    original_event.dispatched_at = original_event.created_at
    original_event.save(update_fields=("dispatched_at",))

    requeue_submission(submission.id)

    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.QUEUED
    repair_event = OutboxEvent.objects.get(topic="tutoring.submission.requeued")
    assert repair_event.payload == {"submission_id": str(submission.id)}
    assert repair_event.dispatched_at is None
