"""Public deterministic compiler entry point."""

from __future__ import annotations
import base64
import html
import re
from pathlib import Path
from .discovery import discover
from .latex import render_latex, validate_latex
from .manifest import canonical_json, checksum
from .sanitization import sanitize_html
from .schema import BUNDLE_SCHEMA_VERSION, Bundle, CompiledExercise, ValidationIssue
from .validation import validate

ASSET_ROOTS = ("assets", "tikzpics", "images", "img")
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def _resolve_asset_reference(reference: str, known_assets: set[str]) -> str | None:
    candidates = [reference, *(f"{root}/{reference}" for root in ASSET_ROOTS)]
    for candidate in candidates:
        if candidate in known_assets:
            return candidate
    suffix = f"/{reference}"
    matches = sorted(asset for asset in known_assets if asset.endswith(suffix))
    return matches[0] if len(matches) == 1 else None


def _asset_data_uri(root: Path, asset_path: str) -> str:
    mime = IMAGE_MIME_TYPES[Path(asset_path).suffix.lower()]
    encoded = base64.b64encode((root / asset_path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _checksum_payload(
    *,
    schema_version: int,
    source_commit: str,
    courses,
    exercises,
    assets,
    issues,
) -> str:
    payload = {
        "schema_version": schema_version,
        "source_commit": source_commit,
        "courses": courses,
        "exercises": [item.__dict__ for item in exercises],
        "assets": assets,
        "issues": [item.__dict__ for item in issues],
    }
    return checksum(canonical_json(payload))


def with_course_names(bundle: Bundle, course_names: dict[str, str]) -> Bundle:
    """Return an equivalent bundle with authoritative display names and a fresh checksum."""
    courses = tuple(
        {**course, "name": course_names.get(course["slug"], course["name"])}
        for course in bundle.courses
    )
    manifest_checksum = _checksum_payload(
        schema_version=bundle.schema_version,
        source_commit=bundle.source_commit,
        courses=courses,
        exercises=bundle.exercises,
        assets=bundle.assets,
        issues=bundle.issues,
    )
    return Bundle(
        bundle.schema_version,
        bundle.source_commit,
        courses,
        bundle.exercises,
        bundle.assets,
        bundle.issues,
        manifest_checksum,
    )


def compile_content(content_root: str | Path, *, source_commit: str = "unknown") -> Bundle:
    root = Path(content_root)
    courses, sources, known_assets, issues = discover(root)
    issues.extend(validate(courses, sources))
    compiled, used_assets = [], set()
    for source in sorted(
        sources, key=lambda item: (item.course_slug, item.exercise_id, item.source_path)
    ):
        if re.search(r"<\s*/?\s*table\b", source.source_text, re.IGNORECASE):
            issues.append(
                ValidationIssue(
                    "unsupported_authored_html_table",
                    source.source_path,
                    "authored HTML tables are rejected; use textual/LaTeX table notation",
                )
            )
        if source.source_format == "latex":
            unsupported, missing_refs, references = validate_latex(source.source_text)
            for construct in unsupported:
                issues.append(
                    ValidationIssue(
                        "unsupported_latex",
                        source.source_path,
                        f"unsupported construct {construct}",
                    )
                )
            for reference in sorted(missing_refs):
                issues.append(
                    ValidationIssue(
                        "invalid_reference",
                        source.source_path,
                        f"unknown label {reference!r}",
                        severity="warning",
                    )
                )
            asset_sources: dict[str, str] = {}
            for reference in sorted(references):
                matched = _resolve_asset_reference(reference, known_assets)
                if matched is None:
                    issues.append(
                        ValidationIssue(
                            "unknown_asset", source.source_path, f"unknown asset {reference!r}"
                        )
                    )
                    continue
                used_assets.add(matched)
                asset_sources[reference] = _asset_data_uri(root, matched)
            if "% FIGURA" in source.source_text:
                figure = f"tikzpics/{source.exercise_id}.png"
                if figure not in known_assets:
                    issues.append(
                        ValidationIssue(
                            "unknown_asset",
                            source.source_path,
                            f"missing legacy figure {figure!r}",
                        )
                    )
                else:
                    used_assets.add(figure)
            rendered = render_latex(source.source_text, asset_sources)
        else:
            # Markdown is deliberately not interpreted as HTML in this production slice.
            rendered = "<p>" + html.escape(source.source_text).replace("\n", "<br>\n") + "</p>"
        compiled.append(
            CompiledExercise(
                source.course_slug,
                source.exercise_id,
                source.external_key,
                source.slug,
                source.title,
                source.section,
                source.source_format,
                source.source_text,
                checksum(source.source_text),
                sanitize_html(rendered),
            )
        )
    for asset in sorted(known_assets - used_assets):
        issues.append(
            ValidationIssue("orphaned_asset", asset, "asset is not referenced", severity="warning")
        )
    issues = sorted(set(issues))
    assets = tuple(
        {"path": asset, "checksum": checksum((root / asset).read_bytes())}
        for asset in sorted(known_assets)
    )
    course_records = tuple(sorted(courses, key=lambda item: item["slug"]))
    manifest_checksum = _checksum_payload(
        schema_version=BUNDLE_SCHEMA_VERSION,
        source_commit=source_commit,
        courses=course_records,
        exercises=compiled,
        assets=assets,
        issues=issues,
    )
    return Bundle(
        BUNDLE_SCHEMA_VERSION,
        source_commit,
        course_records,
        tuple(compiled),
        assets,
        tuple(issues),
        manifest_checksum,
    )


def bundle_bytes(bundle: Bundle) -> bytes:
    return canonical_json(bundle.as_dict())
