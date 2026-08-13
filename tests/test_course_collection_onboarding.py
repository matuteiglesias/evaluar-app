import json
from io import StringIO

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError

from evaluar.content_pipeline import load_bundle
from evaluar.content_pipeline.collection import (
    generated_index_path,
    load_manifest,
    manifest_path,
    validate_manifest,
)


def test_scaffold_validate_review_index_and_bundle_course_collection(tmp_path):
    call_command(
        "scaffold_course",
        "bases-de-datos-2c2026",
        "--subject",
        "bases-de-datos",
        "--name",
        "Bases de Datos — 2C 2026",
        "--root",
        tmp_path,
    )
    course_dir = tmp_path / "collections" / "bases-de-datos-2c2026"
    manifest_file = course_dir / "collection.yaml"
    assert manifest_file.is_file()
    assert (course_dir / "private" / "solutions").is_dir()
    assert (course_dir / "README.md").is_file()

    statement = course_dir / "exercises" / "001.tex"
    statement.write_text("Relación Alumno(id, nombre). $R \\bowtie S$", encoding="utf-8")
    manifest = manifest_file.read_text(encoding="utf-8")
    manifest = manifest.replace("status: unknown", "status: instructor-authored", 1)
    manifest = manifest.replace("status: draft", "status: approved", 1)
    manifest = manifest.replace("rendering_status: pending", "rendering_status: approved", 1)
    manifest_file.write_text(manifest, encoding="utf-8")

    loaded = load_manifest(manifest_path(tmp_path, "bases-de-datos-2c2026"))
    assert not [issue for issue in validate_manifest(loaded) if issue.severity == "error"]

    call_command(
        "validate_course_collection",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--write-index",
    )
    index_path = generated_index_path(loaded)
    generated = index_path.read_text(encoding="utf-8")
    assert "generated_by" in generated
    assert "stable_id" in generated
    assert "bases-de-datos.pilot.001" in generated
    call_command(
        "validate_course_collection", "bases-de-datos-2c2026", "--root", tmp_path, "--check"
    )
    json_output = StringIO()
    call_command(
        "validate_course_collection",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--json",
        stdout=json_output,
    )
    payload = json.loads(json_output.getvalue())
    assert payload["technical_valid"] is True
    assert payload["summary"]["review_required"] >= 1
    index_path.write_text(
        generated.replace("Replace with reviewed title", "manual edit"), encoding="utf-8"
    )
    with pytest.raises(CommandError):
        call_command(
            "validate_course_collection", "bases-de-datos-2c2026", "--root", tmp_path, "--check"
        )
    index_path.write_text(generated, encoding="utf-8")

    review_dir = tmp_path / "build" / "reviews" / "bases-de-datos-2c2026"
    call_command(
        "build_course_review",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--output",
        review_dir,
    )
    html = (review_dir / "index.html").read_text(encoding="utf-8")
    inventory = json.loads((review_dir / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["schema"] == "evaluar-curation-inventory-v1"
    assert inventory["exercises"][0]["probable_learning_objective"] != "unknown"
    assert "Course collection review" in html
    assert "side-by-side" in html
    assert "Relación Alumno" in html
    review = (review_dir / "review.md").read_text(encoding="utf-8")
    assert "Rendered statement" in review
    assert "Relación Alumno" in review
    assert "Reviewer decision" in review

    bundle_dir = tmp_path / "build" / "courses" / "bases-de-datos-2c2026"
    call_command(
        "build_course_bundle",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--output",
        bundle_dir,
        "--source-commit",
        "test-commit",
    )
    bundle = load_bundle(bundle_dir)
    assert bundle.valid
    assert bundle.courses == (
        {"name": "Bases de Datos — 2C 2026", "slug": "bases-de-datos-2c2026"},
    )
    assert bundle.exercises[0].external_key == "bases-de-datos-2c2026:bases-de-datos.pilot.001"
    assert "private" not in bundle.exercises[0].source_text


def test_scaffold_refuses_invalid_or_existing_course_and_supports_dry_run(tmp_path):
    with pytest.raises(CommandError):
        call_command(
            "scaffold_course",
            "Bases de Datos 2026",
            "--subject",
            "bases-de-datos",
            "--name",
            "Bases de Datos",
            "--root",
            tmp_path,
        )
    call_command(
        "scaffold_course",
        "bases-de-datos-2c2026",
        "--subject",
        "bases-de-datos",
        "--name",
        "Bases de Datos — 2C 2026",
        "--root",
        tmp_path,
        "--dry-run",
    )
    assert not (tmp_path / "collections" / "bases-de-datos-2c2026").exists()
    call_command(
        "scaffold_course",
        "bases-de-datos-2c2026",
        "--subject",
        "bases-de-datos",
        "--name",
        "Bases de Datos — 2C 2026",
        "--root",
        tmp_path,
    )
    with pytest.raises(CommandError):
        call_command(
            "scaffold_course",
            "bases-de-datos-2c2026",
            "--subject",
            "bases-de-datos",
            "--name",
            "Bases de Datos — 2C 2026",
            "--root",
            tmp_path,
        )


def test_build_course_bundle_requires_review_approval(tmp_path):
    call_command(
        "scaffold_course",
        "bases-de-datos-2c2026",
        "--subject",
        "bases-de-datos",
        "--name",
        "Bases de Datos — 2C 2026",
        "--root",
        tmp_path,
    )
    with pytest.raises(CommandError):
        call_command(
            "build_course_bundle",
            "bases-de-datos-2c2026",
            "--root",
            tmp_path,
            "--output",
            tmp_path / "bundle",
        )


def test_add_collection_exercise_updates_manifest_statement_and_index(tmp_path):
    call_command(
        "scaffold_course",
        "bases-de-datos-2c2026",
        "--subject",
        "bases-de-datos",
        "--name",
        "Bases de Datos — 2C 2026",
        "--root",
        tmp_path,
    )
    call_command(
        "add_collection_exercise",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--stable-id",
        "bd.sql.001",
        "--title",
        "Selección y proyección",
        "--section",
        "pilot",
    )
    course_dir = tmp_path / "collections" / "bases-de-datos-2c2026"
    assert (course_dir / "exercises" / "bd.sql.001.tex").is_file()
    manifest = (course_dir / "collection.yaml").read_text(encoding="utf-8")
    assert "bd.sql.001" in manifest
    generated = (course_dir / "generated" / "index.csv").read_text(encoding="utf-8")
    assert "bd.sql.001.v1" in generated
    assert "TODO: complete instructor-approved learning objective" in manifest
    with pytest.raises(CommandError):
        call_command(
            "add_collection_exercise",
            "bases-de-datos-2c2026",
            "--root",
            tmp_path,
            "--stable-id",
            "bd.sql.001",
            "--title",
            "Duplicado",
            "--section",
            "pilot",
        )


def test_synthetic_fixture_validates_reviews_and_builds_bundle(tmp_path):
    json_output = StringIO()
    call_command(
        "validate_course_collection",
        "synthetic-db-fixture",
        "--json",
        stdout=json_output,
    )
    payload = json.loads(json_output.getvalue())
    assert payload["technical_valid"] is True
    assert payload["summary"] == {
        "error": 0,
        "informational": 0,
        "review_required": 0,
        "warning": 0,
    }
    review_dir = tmp_path / "review"
    call_command("build_course_review", "synthetic-db-fixture", "--output", review_dir)
    html = (review_dir / "index.html").read_text(encoding="utf-8")
    inventory = json.loads((review_dir / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["summary"] == payload["summary"]
    assert "Synthetic Database Fixture" in html
    assert "Synthetic SQL and schema notation" in html
    assert "Synthetic textual table" in html
    bundle_dir = tmp_path / "bundle"
    call_command(
        "build_course_bundle",
        "synthetic-db-fixture",
        "--output",
        bundle_dir,
        "--source-commit",
        "synthetic-test",
    )
    assert load_bundle(bundle_dir).valid
