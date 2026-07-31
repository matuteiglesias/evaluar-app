# ADR 0003: Legacy data migration and archival policy

- **Status:** Accepted policy; execution blocked on live Firestore evidence and named approvals
- **Date:** 2026-07-31
- **Depends on:** ADR 0002 and the five journey contracts

## Decision

Migration will be allowlisted by data family and purpose. Nothing is migrated
merely because it exists. The future application is not implemented in this
phase. PostgreSQL is the future operational store; Firestore remains unchanged in
GCP until a verified export is archived and all institutional retention controls
are satisfied. This ADR authorizes no deletion.

## Mandatory gates before any production migration

1. Run the read-only Firestore exporter with an approved least-privilege identity.
   Require `status=complete`, no incomplete reads, verified per-file/manifest
   SHA-256 values, project/environment confirmation, source commit, custody record,
   and a separately approved provider-managed backup/export where required.
2. Produce a privacy-reviewed sanitized profile with actual collection counts,
   fields/types, missing rates, timestamp coverage, subcollections and unknowns.
3. Name the institutional data owner, privacy/retention approver, academic content
   owner, security owner, migration operator and acceptance-test owner.
4. Resolve every `owner-decision-required` row in the migration inventory. Legal
   holds override archive expiry or discard plans.
5. Define PostgreSQL schema, constraints, transactions, immutable legacy keys,
   course-scoped exercise foreign keys, provenance columns and reconciliation queries.
6. Demonstrate encrypted backups, restore, rollback and restricted archive access.

## Migration waves

### Wave A — authored content

Copy the 2 course namespaces, 110 metadata rows, 110 exact bodies and 7 referenced
exercise images from the content manifest's hashed Git source. Preserve bytes,
slugs, IDs and global keys. Do not deduplicate the repeated IDs or identical
bodies. Editorial conflicts may block publication but not evidence preservation.

Validation: regenerate the content manifest byte-for-byte; compare every row,
body and asset SHA-256; run the browse journey for both courses, especially the
same numeric ID in different courses.

### Wave B — identity and operational access

Create PostgreSQL users only after a successful Google authentication or an
explicit institution-controlled provisioning event. Store Google subject as the
external key; provision local membership/role separately with issuer, effective
period and audit provenance. Never import the Firestore teacher roster or ticket
assignee as authorization.

Validation: uniqueness and foreign-key checks plus authenticate/course-access
journey tests. Institution-approved membership fixtures must cover allowed and
denied access once policy exists.

### Wave C — open teacher-help work

After live profiling and owner definition of “operational,” select only qualifying
legacy tickets. Transform them into generic unassigned PostgreSQL help packets.
Preserve legacy record/path provenance in a restricted reconciliation mapping,
retain course and exercise separately, and flag missing/ambiguous course rather
than guessing. Do not migrate `teacherId` into authorization or assignment.

Validation: source selection count/hash, rejected-row report, one-to-one target
mapping, status/cutoff checks and the generic teacher-help journey. Closed and
expired records remain encrypted archive only.

### Wave D — historical AI and feedback

Default action is encrypted archive only. A separate approved analytical project
may select and de-identify records after documenting lawful purpose, minimization,
free-text risk, small-group suppression, re-identification testing, retention and
deletion handling. Removing direct identifiers alone is not sufficient because
questions and responses can identify people.

Validation: approved selection specification, aggregate reconciliation, privacy
tests and proof that no direct lookup key or raw text crosses into analytics unless
explicitly approved. Unknown legacy prompt/model metadata stays null/unknown.

### Wave E — prompts, configuration and secrets

Move the current template and inline fallback into an explicitly versioned Git
prompt policy only after academic review. New interactions store prompt hash,
prompt version, model ID and generation parameters. Migrate only reviewed
non-secret configuration. Re-provision and rotate secrets in managed secret
storage; never copy credential files or tokens from an export.

Validation: Git hash review, prompt rendering fixtures, deployment configuration
diff, secret scanning, rotation evidence and journey tests with fakes before live checks.

## Archive-only controls

Raw Firestore evidence is stored outside Git in encrypted, access-logged archival
storage. The application-level NDJSON exporter is not automatically a disaster-
recovery backup. Archive custody records bind project, environment, export
manifest hash, provider backup reference, operator, approvals and retention class.

Teacher roster, assignment history, closed tickets, historical interactions,
responses and feedback remain archive-only unless an allowlisted exception above
is approved. Generated documentation is reproducible and is not a data archive.

## Transformation rules

- Preserve source identifiers as provenance, never as implicit future authority.
- Require course plus exercise ID; quarantine missing/ambiguous course links.
- Preserve original timestamps and timezone semantics; never invent absent dates.
- Record transformation version, source manifest hash, target batch ID and result.
- Normalize only in explicit target columns; retain raw archival bytes separately.
- Use deterministic, restartable transforms and uniqueness constraints.
- Produce accepted, rejected and quarantined counts whose total reconciles to source.
- Do not place raw records or identifier mappings in Git, CI logs or issue trackers.

## Deletion and discard policy

No legacy record, GCP Firestore database, export, backup, teacher record,
credential, or generated artifact is destroyed by this phase. “Discard” means
eligible only after the institution records retention expiry, legal-hold clearance,
data-owner/privacy/security approval, archive/backup scope and deletion evidence.
Until then, the action is archive or unresolved—not delete.

## Migration acceptance

The future system must pass the five no-network journey tests against PostgreSQL
adapters and then environment-specific integration tests. It must reproduce
course-scoped content hashes; authenticate through Google while enforcing local
PostgreSQL roles/memberships; record prompt/model provenance; bind feedback to an
exact response; create generic unassigned teacher packets; and exhibit the
documented failure side effects. Reconciliation and privacy approvals are equally
required—passing UI tests alone is insufficient.

## Current blockers

- No live Firestore export manifest or provider backup evidence is available.
- Every Firestore record count and runtime schema remains unknown.
- Ticket operational cutoff, memberships/roles, retention, analytics purpose,
  prompt policy and content conflicts need named owner/institution decisions.

These are explicit evidence gaps, not zero counts and not permission to omit data.
