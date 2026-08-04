from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from evaluar.identity.models import CourseMembership
from evaluar.tutoring.models import OutboxEvent

from .models import HumanHelpTicket, TicketAssignment, TicketEvent, TicketMessage
from .policies import can_create_ticket, can_manage_ticket, can_view_ticket


VALID_TRANSITIONS = {
    HumanHelpTicket.Status.OPEN: {
        HumanHelpTicket.Status.ASSIGNED,
        HumanHelpTicket.Status.CANCELLED,
    },
    HumanHelpTicket.Status.ASSIGNED: {
        HumanHelpTicket.Status.IN_PROGRESS,
        HumanHelpTicket.Status.OPEN,
        HumanHelpTicket.Status.CANCELLED,
    },
    HumanHelpTicket.Status.IN_PROGRESS: {
        HumanHelpTicket.Status.WAITING_FOR_STUDENT,
        HumanHelpTicket.Status.RESOLVED,
    },
    HumanHelpTicket.Status.WAITING_FOR_STUDENT: {HumanHelpTicket.Status.IN_PROGRESS},
    HumanHelpTicket.Status.RESOLVED: set(),
    HumanHelpTicket.Status.CANCELLED: set(),
}


def _require_support_enabled():
    if not settings.SUPPORT_ENABLED:
        raise PermissionDenied("Support tickets are disabled.")


def _event(ticket, event_type, actor, from_status="", to_status="", metadata=None):
    _require_support_enabled()
    event = TicketEvent.objects.create(
        ticket=ticket,
        event_type=event_type,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        metadata=metadata or {},
    )
    OutboxEvent.objects.create(
        topic=f"support.ticket.{event_type}",
        aggregate_id=ticket.id,
        payload={
            "ticket_id": str(ticket.id),
            "event_id": str(event.id),
            "course_id": str(ticket.course_id),
            "event_type": event_type,
        },
    )
    return event


def _active_assignment(ticket):
    return (
        ticket.assignments.select_for_update().filter(status=TicketAssignment.Status.ACTIVE).first()
    )


def _is_course_admin(user, ticket):
    return CourseMembership.objects.filter(
        user=user,
        course=ticket.course,
        status=CourseMembership.Status.ACTIVE,
        role=CourseMembership.Role.COURSE_ADMIN,
    ).exists()


def _authorized_teacher(user, course):
    return CourseMembership.objects.filter(
        user=user,
        course=course,
        status=CourseMembership.Status.ACTIVE,
        role__in=(CourseMembership.Role.TEACHER, CourseMembership.Role.COURSE_ADMIN),
    ).exists()


def _require_assignee_or_admin(actor, ticket):
    assignment = _active_assignment(ticket)
    if not can_manage_ticket(actor, ticket) or (
        not _is_course_admin(actor, ticket)
        and (assignment is None or assignment.teacher_id != actor.id)
    ):
        raise PermissionDenied("Only the active assignee or a course administrator may do this.")
    return assignment


def _transition(ticket, actor, to_status, event_type, metadata=None):
    _require_support_enabled()
    old_status = ticket.status
    if to_status not in VALID_TRANSITIONS[old_status]:
        raise ValidationError(f"Invalid transition from {old_status} to {to_status}.")
    ticket.status = to_status
    ticket.resolved_at = timezone.now() if to_status == HumanHelpTicket.Status.RESOLVED else None
    ticket.save(update_fields=("status", "resolved_at", "updated_at"))
    _event(ticket, event_type, actor, old_status, to_status, metadata)
    return ticket


@transaction.atomic
def create_ticket(
    *,
    student,
    course,
    exercise_version,
    question,
    idempotency_key,
    tutoring_submission=None,
    tutoring_response=None,
    priority=HumanHelpTicket.Priority.NORMAL,
):
    _require_support_enabled()
    if not can_create_ticket(student, course):
        raise PermissionDenied("An active student membership is required.")
    existing = HumanHelpTicket.objects.filter(
        student=student, idempotency_key=idempotency_key
    ).first()
    if existing:
        return existing, False
    ticket = HumanHelpTicket(
        course=course,
        student=student,
        exercise_version=exercise_version,
        tutoring_submission=tutoring_submission,
        tutoring_response=tutoring_response,
        question=question,
        idempotency_key=idempotency_key,
        priority=priority,
    )
    ticket.save(force_insert=True)
    _event(ticket, "created", student, to_status=ticket.status)
    return ticket, True


@transaction.atomic
def claim_ticket(*, ticket, teacher):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    if not _authorized_teacher(teacher, ticket.course):
        raise PermissionDenied("An authorized course teacher is required.")
    if ticket.status != HumanHelpTicket.Status.OPEN:
        raise ValidationError("Only an open ticket may be claimed.")
    if _active_assignment(ticket):
        raise ValidationError("Ticket already has an active assignment.")
    assignment = TicketAssignment.objects.create(
        ticket=ticket, teacher=teacher, assigned_by=teacher
    )
    _transition(
        ticket,
        teacher,
        HumanHelpTicket.Status.ASSIGNED,
        "claimed",
        {"assignment_id": str(assignment.id), "teacher_id": str(teacher.id)},
    )
    return ticket


@transaction.atomic
def release_ticket(*, ticket, actor):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    assignment = _require_assignee_or_admin(actor, ticket)
    if ticket.status != HumanHelpTicket.Status.ASSIGNED or assignment is None:
        raise ValidationError("Only an assigned ticket may be released.")
    assignment.status = TicketAssignment.Status.RELEASED
    assignment.released_at = timezone.now()
    assignment.save(update_fields=("status", "released_at"))
    return _transition(
        ticket,
        actor,
        HumanHelpTicket.Status.OPEN,
        "released",
        {"assignment_id": str(assignment.id), "teacher_id": str(assignment.teacher_id)},
    )


@transaction.atomic
def start_ticket(*, ticket, actor):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    assignment = _require_assignee_or_admin(actor, ticket)
    if assignment is None:
        raise ValidationError("Ticket has no active assignment.")
    assignment.accepted_at = assignment.accepted_at or timezone.now()
    assignment.save(update_fields=("accepted_at",))
    return _transition(ticket, actor, HumanHelpTicket.Status.IN_PROGRESS, "started")


def _add_message(ticket, author, body, visibility, event_type):
    message = TicketMessage.objects.create(
        ticket=ticket, author=author, body=body, visibility=visibility
    )
    _event(
        ticket,
        event_type,
        author,
        ticket.status,
        ticket.status,
        {"message_id": str(message.id), "visibility": visibility},
    )
    return message


@transaction.atomic
def add_student_message(*, ticket, student, body):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.student_id != student.id or not can_view_ticket(student, ticket):
        raise PermissionDenied
    return _add_message(
        ticket, student, body, TicketMessage.Visibility.PARTICIPANTS, "student_message_added"
    )


@transaction.atomic
def add_teacher_message(*, ticket, teacher, body):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    _require_assignee_or_admin(teacher, ticket)
    return _add_message(
        ticket, teacher, body, TicketMessage.Visibility.PARTICIPANTS, "teacher_message_added"
    )


@transaction.atomic
def add_internal_note(*, ticket, teacher, body):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    _require_assignee_or_admin(teacher, ticket)
    return _add_message(
        ticket, teacher, body, TicketMessage.Visibility.INTERNAL, "internal_note_added"
    )


@transaction.atomic
def wait_for_student(*, ticket, actor):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    _require_assignee_or_admin(actor, ticket)
    return _transition(
        ticket, actor, HumanHelpTicket.Status.WAITING_FOR_STUDENT, "waiting_for_student"
    )


@transaction.atomic
def resume_ticket(*, ticket, actor):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status != HumanHelpTicket.Status.WAITING_FOR_STUDENT:
        raise ValidationError("Only a ticket waiting for the student may be resumed.")
    if actor.id == ticket.student_id:
        if not can_view_ticket(actor, ticket):
            raise PermissionDenied
    else:
        _require_assignee_or_admin(actor, ticket)
    return _transition(ticket, actor, HumanHelpTicket.Status.IN_PROGRESS, "resumed")


@transaction.atomic
def resolve_ticket(*, ticket, actor, metadata=None):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    assignment = _require_assignee_or_admin(actor, ticket)
    result = _transition(ticket, actor, HumanHelpTicket.Status.RESOLVED, "resolved", metadata)
    if assignment:
        assignment.status = TicketAssignment.Status.RELEASED
        assignment.released_at = timezone.now()
        assignment.save(update_fields=("status", "released_at"))
        _event(
            ticket,
            "assignment_released",
            actor,
            result.status,
            result.status,
            {"assignment_id": str(assignment.id), "reason": "ticket_resolved"},
        )
    return result


@transaction.atomic
def cancel_ticket(*, ticket, actor):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    if actor.id != ticket.student_id and not _is_course_admin(actor, ticket):
        raise PermissionDenied
    if not can_view_ticket(actor, ticket):
        raise PermissionDenied
    assignment = _active_assignment(ticket)
    result = _transition(ticket, actor, HumanHelpTicket.Status.CANCELLED, "cancelled")
    if assignment:
        assignment.status = TicketAssignment.Status.RELEASED
        assignment.released_at = timezone.now()
        assignment.save(update_fields=("status", "released_at"))
        _event(
            ticket,
            "assignment_released",
            actor,
            result.status,
            result.status,
            {"assignment_id": str(assignment.id)},
        )
    return result


@transaction.atomic
def admin_reassign_ticket(*, ticket, teacher, admin_user):
    ticket = HumanHelpTicket.objects.select_for_update().get(pk=ticket.pk)
    if not _is_course_admin(admin_user, ticket) or not _authorized_teacher(teacher, ticket.course):
        raise PermissionDenied("A course administrator and authorized teacher are required.")
    if ticket.status != HumanHelpTicket.Status.ASSIGNED:
        raise ValidationError("Only assigned tickets may be reassigned.")
    previous = _active_assignment(ticket)
    if previous is None:
        raise ValidationError("Ticket has no active assignment.")
    if previous.teacher_id == teacher.id:
        return ticket
    previous.status = TicketAssignment.Status.RELEASED
    previous.released_at = timezone.now()
    previous.save(update_fields=("status", "released_at"))
    assignment = TicketAssignment.objects.create(
        ticket=ticket, teacher=teacher, assigned_by=admin_user
    )
    _event(
        ticket,
        "reassigned",
        admin_user,
        ticket.status,
        ticket.status,
        {
            "from_assignment_id": str(previous.id),
            "to_assignment_id": str(assignment.id),
            "teacher_id": str(teacher.id),
        },
    )
    return ticket
