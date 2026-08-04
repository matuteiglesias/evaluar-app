from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from evaluar.courses.models import Course, ExerciseVersion
from evaluar.courses.policies import can_view_exercise, is_course_admin
from evaluar.support.policies import can_create_ticket

from .forms import AnswerSubmissionForm, ResponseFeedbackForm
from .models import ActivePrompt, TutoringAttempt, TutoringResponse, TutoringSubmission
from .services import (
    InvalidTransition,
    QuotaExceeded,
    requeue_submission,
    submit_answer,
    submit_feedback,
)


def _owned_submission(user, submission_id):
    return get_object_or_404(
        TutoringSubmission.objects.select_related(
            "exercise_version__exercise__course", "prompt_version"
        ),
        pk=submission_id,
        user=user,
    )


@login_required
@require_POST
def submit(request, version_id):
    version = get_object_or_404(
        ExerciseVersion.objects.select_related("exercise__course"), pk=version_id
    )
    if not can_view_exercise(request.user, version):
        raise PermissionDenied
    form = AnswerSubmissionForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "courses/exercise_version.html",
            {"course": version.exercise.course, "version": version, "answer_form": form},
            status=400,
        )
    active_prompt = (
        ActivePrompt.objects.select_related("prompt_version")
        .filter(public_id=settings.TUTORING_PROMPT_PUBLIC_ID)
        .first()
    )
    prompt = active_prompt.prompt_version if active_prompt else None
    if prompt is None:
        messages.error(request, "La tutoría no está disponible temporalmente.")
        return redirect(
            "courses:version",
            course_slug=version.exercise.course.slug,
            exercise_slug=version.exercise.slug,
            version_number=version.version_number,
        )
    try:
        created = submit_answer(
            user=request.user,
            exercise_version=version,
            prompt_version=prompt,
            student_answer=form.cleaned_data["student_answer"],
            idempotency_key=str(form.cleaned_data["idempotency_key"]),
        )
    except QuotaExceeded:
        messages.error(request, "Alcanzaste el límite diario de solicitudes de tutoría.")
        return redirect(
            "courses:version",
            course_slug=version.exercise.course.slug,
            exercise_slug=version.exercise.slug,
            version_number=version.version_number,
        )
    return redirect("tutoring:submission", submission_id=created.id)


@login_required
def submission(request, submission_id):
    job = _owned_submission(request.user, submission_id)
    response = getattr(job, "response", None)
    existing_feedback = None
    if response:
        existing_feedback = response.feedback.filter(user=request.user).first()
    return render(
        request,
        "tutoring/submission.html",
        {
            "submission": job,
            "response": response,
            "feedback": existing_feedback,
            "feedback_form": ResponseFeedbackForm(
                initial={"helpful": str(existing_feedback.helpful).lower()}
                if existing_feedback
                else None
            ),
            "can_request_help": can_create_ticket(
                request.user, job.exercise_version.exercise.course
            ),
        },
    )


@login_required
@require_GET
@never_cache
def status(request, submission_id):
    job = _owned_submission(request.user, submission_id)
    return JsonResponse(
        {
            "status": job.status,
            "terminal": job.status
            in (
                TutoringSubmission.Status.SUCCEEDED,
                TutoringSubmission.Status.FAILED,
                TutoringSubmission.Status.CANCELLED,
            ),
            "url": reverse("tutoring:submission", args=(job.id,)),
        }
    )


@login_required
@require_POST
def feedback(request, response_id):
    response = get_object_or_404(
        TutoringResponse.objects.select_related("submission"),
        pk=response_id,
        submission__user=request.user,
    )
    form = ResponseFeedbackForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa los datos de la valoración.")
    else:
        submit_feedback(user=request.user, response=response, **form.cleaned_data)
        messages.success(request, "Gracias por valorar esta respuesta.")
    return redirect("tutoring:submission", submission_id=response.submission_id)


@login_required
def failed_jobs(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    if not is_course_admin(request.user, course):
        raise PermissionDenied
    jobs = (
        TutoringSubmission.objects.filter(
            exercise_version__exercise__course=course,
            status=TutoringSubmission.Status.FAILED,
        )
        .select_related("user", "exercise_version")
        .prefetch_related(
            Prefetch(
                "attempts",
                queryset=TutoringAttempt.objects.order_by("-number"),
                to_attr="admin_attempts",
            )
        )
        .order_by("-updated_at")
    )
    return render(request, "tutoring/failed_jobs.html", {"course": course, "jobs": jobs})


@login_required
@require_POST
def requeue_failed_job(request, course_slug, submission_id):
    course = get_object_or_404(Course, slug=course_slug)
    if not is_course_admin(request.user, course):
        raise PermissionDenied
    job = get_object_or_404(
        TutoringSubmission,
        pk=submission_id,
        exercise_version__exercise__course=course,
    )
    try:
        requeue_submission(job.id)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "La solicitud se volvió a poner en cola.")
    return redirect("tutoring:failed-jobs", course_slug=course.slug)
