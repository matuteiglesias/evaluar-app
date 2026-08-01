import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from evaluar.tutoring.fakes import FakeTutoringModel
from evaluar.tutoring.models import (
    ActivePrompt,
    CourseTutoringQuotaUsage,
    OutboxEvent,
    PromptVersion,
    TutoringAttempt,
    TutoringOperationalAudit,
    TutoringQuotaUsage,
    TutoringSubmission,
)
from evaluar.tutoring.operations import (
    activate_prompt,
    create_prompt_draft,
    publish_prompt,
    resolve_ambiguous_attempt,
)
from evaluar.tutoring.services import QuotaExceeded, run_submission, submit_answer
from test_tutoring import context, result

pytestmark = pytest.mark.django_db


def valid_policy():
    return {"provider": "openai", "requested_model": "gpt-test"}


def test_prompt_draft_publication_creates_audited_immutable_version_without_activation():
    draft = create_prompt_draft(
        public_id="release",
        instructions="Guide the student.",
        model_policy=valid_policy(),
        actor="operator@example.com",
    )
    prompt = publish_prompt(
        public_id="release",
        version=draft.version,
        actor="approver@example.com",
        note="Approved after staging regression",
    )
    assert prompt.status == PromptVersion.Status.PUBLISHED
    assert len(prompt.checksum) == 64
    assert not ActivePrompt.objects.filter(public_id="release").exists()
    assert TutoringOperationalAudit.objects.filter(action="prompt_draft_created").exists()
    publication = TutoringOperationalAudit.objects.get(action="prompt_published")
    assert publication.prompt_version == prompt
    assert publication.actor_identifier == "approver@example.com"


def test_prompt_creation_and_publication_commands(tmp_path):
    instructions = tmp_path / "prompt.md"
    instructions.write_text("Guide, do not reveal answers.", encoding="utf-8")
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(valid_policy()), encoding="utf-8")
    output = StringIO()
    call_command(
        "create_tutoring_prompt",
        "--public-id",
        "commands",
        "--instructions-file",
        str(instructions),
        "--model-policy-file",
        str(policy_file),
        "--actor",
        "operator@example.com",
        stdout=output,
    )
    assert "Created prompt draft commands version 1" in output.getvalue()
    call_command(
        "publish_tutoring_prompt",
        "--public-id",
        "commands",
        "--prompt-version",
        "1",
        "--actor",
        "approver@example.com",
        "--note",
        "Staging approved",
        stdout=output,
    )
    assert PromptVersion.objects.get(public_id="commands", version=1).status == "published"


def test_prompt_activation_and_rollback_preserve_historical_references():
    user, version, first = context()
    second = PromptVersion.objects.create(
        public_id="default",
        version=2,
        system_instructions="Revised policy",
        checksum="d" * 64,
        status=PromptVersion.Status.PUBLISHED,
        model_policy={"provider": "openai", "requested_model": "new-model"},
    )
    activate_prompt(public_id="default", version=1, actor="release@example.com", note="Initial")
    submission = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=first,
        student_answer="answer",
        idempotency_key="historical",
    )
    activate_prompt(public_id="default", version=2, actor="release@example.com", note="Promote")
    activate_prompt(public_id="default", version=1, actor="release@example.com", note="Rollback")
    submission.refresh_from_db()
    assert submission.prompt_version == first
    assert ActivePrompt.objects.get(public_id="default").prompt_version == first
    assert TutoringOperationalAudit.objects.filter(action="prompt_activated").count() == 3
    assert second.model_policy["requested_model"] == "new-model"


def ambiguous_attempt(existing_context=None):
    user, version, prompt = existing_context or context()
    submission = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="answer",
        idempotency_key="ambiguous",
    )
    attempt = TutoringAttempt.objects.create(
        submission=submission,
        number=1,
        status=TutoringAttempt.Status.PROVIDER_SUCCEEDED,
        prompt_checksum=prompt.checksum,
        response_schema_version=prompt.response_schema_version,
        provider="openai",
    )
    submission.status = TutoringSubmission.Status.RUNNING
    submission.save(update_fields=("status",))
    return submission, attempt


@override_settings(TUTORING_ATTEMPT_LEASE_SECONDS=0)
def test_ambiguous_attempt_never_repeats_provider_call_automatically():
    submission, _ = ambiguous_attempt()
    model = FakeTutoringModel(result())
    assert run_submission(submission.id, model) is None
    assert model.requests == []


@pytest.mark.parametrize(
    ("decision", "expected_status", "expected_action"),
    [
        ("terminal", "terminal_failed", "ambiguous_terminated"),
        ("retry", "retryable_failed", "ambiguous_retry_authorized"),
        ("attach-evidence", "terminal_failed", "provider_evidence_attached"),
    ],
)
def test_ambiguous_recovery_requires_an_audited_manual_decision(
    decision, expected_status, expected_action
):
    submission, attempt = ambiguous_attempt()
    resolved = resolve_ambiguous_attempt(
        attempt_id=attempt.id,
        decision=decision,
        actor="operator@example.com",
        note="Reviewed provider console",
        provider_request_id="req-recovered" if decision == "attach-evidence" else "",
    )
    assert resolved.status == expected_status
    audit = TutoringOperationalAudit.objects.get(action=expected_action)
    assert audit.actor_identifier == "operator@example.com"
    assert audit.attempt == attempt
    if decision == "retry":
        submission.refresh_from_db()
        assert submission.status == TutoringSubmission.Status.QUEUED
        assert OutboxEvent.objects.filter(topic="tutoring.submission.requeued").exists()


@override_settings(TUTORING_DAILY_QUOTA=1, TUTORING_COURSE_DAILY_QUOTA=1)
def test_duplicate_and_failed_dispatch_do_not_bypass_or_double_charge_quotas():
    user, version, prompt = context()
    first = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="answer",
        idempotency_key="same",
    )
    duplicate = submit_answer(
        user=user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="answer",
        idempotency_key="same",
    )
    assert duplicate == first
    assert TutoringQuotaUsage.objects.get().reserved_count == 1
    assert CourseTutoringQuotaUsage.objects.get().reserved_count == 1
    assert OutboxEvent.objects.get().dispatched_at is None
    with pytest.raises(QuotaExceeded):
        submit_answer(
            user=user,
            exercise_version=version,
            prompt_version=prompt,
            student_answer="another",
            idempotency_key="another",
        )


@override_settings(TUTORING_DAILY_QUOTA=10, TUTORING_COURSE_DAILY_QUOTA=1)
def test_aggregate_course_quota_applies_across_students():
    first_user, version, prompt = context()
    submit_answer(
        user=first_user,
        exercise_version=version,
        prompt_version=prompt,
        student_answer="first",
        idempotency_key="first-student",
    )
    second_user = type(first_user).objects.create_user("second-quota-student")
    with pytest.raises(QuotaExceeded, match="course"):
        submit_answer(
            user=second_user,
            exercise_version=version,
            prompt_version=prompt,
            student_answer="second",
            idempotency_key="second-student",
        )


def test_operational_commands_activate_list_and_resolve_attempts():
    operational_context = context()
    _, _, prompt = operational_context
    output = StringIO()
    call_command(
        "activate_tutoring_prompt",
        "--public-id",
        prompt.public_id,
        "--prompt-version",
        str(prompt.version),
        "--actor",
        "command-test@example.com",
        "--note",
        "command test",
        stdout=output,
    )
    assert "Active prompt" in output.getvalue()
    _, attempt = ambiguous_attempt(operational_context)
    listed = StringIO()
    call_command("list_ambiguous_tutoring_attempts", stdout=listed)
    assert str(attempt.id) in listed.getvalue()
    call_command(
        "resolve_ambiguous_tutoring_attempt",
        "--attempt",
        str(attempt.id),
        "--decision",
        "terminal",
        "--actor",
        "command-test@example.com",
        "--note",
        "command resolution",
    )
    attempt.refresh_from_db()
    assert attempt.status == TutoringAttempt.Status.TERMINAL_FAILED


def test_operational_status_is_machine_readable_and_includes_release_signals():
    ambiguous_attempt()
    output = StringIO()
    call_command("tutoring_operational_status", "--json", stdout=output)
    signals = json.loads(output.getvalue())
    assert signals["ambiguous_attempts"] == 1
    assert signals["pending_outbox_events"] == 1
    assert "estimated_cost_usd" in signals
    assert "oldest_queued_age_seconds" in signals
