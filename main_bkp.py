'''
This is the main file of the educational platform.
'''

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from authlib.integrations.flask_client import OAuth
from flask_session import Session
import os
import requests
from dotenv import load_dotenv
from evaluator import Evaluator
import json
import pandas as pd
import markdown
from google.cloud import logging as cloud_logging
# from flask import Flask, current_app

def configure_cloud_logging(app: Flask):
    if app.config['ENV'] == 'production':  # Asume producción si quieres usar Cloud Logging solo en producción
        client = cloud_logging.Client()
        # Configura Cloud Logging con el entorno de ejecución de Python
        client.setup_logging()

load_dotenv()


# Environment configuration should be done outside of create_app for global access
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

def get_google_provider_cfg():
    """Fetches Google's OpenID configuration."""
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def create_app():
    app = Flask(__name__)

    # Configure session
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    # Configure Flask to use /tmp for session files
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
    # app.config["SESSION_FILE_DIR"] = "/tmp/flask_session_files"
    app.config['ENV'] = 'development'  # O 'production', según corresponda

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




    @app.route("/login")
    def login():
        """Redirect to Google's OAuth2 login page."""
        # Assuming `oauth.google` is correctly configured elsewhere in your application
        redirect_uri = url_for('callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri=redirect_uri, scope="openid email profile")




    # @app.route("/login")
    # def login():
    #     """Redirect to Google's OAuth2 login page."""
    #     google_provider_cfg = get_google_provider_cfg()
    #     print(f"Google Provider Config: {google_provider_cfg}")
    #     authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    #     print(f"Authorization Endpoint: {authorization_endpoint}")

    #     request_uri = oauth.google.authorize_redirect(
    #         redirect_uri=url_for('callback', _external=True),
    #         scope="openid email profile"
    #     )
    #     print(f"Redirecting to: {request_uri}")  # Debugging line
    #     return redirect(request_uri)

    # @app.route("/login")
    # def login():
    #     """Redirect to Google's OAuth2 login page."""
    #     google_provider_cfg = get_google_provider_cfg()
    #     authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    #     request_uri = oauth.google.authorize_redirect(
    #         redirect_uri=url_for('callback', _external=True),
    #         # scope=["openid", "email", "profile"]
    #         scope="openid email profile"
    #     )
    #     return redirect(request_uri)
    


    # @app.route("/login")
    # def login():
    #     """Redirect to Google's OAuth2 login page."""
    #     google_provider_cfg = get_google_provider_cfg()
    #     authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    #     # request_uri = oauth.google.authorize_redirect(redirect_uri=url_for('callback', _external=True))
    #         # scopes that let you retrieve user's profile from Google
    #     request_uri = google_client.prepare_request_uri(
    #         authorization_endpoint,
    #         redirect_uri=request.base_url + "/callback",
    #         scope=["openid", "email", "profile"],
    #     )
    #     return redirect(request_uri)
    
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

    from oauthlib.oauth2 import WebApplicationClient  # For Google authentication
    google_client = WebApplicationClient(GOOGLE_CLIENT_ID)  # You need to set your Google Client ID here

    @app.route("/login/callback")
    def callback():
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
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        # Parse the tokens!
        google_client.parse_request_body_response(json.dumps(token_response.json()))

        # Now that you have tokens (yay) let's find and hit the URL
        # from Google that gives you the user's profile information,
        # including their Google profile image and email
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = google_client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        # You want to make sure their email is verified.
        # The user authenticated with Google, authorized your
        # app, and now you've verified their email through Google!
        if userinfo_response.json().get("email_verified"):
            unique_id = userinfo_response.json()["sub"]
            users_email = userinfo_response.json()["email"]
            picture = userinfo_response.json()["picture"]
            users_name = userinfo_response.json()["given_name"]

            
            # Check if user exists, if not, create new user in our 'database'
            user = User.get(unique_id)
            if not user:
                User.create(unique_id, users_name, users_email, picture)
                user = User.get(unique_id)
            
            # Begin user session
            session['user'] = user.__dict__

            # Redirect to the homepage or dashboard
            return redirect(url_for("index"))
        

        else:
            return "User email not available or not verified by Google.", 400

    ## EXERCISES ROUTES
        
    @app.route('/get_exercises')
    def get_exercises():
        df = pd.read_csv('./exercises/exercises.csv')
        return jsonify(df.to_dict(orient='records'))

    def preprocess_latex_for_mathjax(latex_content):
        # Simple replacement; for demonstration purposes only
        # A robust solution would require actual LaTeX parsing
        latex_content = latex_content.replace(r'\begin{enumerate}', '<ol>')
        latex_content = latex_content.replace(r'\end{enumerate}', '</ol>')
        latex_content = latex_content.replace(r'\item', '<li>')
        # Close the list item
        latex_content = latex_content.replace(r'</li><li>', '</li>\n<li>')
        latex_content = latex_content.replace(r'\begin{center}', '<div style="text-align: center;">').replace(r'\end{center}', '</div>')
        return latex_content

    def get_exercise_content(filename):
        # Assuming your exercise text files are stored in a directory named 'exercises'
        exercises_dir = 'exercises'
        filepath = os.path.join(exercises_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
                # Optional: Wrap LaTeX content in delimiters here if necessary
                content = preprocess_latex_for_mathjax(content)
                return content
        except FileNotFoundError:
            return "Exercise content not found."
        

    def get_exercise_id_from_filename(filename):
        # Extract the exercise ID from the filename
        df = pd.read_csv('exercises/exercises.csv')
        id = df.loc[df.file == filename, 'id'].values[0]
        return id

    @app.route('/exercises/<filename>')
    def exercise(filename):
        content = get_exercise_content(filename)
        exercise_id = get_exercise_id_from_filename(filename)
        # Pass the content to your template, possibly also passing additional data needed for rendering
        return render_template('exercise.html', content=content, exercise_id=exercise_id)

    def record_interaction(user_details, exercise_id, response, evaluated_response):
        interaction = {
            "user_id": user_details.get('id_'),
            "user_name": user_details.get('name'),
            "user_email": user_details.get('email'),
            "exercise_id": exercise_id,
            "response": response,
            "evaluated_response": evaluated_response
        }
        # Use the /tmp directory for compatibility with GCP's environment
        interactions_file_path = '/tmp/interactions.json'
        try:
            with open(interactions_file_path, 'r+') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []  # If the file is empty and causing errors
                data.append(interaction)
                file.seek(0)
                file.truncate()  # Clear the file before re-writing
                json.dump(data, file, indent=4)
        except FileNotFoundError:
            with open(interactions_file_path, 'w') as file:
                json.dump([interaction], file, indent=4)
            with open('/interactions.json', 'w') as file:
                json.dump([interaction], file, indent=4)



    @app.route('/submit_answer', methods=['POST'])
    def submit():
        app.logger.info("Current user session data: %s", session.get('user'))

        if 'user' not in session:
            app.logger.info("User not in session, redirecting to login")
            return redirect(url_for('login'))

        user_details = session.get('user')
        if not user_details:
            app.logger.info("User details not found in session, redirecting to index")
            return redirect(url_for('index'))

        exercise_id = request.form.get('exercise_id')
        response = request.form.get('response')
        app.logger.info("Received exercise_id: %s and response.", exercise_id)

        # Fetch the exercise content based on the exercise_id
        exercise_content = get_exercise_content(exercise_id)
        app.logger.info("Fetched exercise content for exercise_id: %s", exercise_id)

        evaluator = Evaluator()
        evaluated_response = evaluator.evaluate(exercise_content, response)
        app.logger.info("Evaluated response.")

        # Convert Markdown to HTML
        evaluated_response_html = markdown.markdown(evaluated_response)
        app.logger.info("Converted Markdown to HTML.")

        # Record the interaction with all details
        record_interaction(user_details, exercise_id, response, evaluated_response)
        app.logger.info("Recorded interaction.")

        # Pass the HTML-formatted response to the template
        app.logger.info("Rendering template with evaluated response.")
        return render_template('feedback.html', evaluated_response=evaluated_response_html, exercise_id=exercise_id)

    
    @app.route('/logout')
    def logout():
        session.clear()  # Clear Flask session
        return redirect(url_for('index'))  # Redirect to the index page

    @app.route('/health')
    def health():
        return jsonify({"status": "up"}), 200
    

    configure_cloud_logging(app)

    app.config.get('ENV', 'production')

    def configure_logging(app: Flask):
        if app.config['ENV'] == 'production':
            # Configuración de Google Cloud Logging
            configure_cloud_logging(app)
        else:
            import logging
            app.logger.setLevel(logging.DEBUG)
            # from logging.handlers import RotatingFileHandler
            # # Configuración local de logs, p.ej. a consola o archivo local
            # '''Configure logging for the application.'''
            # logging.basicConfig(level=logging.INFO)
            # logger = logging.getLogger(__name__)
            # handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
            # logger.addHandler(handler)
            # return logger


    configure_logging(app)

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
