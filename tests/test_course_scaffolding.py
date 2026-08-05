import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_scaffold_overwrite_refusal_and_dry_run(tmp_path):
    call_command(
        "scaffold_course",
        "sample-course",
        "--subject",
        "sample",
        "--name",
        "Sample",
        "--root",
        tmp_path,
        "--dry-run",
    )
    assert not (tmp_path / "collections" / "sample-course").exists()
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
    with pytest.raises(CommandError):
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


def test_add_collection_exercise_uses_stable_identity_despite_title_change(tmp_path):
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
    call_command(
        "add_collection_exercise",
        "sample-course",
        "--root",
        tmp_path,
        "--stable-id",
        "sample.001",
        "--title",
        "Original",
        "--section",
        "pilot",
    )
    index = tmp_path / "collections" / "sample-course" / "generated" / "index.csv"
    before = index.read_text()
    manifest = tmp_path / "collections" / "sample-course" / "collection.yaml"
    manifest.write_text(manifest.read_text().replace("title: Original", "title: Retitled"))
    call_command("validate_course_collection", "sample-course", "--root", tmp_path, "--write-index")
    after = index.read_text()
    assert "sample.001.v1" in before and "sample.001.v1" in after
    assert "Retitled" in after


def test_two_focused_courses_can_reuse_local_numeric_filename(tmp_path):
    for slug in ("sample-one", "sample-two"):
        call_command(
            "scaffold_course", slug, "--subject", "sample", "--name", slug, "--root", tmp_path
        )
        call_command("validate_course_collection", slug, "--root", tmp_path)
