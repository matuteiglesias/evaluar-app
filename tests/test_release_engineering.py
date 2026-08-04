from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_required_ci_uses_whole_sprint_gate_and_cleans_up():
    workflow_text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "make verify-sprint" in workflow_text
    assert "make verify-phase3" not in workflow_text
    assert "if: always()" in workflow_text
    assert "docker compose down --volumes --remove-orphans" in workflow_text
    assert "git rev-parse HEAD" in workflow_text
    assert "  pull_request:" in workflow_text
    assert "    branches: [main]" in workflow_text


def test_container_entrypoint_never_owns_migrations():
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text()
    assert "migrate" not in entrypoint
    compose = (ROOT / "compose.yaml").read_text()
    assert "migrate:" in compose
    assert 'command: ["python", "manage.py", "migrate", "--noinput"]' in compose
