import pytest
from evaluar.courses.models import ContentPublication, Course, Exercise, ExerciseVersion
from evaluar.identity.models import CourseMembership, User
from evaluar.support.notifications import dispatch_support_notifications
from evaluar.support.services import create_ticket
from evaluar.tutoring.models import OutboxEvent


class FailingSender:
    def send(self, event):
        raise RuntimeError("mail transport unavailable")


@pytest.mark.django_db
def test_notification_outbox_is_created_without_network():
    course = Course.objects.create(slug="notify", name="Notify")
    publication = ContentPublication.objects.create(
        course=course, source_commit="n", manifest_checksum="n", status="published"
    )
    exercise = Exercise.objects.create(course=course, slug="one", external_key="one")
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="n",
        title="One",
        source_format="text",
        source_text="Q",
        rendered_html="Q",
        publication=publication,
    )
    student = User.objects.create_user(username="notify-student")
    CourseMembership.objects.create(user=student, course=course, role="student")
    ticket, _ = create_ticket(
        student=student,
        course=course,
        exercise_version=version,
        question="Need help",
        idempotency_key="notify",
    )
    event = OutboxEvent.objects.get(aggregate_id=ticket.id)
    assert event.topic == "support.ticket.created"
    assert event.payload["ticket_id"] == str(ticket.id)


@pytest.mark.django_db
def test_notification_failure_is_retryable_and_does_not_rollback_ticket():
    course = Course.objects.create(slug="failure", name="Failure")
    publication = ContentPublication.objects.create(
        course=course, source_commit="f", manifest_checksum="f", status="published"
    )
    exercise = Exercise.objects.create(course=course, slug="one", external_key="one")
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="f",
        title="One",
        source_format="text",
        source_text="Q",
        rendered_html="Q",
        publication=publication,
    )
    student = User.objects.create_user(username="failure-student")
    CourseMembership.objects.create(user=student, course=course, role="student")
    ticket, _ = create_ticket(
        student=student,
        course=course,
        exercise_version=version,
        question="Need help",
        idempotency_key="failure",
    )

    assert dispatch_support_notifications(FailingSender()) == 0
    assert ticket.__class__.objects.filter(pk=ticket.pk, status="open").exists()
    event = OutboxEvent.objects.get(aggregate_id=ticket.id)
    assert event.status == OutboxEvent.Status.PENDING
    assert event.dispatch_attempts == 1
    assert event.last_error == "mail transport unavailable"
