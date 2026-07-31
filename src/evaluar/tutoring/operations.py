from django.db import transaction
from django.utils import timezone

from .models import (
    ActivePrompt,
    PromptVersion,
    TutoringAttempt,
    TutoringOperationalAudit,
    TutoringSubmission,
)
from .services import InvalidTransition, requeue_submission


@transaction.atomic
def activate_prompt(*, public_id: str, version: int, actor: str, note: str) -> ActivePrompt:
    prompt = PromptVersion.objects.select_for_update().get(public_id=public_id, version=version)
    if prompt.status != PromptVersion.Status.PUBLISHED:
        raise InvalidTransition("Only a published prompt version can be activated.")
    active, _ = ActivePrompt.objects.update_or_create(
        public_id=public_id, defaults={"prompt_version": prompt}
    )
    TutoringOperationalAudit.objects.create(
        action=TutoringOperationalAudit.Action.PROMPT_ACTIVATED,
        actor_identifier=actor,
        prompt_version=prompt,
        note=note,
        evidence={"version": version, "checksum": prompt.checksum},
    )
    return active


@transaction.atomic
def resolve_ambiguous_attempt(
    *, attempt_id, decision: str, actor: str, note: str, provider_request_id: str = ""
) -> TutoringAttempt:
    attempt = (
        TutoringAttempt.objects.select_for_update().select_related("submission").get(pk=attempt_id)
    )
    if attempt.status != TutoringAttempt.Status.PROVIDER_SUCCEEDED:
        raise InvalidTransition("Only provider-succeeded attempts are ambiguous.")
    if decision not in {"terminal", "retry", "attach-evidence"}:
        raise ValueError("Decision must be terminal, retry, or attach-evidence.")

    submission = TutoringSubmission.objects.select_for_update().get(pk=attempt.submission_id)
    evidence = {}
    if provider_request_id:
        attempt.provider_request_id = provider_request_id
        evidence["provider_request_id"] = provider_request_id

    if decision == "retry":
        attempt.status = TutoringAttempt.Status.RETRYABLE_FAILED
        attempt.error_category = "manual_retry_authorized"
        action = TutoringOperationalAudit.Action.AMBIGUOUS_RETRY_AUTHORIZED
        submission.status = TutoringSubmission.Status.FAILED
    elif decision == "attach-evidence":
        if not provider_request_id:
            raise ValueError("attach-evidence requires --provider-request-id.")
        attempt.status = TutoringAttempt.Status.TERMINAL_FAILED
        attempt.error_category = "provider_evidence_attached"
        action = TutoringOperationalAudit.Action.PROVIDER_EVIDENCE_ATTACHED
        submission.status = TutoringSubmission.Status.FAILED
    else:
        attempt.status = TutoringAttempt.Status.TERMINAL_FAILED
        attempt.error_category = "manual_ambiguous_termination"
        action = TutoringOperationalAudit.Action.AMBIGUOUS_TERMINATED
        submission.status = TutoringSubmission.Status.FAILED
    attempt.error_detail = note[:2000]
    attempt.finished_at = timezone.now()
    attempt.save()
    submission.save(update_fields=("status", "updated_at"))
    TutoringOperationalAudit.objects.create(
        action=action,
        actor_identifier=actor,
        submission=submission,
        attempt=attempt,
        note=note,
        evidence=evidence,
    )
    if decision == "retry":
        requeue_submission(submission.id)
    return attempt
