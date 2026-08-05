# Course collection onboarding toolkit

This toolkit adds a small authoring layer above the existing deterministic content compiler. It does not replace `compile_content`, immutable exercise versions, or atomic publication. Instructors maintain one `collection.yaml`; the toolkit validates richer curation metadata, writes a deterministic compatibility `generated/index.csv`, materializes compiler-compatible content in a temporary workspace, builds a static review packet, and then writes the normal deterministic bundle.

## Quick workflow

```bash
uv run python manage.py scaffold_course \
  bases-de-datos-2c2026 \
  --subject bases-de-datos \
  --name "Bases de Datos — 2C 2026" \
  --language es-AR
```

This creates `collections/bases-de-datos-2c2026/` with public statements/assets, private instructor-only folders, a starter manifest, and a local README.

Add reviewed public statements under `collections/bases-de-datos-2c2026/exercises/` and edit `collections/bases-de-datos-2c2026/collection.yaml`, or add a draft exercise entry with:

```bash
uv run python manage.py add_collection_exercise \
  bases-de-datos-2c2026 \
  --stable-id bd.sql.001 \
  --title "Selección y proyección" \
  --section pilot
```

The add command creates a statement template, appends a deterministic manifest entry at the next section order, refuses duplicate stable IDs or overwrites, regenerates the compatibility index, and reminds maintainers to complete objective, provenance, permission, and review fields.

```bash
uv run python manage.py validate_course_collection \
  bases-de-datos-2c2026 \
  --write-index

uv run python manage.py validate_course_collection \
  bases-de-datos-2c2026 \
  --check

uv run python manage.py validate_course_collection \
  bases-de-datos-2c2026 \
  --json

uv run python manage.py build_course_review \
  bases-de-datos-2c2026 \
  --output build/reviews/bases-de-datos-2c2026
```

`--write-index` deterministically regenerates `collections/<course>/generated/index.csv` from `collection.yaml`. The file is marked with `generated_by`, `source_manifest`, `stable_id`, `version`, `statement_path`, and `statement_format` columns while preserving the compiler-required `id`, `section`, `file`, `name`, and `info` columns. `--check` fails if the committed generated index is missing, stale, or manually edited.

After instructor and rendering review set each pilot exercise to:

```yaml
review:
  status: approved
  rendering_status: approved
```

Then build and publish the existing bundle format:

```bash
uv run python manage.py build_course_bundle \
  bases-de-datos-2c2026 \
  --output build/courses/bases-de-datos-2c2026 \
  --source-commit "$(git rev-parse HEAD)"

uv run python manage.py publish_content build/courses/bases-de-datos-2c2026
```

## Workspace layout

```text
collections/
└── bases-de-datos-2c2026/
    ├── collection.yaml
    ├── exercises/
    │   └── 001.tex
    ├── assets/
    ├── generated/
    │   └── index.csv
    ├── private/
    │   ├── solutions/
    │   ├── rubrics/
    │   └── tutoring-guidance/
    └── README.md
```

Only `collection.yaml`, public `exercises/`, public `assets/`, and generated compatibility metadata feed publication. `private/` is instructor-only material and is not copied into the student publication bundle.

## Minimal manifest contract

Required for a private pilot:

- `schema: evaluar-collection-manifest-v1`
- `course.slug`, `course.name`, and `course.language`
- `subject.id`
- at least one section with `id`, `title`, and `order`
- each exercise `stable_id`, `version`, `title`, `section`, `order`, `statement.path`, `statement.format`, `learning_objective`, `provenance.status`, and `review.status`

Optional fields such as difficulty, estimated time, tags, owners, reviewers, detailed provenance, rendering requirements, and tutoring policy can be added incrementally. Do not block a first technical validation on dozens of metadata fields; do block publication when required review gates have not passed.

## Example

```yaml
schema: evaluar-collection-manifest-v1

collection:
  id: bases-de-datos/practical-guide
  release: pilot-v0.1

subject:
  id: bases-de-datos

course:
  slug: bases-de-datos-2c2026
  name: Bases de Datos — 2C 2026
  offering: 2C2026
  language: es-AR

governance:
  owners: []
  reviewers: []

sections:
  - id: introduccion
    title: Introducción al modelo relacional
    order: 10

exercises:
  - stable_id: bd.intro.001
    version: 1
    title: Claves primarias y foráneas
    section: introduccion
    order: 10
    statement:
      path: exercises/001.tex
      format: latex
    learning_objective: Distinguir claves primarias, claves foráneas e integridad referencial.
    prerequisites:
      - relación
      - atributo
    provenance:
      status: instructor-authored
      author: Matías Iglesias
      source: null
      license_or_permission: course-use-approved
    review:
      status: draft
      reviewer: null
      reviewed_at: null
      rendering_status: pending
    rendering:
      requirements:
        - prose
        - relational-schema
    tutoring:
      eligible: false
      policy_review_status: pending

assets: []

release:
  notes: []
  publication_eligibility:
    technical_validation: required
    instructor_review: required
    rendering_review: required
```

## Review packet

`build_course_review` writes `index.html` for browser review and `review.md` as a lightweight summary. The HTML packet includes the collection overview, validation summary, publication eligibility, per-exercise metadata, rendered student statement, original source, validation findings, rendering requirements, assets, provenance, review status, tutoring eligibility, and reviewer-decision checkboxes. Exercise source is escaped and rendered output comes from the existing sanitized compiler path; the packet does not execute authored JavaScript or arbitrary active HTML.


## Synthetic fixture

`collections/synthetic-db-fixture/` is a technical fixture only. It contains synthetic Spanish prose, SQL-like text, relational schema notation, inline mathematics, a textual table representation, and a long statement. It exists to prove scaffolding-adjacent validation, deterministic compatibility generation, focused compilation, static review generation, and publication-eligibility calculation without claiming to be an authoritative Database Theory course.
