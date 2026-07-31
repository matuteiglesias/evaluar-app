# Phase 3 data retention and quota policy

## Quota semantics

Acceptance reserves one unit from both the per-student/per-course daily quota and the aggregate course
daily quota. The submission, both reservations, and outbox event commit atomically. An idempotent replay
returns the original submission and consumes neither quota again. Dispatch failure retains the reservation
because the accepted request remains repairable. Automatic delivery/provider retries and manual requeue
do not reserve additional quota. A new student submission with a new idempotency key reserves new quota.

## Retention schedule

| Data | Default retention | End-of-period action |
|---|---:|---|
| student answers | 365 days after course end | delete content after ownership/legal review; retain submission identifier and state |
| rendered/structured model responses | 365 days after course end | delete content with the associated answer |
| provider request/model/framework metadata | 24 months | retain identifiers/checksums needed for audit; remove provider-only detail afterward |
| token and estimated-cost records | 24 months | aggregate for finance, then delete per-attempt token counts where permitted |
| student feedback | 24 months | anonymize user reference where policy permits; retain aggregate outcome |
| failed/ambiguous attempts | 24 months | retain state, error category, and manual-decision link; redact error detail |
| operational audit events | 7 years | immutable retention; never cascade-delete referenced integrity records |
| application traces and logs | 30 days | delete through telemetry-backend lifecycle policy |

No automatic destructive command is enabled in Phase 3. A future `purge_tutoring_content` command must
implement course ownership/legal holds, dry-run output, referential-integrity tests, and an audited approval.
Telemetry must not contain raw student answers, prompt instructions, exercise bodies, or model responses by
default. Database audit identifiers and immutable checksums remain when content is deleted or anonymized.
