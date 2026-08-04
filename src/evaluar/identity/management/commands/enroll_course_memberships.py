import csv
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from evaluar.courses.models import Course
from evaluar.identity.models import (
    AuditEvent,
    CourseMembership,
    PendingCourseEnrollment,
    User,
)


ROLE_RANK = {"student": 0, "teacher": 1, "course_admin": 2}
REQUIRED_COLUMNS = ("course_slug", "identity", "role", "status")


class Command(BaseCommand):
    help = "Validate and idempotently provision course-scoped memberships from CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-role-downgrade", action="store_true")

    def handle(self, *args, **options):
        rows, errors = self._load(Path(options["csv_path"]), options["allow_role_downgrade"])
        if errors:
            self.stdout.write(json.dumps({"status": "invalid", "errors": errors}, sort_keys=True))
            raise CommandError(f"Enrollment CSV contains {len(errors)} error(s); no rows applied.")
        if options["dry_run"]:
            self.stdout.write(
                json.dumps(
                    {"status": "dry_run", "valid_rows": len(rows), "changes": rows}, sort_keys=True
                )
            )
            return
        results = []
        with transaction.atomic():
            for row in rows:
                results.append(self._apply(row))
        self.stdout.write(json.dumps({"status": "applied", "results": results}, sort_keys=True))

    def _load(self, path, allow_downgrade):
        errors, rows = [], []
        try:
            handle = path.open(encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        with handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != REQUIRED_COLUMNS:
                return [], [{"row": 1, "error": f"header must be {','.join(REQUIRED_COLUMNS)}"}]
            seen = set()
            for number, raw in enumerate(reader, start=2):
                row = {key: (raw[key] or "").strip().lower() for key in REQUIRED_COLUMNS}
                row["row"] = number
                row_errors = []
                try:
                    validate_email(row["identity"])
                except ValidationError:
                    row_errors.append("identity must be a valid email address")
                if row["role"] not in ROLE_RANK:
                    row_errors.append("role must be student, teacher, or course_admin")
                if row["status"] not in dict(CourseMembership.Status.choices):
                    row_errors.append("status must be active, suspended, or inactive")
                course = Course.objects.filter(slug=row["course_slug"]).first()
                if not course:
                    row_errors.append("course_slug does not identify an existing course")
                key = (row["course_slug"], row["identity"])
                if key in seen:
                    row_errors.append("duplicate course_slug and identity in CSV")
                seen.add(key)
                users = User.objects.filter(email__iexact=row["identity"])
                if users.count() > 1:
                    row_errors.append("identity matches multiple existing users")
                user = users.first()
                current = (
                    CourseMembership.objects.filter(user=user, course=course).first()
                    if user and course
                    else PendingCourseEnrollment.objects.filter(
                        identity=row["identity"], course=course
                    ).first()
                    if course
                    else None
                )
                if (
                    current
                    and row["role"] in ROLE_RANK
                    and ROLE_RANK[row["role"]] < ROLE_RANK[current.role]
                    and not allow_downgrade
                ):
                    row_errors.append("role downgrade requires --allow-role-downgrade")
                if row_errors:
                    errors.append(
                        {"row": number, "identity": row["identity"], "errors": row_errors}
                    )
                else:
                    row.pop("row")
                    rows.append(row)
        if not rows and not errors:
            errors.append({"row": 2, "error": "CSV must contain at least one enrollment row"})
        return rows, errors

    def _apply(self, row):
        course = Course.objects.get(slug=row["course_slug"])
        user = User.objects.filter(email__iexact=row["identity"]).first()
        if user:
            membership = CourseMembership.objects.filter(user=user, course=course).first()
            if membership and (membership.role, membership.status) == (row["role"], row["status"]):
                action = "unchanged"
            elif membership:
                membership.role, membership.status = row["role"], row["status"]
                membership.save(update_fields=("role", "status", "updated_at"))
                action = "updated"
            else:
                membership = CourseMembership.objects.create(
                    user=user, course=course, role=row["role"], status=row["status"]
                )
                action = "created"
            PendingCourseEnrollment.objects.filter(course=course, identity=row["identity"]).delete()
            return {
                "course_slug": course.slug,
                "identity": row["identity"],
                "action": action,
                "membership_id": str(membership.id),
            }
        pending = PendingCourseEnrollment.objects.filter(
            course=course, identity=row["identity"]
        ).first()
        if pending and (pending.role, pending.status) == (row["role"], row["status"]):
            return {
                "course_slug": course.slug,
                "identity": row["identity"],
                "action": "unchanged",
                "pending_id": pending.id,
            }
        if pending:
            pending.role, pending.status = row["role"], row["status"]
            pending.save(update_fields=("role", "status", "updated_at"))
            created = False
        else:
            pending = PendingCourseEnrollment.objects.create(
                course=course,
                identity=row["identity"],
                role=row["role"],
                status=row["status"],
            )
            created = True
        AuditEvent.objects.create(
            course=course,
            event=AuditEvent.Event.ENROLLMENT_PENDING
            if created
            else AuditEvent.Event.ENROLLMENT_CHANGED,
            metadata={
                "identity": row["identity"],
                "role": row["role"],
                "status": row["status"],
                "source": "batch_enrollment",
            },
        )
        return {
            "course_slug": course.slug,
            "identity": row["identity"],
            "action": "pending_created" if created else "pending_updated",
            "pending_id": pending.id,
        }
