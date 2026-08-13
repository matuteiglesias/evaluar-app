import os

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
TUTORING_EXECUTION_MODE = os.environ.get("TUTORING_EXECUTION_MODE", "inline")
