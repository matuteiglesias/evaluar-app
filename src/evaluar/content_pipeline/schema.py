"""Typed, Django-independent content bundle schema."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

BUNDLE_SCHEMA_VERSION = 1


@dataclass(frozen=True, order=True)
class ValidationIssue:
    code: str
    path: str
    detail: str
    severity: str = "error"


@dataclass(frozen=True)
class ExerciseSource:
    course_slug: str
    exercise_id: str
    external_key: str
    slug: str
    title: str
    section: str
    source_format: str
    source_path: str
    source_text: str


@dataclass(frozen=True)
class CompiledExercise:
    course_slug: str
    exercise_id: str
    external_key: str
    slug: str
    title: str
    section: str
    source_format: str
    source_text: str
    source_checksum: str
    rendered_html: str


@dataclass(frozen=True)
class Bundle:
    schema_version: int
    source_commit: str
    courses: tuple[dict[str, Any], ...]
    exercises: tuple[CompiledExercise, ...]
    assets: tuple[dict[str, str], ...]
    issues: tuple[ValidationIssue, ...]
    manifest_checksum: str

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
