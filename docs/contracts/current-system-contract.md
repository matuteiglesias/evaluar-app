# Current system characterization contract

## Status and scope

This contract captures intended behavior that is executable in characterization
tests and separately records observable legacy behavior. It is a migration
acceptance baseline, not a redesign and not an endorsement of every legacy
choice. Course-scoped identity is written `course_slug:exercise_id`; a numeric ID
alone is never a complete exercise identity.

The content inventory currently supports `exercises/<course>/index.csv` plus its
indexed `.tex` files as the best available authored-content authority. Repeated
numeric IDs across courses remain distinct. Content inventory warnings remain
review items rather than silently repaired content.

## Replaceable boundaries

| Concern | Application boundary | Legacy/default implementation | Test implementation |
|---|---|---|---|
| Identity | `identity_provider.begin/complete` in `app.extensions` | Authlib Google OAuth adapter | In-process verified fake identity |
| Persistence | `persistence.save_interaction/save_feedback/save_teacher_packet` | Compatibility Firestore adapter | In-memory recording fake |
| Tutoring model | `tutor.guide(course, id, content, question)`; legacy fallback uses `Evaluator.evaluate` | OpenAI-backed evaluator | Deterministic recording fake |
| Clock | `clock()` extension through `services.runtime_boundaries.now` | UTC application clock | Fixed aware datetime |
| IDs | `id_generator(kind, identity)` extension | UUID-based IDs | Monotonic deterministic IDs by kind |

These seams are intentionally narrow. They do not introduce a repository layer
for every route or rewrite the content system.

## Persistence direction

Firestore remains the legacy application's compatibility store and historical
data source. It must **not be deleted from the GCP account as part of this work**.
An authorized operator will export it as legacy data and archive it under the
approved retention and access policy. The in-repository adapter does not make
Firestore the future architecture.

PostgreSQL is the selected future operational persistence system. Its schema,
migration, reconciliation, cutover, archival retention, and deletion approvals
are outside this characterization phase. The narrow persistence operations are
designed to be implemented by PostgreSQL later without changing journey intent.

The teacher roster is not required for the intended teacher-time flow. A student
creates a generic teacher-help packet with explicit `unassigned` state. No
specific teacher is selected and no `teachers` dataset lookup is part of the new
contract. Existing Firestore teacher data remains legacy archive evidence until
retention review; this change does not delete it.

## Core invariants

1. Authentication establishes a local session only after a verified identity.
2. Course content is read only through a safe indexed course/file identity.
3. Tutoring, interaction, feedback, and teacher packet records carry both course
   and exercise ID.
4. Feedback carries a persistent response ID and must match the current response
   state exactly; stale, duplicate, or cross-course submissions are rejected.
5. One accepted teacher-help submission creates one open, unassigned packet.
6. External failures produce bounded HTTP failures and do not claim persistence.
7. No characterization test contacts OAuth, Firestore, OpenAI, or any network.

## Deliberately unresolved policy

- Course enrollment/membership is not represented; authentication currently
  grants access to every indexed course.
- The legacy model prompt behaves like evaluation/grading, while the intended
  journey is tutoring guidance. Prompt/product policy requires a later decision.
- Whether a generated answer should be displayed when interaction persistence
  fails is ambiguous. Current safe behavior returns a controlled 503 and clears
  feedback correlation state rather than presenting an unrecorded response.
- Retention and minimization for questions, responses, feedback, identity fields,
  teacher packets, and the Firestore archive require privacy review.
