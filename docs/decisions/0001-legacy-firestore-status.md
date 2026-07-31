# ADR 0001: Legacy Firestore status

- **Status:** Proposed; authority and retention decisions unresolved
- **Date:** 2026-07-31

## Context

The legacy application reads or writes four named Firestore collections. Static
inspection establishes code intent but not the live inventory. This recovery pass
must preserve evidence without selecting Firestore as the future architecture.

## Decision

Firestore is the **historical source of record** for legacy records that were
successfully written there, subject to verification by a live export and any
provider-managed backup. This phrase describes provenance only; it does not assert
that the database is complete, authoritative for every field, or currently live.

The **future operational source of record is not yet selected**. Firestore is not
introduced as a dependency of the future architecture by this ADR or exporter.
Future storage will be chosen in a separate decision based on product, privacy,
retention, integrity, availability, portability, and operational requirements.

## Provisional disposition (not authorization)

| Data | Provisional class | Required decision before action |
|---|---|---|
| Open/active `tickets` and the minimum teacher assignment data they reference | Candidate to migrate | Define active status, target schema/system, identity mapping, cutover and validation owner |
| Closed tickets and records required for audit, user commitments, or approved analytics | Candidate to archive | Establish lawful purpose, access controls, retention period and provider backup relationship |
| `interaction_records` and `user_feedback` needed for an approved continuing purpose | Candidate to archive or migrate in minimized form | Privacy review of free text/model output, consent/purpose, minimization, deletion requests and retention |
| Duplicate, orphaned, test, superseded, or purpose-expired records | Candidate to discard **only after retention review** | Legal/privacy approval, defensible identification rules, hold checks, deletion evidence and backup expiry |
| Teacher roster/contact and capacity configuration | Split candidate: migrate only currently required operational fields; archive/discard remainder | Confirm current roster authority, data owner, target identity source, accuracy and retention |

No row is a final collection-wide disposition. A collection can contain records in
several classes, and deletion is prohibited until the required reviews and holds
are resolved.

## Unresolved decisions

- Actual projects/environments, collections, subcollections, schemas, counts, and completeness.
- Business/data owners and which records remain operational.
- Future operational database and identity source; migration/cutover strategy.
- Required retention, legal holds, user deletion handling, and archive controls.
- Whether timestamps absent from current writers exist historically and how to date records safely.
- Whether provider-managed backup/export or point-in-time recovery exists and must be retained.
- Reconciliation criteria proving migration/archive completeness from hashed evidence.
- Treatment of corrupt, unknown-type, orphaned, duplicate, test, and partially exported records.

## Consequences

The repository gains a deterministic read-only evidence mechanism and an explicit
evidence gap. Raw personal data remains outside Git. No live export, migration,
archive, deletion, disaster-recovery claim, or future persistence choice is
authorized by this decision.
