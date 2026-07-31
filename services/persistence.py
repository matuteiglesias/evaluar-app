"""Replaceable persistence contract; Firestore is only the legacy implementation."""

from flask import current_app

from services.firebase import get_db


class LegacyFirestorePersistence:
    """Compatibility adapter for current data; not a future architecture choice."""

    def save_interaction(self, interaction_id, record):
        get_db().collection("interaction_records").document(interaction_id).set(record)

    def save_feedback(self, feedback_id, record):
        get_db().collection("user_feedback").document(feedback_id).set(record)

    def save_teacher_packet(self, ticket_id, record):
        get_db().collection("tickets").document(ticket_id).set(record)


def get_persistence():
    return current_app.extensions.get("persistence") or LegacyFirestorePersistence()
