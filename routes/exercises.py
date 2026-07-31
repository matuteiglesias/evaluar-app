# routes/exercises.py

from flask import Blueprint, request, session, render_template, jsonify, current_app, abort
import os
from google.api_core.exceptions import GoogleAPICallError

from llm.evaluator import Evaluator
from services.safe_rendering import render_exercise, render_feedback
from services.authentication import login_required
from services.exercise_repository import (
    ExerciseNotFound,
    available_courses,
    exercises_for_course,
    read_exercise,
)
from extensions import limiter

# from firebase_admin import firestore
# # Firestore DB client (assumes firebase_admin.initialize_app() already called)
# db = firestore.client()

from services.firebase import get_db


# Blueprint definition
exercises_bp = Blueprint("exercises", __name__)


@exercises_bp.route("/get_courses")
@login_required
def get_courses():
    """
    Endpoint to retrieve a list of available course directories.

    This function scans the 'exercises' directory for subdirectories,
    which are assumed to represent individual courses. The list of
    course directories is sorted alphabetically and returned as a JSON
    response.

    Returns:
        Response: A JSON response containing a sorted list of course
        directory names.

    Raises:
        OSError: If there is an issue accessing the 'exercises' directory
        or its contents.
    """

    return jsonify(available_courses())


@exercises_bp.route("/get_exercises")
@login_required
def get_exercises():
    """
    Route to retrieve exercises for a specific course.
    This endpoint fetches exercise data from a CSV file corresponding to the
    specified course. If the course is not provided, it defaults to 'tda'.
    The data is returned as a JSON response.
    Returns:
        - JSON response containing a list of exercises for the specified course.
        - HTTP 404 error if the course's index file is not found.
    Query Parameters:
        - course (str): The name of the course to retrieve exercises for. Defaults to 'tda'.
    Response:
        - 200: A JSON array of exercise records, each containing the exercise data
        and the course name.
        - 404: A JSON object with an error message if the course is not found.
    Raises:
        - FileNotFoundError: If the index file for the specified course does not exist.
    """
    course = request.args.get("course", "tda")
    try:
        rows = exercises_for_course(course)
    except ExerciseNotFound:
        abort(404)
    return jsonify([{**row, "course": course} for row in rows])


@exercises_bp.route("/exercises/<course>/<filename>")
@login_required
def exercise(course, filename):
    """
    Renders the exercise page for a given course and exercise file.

    Args:
        course (str): The name or identifier of the course.
        filename (str): The name of the exercise file.

    Returns:
        str: The rendered HTML content for the exercise page.
    """
    try:
        row, raw_content = read_exercise(course, filename=filename)
    except ExerciseNotFound:
        abort(404)
    content = render_exercise(raw_content, row["id"])
    return render_template("exercise.html", content=content, exercise_id=row["id"], course=course)


@exercises_bp.route("/submit_answer", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["ANSWER_RATE_LIMIT"])
def submit_answer():
    """
    Handles the submission of an answer for an exercise.

    This function processes the user's response to an exercise, evaluates it using
    a specified evaluator model, and renders feedback for the user. It also logs
    relevant events and records the interaction for future reference.

    Returns:
        - If the user is not logged in, redirects to the login page.
        - If required input data is missing, returns a 400 error with a message.
        - If an error occurs while loading the exercise or during evaluation,
          returns a 500 error with an appropriate message.
        - On success, renders the feedback page with the evaluated response.

    Workflow:
        1. Checks if the user is logged in via the session.
        2. Validates the presence of `exercise_id` and `response` in the request.
        3. Loads the exercise content based on the provided `exercise_id`.
        4. Evaluates the user's response using the evaluator model.
        5. Stores the evaluated response in the session and converts it to HTML.
        6. Records the interaction for logging and analytics purposes.
        7. Renders the feedback page with the evaluated response.

    Exceptions:
        - Logs and handles errors related to loading the exercise content.
        - Logs and handles errors during the evaluation process.
        - Logs warnings if interaction recording fails.

    Template:
        Renders the `feedback.html` template with:
        - `evaluated_response`: The evaluated response in HTML format.
        - `exercise_id`: The ID of the exercise being evaluated.
    """
    user = session["user"]
    if not current_app.config["AI_EVALUATION_ENABLED"]:
        return "AI evaluation is disabled", 503
    exercise_id = request.form.get("exercise_id")
    course = request.form.get("course", "tda")
    response = (request.form.get("response") or "").strip()

    if not exercise_id or not response:
        current_app.logger.warning("Missing exercise_id or response")
        return "Missing input data", 400

    if len(response) > current_app.config["MAX_ANSWER_LENGTH"]:
        return "Answer is too long", 400
    try:
        _, exercise_content = read_exercise(course, exercise_id=exercise_id)
    except ExerciseNotFound:
        abort(404)

    model = os.getenv("EVALUATOR_MODEL", "gpt-4o-mini")

    evaluator = current_app.extensions.get("evaluator") or Evaluator()
    current_app.logger.info("Using evaluator model: %s", model)
    evaluated_response = evaluator.evaluate(exercise_content, response)
    current_app.logger.info("Received evaluated response.")

    # Store raw and render HTML version
    session["evaluated_response"] = evaluated_response
    evaluated_response_html = render_feedback(evaluated_response)

    try:
        record_interaction(user, exercise_id, response, evaluated_response)
        current_app.logger.info("Interaction recorded successfully.")
    except GoogleAPICallError as error:
        current_app.logger.warning("Could not record interaction: %s", error)

    return render_template(
        "feedback.html",
        evaluated_response=evaluated_response_html,
        exercise_id=exercise_id,
        course=course,
    )


def record_interaction(user_details, exercise_id, user_query, ai_response):
    """Record user interactions with the AI in Firestore."""
    interaction_ref = get_db().collection("interaction_records").document()
    interaction_ref.set(
        {
            "exerciseId": exercise_id,
            "userId": user_details["id_"],
            "userName": user_details["name"],
            "userQuery": user_query,
            "aiResponse": ai_response,
            # "timestamp": firestore.SERVER_TIMESTAMP  # Use server timestamp for consistency
        }
    )
    print("Interaction recorded with Firestore.")


@exercises_bp.route("/submit-feedback", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["FEEDBACK_RATE_LIMIT"])
def submit_feedback():
    """
    Handles the submission of user feedback for an exercise.

    This function retrieves the feedback and exercise ID from the form data,
    validates the input, and stores the feedback in a Firestore database. It
    also logs relevant events and handles errors during the process.

    Returns:
        Response: A JSON response with a success message and HTTP status 200
                  if the feedback is successfully saved.
                  A JSON response with an error message and HTTP status 401
                  if the user is not authenticated.
                  A JSON response with an error message and HTTP status 400
                  if feedback or exercise ID is missing.
                  A JSON response with an error message and HTTP status 500
                  if there is an error saving the feedback.

    Raises:
        Exception: If there is an issue connecting to or interacting with the
                   Firestore database.

    Side Effects:
        - Logs warnings or errors for missing data, unauthenticated access,
          or database issues.
        - Stores feedback data in the Firestore database.
        - Removes the 'evaluated_response' key from the session after successful
          feedback submission.
    """
    user = session["user"]
    feedback = (request.form.get("feedback") or "").strip()
    exercise_id = request.form.get("exercise_id")
    course = request.form.get("course", "tda")
    evaluated_response = session.get("evaluated_response", "No Response")

    if not feedback or not exercise_id:
        current_app.logger.warning("Missing feedback or exercise_id in form submission.")
        return jsonify({"error": "Missing feedback or exercise ID"}), 400
    if len(feedback) > current_app.config["MAX_FEEDBACK_LENGTH"]:
        return jsonify({"error": "Feedback is too long"}), 400
    try:
        read_exercise(course, exercise_id=exercise_id)
    except ExerciseNotFound:
        abort(404)

    try:
        # db = firestore.client()
        doc_ref = get_db().collection("user_feedback").document()
        doc_ref.set(
            {
                "feedback": feedback,
                "exerciseId": exercise_id,
                "studentId": user.get("id_"),
                "studentName": user.get("name"),
                "evaluated_response": evaluated_response,
                # "timestamp": firestore.SERVER_TIMESTAMP
            }
        )
        current_app.logger.info(
            f"Feedback submitted by user {user['email']} on exercise {exercise_id}"
        )
    except GoogleAPICallError as error:
        current_app.logger.error("Error saving feedback: %s", error)
        return jsonify({"error": "Failed to save feedback"}), 500

    session.pop("evaluated_response", None)
    return jsonify({"message": "Feedback submitted successfully!"}), 200
