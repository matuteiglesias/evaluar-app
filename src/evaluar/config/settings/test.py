from .base import *  # noqa: F403

SECRET_KEY = "test-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
TUTORING_ENABLED = True
SUPPORT_ENABLED = True
SUPPORT_NOTIFICATIONS_ENABLED = True
