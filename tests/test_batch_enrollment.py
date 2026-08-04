import csv
import json
from io import StringIO

import pytest
from allauth.account.signals import user_logged_in
from django.core.management import CommandError, call_command

from evaluar.courses.models import Course
from evaluar.identity.models import AuditEvent, CourseMembership, PendingCourseEnrollment, User


pytestmark = pytest.mark.django_db


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("course_slug", "identity", "role", "status"))
        writer.writeheader()
        writer.writerows(rows)


def test_mixed_valid_invalid_csv_is_atomic(tmp_path):
    Course.objects.create(slug="one", name="One")
    path = tmp_path / "enroll.csv"
    write_csv(
        path,
        [
            {
                "course_slug": "one",
                "identity": "dev@example.com",
                "role": "student",
                "status": "active",
            },
            {"course_slug": "missing", "identity": "bad", "role": "owner", "status": "yes"},
        ],
    )
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("enroll_course_memberships", path, stdout=output)
    report = json.loads(output.getvalue())
    assert report["status"] == "invalid"
    assert report["errors"][0]["row"] == 3
    assert not PendingCourseEnrollment.objects.exists()


def test_dry_run_idempotency_pending_resolution_and_downgrade_guard(tmp_path, rf):
    course = Course.objects.create(slug="one", name="One")
    user = User.objects.create_user(username="dev", email="dev@example.com")
    path = tmp_path / "enroll.csv"
    rows = [
        {
            "course_slug": "one",
            "identity": "dev@example.com",
            "role": "teacher",
            "status": "active",
        },
        {
            "course_slug": "one",
            "identity": "future@example.com",
            "role": "student",
            "status": "active",
        },
    ]
    write_csv(path, rows)
    call_command("enroll_course_memberships", path, "--dry-run", stdout=StringIO())
    assert not CourseMembership.objects.exists()
    call_command("enroll_course_memberships", path, stdout=StringIO())
    call_command("enroll_course_memberships", path, stdout=StringIO())
    assert CourseMembership.objects.get(user=user, course=course).role == "teacher"
    assert PendingCourseEnrollment.objects.filter(identity="future@example.com").count() == 1
    assert AuditEvent.objects.filter(course=course).exists()

    rows[0]["role"] = "student"
    write_csv(path, rows)
    with pytest.raises(CommandError):
        call_command("enroll_course_memberships", path, stdout=StringIO())
    call_command("enroll_course_memberships", path, "--allow-role-downgrade", stdout=StringIO())
    assert CourseMembership.objects.get(user=user, course=course).role == "student"

    future = User.objects.create_user(username="future", email="future@example.com")
    user_logged_in.send(sender=User, request=rf.get("/"), user=future)
    assert CourseMembership.objects.filter(user=future, course=course, role="student").exists()
    assert not PendingCourseEnrollment.objects.filter(identity="future@example.com").exists()
