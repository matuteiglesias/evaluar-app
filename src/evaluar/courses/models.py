import uuid
from django.core.exceptions import ValidationError
from django.db import models


class Course(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return self.name


class ContentPublication(models.Model):
    class Status(models.TextChoices):
        VALIDATING = "validating", "Validating"
        VALID = "valid", "Valid"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="publications")
    source_commit = models.CharField(max_length=64)
    manifest_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VALIDATING)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("course",),
                condition=models.Q(status="published"),
                name="one_published_release_per_course",
            ),
            models.UniqueConstraint(
                fields=("course", "manifest_checksum"), name="idempotent_course_publication"
            ),
        ]
        ordering = ("-created_at",)


class Exercise(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="exercises")
    slug = models.SlugField(max_length=100)
    external_key = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("course", "slug"), name="unique_course_exercise_slug"),
            models.UniqueConstraint(
                fields=("course", "external_key"), name="unique_course_external_key"
            ),
        ]
        ordering = ("slug",)


class ExerciseVersion(models.Model):
    class SourceFormat(models.TextChoices):
        LATEX = "latex", "LaTeX"
        MARKDOWN = "markdown", "Markdown"
        TEXT = "text", "Plain text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    source_checksum = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    section = models.CharField(max_length=255, blank=True)
    source_format = models.CharField(max_length=20, choices=SourceFormat.choices)
    source_text = models.TextField()
    rendered_html = models.TextField()
    publication = models.ForeignKey(
        ContentPublication, on_delete=models.PROTECT, related_name="created_versions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("exercise", "version_number"), name="unique_exercise_version"
            ),
            models.UniqueConstraint(
                fields=("exercise", "source_checksum"), name="unique_exercise_checksum"
            ),
        ]
        ordering = ("section", "title", "version_number")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Exercise versions are immutable; create a new version instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Exercise versions are immutable and cannot be deleted.")


class PublishedExerciseVersion(models.Model):
    """Maps a complete release to versions, allowing unchanged snapshots to be reused."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey(
        ContentPublication, on_delete=models.CASCADE, related_name="included_versions"
    )
    version = models.ForeignKey(
        ExerciseVersion, on_delete=models.PROTECT, related_name="publication_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("publication", "version"), name="unique_publication_version"
            ),
        ]
