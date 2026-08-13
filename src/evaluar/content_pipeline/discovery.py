"""Discover course indexes and source files without framework dependencies."""

from __future__ import annotations
import csv
import re
import unicodedata
from pathlib import Path, PurePosixPath
from .schema import ExerciseSource, ValidationIssue

REQUIRED_COLUMNS = {"id", "section", "file", "name"}
SOURCE_SUFFIXES = {".tex": "latex", ".md": "markdown", ".txt": "text"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def stable_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:100] or fallback


def safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and "\\" not in value and not path.is_absolute() and ".." not in path.parts


def discover(
    root: Path,
) -> tuple[list[dict[str, str]], list[ExerciseSource], set[str], list[ValidationIssue]]:
    root = root.resolve()
    courses, exercises, issues = [], [], []
    exercises_root = root / "exercises"
    if not exercises_root.is_dir():
        return (
            [],
            [],
            set(),
            [
                ValidationIssue(
                    "missing_exercises_root", "exercises", "exercises directory is missing"
                )
            ],
        )
    for directory in sorted(
        (p for p in exercises_root.iterdir() if p.is_dir()), key=lambda p: p.name
    ):
        index = directory / "index.csv"
        courses.append({"slug": directory.name, "name": directory.name})
        if not index.is_file():
            issues.append(
                ValidationIssue(
                    "missing_index", index.relative_to(root).as_posix(), "index.csv is missing"
                )
            )
            continue
        seen_slugs: set[str] = set()
        try:
            with index.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, strict=True)
                missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
                if missing:
                    issues.append(
                        ValidationIssue(
                            "schema_invalid",
                            index.relative_to(root).as_posix(),
                            f"missing columns: {', '.join(sorted(missing))}",
                        )
                    )
                    continue
                for line, row in enumerate(reader, 2):
                    filename = row.get("file", "")
                    row_path = f"{index.relative_to(root).as_posix()}:{line}"
                    if not safe_relative(filename) or PurePosixPath(
                        filename
                    ).parent != PurePosixPath("."):
                        issues.append(
                            ValidationIssue(
                                "unsafe_source_path", row_path, f"invalid source path {filename!r}"
                            )
                        )
                        continue
                    source = directory / filename
                    if not source.is_file():
                        issues.append(
                            ValidationIssue(
                                "missing_source_file",
                                row_path,
                                f"source file {filename!r} is missing",
                            )
                        )
                        continue
                    source_format = SOURCE_SUFFIXES.get(source.suffix.lower())
                    if not source_format:
                        issues.append(
                            ValidationIssue(
                                "unsupported_source_format",
                                row_path,
                                f"unsupported source format {source.suffix!r}",
                            )
                        )
                        continue
                    try:
                        text = source.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        issues.append(
                            ValidationIssue(
                                "invalid_utf8",
                                source.relative_to(root).as_posix(),
                                "source is not UTF-8",
                            )
                        )
                        continue
                    identifier = (row.get("id") or "").strip()
                    stable_identifier = (row.get("stable_id") or identifier).strip()
                    title = row.get("name", "").strip()
                    slug = stable_slug(title, f"exercise-{identifier}")
                    if slug in seen_slugs:
                        slug = f"{slug}-{identifier}"[:100]
                    seen_slugs.add(slug)
                    exercises.append(
                        ExerciseSource(
                            directory.name,
                            identifier,
                            f"{directory.name}:{stable_identifier}",
                            slug,
                            title,
                            row.get("section", "").strip(),
                            source_format,
                            source.relative_to(root).as_posix(),
                            text,
                        )
                    )
        except (csv.Error, UnicodeDecodeError) as error:
            issues.append(
                ValidationIssue("schema_invalid", index.relative_to(root).as_posix(), str(error))
            )
    asset_roots = (root / name for name in ("assets", "tikzpics", "images", "img"))
    assets = {
        path.relative_to(root).as_posix()
        for asset_root in asset_roots
        if asset_root.is_dir()
        for path in asset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
    }
    return courses, exercises, assets, issues
