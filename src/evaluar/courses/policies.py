from evaluar.identity.models import CourseMembership
from .models import Course


def accessible_courses(user):
    if not user.is_authenticated:
        return Course.objects.none()
    return Course.objects.filter(
        memberships__user=user,
        memberships__status=CourseMembership.Status.ACTIVE,
        status=Course.Status.ACTIVE,
    ).distinct()


def _active_membership(user, course):
    if not user.is_authenticated:
        return None
    return CourseMembership.objects.filter(
        user=user, course=course, status=CourseMembership.Status.ACTIVE
    ).first()


def can_view_course(user, course):
    return _active_membership(user, course) is not None


def can_view_exercise(user, exercise_version):
    course = exercise_version.exercise.course
    return (
        can_view_course(user, course)
        and exercise_version.publication_links.filter(
            publication__course=course, publication__status="published"
        ).exists()
    )


def can_manage_course(user, course):
    membership = _active_membership(user, course)
    return membership is not None and membership.role in {
        CourseMembership.Role.TEACHER,
        CourseMembership.Role.COURSE_ADMIN,
    }


def is_course_admin(user, course):
    membership = _active_membership(user, course)
    return membership is not None and membership.role == CourseMembership.Role.COURSE_ADMIN
