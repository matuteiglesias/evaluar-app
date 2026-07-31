import firebase_admin
from firebase_admin import credentials, firestore
from flask import current_app


class FirebaseExtension:
    """A narrow, lazy Firebase adapter stored as a Flask extension."""

    def init_app(self, app):
        app.extensions["firebase"] = self

    def get_db(self):
        db = current_app.extensions.get("firebase_db")
        if db is not None:
            return db
        if not current_app.config.get("FIREBASE_ENABLED", True):
            raise RuntimeError("Firebase is disabled by application configuration")

        if not firebase_admin._apps:
            cred_path = current_app.config.get("GOOGLE_APPLICATION_CREDENTIALS")
            credential = (
                credentials.Certificate(cred_path)
                if cred_path
                else credentials.ApplicationDefault()
            )
            firebase_admin.initialize_app(credential)

        db = firestore.client()
        current_app.extensions["firebase_db"] = db
        return db


def get_db():
    return firebase.get_db()


firebase = FirebaseExtension()
