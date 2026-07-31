# Current failure semantics

## HTTP and side-effect matrix

| Condition | Status/response | Durable side effect | Session effect | Retry meaning |
|---|---|---|---|---|
| Anonymous protected request | Redirect to login | None | None | Authenticate first |
| Identity provider rejects/fails | 502 authentication failure | None | No user session | Retry provider flow |
| Missing/blank form identity or text | 400 | None | Existing valid state retained unless noted | Correct input |
| Configured text limit exceeded | 400 | None | Existing state retained | Shorten text |
| Unknown/unsafe course or exercise | 404 | None | None | Select indexed identity |
| AI disabled | 503 | None | No response state created | Operator action required |
| Tutor fails | 502 controlled message | No interaction | No response state created | Safe to retry |
| Tutor succeeds, interaction persistence fails | 503 controlled message | No claimed interaction | New response state cleared | Retry may call model again |
| Feedback response/course/exercise mismatch | 409 | No feedback | Current response state retained | Submit only matching form |
| Feedback state stale/already consumed | 409 | No feedback | None | Generate a new response |
| Feedback persistence fails | 500 JSON error | No claimed feedback | Matching state retained | Safe to retry persistence |
| Teacher packet persistence fails | 500 | No claimed packet | No confirmation packet created | Safe to retry; ID may differ |

No route intentionally persists an interaction when the model fails. A model
success followed by uncertain storage is not reported as success. Adapter
implementations must either confirm one write or raise; future PostgreSQL writes
should use transaction/uniqueness constraints for response, feedback, and packet IDs.

## Atomicity and idempotency gaps

The legacy Firestore adapter performs individual document writes. The application
does not yet provide a client idempotency key, so network ambiguity after a write
could cause a retry with a new ID. Deterministic IDs exist only in tests. PostgreSQL
migration design must specify transactions, unique constraints, retry tokens, and
how to reconcile archived Firestore records.

Session correlation prevents a second accepted feedback in one session after a
successful write. It is not a durable global uniqueness guarantee; PostgreSQL
must enforce the intended one-rating policy (if retained) independently.

## Logging and disclosure

Controlled responses do not expose provider, model, or database exception text.
Server logs may record stack traces and therefore require restricted access and
retention. User questions, model responses, feedback, email addresses, provider
subjects, and packet contents must not be placed in routine diagnostic logs.
