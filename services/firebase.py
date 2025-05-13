import firebase_admin
from firebase_admin import credentials, firestore
import os

_app = None
_db = None

def get_db():
    global _app, _db
    if not _app:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "env/evaluar-app-firebase-adminsdk-mvow6-456d541606.json")
        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred)
    if not _db:
        _db = firestore.client()
    return _db
