import json
from types import SimpleNamespace

import pytest
from django.db import connection
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
        self.deliveries = []
        self.error = error

    def dispatch(self, *, submission_id, dispatch_id):
        if self.error:
            raise self.error
        self.deliveries.append((submission_id, dispatch_id))
        return f"tasks/{submission_id}-{dispatch_id}"


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
    assert dispatcher.deliveries == [(submission.id, event.id)]
    assert event.payload == {"submission_id": str(submission.id)}
    assert event.dispatched_at is not None
    assert event.status == OutboxEvent.Status.DISPATCHED
    assert submission.status == TutoringSubmission.Status.QUEUED


def test_failed_dispatch_remains_in_outbox_for_repair():
    _, submission = accepted_submission()
    assert dispatch_pending(FakeDispatcher(RuntimeError("queue unavailable"))) == 0
    event = OutboxEvent.objects.get()
    assert event.dispatched_at is None
    assert event.dispatch_attempts == 1
    assert event.last_error == "queue unavailable"
    assert event.status == OutboxEvent.Status.PENDING
    assert event.claimed_at is None
    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.ACCEPTED


@pytest.mark.django_db(transaction=True)
def test_dispatcher_calls_external_adapter_after_claim_transaction_commits():
    _, submission = accepted_submission()

    class TransactionCheckingDispatcher(FakeDispatcher):
        def dispatch(self, *, submission_id, dispatch_id):
            assert not connection.in_atomic_block
            return super().dispatch(submission_id=submission_id, dispatch_id=dispatch_id)

    assert dispatch_pending(TransactionCheckingDispatcher()) == 1
    assert OutboxEvent.objects.get(aggregate_id=submission.id).status == "dispatched"


def test_failed_event_does_not_block_later_outbox_events():
    _, first = accepted_submission()
    first_event = OutboxEvent.objects.get()
    first_event.aggregate_id = first.id
    first_event.save(update_fields=("aggregate_id",))
    second_event = OutboxEvent.objects.create(
        topic="tutoring.submission.requeued",
        aggregate_id=first.id,
        payload={"submission_id": str(first.id)},
    )

    class FailFirstDispatcher(FakeDispatcher):
        def dispatch(self, *, submission_id, dispatch_id):
            if dispatch_id == first_event.id:
                raise RuntimeError("first unavailable")
            return super().dispatch(submission_id=submission_id, dispatch_id=dispatch_id)

    dispatcher = FailFirstDispatcher()
    assert dispatch_pending(dispatcher) == 1
    first_event.refresh_from_db()
    second_event.refresh_from_db()
    assert first_event.status == OutboxEvent.Status.PENDING
    assert second_event.status == OutboxEvent.Status.DISPATCHED


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
    event = OutboxEvent.objects.get()
    dispatcher.dispatch(submission_id=submission.id, dispatch_id=event.id)
    assert json.loads(client.task["http_request"]["body"]) == {"submission_id": str(submission.id)}
    assert str(submission.id) in client.task["name"]
    assert str(event.id) in client.task["name"]


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


def test_requeue_uses_a_new_cloud_task_name_for_the_new_outbox_delivery():
    _, submission = accepted_submission()
    dispatcher = FakeDispatcher()
    assert dispatch_pending(dispatcher) == 1
    first_task = dispatcher.deliveries[0]

    submission.status = TutoringSubmission.Status.FAILED
    submission.save(update_fields=("status",))
    requeue_submission(submission.id)

    assert dispatch_pending(dispatcher) == 1
    second_task = dispatcher.deliveries[1]
    assert first_task[0] == second_task[0] == submission.id
    assert first_task[1] != second_task[1]


@override_settings(
    TUTORING_TASK_AUDIENCE="https://worker",
    TUTORING_TASK_SERVICE_ACCOUNT="tasks@example.iam.gserviceaccount.com",
    TUTORING_MODEL_FACTORY="unused.factory",
    TUTORING_TASK_MAX_ATTEMPTS=2,
)
def test_worker_preserves_ambiguous_provider_success_at_retry_exhaustion(
    client, monkeypatch, caplog
):
    _, submission = accepted_submission()
    attempt = TutoringAttempt.objects.create(
        submission=submission,
        number=1,
        status=TutoringAttempt.Status.PROVIDER_SUCCEEDED,
        prompt_checksum=submission.prompt_version.checksum,
        response_schema_version="1",
        provider="openai",
        provider_request_id="provider-request-1",
    )
    submission.status = TutoringSubmission.Status.RUNNING
    submission.save(update_fields=("status",))

    calls = 0

    class CountingModel:
        async def generate(self, request):
            nonlocal calls
            calls += 1
            return result()

    monkeypatch.setattr(
        "evaluar.tutoring.views._verify_oidc_token",
        lambda token: {
            "email": "tasks@example.iam.gserviceaccount.com",
            "email_verified": True,
        },
    )
    monkeypatch.setattr(
        "evaluar.tutoring.views.import_string",
        lambda path: lambda: SimpleNamespace(for_prompt=lambda prompt: CountingModel()),
    )

    response = client.post(
        reverse("tutoring-worker:run"),
        {"submission_id": str(submission.id)},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer valid",
        HTTP_X_CLOUDTASKS_TASKRETRYCOUNT="1",
    )

    assert response.status_code == 204
    assert calls == 0
    attempt.refresh_from_db()
    submission.refresh_from_db()
    assert attempt.status == TutoringAttempt.Status.PROVIDER_SUCCEEDED
    assert submission.status == TutoringSubmission.Status.RUNNING
    assert "tutoring.ambiguous_attempt" in caplog.messages
