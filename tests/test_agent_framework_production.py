import asyncio
import importlib.metadata
import logging

import pytest
from agent_framework import AgentContext, ChatResponse, Message
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from evaluar.tutoring.infrastructure.client_factory import ModelPolicy, ProviderClientFactory
from evaluar.tutoring.infrastructure.errors import (
    CostCeilingExceeded,
    MalformedModelOutput,
    ProviderTimeout,
    normalize_provider_error,
)
from evaluar.tutoring.infrastructure.middleware import TutoringPolicyMiddleware
from evaluar.tutoring.infrastructure.production import ProductionTutoringModelFactory
from evaluar.tutoring.ports import TutoringModelRequest
from test_agent_framework_adapter import RecordingChatClient
from test_tutoring import context

pytestmark = pytest.mark.django_db


class InjectedClientFactory(ProviderClientFactory):
    def __init__(self, client):
        self.client = client

    def create(self, policy):
        self.policy = policy
        return self.client


def policy(**changes):
    value = {
        "provider": "openai",
        "requested_model": "test-model",
        "timeout_seconds": 1,
        "max_input_chars": 10_000,
        "max_cost_usd": 1,
        "input_usd_per_million": 1,
        "output_usd_per_million": 2,
    }
    value.update(changes)
    return value


def test_production_factory_constructs_stateless_agent_from_prompt_version():
    _, _, prompt = context()
    prompt.model_policy = policy()
    # PromptVersion is immutable in storage; this is an isolated in-memory configuration fixture.
    client = RecordingChatClient()
    client_factory = InjectedClientFactory(client)
    model = ProductionTutoringModelFactory(client_factory).for_prompt(prompt)
    output = asyncio.run(
        model.generate(TutoringModelRequest("Title", "Body", "Answer", "ignored", "es"))
    )
    assert output.requested_model == "test-model"
    assert client_factory.policy == ModelPolicy.model_validate(policy())
    assert client.options["instructions"] == prompt.system_instructions
    assert client.options["temperature"] == prompt.temperature
    assert client.options["max_tokens"] == prompt.max_output_tokens
    assert client.options["tool_choice"] == "none"
    assert client.options["store"] is False


@override_settings(TUTORING_CAPTURE_SENSITIVE_TELEMETRY=True)
def test_sensitive_telemetry_cannot_be_enabled():
    with pytest.raises(ImproperlyConfigured, match="Sensitive tutoring telemetry"):
        ProductionTutoringModelFactory()


def middleware(**changes):
    values = {
        "provider": "test",
        "model": "test",
        "timeout_seconds": 1,
        "max_input_chars": 100,
        "max_cost_usd": 1,
        "input_usd_per_million": 1,
        "output_usd_per_million": 1,
        "max_output_tokens": 10,
    }
    values.update(changes)
    return TutoringPolicyMiddleware(**values)


def context_with_secret():
    return AgentContext(
        agent=object(),
        messages=[],
        metadata={"student_answer": "must-not-be-logged"},
    )


def test_timeout_is_normalized_and_telemetry_is_metadata_only(caplog):
    async def execute():
        async def slow_call():
            await asyncio.sleep(0.05)

        await middleware(timeout_seconds=0.001).process(context_with_secret(), slow_call)

    with caplog.at_level(logging.INFO), pytest.raises(ProviderTimeout):
        asyncio.run(execute())
    assert "must-not-be-logged" not in caplog.text
    assert "tutoring.agent_invocation" in caplog.text


def test_cost_ceiling_blocks_provider_call():
    called = False

    async def execute():
        async def provider_call():
            nonlocal called
            called = True

        await middleware(max_cost_usd=0.000001, output_usd_per_million=1000).process(
            context_with_secret(), provider_call
        )

    with pytest.raises(CostCeilingExceeded):
        asyncio.run(execute())
    assert called is False


def test_malformed_output_has_stable_terminal_taxonomy():
    normalized = normalize_provider_error(ValueError("provider response included bad JSON"))
    assert isinstance(normalized, MalformedModelOutput)
    assert normalized.category == "malformed_model_output"
    assert "bad JSON" not in str(normalized)


def test_adapter_rejects_malformed_structured_provider_output():
    class MalformedClient:
        async def get_response(self, messages=None, *, stream=False, options=None, **kwargs):
            return ChatResponse(
                messages=[Message(role="assistant", contents=["not valid JSON"])],
                response_format=options["response_format"],
            )

    model = ProductionTutoringModelFactory(InjectedClientFactory(MalformedClient()))
    _, _, prompt = context()
    prompt.model_policy = policy()
    adapter = model.for_prompt(prompt)
    with pytest.raises(MalformedModelOutput):
        asyncio.run(
            adapter.generate(TutoringModelRequest("Title", "Body", "Answer", "Policy", "en"))
        )


@override_settings(TUTORING_OPENAI_API_KEY="secret-test-key", TUTORING_OPENAI_BASE_URL="")
def test_provider_client_factory_is_provider_scoped_and_cached():
    factory = ProviderClientFactory()
    configured_policy = ModelPolicy.model_validate(policy())
    first = factory.create(configured_policy)
    second = factory.create(configured_policy)
    assert first is second
    assert len(factory._clients) == 1


def test_unknown_provider_is_rejected_before_execution():
    configured_policy = ModelPolicy.model_validate(policy(provider="unknown"))
    with pytest.raises(ImproperlyConfigured, match="Unsupported tutoring provider"):
        ProviderClientFactory().create(configured_policy)


def test_framework_upgrade_contract_is_pinned_and_smoke_tested():
    assert importlib.metadata.version("agent-framework-core") == "1.13.0"
    assert importlib.metadata.version("agent-framework-openai") == "1.12.0"
