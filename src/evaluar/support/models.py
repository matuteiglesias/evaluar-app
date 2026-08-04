import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class HumanHelpTicket(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        URGENT = "urgent", "Urgente"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        ASSIGNED = "assigned", "Asignada"
        IN_PROGRESS = "in_progress", "En curso"
        WAITING_FOR_STUDENT = "waiting_for_student", "Esperando al estudiante"
        RESOLVED = "resolved", "Resuelta"
        CANCELLED = "cancelled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.PROTECT, related_name="help_tickets"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="help_tickets"
    )
    exercise_version = models.ForeignKey(
        "courses.ExerciseVersion", on_delete=models.PROTECT, related_name="help_tickets"
    )
    tutoring_submission = models.ForeignKey(
        "tutoring.TutoringSubmission",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="help_tickets",
    )
    tutoring_response = models.ForeignKey(
        "tutoring.TutoringResponse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="help_tickets",
    )
    question = models.TextField()
    idempotency_key = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("student", "idempotency_key"), name="unique_student_help_ticket_key"
            )
        ]
        ordering = ("-created_at",)

    def clean(self):
        errors = {}
        if self.exercise_version_id and self.course_id:
            if self.exercise_version.exercise.course_id != self.course_id:
                errors["exercise_version"] = "Exercise version must belong to the ticket course."
        if self.tutoring_submission_id:
            submission = self.tutoring_submission
            if submission.user_id != self.student_id:
                errors["tutoring_submission"] = "Submission must belong to the student."
            if submission.exercise_version_id != self.exercise_version_id:
                errors["tutoring_submission"] = "Submission must refer to the exercise version."
            if submission.exercise_version.exercise.course_id != self.course_id:
                errors["tutoring_submission"] = "Submission must belong to the ticket course."
        if self.tutoring_response_id:
            response = self.tutoring_response
            if response.submission.user_id != self.student_id:
                errors["tutoring_response"] = "Response must belong to the student."
            if response.submission.exercise_version_id != self.exercise_version_id:
                errors["tutoring_response"] = "Response must refer to the exercise version."
            if response.submission.exercise_version.exercise.course_id != self.course_id:
                errors["tutoring_response"] = "Response must belong to the ticket course."
            if (
                self.tutoring_submission_id
                and response.submission_id != self.tutoring_submission_id
            ):
                errors["tutoring_response"] = "Response must belong to the referenced submission."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding:
            # Creation cannot bypass the workflow's mandatory initial state.
            self.status = self.Status.OPEN
            self.resolved_at = None
        if self.pk:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "course_id",
                    "student_id",
                    "exercise_version_id",
                    "tutoring_submission_id",
                    "tutoring_response_id",
                    "idempotency_key",
                )
                .first()
            )
            if original and any(original[field] != getattr(self, field) for field in original):
                raise ValidationError("Ticket identity and tutoring references are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)


class TicketAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        RELEASED = "released", "Liberada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        HumanHelpTicket, on_delete=models.PROTECT, related_name="assignments"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_assignments"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_assignments_created",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("ticket",),
                condition=models.Q(status="active"),
                name="one_active_ticket_assignment",
            )
        ]
        ordering = ("-assigned_at",)


class TicketMessage(models.Model):
    class Visibility(models.TextChoices):
        PARTICIPANTS = "participants", "Participantes"
        INTERNAL = "internal", "Interna"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(HumanHelpTicket, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PARTICIPANTS
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class TicketEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(HumanHelpTicket, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=50)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Ticket events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ticket events are append-only.")
