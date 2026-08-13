"""Container HTTP contract for the small Render pilot."""

import os


def _positive_integer(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


bind = f"0.0.0.0:{_positive_integer('PORT', 8000)}"
workers = _positive_integer("WEB_CONCURRENCY", 2)
# Tutoring provider policies permit up to 180 seconds. Leave time to persist the response.
timeout = _positive_integer("GUNICORN_TIMEOUT", 210)
graceful_timeout = _positive_integer("GUNICORN_GRACEFUL_TIMEOUT", 30)
accesslog = "-"
errorlog = "-"
capture_output = True
