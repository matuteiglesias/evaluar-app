"""Shared settings for the Evaluar Django application."""

from pathlib import Path
from typing import Any
import os

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get(
    "SECRET_KEY", "unsafe-local-only-change-me"
)
DEBUG = False
ALLOWED_HOSTS = [
    host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",") if host
]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "evaluar.identity",
    "evaluar.courses",
    "evaluar.tutoring",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "evaluar.config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "evaluar.config.wsgi.application"
ASGI_APPLICATION = "evaluar.config.asgi.application"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    from urllib.parse import urlparse

    _db = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db.path.lstrip("/"),
            "USER": _db.username,
            "PASSWORD": _db.password,
            "HOST": _db.hostname,
            "PORT": _db.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}
    }
AUTH_PASSWORD_VALIDATORS: list[dict[str, Any]] = []
AUTH_USER_MODEL = "identity.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SIGNUP_FIELDS = ["email*"]
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_ADAPTER = "evaluar.identity.adapters.GoogleSocialAccountAdapter"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": GOOGLE_CLIENT_ID,
                "secret": GOOGLE_CLIENT_SECRET,
                "settings": {
                    "scope": ["profile", "email"],
                    "auth_params": {"access_type": "online"},
                    "oauth_pkce_enabled": True,
                },
            }
        ]
    }
}
LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TUTORING_DAILY_QUOTA = int(os.environ.get("TUTORING_DAILY_QUOTA", "20"))
TUTORING_COURSE_DAILY_QUOTA = int(os.environ.get("TUTORING_COURSE_DAILY_QUOTA", "2000"))
TUTORING_ATTEMPT_LEASE_SECONDS = int(os.environ.get("TUTORING_ATTEMPT_LEASE_SECONDS", "900"))
TUTORING_TASK_MAX_ATTEMPTS = int(os.environ.get("TUTORING_TASK_MAX_ATTEMPTS", "5"))
TUTORING_TASK_AUDIENCE = os.environ.get("TUTORING_TASK_AUDIENCE", "")
TUTORING_TASK_SERVICE_ACCOUNT = os.environ.get("TUTORING_TASK_SERVICE_ACCOUNT", "")
TUTORING_TASK_QUEUE_PATH = os.environ.get("TUTORING_TASK_QUEUE_PATH", "")
TUTORING_WORKER_URL = os.environ.get("TUTORING_WORKER_URL", "")
TUTORING_OPENAI_API_KEY = os.environ.get("TUTORING_OPENAI_API_KEY", "")
TUTORING_OPENAI_BASE_URL = os.environ.get("TUTORING_OPENAI_BASE_URL", "")
TUTORING_AZURE_OPENAI_ENDPOINT = os.environ.get("TUTORING_AZURE_OPENAI_ENDPOINT", "")
TUTORING_AZURE_OPENAI_API_KEY = os.environ.get("TUTORING_AZURE_OPENAI_API_KEY", "")
TUTORING_AZURE_OPENAI_API_VERSION = os.environ.get(
    "TUTORING_AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
)
TUTORING_CAPTURE_SENSITIVE_TELEMETRY = False
TUTORING_MODEL_FACTORY = os.environ.get(
    "TUTORING_MODEL_FACTORY",
    "evaluar.tutoring.infrastructure.production.ProductionTutoringModelFactory",
)
TUTORING_PROMPT_PUBLIC_ID = os.environ.get("TUTORING_PROMPT_PUBLIC_ID", "default")
TUTORING_MAX_ANSWER_CHARS = int(os.environ.get("TUTORING_MAX_ANSWER_CHARS", "12000"))
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "courses:list"
LOGOUT_REDIRECT_URL = "account_login"
