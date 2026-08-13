import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1]


def _load_production(extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "DJANGO_SECRET_KEY": "configuration-test-secret",
        "DATABASE_URL": "postgresql://user:pass@db/evaluar",
        "GOOGLE_CLIENT_ID": "placeholder",
        "GOOGLE_CLIENT_SECRET": "placeholder",
    }
    for name in ("DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS", "RENDER_EXTERNAL_HOSTNAME"):
        env.pop(name, None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", "import evaluar.config.settings.production"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_hosts_and_csrf_origins_fail_closed():
    result = _load_production()
    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS" in result.stderr
    result = _load_production(
        {
            "DJANGO_ALLOWED_HOSTS": "pilot.example.edu",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "http://pilot.example.edu/path",
        }
    )
    assert result.returncode != 0
    assert "HTTPS origins without paths" in result.stderr


def test_render_hostname_supplies_explicit_secure_host_contract():
    result = _load_production({"RENDER_EXTERNAL_HOSTNAME": "evaluar.onrender.com"})
    assert result.returncode == 0, result.stderr


def test_gunicorn_uses_non_default_port_and_safe_inline_timeout(monkeypatch):
    monkeypatch.setenv("PORT", "8765")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    assert config["bind"] == "0.0.0.0:8765"
    assert config["workers"] == 1
    assert config["timeout"] > 180


def test_gunicorn_rejects_invalid_port(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-port")
    with pytest.raises(ValueError, match="PORT must be a positive integer"):
        runpy.run_path(str(ROOT / "gunicorn.conf.py"))


def test_production_uses_whitenoise_manifest_storage():
    source = (ROOT / "src/evaluar/config/settings/production.py").read_text()
    base = (ROOT / "src/evaluar/config/settings/base.py").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()
    build_settings = (ROOT / "src/evaluar/config/settings/static_build.py").read_text()
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in base
    assert "CompressedManifestStaticFilesStorage" in source
    assert "STATIC_ROOT =" in base
    assert "collectstatic --noinput" in dockerfile
    assert "staticfiles.json" in dockerfile
    assert "CompressedManifestStaticFilesStorage" in build_settings


def test_render_pilot_preserves_inline_execution_without_dispatcher():
    blueprint = (ROOT / "render.yaml").read_text()
    assert "TUTORING_EXECUTION_MODE" in blueprint
    assert "value: inline" in blueprint
    assert "type: worker" not in blueprint
