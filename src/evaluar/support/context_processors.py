from django.conf import settings

from evaluar.identity.models import CourseMembership


def support_navigation(request):
    if not settings.SUPPORT_ENABLED or not request.user.is_authenticated:
        return {"show_student_support_nav": False, "show_teacher_support_nav": False}
    memberships = CourseMembership.objects.filter(user=request.user, status="active")
    return {
        "show_student_support_nav": memberships.filter(role="student").exists(),
        "show_teacher_support_nav": memberships.filter(
            role__in=("teacher", "course_admin")
        ).exists(),
    }
