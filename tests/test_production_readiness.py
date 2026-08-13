import json
from io import StringIO

import pytest
from django.core.management import call_command

from evaluar.tutoring.models import ActivePrompt, PromptVersion


@pytest.mark.django_db
def test_readiness_json_distinguishes_disabled_capabilities(settings):
    settings.TUTORING_ENABLED = False
    settings.REQUIRE_PUBLISHED_COURSE = False
    settings.SUPPORT_ENABLED = False
    settings.SUPPORT_NOTIFICATIONS_ENABLED = False
    output = StringIO()

    call_command("production_readiness", "--json", stdout=output)

    report = json.loads(output.getvalue())
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert report["status"] == "ready"
    assert statuses["database"] == "healthy"
    assert statuses["schema"] == "healthy"
    assert statuses["content"] == "warning"
    assert statuses["tutoring"] == "disabled"
    assert statuses["support_notifications"] == "disabled"


@pytest.mark.django_db
def test_required_content_is_a_release_error(settings):
    settings.TUTORING_ENABLED = False
    settings.REQUIRE_PUBLISHED_COURSE = True
    settings.SUPPORT_NOTIFICATIONS_ENABLED = False
    output = StringIO()

    call_command("production_readiness", "--json", stdout=output)

    report = json.loads(output.getvalue())
    assert report["status"] == "error"
    assert next(c for c in report["checks"] if c["name"] == "content")["status"] == "error"


@pytest.mark.django_db
def test_inline_tutoring_does_not_require_cloud_tasks(settings):
    settings.TUTORING_ENABLED = True
    settings.TUTORING_EXECUTION_MODE = "inline"
    settings.TUTORING_OPENAI_API_KEY = "test-key"
    settings.TUTORING_PROMPT_PUBLIC_ID = "default"
    settings.REQUIRE_PUBLISHED_COURSE = False
    settings.SUPPORT_ENABLED = False
    settings.SUPPORT_NOTIFICATIONS_ENABLED = False
    prompt = PromptVersion.objects.create(
        public_id="default",
        version=1,
        system_instructions="Give formative guidance.",
        checksum="c" * 64,
        status=PromptVersion.Status.PUBLISHED,
        model_policy={
            "provider": "openai",
            "requested_model": "test-model",
            "timeout_seconds": 45,
            "max_input_chars": 40000,
            "max_cost_usd": 0.1,
            "input_usd_per_million": 0,
            "output_usd_per_million": 0,
        },
    )
    ActivePrompt.objects.create(public_id="default", prompt_version=prompt)
    output = StringIO()

    call_command("production_readiness", "--json", stdout=output)

    report = json.loads(output.getvalue())
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert report["status"] == "ready"
    assert statuses["tutoring_prompt"] == "healthy"
    assert statuses["tutoring_execution"] == "healthy"
    assert statuses["queue"] == "not_required"
    assert statuses["provider"] == "healthy"
