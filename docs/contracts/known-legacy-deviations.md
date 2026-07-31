# Known legacy deviations

## Repaired rather than preserved

These behaviors are not desired characterization outcomes:

- Exercise lookup path traversal and unsafe repository/model HTML were repaired
  during Phase 0 and remain rejected/sanitized.
- Numeric exercise ID without course was ambiguous. New interaction, feedback,
  and teacher packet writes include the course and tests use duplicate numeric ID
  `101` in two courses.
- Feedback previously used a mutable `session["evaluated_response"]` value and no
  persistent response ID. Feedback now requires an exact response/course/exercise
  correlation and consumes it after one successful rating.
- Teacher requests previously queried `teachers`, counted historical tickets for
  load, selected a teacher, and wrote `teacherId`. The intended flow now creates
  one generic open packet with `assignment=unassigned` and no roster dependency.
- Random teacher-prefixed ticket IDs made exact characterization difficult. IDs
  now come from a replaceable generator and do not encode a teacher.
- Provider/model/persistence errors could escape or be conflated with success.
  Essential routes now return controlled failures with explicit side-effect rules.

## Observed but not endorsed

- `models.user` is process-local memory, so user records disappear on restart and
  are not suitable as the future identity store.
- Any authenticated student can browse any indexed course; enrollment and roles
  are absent.
- Course selection and exercise section grouping are implemented by browser
  JavaScript rather than a server-owned course context.
- The evaluator is named and prompted as evaluation/grading even though the
  desired journey is tutoring guidance.
- Legacy Firestore records may omit course, response IDs, timestamps, or explicit
  feedback links. Archive/migration tooling must not invent those values.
- Legacy teacher load counted all streamed tickets rather than clearly limiting
  to open tickets. Since the intended packet is generic, no load rule is carried forward.

## Storage transition

Firestore is not the future operational store. It must remain in the GCP account
until an authorized legacy export is verified and archived; nothing here requests
its deletion. PostgreSQL is the future persistence target. The Firestore adapter
exists only to characterize the running legacy application during transition.

Teacher records may be unnecessary operationally because packets are no longer
assigned to named teachers. They remain part of historical Firestore evidence and
must be archived or retained according to review, not silently deleted.

## Ambiguities requiring later decisions

- Display generated guidance after a persistence outage, queue it, or fail closed.
- One feedback per response versus multiple revisions and cross-device behavior.
- Durable enrollment authorization and course lifecycle/version identity.
- Tutoring-only prompt policy versus assessment/grading features.
- PostgreSQL schemas, idempotency, retention, archival links, and reconciliation.
- Whether old teacher records have an independent lawful archival purpose.
