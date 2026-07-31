"""Deterministically inventory and validate the legacy educational corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


VERSION = 1
REQUIRED_COLUMNS = ("id", "section", "file", "name", "info")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
ASSET_DIRS = ("tikzpics", "assets", "images", "img")
UNSAFE_TEX = re.compile(
    r"\\(?:input|include|includegraphics|write|openout|read|catcode|csname|usepackage|"
    r"href|url|class|style|cssId|htmlClass|htmlId|htmlStyle|unicode)\b",
    re.IGNORECASE,
)
HTML_TAG = re.compile(
    r"<\s*/?\s*([A-Za-z][A-Za-z0-9-]*)"
    r"(?:\s+[A-Za-z_:][\w:.-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))*\s*/?>"
)
IMAGE_HTML = re.compile(r"<img\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
LATEX_IMAGE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
SAFE_EMBEDDED_TAGS = {"br", "code", "div", "em", "i", "img", "li", "ol", "p", "pre", "strong", "ul"}
COURSE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_relative(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _content_commit(root: Path) -> str:
    candidates = ["exercises", "tikzpics"]
    candidates.extend(
        path.name
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".txt", ".tex"}
    )
    try:
        return (
            subprocess.run(
                ["git", "log", "-1", "--format=%H", "--", *sorted(candidates)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            or "uncommitted"
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_inventory(
    root: Path, *, source_commit: str | None = None
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    root = root.resolve()
    commit = source_commit or _content_commit(root)
    issues: list[dict[str, str]] = []

    def issue(
        code: str,
        path: str,
        detail: str,
        *,
        course: str = "",
        key: str = "",
        severity: str = "error",
    ) -> None:
        issues.append(
            {
                "severity": severity,
                "code": code,
                "course": course,
                "global_key": key,
                "path": path,
                "detail": detail,
            }
        )

    asset_paths: dict[str, Path] = {}
    for dirname in ASSET_DIRS:
        directory = root / dirname
        if directory.is_dir():
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                    asset_paths[_relative(path, root)] = path
    docs_assets = root / "docs" / "assets"
    if docs_assets.is_dir():
        for path in docs_assets.rglob("*"):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                asset_paths[_relative(path, root)] = path

    referenced_assets: dict[str, set[str]] = {path: set() for path in asset_paths}
    entries: list[dict[str, Any]] = []
    courses: list[dict[str, Any]] = []
    all_ids: dict[str, list[str]] = {}
    content_hashes: dict[str, list[str]] = {}
    exercises_root = root / "exercises"
    course_dirs = (
        sorted(
            (path for path in exercises_root.iterdir() if path.is_dir()), key=lambda path: path.name
        )
        if exercises_root.is_dir()
        else []
    )

    for course_dir in course_dirs:
        course = course_dir.name
        index_path = course_dir / "index.csv"
        tex_paths = sorted(course_dir.glob("*.tex"), key=lambda path: path.name)
        rows: list[dict[str, str]] = []
        course_issue_start = len(issues)
        if not COURSE_SLUG.fullmatch(course):
            issue(
                "unsafe_course_slug",
                _relative(course_dir, root),
                f"course directory name {course!r} is not a safe application course slug",
                course=course,
            )
        if not index_path.is_file():
            issue(
                "missing_index",
                _relative(course_dir, root),
                "course directory has no index.csv",
                course=course,
            )
        else:
            try:
                text = index_path.read_text(encoding="utf-8")
                reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
                if reader.fieldnames is None:
                    issue(
                        "malformed_csv",
                        _relative(index_path, root),
                        "CSV has no header",
                        course=course,
                    )
                else:
                    missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames))
                    if missing:
                        issue(
                            "missing_columns",
                            _relative(index_path, root),
                            f"missing required columns: {','.join(missing)}",
                            course=course,
                        )
                    rows = [
                        {str(k): str(v or "") for k, v in row.items() if k is not None}
                        for row in reader
                    ]
            except UnicodeDecodeError:
                issue(
                    "invalid_utf8",
                    _relative(index_path, root),
                    "index.csv is not valid UTF-8",
                    course=course,
                )
            except csv.Error as error:
                issue(
                    "malformed_csv",
                    _relative(index_path, root),
                    f"CSV parse error: {error}",
                    course=course,
                )

        ids: dict[str, int] = {}
        filenames: dict[str, int] = {}
        indexed_safe_files: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            exercise_id = row.get("id", "")
            filename = row.get("file", "")
            key = f"{course}:{exercise_id}"
            row_path = f"{_relative(index_path, root)}:{row_number}"
            ids[exercise_id] = ids.get(exercise_id, 0) + 1
            filenames[filename] = filenames.get(filename, 0) + 1
            all_ids.setdefault(exercise_id, []).append(key)
            row_issues_start = len(issues)
            if ids[exercise_id] > 1:
                issue(
                    "duplicate_id",
                    row_path,
                    f"exercise ID {exercise_id!r} is duplicated in course",
                    course=course,
                    key=key,
                )
            if filenames[filename] > 1:
                issue(
                    "duplicate_filename",
                    row_path,
                    f"filename {filename!r} is duplicated in course",
                    course=course,
                    key=key,
                )
            safe_file = _safe_relative(filename) and PurePosixPath(
                filename
            ).parent == PurePosixPath(".")
            if not safe_file:
                issue(
                    "unsafe_path",
                    row_path,
                    f"unsafe or non-local exercise path {filename!r}",
                    course=course,
                    key=key,
                )
            else:
                indexed_safe_files.add(filename)
            if filename != f"{exercise_id}.tex":
                issue(
                    "filename_id_mismatch",
                    row_path,
                    f"expected filename {exercise_id}.tex, found {filename!r}",
                    course=course,
                    key=key,
                )
            metadata_course = row.get("course", "")
            if metadata_course and metadata_course != course:
                issue(
                    "course_metadata_mismatch",
                    row_path,
                    f"metadata course {metadata_course!r} does not match directory {course!r}",
                    course=course,
                    key=key,
                )

            content_path = course_dir / filename if safe_file else None
            content_hash = None
            asset_hashes: list[dict[str, str]] = []
            if content_path is None or not content_path.is_file():
                issue(
                    "missing_content_file",
                    row_path,
                    f"indexed content file {filename!r} is missing",
                    course=course,
                    key=key,
                )
            else:
                raw = content_path.read_bytes()
                content_hash = _hash_bytes(raw)
                content_hashes.setdefault(content_hash, []).append(key)
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    content = ""
                    issue(
                        "invalid_utf8",
                        _relative(content_path, root),
                        "exercise content is not valid UTF-8",
                        course=course,
                        key=key,
                    )
                if not content.strip():
                    issue(
                        "empty_content",
                        _relative(content_path, root),
                        "exercise content is empty",
                        course=course,
                        key=key,
                    )
                tags = sorted({match.group(1).lower() for match in HTML_TAG.finditer(content)})
                unsupported_tags = sorted(set(tags) - SAFE_EMBEDDED_TAGS)
                if unsupported_tags:
                    issue(
                        "unsupported_html",
                        _relative(content_path, root),
                        f"embedded HTML tags not supported by renderer: {','.join(unsupported_tags)}",
                        course=course,
                        key=key,
                        severity="warning",
                    )
                suspicious = sorted(set(match.group(0) for match in UNSAFE_TEX.finditer(content)))
                if suspicious:
                    issue(
                        "suspicious_latex",
                        _relative(content_path, root),
                        f"commands require review: {','.join(suspicious)}",
                        course=course,
                        key=key,
                        severity="warning",
                    )

                references = list(LATEX_IMAGE.findall(content)) + list(IMAGE_HTML.findall(content))
                if "% FIGURA" in content:
                    references.append(f"tikzpics/{exercise_id}.png")
                for reference in sorted(set(references)):
                    if not _safe_relative(reference):
                        issue(
                            "unsafe_asset_path",
                            _relative(content_path, root),
                            f"unsafe or absolute asset reference {reference!r}",
                            course=course,
                            key=key,
                        )
                        continue
                    normalized = reference
                    candidate = root / normalized
                    if not candidate.suffix and (root / f"{normalized}.png").is_file():
                        normalized = f"{normalized}.png"
                        candidate = root / normalized
                    if not candidate.is_file():
                        issue(
                            "missing_image",
                            _relative(content_path, root),
                            f"referenced image {reference!r} is missing",
                            course=course,
                            key=key,
                        )
                    else:
                        digest = _hash_bytes(candidate.read_bytes())
                        asset_hashes.append({"path": normalized, "sha256": digest})
                        referenced_assets.setdefault(normalized, set()).add(key)

            row_canonical = {column: row.get(column, "") for column in sorted(row)}
            entries.append(
                {
                    "global_exercise_key": key,
                    "course_slug": course,
                    "exercise_id": exercise_id,
                    "metadata": row_canonical,
                    "index_path": _relative(index_path, root),
                    "content_path": _relative(content_path, root)
                    if content_path and content_path.is_file()
                    else None,
                    "index_row_sha256": _hash_bytes(_canonical_json(row_canonical)),
                    "content_sha256": content_hash,
                    "referenced_assets": sorted(asset_hashes, key=lambda item: item["path"]),
                    "validation_status": "invalid"
                    if any(
                        item["global_key"] == key and item["severity"] == "error"
                        for item in issues[row_issues_start:]
                    )
                    else ("warning" if len(issues) > row_issues_start else "valid"),
                    "source_git_commit": commit,
                }
            )

        for tex_path in tex_paths:
            if tex_path.name not in indexed_safe_files:
                issue(
                    "orphan_content_file",
                    _relative(tex_path, root),
                    ".tex file has no index row",
                    course=course,
                )
                try:
                    orphan_content = tex_path.read_text(encoding="utf-8")
                    if not orphan_content.strip():
                        issue(
                            "empty_content",
                            _relative(tex_path, root),
                            "unindexed exercise content is empty",
                            course=course,
                        )
                except UnicodeDecodeError:
                    issue(
                        "invalid_utf8",
                        _relative(tex_path, root),
                        "unindexed exercise content is not valid UTF-8",
                        course=course,
                    )
        courses.append(
            {
                "course_slug": course,
                "index_path": _relative(index_path, root) if index_path.exists() else None,
                "index_rows": len(rows),
                "tex_files": len(tex_paths),
                "validation_status": "invalid"
                if any(item["severity"] == "error" for item in issues[course_issue_start:])
                else ("warning" if len(issues) > course_issue_start else "valid"),
            }
        )

    for exercise_id, keys in sorted(all_ids.items()):
        unique_courses = sorted({key.split(":", 1)[0] for key in keys})
        if exercise_id and len(unique_courses) > 1:
            issue(
                "cross_course_repeated_id",
                "exercises",
                f"numeric/string ID {exercise_id!r} occurs as global keys {','.join(sorted(keys))}",
                key=",".join(sorted(keys)),
                severity="warning",
            )
    for digest, keys in sorted(content_hashes.items()):
        if len(keys) > 1:
            issue(
                "duplicate_content_hash",
                "exercises",
                f"SHA-256 {digest} is shared by {','.join(sorted(keys))}",
                key=",".join(sorted(keys)),
                severity="warning",
            )

    assets: list[dict[str, str]] = []
    for relative, path in sorted(asset_paths.items()):
        refs = sorted(referenced_assets.get(relative, set()))
        content_asset = relative.startswith(tuple(f"{name}/" for name in ASSET_DIRS))
        status = "referenced" if refs else "orphan"
        if content_asset and not refs:
            issue(
                "orphan_image",
                relative,
                "content image is not referenced by a canonical indexed exercise",
                severity="warning",
            )
        assets.append(
            {
                "path": relative,
                "sha256": _hash_bytes(path.read_bytes()),
                "referenced_by": ";".join(refs),
                "status": status,
                "authority": "authoritative-when-referenced" if refs else "non-authoritative",
            }
        )

    legacy_files = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix.lower() in {".csv", ".txt", ".tex"}:
            raw = path.read_bytes()
            encoding = "utf-8"
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                encoding = "invalid-utf8"
                issue("invalid_utf8", path.name, "legacy root-level content is not valid UTF-8")
            legacy_files.append(
                {
                    "path": path.name,
                    "sha256": _hash_bytes(raw),
                    "encoding": encoding,
                    "authority": "unresolved-legacy",
                }
            )

    generated_doc_trees = []
    for candidate in (root / "docs", root / "htmlcov"):
        if candidate.is_dir() and any(candidate.rglob("*.html")):
            generated_doc_trees.append(
                {
                    "path": _relative(candidate, root),
                    "html_files": sum(1 for _ in candidate.rglob("*.html")),
                    "authority": "generated-non-authoritative",
                }
            )

    issues.sort(key=lambda item: (item["path"], item["code"], item["global_key"], item["detail"]))
    status_by_key: dict[str, str] = {}
    for finding in issues:
        for finding_key in finding["global_key"].split(","):
            if not finding_key:
                continue
            current = status_by_key.get(finding_key, "valid")
            if finding["severity"] == "error":
                status_by_key[finding_key] = "invalid"
            elif current != "invalid":
                status_by_key[finding_key] = "warning"
    for entry in entries:
        entry["source_git_commit"] = commit
        entry["validation_status"] = status_by_key.get(
            entry["global_exercise_key"], entry["validation_status"]
        )
    course_status = {item["course_slug"]: item["validation_status"] for item in courses}
    for entry in entries:
        if entry["validation_status"] == "invalid":
            course_status[entry["course_slug"]] = "invalid"
        elif (
            entry["validation_status"] == "warning"
            and course_status[entry["course_slug"]] == "valid"
        ):
            course_status[entry["course_slug"]] = "warning"
    for course_entry in courses:
        course_entry["validation_status"] = course_status[course_entry["course_slug"]]
    manifest = {
        "schema_version": VERSION,
        "source_git_commit": commit,
        "courses": sorted(courses, key=lambda item: item["course_slug"]),
        "exercises": sorted(
            entries, key=lambda item: (item["global_exercise_key"], item["index_row_sha256"])
        ),
        "legacy_root_files": legacy_files,
        "generated_documentation_trees": generated_doc_trees,
        "summary": {
            "courses": len(courses),
            "indexed_exercises": len(entries),
            "content_assets": len(assets),
            "issues": len(issues),
            "errors": sum(item["severity"] == "error" for item in issues),
            "warnings": sum(item["severity"] == "warning" for item in issues),
        },
    }
    return manifest, issues, assets


def _csv_bytes(rows: list[dict[str, str]], fields: tuple[str, ...]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def render_outputs(root: Path, *, source_commit: str | None = None) -> dict[Path, bytes]:
    manifest, issues, assets = build_inventory(root, source_commit=source_commit)
    return {
        root / "artifacts/legacy/content-manifest.v1.json": _canonical_json(manifest),
        root / "artifacts/legacy/content-issues.csv": _csv_bytes(
            issues, ("severity", "code", "course", "global_key", "path", "detail")
        ),
        root / "artifacts/legacy/content-assets.csv": _csv_bytes(
            assets, ("path", "sha256", "referenced_by", "status", "authority")
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--check", action="store_true", help="verify committed outputs byte-for-byte"
    )
    parser.add_argument(
        "--fail-on-issues", action="store_true", help="return nonzero when validation issues exist"
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    outputs = render_outputs(root)
    changed = []
    for path, expected in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                changed.append(_relative(path, root))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    manifest = json.loads(outputs[root / "artifacts/legacy/content-manifest.v1.json"])
    if changed:
        print(f"inventory mismatch: {', '.join(changed)}", file=sys.stderr)
        return 1
    if args.fail_on_issues and manifest["summary"]["issues"]:
        print(f"validation found {manifest['summary']['issues']} issue(s)", file=sys.stderr)
        return 1
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
