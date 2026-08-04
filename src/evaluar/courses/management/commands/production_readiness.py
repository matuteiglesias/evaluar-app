import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from pydantic import ValidationError

from evaluar.courses.models import ContentPublication, Course
from evaluar.tutoring.infrastructure.client_factory import ModelPolicy
from evaluar.tutoring.models import ActivePrompt, OutboxEvent, TutoringAttempt


class Command(BaseCommand):
    help = "Report production database, schema, content, tutoring, queue, and support readiness."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        checks: list[dict[str, object]] = []

        def add(name, status, detail, **data):
            checks.append({"name": name, "status": status, "detail": detail, **data})

        try:
            connection.ensure_connection()
            add("database", "healthy", "Database connection succeeded.")
            executor = MigrationExecutor(connection)
            pending = [
                f"{migration.app_label}.{migration.name}"
                for migration, _backwards in executor.migration_plan(
                    executor.loader.graph.leaf_nodes()
                )
            ]
            add(
                "schema",
                "error" if pending else "healthy",
                "Unapplied migrations exist."
                if pending
                else "All required migrations are applied.",
                unapplied=pending,
            )
        except Exception as exc:
            add("database", "error", f"Database check failed: {type(exc).__name__}.")
            pending = []

        database_error = any(c["name"] == "database" and c["status"] == "error" for c in checks)
        if database_error or pending:
            reason = "a ready database schema" if pending else "the database"
            add("content", "error", f"Content state cannot be inspected without {reason}.")
            add("tutoring", "error", f"Tutoring state cannot be inspected without {reason}.")
        else:
            publications = ContentPublication.objects.filter(
                status="published", course__status=Course.Status.ACTIVE
            ).count()
            content_status = (
                "healthy"
                if publications
                else ("error" if settings.REQUIRE_PUBLISHED_COURSE else "warning")
            )
            add("content", content_status, f"{publications} published course release(s).")
            self._tutoring_checks(add)

        add(
            "support",
            "healthy" if settings.SUPPORT_ENABLED else "disabled",
            "Support tickets are enabled."
            if settings.SUPPORT_ENABLED
            else "Support tickets are deliberately disabled; historical records remain stored.",
        )
        notifications_inconsistent = settings.SUPPORT_NOTIFICATIONS_ENABLED
        add(
            "support_notifications",
            "error" if notifications_inconsistent else "disabled",
            "No delivery backend is implemented; SUPPORT_NOTIFICATIONS_ENABLED must remain off."
            if notifications_inconsistent
            else "Notification delivery is not configured; support outbox records remain pending.",
        )
        report = {
            "status": "error" if any(c["status"] == "error" for c in checks) else "ready",
            "generated_at": timezone.now().isoformat(),
            "checks": checks,
        }
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            for check in checks:
                self.stdout.write(
                    f"[{str(check['status']).upper()}] {check['name']}: {check['detail']}"
                )
            self.stdout.write(f"Overall: {report['status']}")
        if options["strict"] and report["status"] == "error":
            raise CommandError("Production readiness contains errors.")

    def _tutoring_checks(self, add):
        if not settings.TUTORING_ENABLED:
            add("tutoring", "disabled", "Tutoring is deliberately disabled.")
            configured = [
                name
                for name in (
                    "TUTORING_TASK_QUEUE_PATH",
                    "TUTORING_WORKER_URL",
                    "TUTORING_TASK_AUDIENCE",
                    "TUTORING_TASK_SERVICE_ACCOUNT",
                    "TUTORING_OPENAI_API_KEY",
                    "TUTORING_AZURE_OPENAI_ENDPOINT",
                    "TUTORING_AZURE_OPENAI_API_KEY",
                )
                if getattr(settings, name)
            ]
            if configured:
                add(
                    "tutoring_configuration",
                    "warning",
                    "Tutoring is disabled although tutoring infrastructure is configured.",
                    configured_settings=configured,
                )
            return
        active = (
            ActivePrompt.objects.select_related("prompt_version")
            .filter(
                public_id=settings.TUTORING_PROMPT_PUBLIC_ID,
                prompt_version__status="published",
            )
            .first()
        )
        policy = None
        if active:
            try:
                policy = ModelPolicy.model_validate(active.prompt_version.model_policy)
                add("tutoring_prompt", "healthy", "An active published prompt is available.")
            except ValidationError:
                add("tutoring_prompt", "error", "The active prompt model policy is invalid.")
        else:
            add("tutoring_prompt", "error", "No active published prompt is available.")
        queue = {
            name: getattr(settings, name)
            for name in (
                "TUTORING_TASK_QUEUE_PATH",
                "TUTORING_WORKER_URL",
                "TUTORING_TASK_AUDIENCE",
                "TUTORING_TASK_SERVICE_ACCOUNT",
            )
        }
        missing = [name for name, value in queue.items() if not value]
        consistent = not missing and queue["TUTORING_WORKER_URL"] == queue["TUTORING_TASK_AUDIENCE"]
        add(
            "queue",
            "healthy" if consistent else "error",
            "Queue path is eligible."
            if consistent
            else f"Queue configuration is incomplete or inconsistent: {', '.join(missing)}.",
        )
        provider_ok = bool(policy) and (
            (policy.provider == "openai" and settings.TUTORING_OPENAI_API_KEY)
            or (
                policy.provider == "azure_openai"
                and settings.TUTORING_AZURE_OPENAI_ENDPOINT
                and settings.TUTORING_AZURE_OPENAI_API_KEY
            )
        )
        add(
            "provider",
            "healthy" if provider_ok else "error",
            "Provider credentials are configured."
            if provider_ok
            else "Provider configuration is unavailable or inconsistent.",
        )
        threshold = timezone.now() - timezone.timedelta(
            seconds=settings.TUTORING_AMBIGUOUS_ALERT_SECONDS
        )
        ambiguous = TutoringAttempt.objects.filter(
            status=TutoringAttempt.Status.PROVIDER_SUCCEEDED, submission__response__isnull=True
        )
        overdue = ambiguous.filter(created_at__lte=threshold).count()
        add(
            "ambiguous_attempts",
            "error" if overdue else ("warning" if ambiguous.exists() else "healthy"),
            f"{ambiguous.count()} unresolved; {overdue} overdue.",
        )
        pending = OutboxEvent.objects.filter(dispatched_at__isnull=True).order_by("created_at")
        oldest = pending.values_list("created_at", flat=True).first()
        add(
            "outbox",
            "warning" if pending.exists() else "healthy",
            f"{pending.count()} pending outbox record(s).",
            oldest_pending_at=oldest.isoformat() if oldest else None,
        )
