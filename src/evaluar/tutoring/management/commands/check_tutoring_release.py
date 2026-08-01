import importlib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from pydantic import ValidationError

from evaluar.tutoring.infrastructure.client_factory import ModelPolicy
from evaluar.tutoring.models import ActivePrompt, TutoringAttempt


class Command(BaseCommand):
    help = "Validate tutoring configuration and durable release prerequisites."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")

    def handle(self, *args, **options):
        errors: list[str] = []
        public_id = settings.TUTORING_PROMPT_PUBLIC_ID
        active = (
            ActivePrompt.objects.select_related("prompt_version")
            .filter(public_id=public_id)
            .first()
        )
        policy = None
        if active is None or active.prompt_version.status != "published":
            errors.append(f"No active published prompt exists for {public_id!r}.")
        else:
            try:
                policy = ModelPolicy.model_validate(active.prompt_version.model_policy)
            except ValidationError as exc:
                errors.append(f"Active prompt model policy is invalid: {exc}")

        required_queue_settings = {
            "TUTORING_TASK_QUEUE_PATH": settings.TUTORING_TASK_QUEUE_PATH,
            "TUTORING_WORKER_URL": settings.TUTORING_WORKER_URL,
            "TUTORING_TASK_AUDIENCE": settings.TUTORING_TASK_AUDIENCE,
            "TUTORING_TASK_SERVICE_ACCOUNT": settings.TUTORING_TASK_SERVICE_ACCOUNT,
        }
        missing = [name for name, value in required_queue_settings.items() if not value]
        if missing:
            errors.append(f"Missing queue/worker settings: {', '.join(missing)}.")
        elif settings.TUTORING_TASK_AUDIENCE != settings.TUTORING_WORKER_URL:
            errors.append("TUTORING_TASK_AUDIENCE must match TUTORING_WORKER_URL.")

        if policy and policy.provider == "openai" and not settings.TUTORING_OPENAI_API_KEY:
            errors.append("TUTORING_OPENAI_API_KEY is required by the active prompt.")
        if policy and policy.provider == "azure_openai":
            azure_missing = [
                name
                for name in ("TUTORING_AZURE_OPENAI_ENDPOINT", "TUTORING_AZURE_OPENAI_API_KEY")
                if not getattr(settings, name)
            ]
            if azure_missing:
                errors.append(f"Missing Azure provider settings: {', '.join(azure_missing)}.")
        if policy and policy.provider not in {"openai", "azure_openai"}:
            errors.append(f"Active prompt uses unsupported provider {policy.provider!r}.")

        for module in ("agent_framework", "google.cloud.tasks_v2"):
            try:
                importlib.import_module(module)
            except ImportError:
                errors.append(f"Required runtime package cannot be imported: {module}.")

        threshold = timezone.now() - timezone.timedelta(
            seconds=settings.TUTORING_AMBIGUOUS_ALERT_SECONDS
        )
        overdue_ambiguous = TutoringAttempt.objects.filter(
            status=TutoringAttempt.Status.PROVIDER_SUCCEEDED,
            submission__response__isnull=True,
            created_at__lte=threshold,
        ).count()
        if overdue_ambiguous:
            errors.append(
                f"{overdue_ambiguous} unresolved ambiguous attempt(s) exceed the alert threshold."
            )

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            if options["strict"]:
                raise CommandError(f"Tutoring release check failed with {len(errors)} error(s).")
            self.stdout.write(self.style.WARNING("Tutoring release check completed with warnings."))
            return
        self.stdout.write(self.style.SUCCESS("Tutoring release check passed."))
