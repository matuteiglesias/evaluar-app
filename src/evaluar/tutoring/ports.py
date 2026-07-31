from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class TutoringModelRequest:
    exercise_title: str
    exercise_body: str
    student_answer: str
    pedagogical_policy: str
    response_language: str


@dataclass(frozen=True)
class TutoringModelResult:
    summary: str
    diagnosis: tuple[str, ...]
    next_steps: tuple[str, ...]
    hints: tuple[str, ...]
    confidence: str
    provider: str
    requested_model: str
    served_model: str | None = None
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    framework_name: str = ""
    framework_version: str = ""


class TutoringModel(Protocol):
    async def generate(self, request: TutoringModelRequest) -> TutoringModelResult: ...


class TaskDispatcher(Protocol):
    def dispatch(self, submission_id: UUID) -> str:
        """Enqueue a submission and return the queue task identifier."""
        ...


class ModelError(Exception):
    category = "model_error"


class RetryableModelError(ModelError):
    """A bounded retry may succeed without changing the request."""

    category = "provider_retryable"


class TerminalModelError(ModelError):
    """The request must not be retried automatically."""

    category = "provider_terminal"
