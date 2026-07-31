# Phase 0B: ingress controls

## Implemented controls

- `login_required` protects course discovery, course indexes, exercise content,
  AI submissions, feedback, teacher escalation, and confirmation. Public routes
  remain the landing page, OAuth entry/callback, logout, health, and static assets.
- Course names accept only lowercase ASCII letters, digits, `_`, and `-` (maximum
  64 characters). A course must be a direct child of `EXERCISES_ROOT` with a valid
  `index.csv`. Exercise files must be exact index entries and direct regular-file
  children of that course after canonical resolution. Invalid and unknown paths
  return 404 without exposing filesystem locations.
- Flask-WTF applies global CSRF validation. All three mutating forms include the
  application CSRF token, including the AJAX feedback form through serialization.
- Flask-Limiter limits login attempts, AI answers, feedback, and teacher-help
  requests. Authenticated keys use `session.user.id_`; other keys use the direct
  `request.remote_addr`. Forwarded headers are deliberately not trusted.
- Inputs are stripped before validation. Empty or overlong values are rejected
  before evaluator or database access. Flask enforces the total request limit.

## Defaults

| Control | Default |
| --- | ---: |
| Total request body | 65,536 bytes |
| Student answer | 8,000 characters |
| Teacher question | 2,000 characters |
| Feedback | 2,000 characters |
| Login | 10/minute |
| AI answer | 5/minute |
| Feedback | 10/minute |
| Teacher help | 5/minute |

All values are configurable through the matching environment/application config
names documented in `env.template`.

## Residual risks

- The default `memory://` rate-limit store is process-local and is suitable only
  for tests and local development. A shared production backend is required for
  consistent limits across workers or instances.
- Session storage remains filesystem-based. Proxy trust is intentionally absent;
  deployment must explicitly configure trusted proxy handling before client IP
  forwarding can safely influence limits.
- OAuth, OpenAI, and Firestore remain external systems. Tests use fake evaluator
  and database adapters and never contact them.
- CSRF failures use Flask-WTF's standard controlled 400 response; request bodies
  over 65,536 bytes use Flask's standard 413 response.
