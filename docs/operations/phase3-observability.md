# Phase 3 operational signals and alerts

`python -m django tutoring_operational_status --json` emits database-authoritative signals. Application
logs additionally emit `tutoring.task_enqueued`, `tutoring.worker_attempt`,
`tutoring.agent_invocation`, `tutoring.outbox_dispatch_failed`, and failed worker HTTP 401 responses.
Raw prompts, student answers, and model responses are prohibited in telemetry.

| Signal | Recommended warning | Recommended critical |
|---|---:|---:|
| oldest queued submission | > 60 seconds for 5 minutes | > 300 seconds |
| queue delay | p95 > 60 seconds | p95 > 300 seconds |
| retryable provider failures | > 5% over 10 minutes | > 20% over 10 minutes |
| terminal failures | > 1% over 15 minutes | > 5% over 15 minutes |
| ambiguous attempts | any for 5 minutes | any for 30 minutes |
| pending outbox events | > 10 for 5 minutes | oldest > 10 minutes |
| provider timeout/rate limits | > 5% over 10 minutes | > 20% over 10 minutes |
| schema-validation failures | any after a prompt/model release | > 1% over 15 minutes |
| estimated daily cost | 75% of budget | 90% of budget |
| failed worker authentication | any | > 5 in 5 minutes |
| submissions over normal processing time | > 5 | > 25 |

Token totals and estimated cost are calculated from persisted attempt usage and the immutable prompt's
price policy. Alert evaluation belongs in the existing log/metrics backend; this design does not require
a new monitoring stack.
