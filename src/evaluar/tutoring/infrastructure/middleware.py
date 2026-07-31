import asyncio
import logging
import time

from agent_framework import AgentContext, AgentMiddleware

from .errors import CostCeilingExceeded, ProviderTimeout

logger = logging.getLogger(__name__)


class TutoringPolicyMiddleware(AgentMiddleware):
    """Enforce execution ceilings and emit metadata-only telemetry."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        timeout_seconds: float,
        max_input_chars: int,
        max_cost_usd: float,
        input_usd_per_million: float,
        output_usd_per_million: float,
        max_output_tokens: int,
    ):
        self.provider = provider
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_input_chars = max_input_chars
        self.max_cost_usd = max_cost_usd
        self.input_usd_per_million = input_usd_per_million
        self.output_usd_per_million = output_usd_per_million
        self.max_output_tokens = max_output_tokens

    async def process(self, context: AgentContext, call_next) -> None:
        # Approximation is deliberately conservative and used only as a preflight ceiling.
        instructions = (context.options or {}).get("instructions", "")
        input_chars = len(instructions) + sum(
            len(message.text or "") for message in context.messages
        )
        if input_chars > self.max_input_chars:
            raise CostCeilingExceeded("The tutoring input exceeds its configured size ceiling.")
        estimated_input_tokens = (input_chars + 3) // 4
        projected_cost = (
            estimated_input_tokens * self.input_usd_per_million
            + self.max_output_tokens * self.output_usd_per_million
        ) / 1_000_000
        if projected_cost > self.max_cost_usd:
            raise CostCeilingExceeded("The model call exceeds its configured cost ceiling.")

        started = time.monotonic()
        status = "succeeded"
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await call_next()
        except TimeoutError as exc:
            status = "timeout"
            raise ProviderTimeout("The model call exceeded its configured timeout.") from exc
        except Exception:
            status = "failed"
            raise
        finally:
            # Never add messages, prompts, responses, or student identifiers to this record.
            logger.info(
                "tutoring.agent_invocation",
                extra={
                    "provider": self.provider,
                    "requested_model": self.model,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "status": status,
                    "sensitive_content_recorded": False,
                },
            )
