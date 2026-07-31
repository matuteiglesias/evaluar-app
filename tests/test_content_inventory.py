import csv
import json
from pathlib import Path

from scripts.content_inventory import build_inventory, render_outputs


HEADER = ["id", "section", "file", "name", "info"]


def write_index(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


def row(identifier, filename=None):
    return {
        "id": str(identifier),
        "section": "1",
        "file": filename or f"{identifier}.tex",
        "name": f"Exercise {identifier}",
        "info": "Safe metadata",
    }


def issue_codes(issues):
    return {item["code"] for item in issues}


def test_valid_course_and_referenced_asset(tmp_path):
    write_index(tmp_path / "exercises/valid/index.csv", [row(101)])
    (tmp_path / "exercises/valid/101.tex").write_text("Question\n% FIGURA\n", encoding="utf-8")
    (tmp_path / "tikzpics").mkdir()
    (tmp_path / "tikzpics/101.png").write_bytes(b"png")

    manifest, issues, assets = build_inventory(tmp_path, source_commit="abc")

    assert not issues
    assert manifest["exercises"][0]["global_exercise_key"] == "valid:101"
    assert manifest["exercises"][0]["validation_status"] == "valid"
    assert assets[0]["status"] == "referenced"


def test_duplicate_missing_orphan_and_cross_course_ids(tmp_path):
    write_index(
        tmp_path / "exercises/one/index.csv",
        [row(101), row(101, "missing.tex")],
    )
    (tmp_path / "exercises/one/101.tex").write_text("first", encoding="utf-8")
    (tmp_path / "exercises/one/orphan.tex").write_text("orphan", encoding="utf-8")
    write_index(tmp_path / "exercises/two/index.csv", [row(101)])
    (tmp_path / "exercises/two/101.tex").write_text("second", encoding="utf-8")

    _, issues, _ = build_inventory(tmp_path, source_commit="abc")

    assert {
        "duplicate_id",
        "missing_content_file",
        "orphan_content_file",
        "cross_course_repeated_id",
    } <= issue_codes(issues)
    cross_course = next(item for item in issues if item["code"] == "cross_course_repeated_id")
    assert "one:101" in cross_course["detail"]
    assert "two:101" in cross_course["detail"]


def test_malformed_index_missing_image_and_path_escape(tmp_path):
    malformed = tmp_path / "exercises/bad/index.csv"
    malformed.parent.mkdir(parents=True)
    malformed.write_text(
        'id,section,file,name,info\n1,1,"unterminated,name,info\n', encoding="utf-8"
    )
    write_index(tmp_path / "exercises/refs/index.csv", [row(202, "../escape.tex"), row(203)])
    (tmp_path / "exercises/refs/203.tex").write_text("% FIGURA", encoding="utf-8")

    _, issues, _ = build_inventory(tmp_path, source_commit="abc")

    assert {"malformed_csv", "unsafe_path", "missing_image"} <= issue_codes(issues)


def test_missing_index_and_orphan_image(tmp_path):
    course = tmp_path / "exercises/no_index"
    course.mkdir(parents=True)
    (course / "1.tex").write_text("content", encoding="utf-8")
    (tmp_path / "tikzpics").mkdir()
    (tmp_path / "tikzpics/unused.png").write_bytes(b"image")

    _, issues, assets = build_inventory(tmp_path, source_commit="abc")

    assert {"missing_index", "orphan_content_file", "orphan_image"} <= issue_codes(issues)
    assert assets[0]["status"] == "orphan"


def test_repeated_generation_is_byte_identical(tmp_path):
    write_index(tmp_path / "exercises/course/index.csv", [row(1)])
    (tmp_path / "exercises/course/1.tex").write_text("content", encoding="utf-8")

    first = render_outputs(tmp_path, source_commit="fixed")
    second = render_outputs(tmp_path, source_commit="fixed")

    assert first == second
    manifest_path = tmp_path / "artifacts/legacy/content-manifest.v1.json"
    payload = json.loads(first[manifest_path])
    assert "timestamp" not in payload
