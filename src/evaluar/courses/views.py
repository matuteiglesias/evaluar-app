from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from .models import ContentPublication, Course, Exercise, ExerciseVersion
from .policies import accessible_courses, can_view_course, can_view_exercise, is_course_admin
from evaluar.tutoring.forms import AnswerSubmissionForm
from evaluar.support.policies import can_create_ticket


@login_required
def course_list(request):
    return render(
        request,
        "courses/course_list.html",
        {"courses": accessible_courses(request.user)},
    )


@login_required
def exercise_list(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug, status=Course.Status.ACTIVE)
    if not can_view_course(request.user, course):
        raise PermissionDenied
    publication = course.publications.filter(status=ContentPublication.Status.PUBLISHED).first()
    versions = ExerciseVersion.objects.filter(publication_links__publication=publication).order_by(
        "section", "title"
    )
    exercises = (
        Exercise.objects.filter(course=course, versions__in=versions)
        .prefetch_related(Prefetch("versions", queryset=versions, to_attr="published_versions"))
        .distinct()
        if publication
        else Exercise.objects.none()
    )
    return render(
        request,
        "courses/exercise_list.html",
        {
            "course": course,
            "exercises": exercises,
            "publication": publication,
            "is_course_admin": is_course_admin(request.user, course),
            "tutoring_enabled": settings.TUTORING_ENABLED,
        },
    )


@login_required
def exercise_version(request, course_slug, exercise_slug, version_number):
    version = get_object_or_404(
        ExerciseVersion.objects.select_related("exercise__course"),
        exercise__course__slug=course_slug,
        exercise__slug=exercise_slug,
        version_number=version_number,
    )
    if not can_view_exercise(request.user, version):
        raise PermissionDenied
    return render(
        request,
        "courses/exercise_version.html",
        {
            "course": version.exercise.course,
            "version": version,
            "answer_form": AnswerSubmissionForm.fresh(),
            "tutoring_enabled": settings.TUTORING_ENABLED,
            "can_request_help": settings.SUPPORT_ENABLED
            and can_create_ticket(request.user, version.exercise.course),
        },
    )
