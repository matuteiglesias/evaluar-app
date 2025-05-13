# routes/auth.py

import json
import requests
from flask import Blueprint, request, redirect, session, url_for, current_app
from oauthlib.oauth2 import WebApplicationClient
from main import oauth, get_google_provider_cfg, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from models.user import User  # Assuming User class is moved to models/user.py

auth_bp = Blueprint('auth', __name__)

# Set up the client globally with the configured Google ID
google_client = WebApplicationClient(GOOGLE_CLIENT_ID)



@auth_bp.route("/login")
def login():
    """
    Handles the login route for the application.

    This route redirects the user to Google's OAuth2 login page for authentication.
    It generates a redirect URI for the OAuth2 callback and specifies the required
    scopes for the authentication process.

    Logs:
        Logs an informational message indicating the redirection to Google's OAuth2 login page.

    Returns:
        A redirect response to Google's OAuth2 login page with the specified redirect URI
        and requested scopes.
    """
    current_app.logger.info("Redirecting to Google's OAuth2 login page")
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri=redirect_uri, scope="openid email profile")


@auth_bp.route("/login/callback")
def callback():
    """
    Handles the callback from Google's OAuth 2.0 login flow.

    This route is triggered after the user authenticates with Google and is redirected
    back to the application. It processes the authorization code, exchanges it for an
    access token, retrieves user information, and logs the user into the application.

    Returns:
        Response: A redirect to the application's main page if authentication is successful.
        Otherwise, returns an error message with a 400 status code.

    Raises:
        Exception: If there are issues with the token exchange or user information retrieval.

    Logs:
        - Logs the entry into the callback route.
        - Logs errors if the authorization code is missing or the user's email is not verified.
        - Logs the authenticated user's details.
        - Logs the creation of a new user if the user does not already exist in the database.
    """
    current_app.logger.info("Entered login callback")
    code = request.args.get("code")
    if not code:
        current_app.logger.error("No code returned from Google")
        return "No code returned from Google.", 400

    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Exchange code for token
    token_url, headers, body = google_client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    current_app.logger.info("Requesting access token from Google")
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    google_client.parse_request_body_response(json.dumps(token_response.json()))

    # Get user info
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = google_client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    data = userinfo_response.json()
    if not data.get("email_verified"):
        current_app.logger.error("User email not verified by Google")
        return "User email not available or not verified by Google.", 400

    user_id = data["sub"]
    user_email = data["email"]
    user_name = data["given_name"]
    user_picture = data["picture"]

    current_app.logger.info(f"Authenticated user: {user_name} ({user_email})")

    user = User.get(user_id)
    if not user:
        current_app.logger.info("New user, creating entry.")
        User.create(user_id, user_name, user_email, user_picture)
        user = User.get(user_id)

    session['user'] = user.__dict__
    return redirect(url_for("core.index"))

