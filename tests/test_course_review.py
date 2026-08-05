import json
from io import StringIO

from django.core.management import call_command


def test_review_packet_and_synthetic_fixture_publication_eligibility(tmp_path):
    out = StringIO()
    call_command("validate_course_collection", "synthetic-db-fixture", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["technical_valid"] is True
    assert payload["summary"]["review_required"] == 0
    review_dir = tmp_path / "review"
    call_command("build_course_review", "synthetic-db-fixture", "--output", review_dir)
    assert (review_dir / "index.html").is_file()
    assert (
        json.loads((review_dir / "inventory.json").read_text())["schema"]
        == "evaluar-curation-inventory-v1"
    )


def test_unsupported_html_table_finding_is_visible_and_escaped(tmp_path):
    call_command(
        "scaffold_course",
        "sample-course",
        "--subject",
        "sample",
        "--name",
        "Sample",
        "--root",
        tmp_path,
    )
    course = tmp_path / "collections" / "sample-course"
    (course / "exercises" / "001.tex").write_text(
        "<table><tr><td>x</td></tr></table><script>alert(1)</script>"
    )
    manifest = course / "collection.yaml"
    manifest.write_text(
        manifest.read_text()
        .replace("status: draft", "status: approved")
        .replace("rendering_status: pending", "rendering_status: approved")
    )
    review_dir = tmp_path / "review"
    call_command("build_course_review", "sample-course", "--root", tmp_path, "--output", review_dir)
    html = (review_dir / "index.html").read_text()
    assert "unsupported_authored_html_table" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_same_exercise_can_appear_in_two_offerings_with_provenance(tmp_path):
    for slug in ("sample-2026a", "sample-2026b"):
        call_command(
            "scaffold_course", slug, "--subject", "sample", "--name", slug, "--root", tmp_path
        )
        manifest = tmp_path / "collections" / slug / "collection.yaml"
        text = manifest.read_text().replace("sample.pilot.001", "sample.shared.001")
        text = text.replace("status: unknown", "status: synthetic-fixture")
        text = text.replace(
            "license_or_permission: null", "license_or_permission: synthetic-fixture-only"
        )
        manifest.write_text(text)
        call_command("validate_course_collection", slug, "--root", tmp_path)
