from evaluar.identity.models import CourseMembership


def _membership(user, course):
    if not user.is_authenticated:
        return None
    return CourseMembership.objects.filter(
        user=user, course=course, status=CourseMembership.Status.ACTIVE
    ).first()


def can_create_ticket(user, course):
    membership = _membership(user, course)
    return membership is not None and membership.role == CourseMembership.Role.STUDENT


def can_view_ticket(user, ticket):
    membership = _membership(user, ticket.course)
    return membership is not None and (
        ticket.student_id == user.id
        or membership.role in {CourseMembership.Role.TEACHER, CourseMembership.Role.COURSE_ADMIN}
    )


def can_manage_ticket(user, ticket):
    membership = _membership(user, ticket.course)
    return membership is not None and membership.role in {
        CourseMembership.Role.TEACHER, CourseMembership.Role.COURSE_ADMIN
    }


def can_assign_ticket(user, ticket):
    return can_manage_ticket(user, ticket)


def can_administer_ticket(user, ticket):
    membership = _membership(user, ticket.course)
    return membership is not None and membership.role == CourseMembership.Role.COURSE_ADMIN


def visible_messages(user, ticket):
    messages = ticket.messages.all()
    return messages if can_manage_ticket(user, ticket) else messages.filter(visibility="participants")
