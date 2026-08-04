import pytest

from evaluar.courses.models import ContentPublication, Course, Exercise, ExerciseVersion
from evaluar.identity.models import CourseMembership, User
from evaluar.support.models import HumanHelpTicket, TicketAssignment
from evaluar.support.policies import visible_messages
from evaluar.support.services import (
    add_student_message,
    add_teacher_message,
    claim_ticket,
    create_ticket,
    resolve_ticket,
    start_ticket,
)
from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.models import PromptVersion, StudentFeedback, TutoringSubmission
from evaluar.tutoring.ports import TutoringModelResult
from evaluar.tutoring.services import run_submission, submit_answer, submit_feedback


@pytest.mark.django_db
def test_network_free_whole_sprint_acceptance_journey():
    course = Course.objects.create(slug="acceptance", name="Acceptance")
    publication = ContentPublication.objects.create(
        course=course,
        source_commit="acceptance",
        manifest_checksum="a" * 64,
        status="published",
    )
    exercise = Exercise.objects.create(course=course, slug="one", external_key="acceptance:one")
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="b" * 64,
        title="One",
        source_format="text",
        source_text="Question",
        rendered_html="<p>Question</p>",
        publication=publication,
    )
    prompt = PromptVersion.objects.create(
        public_id="acceptance",
        version=1,
        system_instructions="Guide the student.",
        checksum="c" * 64,
        status="published",
    )
    student = User.objects.create_user(username="acceptance-student")
    teacher = User.objects.create_user(username="acceptance-teacher")
    CourseMembership.objects.create(user=student, course=course, role="student")
    CourseMembership.objects.create(user=teacher, course=course, role="teacher")

    submission = submit_answer(
        user=student,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="My answer",
        idempotency_key="acceptance-answer",
    )
    model = FakeTutoringModel(
        TutoringModelResult(
            summary="Review the first step.",
            diagnosis=("A step needs justification.",),
            next_steps=("Explain the transformation.",),
            hints=("Check both sides.",),
            confidence="high",
            provider="fake",
            requested_model="fake-1",
            served_model="fake-1",
            provider_request_id="acceptance-request",
            input_tokens=10,
            output_tokens=20,
            latency_ms=1,
        )
    )
    tutoring_response = run_submission(submission.id, model)
    submission.refresh_from_db()
    assert submission.status == TutoringSubmission.Status.SUCCEEDED
    feedback = submit_feedback(
        user=student,
        response=tutoring_response,
        helpful=True,
        comment="Helpful but I still need a person.",
    )
    assert StudentFeedback.objects.get(pk=feedback.pk).response == tutoring_response

    ticket, _ = create_ticket(
        student=student,
        course=course,
        exercise_version=version,
        tutoring_submission=submission,
        tutoring_response=tutoring_response,
        question="Can you review this exact guidance?",
        idempotency_key="acceptance-help",
    )
    claim_ticket(ticket=ticket, teacher=teacher)
    start_ticket(ticket=ticket, actor=teacher)
    teacher_message = add_teacher_message(
        ticket=ticket, teacher=teacher, body="Please explain your second step."
    )
    assert teacher_message in visible_messages(student, ticket)
    add_student_message(ticket=ticket, student=student, body="Here is my explanation.")
    resolve_ticket(ticket=ticket, actor=teacher)

    ticket.refresh_from_db()
    assert ticket.status == HumanHelpTicket.Status.RESOLVED
    assert ticket.tutoring_response == tutoring_response
    assert list(ticket.events.values_list("event_type", flat=True)) == [
        "created",
        "claimed",
        "started",
        "teacher_message_added",
        "student_message_added",
        "resolved",
        "assignment_released",
    ]
    assignment = ticket.assignments.get()
    assert assignment.status == TicketAssignment.Status.RELEASED
    assert assignment.accepted_at is not None
