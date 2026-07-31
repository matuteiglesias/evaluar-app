# Legacy Firestore collection map

## Evidence basis and limits

This map was produced by static inspection of `routes/`, `services/`, `models/`,
and `scripts/`, including the former fixed-collection exporter and the historical
teacher initialization script. No credentials were available during this pass,
so **no live Firestore export was performed**. Collection existence, runtime-only
fields, nested subcollections, counts, and actual types remain an evidence gap.

The HTML API documentation contains older generated source which mentions the
same four collections. It is corroborating history, not evidence of current data.
No Firestore access was found in `models/`. No root-level export script or existing
export artifact was found. The ignored `data/`, `*.json`, and newly ignored
`var/legacy/firestore/` paths could contain operator-local exports, but ignored
files were not present in this checkout and must never be committed.

Types below are inferred from current writers/readers, not observed live values.
`string?` means optional or nullable. Every user-linked collection may contain
personal data.

## Known top-level collections

| Collection path | Known writers | Known readers | Known/inferred fields and types | Personal data | Character | Uncertainty |
|---|---|---|---|---|---|---|
| `teachers` | Historical commented writer in `scripts/init_teachers.py` | `routes/teachers.py` reads a document; `services/teachers.py` streams all | `teacherId`: string; `surname`: string; `name`: string; `email`: string; `currentLoad`: integer; `maxLoad`: integer | Yes: name, surname, email, stable teacher ID | Configuration-like roster plus operational capacity settings | Historical writer is disabled; current load fields are not used by current readers; live presence/types/extra fields unknown |
| `tickets` | `routes/teachers.py` | `services/teachers.py` queries/streams | `exerciseId`: string; `question`: string; `status`: string (`open` written); `studentId`: string; `studentName`: string; `studentEmail`: string; `teacherId`: string (`na` possible); `timestamp`: Firestore timestamp | Yes: student identity/contact, stable IDs, free-text question | Operational request record that becomes historical | Retention, closed-state schema, extra fields, counts, and timestamp completeness unknown |
| `interaction_records` | `routes/exercises.py` | None found | `exerciseId`: string; `userId`: string; `userName`: string; `userQuery`: string; `aiResponse`: string | Yes: identity, student answer/question, model response | Historical/audit or analytics record | No timestamp is currently written; purpose, retention, extra fields and completeness unknown |
| `user_feedback` | `routes/exercises.py` | None found | `feedback`: string; `exerciseId`: string; `studentId`: string?; `studentName`: string?; `evaluated_response`: string | Yes: identity, free text, model response | Historical feedback record | No timestamp is currently written; purpose, retention, extra fields and completeness unknown |

## Subcollections and unknown collections

Static code references no subcollection path. That does **not** establish that no
subcollections or additional top-level collections exist. Firestore allows data
that is not named in application code. The evidence exporter enumerates all
top-level collections and, for every readable document, recursively calls the
read-only subcollection listing API. Empty collections are generally not durable
Firestore resources; a fake empty collection is nevertheless tested to ensure a
listed zero-document collection is represented.

## Read/write inventory

- `routes/exercises.py`: writes `interaction_records` and `user_feedback`.
- `routes/teachers.py`: reads `teachers` and writes `tickets` with a server timestamp.
- `services/teachers.py`: reads and queries `teachers` and `tickets` for assignment.
- `services/firebase.py`: creates the lazy Firestore client but names no collection.
- `scripts/export_firestore.py`: read-only discovery/export of every reachable collection.
- `scripts/init_teachers.py`: historical initialization code; the write loop is commented,
  but importing/running it still initializes a client and reads a local CSV.

Collection authority and disposition are deliberately not inferred from this map;
see [ADR 0001](../decisions/0001-legacy-firestore-status.md).
