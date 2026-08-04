import threading

import pytest
from django.db import close_old_connections

from evaluar.courses.models import ContentPublication, Course, Exercise, ExerciseVersion
from evaluar.identity.models import CourseMembership, User
from evaluar.support.models import TicketAssignment
from evaluar.support.services import claim_ticket, create_ticket


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_concurrent_claims_have_exactly_one_winner(django_db_setup, django_db_blocker):
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL-specific row-locking test")

    course = Course.objects.create(slug="claim-race", name="Claim race")
    publication = ContentPublication.objects.create(
        course=course, source_commit="race", manifest_checksum="race", status="published"
    )
    exercise = Exercise.objects.create(course=course, slug="one", external_key="one")
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="race",
        title="One",
        source_format="text",
        source_text="Q",
        rendered_html="Q",
        publication=publication,
    )
    student = User.objects.create_user(username="race-student")
    teachers = [
        User.objects.create_user(username="race-teacher-one"),
        User.objects.create_user(username="race-teacher-two"),
    ]
    CourseMembership.objects.create(user=student, course=course, role="student")
    for teacher in teachers:
        CourseMembership.objects.create(user=teacher, course=course, role="teacher")
    ticket, _ = create_ticket(
        student=student,
        course=course,
        exercise_version=version,
        question="Concurrent claim",
        idempotency_key="race",
    )

    barrier = threading.Barrier(2)
    results = []
    result_lock = threading.Lock()

    def claim(teacher_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            claim_ticket(
                ticket=ticket.__class__.objects.get(pk=ticket.pk),
                teacher=User.objects.get(pk=teacher_id),
            )
        except Exception as exc:  # The losing claim must fail after the winner commits.
            result = ("lost", exc.__class__.__name__)
        else:
            result = ("won", None)
        finally:
            close_old_connections()
        with result_lock:
            results.append(result)

    threads = [threading.Thread(target=claim, args=(teacher.id,)) for teacher in teachers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(result[0] for result in results) == ["lost", "won"]
    assert TicketAssignment.objects.filter(ticket=ticket, status="active").count() == 1
    ticket.refresh_from_db()
    assert ticket.status == "assigned"
    assert ticket.events.filter(event_type="claimed").count() == 1
