from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403

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
