import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PromptVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.SlugField(max_length=100)
    version = models.PositiveIntegerField()
    system_instructions = models.TextField()
    response_schema_version = models.CharField(max_length=32, default="1")
    model_policy = models.JSONField(default=dict)
    temperature = models.FloatField(default=0.2)
    max_output_tokens = models.PositiveIntegerField(default=1200)
    checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("public_id", "version"), name="unique_tutoring_prompt_version"
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Prompt versions are immutable; create a new version instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Prompt versions are immutable and cannot be deleted.")


class PromptDraft(models.Model):
    """Operator-authored prompt material awaiting immutable publication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.SlugField(max_length=100)
    version = models.PositiveIntegerField()
    system_instructions = models.TextField()
    response_schema_version = models.CharField(max_length=32, default="1")
    model_policy = models.JSONField(default=dict)
    temperature = models.FloatField(default=0.2)
    max_output_tokens = models.PositiveIntegerField(default=1200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("public_id", "version"), name="unique_tutoring_prompt_draft_version"
            )
        ]


class ActivePrompt(models.Model):
    """Mutable pointer used to promote or roll back immutable prompt versions."""

    public_id = models.SlugField(max_length=100, unique=True)
    prompt_version = models.ForeignKey(PromptVersion, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class TutoringSubmission(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tutoring_submissions"
    )
    exercise_version = models.ForeignKey(
        "courses.ExerciseVersion", on_delete=models.PROTECT, related_name="tutoring_submissions"
    )
    prompt_version = models.ForeignKey(
        PromptVersion, on_delete=models.PROTECT, related_name="submissions"
    )
    student_answer = models.TextField()
    response_language = models.CharField(max_length=16, default="es")
    idempotency_key = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACCEPTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "idempotency_key"), name="unique_user_submission_key"
            )
        ]


class TutoringAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        STARTED = "started", "Started"
        PROVIDER_SUCCEEDED = "provider_succeeded", "Provider succeeded"
        VALIDATION_FAILED = "validation_failed", "Validation failed"
        RETRYABLE_FAILED = "retryable_failed", "Retryable failure"
        TERMINAL_FAILED = "terminal_failed", "Terminal failure"
        PERSISTED = "persisted", "Persisted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        TutoringSubmission, on_delete=models.PROTECT, related_name="attempts"
    )
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    prompt_checksum = models.CharField(max_length=64)
    response_schema_version = models.CharField(max_length=32)
    framework_name = models.CharField(max_length=64, blank=True)
    framework_version = models.CharField(max_length=32, blank=True)
    provider = models.CharField(max_length=64, blank=True)
    requested_model = models.CharField(max_length=100, blank=True)
    served_model = models.CharField(max_length=100, blank=True)
    provider_request_id = models.CharField(max_length=255, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error_category = models.CharField(max_length=64, blank=True)
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("submission", "number"), name="unique_submission_attempt_number"
            ),
            models.UniqueConstraint(
                fields=("submission",),
                condition=models.Q(status__in=("created", "started", "provider_succeeded")),
                name="one_active_tutoring_attempt",
            ),
        ]


class TutoringResponse(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        VALIDATED = "validated", "Validated"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.OneToOneField(
        TutoringSubmission, on_delete=models.PROTECT, related_name="response"
    )
    attempt = models.OneToOneField(TutoringAttempt, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GENERATED)
    structured_content = models.JSONField()
    rendered_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)


class StudentFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        TutoringResponse, on_delete=models.PROTECT, related_name="feedback"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    helpful = models.BooleanField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("response", "user"), name="one_feedback_per_user_response"
            )
        ]


class TutoringQuotaUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    day = models.DateField()
    reserved_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course", "day"), name="unique_daily_tutoring_usage"
            )
        ]


class CourseTutoringQuotaUsage(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT)
    day = models.DateField()
    reserved_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("course", "day"), name="unique_daily_course_tutoring_usage"
            )
        ]


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHING = "dispatching", "Dispatching"
        DISPATCHED = "dispatched", "Dispatched"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=100)
    aggregate_id = models.UUIDField()
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatch_attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)


class TutoringOperationalAudit(models.Model):
    class Action(models.TextChoices):
        PROMPT_DRAFT_CREATED = "prompt_draft_created", "Prompt draft created"
        PROMPT_PUBLISHED = "prompt_published", "Prompt published"
        PROMPT_ACTIVATED = "prompt_activated", "Prompt activated"
        AMBIGUOUS_TERMINATED = "ambiguous_terminated", "Ambiguous attempt terminated"
        AMBIGUOUS_RETRY_AUTHORIZED = "ambiguous_retry_authorized", "Ambiguous retry authorized"
        PROVIDER_EVIDENCE_ATTACHED = "provider_evidence_attached", "Provider evidence attached"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=40, choices=Action.choices)
    actor_identifier = models.CharField(max_length=255)
    prompt_version = models.ForeignKey(
        PromptVersion, null=True, blank=True, on_delete=models.PROTECT
    )
    submission = models.ForeignKey(
        TutoringSubmission, null=True, blank=True, on_delete=models.PROTECT
    )
    attempt = models.ForeignKey(TutoringAttempt, null=True, blank=True, on_delete=models.PROTECT)
    note = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
