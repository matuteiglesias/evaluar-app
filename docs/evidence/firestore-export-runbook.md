# Firestore evidence export runbook

## Scope and safety

`scripts/export_firestore.py` is a read-only evidence collector. It uses only
collection listing, document streaming, document decoding, and subcollection
listing. It does not call `set`, `create`, `update`, `delete`, transactions, batch
writes, or import APIs. Run it with a dedicated principal that has only the
minimum Firestore read/list permissions and access to the intended project.

**This evidence export is not automatically a disaster-recovery backup.** It is
an application-level NDJSON representation intended for inventory, profiling,
and migration review. It does not preserve all provider metadata, indexes,
security rules, IAM, point-in-time recovery state, or guarantee an atomic
snapshot. A provider-managed Firestore backup/export and independently tested
restore procedure may also be required outside this repository.

## Prerequisites

1. Use Python 3.10–3.13 with project dependencies installed.
2. Check out the exact source commit to associate with the evidence.
3. Authenticate using Application Default Credentials or set
   `GOOGLE_APPLICATION_CREDENTIALS` to an operator-managed credential outside Git.
4. Confirm the project identifier independently. Never put secrets in command
   arguments, export labels, paths, logs, or committed reports.
5. Choose a new export ID such as an approved UTC timestamp. The exporter refuses
   to overwrite an existing directory.

## Exact operator commands

First perform read-only discovery without writing output:

```bash
python scripts/export_firestore.py \
  --project-id PROJECT_ID \
  --source-environment production \
  --list-only
```

Then export to the required ignored raw-data tree:

```bash
python scripts/export_firestore.py \
  --project-id PROJECT_ID \
  --source-environment production \
  --output var/legacy/firestore/EXPORT_ID
```

The tool writes `documents.ndjson`, `manifest.json`, and `manifest.sha256`.
Documents are ordered by full path; object keys and collection summaries are
ordered. Special values are tagged explicitly (`timestamp`, `reference`,
`geopoint`, `bytes`, non-finite `float`, and unknown values). The manifest records
the operator environment label, project, source commit, tool version, counts,
file hash, and incomplete reads. `manifest.sha256` contains the manifest hash.

## Verification and handling

```bash
cd var/legacy/firestore/EXPORT_ID
sha256sum --check manifest.sha256
sha256sum documents.ndjson
```

Compare the second hash with `files[].sha256` in `manifest.json`. Confirm
`status` is `complete`, `incomplete_collection_reads` is empty, expected
collections appear, and counts are plausible. A nonzero exporter exit is a
failed export even though partial files and an `incomplete` manifest are retained
for diagnosis. Do not treat partial output as complete evidence.

Raw output may contain names, emails, identifiers, student questions, model
responses, tokens, and other personal or secret data. Keep it encrypted with
restricted access, apply the approved retention schedule, and do not attach it to
issues or pull requests. Generate only aggregate field/type/missing-rate reports
for Git; review every redacted sample manually, and omit samples unless their
safety is demonstrable.

## Current evidence gap

No live command was run in this phase because credentials were unavailable. No
collection count or hash in repository documentation should be read as a live
result. An authorized operator must run the exact commands above and separately
record custody, time, credential role, verification result, and approved sanitized
profile.
