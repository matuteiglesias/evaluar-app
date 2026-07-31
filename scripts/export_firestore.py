"""Read-only, deterministic Firestore evidence exporter.

The output contains sensitive raw records and belongs only under the Git-ignored
``var/legacy/firestore`` tree.  This tool never issues a write operation.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from datetime import date, datetime, time
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any


TOOL_VERSION = "1.0.0"


class PartialExportError(RuntimeError):
    """Raised after an incomplete export's manifest has been finalized."""


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def serialize_value(value: Any) -> Any:
    """Convert Firestore/Python values to explicit, loss-aware JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {"__type__": "float", "value": "NaN"}
        if math.isinf(value):
            return {"__type__": "float", "value": "Infinity" if value > 0 else "-Infinity"}
        return value
    if isinstance(value, datetime):
        return {"__type__": "timestamp", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__type__": "time", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "__type__": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, dict):
        return {
            str(key): serialize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]

    # Firestore DocumentReference exposes a stable full path.
    path = getattr(value, "path", None)
    if isinstance(path, str):
        return {"__type__": "reference", "path": path}
    # google.cloud.firestore_v1.GeoPoint exposes latitude/longitude.
    latitude = getattr(value, "latitude", None)
    longitude = getattr(value, "longitude", None)
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        return {"__type__": "geopoint", "latitude": latitude, "longitude": longitude}
    return {
        "__type__": "unknown",
        "python_type": f"{type(value).__module__}.{type(value).__qualname__}",
    }


def _source_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collection_path(collection: Any) -> str:
    path = getattr(collection, "path", None)
    if path:
        return path
    parent = getattr(collection, "parent", None)
    return f"{parent.path}/{collection.id}" if parent else collection.id


def export_evidence(
    client: Any,
    output_dir: Path,
    *,
    source_environment: str,
    project_id: str,
    list_only: bool = False,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Enumerate every reachable collection/document without mutating Firestore."""
    documents: list[dict[str, Any]] = []
    collection_counts: Counter[str] = Counter()
    discovered: set[str] = set()
    failures: dict[str, str] = {}
    try:
        pending = sorted(client.collections(), key=_collection_path)
    except Exception as error:
        pending = []
        failures["<top-level collections>"] = type(error).__name__

    while pending:
        collection = pending.pop(0)
        collection_path = _collection_path(collection)
        if collection_path in discovered:
            continue
        discovered.add(collection_path)
        collection_counts.setdefault(collection_path, 0)
        try:
            snapshots = sorted(collection.stream(), key=lambda item: item.reference.path)
        except Exception as error:  # collection errors must be recorded before failing
            failures[collection_path] = type(error).__name__
            continue
        collection_counts[collection_path] = len(snapshots)
        for snapshot in snapshots:
            document_path = snapshot.reference.path
            documents.append(
                {
                    "collection_path": collection_path,
                    "document_path": document_path,
                    "fields": serialize_value(snapshot.to_dict() or {}),
                }
            )
            try:
                children = sorted(snapshot.reference.collections(), key=_collection_path)
            except Exception as error:
                failures[f"{document_path}/<subcollections>"] = type(error).__name__
                continue
            pending.extend(children)
            pending.sort(key=_collection_path)

    manifest: dict[str, Any] = {
        "format": "evaluar-firestore-evidence-v1",
        "tool_version": TOOL_VERSION,
        "project_id": project_id,
        "source_environment": source_environment,
        "source_commit": source_commit or _source_commit(),
        "status": "incomplete" if failures else "complete",
        "list_only": list_only,
        "collection_counts": dict(sorted(collection_counts.items())),
        "incomplete_collection_reads": [
            {"path": path, "error_type": failures[path]} for path in sorted(failures)
        ],
        "files": [],
    }
    if not list_only:
        output_dir.mkdir(parents=True, exist_ok=False)
        document_file = output_dir / "documents.ndjson"
        with document_file.open("wb") as handle:
            for document in sorted(documents, key=lambda item: item["document_path"]):
                handle.write(_json_bytes(document))
        manifest["files"] = [
            {
                "path": document_file.name,
                "sha256": _sha256(document_file),
                "records": len(documents),
            }
        ]
        manifest_file = output_dir / "manifest.json"
        manifest_file.write_bytes(_json_bytes(manifest))
        # A detached hash avoids the self-referential problem of hashing the manifest within itself.
        (output_dir / "manifest.sha256").write_text(
            f"{_sha256(manifest_file)}  manifest.json\n", encoding="ascii"
        )
    if failures:
        raise PartialExportError(
            f"Firestore export incomplete: {len(failures)} read operation(s) failed"
        )
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-environment", required=True, help="Operator-supplied environment label"
    )
    parser.add_argument(
        "--project-id", help="Firestore project (defaults to credential/ADC project)"
    )
    parser.add_argument("--output", type=Path, help="New directory below var/legacy/firestore")
    parser.add_argument(
        "--list-only", action="store_true", help="List collection paths/counts; write no files"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.list_only and args.output is None:
        print("error: --output is required unless --list-only is used", file=sys.stderr)
        return 2
    if args.output and Path("var/legacy/firestore") not in args.output.parents:
        print("error: --output must be below var/legacy/firestore/", file=sys.stderr)
        return 2

    import firebase_admin
    from firebase_admin import firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": args.project_id} if args.project_id else None
        )
    client = firestore.client()
    project_id = args.project_id or getattr(client, "project", "unknown")
    try:
        manifest = export_evidence(
            client,
            args.output or Path("."),
            source_environment=args.source_environment,
            project_id=project_id,
            list_only=args.list_only,
        )
    except PartialExportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.list_only:
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(f"Export complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
