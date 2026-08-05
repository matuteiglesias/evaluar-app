import yaml
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from evaluar.content_pipeline.collection import load_manifest, validate_manifest


def _scaffold(tmp_path, slug="sample-course"):
    call_command(
        "scaffold_course", slug, "--subject", "sample", "--name", "Sample", "--root", tmp_path
    )
    return tmp_path / "collections" / slug


def test_manifest_rejects_duplicate_ids_bad_sections_missing_paths_assets_and_traversal(tmp_path):
    course = _scaffold(tmp_path)
    manifest = course / "collection.yaml"
    payload = yaml.safe_load(manifest.read_text())
    payload["exercises"][0]["section"] = "missing"
    payload["exercises"][0]["statement"]["path"] = "../escape.tex"
    payload["assets"] = [{"path": "assets/missing.png"}]
    duplicate = dict(payload["exercises"][0])
    duplicate["section"] = "missing"
    duplicate["statement"] = {"path": "exercises/missing.tex", "format": "latex"}
    payload["exercises"].append(duplicate)
    manifest.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    issues = validate_manifest(load_manifest(manifest))
    codes = {issue.code for issue in issues}
    assert {
        "manifest_unknown_section",
        "manifest_unsafe_path",
        "manifest_missing_asset",
        "manifest_duplicate_exercise",
        "manifest_duplicate_order",
        "manifest_missing_statement",
    } <= codes


def test_validate_course_collection_fails_stale_generated_index(tmp_path):
    course = _scaffold(tmp_path)
    call_command("validate_course_collection", "sample-course", "--root", tmp_path, "--write-index")
    (course / "generated" / "index.csv").write_text("manual edit\n")
    with pytest.raises(CommandError):
        call_command("validate_course_collection", "sample-course", "--root", tmp_path, "--check")
