# Phase 0 verification

## Implemented controls

- Phase 0A introduced the application factory, lazy Firebase adapter, explicit
  dependency declarations, offline test configuration, and baseline tests.
- Phase 0B added authentication guards, indexed/canonical exercise lookup, CSRF,
  normalized input/body limits, per-user/direct-IP rate limits, and the teacher
  server-timestamp regression.
- Phase 0C added separate exercise/model sanitization allowlists, safe DOM metadata
  construction, and rendering injection regressions.
- Phase 0D centralizes validated runtime settings, secure cookie/debug defaults,
  conditional AI/OpenAI requirements, Firebase ADC support, Authlib-managed OAuth
  state, external timeouts/status checks, controlled malformed-response failures,
  and the credential-rotation runbook.

## Verification commands and observed results

| Command | Result |
| --- | --- |
| `ruff format --check .` | Passed. |
| `ruff check .` | Passed. |
| `python -m compileall -q main.py extensions.py routes services tests` | Passed. |
| `git diff --check` | Passed. |
| `python -m pytest -q` | Could not start: the available interpreter lacks Flask and other project dependencies. |
| `uv lock` | Failed: the environment proxy denied access to PyPI. No lock was invented from an arbitrary environment. |
| `pip-audit` | Unavailable; no vulnerability audit is claimed. |
| `gitleaks`, `detect-secrets`, `trufflehog` | Unavailable; no third-party secret scan is claimed. |
| `git grep -nE` for common private-key/token assignments | No candidate committed secret values found by this limited pattern check. This is not a substitute for a scanner. |

Because dependency installation and the full suite could not run in this
environment, the Phase 0 completion condition is **not yet verified**. A
network-enabled clean checkout must generate/commit the resolver lock, install
with `uv sync --locked --group dev`, run the entire suite (including production
startup failure, credential-independent test startup, and teacher timestamp),
then run `pip-audit` and an approved secret scanner before merge.

## Changed endpoints and behavior

- Protected course/exercise and mutation endpoints redirect anonymous users;
  missing CSRF receives 400, oversized bodies 413, and exceeded rates 429.
- Invalid course/exercise paths return 404. Empty/overlong input returns 400.
- `/submit_answer` returns 503 when `AI_EVALUATION_ENABLED=false`.
- Production/staging startup stops with a clear configuration error when the
  session secret, OAuth credentials, conditional OpenAI key, secure cookie, or
  valid SameSite setting is missing. Debug defaults off.
- OAuth callback upstream/malformed failures return controlled 400/502 responses.
- Firebase uses an explicit configured credential path or Application Default
  Credentials; there is no repository-relative key fallback.

## Residual risks and manual actions

- Filesystem sessions do not provide robust shared multi-instance lifecycle.
- LLM calls are synchronous, and Firestore remains the operational store.
- OAuth state is managed coherently by Authlib, but full OIDC nonce/ID-token
  validation is not introduced; the flow still depends on Google's userinfo API.
- The default in-memory rate-limit store is not multi-instance safe.
- Teacher assignment/workflow remains incomplete, and no production deployment
  manifest or shared session/rate-limit backend is committed.
- Third-party CDN supply-chain controls and MathJax configuration need later review.
- The owner must create the resolved lock, run unavailable audits/scans, provision
  production secrets/workload identity, and execute deployment smoke tests.

**OpenAI, Google OAuth, Flask session, and Firebase external credential rotation
remains pending until performed and recorded by the repository owner using
`docs/security/credential-rotation-runbook.md`. No rotation is claimed here.**
