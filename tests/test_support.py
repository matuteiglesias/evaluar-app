from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from django.urls import reverse

from evaluar.courses.models import (
    ContentPublication, Course, Exercise, ExerciseVersion, PublishedExerciseVersion,
)
from evaluar.identity.models import CourseMembership, User
from evaluar.support.models import HumanHelpTicket, TicketAssignment
from evaluar.support.policies import visible_messages
from evaluar.support.services import (
    add_internal_note,
    add_student_message,
    add_teacher_message,
    admin_reassign_ticket,
    cancel_ticket,
    claim_ticket,
    create_ticket,
    resolve_ticket,
    release_ticket,
    resume_ticket,
    start_ticket,
    wait_for_student,
)
from evaluar.tutoring.models import (
    OutboxEvent, PromptVersion, TutoringAttempt, TutoringResponse, TutoringSubmission,
)


class SupportWorkflowTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(slug="math", name="Math")
        publication = ContentPublication.objects.create(
            course=self.course, source_commit="a", manifest_checksum="b", status="published"
        )
        exercise = Exercise.objects.create(course=self.course, slug="one", external_key="one")
        self.version = ExerciseVersion.objects.create(
            exercise=exercise, version_number=1, source_checksum="c", title="One",
            source_format="text", source_text="Question", rendered_html="Question",
            publication=publication,
        )
        PublishedExerciseVersion.objects.create(publication=publication, version=self.version)
        self.student = User.objects.create_user(username="student")
        self.teacher = User.objects.create_user(username="teacher")
        self.other_teacher = User.objects.create_user(username="other-teacher")
        self.course_admin = User.objects.create_user(username="course-admin")
        CourseMembership.objects.create(user=self.student, course=self.course, role="student")
        CourseMembership.objects.create(user=self.teacher, course=self.course, role="teacher")
        CourseMembership.objects.create(
            user=self.other_teacher, course=self.course, role="teacher"
        )
        CourseMembership.objects.create(
            user=self.course_admin, course=self.course, role="course_admin"
        )

    def create(self, key="request-1"):
        return create_ticket(student=self.student, course=self.course,
            exercise_version=self.version, question="Please help", idempotency_key=key)

    def test_idempotent_creation_and_transactional_event(self):
        ticket, created = self.create()
        repeated, repeated_created = self.create()
        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(ticket, repeated)
        self.assertEqual(ticket.events.get().event_type, "created")
        self.assertTrue(OutboxEvent.objects.filter(aggregate_id=ticket.id).exists())

    def test_claim_reply_and_resolution_are_audited(self):
        ticket, _ = self.create()
        claim_ticket(ticket=ticket, teacher=self.teacher)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HumanHelpTicket.Status.ASSIGNED)
        start_ticket(ticket=ticket, actor=self.teacher)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HumanHelpTicket.Status.IN_PROGRESS)
        assignment = ticket.assignments.get(status=TicketAssignment.Status.ACTIVE)
        self.assertIsNotNone(assignment.accepted_at)
        resolve_ticket(ticket=ticket, actor=self.teacher)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HumanHelpTicket.Status.RESOLVED)
        self.assertIsNotNone(ticket.resolved_at)
        self.assertEqual(
            list(ticket.events.values_list("event_type", flat=True)),
            ["created", "claimed", "started", "resolved"],
        )

    def test_internal_notes_are_never_in_student_query(self):
        ticket, _ = self.create()
        claim_ticket(ticket=ticket, teacher=self.teacher)
        add_internal_note(ticket=ticket, teacher=self.teacher, body="private")
        add_teacher_message(ticket=ticket, teacher=self.teacher, body="public")
        self.assertEqual(list(visible_messages(self.student, ticket).values_list("body", flat=True)),
                         ["public"])
        with self.assertRaises(PermissionDenied):
            add_internal_note(ticket=ticket, teacher=self.student, body="hidden")

    def test_only_documented_transitions_are_available(self):
        ticket, _ = self.create()
        claim_ticket(ticket=ticket, teacher=self.teacher)
        with self.assertRaises(ValidationError):
            resolve_ticket(ticket=ticket, actor=self.teacher)
        start_ticket(ticket=ticket, actor=self.teacher)
        wait_for_student(ticket=ticket, actor=self.teacher)
        add_student_message(ticket=ticket, student=self.student, body="More detail")
        resume_ticket(ticket=ticket, actor=self.student)
        resolve_ticket(ticket=ticket, actor=self.teacher)
        with self.assertRaises(ValidationError):
            resume_ticket(ticket=ticket, actor=self.teacher)

    def test_cancel_is_limited_to_open_or_assigned(self):
        open_ticket, _ = self.create("cancel-open")
        cancel_ticket(ticket=open_ticket, actor=self.student)
        assigned_ticket, _ = self.create("cancel-assigned")
        claim_ticket(ticket=assigned_ticket, teacher=self.teacher)
        cancel_ticket(ticket=assigned_ticket, actor=self.student)
        in_progress, _ = self.create("cancel-progress")
        claim_ticket(ticket=in_progress, teacher=self.teacher)
        start_ticket(ticket=in_progress, actor=self.teacher)
        with self.assertRaises(ValidationError):
            cancel_ticket(ticket=in_progress, actor=self.student)

    def test_release_and_admin_reassignment_preserve_history(self):
        released, _ = self.create("release")
        claim_ticket(ticket=released, teacher=self.teacher)
        release_ticket(ticket=released, actor=self.teacher)
        released.refresh_from_db()
        self.assertEqual(released.status, HumanHelpTicket.Status.OPEN)
        self.assertEqual(released.assignments.get().status, TicketAssignment.Status.RELEASED)

        reassigned, _ = self.create("reassign")
        claim_ticket(ticket=reassigned, teacher=self.teacher)
        admin_reassign_ticket(
            ticket=reassigned, teacher=self.other_teacher, admin_user=self.course_admin
        )
        self.assertEqual(reassigned.assignments.count(), 2)
        self.assertEqual(
            reassigned.assignments.get(status=TicketAssignment.Status.ACTIVE).teacher,
            self.other_teacher,
        )
        self.assertEqual(reassigned.events.last().event_type, "reassigned")

    def test_claim_has_exactly_one_winner(self):
        ticket, _ = self.create("claim-race")
        claim_ticket(ticket=ticket, teacher=self.teacher)
        with self.assertRaises(ValidationError):
            claim_ticket(ticket=ticket, teacher=self.other_teacher)
        self.assertEqual(ticket.assignments.filter(status="active").count(), 1)
        self.assertEqual(ticket.assignments.get(status="active").teacher, self.teacher)

    def test_teacher_dashboard_groups_course_work_without_inactivity_metrics(self):
        open_ticket, _ = self.create("dashboard-open")
        active_ticket, _ = self.create("dashboard-active")
        claim_ticket(ticket=active_ticket, teacher=self.teacher)
        waiting_ticket, _ = self.create("dashboard-waiting")
        claim_ticket(ticket=waiting_ticket, teacher=self.teacher)
        start_ticket(ticket=waiting_ticket, actor=self.teacher)
        wait_for_student(ticket=waiting_ticket, actor=self.teacher)
        resolved_ticket, _ = self.create("dashboard-resolved")
        claim_ticket(ticket=resolved_ticket, teacher=self.other_teacher)
        start_ticket(ticket=resolved_ticket, actor=self.other_teacher)
        resolve_ticket(ticket=resolved_ticket, actor=self.other_teacher)

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("support:teacher-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(open_ticket, response.context["open_tickets"])
        self.assertIn(active_ticket, response.context["my_active_tickets"])
        self.assertIn(waiting_ticket, response.context["waiting_tickets"])
        self.assertIn(resolved_ticket, response.context["recently_resolved"])
        self.assertNotContains(response, "rendimiento docente")

    def test_only_course_admin_can_cancel_for_a_student(self):
        ticket, _ = self.create("admin-cancel")
        claim_ticket(ticket=ticket, teacher=self.teacher)
        with self.assertRaises(PermissionDenied):
            cancel_ticket(ticket=ticket, actor=self.teacher)
        cancel_ticket(ticket=ticket, actor=self.course_admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HumanHelpTicket.Status.CANCELLED)

    def test_reference_identity_is_immutable(self):
        ticket, _ = self.create()
        other = Course.objects.create(slug="other", name="Other")
        ticket.course = other
        with self.assertRaises(ValidationError):
            ticket.save()

    def test_exercise_escalation_uses_stable_server_session_key(self):
        self.client.force_login(self.student)
        url = reverse("support:create", args=(self.version.id,))
        self.client.get(url)
        first_key = self.client.session[f"support:create:exercise:{self.version.id}"]
        self.client.get(url)
        self.assertEqual(
            self.client.session[f"support:create:exercise:{self.version.id}"], first_key
        )
        response = self.client.post(url, {
            "question": "Necesito ayuda con este ejercicio.",
            "priority": "normal",
            "idempotency_key": first_key,
        })
        self.assertEqual(response.status_code, 302)
        ticket = HumanHelpTicket.objects.get(student=self.student, idempotency_key=first_key)
        self.assertEqual(ticket.exercise_version, self.version)
        self.assertIsNone(ticket.tutoring_submission)
        self.client.post(url, {
            "question": "Este reintento no debe duplicar la solicitud.",
            "priority": "high", "idempotency_key": first_key,
        })
        self.assertEqual(
            HumanHelpTicket.objects.filter(student=self.student, idempotency_key=first_key).count(),
            1,
        )

    def test_failed_submission_escalation_is_owned_and_source_bound(self):
        prompt = PromptVersion.objects.create(
            public_id="support-test", version=1, system_instructions="test",
            checksum="prompt", status="published",
        )
        submission = TutoringSubmission.objects.create(
            user=self.student, exercise_version=self.version, prompt_version=prompt,
            student_answer="Mi intento", idempotency_key="tutoring-failed", status="failed",
        )
        self.client.force_login(self.student)
        url = reverse("support:create-from-submission", args=(submission.id,))
        self.assertEqual(self.client.get(url).status_code, 200)
        key = self.client.session[f"support:create:submission:{submission.id}"]
        response = self.client.post(url, {
            "question": "La tutoría falló y necesito ayuda.",
            "priority": "high",
            "idempotency_key": key,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            HumanHelpTicket.objects.get(idempotency_key=key).tutoring_submission,
            submission,
        )
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_my_requests_never_includes_another_students_ticket(self):
        other_student = User.objects.create_user(username="other-student")
        CourseMembership.objects.create(user=other_student, course=self.course, role="student")
        create_ticket(student=other_student, course=self.course, exercise_version=self.version,
                      question="Otra consulta", idempotency_key="other-ticket")
        own, _ = self.create("own-ticket")
        self.client.force_login(self.student)
        response = self.client.get(reverse("support:list"))
        self.assertEqual(list(response.context["tickets"]), [own])

    def test_completed_response_escalation_keeps_exact_response(self):
        prompt = PromptVersion.objects.create(
            public_id="response-test", version=1, system_instructions="test",
            checksum="response-prompt", status="published",
        )
        submission = TutoringSubmission.objects.create(
            user=self.student, exercise_version=self.version, prompt_version=prompt,
            student_answer="Mi intento", idempotency_key="tutoring-complete",
            status=TutoringSubmission.Status.SUCCEEDED,
        )
        attempt = TutoringAttempt.objects.create(
            submission=submission, number=1, status=TutoringAttempt.Status.PERSISTED,
            prompt_checksum=prompt.checksum, response_schema_version="1",
        )
        tutoring_response = TutoringResponse.objects.create(
            submission=submission, attempt=attempt, status=TutoringResponse.Status.PUBLISHED,
            structured_content={"summary": "Ayuda"}, rendered_html="<p>Ayuda</p>",
        )
        self.client.force_login(self.student)
        url = reverse("support:create-from-response", args=(tutoring_response.id,))
        self.assertEqual(self.client.get(url).status_code, 200)
        key = self.client.session[f"support:create:response:{tutoring_response.id}"]
        self.client.post(url, {
            "question": "Quiero consultar esta respuesta exacta.",
            "priority": "normal", "idempotency_key": key,
        })
        ticket = HumanHelpTicket.objects.get(idempotency_key=key)
        self.assertEqual(ticket.tutoring_submission, submission)
        self.assertEqual(ticket.tutoring_response, tutoring_response)
