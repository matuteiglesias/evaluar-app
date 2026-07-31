# Firestore data profile

## Status

This is a **static, sanitized profile**, not the output of a live export. It
contains no document paths, document IDs, names, email addresses, free-text
questions, student answers, model responses, tokens, or raw samples. Runtime
counts, hashes, type frequencies, missing-field rates, and unknown collections
remain unavailable because this phase had no Firestore credentials.

| Collection | Fields named by code | Fields per inferred type | Missing-field rate | Document count | Live evidence |
|---|---|---|---|---|---|
| `teachers` | `teacherId`, `surname`, `name`, `email`, `currentLoad`, `maxLoad` | string: 4; integer: 2 | Unknown | Unknown | Not collected |
| `tickets` | `exerciseId`, `question`, `status`, `studentId`, `studentName`, `studentEmail`, `teacherId`, `timestamp` | string: 7; timestamp: 1 | Unknown | Unknown | Not collected |
| `interaction_records` | `exerciseId`, `userId`, `userName`, `userQuery`, `aiResponse` | string: 5 | Unknown | Unknown | Not collected |
| `user_feedback` | `feedback`, `exerciseId`, `studentId`, `studentName`, `evaluated_response` | string/string-nullable: 5 | Unknown | Unknown | Not collected |

The field totals describe the legacy code contract only. They do not prove that
the fields exist in every record or that Firestore contains no additional types.
In particular, earlier code revisions and manual operations may have produced
different schemas.

## Sanitized profiling procedure

After an authorized raw export, derive in a controlled environment:

1. collection/subcollection path patterns with document ID segments removed;
2. document counts per sanitized collection pattern;
3. field-name/type frequency and missing-field rate per pattern;
4. counts of exporter `unknown` values and incomplete reads;
5. the raw-file SHA-256 manifest (hashes, never raw content).

Treat field names as potentially sensitive until reviewed. Use no raw samples by
default. Aggregate small groups may still re-identify people, so suppress or
coarsen them under the applicable privacy threshold. Commit a generated profile
only after privacy/security review and record its raw manifest hash so the result
is reproducible without placing raw records in Git.

## Evidence gaps to close

- Run list-only and full export with an approved read-only principal.
- Establish whether unreferenced top-level collections or nested subcollections exist.
- Measure counts, types, missing fields, timestamp coverage, duplicates, and orphans.
- Determine retention/legal requirements and whether free text contains secrets.
- Compare an application-level export with any provider-managed backup inventory.
