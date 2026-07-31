import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from .models import OutboxEvent, TutoringSubmission
from .ports import TaskDispatcher

logger = logging.getLogger(__name__)


class CloudTasksClient(Protocol):
    def create_task(self, *, parent: str, task: dict): ...


@dataclass
class CloudTasksDispatcher:
    """Cloud Tasks adapter with a deterministic task name for enqueue idempotency."""

    client: CloudTasksClient
    queue_path: str
    worker_url: str
    service_account_email: str
    audience: str

    @classmethod
    def from_settings(cls):
        from google.cloud import tasks_v2

        return cls(
            client=tasks_v2.CloudTasksClient(),
            queue_path=settings.TUTORING_TASK_QUEUE_PATH,
            worker_url=settings.TUTORING_WORKER_URL,
            service_account_email=settings.TUTORING_TASK_SERVICE_ACCOUNT,
            audience=settings.TUTORING_TASK_AUDIENCE,
        )

    def dispatch(self, submission_id: UUID) -> str:
        task_name = f"{self.queue_path}/tasks/tutoring-{submission_id}"
        task = {
            "name": task_name,
            "http_request": {
                "http_method": 1,  # google.cloud.tasks_v2.HttpMethod.POST
                "url": self.worker_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"submission_id": str(submission_id)}).encode(),
                "oidc_token": {
                    "service_account_email": self.service_account_email,
                    "audience": self.audience,
                },
            },
        }
        try:
            created = self.client.create_task(parent=self.queue_path, task=task)
            return created.name
        except Exception as exc:
            # A deterministic name turns ALREADY_EXISTS into a successful replay.
            if exc.__class__.__name__ == "AlreadyExists":
                return task_name
            raise


def dispatch_pending(dispatcher: TaskDispatcher, *, limit: int = 100) -> int:
    dispatched = 0
    for _ in range(limit):
        with transaction.atomic():
            event = (
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(
                    dispatched_at__isnull=True,
                    topic__in=(
                        "tutoring.submission.accepted",
                        "tutoring.submission.requeued",
                    ),
                )
                .order_by("created_at")
                .first()
            )
            if event is None:
                break
            event.dispatch_attempts += 1
            try:
                task_id = dispatcher.dispatch(event.aggregate_id)
            except Exception as exc:
                event.last_error = str(exc)[:2000]
                event.save(update_fields=("dispatch_attempts", "last_error"))
                logger.warning("tutoring.outbox_dispatch_failed", extra={"event_id": str(event.id)})
                break
            event.dispatched_at = django_timezone.now()
            event.last_error = ""
            event.save(update_fields=("dispatch_attempts", "dispatched_at", "last_error"))
            TutoringSubmission.objects.filter(
                pk=event.aggregate_id, status=TutoringSubmission.Status.ACCEPTED
            ).update(status=TutoringSubmission.Status.QUEUED)
            queue_delay_ms = round(
                (datetime.now(timezone.utc) - event.created_at).total_seconds() * 1000
            )
            logger.info(
                "tutoring.task_enqueued",
                extra={
                    "submission_id": str(event.aggregate_id),
                    "task_id": task_id,
                    "queue_delay_ms": queue_delay_ms,
                    "dispatch_attempt": event.dispatch_attempts,
                },
            )
            dispatched += 1
    return dispatched
