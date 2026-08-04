import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Local identity; the provider subject, not email, is the immutable external key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)


class CourseMembership(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"
        COURSE_ADMIN = "course_admin", "Course administrator"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_memberships")
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "course"), name="unique_user_course_membership")
        ]
        ordering = ("course_id", "user_id")


class PendingCourseEnrollment(models.Model):
    """A course-scoped grant waiting for a real identity to sign in."""

    identity = models.EmailField()
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="pending_enrollments"
    )
    role = models.CharField(max_length=20, choices=CourseMembership.Role.choices)
    status = models.CharField(max_length=20, choices=CourseMembership.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("course", "identity"), name="unique_pending_course_identity"
            )
        ]


class AuditEvent(models.Model):
    class Event(models.TextChoices):
        SIGN_IN = "sign_in", "Sign in"
        MEMBERSHIP_CREATED = "membership_created", "Membership created"
        MEMBERSHIP_CHANGED = "membership_changed", "Membership changed"
        MEMBERSHIP_DELETED = "membership_deleted", "Membership deleted"
        ENROLLMENT_PENDING = "enrollment_pending", "Enrollment pending"
        ENROLLMENT_CHANGED = "enrollment_changed", "Enrollment changed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events"
    )
    event = models.CharField(max_length=32, choices=Event.choices)
    subject_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="subject_audit_events"
    )
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
