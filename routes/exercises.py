# routes/exercises.py

from flask import (
    Blueprint, request, session, redirect,
    url_for, render_template, jsonify, current_app
)
import os
import markdown

from llm.evaluator import Evaluator
from services.exercise_loader import (
    get_exercise_content,
    get_exercise_id_from_filename,
    get_filename_from_exercise_id
)

from firebase_admin import firestore
import pandas as pd

# Blueprint definition
exercises_bp = Blueprint('exercises', __name__)

# Firestore DB client (assumes firebase_admin.initialize_app() already called)
db = firestore.client()



@exercises_bp.route('/get_exercises')
def get_exercises():
    # Move to services if logic grows
    df = pd.read_csv('./exercises/exercises.csv') ## relative path is ./../exercises... 
    return jsonify(df.to_dict(orient='records'))


@exercises_bp.route('/exercises/<filename>')
def exercise(filename):
    content = get_exercise_content(filename)
    exercise_id = get_exercise_id_from_filename(filename)
    return render_template('exercise.html', content=content, exercise_id=exercise_id)



@exercises_bp.route('/submit_answer', methods=['POST'])
def submit_answer():
    user = session.get('user')
    if not user:
        current_app.logger.info("User not in session, redirecting to login")
        return redirect(url_for('core.index'))

    exercise_id = request.form.get('exercise_id')
    response = request.form.get('response')

    if not exercise_id or not response:
        current_app.logger.warning("Missing exercise_id or response")
        return "Missing input data", 400

    current_app.logger.info("Received submission for exercise_id=%s", exercise_id)

    try:
        filename = get_filename_from_exercise_id(exercise_id)
        exercise_content = get_exercise_content(filename)
        current_app.logger.info("Loaded content for file: %s", filename)
    except Exception as e:
        current_app.logger.error(f"Error loading exercise: {e}")
        return "Error loading exercise", 500

    model = os.getenv("EVALUATOR_MODEL", "gpt-4o-mini")

    try:
        evaluator = Evaluator()

        current_app.logger.info("Using evaluator model: %s", model)
        evaluated_response = evaluator.evaluate(exercise_content, response)
        current_app.logger.info("Received evaluated response.")

    except Exception as e:
        current_app.logger.error(f"Error during evaluation: {e}")
        return "Error evaluating the response", 500

    # Store raw and render HTML version
    session['evaluated_response'] = evaluated_response
    evaluated_response_html = markdown.markdown(evaluated_response)

    try:
        record_interaction(user, exercise_id, response, evaluated_response)
        current_app.logger.info("Interaction recorded successfully.")
    except Exception as e:
        current_app.logger.warning(f"Could not record interaction: {e}")

    return render_template('feedback.html', evaluated_response=evaluated_response_html, exercise_id=exercise_id)



def record_interaction(user_details, exercise_id, user_query, ai_response):
    """Record user interactions with the AI in Firestore."""
    interaction_ref = db.collection('interaction_records').document()
    interaction_ref.set({
        "exerciseId": exercise_id,
        "userId": user_details['id_'],
        "userName": user_details['name'],
        "userQuery": user_query,
        "aiResponse": ai_response,
        "timestamp": firestore.SERVER_TIMESTAMP  # Use server timestamp for consistency
    })
    print("Interaction recorded with Firestore.")




@exercises_bp.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    user = session.get('user')
    if not user:
        current_app.logger.warning("Feedback submission attempted without user session.")
        return jsonify({"error": "Not authenticated"}), 401

    feedback = request.form.get('feedback')
    exercise_id = request.form.get('exercise_id')
    evaluated_response = session.get('evaluated_response', 'No Response')

    if not feedback or not exercise_id:
        current_app.logger.warning("Missing feedback or exercise_id in form submission.")
        return jsonify({"error": "Missing feedback or exercise ID"}), 400

    try:
        db = firestore.client()
        doc_ref = db.collection('user_feedback').document()
        doc_ref.set({
            "feedback": feedback,
            "exerciseId": exercise_id,
            "studentId": user.get('id_'),
            "studentName": user.get('name'),
            "evaluated_response": evaluated_response,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        current_app.logger.info(f"Feedback submitted by user {user['email']} on exercise {exercise_id}")
    except Exception as e:
        current_app.logger.error(f"Error saving feedback: {e}")
        return jsonify({"error": "Failed to save feedback"}), 500

    session.pop('evaluated_response', None)
    return jsonify({"message": "Feedback submitted successfully!"}), 200




    # from flask import request, redirect, url_for
    # from firebase_admin import firestore

    # Assuming you have Firebase Admin SDK initialized

    # db = firestore.client()

