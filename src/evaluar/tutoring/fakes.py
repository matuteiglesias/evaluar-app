from .ports import TutoringModelRequest, TutoringModelResult


class FakeTutoringModel:
    """Deterministic, network-free adapter for application and contract tests."""

    def __init__(self, result: TutoringModelResult):
        self.result = result
        self.requests: list[TutoringModelRequest] = []

    async def generate(self, request: TutoringModelRequest) -> TutoringModelResult:
        self.requests.append(request)
        return self.result
