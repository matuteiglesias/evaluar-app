from functools import wraps

from flask import current_app, redirect, request, session, url_for


def login_required(view):
    """Redirect anonymous users to the single login entry point."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def _rate_limit_namespace():
    return current_app.config.get("RATELIMIT_KEY_PREFIX", "app")


def direct_remote_address_key():
    """Use the direct peer address without trusting forwarding headers."""
    return f"{_rate_limit_namespace()}:ip:{request.remote_addr or 'unknown'}"


def rate_limit_key():
    """Prefer the authenticated stable ID, otherwise use the direct peer address."""
    user = session.get("user") or {}
    identity = (
        f"user:{user['id_']}" if user.get("id_") else f"ip:{request.remote_addr or 'unknown'}"
    )
    return f"{_rate_limit_namespace()}:{identity}"
