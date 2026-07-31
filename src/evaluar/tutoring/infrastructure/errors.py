from agent_framework.exceptions import AgentFrameworkException
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ContentFilterFinishReasonError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from ..ports import RetryableModelError, TerminalModelError


class ProviderTimeout(RetryableModelError):
    category = "provider_timeout"


class ProviderRateLimited(RetryableModelError):
    category = "provider_rate_limited"


class ProviderUnavailable(RetryableModelError):
    category = "provider_unavailable"


class ProviderRejected(TerminalModelError):
    category = "provider_rejected"


class ProviderAuthenticationFailed(TerminalModelError):
    category = "provider_authentication"


class MalformedModelOutput(TerminalModelError):
    category = "malformed_model_output"


class CostCeilingExceeded(TerminalModelError):
    category = "cost_ceiling_exceeded"


def normalize_provider_error(exc: Exception) -> RetryableModelError | TerminalModelError:
    """Map provider/framework exceptions to stable application error categories."""
    if isinstance(exc, (RetryableModelError, TerminalModelError)):
        return exc
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return ProviderTimeout("The model provider timed out.")
    if isinstance(exc, RateLimitError):
        return ProviderRateLimited("The model provider rate limit was reached.")
    if isinstance(exc, APIConnectionError):
        return ProviderUnavailable("The model provider is unavailable.")
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return ProviderAuthenticationFailed("The model provider rejected its credentials.")
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return ProviderUnavailable(f"The model provider returned HTTP {exc.status_code}.")
    if isinstance(exc, (BadRequestError, ContentFilterFinishReasonError)):
        return ProviderRejected("The model provider rejected the request.")
    if isinstance(exc, (ValidationError, APIResponseValidationError, TypeError, ValueError)):
        return MalformedModelOutput("The model returned malformed structured output.")
    if isinstance(exc, AgentFrameworkException):
        return ProviderRejected("Agent Framework could not execute the request.")
    return ProviderUnavailable("Unexpected model provider failure.")
