import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403


def _csv_setting(name: str) -> list[str]:
    """Read a comma-separated deployment setting without accepting blank entries."""
    raw = os.environ.get(name, "")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if raw and any(not value.strip() for value in raw.split(",")):
        raise ImproperlyConfigured(f"{name} contains an empty value.")
    return values


_configured_hosts = _csv_setting("DJANGO_ALLOWED_HOSTS")
_configured_origins = _csv_setting("DJANGO_CSRF_TRUSTED_ORIGINS")
_render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_hostname:
    if "://" in _render_hostname or "/" in _render_hostname:
        raise ImproperlyConfigured("RENDER_EXTERNAL_HOSTNAME must be a hostname, not a URL.")
    _configured_hosts.append(_render_hostname)
    _configured_origins.append(f"https://{_render_hostname}")

ALLOWED_HOSTS = list(dict.fromkeys(_configured_hosts))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_configured_origins))
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "Missing production setting: DJANGO_ALLOWED_HOSTS (or RENDER_EXTERNAL_HOSTNAME)."
    )
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list explicit production hostnames.")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "Missing production setting: DJANGO_CSRF_TRUSTED_ORIGINS (or RENDER_EXTERNAL_HOSTNAME)."
    )
for origin in CSRF_TRUSTED_ORIGINS:
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise ImproperlyConfigured(
            "DJANGO_CSRF_TRUSTED_ORIGINS entries must be HTTPS origins without paths."
        )

required = {
    name: globals()[name]
    for name in ("SECRET_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "DATABASE_URL")
}
missing = [
    name for name, value in required.items() if not value or value == "unsafe-local-only-change-me"
]
if missing:
    raise ImproperlyConfigured(f"Missing production settings: {', '.join(missing)}")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
