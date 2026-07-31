from flask import Blueprint, current_app, redirect, session, url_for

from extensions import limiter
from main import oauth as oauth  # compatibility handle for existing Authlib-focused tests
from models.user import User
from services.identity import IdentityProviderError, get_identity_provider


auth_bp = Blueprint("auth", __name__)


def _timeout():
    return (
        current_app.config["HTTP_CONNECT_TIMEOUT"],
        current_app.config["HTTP_READ_TIMEOUT"],
    )


def _authentication_failure(status=400):
    current_app.logger.warning("Google authentication failed")
    return "Authentication failed.", status


@auth_bp.route("/login")
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    """Start the Authlib-managed OAuth flow, including state generation."""
    redirect_uri = url_for("auth.callback", _external=True)
    return get_identity_provider().begin(redirect_uri)


@auth_bp.route("/login/callback")
def callback():
    """Complete OAuth through the same Authlib client and validate user information."""
    try:
        identity = get_identity_provider().complete(_timeout())
    except IdentityProviderError:
        return _authentication_failure(502)

    user_id = identity.subject
    user_email = identity.email
    user_name = identity.name
    user_picture = identity.picture
    user = User.get(user_id)
    if not user:
        User.create(user_id, user_name, user_email, user_picture)
        user = User.get(user_id)

    session["user"] = user.__dict__
    return redirect(url_for("core.index"))
