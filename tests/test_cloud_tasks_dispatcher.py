from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from evaluar.tutoring import queue


@dataclass
class CreatedTask:
    name: str


class Client:
    def __init__(self, result=None, error: BaseException | None = None):
        self.result = result
        self.error = error

    def create_task(self, *, parent: str, task: dict):
        if self.error is not None:
            raise self.error
        return self.result


def dispatcher(client: Client) -> queue.CloudTasksDispatcher:
    return queue.CloudTasksDispatcher(
        client=client,
        queue_path="projects/p/locations/l/queues/q",
        worker_url="https://worker.example.test/task",
        service_account_email="worker@example.test",
        audience="https://worker.example.test",
    )


def test_typed_already_exists_is_a_successful_replay(monkeypatch) -> None:
    class ProviderAlreadyExists(Exception):
        pass

    monkeypatch.setattr(
        queue,
        "_cloud_tasks_already_exists_type",
        lambda: ProviderAlreadyExists,
    )
    submission_id = uuid4()
    dispatch_id = uuid4()

    task_name = dispatcher(Client(error=ProviderAlreadyExists())).dispatch(
        submission_id=submission_id,
        dispatch_id=dispatch_id,
    )

    assert task_name.endswith(f"/tasks/tutoring-{submission_id}-{dispatch_id}")


def test_unrelated_same_named_exception_is_not_suppressed(monkeypatch) -> None:
    class ProviderAlreadyExists(Exception):
        pass

    SameNameButUnrelated = type("ProviderAlreadyExists", (Exception,), {})
    monkeypatch.setattr(
        queue,
        "_cloud_tasks_already_exists_type",
        lambda: ProviderAlreadyExists,
    )

    with pytest.raises(SameNameButUnrelated):
        dispatcher(Client(error=SameNameButUnrelated())).dispatch(
            submission_id=uuid4(),
            dispatch_id=uuid4(),
        )


def test_ordinary_provider_failure_propagates(monkeypatch) -> None:
    class ProviderAlreadyExists(Exception):
        pass

    monkeypatch.setattr(
        queue,
        "_cloud_tasks_already_exists_type",
        lambda: ProviderAlreadyExists,
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        dispatcher(Client(error=RuntimeError("provider unavailable"))).dispatch(
            submission_id=uuid4(),
            dispatch_id=uuid4(),
        )


def test_success_returns_provider_task_name(monkeypatch) -> None:
    class ProviderAlreadyExists(Exception):
        pass

    monkeypatch.setattr(
        queue,
        "_cloud_tasks_already_exists_type",
        lambda: ProviderAlreadyExists,
    )

    assert (
        dispatcher(Client(result=CreatedTask(name="provider-task"))).dispatch(
            submission_id=uuid4(),
            dispatch_id=uuid4(),
        )
        == "provider-task"
    )
