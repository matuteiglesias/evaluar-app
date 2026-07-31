# Content authority hypothesis and conflicts

## Starting hypothesis

The tested hypothesis is that each `exercises/<course>/index.csv` together with
its corresponding `.tex` files is the canonical authored exercise source;
generated documentation is not authoritative; root-level legacy CSV/text files
are non-authoritative unless uniquely preserving content; and images are
authoritative only when referenced by canonical exercises.

The inventory supports this hypothesis structurally but does **not** make a final
editorial or migration decision. No duplicate, legacy, or malformed content was
deleted or rewritten.

## Evidence supporting the hypothesis

- Both course directories have readable indexes with the required `id`,
  `section`, `file`, `name`, and `info` columns.
- All 110 index rows resolve to a non-empty, UTF-8 `.tex` file, and there are no
  unindexed `.tex` files.
- All seven `tikzpics/` images are referenced by canonical indexed exercises;
  there are no missing or orphan canonical images.
- There is no root-level legacy CSV, text, or TeX candidate in this checkout that
  could contain uniquely absent exercise content.
- The `docs/` HTML and its two presentation images are generated documentation,
  not an authored exercise input to the application.

## Conflicts preventing unconditional acceptance

### Cross-course identity and duplicated bytes

IDs `101`, `102`, `201`, and `202` occur in both `demo_course` and `tda`. Each pair
also has byte-identical `.tex` content. The inventory preserves both course-scoped
global keys and does not decide whether `demo_course` is a sample, a fork, or an
independently authoritative course.

Within `tda`, exercises `502` and `504` also have the same content SHA-256 while
retaining distinct IDs and metadata rows. Editorial review must decide whether
this is intentional reuse or an accidental duplicate. Until then neither entry
is preferred.

### Renderer/content disagreement

Exercises `demo_course:102`, `tda:102`, `tda:408`, and `tda:415` embed HTML tables.
The current sanitizer does not allow `table`, `tr`, or `td`, so rendered output
does not faithfully preserve those authored structures. This is a renderer
compatibility conflict, not proof that the source files are wrong. The validator
reports it and leaves both renderer and corpus unchanged.

### Generated documentation duplication/staleness risk

The generated `docs/` tree mirrors application modules and can preserve older
rendered source independently of current Python files. It is useful historical
evidence but is not authoritative for exercise metadata or content. It must not
win a conflict merely because it duplicates a source representation.

## Authority outcome

The course indexes and their `.tex` files remain the **best-supported authority
hypothesis**, with course scope integral to identity. Referenced `tikzpics/`
assets participate in that hypothesis. Acceptance remains conditional on resolving
the duplicated course/content relationships and the four HTML rendering conflicts.
The artifacts record facts; they do not silently choose winners.
