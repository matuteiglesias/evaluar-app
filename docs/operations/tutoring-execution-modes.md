# Tutoring execution modes

Evaluar has one tutoring domain flow and two delivery modes. Select the mode with
`TUTORING_EXECUTION_MODE=inline|queued`.

## Inline

`inline` executes the configured tutoring model during the student's POST request. The submission,
quota reservation, attempt, model trace, and response are still persisted through the same domain
services used by the worker path, but no tutoring outbox event is created.

This mode is the default under `evaluar.config.settings.local` and is appropriate for local
development and small deployments where the expected model latency fits comfortably inside the HTTP
request timeout. The web process must have the provider credentials required by the active prompt,
for example `TUTORING_OPENAI_API_KEY` for an OpenAI prompt policy.

A retryable provider failure is terminal for that inline request. The student sees the existing
non-technical failure state and can submit a new attempt; inline execution never leaves a request
waiting for a queue that does not exist.

## Queued

`queued` is the base and production-safe default. Student submission commits a durable outbox event,
the dispatcher sends that event to Cloud Tasks, and the authenticated worker executes the same
`run_submission` service. Queue retries remain bounded and retain the existing ambiguity protections.

Queued mode requires `TUTORING_TASK_QUEUE_PATH`, `TUTORING_WORKER_URL`,
`TUTORING_TASK_AUDIENCE`, and `TUTORING_TASK_SERVICE_ACCOUNT` in addition to the provider
configuration.

## Readiness contract

`production_readiness` is execution-mode aware. Missing Cloud Tasks configuration is an error only
when `queued` is selected. Provider credentials and an active published prompt are required in both
modes. Pending historical outbox records remain visible as an operational warning even in inline
mode so operators can clean up state left by an earlier queued configuration.

The setting rejects values other than `inline` and `queued` at settings load time. Changing execution
mode does not rewrite historical submissions or prompt versions.
