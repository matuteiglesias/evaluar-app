import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone as django_timezone

from .models import OutboxEvent, TutoringSubmission
from .ports import TaskDispatcher

logger = logging.getLogger(__name__)


class CloudTasksClient(Protocol):
    def create_task(self, *, parent: str, task: dict): ...


def _cloud_tasks_already_exists_type() -> type[BaseException]:
    """Resolve the provider exception only when the Cloud Tasks adapter is used."""

    from google.api_core.exceptions import AlreadyExists

    return AlreadyExists


@dataclass
class CloudTasksDispatcher:
    """Cloud Tasks adapter with a deterministic name per outbox delivery."""

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

    def dispatch(self, *, submission_id: UUID, dispatch_id: UUID) -> str:
        task_name = f"{self.queue_path}/tasks/tutoring-{submission_id}-{dispatch_id}"
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
        except _cloud_tasks_already_exists_type():
            # A deterministic name turns the provider's ALREADY_EXISTS into replay success.
            return task_name


def _claim_event(*, excluded_ids: set[UUID]) -> OutboxEvent | None:
    now = django_timezone.now()
    lease_seconds = getattr(settings, "TUTORING_OUTBOX_LEASE_SECONDS", 300)
    with transaction.atomic():
        event = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(dispatched_at__isnull=True)
            .filter(
                Q(status=OutboxEvent.Status.PENDING)
                | Q(
                    status=OutboxEvent.Status.DISPATCHING,
                    claim_expires_at__lte=now,
                )
            )
            .filter(
                topic__in=(
                    "tutoring.submission.accepted",
                    "tutoring.submission.requeued",
                )
            )
            .exclude(id__in=excluded_ids)
            .order_by("created_at")
            .first()
        )
        if event is None:
            return None
        event.status = OutboxEvent.Status.DISPATCHING
        event.claimed_at = now
        event.claim_expires_at = now + django_timezone.timedelta(seconds=lease_seconds)
        event.dispatch_attempts += 1
        event.save(update_fields=("status", "claimed_at", "claim_expires_at", "dispatch_attempts"))
        return event


def dispatch_pending(dispatcher: TaskDispatcher, *, limit: int = 100) -> int:
    dispatched = 0
    attempted_ids: set[UUID] = set()
    for _ in range(limit):
        event = _claim_event(excluded_ids=attempted_ids)
        if event is None:
            break
        attempted_ids.add(event.id)
        claimed_at = event.claimed_at
        try:
            task_id = dispatcher.dispatch(
                submission_id=event.aggregate_id,
                dispatch_id=event.id,
            )
        except Exception as exc:
            with transaction.atomic():
                locked = OutboxEvent.objects.select_for_update().get(pk=event.id)
                if locked.claimed_at == claimed_at:
                    locked.status = OutboxEvent.Status.PENDING
                    locked.claimed_at = None
                    locked.claim_expires_at = None
                    locked.last_error = str(exc)[:2000]
                    locked.save(
                        update_fields=("status", "claimed_at", "claim_expires_at", "last_error")
                    )
            logger.warning("tutoring.outbox_dispatch_failed", extra={"event_id": str(event.id)})
            continue
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update().get(pk=event.id)
            if event.status != OutboxEvent.Status.DISPATCHING or event.claimed_at != claimed_at:
                continue
            event.status = OutboxEvent.Status.DISPATCHED
            event.claimed_at = None
            event.claim_expires_at = None
            event.dispatched_at = django_timezone.now()
            event.last_error = ""
            event.save(
                update_fields=(
                    "status",
                    "claimed_at",
                    "claim_expires_at",
                    "dispatched_at",
                    "last_error",
                )
            )
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
