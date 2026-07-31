# routes/teachers.py

from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from services.authentication import login_required
from services.exercise_repository import ExerciseNotFound, read_exercise
from services.persistence import get_persistence
from services.runtime_boundaries import new_id, now

# Retained as import-compatible legacy evidence; generic packets do not call them.
from services.teachers import (
    find_eligible_teacher as find_eligible_teacher,
    get_teacher_loads as get_teacher_loads,
)
from extensions import limiter


teachers_bp = Blueprint("teachers", __name__)

# from firebase_admin import firestore
# db = firestore.client()


@teachers_bp.route("/request-teacher-time", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["TEACHER_HELP_RATE_LIMIT"])
def request_teacher_time():
    """Create one generic, explicitly unassigned teacher-help packet."""
    user = session["user"]
    exercise_id = request.form.get("exercise_id")
    course = request.form.get("course", "tda")
    question = (request.form.get("question") or "").strip()

    if not exercise_id or not question:
        current_app.logger.warning("Missing exercise_id or question in form submission")
        return "Missing data", 400
    if len(question) > current_app.config["MAX_TEACHER_QUESTION_LENGTH"]:
        return "Question is too long", 400
    try:
        read_exercise(course, exercise_id=exercise_id)
    except ExerciseNotFound:
        return "Exercise not found", 404

    identity = f"{course}:{exercise_id}"
    ticket_id = new_id("teacher-packet", identity)
    ticket_data = {
        "ticketId": ticket_id,
        "course": course,
        "exerciseId": exercise_id,
        "question": question,
        "status": "open",
        "studentId": user["id_"],
        "studentName": user["name"],
        "studentEmail": user["email"],
        "assignment": "unassigned",
        "timestamp": now(),
    }

    try:
        get_persistence().save_teacher_packet(ticket_id, ticket_data)
        current_app.logger.info("Teacher packet %s created successfully", ticket_id)
    except Exception:
        current_app.logger.exception("Failed to create teacher packet %s", ticket_id)
        return "Failed to submit request", 500

    session["ticket_details"] = {
        "ticket_id": ticket_id,
        "course": course,
        "exerciseId": exercise_id,
        "question": question,
        "studentName": user["name"],
        "studentEmail": user["email"],
        "assignment": "unassigned",
    }

    return redirect(url_for("teachers.confirmation_page"))


@teachers_bp.route("/confirmation", methods=["GET"])
@login_required
def confirmation_page():
    return render_template("confirmation.html")
