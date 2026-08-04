.PHONY: verify-phase3 verify-phase3-live verify-sprint verify-sprint-local \
	verify-sprint-postgres verify-sprint-image verify-sprint-smoke

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
	docker compose up -d --wait db
	DATABASE_URL=postgresql://evaluar:evaluar@localhost:5432/evaluar \
		DJANGO_SETTINGS_MODULE=evaluar.config.settings.postgres_test \
		uv run --extra ai --extra queue --group dev pytest -q -m postgres tests/test_support_postgres.py

verify-sprint-image:
	@mkdir -p artifacts
	docker build --iidfile artifacts/evaluar-app.iid -t evaluar-app:sprint .
	docker run --rm --entrypoint python evaluar-app:sprint -c \
		"import django, gunicorn, agent_framework; from google.cloud import tasks_v2; import evaluar.config.wsgi"

verify-sprint-smoke:
	docker compose up -d --wait db
	docker compose run --rm app python manage.py migrate --noinput
	docker compose up -d --wait app
	@for attempt in $$(seq 1 20); do \
		curl -fsS -H 'X-Forwarded-Proto: https' http://localhost:8000/health/ready && exit 0; \
		sleep 2; \
	done; docker compose logs app; exit 1
