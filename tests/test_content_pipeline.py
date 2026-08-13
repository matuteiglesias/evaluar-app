import csv
import json
from pathlib import Path
from evaluar.content_pipeline import bundle_bytes, compile_content
from evaluar.content_pipeline.sanitization import sanitize_html


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


def test_database_theory_rendering_integrity_and_table_rejection(tmp_path):
    long_spanish = "Descripción en español: relación Alumno(id, nombre). " * 100
    first = write_course(
        tmp_path,
        "db-one",
        [
            {"id": "101", "section": "SQL", "file": "101.tex", "name": "Consulta"},
            {"id": "102", "section": "Álgebra", "file": "102.tex", "name": "Relaciones"},
        ],
    )
    second = write_course(
        tmp_path,
        "db-two",
        [{"id": "101", "section": "Otra", "file": "101.tex", "name": "Reutilizado"}],
    )
    sql = r"SELECT alumno_id, COUNT(*) FROM Inscripcion GROUP BY alumno_id; $R \bowtie S$"
    (first / "101.tex").write_text(sql, encoding="utf-8")
    (first / "102.tex").write_text(long_spanish, encoding="utf-8")
    (second / "101.tex").write_text("Clave foránea y teoría de dependencias.", encoding="utf-8")
    bundle = compile_content(tmp_path)

    assert bundle.valid
    rendered = {item.external_key: item.rendered_html for item in bundle.exercises}
    assert "SELECT alumno_id, COUNT(*)" in rendered["db-one:101"]
    assert "$R \\bowtie S$" in rendered["db-one:101"]
    assert "Descripción en español" in rendered["db-one:102"]
    assert len(rendered["db-one:102"]) > 4_000
    assert {item.external_key for item in bundle.exercises} >= {"db-one:101", "db-two:101"}
    assert {item.section for item in bundle.exercises} >= {"SQL", "Álgebra", "Otra"}

    (first / "101.tex").write_text("<table><tr><td>silenciosa</td></tr></table>", encoding="utf-8")
    rejected = compile_content(tmp_path)
    issue = next(item for item in rejected.issues if item.code == "unsupported_authored_html_table")
    assert issue.severity == "error"
    assert not rejected.valid


def test_latex_images_are_inlined_from_validated_assets(tmp_path):
    directory = write_course(
        tmp_path,
        "db-images",
        [{"id": "201", "section": "DER", "file": "201.tex", "name": "Diagrama"}],
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    (directory / "201.tex").write_text(
        "Observe el siguiente DER.\n\n\\includegraphics{diagram.png}\n\nExplique el modelo.",
        encoding="utf-8",
    )

    bundle = compile_content(tmp_path)

    assert bundle.valid
    rendered = bundle.exercises[0].rendered_html
    assert '<img class="exercise-figure" src="data:image/png;base64,' in rendered
    assert "\\includegraphics" not in rendered
    assert not [issue for issue in bundle.issues if issue.code == "orphaned_asset"]
    assert "<img" not in sanitize_html('<img src="https://example.invalid/tracker.png" alt="x">')
