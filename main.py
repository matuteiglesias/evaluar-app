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


from flask import Flask, render_template, request, redirect, url_for
from exercise import Exercise
from database import Database
from evaluator import Evaluator
app = Flask(__name__)
exercise = Exercise()
database = Database()
evaluator = Evaluator()


@app.route('/submit', methods=['POST'])
def submit():
    response = request.form['response']
    # Log the submission event
    logger.info(f"Exercise submitted by user: {response}")
    database.save_interaction(response)
    evaluated_response = evaluator.evaluate(response)
    return redirect(url_for('index', evaluated_response=evaluated_response))
if __name__ == '__main__':
    app.run()

@app.route('/submit', methods=['POST'])
def index():
    evaluated_response = request.args.get('evaluated_response')
    # Log the access event
    logger.info("Exercise accessed")
    return render_template('index.html', prompt=exercise.get_prompt(), evaluated_response=evaluated_response)
