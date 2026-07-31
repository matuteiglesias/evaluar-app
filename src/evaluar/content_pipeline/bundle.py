"""Public deterministic compiler entry point."""

from __future__ import annotations
import html
from pathlib import Path
from .discovery import discover
from .latex import render_latex, validate_latex
from .manifest import canonical_json, checksum
from .sanitization import sanitize_html
from .schema import BUNDLE_SCHEMA_VERSION, Bundle, CompiledExercise, ValidationIssue
from .validation import validate


def compile_content(content_root: str | Path, *, source_commit: str = "unknown") -> Bundle:
    root = Path(content_root)
    courses, sources, known_assets, issues = discover(root)
    issues.extend(validate(courses, sources))
    compiled, used_assets = [], set()
    for source in sorted(
        sources, key=lambda item: (item.course_slug, item.exercise_id, item.source_path)
    ):
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
            for asset in sorted(references):
                candidates = {asset, f"assets/{asset}", f"tikzpics/{asset}"}
                matches = candidates & known_assets
                if not matches:
                    issues.append(
                        ValidationIssue(
                            "unknown_asset", source.source_path, f"unknown asset {asset!r}"
                        )
                    )
                used_assets.update(matches)
            rendered = render_latex(source.source_text)
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
    payload = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "source_commit": source_commit,
        "courses": course_records,
        "exercises": [item.__dict__ for item in compiled],
        "assets": assets,
        "issues": [item.__dict__ for item in issues],
    }
    return Bundle(
        BUNDLE_SCHEMA_VERSION,
        source_commit,
        course_records,
        tuple(compiled),
        assets,
        tuple(issues),
        checksum(canonical_json(payload)),
    )


def bundle_bytes(bundle: Bundle) -> bytes:
    return canonical_json(bundle.as_dict())
