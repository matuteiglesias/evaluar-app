import csv
import json
import uuid
from pathlib import Path
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from courses.models import (
    ContentPublication,
    Course,
    Exercise,
    ExerciseVersion,
    PublishedExerciseVersion,
)
from courses.policies import can_manage_course
from identity.models import AuditEvent, CourseMembership, User

pytestmark = pytest.mark.django_db


def published_exercise():
    course = Course.objects.create(slug="tda", name="TDA")
    publication = ContentPublication.objects.create(
        course=course, source_commit="abc", manifest_checksum="a" * 64, status="published"
    )
    exercise = Exercise.objects.create(
        course=course, slug="suma-subconjuntos", external_key="tda:101"
    )
    version = ExerciseVersion.objects.create(
        exercise=exercise,
        version_number=1,
        source_checksum="b" * 64,
        title="Suma",
        section="1",
        source_format="latex",
        source_text="x",
        rendered_html="<p>x</p>",
        publication=publication,
    )
    PublishedExerciseVersion.objects.create(publication=publication, version=version)
    return course, exercise, version


def test_anonymous_is_redirected(client):
    response = client.get(reverse("courses:list"))
    assert response.status_code == 302


def test_authenticated_non_member_is_denied(client):
    course, exercise, version = published_exercise()
    client.force_login(User.objects.create_user("outsider"))
    assert client.get(reverse("courses:exercises", args=[course.slug])).status_code == 403
    assert (
        client.get(
            reverse("courses:version", args=[course.slug, exercise.slug, version.version_number])
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", ["student", "teacher", "course_admin"])
def test_active_course_roles_can_browse(client, role):
    course, exercise, version = published_exercise()
    user = User.objects.create_user(role)
    CourseMembership.objects.create(user=user, course=course, role=role)
    client.force_login(user)
    assert client.get(reverse("courses:exercises", args=[course.slug])).status_code == 200
    response = client.get(
        reverse("courses:version", args=[course.slug, exercise.slug, version.version_number])
    )
    assert response.status_code == 200
    assert b"<p>x</p>" in response.content


def test_suspended_member_is_denied_and_change_is_audited(client):
    course, exercise, version = published_exercise()
    user = User.objects.create_user("suspended")
    membership = CourseMembership.objects.create(
        user=user, course=course, role="student", status="suspended"
    )
    client.force_login(user)
    assert client.get(reverse("courses:exercises", args=[course.slug])).status_code == 403
    assert AuditEvent.objects.filter(
        subject_user=user, course=course, event="membership_created"
    ).exists()
    membership.role = "teacher"
    membership.save()
    assert AuditEvent.objects.filter(subject_user=user, event="membership_changed").exists()


def test_only_teacher_and_course_admin_can_manage():
    course, _, _ = published_exercise()
    for role, expected in (("student", False), ("teacher", True), ("course_admin", True)):
        user = User.objects.create_user(role)
        CourseMembership.objects.create(user=user, course=course, role=role)
        assert can_manage_course(user, course) is expected


def write_source(root: Path):
    directory = root / "exercises" / "tda"
    directory.mkdir(parents=True)
    with (directory / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "section", "file", "name"))
        writer.writeheader()
        writer.writerow(
            {"id": "101", "section": "1", "file": "101.tex", "name": "Suma subconjuntos"}
        )
    (directory / "101.tex").write_text("Solve $x$", encoding="utf-8")


def test_build_publish_is_checksum_verified_uuid_backed_and_idempotent(tmp_path):
    write_source(tmp_path)
    output = tmp_path / "build"
    call_command("build_content_bundle", str(tmp_path), output=str(output), source_commit="abc")
    call_command("publish_content", str(output))
    call_command("publish_content", str(output))
    exercise = Exercise.objects.get()
    assert isinstance(exercise.pk, uuid.UUID)
    assert exercise.external_key == "tda:101"
    assert exercise.slug == "suma-subconjuntos"
    assert ContentPublication.objects.count() == 1
    assert ExerciseVersion.objects.count() == 1

    path = output / "bundle.json"
    payload = json.loads(path.read_text())
    payload["source_commit"] = "tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(CommandError, match="checksum"):
        call_command("publish_content", str(output))


def test_health_endpoints(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
