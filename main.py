
# def create_app():
#     logger.info('Creating Flask app')
#     app = Flask(__name__)

#     @app.route('/')
#     def hello():
#         return 'Hello, World!'

#     # You can add more routes and configuration here

#     return app

# if __name__ == '__main__':
#     # This block runs only if this script is executed directly, not imported
#     app = create_app()
#     logger.info('Starting Flask app')
#     app.run(host='0.0.0.0', port=8080)  # Adjust host and port if needed



'''
This is the main file of the educational platform.
'''

from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_from_directory
from authlib.integrations.flask_client import OAuth
from flask_session import Session
import os
import requests
from dotenv import load_dotenv
# from evaluator import Evaluator
from evaluator import Evaluator35, Evaluator40, Consulta40
import json
import logging
# from logging.handlers import RotatingFileHandler
import pandas as pd
import markdown
import re


import firebase_admin
from firebase_admin import credentials, firestore, initialize_app


load_dotenv()

# Environment configuration should be done outside of create_app for global access
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

def get_google_provider_cfg():
    """Fetches Google's OpenID configuration."""
    logging.info("Fetching Google's OpenID configuration")
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def create_app():
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)
    logging.info("Creating Flask app")


    # Configure session
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    # Configure Flask to use /tmp for session files
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
    # app.config["SESSION_FILE_DIR"] = "/tmp/flask_session_files"

    Session(app)
    app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

    # Setup OAuth2 client
    oauth = OAuth(app)
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid profile email'},
    )# Scope of Access: The request is asking for specific scopes (openid, https://www.googleapis.com/auth/userinfo.email, https://www.googleapis.com/auth/userinfo.profile). Ensure that these scopes are correctly configured and that the application has permission to request them. Also, the user needs to consent to these scopes; if they haven't, it might result in access being denied.



    # Path to your Firebase service account file
    service_account_path = './evaluar-app-firebase-adminsdk-mvow6-456d541606.json'

    if not firebase_admin._apps:
        logging.info("Initializing Firebase Admin SDK")
        cred = credentials.Certificate(service_account_path)
        initialize_app(cred)

    db = firestore.client()



    @app.route("/login")
    def login():
        logging.info("Redirecting to Google's OAuth2 login page")
        # Assuming `oauth.google` is correctly configured elsewhere in your application
        redirect_uri = url_for('callback', _external=True)
        app.logger.info(f"Redirect URI: {redirect_uri}")
        return oauth.google.authorize_redirect(redirect_uri=redirect_uri, scope="openid email profile")

    from oauthlib.oauth2 import WebApplicationClient  # For Google authentication
    google_client = WebApplicationClient(GOOGLE_CLIENT_ID)  # You need to set your Google Client ID here


    @app.route("/login/callback")
    def callback():
        app.logger.info("Entered callback function")
        code = request.args.get("code")
        if not code:
            app.logger.error("No code returned from Google")
            return "No code returned from Google.", 400
        
        logging.info("Processing callback from Google's OAuth2")
        # Get authorization code Google sent back to you
        code = request.args.get("code")

        # Find out what URL to hit to get tokens that allow you to ask for
        # things on behalf of a user
        google_provider_cfg = get_google_provider_cfg()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = google_client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=request.base_url,
            code=code
        )
        logging.info("Requesting access token")
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )
        logging.info("Parsing access token response")
        # Parse the tokens!
        google_client.parse_request_body_response(json.dumps(token_response.json()))

        # Now that you have tokens (yay) let's find and hit the URL
        # from Google that gives you the user's profile information,
        # including their Google profile image and email
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = google_client.add_token(userinfo_endpoint)
        logging.info("Requesting user info")
        userinfo_response = requests.get(uri, headers=headers, data=body)

        # You want to make sure their email is verified.
        # The user authenticated with Google, authorized your
        # app, and now you've verified their email through Google!
        if userinfo_response.json().get("email_verified"):
            unique_id = userinfo_response.json()["sub"]
            users_email = userinfo_response.json()["email"]
            picture = userinfo_response.json()["picture"]
            users_name = userinfo_response.json()["given_name"]
            logging.info(f"User {users_name} authenticated successfully")
            
            # Check if user exists, if not, create new user in our 'database'
            user = User.get(unique_id)
            if not user:
                logging.info(f"User {users_name} did not exist in our DB, creating new user.")
                User.create(unique_id, users_name, users_email, picture)
                user = User.get(unique_id)
            
            # Begin user session
            session['user'] = user.__dict__

            # Redirect to the homepage or dashboard
            return redirect(url_for("index"))
        

        else:
            logging.error("User email not verified by Google")
            return "User email not available or not verified by Google.", 400


    
    # Define all routes here
    @app.route("/")
    def index():
        # Check if user is authenticated
        if 'user' in session:
            # User is logged in
            return render_template('index.html', user=session['user'])
        else:
            # User is not logged in, show login link
            return render_template('login.html')
        # email = dict(session).get('email', None)
        # return f'Hello, {email}!' if email else redirect(url_for('login'))

    # Add more route definitions here
    # # Define routes here or import them if they're defined in other files
        

    ## EXERCISES ROUTES

    @app.route('/tikzpics/<filename>')
    def tikzpics(filename):
        return send_from_directory('tikzpics', filename)
        
    @app.route('/get_exercises')
    def get_exercises():
        df = pd.read_csv('./exercises/exercises.csv')
        return jsonify(df.to_dict(orient='records'))

    def preprocess_latex_for_mathjax(latex_content, exercise_id):
        # Reemplaza \emph{} con <em></em>
        latex_content = re.sub(r'\\emph\{(.*?)\}', r'<em>\1</em>', latex_content)
        
        # Reemplaza \textit{} con <i></i>
        latex_content = re.sub(r'\\textit\{(.*?)\}', r'<i>\1</i>', latex_content)
        
        # Reemplaza \textbf{} con <strong></strong>
        latex_content = re.sub(r'\\textbf\{(.*?)\}', r'<strong>\1</strong>', latex_content)
            
        # A robust solution would require actual LaTeX parsing
        latex_content = latex_content.replace(r'\begin{enumerate}', '<ol>')
        latex_content = latex_content.replace(r'\end{enumerate}', '</ol>')
        latex_content = latex_content.replace(r'\item', '<li>')
        # Close the list item
        latex_content = latex_content.replace(r'</li><li>', '</li>\n<li>')
        latex_content = latex_content.replace(r'\begin{center}', '<div style="text-align: center;">').replace(r'\end{center}', '</div>')

        # Reemplaza el marcador con la etiqueta img HTML
        figure_placeholder = "% FIGURA"
        # img_html = f'<img src="/tikzpics/{exercise_id}.png" alt="Figura para el ejercicio {exercise_id}" />'
        img_html = f'<img src="/tikzpics/{exercise_id}.png" alt="Figura para el ejercicio {exercise_id}" style="max-width: 80%; height: auto; display: block; margin-left: auto; margin-right: auto;" />'
        latex_content = latex_content.replace(figure_placeholder, img_html)

        return latex_content

    # @app.route('/exercises/<filename>')
    def get_exercise_content(filename):
        # Asumiendo que tus archivos de texto de ejercicios están almacenados en un directorio llamado 'exercises'
        exercises_dir = 'exercises'
        filepath = os.path.join(exercises_dir, filename)
        logger.info(f"Attempting to open exercise file at path: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
                logger.debug(f"Successfully read content from {filename}")

                # Extrae el ID del ejercicio del nombre del archivo, asumiendo que el formato es 'ID.tex'
                exercise_id = filename.split('.')[0]

                # Opcional: Envuelve el contenido LaTeX en delimitadores aquí si es necesario
                content = preprocess_latex_for_mathjax(content, exercise_id)
                return content
        except FileNotFoundError:
            logger.error(f"File {filename} not found in directory {exercises_dir}.")
            return "Exercise content not found."
        except Exception as e:
            logger.error(f"An unexpected error occurred while trying to read {filename}: {e}")
            return "An error occurred while fetching the exercise content."
        
    
    def get_filename_from_exercise_id(exercise_id):
        # Extract the filename from the exercise ID
        df = pd.read_csv('exercises/exercises.csv')
        filename = df.loc[df.id == int(exercise_id), 'file'].values[0]
        return filename

    @app.route('/exercises/<filename>')
    def exercise(filename):
        content = get_exercise_content(filename)
        exercise_id = get_exercise_id_from_filename(filename)
        # Pass the content to your template, possibly also passing additional data needed for rendering
        return render_template('exercise.html', content=content, exercise_id=exercise_id)

    def get_exercise_id_from_filename(filename):
        # Extract the exercise ID from the filename
        df = pd.read_csv('exercises/exercises.csv')
        id = df.loc[df.file == filename, 'id'].values[0]
        return id


    @app.route('/submit_answer', methods=['POST'])
    def submit():
        logger.info("Current user session data: %s", session.get('user'))

        if 'user' not in session:
            logger.info("User not in session, redirecting to login")
            return redirect(url_for('login'))

        user_details = session.get('user')
        if not user_details:
            logger.info("User details not found in session, redirecting to index")
            return redirect(url_for('index'))


        exercise_id = request.form.get('exercise_id')
        response = request.form.get('response')
        logger.info("Received exercise_id: %s and response.", exercise_id)

        # Convert exercise_id to filename
        filename = get_filename_from_exercise_id(exercise_id)

        # Fetch the exercise content based on the filename
        exercise_content = get_exercise_content(filename)
        logger.info("Fetched exercise content for exercise_id: %s", exercise_id)

        # evaluator = Evaluator()
        # evaluated_response = evaluator.evaluate(exercise_content, response)
        # logger.info("Evaluated response.")

        # Asumiendo que tienes una variable de entorno EVALUATOR_MODEL que puede ser "gpt-3.5" o "gpt-4"
        model = os.getenv("EVALUATOR_MODEL", "gpt-3.5")

        if model == "gpt-3.5":
            evaluator = Evaluator35()
        elif model == "gpt-4":
            # evaluator = Evaluator40()
            # evaluator = Evaluator35()
            evaluator = Consulta40()
            
        else:
            raise ValueError(f"Modelo de evaluador no soportado: {model}")

        # logger.info(f"About to call evaluate with exercise_content: '{exercise_content}' and response: '{response}'")
        logger.info(f"About to call evaluate with exercise_content:  and response: '{response}'")
        evaluated_response = evaluator.evaluate(exercise_content, response)
        logger.info("Evaluated response.")

        # Convert Markdown to HTML
        evaluated_response_html = markdown.markdown(evaluated_response)
        logger.info("Converted Markdown to HTML.")

        # Almacenar la respuesta evaluada en la sesión para su uso posterior
        session['evaluated_response'] = evaluated_response
        logger.info("Stored evaluated response in session.")

        # Record the interaction with all details
        # record_interaction(user_details, exercise_id, response, evaluated_response)

        # Record the interaction
        user_details = session.get('user')
        record_interaction(user_details, exercise_id, response, evaluated_response)
        logger.info("Recorded interaction.")

        # Pass the HTML-formatted response to the template
        logger.info("Rendering template with evaluated response.")
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
        app.logger.info("Interaction recorded with Firestore.")

    # def record_interaction(user_details, exercise_id, response, evaluated_response):
    #     interaction = {
    #         "user_id": user_details.get('id_'),
    #         "user_name": user_details.get('name'),
    #         "user_email": user_details.get('email'),
    #         "exercise_id": exercise_id,
    #         "response": response,
    #         "evaluated_response": evaluated_response
    #     }
    #     # Use the /tmp directory for compatibility with GCP's environment
    #     interactions_file_path = '/tmp/interactions.json'
    #     try:
    #         with open(interactions_file_path, 'r+') as file:
    #             try:
    #                 data = json.load(file)
    #             except json.JSONDecodeError:
    #                 data = []  # If the file is empty and causing errors
    #             data.append(interaction)
    #             file.seek(0)
    #             file.truncate()  # Clear the file before re-writing
    #             json.dump(data, file, indent=4)
    #     except FileNotFoundError:
    #         with open(interactions_file_path, 'w') as file:
    #             json.dump([interaction], file, indent=4)
    #         # with open('/interactions.json', 'w') as file:
    #         #     json.dump([interaction], file, indent=4)

    
    @app.route('/logout')
    def logout():
        session.clear()  # Clear Flask session
        return redirect(url_for('index'))  # Redirect to the index page

    @app.route('/health')
    def health():
        return jsonify({"status": "up"}), 200
    

    # from flask import request, redirect, url_for
    # from firebase_admin import firestore

    # Assuming you have Firebase Admin SDK initialized

    # db = firestore.client()

    def is_user_logged_in():
    
        return 'user_info' in session


    @app.route('/submit-feedback', methods=['POST'])
    def submit_feedback():
        feedback = request.form.get('feedback')
        exercise_id = request.form.get('exercise_id')  # CAPTURE EXERCISE ID WITHOUT ASKING
        student_id = session['user']['id_']
        # Suponiendo que guardaste la respuesta de IA en la sesión:
        ia_response = session.get('evaluated_response', 'No Response')  # Obtener la respuesta evaluada de la sesión

        # Log feedback to Firestore
        doc_ref = db.collection('user_feedback').document()
        doc_ref.set({
            "feedback": feedback,
            "exerciseId": exercise_id,
            "studentId": student_id,
            "studentName": session['user']['name'],
            "evaluated_response": ia_response,  # Guarda la respuesta de IA
            "timestamp": firestore.SERVER_TIMESTAMP  # Use server timestamp for consistency
        })

        app.logger.info(f"Received feedback: {feedback}, Exercise ID: {exercise_id}, Student ID: {student_id}, IA Response: {ia_response}")
        session.pop('evaluated_response', None)

        return 'Feedback submitted successfully!'
    

    # currentLoad 0
    # (number)
    # email "manu.nores@gmail.com"
    # (string)
    # maxLoad 99
    # (number)
    # name "Manuel"
    # (string)
    # surname "Nores"
    # (string)
    # teacherId "01" 

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


    import random
    import string

    def generate_custom_ticket_id(teacher_id, exercise_id):
        # Genera una letra aleatoria (mayúscula) y dos números
        random_letter = random.choice(string.ascii_uppercase)
        random_numbers = random.randint(10, 99)  # Genera un número entre 10 y 99
        # Construye el ID del ticket
        ticket_id = f"{teacher_id}-{exercise_id}-{random_letter}{random_numbers}"
        return ticket_id


    @app.route('/request-teacher-time', methods=['POST'])
    def request_teacher_time():

        if request.method == 'GET':
            return render_template('request_teacher_time_form.html')    

        if request.method == 'POST':
            # Suponiendo que ya hay una sesión de usuario establecida y que 'session['user']' está disponible
            exercise_id = request.form.get('exercise_id')  # Obtener el ID del ejercicio desde el formulario
            question = request.form.get('question')

            # Obtener la carga de trabajo de los docentes y el docente elegible
            teachers_load, average_load = get_teacher_loads()
            eligible_teacher_id = find_eligible_teacher(exercise_id, teachers_load, average_load)

            # Información del docente asignado, asumiendo que puedes obtener el nombre del profesor así
            if eligible_teacher_id:
                teacher_info = db.collection('teachers').document(eligible_teacher_id).get()
                teacher_name = teacher_info.to_dict().get('name', 'No asignado')
            else:
                teacher_name = 'No asignado'
                eligible_teacher_id = 'na'
            custom_ticket_id = generate_custom_ticket_id(eligible_teacher_id, exercise_id)

            ticket = {
                "exerciseId": exercise_id,
                "question": question,
                "status": "open",
                "studentId": session['user']['id_'],
                "studentName": session['user']['name'],
                "studentEmail": session['user']['email'],
                "teacherId": eligible_teacher_id,
                "timestamp": firestore.SERVER_TIMESTAMP  # Use server timestamp for consistency
            }

            # Crear o actualizar el documento con el ID personalizado
            ticket_ref = db.collection('tickets').document(custom_ticket_id)
            ticket_ref.set(ticket)

            # Guardar detalles del ticket en la sesión
            session['ticket_details'] = {
                'ticket_id': custom_ticket_id,  # Aquí se usa directamente el 'custom_ticket_id'
                'exerciseId': exercise_id,
                'question': question,
                'studentName': session['user']['name'],
                'studentEmail': session['user']['email'],
                'teacher_name': teacher_name
            }

            # Log for debugging
            app.logger.info('Ticket submitted successfully.')

            # Redirect to a confirmation page or somewhere appropriate
            return redirect(url_for('confirmation_page'))


    @app.route('/confirmation', methods=['GET'])
    def confirmation_page():
        return render_template('confirmation.html')

    def configure_logging():

        logging.basicConfig(level=logging.INFO)
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        # Additional logger configuration...
        return logger

    # def configure_logging():
    #     '''Configure logging for the application.'''
    #     logging.basicConfig(level=logging.INFO)
    #     # logger = logging.getLogger(__name__)
    #     # handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
    #     # logger.addHandler(handler)
    #     # return logger

    logger = configure_logging()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

# A simple in-memory 'database' to store user info
users_db = {}

class User:
    def __init__(self, id_, name, email, profile_pic):
        self.id_ = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

    @staticmethod
    def get(user_id):
        if user_id in users_db:
            user_info = users_db[user_id]
            return User(id_=user_id, **user_info)
        return None

    @staticmethod
    def create(id_, name, email, profile_pic):
        users_db[id_] = {"name": name, "email": email, "profile_pic": profile_pic}
