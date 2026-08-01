# Phase 3 tutoring operations runbook

All commands run from the repository root. Set `DJANGO_SETTINGS_MODULE=evaluar.config.settings.production`
and the documented production environment variables before operational commands.

## Release verification and deployment

```bash
make verify-phase3
uv run --extra ai --extra queue python -m django migrate --check
uv run --extra ai --extra queue python -m django migrate
gcloud run deploy "$WEB_SERVICE" --image "$IMAGE" --region "$REGION"
gcloud run deploy "$WORKER_SERVICE" --image "$IMAGE" --region "$REGION"
```

Do not route production traffic until `make verify-phase3` passes. Migrations are additive in Phase 3.
Rollback the application image with:

```bash
gcloud run services update-traffic "$WEB_SERVICE" --region "$REGION" --to-revisions "$PREVIOUS_REVISION=100"
gcloud run services update-traffic "$WORKER_SERVICE" --region "$REGION" --to-revisions "$PREVIOUS_WORKER_REVISION=100"
```

Do not reverse migrations while Phase 3 records exist.

## Outbox and queue health

```bash
uv run --extra queue python -m django dispatch_tutoring_outbox --limit 100
uv run --extra queue python -m django tutoring_operational_status --json
gcloud tasks queues describe "$QUEUE_ID" --location "$REGION"
gcloud tasks tasks list --queue "$QUEUE_ID" --location "$REGION" --limit 100
```

Run the outbox dispatcher repeatedly until `pending_outbox_events` is zero. A failed dispatch remains
pending and retains its error; it does not release or consume another quota reservation.

## Failed jobs and explicit requeue

Course administrators use `/tutoring/courses/<course-slug>/failed/`. The requeue button creates a new
outbox event but does **not** reserve quota again. The equivalent Django-admin action is **Requeue
selected failed tutoring submissions**.

## Ambiguous attempts

An attempt in `provider_succeeded` without a response is ambiguous. It is never automatically retried.

```bash
uv run python -m django list_ambiguous_tutoring_attempts
uv run python -m django resolve_ambiguous_tutoring_attempt \
  --attempt "$ATTEMPT_UUID" --decision terminal --actor "$OPERATOR" \
  --note "Provider console checked; response unavailable"
uv run python -m django resolve_ambiguous_tutoring_attempt \
  --attempt "$ATTEMPT_UUID" --decision attach-evidence --actor "$OPERATOR" \
  --provider-request-id "$PROVIDER_REQUEST_ID" --note "Provider completion confirmed"
uv run python -m django resolve_ambiguous_tutoring_attempt \
  --attempt "$ATTEMPT_UUID" --decision retry --actor "$OPERATOR" \
  --note "Explicit duplicate-cost risk accepted"
```

Every decision creates `TutoringOperationalAudit`. `retry` is the only decision that authorizes another
provider call.

## Prompt and model rollback

Create and publish prompt material through the audited commands. Publication calculates the checksum
and creates an immutable historical row; it does not activate that row:

```bash
uv run python -m django create_tutoring_prompt --public-id default \
  --instructions-file prompt.md --model-policy-file policy.json --actor "$OPERATOR"
uv run python -m django publish_tutoring_prompt --public-id default --prompt-version 7 \
  --actor "$OPERATOR" --note "Approved after staging regression"
```

Activate a published replacement or restore a previous version by moving the separately audited
pointer:

```bash
uv run python -m django activate_tutoring_prompt --public-id default --prompt-version 7 \
  --actor "$OPERATOR" --note "Release approved prompt 7"
uv run python -m django activate_tutoring_prompt --public-id default --prompt-version 6 \
  --actor "$OPERATOR" --note "Rollback after staging regression"
```

Create a new prompt version to change model policy; never edit a historical row. Existing submissions
retain their original prompt/model policy.

## Outbox dispatcher

Run exactly one or more dispatcher instances continuously. Each event is leased in PostgreSQL before
the Cloud Tasks network call, and expired leases are reclaimable after a process crash:

```bash
python -m django dispatch_tutoring_outbox --watch --interval 60
```

The `dispatcher` Compose service provides this topology under the `tutoring` profile. In GCP, deploy
the same image and command as a continuously running service, or invoke the command as a Cloud Run Job
every minute with Cloud Scheduler. Multiple instances are safe because claims use locked rows.

Before promotion, run the non-billable release gate in the configured production environment:

```bash
python -m django check_tutoring_release --strict
```

## Framework rollback

The framework is pinned in `pyproject.toml` and `uv.lock`. On a release branch:

```bash
uv add --optional ai "agent-framework-core==$PREVIOUS_CORE_VERSION" \
  "agent-framework-openai==$PREVIOUS_OPENAI_INTEGRATION_VERSION"
make verify-phase3
git add pyproject.toml uv.lock
git commit -m "Revert Agent Framework versions"
```

Deploy that commit using the normal deployment procedure. Historical attempts retain the framework
version recorded at execution.

## Provider outage and credentials

During an outage, leave queued submissions authoritative in PostgreSQL, pause queue delivery, and keep
dispatching disabled:

```bash
gcloud tasks queues pause "$QUEUE_ID" --location "$REGION"
gcloud tasks queues resume "$QUEUE_ID" --location "$REGION"
```

Rotate provider credentials in the runtime secret store, deploy a new revision, verify it in staging,
then revoke the old credential. Never print credentials or place them in Django, task, or provider logs.

## Billable staging gate

```bash
TUTORING_LIVE_TEST=1 \
TUTORING_LIVE_MODEL="$STAGING_MODEL" \
TUTORING_LIVE_INPUT_USD_PER_MILLION="$INPUT_RATE" \
TUTORING_LIVE_OUTPUT_USD_PER_MILLION="$OUTPUT_RATE" \
make verify-phase3-live
```

Pass criteria: every structural assertion passes; no system prompt is disclosed; rendered output remains
sanitized; token and served-model metadata are present; no case exceeds its configured cost ceiling; and
timeout/malformed-output tests remain bounded. Billable tests are never part of ordinary CI.
