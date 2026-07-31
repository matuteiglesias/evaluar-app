import csv
import json
from pathlib import Path
from content_pipeline import bundle_bytes, compile_content


def write_course(root: Path, course: str, rows):
    directory = root / "exercises" / course
    directory.mkdir(parents=True)
    with (directory / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "section", "file", "name"))
        writer.writeheader()
        writer.writerows(rows)
    return directory


def test_bundle_is_deterministic_and_sanitized(tmp_path):
    directory = write_course(
        tmp_path, "algebra", [{"id": "one", "section": "A", "file": "one.tex", "name": "One"}]
    )
    (directory / "one.tex").write_text("Solve <script>alert(1)</script> $x$", encoding="utf-8")
    first = compile_content(tmp_path, source_commit="abc")
    second = compile_content(tmp_path, source_commit="abc")
    assert bundle_bytes(first) == bundle_bytes(second)
    assert "<script>" not in first.exercises[0].rendered_html
    assert json.loads(bundle_bytes(first))["manifest_checksum"] == first.manifest_checksum


def test_formal_duplicate_latex_reference_and_asset_validation(tmp_path):
    one = write_course(
        tmp_path,
        "one",
        [
            {"id": "101", "section": "A", "file": "101.tex", "name": "One"},
            {"id": "101", "section": "B", "file": "101.tex", "name": "Duplicate"},
        ],
    )
    two = write_course(
        tmp_path, "two", [{"id": "101", "section": "A", "file": "101.tex", "name": "Two"}]
    )
    (one / "101.tex").write_text(
        r"\\input{bad} \\ref{missing} \\includegraphics{absent.png}", encoding="utf-8"
    )
    (two / "101.tex").write_text("safe", encoding="utf-8")
    bundle = compile_content(tmp_path)
    codes = {issue.code for issue in bundle.issues}
    assert {
        "duplicate_exercise_id",
        "unsupported_latex",
        "invalid_reference",
        "unknown_asset",
    } <= codes
    assert not bundle.valid
