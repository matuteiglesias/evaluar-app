"""
Main entry point for the educational platform.
Sets up the Flask app, environment, sessions, OAuth, Firebase, and routes.
"""

import logging
import uuid
from flask import Flask
from flask_session import Session
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from services.settings import runtime_settings, validate_settings

# Load .env variables early
load_dotenv()

# OAuth and Firebase objects will be used inside route files
oauth = OAuth()


def configure_logging():
    """Set up global logging configuration."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    return logging.getLogger(__name__)


def create_app(config_overrides=None, adapters=None):
    """
    Creates and configures the Flask application.

    This function initializes the Flask app with necessary configurations,
    sets up logging, session management, OAuth with Google, and Firebase Admin SDK.
    It also registers the application's blueprints for routing.

    Returns:
        Flask: The configured Flask application instance.

    Raises:
        FileNotFoundError: If the Firebase service account file is not found.

    Configuration:
        - SECRET_KEY: The secret key for the Flask application, loaded from environment variables.
        - SESSION_PERMANENT: Boolean indicating whether sessions are permanent.
        - SESSION_TYPE: The type of session storage (e.g., filesystem).
        - SESSION_FILE_DIR: Directory for storing session files.

    Blueprints:
        - auth_bp: Handles authentication routes.
        - exercises_bp: Handles routes related to exercises.
        - teachers_bp: Handles routes related to teachers.
        - core_bp: Handles core application routes.
        - static_bp: Handles static file routes.

    External Services:
        - Google OAuth: Configured for user authentication using Google.
        - Firebase Admin SDK: Initialized for Firebase integration.
    """
    logger = configure_logging()
    logger.info("Creating Flask app")

    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    app.config.update(runtime_settings(app.root_path))
    if config_overrides:
        app.config.update(config_overrides)
    if adapters:
        app.extensions.update(adapters)
    validate_settings(app.config)

    # Initialize session
    Session(app)
    from extensions import csrf, limiter

    csrf.init_app(app)
    # Never let tests consume or reset a developer/CI shared limiter backend.
    # The extension is process-global, so reset its ephemeral store for every
    # test app to avoid counters leaking between app fixtures.
    if app.config.get("TESTING"):
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"
        app.config["RATELIMIT_KEY_PREFIX"] = f"test-app:{uuid.uuid4()}"
    limiter.init_app(app)
    if app.config.get("TESTING"):
        limiter.reset()
    # Initialize OAuth with Google
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        access_token_url="https://accounts.google.com/o/oauth2/token",
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        api_base_url="https://www.googleapis.com/oauth2/v1/",
        client_kwargs={"scope": "openid profile email"},
    )

    # Firebase is deliberately lazy: importing and constructing the app must not
    # read credentials or contact Google.  Routes resolve it only when needed.
    from services.firebase import firebase

    firebase.init_app(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.exercises import exercises_bp
    from routes.teachers import teachers_bp
    from routes.core import core_bp
    from routes.static import static_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(exercises_bp)
    app.register_blueprint(teachers_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(static_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
