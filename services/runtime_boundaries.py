"""Small clock and identifier seams for deterministic characterization tests."""

from datetime import datetime, timezone
import uuid

from flask import current_app


def new_id(kind, identity):
    factory = current_app.extensions.get("id_generator")
    return factory(kind, identity) if factory else f"{kind}-{uuid.uuid4().hex}"


def now():
    clock = current_app.extensions.get("clock")
    return clock() if clock else datetime.now(timezone.utc)
