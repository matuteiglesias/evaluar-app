from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from evaluar.tutoring.models import ActivePrompt, PromptVersion, TutoringAttempt
from test_tutoring_operations import ambiguous_attempt

pytestmark = pytest.mark.django_db


RELEASE_SETTINGS = {
    "TUTORING_PROMPT_PUBLIC_ID": "release",
    "TUTORING_TASK_QUEUE_PATH": "projects/p/locations/l/queues/q",
    "TUTORING_WORKER_URL": "https://worker.example/internal/tutoring/run",
    "TUTORING_TASK_AUDIENCE": "https://worker.example/internal/tutoring/run",
    "TUTORING_TASK_SERVICE_ACCOUNT": "tasks@example.iam.gserviceaccount.com",
    "TUTORING_OPENAI_API_KEY": "test-secret",
    "TUTORING_AMBIGUOUS_ALERT_SECONDS": 900,
}


def active_release_prompt():
    prompt = PromptVersion.objects.create(
        public_id="release",
        version=1,
        system_instructions="Guide the student.",
        checksum="a" * 64,
        status=PromptVersion.Status.PUBLISHED,
        model_policy={"provider": "openai", "requested_model": "gpt-test"},
    )
    ActivePrompt.objects.create(public_id="release", prompt_version=prompt)


@override_settings(**RELEASE_SETTINGS)
def test_strict_release_check_passes_for_complete_configuration():
    active_release_prompt()
    output = StringIO()
    call_command("check_tutoring_release", "--strict", stdout=output)
    assert "Tutoring release check passed" in output.getvalue()


@override_settings(**RELEASE_SETTINGS)
def test_strict_release_check_rejects_overdue_ambiguous_attempt():
    active_release_prompt()
    _, attempt = ambiguous_attempt()
    TutoringAttempt.objects.filter(pk=attempt.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )
    with pytest.raises(CommandError, match="release check failed"):
        call_command("check_tutoring_release", "--strict")
