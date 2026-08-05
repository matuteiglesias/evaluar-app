# Adding a course collection

This guide is for instructors and technical content maintainers. It explains how to create a reviewed course collection without reading deployment docs, editing Django models, or touching database rows.

## Five-minute quick start

```bash
uv run python manage.py scaffold_course sample-course \
  --subject sample-subject \
  --name "Sample Course" \
  --language es-AR

uv run python manage.py add_collection_exercise sample-course \
  --stable-id sample.intro.001 \
  --title "Synthetic starter exercise" \
  --section pilot
```

Edit the public statement under `collections/sample-course/exercises/` and complete the `TODO` fields in `collections/sample-course/collection.yaml`.

```bash
uv run python manage.py validate_course_collection sample-course --write-index
uv run python manage.py validate_course_collection sample-course --check
uv run python manage.py validate_course_collection sample-course --json
uv run python manage.py build_course_review sample-course \
  --output build/reviews/sample-course
```

Open `build/reviews/sample-course/index.html` in a browser. After instructor and rendering review, mark reviewed exercises as approved:

```yaml
review:
  status: approved
  rendering_status: approved
```

Then build the existing deterministic publication bundle:

```bash
uv run python manage.py build_course_bundle sample-course \
  --output build/courses/sample-course \
  --source-commit "$(git rev-parse HEAD)"
```

Publish only when the course owner is ready:

```bash
uv run python manage.py publish_content build/courses/sample-course
```

## Workspace layout

`scaffold_course` creates this structure:

```text
collections/<course>/
├── collection.yaml
├── exercises/
├── assets/
├── generated/index.csv
├── private/
│   ├── solutions/
│   ├── rubrics/
│   └── tutoring-guidance/
└── README.md
```

Only public statements, public assets, `collection.yaml`, and generated compatibility metadata participate in the publication bundle. Files under `private/` are instructor-only and must not be referenced by public statements.

## Obtain authoritative source material

Before adding real exercises, obtain the instructor-approved source statements, section names, intended order, permissions, and any required public assets. Do not copy textbook, exam, website, or third-party material into a public collection unless the course owner records permission in the manifest.

## Stable IDs and versions

Use stable IDs for pedagogical identity, not filenames or title slugs. A title may change without changing the stable ID. If the statement meaning changes substantially, increment the exercise version or add a new explicitly related exercise; do not overwrite history silently.

## Minimum metadata

For a private pilot, each exercise must record at least:

- `stable_id`
- `version`
- `title`
- `section`
- `order`
- `statement.path`
- `statement.format`
- `learning_objective`
- `provenance.status`
- `review.status`

Unknowns must remain explicit. Use `unknown` or leave review fields in `draft`/`pending` until an instructor resolves them; do not invent learning intent, provenance, permissions, or review decisions.

## Validation and generated index

`validate_course_collection` validates only the selected collection. It does not validate the legacy TDA corpus and is not contaminated by unrelated legacy warnings.

- `--write-index` regenerates `collections/<course>/generated/index.csv` from `collection.yaml`.
- `--check` fails if the generated index is missing, stale, or manually edited.
- `--json` emits machine-readable findings with `error`, `warning`, `review_required`, and `informational` severities.

Technical errors block bundle creation. Governance gaps such as unknown provenance, missing permission, missing instructor review, missing rendering review, or tutoring eligibility without tutoring-policy approval are reported as review-required findings unless publication eligibility is explicitly checked.

## Review packet

`build_course_review` writes:

- `index.html`: browser-openable review packet;
- `review.md`: lightweight Markdown summary;
- `inventory.json`: canonical collection inventory using the same `evaluar-curation-inventory-v1` vocabulary as the evidence inventory.

The packet shows rendered student statements next to escaped original source, validation findings, metadata, assets, provenance, review state, tutoring eligibility, and reviewer decision checkboxes. It does not execute arbitrary authored JavaScript or active HTML.

## Approval and publication

After reviewing the browser packet, the instructor updates manifest review fields. `build_course_bundle` enforces publication gates by default and writes the existing deterministic `bundle.json` format used by `publish_content`.

## Revision workflow

Revise through immutable versions:

1. edit source/metadata in the collection workspace;
2. regenerate and check `generated/index.csv`;
3. rebuild the review packet;
4. obtain instructor/rendering approval;
5. build a new bundle with the current source commit;
6. publish explicitly.

## Governance notes

Treat collections as maintained academic assets. Record provenance, permission, review status, rendering requirements, and tutoring boundaries before using an exercise beyond a small private pilot. Keep solutions, rubrics, and answer-revealing tutoring guidance under `private/` and do not add them to public statements or public assets.

## Synthetic fixture

`collections/synthetic-db-fixture/` is a technical fixture only. It demonstrates Spanish prose, SQL-like text, relational schema notation, inline math, textual table representation, and long-statement rendering. It is not a real Database Theory curriculum.
