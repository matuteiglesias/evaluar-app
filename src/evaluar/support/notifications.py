import logging
from typing import Protocol
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from evaluar.tutoring.models import OutboxEvent

logger = logging.getLogger(__name__)


class NotificationSender(Protocol):
    def send(self, event: OutboxEvent) -> str: ...


def _claim_notification(*, excluded_ids: set[UUID]) -> OutboxEvent | None:
    now = timezone.now()
    lease_seconds = getattr(settings, "SUPPORT_NOTIFICATION_LEASE_SECONDS", 300)
    with transaction.atomic():
        event = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(topic__startswith="support.ticket.", dispatched_at__isnull=True)
            .filter(
                Q(status=OutboxEvent.Status.PENDING)
                | Q(status=OutboxEvent.Status.DISPATCHING, claim_expires_at__lte=now)
            )
            .exclude(id__in=excluded_ids)
            .order_by("created_at")
            .first()
        )
        if event is None:
            return None
        event.status = OutboxEvent.Status.DISPATCHING
        event.claimed_at = now
        event.claim_expires_at = now + timezone.timedelta(seconds=lease_seconds)
        event.dispatch_attempts += 1
        event.save(
            update_fields=(
                "status",
                "claimed_at",
                "claim_expires_at",
                "dispatch_attempts",
            )
        )
        return event


def dispatch_support_notifications(sender: NotificationSender, *, limit: int = 100) -> int:
    """Deliver support outbox records after domain commits; failures remain retryable."""
    if not settings.SUPPORT_ENABLED or not settings.SUPPORT_NOTIFICATIONS_ENABLED:
        logger.warning("support.notification_not_configured")
        return 0
    delivered = 0
    attempted: set[UUID] = set()
    for _ in range(limit):
        event = _claim_notification(excluded_ids=attempted)
        if event is None:
            break
        attempted.add(event.id)
        claim = event.claimed_at
        try:
            sender.send(event)
        except Exception as exc:
            with transaction.atomic():
                locked = OutboxEvent.objects.select_for_update().get(pk=event.id)
                if locked.claimed_at == claim:
                    locked.status = OutboxEvent.Status.PENDING
                    locked.claimed_at = None
                    locked.claim_expires_at = None
                    locked.last_error = str(exc)[:2000]
                    locked.save(
                        update_fields=(
                            "status",
                            "claimed_at",
                            "claim_expires_at",
                            "last_error",
                        )
                    )
            logger.warning("support.notification_failed", extra={"event_id": str(event.id)})
            continue
        with transaction.atomic():
            locked = OutboxEvent.objects.select_for_update().get(pk=event.id)
            if locked.status != OutboxEvent.Status.DISPATCHING or locked.claimed_at != claim:
                continue
            locked.status = OutboxEvent.Status.DISPATCHED
            locked.claimed_at = None
            locked.claim_expires_at = None
            locked.dispatched_at = timezone.now()
            locked.last_error = ""
            locked.save(
                update_fields=(
                    "status",
                    "claimed_at",
                    "claim_expires_at",
                    "dispatched_at",
                    "last_error",
                )
            )
            delivered += 1
    return delivered
