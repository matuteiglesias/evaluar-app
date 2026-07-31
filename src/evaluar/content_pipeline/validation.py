"""Cross-document validation rules."""

from collections import Counter
from .schema import ExerciseSource, ValidationIssue


def validate(
    courses: list[dict[str, str]], exercises: list[ExerciseSource]
) -> list[ValidationIssue]:
    issues = []
    course_counts = Counter(course["slug"] for course in courses)
    scoped_counts = Counter(item.external_key for item in exercises)
    slug_counts = Counter((item.course_slug, item.slug) for item in exercises)
    for slug, count in sorted(course_counts.items()):
        if count > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_course_slug",
                    f"exercises/{slug}",
                    f"course slug occurs {count} times",
                )
            )
    for external_key, count in sorted(scoped_counts.items()):
        if external_key.endswith(":"):
            issues.append(
                ValidationIssue("schema_invalid", external_key, "exercise ID is required")
            )
        elif count > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_exercise_id",
                    external_key,
                    f"course-scoped exercise ID occurs {count} times",
                )
            )
    for (course, slug), count in sorted(slug_counts.items()):
        if count > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_exercise_slug",
                    f"{course}:{slug}",
                    f"exercise slug occurs {count} times in course",
                )
            )
    return issues
