from __future__ import annotations

import pytest

from evaluar.tutoring.operations import create_prompt_draft, publish_prompt


pytestmark = pytest.mark.django_db


def policy(model: str = "gpt-test") -> dict:
    return {"provider": "openai", "requested_model": model}


def publish(public_id: str, *, instructions: str = "Guide the student.", **draft_changes):
    draft = create_prompt_draft(
        public_id=public_id,
        instructions=instructions,
        model_policy=policy(),
        actor="identity-test@example.com",
    )
    for field, value in draft_changes.items():
        setattr(draft, field, value)
    if draft_changes:
        draft.save(update_fields=tuple(draft_changes))
    return publish_prompt(
        public_id=public_id,
        version=draft.version,
        actor="identity-test@example.com",
        note="Identity regression fixture",
    )


def test_equivalent_execution_config_has_same_prompt_identity():
    first = publish("identity-equivalent-a")
    second = publish("identity-equivalent-b")

    assert first.checksum == second.checksum


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("system_instructions", "Guide the student, but ask one question at a time."),
        ("model_policy", policy("gpt-other")),
        ("temperature", 0.7),
        ("max_output_tokens", 1600),
        ("response_schema_version", "2"),
    ],
)
def test_material_execution_config_changes_prompt_identity(field, value):
    baseline = publish(f"identity-{field}-baseline")
    changed = publish(f"identity-{field}-changed", **{field: value})

    assert baseline.checksum != changed.checksum
