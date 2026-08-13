import pytest
from django.core.management import call_command

from evaluar.courses.models import ContentPublication, Course, Exercise, ExerciseVersion

pytestmark = pytest.mark.django_db


def _approve_scaffolded_manifest(manifest_file):
    manifest = manifest_file.read_text(encoding="utf-8")
    manifest = manifest.replace("status: unknown", "status: instructor-authored", 1)
    manifest = manifest.replace("status: draft", "status: approved", 1)
    manifest = manifest.replace("rendering_status: pending", "rendering_status: approved", 1)
    manifest_file.write_text(manifest, encoding="utf-8")


def test_manifest_versions_publish_under_one_stable_exercise(tmp_path):
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
    statement = course_dir / "exercises" / "001.tex"
    _approve_scaffolded_manifest(manifest_file)

    statement.write_text("Primera versión del ejercicio.", encoding="utf-8")
    first_bundle = tmp_path / "build" / "v1"
    call_command(
        "build_course_bundle",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--output",
        first_bundle,
        "--source-commit",
        "commit-v1",
    )
    call_command("publish_content", first_bundle)

    course = Course.objects.get(slug="bases-de-datos-2c2026")
    exercise = Exercise.objects.get(course=course)
    assert course.name == "Bases de Datos — 2C 2026"
    assert exercise.external_key == "bases-de-datos-2c2026:bases-de-datos.pilot.001"
    assert list(exercise.versions.values_list("version_number", flat=True)) == [1]

    manifest = manifest_file.read_text(encoding="utf-8")
    manifest_file.write_text(manifest.replace("version: 1", "version: 2", 1), encoding="utf-8")
    statement.write_text("Segunda versión, con una aclaración.", encoding="utf-8")
    second_bundle = tmp_path / "build" / "v2"
    call_command(
        "build_course_bundle",
        "bases-de-datos-2c2026",
        "--root",
        tmp_path,
        "--output",
        second_bundle,
        "--source-commit",
        "commit-v2",
    )
    call_command("publish_content", second_bundle)

    assert Exercise.objects.filter(course=course).count() == 1
    assert ExerciseVersion.objects.filter(exercise=exercise).count() == 2
    assert list(exercise.versions.values_list("version_number", flat=True)) == [1, 2]
    assert ContentPublication.objects.filter(course=course).count() == 2
    assert ContentPublication.objects.filter(course=course, status="published").count() == 1
