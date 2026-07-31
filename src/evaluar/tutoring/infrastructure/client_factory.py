from dataclasses import dataclass, field
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic import BaseModel, ConfigDict, Field

from agent_framework import SupportsChatGetResponse
from agent_framework.openai import OpenAIChatClient


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    requested_model: str
    timeout_seconds: float = Field(default=45, gt=0, le=180)
    max_input_chars: int = Field(default=40_000, gt=0, le=200_000)
    max_cost_usd: float = Field(default=0.10, gt=0, le=10)
    input_usd_per_million: float = Field(default=0, ge=0)
    output_usd_per_million: float = Field(default=0, ge=0)


@dataclass
class ProviderClientFactory:
    """Build and cache provider clients without exposing credentials to the domain."""

    _clients: dict[tuple[str, str], SupportsChatGetResponse] = field(default_factory=dict)

    def create(self, policy: ModelPolicy) -> SupportsChatGetResponse:
        key = (policy.provider, policy.requested_model)
        if key in self._clients:
            return self._clients[key]
        if policy.provider == "openai":
            if not settings.TUTORING_OPENAI_API_KEY:
                raise ImproperlyConfigured("TUTORING_OPENAI_API_KEY is required.")
            client = OpenAIChatClient(
                model=policy.requested_model,
                api_key=settings.TUTORING_OPENAI_API_KEY,
                base_url=settings.TUTORING_OPENAI_BASE_URL or None,
            )
        elif policy.provider == "azure_openai":
            if (
                not settings.TUTORING_AZURE_OPENAI_ENDPOINT
                or not settings.TUTORING_AZURE_OPENAI_API_KEY
            ):
                raise ImproperlyConfigured(
                    "TUTORING_AZURE_OPENAI_ENDPOINT and TUTORING_AZURE_OPENAI_API_KEY are required."
                )
            client = OpenAIChatClient(
                model=policy.requested_model,
                api_key=settings.TUTORING_AZURE_OPENAI_API_KEY,
                azure_endpoint=settings.TUTORING_AZURE_OPENAI_ENDPOINT,
                api_version=settings.TUTORING_AZURE_OPENAI_API_VERSION,
            )
        else:
            raise ImproperlyConfigured(f"Unsupported tutoring provider: {policy.provider}")
        self._clients[key] = client
        return client
