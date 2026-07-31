import json
from pathlib import Path
from .manifest import canonical_json, checksum
from .schema import Bundle, CompiledExercise, ValidationIssue

BUNDLE_FILE = "bundle.json"


def write_bundle(bundle: Bundle, output: str | Path) -> Path:
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / BUNDLE_FILE
    path.write_bytes(canonical_json(bundle.as_dict()))
    return path


def load_bundle(path: str | Path) -> Bundle:
    source = Path(path)
    if source.is_dir():
        source = source / BUNDLE_FILE
    payload = json.loads(source.read_text(encoding="utf-8"))
    recorded = payload.pop("manifest_checksum", "")
    checksum_payload = {
        key: payload[key]
        for key in ("schema_version", "source_commit", "courses", "exercises", "assets", "issues")
    }
    actual = checksum(canonical_json(checksum_payload))
    if not recorded or recorded != actual:
        raise ValueError("Bundle manifest checksum does not match its content.")
    return Bundle(
        payload["schema_version"],
        payload["source_commit"],
        tuple(payload["courses"]),
        tuple(CompiledExercise(**item) for item in payload["exercises"]),
        tuple(payload["assets"]),
        tuple(ValidationIssue(**item) for item in payload["issues"]),
        recorded,
    )
