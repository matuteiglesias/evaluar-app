from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import ValidationError
from agent_framework.observability import OBSERVABILITY_SETTINGS

from ..models import PromptVersion
from .agent_framework import AgentFrameworkTutoringModel
from .client_factory import ModelPolicy, ProviderClientFactory
from .middleware import TutoringPolicyMiddleware


class ProductionTutoringModelFactory:
    def __init__(self, client_factory: ProviderClientFactory | None = None):
        if settings.TUTORING_CAPTURE_SENSITIVE_TELEMETRY:
            raise ImproperlyConfigured(
                "Sensitive tutoring telemetry is prohibited in the production adapter."
            )
        # Override ENABLE_SENSITIVE_DATA defensively while preserving metadata instrumentation.
        OBSERVABILITY_SETTINGS.enable_sensitive_data = False
        self.client_factory = client_factory or ProviderClientFactory()

    def for_prompt(self, prompt: PromptVersion) -> AgentFrameworkTutoringModel:
        if prompt.status != PromptVersion.Status.PUBLISHED:
            raise ImproperlyConfigured("The tutoring adapter requires a published prompt.")
        try:
            policy = ModelPolicy.model_validate(prompt.model_policy)
        except ValidationError as exc:
            raise ImproperlyConfigured("PromptVersion has an invalid model policy.") from exc
        middleware = TutoringPolicyMiddleware(
            provider=policy.provider,
            model=policy.requested_model,
            timeout_seconds=policy.timeout_seconds,
            max_input_chars=policy.max_input_chars,
            max_cost_usd=policy.max_cost_usd,
            input_usd_per_million=policy.input_usd_per_million,
            output_usd_per_million=policy.output_usd_per_million,
            max_output_tokens=prompt.max_output_tokens,
        )
        return AgentFrameworkTutoringModel(
            self.client_factory.create(policy),
            provider=policy.provider,
            requested_model=policy.requested_model,
            instructions=prompt.system_instructions,
            temperature=prompt.temperature,
            max_output_tokens=prompt.max_output_tokens,
            middleware=(middleware,),
        )
