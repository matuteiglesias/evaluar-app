import uuid
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluar.courses.models import ExerciseVersion
from evaluar.identity.models import CourseMembership
from evaluar.tutoring.models import TutoringResponse, TutoringSubmission
from .forms import TicketCreateForm, TicketMessageForm
from .models import HumanHelpTicket
from .policies import (
    can_administer_ticket,
    can_create_ticket,
    can_manage_ticket,
    can_view_ticket,
    visible_messages,
)
from .services import (
    add_internal_note,
    add_student_message,
    add_teacher_message,
    cancel_ticket,
    claim_ticket,
    create_ticket,
    resolve_ticket,
    resume_ticket,
    start_ticket,
    wait_for_student,
)


@login_required
def ticket_list(request):
    active_student_courses = CourseMembership.objects.filter(
        user=request.user, status="active", role="student"
    ).values("course_id")
    tickets = HumanHelpTicket.objects.filter(
        student=request.user, course_id__in=active_student_courses
    ).select_related("course", "exercise_version")
    return render(request, "support/ticket_list.html", {"tickets": tickets})


@login_required
def teacher_dashboard(request):
    eligible_courses = CourseMembership.objects.filter(
        user=request.user, status="active", role__in=("teacher", "course_admin")
    ).values("course_id")
    if not eligible_courses.exists():
        raise PermissionDenied
    tickets = HumanHelpTicket.objects.filter(course_id__in=eligible_courses).select_related(
        "course", "student", "exercise_version"
    )
    my_assignment = {
        "assignments__teacher": request.user,
        "assignments__status": "active",
    }
    context = {
        "open_tickets": tickets.filter(status=HumanHelpTicket.Status.OPEN),
        "my_active_tickets": tickets.filter(
            status__in=(HumanHelpTicket.Status.ASSIGNED, HumanHelpTicket.Status.IN_PROGRESS),
            **my_assignment,
        ).distinct(),
        "waiting_tickets": tickets.filter(
            status=HumanHelpTicket.Status.WAITING_FOR_STUDENT, **my_assignment
        ).distinct(),
        "recently_resolved": tickets.filter(
            status=HumanHelpTicket.Status.RESOLVED,
            resolved_at__gte=timezone.now() - timedelta(days=30),
        ).order_by("-resolved_at"),
    }
    return render(request, "support/teacher_dashboard.html", context)


def _stable_idempotency_key(request, source_key):
    session_key = f"support:create:{source_key}"
    if session_key not in request.session:
        request.session[session_key] = str(uuid.uuid4())
    return session_key, request.session[session_key]


def _create_ticket(request, *, exercise, submission=None, response=None):
    course = exercise.exercise.course
    if not can_create_ticket(request.user, course):
        raise PermissionDenied
    source = f"response:{response.id}" if response else (
        f"submission:{submission.id}" if submission else f"exercise:{exercise.id}"
    )
    _, idempotency_key = _stable_idempotency_key(request, source)
    form = TicketCreateForm(request.POST or None, initial={"idempotency_key": idempotency_key})
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["idempotency_key"] != idempotency_key:
            raise PermissionDenied("La clave de la solicitud no es válida.")
        ticket, _ = create_ticket(student=request.user, course=course,
            exercise_version=exercise, question=form.cleaned_data["question"],
            idempotency_key=idempotency_key, priority=form.cleaned_data["priority"],
            tutoring_submission=submission, tutoring_response=response)
        return redirect("support:detail", ticket_id=ticket.id)
    return render(request, "support/ticket_create.html", {
        "form": form, "exercise": exercise, "submission": submission, "response": response,
    })


@login_required
def ticket_create(request, exercise_version_id):
    exercise = get_object_or_404(
        ExerciseVersion.objects.select_related("exercise__course"), pk=exercise_version_id
    )
    return _create_ticket(request, exercise=exercise)


@login_required
def ticket_create_from_submission(request, submission_id):
    submission = get_object_or_404(
        TutoringSubmission.objects.select_related("exercise_version__exercise__course"),
        pk=submission_id, user=request.user, status=TutoringSubmission.Status.FAILED,
    )
    return _create_ticket(request, exercise=submission.exercise_version, submission=submission)


@login_required
def ticket_create_from_response(request, response_id):
    response = get_object_or_404(
        TutoringResponse.objects.select_related("submission__exercise_version__exercise__course"),
        pk=response_id, submission__user=request.user,
        submission__status=TutoringSubmission.Status.SUCCEEDED,
        status=TutoringResponse.Status.PUBLISHED,
    )
    return _create_ticket(
        request, exercise=response.submission.exercise_version,
        submission=response.submission, response=response,
    )


def _ticket_for(user, ticket_id):
    ticket = get_object_or_404(HumanHelpTicket.objects.select_related(
        "course", "student", "exercise_version", "exercise_version__exercise",
        "tutoring_submission", "tutoring_response"), pk=ticket_id)
    if not can_view_ticket(user, ticket):
        raise Http404
    return ticket


@login_required
def ticket_detail(request, ticket_id):
    ticket = _ticket_for(request.user, ticket_id)
    staff = can_manage_ticket(request.user, ticket)
    form = TicketMessageForm(allow_internal=staff)
    return render(request, "support/ticket_detail.html", {
        "ticket": ticket, "ticket_messages": visible_messages(request.user, ticket),
        "form": form, "can_manage": staff,
        "can_administer": can_administer_ticket(request.user, ticket),
        "is_student_owner": request.user.id == ticket.student_id,
    })


@login_required
@require_POST
def message_create(request, ticket_id):
    ticket = _ticket_for(request.user, ticket_id)
    form = TicketMessageForm(request.POST, allow_internal=can_manage_ticket(request.user, ticket))
    if form.is_valid():
        body = form.cleaned_data["body"]
        if request.user.id == ticket.student_id:
            add_student_message(ticket=ticket, student=request.user, body=body)
        elif form.cleaned_data["visibility"] == "internal":
            add_internal_note(ticket=ticket, teacher=request.user, body=body)
        else:
            add_teacher_message(ticket=ticket, teacher=request.user, body=body)
    return redirect("support:detail", ticket_id=ticket.id)


@login_required
@require_POST
def claim(request, ticket_id):
    ticket = _ticket_for(request.user, ticket_id)
    claim_ticket(ticket=ticket, teacher=request.user)
    return redirect("support:detail", ticket_id=ticket.id)


@login_required
@require_POST
def action(request, ticket_id):
    ticket = _ticket_for(request.user, ticket_id)
    actions = {
        "start": start_ticket,
        "wait_for_student": wait_for_student,
        "resume": resume_ticket,
        "resolve": resolve_ticket,
        "cancel": cancel_ticket,
    }
    service = actions.get(request.POST.get("action"))
    if service is None:
        raise Http404
    service(ticket=ticket, actor=request.user)
    return redirect("support:detail", ticket_id=ticket.id)
