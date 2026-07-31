.PHONY: verify-phase3 verify-phase3-live

verify-phase3:
	uv run --extra ai --extra queue --group dev pytest -q -m "not live" tests/test_django_phase2.py tests/test_tutoring.py tests/test_tutoring_queue.py tests/test_agent_framework_adapter.py tests/test_agent_framework_production.py tests/test_tutoring_student_experience.py tests/test_tutoring_operations.py
	uv run --extra ai --extra queue --group dev ruff check .
	uv run --extra ai --extra queue --group dev ruff format --check .
	uv run --extra ai --extra queue --group dev mypy src/evaluar/tutoring src/evaluar/courses
	uv run --extra ai --extra queue --group dev python -m django makemigrations --check --dry-run --settings=evaluar.config.settings.test

verify-phase3-live:
	@test "$${TUTORING_LIVE_TEST}" = "1" || (echo "Set TUTORING_LIVE_TEST=1 to authorize billable staging calls." && exit 2)
	uv run --extra ai --group dev pytest -q -m live tests/test_tutoring_live_staging.py
