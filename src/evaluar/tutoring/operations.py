import hashlib
import json

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .infrastructure.client_factory import ModelPolicy
from .models import (
    ActivePrompt,
    PromptDraft,
    PromptVersion,
    TutoringAttempt,
    TutoringOperationalAudit,
    TutoringSubmission,
)
from .services import InvalidTransition, requeue_submission


def _prompt_checksum(draft: PromptDraft) -> str:
    content = {
        "system_instructions": draft.system_instructions,
        "response_schema_version": draft.response_schema_version,
        "model_policy": draft.model_policy,
        "temperature": draft.temperature,
        "max_output_tokens": draft.max_output_tokens,
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic
def create_prompt_draft(
    *, public_id: str, instructions: str, model_policy: dict, actor: str
) -> PromptDraft:
    validated_policy = ModelPolicy.model_validate(model_policy).model_dump(mode="json")
    latest_draft = (
        PromptDraft.objects.filter(public_id=public_id).aggregate(Max("version"))["version__max"]
        or 0
    )
    latest_published = (
        PromptVersion.objects.filter(public_id=public_id).aggregate(Max("version"))["version__max"]
        or 0
    )
    draft = PromptDraft.objects.create(
        public_id=public_id,
        version=max(latest_draft, latest_published) + 1,
        system_instructions=instructions,
        model_policy=validated_policy,
    )
    TutoringOperationalAudit.objects.create(
        action=TutoringOperationalAudit.Action.PROMPT_DRAFT_CREATED,
        actor_identifier=actor,
        note="Prompt draft created.",
        evidence={"public_id": public_id, "version": draft.version},
    )
    return draft


@transaction.atomic
def publish_prompt(*, public_id: str, version: int, actor: str, note: str) -> PromptVersion:
    draft = PromptDraft.objects.select_for_update().get(public_id=public_id, version=version)
    validated_policy = ModelPolicy.model_validate(draft.model_policy).model_dump(mode="json")
    if PromptVersion.objects.filter(public_id=public_id, version=version).exists():
        raise InvalidTransition("This prompt version is already published.")
    prompt = PromptVersion.objects.create(
        public_id=draft.public_id,
        version=draft.version,
        system_instructions=draft.system_instructions,
        response_schema_version=draft.response_schema_version,
        model_policy=validated_policy,
        temperature=draft.temperature,
        max_output_tokens=draft.max_output_tokens,
        checksum=_prompt_checksum(draft),
        status=PromptVersion.Status.PUBLISHED,
        published_at=timezone.now(),
    )
    TutoringOperationalAudit.objects.create(
        action=TutoringOperationalAudit.Action.PROMPT_PUBLISHED,
        actor_identifier=actor,
        prompt_version=prompt,
        note=note,
        evidence={"version": version, "checksum": prompt.checksum},
    )
    return prompt


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
