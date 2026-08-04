"""Test settings that retain the PostgreSQL DATABASE_URL configured by base settings."""

from .base import *  # noqa: F403

SECRET_KEY = "postgres-test-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
