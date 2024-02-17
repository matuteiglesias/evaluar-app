'''
This is the main file of the educational platform.
'''


import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
logger.addHandler(handler)


from flask import Flask, render_template, request, redirect, session, url_for
from authlib.integrations.flask_client import OAuth

from flask_session import Session  # For managing user sessions
from oauthlib.oauth2 import WebApplicationClient  # For Google authentication

import requests
import os
import pymysql

from dotenv import load_dotenv
load_dotenv()  # This method will load environment variables from a .env file


# Google OAuth2 Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)



app = Flask(__name__)
# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Google OAuth2 client setup
google_client = WebApplicationClient(GOOGLE_CLIENT_ID)  # You need to set your Google Client ID here

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


###

app.secret_key = 'your_secret_key'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_CLIENT_SECRET',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid profile email'},
)



@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = google_client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

    # return google.authorize_redirect(redirect_uri=url_for('auth', _external=True))

# class User:
#     # This is a simple in-memory store for users
#     users = {}

#     def __init__(self, id_, name, email, profile_pic):
#         self.id = id_
#         self.name = name
#         self.email = email
#         self.profile_pic = profile_pic

#     @classmethod
#     def get(cls, user_id):
#         # Returns the user instance if exists, else None
#         return cls.users.get(user_id)

#     @classmethod
#     def create(cls, user_id, name, email, profile_pic):
#         # Creates a new user and adds it to the users dictionary
#         if user_id not in cls.users:
#             cls.users[user_id] = User(user_id, name, email, profile_pic)


# A simple in-memory 'database' to store user info
users_db = {}

class User:
    def __init__(self, id_, name, email, profile_pic):
        self.id = id_
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



from flask import session
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
    import json
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



    # Create a user in your db with the information provided
    # by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    # Doesn't exist? Add it to the database.
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)

        # Begin user session by logging the user in
    # Begin user session by logging the user in
    session['user'] = user

    # Send user back to homepage
    return redirect(url_for("index"))




@app.route('/exercise/<int:id>')
def exercise(id):
    if 'user' in session:
        # Fetch exercise details from the database using the id
        exercise = get_exercise_by_id(id)  # Placeholder function, implement as needed
        return render_template('exercise.html', exercise=exercise)
    else:
        return redirect(url_for('login'))



# from database import Database

import pandas as pd

def load_exercises_from_csv(csv_file_path):
    df = pd.read_csv(csv_file_path)
    return df


def get_exercise_by_id(exercise_id):
    df = load_exercises_from_csv('exercises/exercises.csv')  # Assuming 'exercises.csv' is your file name
    exercise_row = df.loc[df['id'] == exercise_id]
    if not exercise_row.empty:
        # Convert the row to a dictionary for easier use in templates
        exercise = exercise_row.to_dict('records')[0]
        
        text_file = './exercises/' + exercise_row['file']
        with open(text_file, 'r') as file:
            exercise['text'] = file.read()
            
        return exercise
    else:
        return None

@app.route('/')
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


# @app.route('/submit', methods=['POST'])
# def submit():
#     response = request.form['response']
#     # Log the submission event
#     logger.info(f"Exercise submitted by user: {response}")
#     database.save_interaction(response)
#     evaluated_response = evaluator.evaluate(response)
#     return redirect(url_for('index', evaluated_response=evaluated_response))
# if __name__ == '__main__':
#     app.run()

# @app.route('/submit', methods=['POST'])
# def index():
#     evaluated_response = request.args.get('evaluated_response')
#     # Log the access event
#     logger.info("Exercise accessed")
#     return render_template('index.html', prompt=exercise.get_prompt(), evaluated_response=evaluated_response)



import json

def record_interaction(user_id, exercise_id, response):
    interaction = {
        "user_id": user_id,
        "exercise_id": exercise_id,
        "response": response
    }
    try:
        with open('interactions.json', 'r+') as file:
            data = json.load(file)
            data.append(interaction)
            file.seek(0)
            json.dump(data, file, indent=4)
    except FileNotFoundError:
        with open('interactions.json', 'w') as file:
            json.dump([interaction], file, indent=4)


@app.route('/submit', methods=['POST'])
def submit():
    if 'user' in session:
        user_id = session['user']['id_']  # Adjust according to how you store user ID in session
        exercise_id = request.form.get('exercise_id')
        response = request.form['response']
        record_interaction(user_id, exercise_id, response)
        # You may want to evaluate the response here and provide feedback
        evaluated_response = "Your response has been recorded."  # Placeholder
        return redirect(url_for('exercise', id=exercise_id, evaluated_response=evaluated_response))
    else:
        return redirect(url_for('login'))
