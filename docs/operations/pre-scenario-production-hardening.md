# Pre-scenario production hardening

## Baseline and implementation plan

Work began from `d399e1330ff4e1b538b29c49b5cec5c2e8f614c1`. At that baseline, CI called
`make verify-sprint`, but also duplicated an unsafe container smoke in which the image entrypoint
silently migrated every web or worker invocation. Migration heads were `courses.0001_initial`,
`identity.0001_initial`, `support.0002_alter_humanhelpticket_priority_and_more`, and
`tutoring.0004_outboxevent_claim_expires_at_outboxevent_claimed_at_and_more`.

The compact plan was: (1) make the whole-sprint gate regression-tested and failure-cleaning; (2)
make migration ownership an explicit release/local bootstrap action; (3) separate process liveness,
database-and-schema readiness, and capability readiness; (4) document evidence and the stable
boundary for the later scenario-mode task. No scenario facility is part of this change.

## Release topology and canonical command model

Run commands from the repository root. These are the only current operational commands; phase
runbooks and closure documents are historical evidence.

| Operation | Canonical command |
| --- | --- |
| Initialize an empty local PostgreSQL database | `docker compose up -d --wait db && docker compose run --rm migrate` |
| Apply migrations in a release job | `python manage.py migrate --noinput` |
| Check schema without changing it | `python manage.py migrate --check` |
| Run local web | `docker compose up --build app` |
| Run tutoring dispatcher | `TUTORING_ENABLED=1 docker compose --profile tutoring up --build dispatcher` |
| Validate authored content | `python manage.py validate_content .` |
| Build deterministic course bundle | `python manage.py build_content_bundle . --output ./build/content --source-commit "$(git rev-parse HEAD)"` |
| Publish a validated bundle | `python manage.py publish_content ./build/content` |
| Validate enrollment CSV | `python manage.py enroll_course_memberships enrollments.csv --dry-run` |
| Apply enrollment CSV | `python manage.py enroll_course_memberships enrollments.csv` |
| Human readiness report | `python manage.py production_readiness` |
| Automation release readiness | `python manage.py production_readiness --strict --json` |
| Non-billable tutoring staging proof | `python manage.py verify_tutoring_staging --user-id UUID --exercise-version-id UUID --idempotency-key UNIQUE-RUN-ID` |
| Optional billable tutoring proof | `TUTORING_LIVE_TEST=1 python manage.py verify_tutoring_staging --live --user-id UUID --exercise-version-id UUID --idempotency-key UNIQUE-RUN-ID` |
| Required release gate | `make verify-sprint` |
| Verify the final production runtime locally | `make verify-production-runtime` |

The live command is optional and must not run unless an operator deliberately supplies the applicable
provider credentials. The dispatcher command requires the complete queue/worker configuration
reported by readiness; do not guess it. Production web is the image's default Gunicorn command.

## Render pilot deployment contract

The pilot topology is one Docker-backed Render web service running Django/Gunicorn and inline
tutoring, connected to one managed Render PostgreSQL database and from the web process to Microsoft
Agent Framework/OpenAI. `render.yaml` is the canonical topology definition. **Applying that
Blueprint can create billable infrastructure**; committing or testing it provisions nothing. There
is intentionally no dispatcher, worker, Cloud Tasks resource, Redis/Celery service, or
support-notification delivery backend.

Render supplies `DATABASE_URL` from the Blueprint database and `RENDER_EXTERNAL_HOSTNAME` to the web
runtime. Production adds that hostname to `ALLOWED_HOSTS` and its HTTPS origin to
`CSRF_TRUSTED_ORIGINS`. Outside Render, operators must set `DJANGO_ALLOWED_HOSTS` (comma-separated
hostnames) and `DJANGO_CSRF_TRUSTED_ORIGINS` (comma-separated HTTPS origins). Wildcard hosts, blank
list members, non-HTTPS origins, and origins with paths fail startup. Existing HTTPS redirect,
secure-cookie, HSTS, and trusted-proxy settings remain enabled.

Required secrets are `DJANGO_SECRET_KEY` (platform-generated), `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, and `TUTORING_OPENAI_API_KEY`; the latter three are operator-entered
Blueprint secrets (`sync: false`). `DATABASE_URL` is database-derived and secret. Non-secret pilot
values are `DJANGO_SETTINGS_MODULE=evaluar.config.settings.production`, `TUTORING_ENABLED=1`,
`TUTORING_EXECUTION_MODE=inline`, `SUPPORT_ENABLED=1`, and `SUPPORT_NOTIFICATIONS_ENABLED=0`.
Optional `PORT` defaults to `8000`, `WEB_CONCURRENCY` to the conservative value `2`,
`GUNICORN_TIMEOUT` to `210` seconds (above the provider-policy maximum of 180), and
`GUNICORN_GRACEFUL_TIMEOUT` to `30` seconds. Gunicorn binds `0.0.0.0:$PORT`, logs to stdout/stderr,
and remains PID 1 through the exec-only entrypoint.

The image build runs deterministic `collectstatic` with non-secret base settings and verifies admin
CSS exists before switching to the non-root `evaluar` user. Production uses WhiteNoise compressed
manifest storage. Neither collection nor migration happens at web startup. Render's
`preDeployCommand` runs `python manage.py migrate --noinput` against the same image before release.
`/health/live` checks HTTP process liveness; `/health/ready` checks database connectivity and
migration state.

Run `make verify-production-runtime` from the repository root. It builds the image, starts fresh
PostgreSQL, proves the unmigrated web can become live but not ready and did not create migration
state, migrates separately, then starts on non-default port `8765` and checks both probes plus
`/static/admin/css/base.css` through WhiteNoise. It uses placeholders, with no Google/OpenAI call.
`make verify-sprint` invokes this same runtime proof.

After merge, a human must review the proposed Render plan/cost, enter the operator secrets,
configure the Google OAuth callback for the final HTTPS hostname, apply the Blueprint, inspect the
pre-deploy migration logs, and run:

```bash
curl --fail https://HOST/health/live
curl --fail https://HOST/health/ready
curl --fail https://HOST/static/admin/css/base.css
```

Before deployment, owners must approve billing, database region/plan/backups, custom domain and
OAuth consent/callback configuration, populate reviewed course and active prompt data, and authorize
a separately controlled provider smoke call. Cloud Tasks/queued execution, a dispatcher, and
support-notification delivery remain intentionally unconfigured.

### Rollback

Stop web and dispatcher writers, capture a PostgreSQL backup and current image identifier, deploy the
previous known-good image, and run that image's non-mutating schema/readiness checks before restoring
traffic. Never destructively reverse the additive identity, content, tutoring, support, audit, or
outbox tables to accommodate an older image. If compatibility with the previous image is unknown,
keep traffic stopped rather than assuming it.

The production image entrypoint only executes its supplied command. A release controller must run
the following command exactly once and must stop promotion if it fails:

```bash
python manage.py migrate --noinput
python manage.py production_readiness --strict --json
```

Web and dispatcher replicas start only after that job succeeds. Local initialization is safe to
repeat because ordinary Django migrations record their application.

## Probe semantics and go/no-go evidence

* `/health/live` proves only that the process can answer HTTP.
* `/health/ready` verifies database connectivity and that the checked-out application has no
  unapplied migration leaf. It does not claim that optional tutoring or notification paths work.
* `production_readiness` emits a human report by default and JSON with `--json`. Use `--strict` to
  fail automation on errors. It reports database, schema, active published content, prompt,
  provider credentials, all four Cloud Tasks/worker settings, audience consistency, ambiguous
  attempts, pending/oldest tutoring outbox, and support notification mode. Disabled optional
  capabilities are explicitly `disabled`, never `healthy`.

Tutoring, support tickets, and support notifications are independent, explicit safety switches and
all default off. Disabled tutoring and support routes return 404, while domain write/dispatch paths
also refuse new work; persisted history remains readable to operators through Django admin. Turning
a switch off does not delete, fail, or claim pending records.

This baseline deliberately selects the **no-delivery support notification contract**. There is no
email backend and `SUPPORT_NOTIFICATIONS_ENABLED=1` is therefore a release error. With delivery off,
support workflow events remain in the durable outbox, dispatch logs
`support.notification_not_configured`, and no UI claims that a notification was delivered. The
`NotificationSender` protocol remains the injection boundary for a later, separately tested backend.

For a deterministic tutoring proof against persisted staging enrollment and content, run:

```bash
python manage.py verify_tutoring_staging --user-id UUID --exercise-version-id UUID \
  --idempotency-key UNIQUE-RUN-ID
```

The default fake adapter performs no network call and emits one JSON report proving prompt policy,
submission, outbox dispatch, worker-domain processing, persisted response, retry deduplication, and
trace completeness. `--live` is rejected unless `TUTORING_LIVE_TEST=1`; rejection output lists the
required provider environment and expected machine-verifiable results rather than reporting a fake
pass.

For controlled course enrollment, prepare a UTF-8 CSV with the exact header
`course_slug,identity,role,status`, then validate before applying:

```bash
python manage.py enroll_course_memberships enrollments.csv --dry-run
python manage.py enroll_course_memberships enrollments.csv
```

`identity` is the user's email. If the Google-backed user already exists, the command creates the
course membership immediately; otherwise it stores a pending, course-scoped enrollment and resolves
it on that email's first real login. Repeating identical input is a no-op. Role downgrades require
`--allow-role-downgrade`; any invalid row rejects the entire batch.

Attach the candidate SHA printed by CI and the complete `make verify-sprint` output to promotion
evidence. A release is **NO-GO** if the gate fails, migrations fail, strict readiness reports an
error, or required operational owners have not reviewed warnings. Live billable provider tests
remain separately authorized with `TUTORING_LIVE_TEST=1`; the standard gate must not contact one.

## Scenario-mode readiness assessment

The next task can rely on production authentication remaining Google OIDC, enrollment remaining an
active persisted `CourseMembership`, and course policies remaining authoritative. It can rely on
immutable exercise/prompt versions, atomic complete publications, submission version pinning,
duplicate-safe queue boundaries, explicit ambiguous-attempt resolution, and append-only support
history. Scenario mode must be isolated from these production paths and must not alter their
configuration, records, migrations, entrypoint, probes, or release gate.

### Stable, evidenced boundaries

* **Authentication and authorization:** production authentication remains Google OIDC; active,
  course-scoped `CourseMembership` records and policy checks are the request boundary. The real
  two-course request test denies cross-course content, tutoring, and support access.
* **Enrollment reproducibility:** the strict CSV command can create real memberships or pending email
  grants and resolves pending grants only after a real matching login. It is atomic, audited, and
  idempotent. A future scenario facility must not reuse pending production grants as fake identity.
* **Course import:** deterministic compilation, atomic/idempotent publication, reused identifiers
  across courses, long Spanish/SQL/math rendering, and explicit HTML-table rejection are locally
  tested.
* **Tutoring extension point:** `TutoringModel`/factory injection is the adapter boundary. The staging
  verifier proves the fake adapter without network access; production remains refused when
  `TUTORING_ENABLED=0`, and live calls additionally require `TUTORING_LIVE_TEST=1`.
* **Feature refusal:** `TUTORING_ENABLED`, `SUPPORT_ENABLED`, and
  `SUPPORT_NOTIFICATIONS_ENABLED` default off. Middleware, domain services, worker, and dispatchers
  fail closed rather than relying on hidden UI.

### Safe future extension points and required tests

A future scenario implementation may add a test-only authentication backend, isolated fixture
loader, and fake tutoring factory only behind a scenario-specific settings module that production
cannot load. It must test production refusal, configuration isolation, persona-to-membership mapping,
two-course denial, immutable version references, queue replay, support history, and absence of
provider network calls. It must not add production URL bypasses, mutate historical rows, or weaken
policies.

### Blockers and conclusion

There is **no approved synthetic-user strategy in this revision**; designing and proving an isolated
one remains work for the scenario task. Docker/PostgreSQL, final image, final CI, and live tutoring
evidence remain unavailable as recorded in `docs/evidence/pre-scenario-readiness.md`. Therefore the
production release decision remains **NO-GO**, while the production boundaries are sufficiently
explicit for scenario-mode design to begin without using scenario mode to hide those missing release
results.
