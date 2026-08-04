# Pre-scenario readiness evidence

Recorded 2026-08-04 UTC in `/workspace/evaluar-app`.

## Observed revision and checks

* Revision observed before this evidence update: `a9990b4`. The final revision containing this file
  is not embedded because a commit cannot contain its own SHA; CI must record it with
  `git rev-parse HEAD`.
* Migration drift: `python -m django makemigrations --check --dry-run` reported no changes after
  adding the `identity.0002_pendingcourseenrollment` migration.
* Migration heads observed in the repository: `courses.0001_initial`,
  `identity.0002_pendingcourseenrollment`,
  `support.0002_alter_humanhelpticket_priority_and_more`, and
  `tutoring.0004_outboxevent_claim_expires_at_outboxevent_claimed_at_and_more`.
* Targeted enrollment, feature enforcement, multi-course request isolation, content rendering, and
  readiness tests: 13 passed locally.
* A fresh local SQLite database applied every migration through
  `identity.0002_pendingcourseenrollment`, `support.0002`, and `tutoring.0004` successfully.
* `production_readiness --json` against that migrated empty database reported healthy database and
  schema, a content warning, and tutoring, support, and notifications explicitly disabled. This was
  a local SQLite result, not a deployed-environment result.
* `make verify-sprint` ran its local stage: 98 tests, Ruff, formatting, mypy, and migration drift
  passed. The command then exited 127 at the PostgreSQL stage because `docker` was not installed; no
  later image or smoke stage ran.
* PostgreSQL-specific test: **not executed in this update**; Docker is unavailable in this
  environment.
* Production image build: **not executed in this update**; Docker is unavailable in this
  environment.
* GitHub Actions result for the final revision: **not observed**.
* Live tutoring staging: **not executed**. No billable provider call was authorized.

## Observed default capability state

The production settings source defaults `TUTORING_ENABLED=0`, `SUPPORT_ENABLED=0`, and
`SUPPORT_NOTIFICATIONS_ENABLED=0`. No deployed runtime configuration was inspected. Tutoring and
support therefore have a source default of disabled; this is not evidence of a particular deployed
environment's state. Support uses the explicit no-delivery contract and has no production delivery
backend in this revision.

## Known gaps

* The final candidate has not completed the Docker/PostgreSQL whole-sprint gate in this environment.
* No final-candidate CI run, production image, PostgreSQL migration run, container readiness smoke,
  or live-provider staging result was observed.
* Pending enrollment resolution is exercised through the allauth login signal locally; no external
  Google OIDC login was performed.

## Rollback steps

1. Stop web and dispatcher writers.
2. Capture a PostgreSQL backup and the currently deployed image identifier.
3. Deploy the previous known-good image.
4. Do not destructively reverse additive identity, tutoring, or support history tables.
5. Run that image's schema/readiness checks before restoring traffic.

## Go/no-go

**NO-GO.** Local tests are positive evidence, but the required final-candidate CI,
PostgreSQL-specific checks, production image build, migration execution, and container smoke were
not observed. No inference of success is made for those steps.
