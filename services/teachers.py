

import random
import string
from firebase_admin import firestore

from flask import current_app as app

db = firestore.client()


def generate_custom_ticket_id(teacher_id, exercise_id):
    # Genera una letra aleatoria (mayúscula) y dos números
    random_letter = random.choice(string.ascii_uppercase)
    random_numbers = random.randint(10, 99)  # Genera un número entre 10 y 99
    # Construye el ID del ticket
    ticket_id = f"{teacher_id}-{exercise_id}-{random_letter}{random_numbers}"
    return ticket_id



def find_eligible_teacher(exercise_id, teachers_load, average_load):
    # Logging the entry to the function with given parameters
    app.logger.info(f"Finding eligible teacher for exercise {exercise_id} with average load {average_load}")

    # First, try to find a teacher who has previously worked on this exercise and isn't overloaded
    previous_teachers = db.collection('tickets').where('exerciseId', '==', exercise_id).stream()
    for ticket in previous_teachers:
        teacher_id = ticket.to_dict().get('teacherId')
        # if teacher_id and teachers_load.get(teacher_id, 0) <= average_load * 1.15:
        if teacher_id and teachers_load.get(teacher_id, 0) <= (average_load + 3):
            app.logger.info(f"Found previous teacher {teacher_id} for exercise {exercise_id}")
            return teacher_id
    
    # If no previous teacher or all are overloaded, find any eligible teacher
    for teacher_id, load in teachers_load.items():
        if load <= (average_load + 1):
            app.logger.debug(f"Assigning to teacher {teacher_id} with load {load}")
            return teacher_id
    
    # If no eligible teacher is found, return None or handle as needed
    app.logger.debug("No eligible teacher found.")
    return None




def obtener_todos_los_profesores_ids():
    teachers = db.collection('teachers').stream()  # Asume que 'db' es tu objeto de base de datos de Firestore
    teacher_ids = [teacher.to_dict().get('teacherId') for teacher in teachers]
    return teacher_ids

def get_teacher_loads():
    # Inicializar las cargas de todos los profesores posibles con 0
    # Aquí necesitarías una lista o conjunto de todos los IDs de profesores posibles
    all_teacher_ids = obtener_todos_los_profesores_ids()
    teachers_load = {teacher_id: 0 for teacher_id in all_teacher_ids}
    
    tickets = db.collection('tickets').stream()
    for ticket in tickets:
        teacher_id = ticket.to_dict().get('teacherId')
        if teacher_id and teacher_id in teachers_load:
            teachers_load[teacher_id] += 1
    
    # Ahora el cálculo del promedio incluirá a todos los profesores, incluso aquellos sin tickets asignados
    average_load = sum(teachers_load.values()) / len(teachers_load) if teachers_load else 0

    app.logger.info(f"Teachers' loads: {teachers_load}, Average load: {average_load}")
    return teachers_load, average_load


