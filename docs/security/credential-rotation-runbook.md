# Credential rotation runbook

This is a manual owner/operator procedure. Creating this runbook does **not**
rotate any credential. Never paste secret values into tickets, chat, logs, commit
history, or command output captured by CI.

## Preparation and safe rollout

1. Identify the secret manager and every active environment, worker, scheduled
   task, and developer integration using the credential. Record credential IDs,
   not values.
2. Confirm there is an authorized operator, a maintenance window, tested health
   and authentication checks, and a rollback owner. Back up configuration
   metadata, never plaintext secrets.
3. Prefer an overlap rollout: create a new credential, store it as a new secret
   version, deploy it, verify it, then disable the old credential. Where overlap
   is impossible (notably Flask session signing), announce the forced logout.
4. Roll back by selecting a still-active prior secret-manager version only if it
   is not suspected compromised. Never reactivate a compromised credential;
   instead correct the deployment and issue another credential.

## OpenAI API key

1. Create a new project-scoped key in the OpenAI administrative console with the
   minimum required project permissions and spend controls.
2. Update `OPENAI_API_KEY` in the deployment secret manager and restart/roll the
   application without printing the value.
3. Submit one authorized exercise answer and verify a successful evaluation plus
   expected OpenAI project usage/telemetry. Verify failure logs contain no key or
   response token.
4. Revoke the old key in the OpenAI console. Confirm an isolated request using
   the old key is rejected, then monitor error and spend dashboards.

## Google OAuth client secret

1. In Google Cloud Console, verify authorized origins/redirect URIs, then create
   or reset the OAuth client secret according to Google's supported overlap model.
2. Update `GOOGLE_CLIENT_ID` if required and `GOOGLE_CLIENT_SECRET` in the secret
   manager; deploy all instances together.
3. Complete a new incognito login, verify state validation/callback success and
   logout, and inspect only status-level logs.
4. Disable/delete the old secret when Google permits. Confirm the old value can no
   longer exchange a test authorization code. Do not log codes, tokens, complete
   callback URLs, or authorization responses.

## Flask session secret and session invalidation

1. Generate at least 32 cryptographically random bytes and encode them for
   `SECRET_KEY`; do not derive it from another credential.
2. Schedule a coordinated deployment because changing this value invalidates all
   signed sessions. Stop or drain old instances so old and new signing keys do not
   coexist unpredictably.
3. Delete the server-side filesystem session directory/store entries and deploy
   the new value to every instance. Users must authenticate again.
4. Verify old cookies are rejected and a new login produces a cookie with Secure,
   HttpOnly, and the intended SameSite attribute. Retire the previous secret
   version after the rollback window unless compromise requires immediate removal.

## Firebase service-account key or workload identity

Prefer Application Default Credentials with workload identity and no exported key.

1. For workload identity, update the workload/service-account binding, deploy,
   verify the intended Firestore operations, then remove the old binding.
2. If an exported key is unavoidable, create a new key for the least-privileged
   service account, place it in the platform secret/file mount outside the
   repository, and update `GOOGLE_APPLICATION_CREDENTIALS`. Never log its path or
   JSON content.
3. Deploy and verify health, one fake-safe operational read/write workflow, and
   Cloud Audit Logs. Delete the old key in IAM and confirm its key ID is disabled
   and an isolated old-key authentication attempt fails.
4. Remove old mounted files and secret versions from every host, image, CI store,
   and developer machine. If a key entered Git history, treat it as compromised,
   revoke it immediately, and separately coordinate history remediation.

## Completion record

For each rotation, record operator, time, affected environments, non-secret old
and new credential IDs, deployment version, verification results, revocation
evidence, session invalidation status, and rollback disposition. External
credential rotation remains pending until the repository owner performs and
records these steps.
