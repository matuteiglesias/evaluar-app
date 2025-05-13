"""
Main entry point for the educational platform.
Sets up the Flask app, environment, sessions, OAuth, Firebase, and routes.
"""
import os
import logging
from flask import Flask
from flask_session import Session
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
import requests

import firebase_admin
from firebase_admin import credentials, initialize_app

# Load .env variables early
load_dotenv()

# Global environment variables (used in route modules too)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth and Firebase objects will be used inside route files
oauth = OAuth()
firebase_initialized = False



def get_google_provider_cfg():
    """Fetch Google's OpenID configuration."""
    logging.info("Fetching Google's OpenID configuration")
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def configure_logging():
    """Set up global logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)




def create_app():
    logger = configure_logging()
    logger.info("Creating Flask app")

    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

    # Flask session configuration
    app.config.update({
        "SESSION_PERMANENT": False,
        "SESSION_TYPE": "filesystem",
        "SESSION_FILE_DIR": "/tmp/flask_session"
    })

    # Initialize session
    Session(app)
    # Initialize OAuth with Google
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid profile email'}
    )

    # Initialize Firebase only once
    global firebase_initialized
    if not firebase_initialized and not firebase_admin._apps:
        service_account_path = './evaluar-app-firebase-adminsdk-mvow6-456d541606.json'
        logger.info("Initializing Firebase Admin SDK")
        cred = credentials.Certificate(service_account_path)
        initialize_app(cred)
        firebase_initialized = True

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
    app.run(debug=True)
    