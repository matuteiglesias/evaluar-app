from io import StringIO

import pytest
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import override_settings

from evaluar.identity.models import CourseMembership
from evaluar.support.notifications import dispatch_support_notifications
from evaluar.support.services import create_ticket
from evaluar.tutoring.models import ActivePrompt, OutboxEvent
from evaluar.tutoring.services import submit_answer
from test_tutoring import context


pytestmark = pytest.mark.django_db


@override_settings(TUTORING_ENABLED=False, SUPPORT_ENABLED=False)
def test_disabled_http_features_are_unreachable(client):
    assert client.get("/tutoring/anything").status_code == 404
    assert client.get("/internal/tutoring/run").status_code == 404
    assert client.get("/support/").status_code == 404


@override_settings(TUTORING_ENABLED=False)
def test_tutoring_backend_rejects_new_work():
    user, version, prompt = context()
    with pytest.raises(PermissionDenied):
        submit_answer(
            user=user,
            exercise_version=version,
            prompt_version=prompt,
            student_answer="answer",
            idempotency_key="disabled",
        )


@override_settings(SUPPORT_ENABLED=False)
def test_support_backend_rejects_new_work():
    user, version, _prompt = context()
    CourseMembership.objects.create(user=user, course=version.exercise.course, role="student")
    with pytest.raises(PermissionDenied):
        create_ticket(
            student=user,
            course=version.exercise.course,
            exercise_version=version,
            question="help",
            idempotency_key="disabled",
        )


@override_settings(SUPPORT_ENABLED=True, SUPPORT_NOTIFICATIONS_ENABLED=False)
def test_notification_no_delivery_mode_preserves_pending_outbox(caplog):
    event = OutboxEvent.objects.create(
        topic="support.ticket.created", aggregate_id="00000000-0000-0000-0000-000000000001"
    )

    class Sender:
        def send(self, event):
            raise AssertionError("disabled delivery must not call a sender")

    assert dispatch_support_notifications(Sender()) == 0
    event.refresh_from_db()
    assert event.status == OutboxEvent.Status.PENDING
    assert event.dispatch_attempts == 0
    assert "notification_not_configured" in caplog.text


def test_deterministic_tutoring_staging_command():
    user, version, prompt = context()
    CourseMembership.objects.create(user=user, course=version.exercise.course, role="student")
    prompt.model_policy = {"provider": "openai", "requested_model": "not-called"}
    # Prompt versions are immutable through save; direct setup update mirrors an already-published row.
    type(prompt).objects.filter(pk=prompt.pk).update(model_policy=prompt.model_policy)
    ActivePrompt.objects.create(public_id="default", prompt_version=prompt)
    output = StringIO()

    call_command(
        "verify_tutoring_staging",
        user_id=str(user.id),
        exercise_version_id=str(version.id),
        idempotency_key="staging-proof",
        stdout=output,
    )

    import json

    report = json.loads(output.getvalue())
    assert report["status"] == "passed"
    assert report["provider_mode"] == "fake"
    assert report["outbox_dispatched"] is True
    assert report["duplicate_execution_prevented"] is True
    assert report["trace_complete"] is True
