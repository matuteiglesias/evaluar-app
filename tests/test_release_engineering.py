from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_required_ci_uses_whole_sprint_gate_without_global_compose_cleanup():
    workflow_text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "make verify-sprint" in workflow_text
    assert "make verify-phase3" not in workflow_text
    assert "docker compose down" not in workflow_text
    assert "git rev-parse HEAD" in workflow_text
    assert "  pull_request:" in workflow_text
    assert "    branches: [main]" in workflow_text


def test_postgres_gate_uses_an_isolated_compose_project_and_port():
    makefile = (ROOT / "Makefile").read_text()
    target = makefile.split("verify-sprint-postgres:", 1)[1].split("verify-sprint-image:", 1)[0]
    assert 'COMPOSE_PROJECT_NAME="evaluar-verify-$$$$"' in target
    assert "POSTGRES_PORT=" in target
    assert "localhost:$${POSTGRES_PORT}" in target
    assert "docker compose down --remove-orphans;" not in target
    assert "trap 'docker compose down --volumes --remove-orphans' EXIT" in target


def test_runtime_smoke_test_only_cleans_its_named_resources():
    script = (ROOT / "scripts/verify-production-runtime.sh").read_text()
    assert "docker compose down" not in script
    assert 'docker rm -f "$WEB" "$DB"' in script
    assert 'docker network rm "$NETWORK"' in script


def test_container_entrypoint_never_owns_migrations():
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text()
    assert "migrate" not in entrypoint
    compose = (ROOT / "compose.yaml").read_text()
    assert "migrate:" in compose
    assert 'command: ["python", "manage.py", "migrate", "--noinput"]' in compose
