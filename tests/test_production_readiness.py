import json
from io import StringIO

import pytest
from django.core.management import call_command


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
