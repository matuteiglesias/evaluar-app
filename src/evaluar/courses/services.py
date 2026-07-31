from collections import defaultdict
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from content_pipeline.schema import Bundle
from .models import ContentPublication, Course, Exercise, ExerciseVersion, PublishedExerciseVersion


@transaction.atomic
def publish_bundle(bundle: Bundle) -> list[ContentPublication]:
    """Atomically publish every course in a checksum-verified, valid bundle."""
    if not bundle.valid:
        raise ValueError("A bundle with validation errors cannot be published.")
    grouped = defaultdict(list)
    for item in bundle.exercises:
        grouped[item.course_slug].append(item)
    course_metadata = {item["slug"]: item for item in bundle.courses}
    publications = []
    now = timezone.now()
    for course_slug in sorted(course_metadata):
        metadata = course_metadata[course_slug]
        course, _ = Course.objects.select_for_update().get_or_create(
            slug=course_slug, defaults={"name": metadata["name"]}
        )
        if course.name != metadata["name"]:
            course.name = metadata["name"]
            course.save(update_fields=["name"])
        publication, created = ContentPublication.objects.get_or_create(
            course=course,
            manifest_checksum=bundle.manifest_checksum,
            defaults={
                "source_commit": bundle.source_commit,
                "status": ContentPublication.Status.VALIDATING,
            },
        )
        if created:
            for item in grouped[course_slug]:
                exercise, _ = Exercise.objects.update_or_create(
                    course=course,
                    external_key=item.external_key,
                    defaults={"slug": item.slug},
                )
                version = exercise.versions.filter(source_checksum=item.source_checksum).first()
                if version is None:
                    number = (
                        exercise.versions.aggregate(value=Max("version_number"))["value"] or 0
                    ) + 1
                    version = ExerciseVersion.objects.create(
                        exercise=exercise,
                        version_number=number,
                        source_checksum=item.source_checksum,
                        title=item.title,
                        section=item.section,
                        source_format=item.source_format,
                        source_text=item.source_text,
                        rendered_html=item.rendered_html,
                        publication=publication,
                    )
                PublishedExerciseVersion.objects.create(publication=publication, version=version)
        ContentPublication.objects.filter(
            course=course, status=ContentPublication.Status.PUBLISHED
        ).exclude(pk=publication.pk).update(status=ContentPublication.Status.VALID)
        if publication.status != ContentPublication.Status.PUBLISHED:
            publication.status = ContentPublication.Status.PUBLISHED
            publication.published_at = now
            publication.save(update_fields=["status", "published_at"])
        publications.append(publication)
    return publications
