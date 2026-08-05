# Collection curation investigation

Starting commit: `a0d8727f8eac5172ef7340e84f766f638cfac80b`.

Machine-readable companions:

- `docs/evidence/collection-inventory.v1.json`: per-exercise inventory with checksum, generated slug, constructs, references, assets, findings, inferred objective from legacy `info`, and explicit unknown review/provenance fields.
- `docs/evidence/content-validation-findings.v1.json`: current compiler validation findings from `compile_content('.')`.
- `artifacts/legacy/content-manifest.v1.json`, `artifacts/legacy/content-issues.csv`, and `artifacts/legacy/content-assets.csv`: existing deterministic legacy inventory outputs.

## 1. Existing collection topology

Current course directories under `exercises/` are:

| Course | Indexed exercises | Tex files | Sections | Status |
|---|---:|---:|---|---|
| `demo_course` | 4 | 4 | `1` (2), `2` (2) | warning in legacy inventory; invalid in formal compiler because exercise 102 has authored HTML table |
| `tda` | 106 | 106 | `1` (21), `2` (12), `3` (19), `4` (19), `5` (20), `6` (15) | warning in legacy inventory; invalid in formal compiler because three exercises have authored HTML tables and many unresolved references |

The stable author-facing identifiers currently available are course-scoped external keys such as `tda:101` and `demo_course:101`. Numeric IDs alone are not globally stable because `101`, `102`, `201`, and `202` occur in both `demo_course` and `tda`. The generated application slug is derived from title normalization; it is deterministic but not an identity because title edits can change it.

Observed disagreements:

- Filenames match `id.tex` for all indexed exercises in the current inventory.
- `demo_course` duplicates the first four TDA exercises byte-for-byte, so it is a demonstration copy, not an independent canonical course collection.
- `tda:502` and `tda:504` have the same content checksum and require instructor review to decide whether they are intended duplicates, variants with missing edits, or a copy error.
- Titles include presentation-oriented names and some punctuation/diacritics that normalize into different slugs; this is acceptable for URLs but should not define exercise identity.

Supporting assets live outside course directories in global `tikzpics/`. Current content assets are `303.png`, `314.png`, `318.png`, `403.png`, `411.png`, `417.png`, and `520.png`; application/documentation assets also live in `static/` and `docs/assets/`. Because TDA files reference labels such as `fig:grafo orientado` rather than file paths, some figure dependencies are currently implicit in the legacy LaTeX context.

Legacy Flask conventions visible in docs/code rather than pedagogy:

- Adding a course means creating `exercises/<course>/index.csv` with columns `id`, `name`, `info`, `file`, `section`.
- The old access pattern used `http://localhost:5000/course?course=<slug>`.
- The production Django compiler now treats imported IDs as course-scoped external keys and generates deterministic title slugs; publishing is checksum verified and atomic.

## 2. Pedagogical topology

### `demo_course`

`demo_course` is a demonstration subset copied from TDA:

- Section `1`: backtracking / dynamic programming introductory exercises (`SumaSubconjuntosBT`, `MagiCuadrados`).
- Section `2`: divide-and-conquer introductory exercises (`IzquierdaDominante`, `ÍndiceEspejo`).

Pedagogical provenance, intended placement, difficulty, expected time, and review status are unknown and should not be inferred as canonical for another course.

### `tda`

TDA has six numeric sections. The `index.csv` order, filenames, titles, and descriptions indicate the following broad progression, but the section names are not recorded in metadata and require instructor confirmation:

1. Section `1` — backtracking, dynamic programming, greedy algorithms, optimization problems, and recurrence formulation.
2. Section `2` — divide and conquer, recurrence analysis, sublinear searches, and construction problems.
3. Section `3` — graph-theory proof exercises: degrees, connectivity, cycles, paths, bipartite structures, independent sets, cliques, coloring, and graph classes.
4. Section `4` — graph algorithms and traversal properties, DFS/BFS-style reasoning, bridges/articulation-like ideas, ordering, bandwidth-style graph measures, and graph transformations.
5. Section `5` — advanced graph/optimization themes including paths, matchings/flows or reductions where labels such as `SRD`, `fmcm`, and `matching` appear.
6. Section `6` — later TDA material; exact topic labels require instructor review from authoritative syllabus/source PDFs.

Per-exercise learning objective is captured only as a prose `info` field. Difficulty, expected time, prerequisites, assessment type, relation to lecture/practical/exam, and instructor-reviewed solution technique are all unknown unless directly implied by the statement and must remain `unknown` or `requires instructor review` in the inventory.

## 3. Content quality and defect taxonomy

Severity scale for curation:

| Code | Meaning | Publication posture |
|---|---|---|
| P0 | Materially wrong, unsafe, confidential, or rights-unsafe to publish | Block publication until instructor/owner resolves |
| P1 | Meaning lost during rendering or current compiler rejects meaningful structure | Block publication or require explicit compiler support/rewrite with review |
| P2 | Ambiguous/incomplete statement; multiple plausible interpretations; missing constraints | Instructor review required before high-stakes use |
| P3 | Broken reference, missing/implicit asset, or reliance on external LaTeX context | Require attached asset, label map, or human rendering review |
| P4 | Metadata/provenance/review gap | Does not block a private pilot, blocks stable public/reusable release |
| P5 | Editorial inconsistency, Spanish terminology, typography, overly long statement | Batch editorial pass after semantics are understood |
| P6 | Optional pedagogical improvement | Backlog only after launch needs are met |

Current validation findings classified:

| Finding | Affected items | Classification | Root cause | Safe automation? | Human judgment? |
|---|---|---|---|---|---|
| `unsupported_authored_html_table` | `demo_course:102`, `tda:102`, `tda:408`, `tda:415` | P1 | Authored HTML tables are deliberately rejected by the compiler | No silent stripping; can auto-detect and propose conversion fixture | Yes, to verify table semantics after conversion |
| `invalid_reference` | TDA 105, 120, 121, 303, 313, 315, 318, 403, 411, 412, 417, 512, 514, 520, 613, 614 | P3 | Individual `.tex` files reference labels defined outside the file or missing from repo-local source | Can inventory and map labels; cannot invent target | Yes |
| `unsupported_html` in legacy inventory | Same table-bearing files | P1 | Legacy inventory warns on unsupported tags; formal compiler errors on tables | Detect only | Yes |
| `cross_course_repeated_id` | demo/TDA copied IDs 101, 102, 201, 202 | P4 | Numeric IDs are course-scoped and demo content copied from TDA | Yes: report scoped IDs | Owner decides canonical/demo status |
| `duplicate_content_hash` | demo/TDA copied files; TDA 502/504 | P4/P2 | Demonstration copy or possible accidental duplicate | Detect only | Yes |
| No provenance/license/reviewer metadata | All exercises | P4 | Legacy contract has no fields for author/source/license/review | Can scaffold unknown fields | Yes |

## 4. Rendering contract

Current application/compiler behavior:

- Ordinary prose and accented Spanish: supported as UTF-8 escaped HTML.
- Inline and display mathematics: preserved as source for client-side MathJax because rendering escapes source and retains `$...$`/LaTeX text.
- Long statements and paragraphs: supported by escaping and paragraph splitting.
- Source code, SQL, pseudocode, relational schemas, recurrence relations, automata, trees, traces: only supported as literal escaped text unless represented by allowed LaTeX/math text; require rendering fixtures for Database Theory before publication.
- Images: supported only through known asset files discovered under `assets/`, `tikzpics/`, `images/`, or `img`; references must be explicit and present.
- Tables: authored HTML tables are rejected; LaTeX tables are not canonically compiled into semantic HTML.
- Graphs/diagrams: currently image-backed or implicit through legacy labels; TikZ source is not compiled by this pipeline.
- Cross references: fragile. The compiler only considers labels inside each individual source, so legacy global labels produce warnings.
- Nested lists: literal HTML list tags are partially tolerated in the legacy inventory allowlist, but the compiler escapes source HTML, so authored HTML structure is not a faithful rendering contract.

Recommended posture:

| Construct | Recommendation |
|---|---|
| Prose, Spanish accents, inline/display math, recurrence formulas | Support canonically |
| Pseudocode, source code, SQL, relational algebra, schemas, traces | Support canonically via fenced/source block notation or explicit compiler transform |
| LaTeX/HTML tables | Transform through an explicit compiler or reject before publication; never silently strip |
| Graphs, automata, trees, diagrams | Require attached asset or canonical diagram source with deterministic renderer |
| `\ref` / `\label` relationships | Require manifest-declared references or compile a collection-level label map |
| `\input`, `\include`, `\usepackage`, arbitrary HTML/CSS | Reject before publication unless specifically whitelisted and compiled safely |
| Exercises relying on classroom-only context | Require human-rendering and pedagogical review |

## 5. Collection identity model

Use these terms distinctly:

- Subject: long-lived academic domain, e.g. `bases-de-datos` or `tda`.
- Course definition: institution-specific teachable course tied to a subject.
- Academic offering: concrete term, e.g. `bases-de-datos-2c2026`.
- Collection: ordered set of exercise placements for a purpose, e.g. practical guide, homework set, exam practice.
- Release: immutable publication of a collection with checksum, release notes, owners, and eligibility status.
- Exercise identity: stable pedagogical object ID, not a filename or title slug.
- Exercise version: immutable statement/metadata/provenance revision.
- Placement: inclusion of one exercise version in a collection section/order with local display metadata.

No database migration is required for the first curation step. A directory and manifest convention can compile into the existing deterministic bundle while preserving current `index.csv` compatibility. For Database Theory, prefer `subject: bases-de-datos`, `offering: bases-de-datos-2c2026`, and `collection release: practical-guide-v0.1`, even if the current application course slug remains `bases-de-datos-2c2026`.

## 6. Reuse and duplication policy

- Same exercise in two offerings: reuse the same stable exercise ID and version through manifest composition when wording is unchanged.
- Wording changes but same mathematical intent: create a new exercise version with `derived_from` pointing to prior version.
- Simpler variant or parameter changes: create a related exercise ID or variant version with explicit relation (`simplifies`, `parameterized_from`, `exam_adaptation_of`).
- Translation: separate version or locale-specific statement linked to canonical identity; record translator/reviewer.
- Exam adaptation: new version with confidentiality/embargo metadata; do not expose private solution/rubric by default.
- Borrowed material: record canonical source, license/permission, and adaptation notes before publication.
- Demonstrations: mark `demo_course` as a non-authoritative copy unless an instructor explicitly adopts it.

Copying remains acceptable for a small pilot only when the manifest records provenance and intended divergence. Untraceable copying should be prevented by duplicate checksum reports.

## 7. Provenance and rights

The current repository records no per-exercise author, contributing instructors, original source, adaptation history, license/permission, academic term, reviewer, last substantive review, solution status, or confidentiality constraints in the exercise indexes. Repository-level MIT licensing for code is not sufficient evidence that all educational content is freely licensed or reusable.

Publication rule: any exercise with unknown third-party origin, exam origin, textbook/web origin, or missing permission is not eligible for public reusable release. It may be used in a private instructor-reviewed pilot only if the institution/course owner accepts that risk.

## 8. Solutions and assessment knowledge contract

No repository-local canonical solutions, hints, rubrics, expected concepts, common mistakes, or tests were found in the inspected content paths. A future contract must keep these separate:

- `public_statement`: student-visible prompt.
- `student_hint`: progressively revealable hints, reviewed for not solving the exercise outright.
- `private_solution`: instructor-only solution; never sent to general AI tutor prompts.
- `assessment_rubric`: grading criteria, optionally visible to students if instructor chooses.
- `common_misconceptions`: safe for tutor if phrased diagnostically rather than as answer key.
- `ai_tutoring_guidance`: allowed tutor strategy, Socratic prompts, boundaries, and escalation conditions.
- `forbidden_disclosure`: explicit answer fragments, exam-sensitive facts, or solution paths that must not be disclosed.

Maintainers decide tutor access exercise by exercise. Eligibility requires an unambiguous statement, learning objective, explicit prerequisites/context, reviewed public/private boundary, and instructor-inspectable generated guidance examples.

## 9. Minimal authoring contract

Recommended `exercise.yaml` (or a collection manifest entry) fields:

Required for publication:

- `stable_id`
- `title`
- `section`
- `statement.path`
- `statement.format`
- `order`
- `learning_objective`
- `provenance.status`
- `visibility.statement`
- `review.status`

Required for stable/reusable release, optional for private pilot:

- `prerequisites`
- `difficulty`
- `estimated_time_minutes`
- `tags`
- `provenance.author`, `source`, `license_or_permission`, `adaptation_history`
- `assets`
- `solution_refs`, `hint_refs`, `rubric_refs`, all with visibility scopes
- `rendering_requirements`
- `last_substantive_review`, `reviewer`

Keep `index.csv` as backward-compatible compile input, but do not overload it with long provenance, review, and tutoring policy fields. Use a small YAML/JSON manifest that can generate `index.csv` and the deterministic bundle.

## 10. Collection manifest contract

A collection manifest should declare:

```yaml
schema: evaluar-collection-manifest-v1
collection_id: bases-de-datos/practical-guide
release_id: practical-guide-v0.1
subject: bases-de-datos
course_definition: bases-de-datos
offering: bases-de-datos-2c2026
language: es-AR
owners: []
reviewers: []
sections:
  - id: sql
    title: SQL
    order: 10
exercises:
  - stable_id: bd.sql.001
    version: 1
    placement:
      section: sql
      order: 10
    statement:
      path: exercises/bases-de-datos-2c2026/001.tex
      format: latex
assets: []
release_notes: []
publication_eligibility:
  technical_validation: required
  instructor_review: required
  rendering_review: required
```

Compilation path: manifest validates identity/provenance/review, materializes or checks `index.csv`, invokes `compile_content(root)`, records bundle checksum and validation findings, and blocks publication unless all required eligibility gates pass.

## 11. Human curation workflow

| Stage | Owner | Inputs | Outputs | Automation | Human judgment | Stop conditions |
|---|---|---|---|---|---|---|
| Ingest | Content maintainer + instructor | Authoritative files, PDFs, notes | Raw sources preserved with provenance | Checksums, file listing | Which sources are authoritative | Missing permission/source |
| Inventory | Knowledge engineer | Raw sources, repo | Machine inventory and review report | Parse indexes, detect constructs/refs/assets | Interpret unknowns | Unreadable files |
| Classify | Curriculum designer + editor | Inventory | Defect taxonomy per item | Suggested labels | Severity, pedagogical impact | P0/P1 unknowns unresolved |
| Resolve provenance | Course owner | Source history | Rights/provenance metadata | Duplicate/source similarity reports | Permission and confidentiality decisions | Unknown third-party/public rights |
| Technical normalization | Platform maintainer | Reviewed source | Minimal normalized statements/assets | Explicit transforms, fixtures | Verify meaning preserved | Rendering loss |
| Instructor review | CS instructor | Rendered/source/metadata | Approved or changes requested | Review report generation | Correctness, intent, prerequisites | Ambiguous/wrong prompt |
| Rendering review | Technical editor | Browser/HTML previews | Rendering approval | Screenshots, diff reports | Visual/math fidelity | Broken math/table/figure |
| Pilot publication | Software engineer | Approved subset | Immutable private release | Deterministic bundle/publish | Choose pilot scope | Failed validation/browser experience |
| Student feedback | Instructor | Pilot usage | Issues and improvements | Feedback aggregation | Interpret learning signals | Serious confusion |
| Revision | Joint team | Feedback/issues | New versions | Diff/checksum/revalidation | Accept semantic changes | Unreviewed changes |
| Stable release | Course owner | Approved revisions | Release notes + published collection | Atomic publish | Final go/no-go | Any required gate incomplete |

## 12. Instructor review surface

Start with generated Markdown or static HTML, not a CMS. For each exercise show:

- rendered statement;
- source side by side;
- metadata and unknown fields;
- validation warnings/errors with P-code;
- references and attached/missing assets;
- previous version diff when available;
- provenance/license status;
- solution/hint/rubric visibility;
- reviewer decision (`approve`, `approve with minor edits`, `needs technical fix`, `needs pedagogical fix`, `do not publish`);
- notes and publication eligibility summary.

## 13. Database Theory onboarding plan

Use likely Database Theory constructs only as rendering/metadata tests, not as syllabus assertions.

1. Acquire authoritative instructor materials for `bases-de-datos-2c2026`: statements, section names, ordering, diagrams, schemas, expected notation, source/permission, solution visibility, and any term-specific constraints.
2. Preserve raw sources with checksums outside generated artifacts.
3. Select a pilot of 5-15 exercises spanning representative constructs: relational schemas, SQL, relational algebra, dependencies/normalization, transactions/schedules, and diagrams only if instructors supply them.
4. Assign stable IDs that do not depend on filenames or term slug.
5. Create a collection manifest for subject/offering/release identity.
6. Add rendering fixtures for SQL, schemas, relational algebra, tables, and long Spanish statements.
7. Run inventory and formal validation; classify all findings.
8. Generate instructor review report and resolve provenance/review status.
9. Publish a private pilot release only after technical validation, instructor approval, and rendering review.
10. Collect student/instructor feedback, revise as new versions, then expand incrementally.

Do not bulk migrate a full Database Theory corpus before the pilot proves faithful rendering, useful metadata, stable identifiers, publication, and acceptable browser experience.

## 14. AI-tutoring boundary

An exercise is eligible for AI tutoring only after:

- public statement is unambiguous and render-reviewed;
- learning objective and prerequisites are recorded;
- instructor defines allowed tutor behavior and escalation policy;
- private solution/rubric is separated from tutor context unless explicitly approved;
- common mistakes are curated as diagnostic hints rather than answer reveals;
- required course context is explicit;
- prompt evaluation examples exist for at least correct, partially correct, and misconception answers;
- instructors can inspect representative tutor guidance before activation.

## 15. Prioritized backlog

### Immediate launch

| Item | Problem | Evidence | Impact | Human owner | Automation opportunity | Acceptance criterion | Scope |
|---|---|---|---|---|---|---|---|
| DB pilot source packet | No authoritative DB exercises in repo | No `exercises/bases-de-datos-2c2026` directory | Cannot publish safely | DB course owner | Checklist + checksum ingest | 5-15 instructor-approved statements received with provenance | S |
| Manifest for pilot | Current `index.csv` cannot hold provenance/review/tutoring boundaries | Legacy docs define only CSV fields | Prevents reviewable release governance | Content maintainer | YAML validation/generation | Manifest compiles to current bundle and records unknowns | M |
| Rendering fixtures | DB constructs may include SQL/schemas/tables/algebra | Current table rejection and literal rendering contract | Prevents faithful DB publication | Platform maintainer + instructor | Snapshot fixtures | Pilot constructs render faithfully or are rejected | M |
| Instructor review report | Instructors need side-by-side review | Current artifacts are machine reports | Avoids data-entry workflow | Technical editor | Generate Markdown/HTML from inventory | Reviewer can approve/block each pilot exercise | M |

### TDA rehabilitation

| Item | Problem | Evidence | Impact | Human owner | Automation opportunity | Acceptance criterion | Scope |
|---|---|---|---|---|---|---|---|
| Section naming | Numeric sections lack semantic labels | `index.csv` stores `1`-`6` only | Hard to review/reuse | TDA instructor | Draft map from index descriptions | Instructor-approved section titles | S |
| HTML table conversion | Four table statements blocked | Formal compiler errors on 102/408/415 plus demo copy | Cannot publish full TDA | Instructor + editor | Convert to canonical table notation with diff | Tables render with no meaning loss | M |
| Label/figure map | 23 unresolved refs | Formal validation warnings | Rendering/reference loss | TDA instructor | Extract labels/refs and assets | Every ref maps to exercise/figure or is removed with review | M |
| Duplicate audit | Demo copy and TDA 502/504 duplicate | Duplicate checksum findings | Unclear provenance/possible copy error | TDA owner | Checksum reports | Each duplicate marked demo/reuse/variant/error | S |
| Provenance registry | No content rights metadata | Index has no provenance fields | Blocks stable public reuse | Course owner | Scaffold unknown metadata | All stable-release exercises have source/license/review | L |

### Long-term collection platform

| Item | Problem | Evidence | Impact | Human owner | Automation opportunity | Acceptance criterion | Scope |
|---|---|---|---|---|---|---|---|
| Collection manifest compiler | Need subject/offering/release separation | Current app course slug can conflate offering and subject | Better reuse across terms | Platform maintainer | Compile manifest to bundle | Two offerings can share exercise versions with explicit placements | L |
| Review UI | Static report may become insufficient | Pilot feedback TBD | Efficient instructor workflow | Product owner | Web review queue | Only after static report proves value and gaps | L |
| Tutor content governance | AI tutor must avoid answer leakage | Current README mentions AI but no content boundary | Academic integrity risk | Course owner + AI maintainer | Policy lint checks | Tutor eligibility gate enforced per exercise | L |
| Provenance/reuse graph | Avoid untraceable copying | Existing duplicate content hashes | Maintainable knowledge base | Knowledge engineer | Similarity/provenance reports | Reuse/variant/translation relations queryable | L |

## 16. Recommended next execution task

Build a reviewable inventory and pilot publication for the first 5-15 authoritative `bases-de-datos-2c2026` exercises. Confirm the exact pilot scope from instructor-supplied source materials before adding content. The pilot should include only exercises whose statement, provenance, stable ID, rendering, metadata, and instructor review can be verified end-to-end.
