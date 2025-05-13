# routes/teachers.py

from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from firebase_admin import firestore
from services.teachers import (
    get_teacher_loads,
    find_eligible_teacher,
    generate_custom_ticket_id
)

teachers_bp = Blueprint('teachers', __name__)
db = firestore.client()


@teachers_bp.route('/request-teacher-time', methods=['POST'])
def request_teacher_time():
    user = session.get('user')
    if not user:
        current_app.logger.warning("Unauthorized access to teacher time request")
        return redirect(url_for('core.index'))

    exercise_id = request.form.get('exercise_id')
    question = request.form.get('question')

    if not exercise_id or not question:
        current_app.logger.warning("Missing exercise_id or question in form submission")
        return "Missing data", 400

    # Get load information
    try:
        teachers_load, avg_load = get_teacher_loads()
        teacher_id = find_eligible_teacher(exercise_id, teachers_load, avg_load)
    except Exception as e:
        current_app.logger.error(f"Error assigning teacher: {e}")
        teacher_id = None

    teacher_name = "No asignado"
    if teacher_id:
        try:
            teacher_doc = db.collection('teachers').document(teacher_id).get()
            teacher_name = teacher_doc.to_dict().get('name', teacher_name)
        except Exception as e:
            current_app.logger.warning(f"Failed to get teacher info for {teacher_id}: {e}")
        assigned_teacher_id = teacher_id
    else:
        assigned_teacher_id = "na"

    ticket_id = generate_custom_ticket_id(assigned_teacher_id, exercise_id)
    ticket_data = {
        "exerciseId": exercise_id,
        "question": question,
        "status": "open",
        "studentId": user["id_"],
        "studentName": user["name"],
        "studentEmail": user["email"],
        "teacherId": assigned_teacher_id,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    try:
        db.collection('tickets').document(ticket_id).set(ticket_data)
        current_app.logger.info(f"Ticket {ticket_id} created successfully.")
    except Exception as e:
        current_app.logger.error(f"Failed to create ticket {ticket_id}: {e}")
        return "Failed to submit request", 500

    session['ticket_details'] = {
        "ticket_id": ticket_id,
        "exerciseId": exercise_id,
        "question": question,
        "studentName": user["name"],
        "studentEmail": user["email"],
        "teacher_name": teacher_name
    }

    return redirect(url_for('teachers.confirmation_page'))


@teachers_bp.route('/confirmation', methods=['GET'])
def confirmation_page():
    return render_template('confirmation.html')
