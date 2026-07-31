from datetime import datetime, timezone
import json

import pytest

from scripts.export_firestore import PartialExportError, export_evidence


class FakeReference:
    def __init__(self, path, children=()):
        self.path = path
        self._children = list(children)

    def collections(self):
        return iter(self._children)


class FakeSnapshot:
    def __init__(self, path, fields, children=()):
        self.reference = FakeReference(path, children)
        self._fields = fields

    def to_dict(self):
        return self._fields


class FakeCollection:
    def __init__(self, path, documents=(), failure=None):
        self.path = path
        self.id = path.rsplit("/", 1)[-1]
        self._documents = list(documents)
        self._failure = failure

    def stream(self):
        if self._failure:
            raise self._failure
        return iter(self._documents)


class FakeClient:
    def __init__(self, collections):
        self._collections = collections

    def collections(self):
        return iter(self._collections)


class FakeGeoPoint:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude


def fake_client():
    empty_child = FakeCollection("parents/p1/empty")
    child = FakeCollection(
        "parents/p1/children",
        [FakeSnapshot("parents/p1/children/c1", {"optional": None})],
    )
    parents = FakeCollection(
        "parents",
        [
            FakeSnapshot(
                "parents/p1",
                {
                    "at": datetime(2024, 1, 2, tzinfo=timezone.utc),
                    "blob": b"abc",
                    "location": FakeGeoPoint(-34.6, -58.4),
                    "link": FakeReference("other/o1"),
                },
                [empty_child, child],
            )
        ],
    )
    return FakeClient(
        [FakeCollection("empty"), FakeCollection("other", [FakeSnapshot("other/o1", {})]), parents]
    )


def test_export_is_deterministic_and_recurses(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    kwargs = dict(source_environment="test", project_id="fake-project", source_commit="abc123")
    manifest = export_evidence(fake_client(), first, **kwargs)
    export_evidence(fake_client(), second, **kwargs)

    assert manifest["collection_counts"] == {
        "empty": 0,
        "other": 1,
        "parents": 1,
        "parents/p1/children": 1,
        "parents/p1/empty": 0,
    }
    assert (first / "documents.ndjson").read_bytes() == (second / "documents.ndjson").read_bytes()
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    records = [json.loads(line) for line in (first / "documents.ndjson").read_text().splitlines()]
    parent = next(item for item in records if item["document_path"] == "parents/p1")
    assert parent["fields"]["at"]["__type__"] == "timestamp"
    assert parent["fields"]["blob"] == {"__type__": "bytes", "encoding": "base64", "value": "YWJj"}
    assert parent["fields"]["link"] == {"__type__": "reference", "path": "other/o1"}
    assert parent["fields"]["location"]["__type__"] == "geopoint"


def test_list_only_writes_nothing(tmp_path):
    output = tmp_path / "unused"
    manifest = export_evidence(
        fake_client(), output, source_environment="test", project_id="fake", list_only=True
    )
    assert manifest["list_only"] is True
    assert not output.exists()


def test_partial_read_writes_incomplete_manifest_and_fails(tmp_path):
    client = FakeClient(
        [
            FakeCollection(
                "good",
                [
                    FakeSnapshot("good/1", {"sometimes": "present"}),
                    FakeSnapshot("good/2", {}),
                ],
            ),
            FakeCollection("broken", failure=RuntimeError("private detail")),
        ]
    )
    output = tmp_path / "partial"
    with pytest.raises(PartialExportError, match="incomplete"):
        export_evidence(client, output, source_environment="test", project_id="fake")

    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "incomplete"
    assert manifest["incomplete_collection_reads"] == [
        {"error_type": "RuntimeError", "path": "broken"}
    ]
    assert "private detail" not in (output / "manifest.json").read_text()
