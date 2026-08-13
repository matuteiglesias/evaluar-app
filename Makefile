.PHONY: verify-phase3 verify-phase3-live verify-sprint verify-sprint-local \
	verify-sprint-postgres verify-sprint-image verify-sprint-smoke migrate check-schema \
	verify-production-runtime

verify-phase3:
	uv run --extra ai --extra queue --group dev pytest -q -m "not live" tests/test_packaging_layout.py tests/test_content_pipeline.py tests/test_content_inventory.py tests/test_django_phase2.py tests/test_tutoring.py tests/test_tutoring_queue.py tests/test_agent_framework_adapter.py tests/test_agent_framework_production.py tests/test_tutoring_student_experience.py tests/test_tutoring_operations.py tests/test_tutoring_release.py
	uv run --extra ai --extra queue --group dev ruff check .
	uv run --extra ai --extra queue --group dev ruff format --check .
	uv run --extra ai --extra queue --group dev mypy src/evaluar/tutoring src/evaluar/courses
	uv run --extra ai --extra queue --group dev python -m django makemigrations --check --dry-run --settings=evaluar.config.settings.test

verify-phase3-live:
	@test "$${TUTORING_LIVE_TEST}" = "1" || (echo "Set TUTORING_LIVE_TEST=1 to authorize billable staging calls." && exit 2)
	uv run --extra ai --group dev pytest -q -m live tests/test_tutoring_live_staging.py

SPRINT_TESTS = tests/test_packaging_layout.py tests/test_content_pipeline.py \
	tests/test_content_inventory.py tests/test_django_phase2.py tests/test_tutoring.py \
	tests/test_tutoring_queue.py tests/test_agent_framework_adapter.py \
	tests/test_agent_framework_production.py tests/test_tutoring_student_experience.py \
	tests/test_tutoring_operations.py tests/test_tutoring_release.py tests/test_support.py \
	tests/test_support_notifications.py tests/test_sprint_acceptance.py

# This test is intentionally part of the gate: it prevents CI from regressing to
# the narrower phase-3 target.
SPRINT_TESTS += tests/test_release_engineering.py tests/test_production_readiness.py
SPRINT_TESTS += tests/test_feature_safety.py
SPRINT_TESTS += tests/test_batch_enrollment.py tests/test_multi_course_acceptance.py
SPRINT_TESTS += tests/test_course_collection_onboarding.py tests/test_collection_publication_contracts.py
SPRINT_TESTS += tests/test_runtime_deployment.py

verify-sprint: verify-sprint-local verify-sprint-postgres verify-sprint-image verify-sprint-smoke
	@mkdir -p artifacts
	@{ echo "verified_commit=$$(git rev-parse HEAD)"; \
	   echo "verified_at_utc=$$(date -u +%Y-%m-%dT%H:%M:%SZ)"; \
	   echo "image_id=$$(cat artifacts/evaluar-app.iid 2>/dev/null || echo unavailable)"; \
	 } > artifacts/sprint-verification.txt
	@echo "Sprint verification passed. Evidence: artifacts/sprint-verification.txt"

verify-sprint-local:
	uv run --extra ai --extra queue --group dev pytest -q -m "not live and not postgres" $(SPRINT_TESTS)
	uv run --extra ai --extra queue --group dev ruff check .
	uv run --extra ai --extra queue --group dev ruff format --check .
	uv run --extra ai --extra queue --group dev mypy src/evaluar
	uv run --extra ai --extra queue --group dev python -m django makemigrations --check --dry-run --settings=evaluar.config.settings.test

verify-sprint-postgres:
	@set -eu; \
		export COMPOSE_PROJECT_NAME="evaluar-verify-$$$$"; \
		export POSTGRES_PORT="$$(python -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		trap 'docker compose down --volumes --remove-orphans' EXIT; \
		docker compose up -d --wait db; \
		DATABASE_URL="postgresql://evaluar:evaluar@localhost:$${POSTGRES_PORT}/evaluar" \
		DJANGO_SETTINGS_MODULE=evaluar.config.settings.postgres_test \
		uv run --extra ai --extra queue --group dev pytest -q -m postgres tests/test_support_postgres.py

verify-sprint-image:
	@mkdir -p artifacts
	docker build --iidfile artifacts/evaluar-app.iid -t evaluar-app:sprint .
	docker run --rm --entrypoint python \
		-e DJANGO_SETTINGS_MODULE=evaluar.config.settings.test \
		evaluar-app:sprint -c \
		"import django, gunicorn, agent_framework; from google.cloud import tasks_v2; import evaluar.config.wsgi"

verify-sprint-smoke:
	IMAGE=evaluar-app:sprint SKIP_BUILD=1 ./scripts/verify-production-runtime.sh

verify-production-runtime:
	./scripts/verify-production-runtime.sh

migrate:
	uv run python manage.py migrate --noinput

check-schema:
	uv run python manage.py migrate --check
