import csv
import re
from pathlib import Path

from flask import current_app


COURSE_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class ExerciseNotFound(LookupError):
    pass


def _root():
    return Path(current_app.config["EXERCISES_ROOT"]).resolve(strict=True)


def _course_dir(course):
    if not isinstance(course, str) or not COURSE_SLUG.fullmatch(course):
        raise ExerciseNotFound
    root = _root()
    path = (root / course).resolve()
    if path.parent != root or not path.is_dir():
        raise ExerciseNotFound
    return path


def exercises_for_course(course):
    course_dir = _course_dir(course)
    index_path = (course_dir / "index.csv").resolve()
    if index_path.parent != course_dir or not index_path.is_file():
        raise ExerciseNotFound
    with index_path.open(encoding="utf-8", newline="") as index_file:
        rows = list(csv.DictReader(index_file))
    if not rows or not {"id", "file"}.issubset(rows[0]):
        raise ExerciseNotFound
    return rows


def available_courses():
    root = _root()
    courses = []
    for path in root.iterdir():
        try:
            exercises_for_course(path.name)
        except ExerciseNotFound:
            continue
        courses.append(path.name)
    return sorted(courses)


def exercise_file(course, *, filename=None, exercise_id=None):
    rows = exercises_for_course(course)
    key, expected = ("file", filename) if filename is not None else ("id", str(exercise_id))
    row = next((item for item in rows if item.get(key) == expected), None)
    if row is None:
        raise ExerciseNotFound

    indexed_filename = row["file"]
    # Separators, absolute paths and dot segments are forbidden even if a poisoned
    # index ever contains them.
    if Path(indexed_filename).name != indexed_filename or indexed_filename in {".", ".."}:
        raise ExerciseNotFound
    course_dir = _course_dir(course)
    path = (course_dir / indexed_filename).resolve()
    if path.parent != course_dir or not path.is_file():
        raise ExerciseNotFound
    return row, path


def read_exercise(course, *, filename=None, exercise_id=None):
    row, path = exercise_file(course, filename=filename, exercise_id=exercise_id)
    return row, path.read_text(encoding="utf-8")
