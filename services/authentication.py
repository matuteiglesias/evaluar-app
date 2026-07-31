from functools import wraps

from flask import redirect, request, session, url_for


def login_required(view):
    """Redirect anonymous users to the single login entry point."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def rate_limit_key():
    """Prefer the authenticated stable ID, otherwise use the direct peer address."""
    user = session.get("user") or {}
    return f"user:{user['id_']}" if user.get("id_") else f"ip:{request.remote_addr or 'unknown'}"
