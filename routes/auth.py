import requests
from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, redirect, session, url_for

from extensions import limiter
from main import oauth
from models.user import User


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
    return oauth.google.authorize_redirect(redirect_uri=redirect_uri, scope="openid email profile")


@auth_bp.route("/login/callback")
def callback():
    """Complete OAuth through the same Authlib client and validate user information."""
    try:
        token = oauth.google.authorize_access_token(timeout=_timeout())
        if not token or not token.get("access_token"):
            return _authentication_failure()
        response = oauth.google.get("userinfo", token=token, timeout=_timeout())
        response.raise_for_status()
        data = response.json()
        required = ("sub", "email")
        if not isinstance(data, dict) or any(not data.get(field) for field in required):
            return _authentication_failure()
        if data.get("email_verified") is not True:
            return _authentication_failure()
    except (OAuthError, requests.RequestException, ValueError, TypeError):
        return _authentication_failure(502)

    user_id = data["sub"]
    user_email = data["email"]
    user_name = data.get("given_name") or data.get("name") or user_email
    user_picture = data.get("picture", "")
    user = User.get(user_id)
    if not user:
        User.create(user_id, user_name, user_email, user_picture)
        user = User.get(user_id)

    session["user"] = user.__dict__
    return redirect(url_for("core.index"))
