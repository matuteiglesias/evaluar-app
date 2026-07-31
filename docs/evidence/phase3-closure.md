# Phase 3 closure evidence

Evidence date: 2026-07-31 UTC

## Release candidate

| Item | Evidence |
|---|---|
| release implementation commit | `a4df194` (`Add Phase 3 operational release controls`) |
| migration head | `tutoring/0003_activeprompt_tutoringoperationalaudit_and_more.py` |
| migration drift | none (`makemigrations --check --dry-run`) |
| canonical non-live gate | PASS, 46 tests plus lint, format, mypy, and migration checks |
| live staging gate | PENDING; deliberately not executed without billable staging credentials |
| active prompt | environment-owned; no production database was available in this workspace |
| active model policy | stored on the environment's selected immutable `PromptVersion`; pending selection |
| Agent Framework pins | `agent-framework-core==1.13.0`; `agent-framework-openai==1.12.0` |

Canonical evidence command:

```bash
make verify-phase3
```

The live command and acceptance thresholds are in the [runbook](../operations/phase3-runbook.md).
Live staging remains optional for ordinary CI but must be explicitly accepted as pending or executed by
the release owner before production traffic is enabled.

## Completed release properties

- PostgreSQL owns submissions, immutable prompt references, attempts, responses, feedback, quotas,
  outbox state, and manual-recovery audit records.
- Duplicate submissions do not consume quota twice. Student/course reservations and outbox creation are
  transactional. Dispatch retries and manual requeue do not consume another reservation.
- Cloud Tasks payloads contain only the submission identifier; worker delivery is authenticated and
  duplicate-safe.
- Provider calls have structured output, timeout and projected-cost ceilings, stable failure taxonomy,
  usage capture, and sensitive telemetry disabled.
- Ambiguous provider-success attempts cannot automatically issue a second provider call. Terminal,
  evidence, and retry decisions require an identified operator, note, and durable audit event.
- Prompt/model rollback moves an audited `ActivePrompt` pointer between immutable versions. Historical
  submissions continue referencing their original version.
- Framework rollback is a lockfile change followed by the complete non-live gate. Historical attempts
  retain the framework version used at execution.

## Known limitations

- Live staging results are pending in this environment because credentials and permission for billable
  calls were not provided.
- The production active prompt/model cannot be reported without access to the production database. It
  must be selected with `activate_tutoring_prompt` during deployment.
- Provider evidence can be attached to an ambiguous attempt, but Phase 3 does not reconstruct a missing
  response from provider storage automatically.
- Retention is policy-only in Phase 3; automatic destructive deletion is intentionally disabled.
- No streaming, tools, sessions, MCP, multi-agent workflow, retrieval, or human-support workflow exists.
  Human support remains Phase 4.

## Rollback summary

1. Route web and worker traffic to their previous Cloud Run revisions.
2. Do not reverse additive migrations while Phase 3 records exist.
3. Restore the previous prompt/model with `activate_tutoring_prompt`.
4. If required, restore prior Agent Framework pins with `uv add --optional ai ...`, run
   `make verify-phase3`, commit the lockfile, and deploy.
5. Pause Cloud Tasks during provider outages; retain authoritative queued state in PostgreSQL.

The exact commands are verified and documented in the [Phase 3 runbook](../operations/phase3-runbook.md).

## Go/no-go decision

**GO for staging and operational validation. CONDITIONAL NO-GO for production traffic in this workspace.**

The non-live release gate is complete. Production traffic requires the release owner to record the active
prompt/model selection, confirm migrations against the target database, and either pass the live staging
gate or explicitly accept it as pending. These are environment release decisions rather than missing code.

> Phase 3 delivers a durable asynchronous tutoring workflow with immutable content and prompt references,
> bounded provider execution, authoritative PostgreSQL state, duplicate-safe queue processing, structured
> Agent Framework output, quota and cost controls, student-facing status and feedback, and explicit
> operational recovery and rollback procedures. Human support remains Phase 4.
