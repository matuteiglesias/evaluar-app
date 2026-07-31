import uuid

import pytest
from django.urls import reverse

from evaluar.courses.models import PublishedExerciseVersion
from evaluar.identity.models import CourseMembership, User
from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.models import ActivePrompt, StudentFeedback, TutoringSubmission
from evaluar.tutoring.services import run_submission, submit_answer
from test_tutoring import context, result

pytestmark = pytest.mark.django_db


def student_context():
    user, version, prompt = context()
    PublishedExerciseVersion.objects.create(publication=version.publication, version=version)
    CourseMembership.objects.create(
        user=user, course=version.exercise.course, role=CourseMembership.Role.STUDENT
    )
    ActivePrompt.objects.create(public_id="default", prompt_version=prompt)
    return user, version, prompt


def create_submission(user, version, prompt, *, key="student-view"):
    return submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="Mi intento razonado",
        idempotency_key=key,
    )


def test_exercise_page_submits_answer_and_redirects_to_queued_status(client):
    user, version, _ = student_context()
    client.force_login(user)
    exercise_url = reverse(
        "courses:version",
        args=(version.exercise.course.slug, version.exercise.slug, version.version_number),
    )
    page = client.get(exercise_url)
    assert page.status_code == 200
    assert "Solicitar orientación" in page.content.decode()

    response = client.post(
        reverse("tutoring:submit", args=(version.id,)),
        {"student_answer": "Mi intento", "idempotency_key": str(uuid.uuid4())},
    )
    submission = TutoringSubmission.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("tutoring:submission", args=(submission.id,))
    queued = client.get(response.url)
    assert "Tu respuesta está en cola" in queued.content.decode()
    assert "volverá a intentarlo automáticamente" in queued.content.decode()
    assert "EventSource" not in queued.content.decode()


def test_status_polling_is_owner_only_and_reports_terminal_state(client):
    user, version, prompt = student_context()
    submission = create_submission(user, version, prompt)
    client.force_login(user)
    url = reverse("tutoring:status", args=(submission.id,))
    payload = client.get(url).json()
    assert payload == {
        "status": "accepted",
        "terminal": False,
        "url": reverse("tutoring:submission", args=(submission.id,)),
    }
    outsider = User.objects.create_user("polling-outsider")
    client.force_login(outsider)
    assert client.get(url).status_code == 404


def test_completed_page_feedback_is_linked_to_exact_response(client):
    user, version, prompt = student_context()
    submission = create_submission(user, version, prompt)
    tutoring_response = run_submission(submission.id, FakeTutoringModel(result()))
    client.force_login(user)
    page_url = reverse("tutoring:submission", args=(submission.id,))
    page = client.get(page_url)
    assert "Review the accumulator" in page.content.decode()
    assert "Valora esta respuesta" in page.content.decode()

    feedback_url = reverse("tutoring:feedback", args=(tutoring_response.id,))
    posted = client.post(feedback_url, {"helpful": "true", "comment": "Me ayudó"})
    assert posted.status_code == 302
    feedback = StudentFeedback.objects.get()
    assert feedback.response == tutoring_response
    assert feedback.helpful is True
    assert feedback.comment == "Me ayudó"

    outsider = User.objects.create_user("feedback-outsider")
    client.force_login(outsider)
    assert client.post(feedback_url, {"helpful": "false"}).status_code == 404


def test_failed_page_has_nontechnical_retry_message(client):
    user, version, prompt = student_context()
    submission = create_submission(user, version, prompt)
    submission.status = TutoringSubmission.Status.FAILED
    submission.save(update_fields=("status",))
    client.force_login(user)
    page = client.get(reverse("tutoring:submission", args=(submission.id,)))
    body = page.content.decode()
    assert "No pudimos generar la orientación" in body
    assert "intentarlo de nuevo más tarde" in body


def test_only_course_admin_can_view_and_requeue_failed_jobs(client):
    student, version, prompt = student_context()
    submission = create_submission(student, version, prompt)
    submission.status = TutoringSubmission.Status.FAILED
    submission.save(update_fields=("status",))
    course = version.exercise.course
    teacher = User.objects.create_user("teacher-phase3e")
    CourseMembership.objects.create(user=teacher, course=course, role="teacher")
    admin = User.objects.create_user("admin-phase3e")
    CourseMembership.objects.create(user=admin, course=course, role="course_admin")
    list_url = reverse("tutoring:failed-jobs", args=(course.slug,))

    client.force_login(teacher)
    assert client.get(list_url).status_code == 403
    client.force_login(admin)
    page = client.get(list_url)
    assert page.status_code == 200
    assert str(submission.id) in page.content.decode()
    requeue_url = reverse("tutoring:requeue-failed-job", args=(course.slug, submission.id))
    assert client.post(requeue_url).status_code == 302
    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.QUEUED
