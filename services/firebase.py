import firebase_admin
from firebase_admin import credentials, firestore
import os

_db = None

def get_db():
    global _db

    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "env/evaluar-app-firebase-adminsdk-mvow6-456d541606.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    if not _db:
        _db = firestore.client()

    return _db
