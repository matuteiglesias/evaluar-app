# Phase 0A: reproducible legacy baseline

## Files changed

- `pyproject.toml`: supported Python range, direct runtime dependencies, and a
  separate development group.
- `main.py` and `services/firebase.py`: test configuration overrides and one
  lazy Firebase extension.
- `routes/exercises.py`, `routes/teachers.py`, and `services/teachers.py`:
  Firestore is resolved at request/service execution rather than import time.
- `tests/test_app.py`: app, health, route-map, disabled-Firebase, and network
  containment tests.
- `env.template`, `.gitignore`, and `CONTRIBUTING.md`: configuration and clean
  installation instructions.

## Dependency decisions

Imports in `routes/`, `services/`, `models/`, `llm/`, `scripts/`, and `tests/`
were compared with the last historical `requirements.txt` (commit `2d4a3ae`).
The runtime list retains the imported Flask, OAuth, Firebase, OpenAI, Markdown,
pandas, dotenv, and HTTP libraries, plus Gunicorn from the historical deployment
contract. Google API client, `google-auth-httplib2`, `uritemplate`, PyJWT, and
CacheControl were not retained as direct requirements: there are no direct
imports, and any needed versions are resolver-managed transitives. Pytest,
pytest-mock, and Ruff are development-only. OpenAI is constrained to its 1.x API
because the current evaluator uses `openai.chat.completions`.

Python 3.10 through 3.13 is supported. Python 3.14 is excluded pending upstream
compatibility validation.

## Commands executed and results

The intended clean verification is:

```bash
python3.12 -m venv /tmp/evaluar-phase-0a
source /tmp/evaluar-phase-0a/bin/activate
python -m pip install --upgrade pip
python -m pip install uv
uv sync --locked --group dev
pytest
ruff check .
ruff format --check .
```

During development, `uv lock` and `uv lock --offline` were also executed. The
online package index was unavailable through the environment proxy, while the
local resolver cache did not contain Authlib. This environmental limitation is
recorded rather than treating an arbitrary pre-existing environment as the
dependency source.

Consequently, a resolved `uv.lock` could not be generated or honestly committed
in this environment, and the clean-install/test acceptance sequence remains
blocked. Run `uv lock`, commit its output, and execute the clean verification
above from a network-enabled environment before merging this baseline.

## Deliberately unresolved risks

- OAuth callbacks and LLM/Firestore operations still require integration tests;
  baseline tests intentionally never contact those systems.
- Existing route authorization, input validation, exception handling, and
  credential-management issues remain for later Phase 0 hardening.
- The filesystem session backend and global OAuth client are retained to avoid
  changing legacy behavior.
- Firestore collection and document names are unchanged; no schema migration is
  included.
