"""Authoring-layer support for reviewable course collection manifests."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import html
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .bundle import compile_content
from .io import write_bundle
from .schema import Bundle, ValidationIssue

SCHEMA = "evaluar-collection-manifest-v1"
DIFFICULTIES = {"introductory", "intermediate", "advanced"}
FORMATS = {"latex", "markdown", "text"}
PROVENANCE_STATUSES = {
    "unknown",
    "instructor-authored",
    "adapted",
    "third-party",
    "requires-review",
    "synthetic-fixture",
}
REVIEW_STATUSES = {"draft", "approved", "changes_requested", "rejected"}
RENDERING_REVIEW_STATUSES = {"pending", "approved", "needs_fix", "not_required"}
TUTORING_POLICY_STATUSES = {"pending", "approved", "rejected", "not_required"}
COURSE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
GENERATED_INDEX = "generated/index.csv"
INDEX_FIELDS = (
    "id",
    "section",
    "file",
    "name",
    "info",
    "stable_id",
    "version",
    "statement_path",
    "statement_format",
    "generated_by",
    "source_manifest",
)

REQUIRED_RENDERING = {
    "prose",
    "inline-math",
    "display-math",
    "pseudocode",
    "source-code",
    "sql",
    "relational-schema",
    "table",
    "graph",
    "diagram",
    "image",
    "recurrence",
    "automata",
    "tree",
    "trace",
    "nested-list",
}


@dataclass(frozen=True)
class CollectionManifest:
    """Loaded collection manifest with its filesystem origin."""

    path: Path
    payload: dict[str, Any]

    @property
    def course_slug(self) -> str:
        return str(self.payload["course"]["slug"])

    @property
    def course_name(self) -> str:
        return str(self.payload["course"]["name"])

    @property
    def course_dir(self) -> Path:
        return self.path.parent


def safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and "\\" not in value and not path.is_absolute() and ".." not in path.parts


def manifest_path(root: str | Path, course_slug: str) -> Path:
    base = Path(root).resolve()
    candidates = (
        base / "collections" / course_slug / "collection.yaml",
        base / "exercises" / course_slug / "collection.yaml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def validate_course_slug(value: str) -> bool:
    return bool(COURSE_SLUG.fullmatch(value))


def compiler_filename(stable_id: str, version: int, source_format: str) -> str:
    suffix = {"latex": ".tex", "markdown": ".md", "text": ".txt"}[source_format]
    compiler_id = f"{stable_id}.v{version}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", compiler_id) + suffix


def stable_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:100] or fallback


def load_manifest(path: str | Path) -> CollectionManifest:
    source = Path(path).resolve()
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"collection manifest is not valid YAML: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("collection manifest must contain a mapping at top level")
    return CollectionManifest(source, payload)


def _issue(code: str, path: str, detail: str, *, severity: str = "error") -> ValidationIssue:
    return ValidationIssue(code, path, detail, severity=severity)


def _required_mapping(
    payload: dict[str, Any], key: str, issues: list[ValidationIssue], path: str
) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        issues.append(_issue("manifest_schema_invalid", path, f"{key!r} must be a mapping"))
        return {}
    return value


def validate_manifest(manifest: CollectionManifest) -> list[ValidationIssue]:
    """Validate authoring metadata without compiling exercise sources."""
    issues: list[ValidationIssue] = []
    rel_manifest = manifest.path.as_posix()
    payload = manifest.payload
    if payload.get("schema") != SCHEMA:
        issues.append(
            _issue(
                "manifest_schema_invalid",
                rel_manifest,
                f"schema must be {SCHEMA!r}",
            )
        )
    collection = _required_mapping(payload, "collection", issues, rel_manifest)
    subject = _required_mapping(payload, "subject", issues, rel_manifest)
    course = _required_mapping(payload, "course", issues, rel_manifest)
    release = _required_mapping(payload, "release", issues, rel_manifest)

    for mapping, key, label in (
        (collection, "id", "collection.id"),
        (collection, "release", "collection.release"),
        (subject, "id", "subject.id"),
        (course, "slug", "course.slug"),
        (course, "name", "course.name"),
        (course, "language", "course.language"),
    ):
        if not str(mapping.get(key) or "").strip():
            issues.append(
                _issue("manifest_required_field_missing", rel_manifest, f"{label} is required")
            )

    slug = str(course.get("slug") or "")
    if slug and not validate_course_slug(slug):
        issues.append(
            _issue(
                "manifest_invalid_course_slug",
                rel_manifest,
                "course.slug is not a safe application slug",
            )
        )
    if slug != manifest.course_dir.name:
        issues.append(
            _issue(
                "manifest_course_slug_mismatch",
                rel_manifest,
                "course.slug must match the collection directory name",
            )
        )

    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        issues.append(
            _issue(
                "manifest_required_field_missing", rel_manifest, "sections must be a non-empty list"
            )
        )
        section_by_id: dict[str, dict[str, Any]] = {}
    else:
        section_by_id = {}
        seen_orders: set[int] = set()
        for index, section in enumerate(sections):
            section_path = f"{rel_manifest}:sections[{index}]"
            if not isinstance(section, dict):
                issues.append(
                    _issue("manifest_schema_invalid", section_path, "section must be a mapping")
                )
                continue
            section_id = str(section.get("id") or "").strip()
            if not section_id:
                issues.append(
                    _issue(
                        "manifest_required_field_missing", section_path, "section.id is required"
                    )
                )
                continue
            if section_id in section_by_id:
                issues.append(
                    _issue(
                        "manifest_duplicate_section",
                        section_path,
                        f"section {section_id!r} is duplicated",
                    )
                )
            section_by_id[section_id] = section
            if not str(section.get("title") or "").strip():
                issues.append(
                    _issue(
                        "manifest_required_field_missing", section_path, "section.title is required"
                    )
                )
            order = section.get("order")
            if not isinstance(order, int):
                issues.append(
                    _issue(
                        "manifest_required_field_missing",
                        section_path,
                        "section.order integer is required",
                    )
                )
            elif order in seen_orders:
                issues.append(
                    _issue(
                        "manifest_duplicate_order",
                        section_path,
                        f"section order {order} is duplicated",
                    )
                )
            else:
                seen_orders.add(order)

    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        issues.append(
            _issue(
                "manifest_required_field_missing",
                rel_manifest,
                "exercises must be a non-empty list",
            )
        )
        exercises = []
    stable_ids: set[str] = set()
    placements: set[tuple[str, int]] = set()
    for index, exercise in enumerate(exercises):
        exercise_path = f"{rel_manifest}:exercises[{index}]"
        if not isinstance(exercise, dict):
            issues.append(
                _issue("manifest_schema_invalid", exercise_path, "exercise must be a mapping")
            )
            continue
        for field in ("stable_id", "version", "title", "section", "order", "learning_objective"):
            if exercise.get(field) in (None, "", []):
                issues.append(
                    _issue("manifest_required_field_missing", exercise_path, f"{field} is required")
                )
        stable_id = str(exercise.get("stable_id") or "").strip()
        if stable_id in stable_ids:
            issues.append(
                _issue(
                    "manifest_duplicate_exercise",
                    exercise_path,
                    f"stable_id {stable_id!r} is duplicated",
                )
            )
        stable_ids.add(stable_id)
        section_id = str(exercise.get("section") or "").strip()
        if section_id and section_id not in section_by_id:
            issues.append(
                _issue(
                    "manifest_unknown_section",
                    exercise_path,
                    f"section {section_id!r} is not declared",
                )
            )
        order = exercise.get("order")
        if not isinstance(order, int):
            issues.append(
                _issue(
                    "manifest_required_field_missing", exercise_path, "order integer is required"
                )
            )
        elif (section_id, order) in placements:
            issues.append(
                _issue(
                    "manifest_duplicate_order",
                    exercise_path,
                    f"order {order} is duplicated in section {section_id!r}",
                )
            )
        else:
            placements.add((section_id, order))
        statement = exercise.get("statement")
        if not isinstance(statement, dict):
            issues.append(
                _issue(
                    "manifest_required_field_missing",
                    exercise_path,
                    "statement mapping is required",
                )
            )
        else:
            source_path = str(statement.get("path") or "")
            source_format = str(statement.get("format") or "")
            if not safe_relative(source_path):
                issues.append(
                    _issue(
                        "manifest_unsafe_path",
                        exercise_path,
                        f"statement.path {source_path!r} is not safe",
                    )
                )
            elif not (manifest.course_dir / source_path).is_file():
                issues.append(
                    _issue(
                        "manifest_missing_statement",
                        exercise_path,
                        f"statement file {source_path!r} is missing",
                    )
                )
            if source_format not in FORMATS:
                issues.append(
                    _issue(
                        "manifest_unsupported_format",
                        exercise_path,
                        f"statement.format {source_format!r} is unsupported",
                    )
                )
        provenance = exercise.get("provenance")
        if not isinstance(provenance, dict) or not str(provenance.get("status") or "").strip():
            issues.append(
                _issue(
                    "manifest_required_field_missing",
                    exercise_path,
                    "provenance.status is required",
                )
            )
        elif provenance.get("status") not in PROVENANCE_STATUSES:
            issues.append(
                _issue(
                    "manifest_malformed_provenance",
                    exercise_path,
                    f"provenance.status {provenance.get('status')!r} is not recognized",
                )
            )
        review = exercise.get("review")
        review_status = review.get("status") if isinstance(review, dict) else None
        if not review_status:
            issues.append(
                _issue(
                    "manifest_required_field_missing", exercise_path, "review.status is required"
                )
            )
        elif review_status not in REVIEW_STATUSES:
            issues.append(
                _issue(
                    "manifest_malformed_review",
                    exercise_path,
                    f"review.status {review_status!r} is not recognized",
                )
            )
        if isinstance(review, dict):
            rendering_status = review.get("rendering_status")
            if rendering_status and rendering_status not in RENDERING_REVIEW_STATUSES:
                issues.append(
                    _issue(
                        "manifest_malformed_review",
                        exercise_path,
                        f"review.rendering_status {rendering_status!r} is not recognized",
                    )
                )
        tutoring = exercise.get("tutoring")
        if isinstance(tutoring, dict):
            policy_status = tutoring.get("policy_review_status")
            if policy_status and policy_status not in TUTORING_POLICY_STATUSES:
                issues.append(
                    _issue(
                        "manifest_malformed_review",
                        exercise_path,
                        f"tutoring.policy_review_status {policy_status!r} is not recognized",
                    )
                )
        rendering = exercise.get("rendering")
        requirements = rendering.get("requirements", []) if isinstance(rendering, dict) else []
        unknown = sorted(set(requirements) - REQUIRED_RENDERING)
        if unknown:
            issues.append(
                _issue(
                    "manifest_unknown_rendering_requirement",
                    exercise_path,
                    f"unknown rendering requirements: {', '.join(unknown)}",
                    severity="warning",
                )
            )
        difficulty = exercise.get("difficulty")
        if difficulty and difficulty not in DIFFICULTIES:
            issues.append(
                _issue(
                    "manifest_unknown_difficulty",
                    exercise_path,
                    f"unknown difficulty {difficulty!r}",
                    severity="warning",
                )
            )

    assets = payload.get("assets", [])
    if assets is None:
        assets = []
    if not isinstance(assets, list):
        issues.append(_issue("manifest_schema_invalid", rel_manifest, "assets must be a list"))
    else:
        seen_assets: set[str] = set()
        for index, asset in enumerate(assets):
            asset_path = f"{rel_manifest}:assets[{index}]"
            if not isinstance(asset, dict):
                issues.append(
                    _issue("manifest_schema_invalid", asset_path, "asset must be a mapping")
                )
                continue
            path = str(asset.get("path") or "")
            if not safe_relative(path):
                issues.append(
                    _issue("manifest_unsafe_path", asset_path, f"asset path {path!r} is not safe")
                )
                continue
            if path in seen_assets:
                issues.append(
                    _issue("manifest_duplicate_asset", asset_path, f"asset {path!r} is duplicated")
                )
            seen_assets.add(path)
            if not (manifest.course_dir / path).is_file():
                issues.append(
                    _issue("manifest_missing_asset", asset_path, f"asset file {path!r} is missing")
                )

    eligibility = release.get("publication_eligibility", {})
    if not isinstance(eligibility, dict):
        issues.append(
            _issue(
                "manifest_schema_invalid",
                rel_manifest,
                "release.publication_eligibility must be a mapping",
            )
        )
    return sorted(set(issues))


def manifest_is_publication_eligible(manifest: CollectionManifest) -> tuple[bool, list[str]]:
    """Return human-facing publication gate failures from review metadata."""
    failures: list[str] = []
    release = (
        manifest.payload.get("release", {})
        if isinstance(manifest.payload.get("release"), dict)
        else {}
    )
    gates = (
        release.get("publication_eligibility", {})
        if isinstance(release.get("publication_eligibility"), dict)
        else {}
    )
    require_instructor = gates.get("instructor_review") == "required"
    require_rendering = gates.get("rendering_review") == "required"
    for exercise in manifest.payload.get("exercises", []) or []:
        if not isinstance(exercise, dict):
            continue
        stable_id = str(exercise.get("stable_id") or "<unknown>")
        review = exercise.get("review", {}) if isinstance(exercise.get("review"), dict) else {}
        if require_instructor and review.get("status") != "approved":
            failures.append(f"{stable_id}: review.status must be 'approved'")
        if require_rendering and review.get("rendering_status") != "approved":
            failures.append(f"{stable_id}: review.rendering_status must be 'approved'")
    return not failures, failures


def compatibility_index_rows(manifest: CollectionManifest) -> list[dict[str, str]]:
    """Return deterministic compiler-compatible index rows derived from one manifest."""
    rows: list[dict[str, str]] = []
    exercises = sorted(
        manifest.payload.get("exercises", []) or [],
        key=lambda item: (
            str(item.get("section") or ""),
            int(item.get("order") or 0),
            str(item.get("stable_id") or ""),
        ),
    )
    for exercise in exercises:
        stable_id = str(exercise["stable_id"])
        version = int(exercise.get("version") or 1)
        compiler_id = f"{stable_id}.v{version}"
        source_format = str(exercise["statement"]["format"])
        rows.append(
            {
                "id": compiler_id,
                "section": str(exercise["section"]),
                "file": compiler_filename(stable_id, version, source_format),
                "name": str(exercise["title"]),
                "info": str(exercise["learning_objective"]),
                "stable_id": stable_id,
                "version": str(version),
                "statement_path": str(exercise["statement"]["path"]),
                "statement_format": source_format,
                "generated_by": SCHEMA,
                "source_manifest": manifest.path.name,
            }
        )
    return rows


def compatibility_index_bytes(manifest: CollectionManifest) -> bytes:
    from io import StringIO

    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=INDEX_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(compatibility_index_rows(manifest))
    return output.getvalue().encode("utf-8")


def generated_index_path(manifest: CollectionManifest) -> Path:
    return manifest.course_dir / GENERATED_INDEX


def write_compatibility_index(manifest: CollectionManifest) -> Path:
    path = generated_index_path(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compatibility_index_bytes(manifest))
    return path


def compatibility_index_current(manifest: CollectionManifest) -> bool:
    path = generated_index_path(manifest)
    return path.is_file() and path.read_bytes() == compatibility_index_bytes(manifest)


def materialize_compiler_root(manifest: CollectionManifest, output_root: str | Path) -> Path:
    """Create a temporary/compiler-compatible content root for one manifest course."""
    root = Path(output_root)
    course_dir = root / "exercises" / manifest.course_slug
    course_dir.mkdir(parents=True, exist_ok=True)
    rows = compatibility_index_rows(manifest)
    for row in rows:
        shutil.copyfile(manifest.course_dir / row["statement_path"], course_dir / row["file"])
    with (course_dir / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("id", "section", "file", "name", "info"), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(
            {key: row[key] for key in ("id", "section", "file", "name", "info")} for row in rows
        )
    for asset in manifest.payload.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        source = str(asset.get("path") or "")
        if safe_relative(source) and (manifest.course_dir / source).is_file():
            target = root / "assets" / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(manifest.course_dir / source, target)
    return root


def compile_manifest_course(
    manifest: CollectionManifest, *, source_commit: str = "unknown"
) -> Bundle:
    with tempfile.TemporaryDirectory() as directory:
        root = materialize_compiler_root(manifest, directory)
        return compile_content(root, source_commit=source_commit)


def write_manifest_bundle(
    manifest: CollectionManifest, output: str | Path, *, source_commit: str
) -> Path:
    bundle = compile_manifest_course(manifest, source_commit=source_commit)
    if not bundle.valid:
        details = "; ".join(
            f"{item.code}: {item.path}: {item.detail}"
            for item in bundle.issues
            if item.severity == "error"
        )
        raise ValueError(f"Content validation failed; bundle was not written. {details}")
    return write_bundle(bundle, output)


def governance_findings(manifest: CollectionManifest) -> list[ValidationIssue]:
    """Return non-compiler governance findings for instructor review."""
    findings: list[ValidationIssue] = []
    for index, exercise in enumerate(manifest.payload.get("exercises", []) or []):
        if not isinstance(exercise, dict):
            continue
        path = f"{manifest.path.as_posix()}:exercises[{index}]"
        stable_id = str(exercise.get("stable_id") or "<unknown>")
        provenance = (
            exercise.get("provenance", {}) if isinstance(exercise.get("provenance"), dict) else {}
        )
        provenance_status = str(provenance.get("status") or "").strip()
        permission = provenance.get("license_or_permission")
        if provenance_status in {"", "unknown"}:
            findings.append(
                ValidationIssue(
                    "governance_unknown_provenance",
                    path,
                    f"{stable_id}: provenance.status is unknown",
                    severity="review_required",
                )
            )
        if permission in (None, "", "unknown"):
            findings.append(
                ValidationIssue(
                    "governance_missing_permission",
                    path,
                    f"{stable_id}: provenance.license_or_permission is missing",
                    severity="review_required",
                )
            )
        review = exercise.get("review", {}) if isinstance(exercise.get("review"), dict) else {}
        if review.get("status") != "approved":
            findings.append(
                ValidationIssue(
                    "governance_missing_instructor_review",
                    path,
                    f"{stable_id}: review.status is not approved",
                    severity="review_required",
                )
            )
        if review.get("rendering_status") != "approved":
            findings.append(
                ValidationIssue(
                    "governance_missing_rendering_review",
                    path,
                    f"{stable_id}: review.rendering_status is not approved",
                    severity="review_required",
                )
            )
        tutoring = (
            exercise.get("tutoring", {}) if isinstance(exercise.get("tutoring"), dict) else {}
        )
        if tutoring.get("eligible") is True and tutoring.get("policy_review_status") != "approved":
            findings.append(
                ValidationIssue(
                    "governance_tutoring_policy_pending",
                    path,
                    f"{stable_id}: tutoring is eligible without approved tutoring policy review",
                    severity="review_required",
                )
            )
    return sorted(set(findings))


def validation_summary(issues: list[ValidationIssue]) -> dict[str, int]:
    severities = ("error", "warning", "review_required", "informational")
    return {severity: sum(item.severity == severity for item in issues) for severity in severities}


def findings_by_compiler_id(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in issues:
        for match in re.findall(r"([A-Za-z0-9_.-]+\.v\d+)", issue.path + " " + issue.detail):
            grouped.setdefault(match, []).append(issue)
    return grouped


def collection_inventory(
    manifest: CollectionManifest, bundle: Bundle | None = None
) -> dict[str, Any]:
    """Return canonical review inventory compatible with evidence inventory semantics."""
    manifest_issues = validate_manifest(manifest)
    governance = governance_findings(manifest)
    compiler_issues = list(bundle.issues) if bundle else []
    all_issues = sorted(set(manifest_issues + compiler_issues + governance))
    compiled_by_id = {item.exercise_id: item for item in bundle.exercises} if bundle else {}
    exercises = []
    for exercise in sorted(
        manifest.payload.get("exercises", []) or [],
        key=lambda item: (str(item.get("section")), int(item.get("order", 0))),
    ):
        stable_id = str(exercise.get("stable_id"))
        version = int(exercise.get("version") or 1)
        compiler_id = f"{stable_id}.v{version}"
        compiled = compiled_by_id.get(compiler_id)
        statement = (
            exercise.get("statement", {}) if isinstance(exercise.get("statement"), dict) else {}
        )
        rendering = (
            exercise.get("rendering", {}) if isinstance(exercise.get("rendering"), dict) else {}
        )
        provenance = (
            exercise.get("provenance", {}) if isinstance(exercise.get("provenance"), dict) else {}
        )
        review = exercise.get("review", {}) if isinstance(exercise.get("review"), dict) else {}
        tutoring = (
            exercise.get("tutoring", {}) if isinstance(exercise.get("tutoring"), dict) else {}
        )
        exercise_issues = [
            issue
            for issue in all_issues
            if stable_id in issue.detail or compiler_id in issue.path or compiler_id in issue.detail
        ]
        exercises.append(
            {
                "course": manifest.course_slug,
                "section": str(exercise.get("section", "unknown")),
                "order": exercise.get("order"),
                "external_id": compiler_id,
                "stable_id": stable_id,
                "version": version,
                "filename": compiler_filename(
                    stable_id, version, str(statement.get("format", "latex"))
                ),
                "title": str(exercise.get("title", "")),
                "generated_slug": stable_slug(
                    str(exercise.get("title", "")), f"exercise-{stable_id}"
                ),
                "source_format": str(statement.get("format", "unknown")),
                "checksum": compiled.source_checksum if compiled else "unknown",
                "rendering_constructs": list(rendering.get("requirements", []) or [])
                or ["unknown"],
                "references": "unknown",
                "assets": manifest.payload.get("assets", []) or [],
                "validation_findings": [item.__dict__ for item in exercise_issues],
                "probable_learning_objective": exercise.get("learning_objective", "unknown"),
                "prerequisites": exercise.get("prerequisites", "unknown"),
                "difficulty_if_known": exercise.get("difficulty", "unknown"),
                "estimated_time_minutes": exercise.get("estimated_time_minutes", "unknown"),
                "provenance_status": provenance.get("status", "unknown"),
                "review_status": review.get("status", "requires instructor review"),
                "rendering_review_status": review.get(
                    "rendering_status", "requires instructor review"
                ),
                "tutoring_eligible": tutoring.get("eligible", False),
            }
        )
    return {
        "schema": "evaluar-curation-inventory-v1",
        "source": "collection-manifest",
        "manifest": manifest.path.as_posix(),
        "course": manifest.course_slug,
        "summary": validation_summary(all_issues),
        "issues": [item.__dict__ for item in all_issues],
        "exercises": exercises,
    }


def review_html(manifest: CollectionManifest, bundle: Bundle | None = None) -> str:
    inventory = collection_inventory(manifest, bundle)
    all_issues = [ValidationIssue(**item) for item in inventory["issues"]]
    summary = inventory["summary"]
    compiled_by_id = {item.exercise_id: item for item in bundle.exercises} if bundle else {}
    section_titles = {
        str(section.get("id")): str(section.get("title"))
        for section in manifest.payload.get("sections", []) or []
        if isinstance(section, dict)
    }
    rows = []
    exercises = sorted(
        manifest.payload.get("exercises", []) or [],
        key=lambda item: (str(item.get("section")), int(item.get("order", 0))),
    )
    for exercise in exercises:
        stable_id = str(exercise.get("stable_id"))
        version = int(exercise.get("version") or 1)
        compiler_id = f"{stable_id}.v{version}"
        compiled = compiled_by_id.get(compiler_id)
        statement_path = str(exercise.get("statement", {}).get("path", ""))
        source_path = manifest.course_dir / statement_path
        source = source_path.read_text(encoding="utf-8") if source_path.is_file() else ""
        issue_items = [
            issue
            for issue in all_issues
            if stable_id in issue.detail or compiler_id in issue.path or compiler_id in issue.detail
        ]
        issue_html = (
            "".join(
                f"<li class='severity-{html.escape(issue.severity)}'><strong>{html.escape(issue.severity)}</strong> "
                f"<code>{html.escape(issue.code)}</code>: {html.escape(issue.detail)}</li>"
                for issue in issue_items
            )
            or "<li class='severity-informational'>No exercise-specific findings.</li>"
        )
        rendering = (
            exercise.get("rendering", {}) if isinstance(exercise.get("rendering"), dict) else {}
        )
        provenance = (
            exercise.get("provenance", {}) if isinstance(exercise.get("provenance"), dict) else {}
        )
        review = exercise.get("review", {}) if isinstance(exercise.get("review"), dict) else {}
        tutoring = (
            exercise.get("tutoring", {}) if isinstance(exercise.get("tutoring"), dict) else {}
        )
        rows.append(
            f"""<section class="exercise">
<h3>{html.escape(str(exercise.get("title", stable_id)))}</h3>
<dl>
  <dt>Stable ID</dt><dd><code>{html.escape(stable_id)}</code></dd>
  <dt>Version</dt><dd>{version}</dd>
  <dt>Section/order</dt><dd>{html.escape(str(exercise.get("section")))} / {html.escape(str(exercise.get("order")))}</dd>
  <dt>Checksum</dt><dd><code>{html.escape(compiled.source_checksum if compiled else "not compiled")}</code></dd>
  <dt>Learning objective</dt><dd>{html.escape(str(exercise.get("learning_objective", "unknown")))}</dd>
  <dt>Prerequisites</dt><dd>{html.escape(", ".join(str(item) for item in exercise.get("prerequisites", []) or []) or "unknown")}</dd>
  <dt>Difficulty/time</dt><dd>{html.escape(str(exercise.get("difficulty", "unknown")))} / {html.escape(str(exercise.get("estimated_time_minutes", "unknown")))} minutes</dd>
  <dt>Rendering requirements</dt><dd>{html.escape(", ".join(str(item) for item in rendering.get("requirements", []) or []) or "unknown")}</dd>
  <dt>Assets</dt><dd>{html.escape(", ".join(str(item.get("path")) for item in manifest.payload.get("assets", []) or [] if isinstance(item, dict)) or "none declared")}</dd>
  <dt>Provenance</dt><dd><code>{html.escape(str(provenance.get("status", "unknown")))}</code>; permission: <code>{html.escape(str(provenance.get("license_or_permission", "unknown")))}</code></dd>
  <dt>Review</dt><dd>instructor: <code>{html.escape(str(review.get("status", "unknown")))}</code>; rendering: <code>{html.escape(str(review.get("rendering_status", "unknown")))}</code></dd>
  <dt>Tutoring</dt><dd>eligible: <code>{html.escape(str(tutoring.get("eligible", False)))}</code>; policy: <code>{html.escape(str(tutoring.get("policy_review_status", "unknown")))}</code></dd>
</dl>
<ul class="findings">{issue_html}</ul>
<div class="side-by-side">
  <div><h4>Rendered student statement</h4><div class="rendered">{compiled.rendered_html if compiled is not None else "<p>Not compiled.</p>"}</div></div>
  <div><h4>Original source</h4><pre>{html.escape(source)}</pre></div>
</div>
<p class="decision">Reviewer decision: ☐ approve ☐ needs technical fix ☐ needs pedagogical fix ☐ do not publish</p>
</section>"""
        )
    owners = (
        manifest.payload.get("governance", {}).get("owners", [])
        if isinstance(manifest.payload.get("governance"), dict)
        else []
    )
    reviewers = (
        manifest.payload.get("governance", {}).get("reviewers", [])
        if isinstance(manifest.payload.get("governance"), dict)
        else []
    )
    sections = "".join(
        f"<li><code>{html.escape(section_id)}</code>: {html.escape(title)}</li>"
        for section_id, title in sorted(section_titles.items())
    )
    issue_list = (
        "".join(
            f"<li class='severity-{html.escape(issue.severity)}'><strong>{html.escape(issue.severity)}</strong> "
            f"<code>{html.escape(issue.code)}</code> at <code>{html.escape(issue.path)}</code>: {html.escape(issue.detail)}</li>"
            for issue in all_issues
        )
        or "<li>No findings.</li>"
    )
    release = (
        manifest.payload.get("collection", {})
        if isinstance(manifest.payload.get("collection"), dict)
        else {}
    )
    course = (
        manifest.payload.get("course", {})
        if isinstance(manifest.payload.get("course"), dict)
        else {}
    )
    subject = (
        manifest.payload.get("subject", {})
        if isinstance(manifest.payload.get("subject"), dict)
        else {}
    )
    eligible, failures = manifest_is_publication_eligible(manifest)
    failure_list = (
        "".join(f"<li>{html.escape(failure)}</li>" for failure in failures)
        or "<li>No review-gate failures.</li>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Course collection review: {html.escape(manifest.course_name)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; }}
code, pre {{ background: #f6f8fa; }}
pre {{ padding: 1rem; overflow: auto; white-space: pre-wrap; }}
.side-by-side {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1rem; }}
.exercise {{ border-top: 1px solid #ddd; padding-top: 1rem; margin-top: 2rem; }}
.rendered {{ border: 1px solid #ddd; padding: 1rem; }}
.severity-error {{ color: #9b1c1c; }}
.severity-warning {{ color: #92400e; }}
.severity-review_required {{ color: #1d4ed8; }}
.severity-informational {{ color: #374151; }}
dl {{ display: grid; grid-template-columns: 14rem minmax(0, 1fr); gap: .25rem 1rem; }}
dt {{ font-weight: 700; }}
</style>
</head>
<body>
<h1>Course collection review: {html.escape(manifest.course_name)}</h1>
<section>
<h2>Collection overview</h2>
<dl>
  <dt>Course</dt><dd><code>{html.escape(str(course.get("slug", "unknown")))}</code> — {html.escape(str(course.get("name", "unknown")))}</dd>
  <dt>Subject</dt><dd><code>{html.escape(str(subject.get("id", "unknown")))}</code></dd>
  <dt>Offering</dt><dd>{html.escape(str(course.get("offering", "unknown")))}</dd>
  <dt>Release</dt><dd>{html.escape(str(release.get("release", "unknown")))}</dd>
  <dt>Owners</dt><dd>{html.escape(str(owners))}</dd>
  <dt>Reviewers</dt><dd>{html.escape(str(reviewers))}</dd>
  <dt>Exercise count</dt><dd>{len(exercises)}</dd>
  <dt>Validation summary</dt><dd>{html.escape(str(summary))}</dd>
  <dt>Publication eligible</dt><dd>{"yes" if eligible else "no"}</dd>
</dl>
<h3>Sections</h3><ul>{sections}</ul>
<h3>Publication gate failures</h3><ul>{failure_list}</ul>
<h3>All validation findings</h3><ul>{issue_list}</ul>
</section>
{"".join(rows)}
</body>
</html>
"""


def review_markdown(manifest: CollectionManifest, bundle: Bundle | None = None) -> str:
    issues = validate_manifest(manifest)
    compiled_by_id = {}
    if bundle:
        for item in bundle.exercises:
            compiled_by_id[item.exercise_id] = item
    lines = [
        f"# Course collection review: {manifest.course_name}",
        "",
        f"Manifest: `{manifest.path.as_posix()}`",
        f"Course slug: `{manifest.course_slug}`",
        f"Subject: `{manifest.payload.get('subject', {}).get('id', 'unknown')}`",
        f"Language: `{manifest.payload.get('course', {}).get('language', 'unknown')}`",
        "",
        "## Publication gates",
        "",
    ]
    eligible, failures = manifest_is_publication_eligible(manifest)
    lines.append(f"Publication eligible by review metadata: **{'yes' if eligible else 'no'}**")
    if failures:
        lines.extend(["", "Gate failures:", *[f"- {failure}" for failure in failures]])
    if issues:
        lines.extend(["", "## Manifest findings", ""])
        for issue in issues:
            lines.append(
                f"- **{issue.severity}** `{issue.code}` at `{issue.path}` — {issue.detail}"
            )
    if bundle and bundle.issues:
        lines.extend(["", "## Compiler findings", ""])
        for issue in bundle.issues:
            lines.append(
                f"- **{issue.severity}** `{issue.code}` at `{issue.path}` — {issue.detail}"
            )
    lines.extend(["", "## Exercises", ""])
    for exercise in sorted(
        manifest.payload.get("exercises", []) or [],
        key=lambda item: (str(item.get("section")), int(item.get("order", 0))),
    ):
        stable_id = str(exercise.get("stable_id"))
        version = int(exercise.get("version") or 1)
        compiler_id = f"{stable_id}.v{version}"
        statement = manifest.course_dir / exercise["statement"]["path"]
        source = statement.read_text(encoding="utf-8") if statement.is_file() else ""
        compiled_markdown = compiled_by_id.get(compiler_id)
        rendered = (
            compiled_markdown.rendered_html if compiled_markdown is not None else "not compiled"
        )
        lines.extend(
            [
                f"### {html.escape(str(exercise.get('title', stable_id)))}",
                "",
                f"- Stable ID: `{stable_id}`",
                f"- Version: `{version}`",
                f"- Section: `{exercise.get('section', 'unknown')}`",
                f"- Order: `{exercise.get('order', 'unknown')}`",
                f"- Statement: `{exercise.get('statement', {}).get('path', 'unknown')}`",
                f"- Learning objective: {exercise.get('learning_objective', 'unknown')}",
                f"- Provenance status: `{exercise.get('provenance', {}).get('status', 'unknown')}`",
                f"- Review status: `{exercise.get('review', {}).get('status', 'unknown')}`",
                f"- Rendering status: `{exercise.get('review', {}).get('rendering_status', 'unknown')}`",
                "",
                "#### Rendered statement",
                "",
                rendered,
                "",
                "#### Source",
                "",
                "```text",
                source.rstrip(),
                "```",
                "",
                "Reviewer decision: `[ ] approve` `[ ] needs technical fix` `[ ] needs pedagogical fix` `[ ] do not publish`",
                "",
                "Notes:",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
